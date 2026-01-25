"""Abstract base class for terminal backend implementations.

This module defines the interface that all terminal backends must implement.
This abstraction allows the monitor to work with different terminal
multiplexers (tmux, WezTerm) using a common interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionInfo:
    """Standardized session information across backends.

    All terminal backends return session information in this format,
    allowing the rest of the application to be backend-agnostic.
    """

    name: str  # Session name (e.g., "claude-project-abc123")
    pane_id: str  # Backend-specific pane/session identifier
    created: str  # Unix timestamp or ISO string
    attached: bool  # Whether a client is attached
    windows: int  # Number of windows/panes
    pane_pid: Optional[int]  # PID of process in pane
    pane_tty: Optional[str]  # TTY path (e.g., /dev/ttys001)
    pane_path: Optional[str]  # Current working directory


class TerminalBackend(ABC):
    """Abstract interface for terminal multiplexer backends.

    This defines the contract that all terminal backends must implement.
    The interface is designed to support common operations needed by
    the Claude Headspace monitor:

    - Session discovery and listing
    - Session creation and termination
    - Sending text/commands to sessions
    - Capturing terminal output
    - Window focus control
    """

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the backend identifier (e.g., 'tmux', 'wezterm').

        Returns:
            String identifier for this backend.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend is installed and available.

        Returns:
            True if the backend binary is available, False otherwise.
            Result may be cached for performance.
        """
        pass

    @abstractmethod
    def list_sessions(self) -> list[dict]:
        """List all active sessions.

        Returns:
            List of session dicts with keys:
            - name: Session name
            - created: Creation timestamp
            - attached: Whether session is attached
            - windows: Number of windows
        """
        pass

    @abstractmethod
    def session_exists(self, session_name: str) -> bool:
        """Check if a session with the given name exists.

        Args:
            session_name: The session name to check.

        Returns:
            True if session exists, False otherwise.
        """
        pass

    @abstractmethod
    def get_claude_sessions(self) -> list[SessionInfo]:
        """Get sessions matching the claude-* naming pattern.

        Returns:
            List of SessionInfo objects for Claude sessions.
        """
        pass

    @abstractmethod
    def create_session(
        self,
        session_name: str,
        working_dir: Optional[str] = None,
        command: Optional[str] = None,
    ) -> bool:
        """Create a new detached session.

        Args:
            session_name: Name for the new session.
            working_dir: Working directory for the session.
            command: Optional command to run in the session.

        Returns:
            True if session created successfully, False otherwise.
        """
        pass

    @abstractmethod
    def kill_session(self, session_name: str) -> bool:
        """Terminate a session.

        Args:
            session_name: Name of the session to kill.

        Returns:
            True if session killed successfully, False otherwise.
        """
        pass

    @abstractmethod
    def send_keys(
        self,
        session_name: str,
        text: str,
        enter: bool = True,
        correlation_id: Optional[str] = None,
        log_operation: bool = False,
    ) -> bool:
        """Send text to a session.

        Args:
            session_name: Target session name.
            text: Text to send.
            enter: If True, append Enter key after text.
            correlation_id: Optional ID to link with corresponding capture.
            log_operation: If True, log this operation.

        Returns:
            True if send successful, False otherwise.
        """
        pass

    @abstractmethod
    def capture_pane(
        self,
        session_name: str,
        lines: int = 100,
        start_line: Optional[int] = None,
        correlation_id: Optional[str] = None,
        log_operation: bool = False,
    ) -> Optional[str]:
        """Capture terminal content from a session.

        Args:
            session_name: Target session name.
            lines: Number of lines to capture from scrollback.
            start_line: Optional start line (negative for scrollback).
            correlation_id: Optional ID to link with corresponding send.
            log_operation: If True, log this operation.

        Returns:
            Captured text content, or None on failure.
        """
        pass

    @abstractmethod
    def get_session_info(self, session_name: str) -> Optional[SessionInfo]:
        """Get detailed information about a session.

        Args:
            session_name: Target session name.

        Returns:
            SessionInfo with session details, or None if session doesn't exist.
        """
        pass

    @abstractmethod
    def focus_window(self, session_name: str) -> bool:
        """Bring the terminal window containing this session to foreground.

        Args:
            session_name: Name of the session to focus.

        Returns:
            True if focus successful, False otherwise.
        """
        pass
