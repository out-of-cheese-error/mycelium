"""
Terminal router: WebSocket PTY via tmux sessions + terminal chat endpoint.

Each workspace gets a persistent tmux session with two windows:
  - "main" (window 0): User's interactive shell, attached via WebSocket
  - "llm"  (window 1): Hidden shell for LLM tool command execution
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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.terminal_session_service import terminal_session_service

router = APIRouter(prefix="/terminal", tags=["terminal"])


# ---------------------------------------------------------------------------
# WebSocket terminal (attaches to tmux "main" window)
# ---------------------------------------------------------------------------


@router.websocket("/{workspace_id}/ws")
async def terminal_websocket(workspace_id: str, ws: WebSocket):
    await ws.accept()

    # Ensure tmux session exists for this workspace
    session_name = terminal_session_service.ensure_session(workspace_id)

    # Detach any stale clients from previous connections so they don't
    # constrain the window size for our new client.
    stale = subprocess.run(
        ["tmux", "list-clients", "-t", session_name, "-F", "#{client_name}"],
        capture_output=True, text=True,
    )
    for client in stale.stdout.strip().split("\n"):
        if client.strip():
            subprocess.run(
                ["tmux", "detach-client", "-t", client.strip()],
                capture_output=True,
            )

    # Create PTY at generous initial size — the real size arrives shortly
    # from fitAddon.fit() on the frontend and we resize dynamically.
    master_fd, slave_fd = pty.openpty()
    winsize = struct.pack("HHHH", 50, 200, 0, 0)  # rows=50, cols=200
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

    # Get the slave PTY device path before we close it — needed for
    # establishing the controlling terminal in the child process.
    slave_name = os.ttyname(slave_fd)

    def _setup_child():
        """Create new session and establish controlling terminal.

        setsid() gives the child its own session (needed for killpg cleanup)
        but removes its controlling terminal. Re-opening the slave PTY
        makes it the controlling terminal, so SIGWINCH from TIOCSWINSZ
        reaches tmux and triggers proper resizing.
        """
        os.setsid()
        ctty_fd = os.open(slave_name, os.O_RDWR)
        os.close(ctty_fd)

    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"

    process = subprocess.Popen(
        ["tmux", "attach-session", "-t", session_name],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        preexec_fn=_setup_child,
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
                data = await loop.run_in_executor(None, _blocking_read, master_fd)
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

            # Binary data -> terminal input
            if "bytes" in message and message["bytes"]:
                os.write(master_fd, message["bytes"])

            # Text data -> JSON control messages (resize, etc.)
            if "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")

                    if msg_type == "resize":
                        cols = data.get("cols", 80)
                        rows = data.get("rows", 24)
                        print(f"[terminal] resize: {cols}x{rows}")
                        # Resize the PTY (sends SIGWINCH to tmux attach)
                        winsize = struct.pack("HHHH", rows, cols, 0, 0)
                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                        # Also force tmux to resize the window directly
                        rz = subprocess.run(
                            [
                                "tmux", "resize-window",
                                "-t", f"{session_name}:main",
                                "-x", str(cols), "-y", str(rows),
                            ],
                            capture_output=True, text=True,
                        )
                        if rz.returncode != 0:
                            print(f"[terminal] resize-window failed: {rz.stderr}")
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
        # Kill the tmux-attach process only, NOT the tmux session itself
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


# ---------------------------------------------------------------------------
# Terminal chat endpoint (LLM translates natural language -> shell commands)
# ---------------------------------------------------------------------------


class TerminalChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class TerminalChatRequest(BaseModel):
    message: str
    history: list[TerminalChatMessage] = []


TERMINAL_SYSTEM_PROMPT = """You are a terminal assistant. The user describes what they want to do, \
and you execute shell commands using the run_terminal_command tool.

Rules:
- Always use the run_terminal_command tool to execute commands — never just suggest commands.
- Explain briefly what you're about to do before executing.
- If a command fails, diagnose the error and try an alternative.
- Be concise in your explanations.
- You can chain multiple commands if needed to accomplish the user's goal.
- The terminal is inside a Docker container (Debian-based) in a workspace directory.
- Commands you run are also shown in the user's visible terminal, so they can follow along."""


@router.post("/{workspace_id}/chat")
async def terminal_chat(workspace_id: str, request: TerminalChatRequest):
    """Terminal chat — LLM translates natural language to shell commands."""
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )
    from langchain_core.tools import tool

    from app.llm_config import llm_config

    # Ensure tmux session exists
    terminal_session_service.ensure_session(workspace_id)

    @tool
    async def run_terminal_command(command: str) -> str:
        """Execute a shell command in the workspace terminal and return the output.
        The command is also sent to the user's visible terminal."""
        return await terminal_session_service.execute_command_visible(
            workspace_id, command, timeout=30.0
        )

    llm = llm_config.get_chat_llm()
    llm_with_tools = llm.bind_tools([run_terminal_command])

    # Build messages with conversation history
    messages = [SystemMessage(content=TERMINAL_SYSTEM_PROMPT)]
    for msg in request.history:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant" and msg.content:
            messages.append(AIMessage(content=msg.content))
    messages.append(HumanMessage(content=request.message))

    async def event_generator():
        nonlocal messages
        max_iterations = 5

        try:
            for _iteration in range(max_iterations):
                response = await llm_with_tools.ainvoke(messages)
                messages.append(response)

                # Yield any text content the LLM produced
                if response.content:
                    # Handle content that might be a list (some providers)
                    if isinstance(response.content, list):
                        for block in response.content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                yield block["text"]
                            elif isinstance(block, str):
                                yield block
                    else:
                        yield response.content

                # If no tool calls, we're done
                if not hasattr(response, "tool_calls") or not response.tool_calls:
                    break

                # Execute tool calls
                for tc in response.tool_calls:
                    cmd = tc["args"].get("command", "")
                    yield f"\n> `{cmd}`\n"

                    result = await terminal_session_service.execute_command_visible(
                        workspace_id, cmd, timeout=30.0
                    )
                    messages.append(
                        ToolMessage(content=result, tool_call_id=tc["id"])
                    )

                    if result.strip():
                        yield f"\n```\n{result}\n```\n"
                    else:
                        yield "\n*(no output)*\n"

        except Exception as e:
            print(f"[terminal chat] error: {e}")
            import traceback

            traceback.print_exc()
            yield f"\n[Error: {str(e)}]"

    return StreamingResponse(event_generator(), media_type="text/plain")
