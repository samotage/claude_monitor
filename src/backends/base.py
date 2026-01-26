"""Abstract base class for terminal backend implementations.

Defines the interface for terminal multiplexer integrations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SessionInfo:
    """Information about a terminal session."""

    session_id: str  # Backend-specific identifier (pane_id for WezTerm)
    name: str  # Human-readable name (e.g., "claude-myproject-abc123")
    pid: int | None = None  # Process ID running in the session
    tty: str | None = None  # TTY path (e.g., /dev/ttys001)
    cwd: str | None = None  # Current working directory
    title: str | None = None  # Window/pane title (may contain spinner for activity)


class TerminalBackend(ABC):
    """Abstract interface for terminal backends.

    Terminal backends provide the ability to:
    - Discover running sessions
    - Capture terminal content
    - Send text to sessions
    - Focus/activate panes
    """

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the backend identifier (e.g., 'wezterm', 'tmux')."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend is installed and running.

        Returns:
            True if the backend can be used, False otherwise.
        """

    @abstractmethod
    def list_sessions(self) -> list[SessionInfo]:
        """List all active sessions.

        Returns:
            List of SessionInfo for each active session.
        """

    @abstractmethod
    def get_content(self, session_id: str, lines: int = 100) -> str | None:
        """Capture terminal content from a session.

        Args:
            session_id: The session identifier.
            lines: Number of lines to capture from scrollback.

        Returns:
            Terminal content as string, or None on failure.
        """

    @abstractmethod
    def send_text(self, session_id: str, text: str, enter: bool = True) -> bool:
        """Send text to a session.

        Args:
            session_id: The session identifier.
            text: Text to send.
            enter: If True, append Enter key after text.

        Returns:
            True if send successful, False otherwise.
        """

    @abstractmethod
    def focus_pane(self, session_id: str) -> bool:
        """Bring the pane/window to foreground.

        Args:
            session_id: The session identifier.

        Returns:
            True if focus successful, False otherwise.
        """

    def get_claude_sessions(self) -> list[SessionInfo]:
        """Get sessions that appear to be Claude Code sessions.

        Default implementation filters by 'claude-' prefix in name.

        Returns:
            List of SessionInfo for Claude sessions.
        """
        return [s for s in self.list_sessions() if s.name.startswith("claude-")]
