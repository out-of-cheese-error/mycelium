"""
WebSocket endpoint that spawns a PTY shell inside the Docker container,
giving browser-based terminal access via xterm.js on the frontend.
"""

import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import subprocess
import termios

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/terminal", tags=["terminal"])

MEMORY_BASE_DIR = os.environ.get("MEMORY_BASE_DIR", "./memory_data")


@router.websocket("/ws")
async def terminal_websocket(ws: WebSocket):
    await ws.accept()

    # Create pseudo-terminal pair
    master_fd, slave_fd = pty.openpty()

    # Build environment for the shell
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"

    # Spawn bash attached to the slave PTY
    process = subprocess.Popen(
        ["/bin/bash"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        preexec_fn=os.setsid,
        cwd=MEMORY_BASE_DIR,
        env=env,
    )
    os.close(slave_fd)  # parent only needs master

    # Make master_fd non-blocking for the async read loop
    flag = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)

    loop = asyncio.get_event_loop()

    async def read_pty_output():
        """Read from PTY master and forward to WebSocket."""
        while True:
            try:
                data = await loop.run_in_executor(
                    None, _blocking_read, master_fd
                )
                if data is None:
                    break  # fd closed / process exited
                if data:
                    await ws.send_bytes(data)
            except OSError:
                break
            except Exception:
                break

    read_task = asyncio.create_task(read_pty_output())

    try:
        while True:
            message = await ws.receive()

            if message["type"] == "websocket.disconnect":
                break

            # Binary data → terminal input
            if "bytes" in message and message["bytes"]:
                os.write(master_fd, message["bytes"])

            # Text data → JSON control messages (resize, etc.)
            if "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")

                    if msg_type == "resize":
                        cols = data.get("cols", 80)
                        rows = data.get("rows", 24)
                        winsize = struct.pack("HHHH", rows, cols, 0, 0)
                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                except (json.JSONDecodeError, KeyError):
                    pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[terminal] WebSocket error: {e}")
    finally:
        read_task.cancel()
        try:
            os.close(master_fd)
        except OSError:
            pass
        # Kill the entire process group to clean up child processes
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def _blocking_read(fd: int):
    """Blocking read wrapper for use inside run_in_executor.

    Uses select to wait for data with a short timeout so the executor
    thread can be reclaimed promptly when the task is cancelled.
    Returns bytes on success, b"" on timeout, None on fd closed.
    """
    import select as _select

    try:
        readable, _, _ = _select.select([fd], [], [], 0.1)
        if readable:
            data = os.read(fd, 4096)
            return data if data else None  # empty read = fd closed
        return b""  # timeout, no data yet
    except (OSError, ValueError):
        return None  # fd closed
