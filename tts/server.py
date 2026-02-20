"""
VibeVoice TTS + ASR HTTP Streaming Server

Adapted from the VibeVoice WebSocket demo (demo/web/app.py) to serve
HTTP POST streaming responses compatible with the MyCelium backend
audio router contract (backend/app/routers/audio.py).

TTS Endpoint: POST /v1/stream
  Body: {"input": str, "voice": str, "response_format": "pcm"}
  Response: streaming PCM16 bytes (24kHz, mono, 16-bit)

ASR Endpoint: POST /v1/transcribe
  Body: raw PCM16 bytes (16kHz, mono, 16-bit)
  Response: {"text": str, "language": str}
"""

import asyncio
import copy
import os
import threading
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

import numpy as np
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from faster_whisper import WhisperModel

from vibevoice.modular.modeling_vibevoice_streaming_inference import (
    VibeVoiceStreamingForConditionalGenerationInference,
)
from vibevoice.processor.vibevoice_streaming_processor import (
    VibeVoiceStreamingProcessor,
)
from vibevoice.modular.streamer import AudioStreamer

SAMPLE_RATE = 24_000


class StreamingTTSService:
    """Loads VibeVoice-Realtime-0.5B and provides a streaming generator.

    Adapted from the upstream demo/web/app.py StreamingTTSService with
    the only structural change being a configurable voices directory
    (via VOICES_DIR env var instead of hardcoded relative path).
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        inference_steps: int = 5,
    ) -> None:
        self.model_path = model_path
        self.inference_steps = inference_steps
        self.sample_rate = SAMPLE_RATE

        self.processor: Optional[VibeVoiceStreamingProcessor] = None
        self.model: Optional[VibeVoiceStreamingForConditionalGenerationInference] = None
        self.voice_presets: Dict[str, Path] = {}
        self.default_voice_key: Optional[str] = None
        self._voice_cache: Dict[str, object] = {}

        if device == "mpx":
            device = "mps"
        if device == "mps" and not torch.backends.mps.is_available():
            print("Warning: MPS not available. Falling back to CPU.")
            device = "cpu"
        self.device = device
        self._torch_device = torch.device(device)

    def load(self) -> None:
        print(f"[startup] Loading processor from {self.model_path}")
        self.processor = VibeVoiceStreamingProcessor.from_pretrained(self.model_path)

        if self.device == "mps":
            load_dtype = torch.float32
            device_map = None
            attn_impl_primary = "sdpa"
        elif self.device == "cuda":
            load_dtype = torch.bfloat16
            device_map = "cuda"
            attn_impl_primary = "flash_attention_2"
        else:
            load_dtype = torch.float32
            device_map = "cpu"
            attn_impl_primary = "sdpa"

        print(f"Using device: {device_map}, torch_dtype: {load_dtype}, attn: {attn_impl_primary}")

        try:
            self.model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                self.model_path,
                torch_dtype=load_dtype,
                device_map=device_map,
                attn_implementation=attn_impl_primary,
            )
            if self.device == "mps":
                self.model.to("mps")
        except Exception as e:
            if attn_impl_primary == "flash_attention_2":
                print("flash_attention_2 failed, falling back to sdpa")
                self.model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                    self.model_path,
                    torch_dtype=load_dtype,
                    device_map=self.device,
                    attn_implementation="sdpa",
                )
            else:
                raise e

        self.model.eval()
        self.model.model.noise_scheduler = self.model.model.noise_scheduler.from_config(
            self.model.model.noise_scheduler.config,
            algorithm_type="sde-dpmsolver++",
            beta_schedule="squaredcos_cap_v2",
        )
        self.model.set_ddpm_inference_steps(num_steps=self.inference_steps)

        self.voice_presets = self._load_voice_presets()
        preset_name = os.environ.get("VOICE_PRESET")
        self.default_voice_key = self._determine_voice_key(preset_name)
        self._ensure_voice_cached(self.default_voice_key)
        print(f"[startup] Default voice: {self.default_voice_key}")

    def _load_voice_presets(self) -> Dict[str, Path]:
        voices_dir = Path(os.environ.get("VOICES_DIR", "/app/voices/streaming_model"))
        if not voices_dir.exists():
            raise RuntimeError(f"Voices directory not found: {voices_dir}")

        presets: Dict[str, Path] = {}
        for pt_path in voices_dir.rglob("*.pt"):
            presets[pt_path.stem] = pt_path

        if not presets:
            raise RuntimeError(f"No voice preset (.pt) files found in {voices_dir}")

        print(f"[startup] Found {len(presets)} voice presets: {sorted(presets.keys())}")
        return dict(sorted(presets.items()))

    def _determine_voice_key(self, name: Optional[str]) -> str:
        if name and name in self.voice_presets:
            return name
        default_key = "en-Emma_woman"
        if default_key in self.voice_presets:
            return default_key
        first_key = next(iter(self.voice_presets))
        return first_key

    def _ensure_voice_cached(self, key: str) -> object:
        if key not in self.voice_presets:
            raise RuntimeError(f"Voice preset {key!r} not found")
        if key not in self._voice_cache:
            preset_path = self.voice_presets[key]
            print(f"[voices] Loading preset {key} from {preset_path}")
            prefilled_outputs = torch.load(
                preset_path,
                map_location=self._torch_device,
                weights_only=False,
            )
            self._voice_cache[key] = prefilled_outputs
        return self._voice_cache[key]

    def _get_voice_resources(self, requested_key: Optional[str]) -> Tuple[str, object]:
        key = requested_key if requested_key and requested_key in self.voice_presets else self.default_voice_key
        if key is None:
            key = next(iter(self.voice_presets))
            self.default_voice_key = key
        prefilled_outputs = self._ensure_voice_cached(key)
        return key, prefilled_outputs

    def _prepare_inputs(self, text: str, prefilled_outputs: object):
        if not self.processor or not self.model:
            raise RuntimeError("StreamingTTSService not initialized")
        processed = self.processor.process_input_with_cached_prompt(
            text=text.strip(),
            cached_prompt=prefilled_outputs,
            padding=True,
            return_tensors="pt",
            return_attention_mask=True,
        )
        prepared = {
            key: value.to(self._torch_device) if hasattr(value, "to") else value
            for key, value in processed.items()
        }
        return prepared

    def _run_generation(
        self,
        inputs,
        audio_streamer: AudioStreamer,
        errors,
        cfg_scale: float,
        do_sample: bool,
        temperature: float,
        top_p: float,
        refresh_negative: bool,
        prefilled_outputs,
        stop_event: threading.Event,
    ) -> None:
        try:
            self.model.generate(
                **inputs,
                max_new_tokens=None,
                cfg_scale=cfg_scale,
                tokenizer=self.processor.tokenizer,
                generation_config={
                    "do_sample": do_sample,
                    "temperature": temperature if do_sample else 1.0,
                    "top_p": top_p if do_sample else 1.0,
                },
                audio_streamer=audio_streamer,
                stop_check_fn=stop_event.is_set,
                verbose=False,
                refresh_negative=refresh_negative,
                all_prefilled_outputs=copy.deepcopy(prefilled_outputs),
            )
        except Exception as exc:
            errors.append(exc)
            traceback.print_exc()
            audio_streamer.end()

    def stream(
        self,
        text: str,
        cfg_scale: float = 1.5,
        do_sample: bool = False,
        temperature: float = 0.9,
        top_p: float = 0.9,
        refresh_negative: bool = True,
        inference_steps: Optional[int] = None,
        voice_key: Optional[str] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> Iterator[np.ndarray]:
        if not text.strip():
            return
        text = text.replace("\u2019", "'")

        selected_voice, prefilled_outputs = self._get_voice_resources(voice_key)

        steps_to_use = self.inference_steps
        if inference_steps is not None:
            try:
                parsed_steps = int(inference_steps)
                if parsed_steps > 0:
                    steps_to_use = parsed_steps
            except (TypeError, ValueError):
                pass
        if self.model:
            self.model.set_ddpm_inference_steps(num_steps=steps_to_use)
        self.inference_steps = steps_to_use

        inputs = self._prepare_inputs(text, prefilled_outputs)
        audio_streamer = AudioStreamer(batch_size=1, stop_signal=None, timeout=None)
        errors: list = []
        stop_signal = stop_event or threading.Event()

        thread = threading.Thread(
            target=self._run_generation,
            kwargs={
                "inputs": inputs,
                "audio_streamer": audio_streamer,
                "errors": errors,
                "cfg_scale": cfg_scale,
                "do_sample": do_sample,
                "temperature": temperature,
                "top_p": top_p,
                "refresh_negative": refresh_negative,
                "prefilled_outputs": prefilled_outputs,
                "stop_event": stop_signal,
            },
            daemon=True,
        )
        thread.start()

        try:
            stream = audio_streamer.get_stream(0)
            for audio_chunk in stream:
                if torch.is_tensor(audio_chunk):
                    audio_chunk = audio_chunk.detach().cpu().to(torch.float32).numpy()
                else:
                    audio_chunk = np.asarray(audio_chunk, dtype=np.float32)

                if audio_chunk.ndim > 1:
                    audio_chunk = audio_chunk.reshape(-1)

                peak = np.max(np.abs(audio_chunk)) if audio_chunk.size else 0.0
                if peak > 1.0:
                    audio_chunk = audio_chunk / peak

                yield audio_chunk.astype(np.float32, copy=False)
        finally:
            stop_signal.set()
            audio_streamer.end()
            thread.join()
            if errors:
                raise errors[0]

    @staticmethod
    def chunk_to_pcm16(chunk: np.ndarray) -> bytes:
        chunk = np.clip(chunk, -1.0, 1.0)
        pcm = (chunk * 32767.0).astype(np.int16)
        return pcm.tobytes()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

class TTSRequest(BaseModel):
    input: str
    voice: str = "en-Emma_woman"
    response_format: str = "pcm"


app = FastAPI(title="VibeVoice TTS Service")

_inference_lock = asyncio.Lock()


ASR_SAMPLE_RATE = 16_000


@app.on_event("startup")
async def _startup() -> None:
    model_path = os.environ.get("MODEL_PATH", "microsoft/VibeVoice-Realtime-0.5B")
    device = os.environ.get("MODEL_DEVICE", "cuda")

    service = StreamingTTSService(model_path=model_path, device=device)
    service.load()

    app.state.tts_service = service
    print(f"[startup] VibeVoice TTS ready on {device}")

    # Load faster-whisper ASR model
    asr_model_size = os.environ.get("ASR_MODEL", "tiny")
    asr_device = os.environ.get("ASR_DEVICE", device)
    # Use int8 on CUDA to minimize VRAM, float32 on CPU/MPS
    compute_type = "int8" if asr_device == "cuda" else "float32"
    print(f"[startup] Loading faster-whisper ASR model: {asr_model_size} on {asr_device} ({compute_type})")
    app.state.asr_model = WhisperModel(asr_model_size, device=asr_device, compute_type=compute_type)
    print(f"[startup] ASR model ready")


@app.post("/v1/stream")
async def stream_tts(request: TTSRequest):
    """Stream PCM16 audio for the given text.

    Compatible with the MyCelium backend audio router which POSTs here
    and expects raw PCM16 bytes (24 kHz, mono, 16-bit).
    """
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="Empty input text")

    service: StreamingTTSService = app.state.tts_service

    voice_key = request.voice
    if voice_key not in service.voice_presets:
        voice_key = service.default_voice_key

    async def generate_pcm():
        async with _inference_lock:
            stop_event = threading.Event()
            iterator = service.stream(
                text=request.input,
                voice_key=voice_key,
                stop_event=stop_event,
            )
            sentinel = object()
            try:
                while True:
                    chunk = await asyncio.to_thread(next, iterator, sentinel)
                    if chunk is sentinel:
                        break
                    yield service.chunk_to_pcm16(chunk)
            finally:
                stop_event.set()
                close_fn = getattr(iterator, "close", None)
                if callable(close_fn):
                    close_fn()

    return StreamingResponse(
        generate_pcm(),
        media_type="application/octet-stream",
    )


@app.get("/v1/voices")
async def list_voices():
    service: StreamingTTSService = app.state.tts_service
    return {
        "voices": sorted(service.voice_presets.keys()),
        "default": service.default_voice_key,
    }


@app.post("/v1/transcribe")
async def transcribe(request: Request):
    """Transcribe raw PCM16 audio (16kHz, mono, 16-bit) to text.

    Accepts raw bytes in the request body. Returns JSON with transcribed text.
    """
    audio_bytes = await request.body()
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Audio too short")

    # Convert PCM16 bytes to float32 numpy array
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    asr: WhisperModel = app.state.asr_model
    language = os.environ.get("ASR_LANGUAGE", None)  # None = auto-detect

    segments, info = asr.transcribe(
        audio_np,
        language=language if language else None,
        beam_size=1,
        vad_filter=True,
    )
    text = " ".join(seg.text for seg in segments).strip()
    return {"text": text, "language": info.language}


@app.get("/v1/asr/health")
async def asr_health():
    has_asr = hasattr(app.state, "asr_model") and app.state.asr_model is not None
    return {"status": "ok" if has_asr else "not loaded"}


@app.get("/health")
async def health():
    has_asr = hasattr(app.state, "asr_model") and app.state.asr_model is not None
    return {"status": "ok", "model": "VibeVoice-Realtime-0.5B", "asr": has_asr}
