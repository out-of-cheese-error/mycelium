"""
WebSocket endpoint for live voice calls with the LLM.

Flow: Browser mic → WS binary → accumulate → ASR → LLM (streaming) → TTS → WS binary → speaker
"""

import asyncio
import json
import os
import re

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, AIMessage

from app.agent import app_agent, run_background_extraction_and_emotions
from app.llm_config import llm_config
from app.utils.thinking import strip_thinking, extract_thinking
from app.routers.audio import _clean_for_tts

router = APIRouter(prefix="/call", tags=["call"])

MEMORY_BASE_DIR = os.environ.get("MEMORY_BASE_DIR", "./memory_data")

# Sentence boundary regex: split on . ! ? followed by whitespace or end
_SENTENCE_END = re.compile(r'[.!?]\s+|[.!?]$|\n')


def _get_thread_path(workspace_id: str, thread_id: str) -> str:
    return os.path.join(MEMORY_BASE_DIR, workspace_id, "threads", f"{thread_id}.json")


def _load_thread(path: str) -> dict:
    with open(path, 'r') as f:
        return json.load(f)


def _save_thread(path: str, data: dict) -> None:
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _build_langchain_messages(stored_messages: list) -> list:
    msgs = []
    for m in stored_messages:
        if m["role"] == "user":
            msgs.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            msgs.append(AIMessage(content=m["content"]))
    return msgs


async def _transcribe(audio_pcm: bytes) -> dict:
    """Send raw PCM16 audio to the TTS container's /v1/transcribe endpoint."""
    cfg = llm_config.get_config()
    base = cfg.tts_base_url.rstrip("/")
    # tts_base_url is like http://tts:8100/v1, transcribe is at /v1/transcribe
    url = f"{base}/transcribe"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            content=audio_pcm,
            headers={"Content-Type": "application/octet-stream"},
        )
        resp.raise_for_status()
        return resp.json()


async def _stream_llm_and_tts(
    ws: WebSocket,
    transcript: str,
    workspace_id: str,
    thread_path: str,
    thread_data: dict,
    cancelled: asyncio.Event,
):
    """Run LLM on the transcript, stream response text to client, and pipe sentences to TTS."""
    cfg = llm_config.get_config()

    # Build message history
    stored = thread_data.get("messages", [])
    langchain_messages = _build_langchain_messages(stored)
    langchain_messages.append(HumanMessage(content=transcript))

    initial_state = {
        "messages": langchain_messages,
        "context": "",
        "workspace_id": workspace_id,
        "voice_mode": True,
    }

    full_raw = ""
    sentence_buffer = ""

    await ws.send_json({"type": "state", "state": "thinking"})

    try:
        async for event in app_agent.astream_events(
            initial_state, version="v1", config={"recursion_limit": 100}
        ):
            if cancelled.is_set():
                break

            kind = event["event"]
            if kind == "on_chat_model_stream":
                if event.get("metadata", {}).get("langgraph_node") == "generate":
                    content = event["data"]["chunk"].content
                    if not content:
                        continue

                    full_raw += content
                    sentence_buffer += content

                    # Send text chunk to client for display
                    await ws.send_json({"type": "response_text", "text": content, "done": False})

                    # Check for sentence boundary → send to TTS
                    if _SENTENCE_END.search(sentence_buffer):
                        text_to_speak = sentence_buffer.strip()
                        sentence_buffer = ""
                        if text_to_speak and not cancelled.is_set():
                            await ws.send_json({"type": "state", "state": "speaking"})
                            await _stream_tts_to_ws(ws, text_to_speak, cancelled)

    except Exception as e:
        print(f"[call] LLM streaming error: {e}")
        import traceback
        traceback.print_exc()
        await ws.send_json({"type": "error", "message": str(e)})

    # Flush remaining sentence buffer
    if sentence_buffer.strip() and not cancelled.is_set():
        await ws.send_json({"type": "state", "state": "speaking"})
        await _stream_tts_to_ws(ws, sentence_buffer.strip(), cancelled)

    await ws.send_json({"type": "response_text", "text": "", "done": True})

    # Strip thinking from full response for storage
    _, clean_response = extract_thinking(full_raw)
    clean_response = strip_thinking(clean_response) if clean_response else full_raw

    # Save to thread
    thread_data["messages"].append({"role": "user", "content": transcript})
    thread_data["messages"].append({"role": "assistant", "content": clean_response})
    _save_thread(thread_path, thread_data)

    # Fire background extraction and emotion update (non-blocking)
    import threading
    t = threading.Thread(
        target=run_background_extraction_and_emotions,
        args=(workspace_id, transcript, clean_response),
        daemon=True
    )
    t.start()


async def _stream_tts_to_ws(ws: WebSocket, text: str, cancelled: asyncio.Event):
    """Stream TTS audio from the TTS container back to the WebSocket client as binary frames."""
    cfg = llm_config.get_config()
    if not cfg.tts_enabled:
        return

    # Strip emojis and non-speech symbols that make TTS produce gibberish
    text = _clean_for_tts(text)
    if not text:
        return

    base = cfg.tts_base_url.rstrip("/")
    url = f"{base}/stream"
    payload = {
        "input": text,
        "voice": cfg.tts_voice,
        "response_format": "pcm",
    }

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            req = client.build_request("POST", url, json=payload)
            resp = await client.send(req, stream=True)
            async for chunk in resp.aiter_bytes(chunk_size=4096):
                if cancelled.is_set():
                    break
                await ws.send_bytes(chunk)
            await resp.aclose()
    except Exception as e:
        print(f"[call] TTS streaming error: {e}")


@router.websocket("/ws")
async def call_websocket(ws: WebSocket):
    await ws.accept()

    workspace_id = None
    thread_id = None
    thread_path = None
    thread_data = None
    audio_buffer = bytearray()
    cancelled = asyncio.Event()
    current_task: asyncio.Task | None = None

    try:
        while True:
            message = await ws.receive()

            if message["type"] == "websocket.disconnect":
                break

            # Binary frame = microphone audio
            if "bytes" in message and message["bytes"]:
                audio_buffer.extend(message["bytes"])
                continue

            # Text frame = JSON control message
            if "text" not in message:
                continue

            data = json.loads(message["text"])
            msg_type = data.get("type")

            if msg_type == "start_call":
                workspace_id = data.get("workspace_id")
                thread_id = data.get("thread_id")
                if not workspace_id or not thread_id:
                    await ws.send_json({"type": "error", "message": "workspace_id and thread_id required"})
                    continue

                thread_path = _get_thread_path(workspace_id, thread_id)
                if not os.path.exists(thread_path):
                    await ws.send_json({"type": "error", "message": "Thread not found"})
                    continue

                thread_data = _load_thread(thread_path)
                audio_buffer.clear()
                cancelled.clear()
                await ws.send_json({"type": "call_started"})
                await ws.send_json({"type": "state", "state": "listening"})

            elif msg_type == "vad_speech_end":
                if not workspace_id or not thread_data:
                    continue

                audio = bytes(audio_buffer)
                audio_buffer.clear()

                if len(audio) < 1600:  # Less than 50ms of 16kHz audio
                    await ws.send_json({"type": "state", "state": "listening"})
                    continue

                # Transcribe
                await ws.send_json({"type": "state", "state": "thinking"})
                try:
                    result = await _transcribe(audio)
                    transcript = result.get("text", "").strip()
                except Exception as e:
                    print(f"[call] ASR error: {e}")
                    await ws.send_json({"type": "error", "message": f"Transcription failed: {e}"})
                    await ws.send_json({"type": "state", "state": "listening"})
                    continue

                if not transcript:
                    await ws.send_json({"type": "state", "state": "listening"})
                    continue

                await ws.send_json({"type": "transcript", "text": transcript, "final": True})

                # Reload thread data (may have been saved by a prior turn)
                thread_data = _load_thread(thread_path)

                # Run LLM + TTS pipeline
                cancelled.clear()
                current_task = asyncio.create_task(
                    _stream_llm_and_tts(ws, transcript, workspace_id, thread_path, thread_data, cancelled)
                )
                await current_task
                current_task = None

                # Back to listening
                await ws.send_json({"type": "state", "state": "listening"})

            elif msg_type == "interrupt":
                cancelled.set()
                audio_buffer.clear()
                if current_task and not current_task.done():
                    current_task.cancel()
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        pass
                current_task = None
                cancelled.clear()
                await ws.send_json({"type": "state", "state": "listening"})

            elif msg_type == "end_call":
                cancelled.set()
                if current_task and not current_task.done():
                    current_task.cancel()
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        pass
                await ws.send_json({"type": "call_ended"})
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[call] WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cancelled.set()
        if current_task and not current_task.done():
            current_task.cancel()
