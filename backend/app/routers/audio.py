from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import re
import httpx
from app.llm_config import llm_config

# Strip emojis and other non-speech symbols that cause TTS to produce gibberish
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols, extended-A
    "\U0001FA70-\U0001FAFF"  # symbols extended-A continued
    "\U00002702-\U000027B0"  # dingbats
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero width joiner
    "\U000020E3"             # combining enclosing keycap
    "\U00002600-\U000026FF"  # misc symbols (checkboxes, stars, etc.)
    "\U00002300-\U000023FF"  # misc technical
    "]+",
    flags=re.UNICODE,
)

def _strip_markdown(text: str) -> str:
    """Remove common markdown formatting artifacts for cleaner TTS output."""
    text = re.sub(r'```[\s\S]*?```', '', text)           # code blocks
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)  # headers
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)   # bold/italic
    text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text)      # underscored bold/italic
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)  # images
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)   # links
    text = re.sub(r'`([^`]+)`', r'\1', text)               # inline code
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)  # horizontal rules
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)  # blockquotes
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)   # unordered list markers
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)   # ordered list markers
    return text

def _strip_references(text: str) -> str:
    """Remove citations, references, and wiki-style annotations."""
    text = re.sub(r'\[(?:Image|File|Category|Citation needed)[^\]]*\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[\d+\]', '', text)                # [1], [32]
    text = re.sub(r'\[[\w\s,]+\]', '', text)           # [a], [note 1], [edit]
    text = re.sub(r'\{\{[^}]*\}\}', '', text)          # {{template}} wiki markup
    return text

def _clean_for_tts(text: str) -> str:
    text = _strip_references(text)
    text = _strip_markdown(text)
    text = _EMOJI_RE.sub(" ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()

router = APIRouter(prefix="/audio", tags=["audio"])

class SpeechRequest(BaseModel):
    input: str

async def _stream_tts(text: str):
    cfg = llm_config.get_config()
    
    if not hasattr(cfg, 'tts_enabled') or not cfg.tts_enabled:
        raise HTTPException(status_code=400, detail="TTS is currently disabled in settings.")

    text = _clean_for_tts(text)
    if not text:
        raise HTTPException(status_code=400, detail="Nothing to speak after cleaning input.")

    base = cfg.tts_base_url.rstrip("/")
    url = f"{base}/stream"

    payload = {
        "input": text,
        "voice": cfg.tts_voice,
        "response_format": "pcm"
    }

    def create_wav_header():
        # WAV Header for 24kHz, 16-bit, mono
        # 44 bytes
        import struct
        
        sample_rate = 24000
        num_channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
        block_align = num_channels * (bits_per_sample // 8)
        
        # Set data size to a large number (approx 100MB) for streaming
        # Browsers usually handle "incorrect" lengths fine for playback
        data_size = 100 * 1024 * 1024 
        chunk_size = 36 + data_size
        
        header = b'RIFF'
        header += struct.pack('<I', chunk_size)
        header += b'WAVE'
        header += b'fmt '
        header += struct.pack('<I', 16) # Subchunk1Size
        header += struct.pack('<H', 1)  # AudioFormat (1=PCM)
        header += struct.pack('<H', num_channels)
        header += struct.pack('<I', sample_rate)
        header += struct.pack('<I', byte_rate)
        header += struct.pack('<H', block_align)
        header += struct.pack('<H', bits_per_sample)
        header += b'data'
        header += struct.pack('<I', data_size)
        return header

    async def iter_audio():
        # ... (httpx logic) implementation below
        pass

    # Improved implementation:
    client = httpx.AsyncClient(timeout=None)
    req = client.build_request("POST", url, json=payload)
    response = await client.send(req, stream=True)
    
    if response.status_code != 200:
        await response.aread() # Read error body
        print(f"TTS Error: {response.text}")
        await client.aclose()
        raise HTTPException(status_code=response.status_code, detail=f"TTS Provider Error: {response.text}")

    print(f"DEBUG: Wrapping PCM stream in WAV header (assuming 24kHz)")

    async def stream_response():
        try:
            yield create_wav_header()
            async for chunk in response.aiter_bytes(chunk_size=1024):
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_response(),
        media_type="audio/wav"
    )

@router.get("/test")
async def test_tts_connection():
    """Test connectivity to the TTS service."""
    cfg = llm_config.get_config()
    base = cfg.tts_base_url.rstrip("/")
    url = f"{base.rsplit('/v1', 1)[0]}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                # Also fetch available voices
                voices_url = f"{base}/voices"
                voices_resp = await client.get(voices_url)
                voices = voices_resp.json() if voices_resp.status_code == 200 else {}
                return {**data, **voices, "status": "connected"}
            return {"status": "error", "detail": f"TTS returned {response.status_code}"}
    except httpx.ConnectError:
        return {"status": "error", "detail": f"Cannot connect to {url}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@router.post("/speech")
async def generate_speech(request: SpeechRequest):
    return await _stream_tts(request.input)

@router.get("/stream")
async def stream_speech(input: str):
    return await _stream_tts(input)

@router.get("/extract-text")
async def extract_text_from_url(url: str):
    """Fetch a URL and return the extracted article text, cleaned for TTS."""
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.content, 'html.parser')

            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button", "iframe"]):
                tag.decompose()

            article = soup.find('article') or soup.find('main') or soup.find('body')
            text = article.get_text(separator="\n") if article else soup.get_text(separator="\n")

            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            if not text.strip():
                raise HTTPException(status_code=400, detail="No text could be extracted from the URL.")

            title_tag = soup.find('title')
            title = title_tag.get_text().strip() if title_tag else ""

            return {"title": title, "text": text}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch URL: {e}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach URL: {str(e)}")
