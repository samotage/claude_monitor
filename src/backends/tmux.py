"""DEPRECATED: tmux terminal backend.

This module is deprecated in favor of WezTerm. It is kept for the migration
period but will be removed in a future release.

Use src.backends.wezterm.WezTermBackend instead.
"""

import logging
import shutil
import subprocess
import warnings

from src.backends.base import SessionInfo, TerminalBackend

logger = logging.getLogger(__name__)

# Cache the tmux availability check
_tmux_available: bool | None = None


def _run_tmux(*args: str, timeout: int = 10) -> tuple[int, str, str]:
    """Run a tmux command.

    Args:
        *args: Command arguments to pass to tmux.
        timeout: Command timeout in seconds.

    Returns:
        Tuple of (return_code, stdout, stderr).
    """
    cmd = ["tmux", *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (result.returncode, result.stdout or "", result.stderr or "")
    except subprocess.TimeoutExpired:
        return (1, "", "Command timed out")
    except FileNotFoundError:
        return (1, "", "tmux not found")


class TmuxBackend(TerminalBackend):
    """DEPRECATED: tmux-based terminal backend.

    WARNING: This backend is deprecated. Use WezTermBackend instead.
    """

    def __init__(self):
        """Initialize the tmux backend with a deprecation warning."""
        warnings.warn(
            "TmuxBackend is deprecated. Use WezTermBackend instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning(
            "TmuxBackend is deprecated and will be removed in a future release. "
            "Please migrate to WezTermBackend."
        )

    @property
    def backend_name(self) -> str:
        """Return the backend identifier."""
        return "tmux"

    def is_available(self) -> bool:
        """Check if tmux is installed and a server is running.

        Returns:
            True if tmux is available, False otherwise.
        """
        global _tmux_available
        if _tmux_available is not None:
            return _tmux_available

        if shutil.which("tmux") is None:
            _tmux_available = False
            return False

        # Check if tmux server is running
        returncode, _, _ = _run_tmux("list-sessions")
        _tmux_available = returncode == 0
        return _tmux_available

    def list_sessions(self) -> list[SessionInfo]:
        """List all active tmux sessions.

        Returns:
            List of SessionInfo for each active session.
        """
        if not self.is_available():
            return []

        # Get session info with format string
        fmt = "#{session_name}|#{session_id}|#{pane_pid}|#{pane_tty}|#{pane_current_path}|#{pane_title}"
        returncode, stdout, _ = _run_tmux("list-panes", "-a", "-F", fmt)

        if returncode != 0:
            return []

        sessions = []
        for line in stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("|")
            if len(parts) < 6:
                continue

            name, session_id, pid_str, tty, cwd, title = parts[:6]

            try:
                pid = int(pid_str) if pid_str else None
            except ValueError:
                pid = None

            sessions.append(
                SessionInfo(
                    session_id=session_id,
                    name=name,
                    pid=pid,
                    tty=tty or None,
                    cwd=cwd or None,
                    title=title or None,
                )
            )

        return sessions

    def get_content(self, session_id: str, lines: int = 100) -> str | None:
        """Capture content from a tmux pane.

        Args:
            session_id: The session/pane identifier.
            lines: Number of lines to capture.

        Returns:
            Captured text, or None on failure.
        """
        if not self.is_available():
            return None

        args = ["capture-pane", "-t", session_id, "-p", "-S", str(-lines)]
        returncode, stdout, _ = _run_tmux(*args)

        if returncode != 0:
            return None

        return stdout

    def send_text(self, session_id: str, text: str, enter: bool = True) -> bool:
        """Send text to a tmux pane.

        Args:
            session_id: The session/pane identifier.
            text: Text to send.
            enter: If True, append Enter key.

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available():
            return False

        args = ["send-keys", "-t", session_id, text]
        if enter:
            args.append("Enter")

        returncode, _, _ = _run_tmux(*args)
        return returncode == 0

    def focus_pane(self, session_id: str) -> bool:
        """Focus a tmux pane.

        Note: tmux cannot bring a terminal window to foreground,
        only switch the active pane within tmux.

        Args:
            session_id: The session/pane identifier.

        Returns:
            True if pane selection successful, False otherwise.
        """
        if not self.is_available():
            return False

        returncode, _, _ = _run_tmux("select-pane", "-t", session_id)
        return returncode == 0


# Singleton instance
_backend_instance: TmuxBackend | None = None


def get_tmux_backend() -> TmuxBackend:
    """Get the singleton tmux backend instance.

    WARNING: This function is deprecated. Use get_wezterm_backend() instead.
    """
    global _backend_instance
    if _backend_instance is None:
        _backend_instance = TmuxBackend()
    return _backend_instance


def reset_tmux_backend() -> None:
    """Reset the singleton instance (for testing)."""
    global _backend_instance, _tmux_available
    _backend_instance = None
    _tmux_available = None
