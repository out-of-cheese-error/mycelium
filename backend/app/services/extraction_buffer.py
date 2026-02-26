"""
Per-workspace extraction buffer (Short-Term Memory).

Inspired by LightMem's ShortMemBufferManager: accumulates chat turns and
triggers batch extraction only when a threshold is reached, reducing LLM
API calls while giving the extraction LLM richer context.
"""

import threading
import time
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional


@dataclass
class BufferedTurn:
    """A single chat turn waiting to be extracted."""
    user_message: str
    ai_response: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class BufferConfig:
    """Thresholds that trigger extraction. Whichever is hit first wins."""
    turn_threshold: int = 5           # Max turns before forced extraction
    token_threshold: int = 2000       # Estimated token count of user messages
    time_threshold_seconds: int = 600  # Max seconds since last extraction (10 min)


class ExtractionBuffer:
    """
    Per-workspace buffer that accumulates (user_message, ai_response) pairs.
    Triggers batch extraction when any configured threshold is exceeded.
    """

    def __init__(self, workspace_id: str, config: Optional[BufferConfig] = None):
        self.workspace_id = workspace_id
        self.config = config or BufferConfig()
        self.turns: List[BufferedTurn] = []
        self._last_extraction_time: float = time.time()
        self._lock = threading.Lock()

    def add_turn(self, user_message: str, ai_response: str) -> bool:
        """
        Add a turn to the buffer.
        Returns True if extraction should be triggered.
        """
        with self._lock:
            self.turns.append(BufferedTurn(
                user_message=user_message,
                ai_response=ai_response,
                timestamp=time.time(),
            ))
            return self._should_trigger()

    def _should_trigger(self) -> bool:
        """Check if any threshold is exceeded."""
        if len(self.turns) >= self.config.turn_threshold:
            return True
        if self._estimate_tokens() >= self.config.token_threshold:
            return True
        if time.time() - self._last_extraction_time > self.config.time_threshold_seconds:
            return True
        return False

    def _estimate_tokens(self) -> int:
        """Rough token estimate: ~4 chars per token for user messages."""
        return sum(len(t.user_message) // 4 for t in self.turns)

    def flush(self) -> List[BufferedTurn]:
        """Return all buffered turns and clear the buffer."""
        with self._lock:
            turns = list(self.turns)
            self.turns.clear()
            self._last_extraction_time = time.time()
            return turns

    def is_empty(self) -> bool:
        with self._lock:
            return len(self.turns) == 0

    def save_to_disk(self, workspace_dir: str):
        """Persist buffer to disk for crash recovery."""
        path = os.path.join(workspace_dir, "extraction_buffer.json")
        with self._lock:
            data = [asdict(t) for t in self.turns]
        try:
            os.makedirs(workspace_dir, exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f)
            os.replace(tmp_path, path)
        except Exception as e:
            print(f"BG: Failed to save extraction buffer for {self.workspace_id}: {e}")

    def load_from_disk(self, workspace_dir: str):
        """Load persisted buffer on startup."""
        path = os.path.join(workspace_dir, "extraction_buffer.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            with self._lock:
                for item in data:
                    self.turns.append(BufferedTurn(
                        user_message=item["user_message"],
                        ai_response=item["ai_response"],
                        timestamp=item.get("timestamp", time.time()),
                    ))
            # Clean up the file after loading
            os.remove(path)
            print(f"BG: Restored {len(data)} buffered turns for {self.workspace_id}")
        except Exception as e:
            print(f"BG: Failed to load extraction buffer for {self.workspace_id}: {e}")


# ---------------------------------------------------------------------------
# Global buffer registry (one buffer per workspace)
# ---------------------------------------------------------------------------
_buffers: Dict[str, ExtractionBuffer] = {}
_buffers_lock = threading.Lock()

MEMORY_BASE_DIR = os.environ.get("MEMORY_BASE_DIR", "./memory_data")


def get_buffer(workspace_id: str, config: Optional[BufferConfig] = None) -> ExtractionBuffer:
    """Get or create the extraction buffer for a workspace."""
    with _buffers_lock:
        if workspace_id not in _buffers:
            buf = ExtractionBuffer(workspace_id, config)
            # Try to restore from disk
            ws_dir = os.path.join(MEMORY_BASE_DIR, workspace_id)
            buf.load_from_disk(ws_dir)
            _buffers[workspace_id] = buf
        return _buffers[workspace_id]


def flush_all_buffers():
    """
    Force-flush all workspace buffers. Called on server shutdown.
    Returns dict of workspace_id -> list of BufferedTurn for processing.
    """
    results: Dict[str, List[BufferedTurn]] = {}
    with _buffers_lock:
        for ws_id, buffer in _buffers.items():
            turns = buffer.flush()
            if turns:
                results[ws_id] = turns
    return results


def save_all_buffers():
    """Persist all buffers to disk. Called on server shutdown."""
    with _buffers_lock:
        for ws_id, buffer in _buffers.items():
            if not buffer.is_empty():
                ws_dir = os.path.join(MEMORY_BASE_DIR, ws_id)
                buffer.save_to_disk(ws_dir)


def restore_buffers_from_disk():
    """Scan all workspaces for persisted buffers and restore them."""
    if not os.path.exists(MEMORY_BASE_DIR):
        return
    for ws_name in os.listdir(MEMORY_BASE_DIR):
        ws_dir = os.path.join(MEMORY_BASE_DIR, ws_name)
        buf_path = os.path.join(ws_dir, "extraction_buffer.json")
        if os.path.isfile(buf_path):
            get_buffer(ws_name)  # This triggers load_from_disk
