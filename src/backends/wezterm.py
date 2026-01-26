"""WezTerm terminal backend for Claude Headspace.

Implements the TerminalBackend interface using the wezterm CLI.
"""

import contextlib
import json
import shutil
import subprocess

from src.backends.base import SessionInfo, TerminalBackend

# Cache the WezTerm availability check
_wezterm_available: bool | None = None


def _run_wezterm(*args: str, timeout: int = 10) -> tuple[int, str, str]:
    """Run a wezterm CLI command.

    Args:
        *args: Command arguments to pass to wezterm cli.
        timeout: Command timeout in seconds.

    Returns:
        Tuple of (return_code, stdout, stderr).
    """
    cmd = ["wezterm", "cli", *args]
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
        return (1, "", "wezterm not found")


class WezTermBackend(TerminalBackend):
    """WezTerm-based terminal backend.

    Uses the wezterm CLI to manage sessions, send text, and capture content.
    """

    # Session name to pane-id mapping cache
    _session_pane_map: dict[str, str]

    def __init__(self):
        """Initialize the WezTerm backend."""
        self._session_pane_map = {}

    @property
    def backend_name(self) -> str:
        """Return the backend identifier."""
        return "wezterm"

    def is_available(self) -> bool:
        """Check if WezTerm is installed and available.

        Returns:
            True if wezterm CLI is available, False otherwise.
        """
        global _wezterm_available
        if _wezterm_available is not None:
            return _wezterm_available

        _wezterm_available = shutil.which("wezterm") is not None
        return _wezterm_available

    def list_sessions(self) -> list[SessionInfo]:
        """List all active WezTerm panes.

        Uses 'wezterm cli list --format json' to get pane information.

        Returns:
            List of SessionInfo for each active pane.
        """
        if not self.is_available():
            return []

        returncode, stdout, _ = _run_wezterm("list", "--format", "json")
        if returncode != 0:
            return []

        try:
            panes = json.loads(stdout)
        except json.JSONDecodeError:
            return []

        sessions = []
        for pane in panes:
            pane_id = str(pane.get("pane_id", ""))
            title = pane.get("title", "")
            tab_title = pane.get("tab_title", "")

            # Prefer tab_title for session name when it identifies a Claude session
            # Tab titles persist even when Claude Code overwrites the pane title
            name = tab_title if tab_title.startswith("claude-") else title

            session = SessionInfo(
                session_id=pane_id,
                name=name,
                pid=pane.get("pid"),
                tty=pane.get("tty_name"),
                cwd=pane.get("cwd"),
                title=title,  # Raw pane title (has spinner chars for activity)
            )
            sessions.append(session)

            # Update session map if this looks like a Claude session
            if name.startswith("claude-"):
                self._session_pane_map[name] = pane_id

        return sessions

    def get_content(self, session_id: str, lines: int = 100) -> str | None:
        """Capture content from a WezTerm pane.

        Uses 'wezterm cli get-text' to capture pane content.

        Args:
            session_id: The pane ID.
            lines: Number of lines to capture from scrollback.

        Returns:
            Captured text content, or None on failure.
        """
        if not self.is_available():
            return None

        # WezTerm uses negative numbers for scrollback
        args = ["get-text", "--pane-id", session_id, "--start-line", str(-lines)]

        returncode, stdout, _ = _run_wezterm(*args)
        if returncode != 0:
            return None

        return stdout

    def send_text(self, session_id: str, text: str, enter: bool = True) -> bool:
        """Send text to a WezTerm pane.

        Uses 'wezterm cli send-text' to send text.

        Args:
            session_id: The pane ID.
            text: Text to send.
            enter: If True, append Enter key after text.

        Returns:
            True if send successful, False otherwise.
        """
        if not self.is_available():
            return False

        send_text = text + "\n" if enter else text

        # Use --no-paste to send raw text (not as a paste operation)
        args = ["send-text", "--pane-id", session_id, "--no-paste", send_text]

        returncode, _, _ = _run_wezterm(*args)
        return returncode == 0

    def focus_pane(self, session_id: str) -> bool:
        """Bring the WezTerm window to foreground.

        Uses 'wezterm cli activate-pane' and AppleScript for app activation.

        Args:
            session_id: The pane ID.

        Returns:
            True if focus successful, False otherwise.
        """
        if not self.is_available():
            return False

        returncode, _, _ = _run_wezterm("activate-pane", "--pane-id", session_id)
        if returncode != 0:
            return False

        # Also bring WezTerm application to foreground (macOS)
        with contextlib.suppress(Exception):
            subprocess.run(
                ["osascript", "-e", 'tell application "WezTerm" to activate'],
                capture_output=True,
                timeout=5,
            )

        return True

    def get_session_by_name(self, name: str) -> SessionInfo | None:
        """Get a session by its name.

        Args:
            name: The session name (e.g., "claude-myproject-abc123").

        Returns:
            SessionInfo if found, None otherwise.
        """
        # Check cache first
        if name in self._session_pane_map:
            pane_id = self._session_pane_map[name]
            # Verify pane still exists
            for session in self.list_sessions():
                if session.session_id == pane_id:
                    return session
            # Pane no longer exists, remove from cache
            del self._session_pane_map[name]

        # Search in current sessions
        for session in self.list_sessions():
            if session.name == name:
                return session

        return None

    def get_content_by_name(self, name: str, lines: int = 100) -> str | None:
        """Get content for a session by name.

        Args:
            name: The session name.
            lines: Number of lines to capture.

        Returns:
            Terminal content, or None if session not found.
        """
        session = self.get_session_by_name(name)
        if session is None:
            return None
        return self.get_content(session.session_id, lines)

    def send_text_by_name(self, name: str, text: str, enter: bool = True) -> bool:
        """Send text to a session by name.

        Args:
            name: The session name.
            text: Text to send.
            enter: If True, append Enter key.

        Returns:
            True if successful, False otherwise.
        """
        session = self.get_session_by_name(name)
        if session is None:
            return False
        return self.send_text(session.session_id, text, enter)

    def focus_by_name(self, name: str) -> bool:
        """Focus a session by name.

        Args:
            name: The session name.

        Returns:
            True if successful, False otherwise.
        """
        session = self.get_session_by_name(name)
        if session is None:
            return False
        return self.focus_pane(session.session_id)


# Singleton instance
_backend_instance: WezTermBackend | None = None


def get_wezterm_backend() -> WezTermBackend:
    """Get the singleton WezTerm backend instance."""
    global _backend_instance
    if _backend_instance is None:
        _backend_instance = WezTermBackend()
    return _backend_instance


def reset_wezterm_backend() -> None:
    """Reset the singleton instance (for testing)."""
    global _backend_instance, _wezterm_available
    _backend_instance = None
    _wezterm_available = None
