from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
from app.llm_config import llm_config

router = APIRouter(prefix="/audio", tags=["audio"])

class SpeechRequest(BaseModel):
    input: str

async def _stream_tts(text: str):
    cfg = llm_config.get_config()
    
    if not hasattr(cfg, 'tts_enabled') or not cfg.tts_enabled:
        raise HTTPException(status_code=400, detail="TTS is currently disabled in settings.")

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

@router.post("/speech")
async def generate_speech(request: SpeechRequest):
    return await _stream_tts(request.input)

@router.get("/stream")
async def stream_speech(input: str):
    return await _stream_tts(input)
