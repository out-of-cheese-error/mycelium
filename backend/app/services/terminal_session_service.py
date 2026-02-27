"""
Terminal Session Service

Manages tmux sessions per workspace. Each workspace gets a persistent
tmux session named 'mycelium-{workspace_id}' rooted at the workspace directory.

The interactive terminal (WebSocket) attaches to the tmux session.
LLM tool command execution uses direct subprocess for reliable output capture.
"""

import asyncio
import os
import subprocess

MEMORY_BASE_DIR = os.environ.get("MEMORY_BASE_DIR", "./memory_data")

# Helper script for visible command execution. Defines _mc() which
# runs a command, tees output to a temp file, and touches a done marker.
# The marker ID is read from /tmp/.mc_id (written by Python before each call).
_HELPER_PATH = "/tmp/.mc_fn"
_HELPER_SCRIPT = (
    '_mc() { local m=$(cat /tmp/.mc_id);'
    ' eval "$@" 2>&1 | tee /tmp/.mc_out_$m;'
    ' touch /tmp/.mc_done_$m; }\n'
)


def _ensure_helper():
    """Write the _mc helper function to a sourceable file."""
    try:
        with open(_HELPER_PATH, "w") as f:
            f.write(_HELPER_SCRIPT)
    except OSError:
        pass


class TerminalSessionService:
    """Manages tmux sessions for workspaces."""

    def _session_name(self, workspace_id: str) -> str:
        return f"mycelium-{workspace_id}"

    def _workspace_dir(self, workspace_id: str) -> str:
        path = os.path.join(MEMORY_BASE_DIR, workspace_id)
        os.makedirs(path, exist_ok=True)
        return os.path.abspath(path)

    def session_exists(self, workspace_id: str) -> bool:
        """Check if a tmux session exists for this workspace."""
        result = subprocess.run(
            ["tmux", "has-session", "-t", self._session_name(workspace_id)],
            capture_output=True,
        )
        return result.returncode == 0

    def ensure_session(self, workspace_id: str) -> str:
        """Create tmux session if it doesn't exist. Returns session name."""
        name = self._session_name(workspace_id)
        if not self.session_exists(workspace_id):
            cwd = self._workspace_dir(workspace_id)
            subprocess.run(
                [
                    "tmux", "new-session", "-d",
                    "-s", name,
                    "-n", "main",
                    "-c", cwd,
                    "-x", "200", "-y", "50",
                ],
                check=True,
            )
        # Always ensure correct options (covers both new and existing sessions)
        subprocess.run(
            ["tmux", "set-option", "-t", name, "window-size", "latest"],
            capture_output=True,
        )
        subprocess.run(
            ["tmux", "set-window-option", "-t", name, "aggressive-resize", "on"],
            capture_output=True,
        )
        # Hide tmux status bar — the xterm.js UI handles that
        subprocess.run(
            ["tmux", "set-option", "-t", name, "status", "off"],
            capture_output=True,
        )
        return name

    def kill_session(self, workspace_id: str):
        """Kill session for workspace (e.g., on workspace deletion)."""
        if self.session_exists(workspace_id):
            subprocess.run(
                ["tmux", "kill-session", "-t", self._session_name(workspace_id)],
                capture_output=True,
            )

    async def execute_command(
        self, workspace_id: str, command: str, timeout: float = 30.0
    ) -> str:
        """
        Execute a command in the workspace directory using subprocess.
        Returns combined stdout + stderr.
        """
        cwd = self._workspace_dir(workspace_id)
        loop = asyncio.get_event_loop()

        def _run():
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=timeout,
                    env={**os.environ, "TERM": "xterm-256color"},
                )
                output = result.stdout
                if result.stderr:
                    if output:
                        output += "\n"
                    output += result.stderr
                return output.strip() if output else "(no output)"
            except subprocess.TimeoutExpired:
                return f"[Command timed out after {timeout}s]"
            except Exception as e:
                return f"[Error: {e}]"

        return await loop.run_in_executor(None, _run)

    async def execute_command_visible(
        self, workspace_id: str, command: str, timeout: float = 30.0
    ) -> str:
        """Execute a command in the visible tmux terminal and capture output.

        Uses the _mc helper function so the user sees a clean command like:
            . /tmp/.mc_fn;_mc 'ls -la'
        The command runs ONCE in the visible terminal; output is captured
        via a temp file for the LLM.
        """
        import time as _time

        name = self._session_name(workspace_id)
        if not self.session_exists(workspace_id):
            return await self.execute_command(workspace_id, command, timeout)

        _ensure_helper()

        loop = asyncio.get_event_loop()
        marker = os.urandom(4).hex()

        def _run():
            # Write marker ID so the _mc function knows which temp files to use
            with open("/tmp/.mc_id", "w") as f:
                f.write(marker)

            # Escape single quotes in the command for safe wrapping
            escaped = command.replace("'", "'\\''")
            # User sees: . /tmp/.mc_fn;_mc 'ls -la'
            wrapped = f". {_HELPER_PATH};_mc '{escaped}'"
            subprocess.run(
                ["tmux", "send-keys", "-t", f"{name}:main", wrapped, "Enter"],
                capture_output=True,
            )

            # Poll for the done marker
            done_path = f"/tmp/.mc_done_{marker}"
            out_path = f"/tmp/.mc_out_{marker}"
            start = _time.time()
            while _time.time() - start < timeout:
                _time.sleep(0.3)
                if os.path.exists(done_path):
                    break

            # Read captured output
            output = ""
            try:
                with open(out_path) as f:
                    output = f.read().strip()
            except FileNotFoundError:
                output = "(command sent to terminal)"

            # Cleanup
            for path in (out_path, done_path):
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass

            return output or "(no output)"

        return await loop.run_in_executor(None, _run)

    def resize_session(self, workspace_id: str, cols: int, rows: int):
        """Resize the tmux session's main window."""
        if self.session_exists(workspace_id):
            subprocess.run(
                [
                    "tmux", "resize-window",
                    "-t", f"{self._session_name(workspace_id)}:main",
                    "-x", str(cols), "-y", str(rows),
                ],
                capture_output=True,
            )


# Singleton instance
terminal_session_service = TerminalSessionService()
