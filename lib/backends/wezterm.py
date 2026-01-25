"""WezTerm terminal backend for Claude Headspace.

This module provides WezTerm integration using the wezterm CLI.
It implements the TerminalBackend interface defined in base.py.

Key advantages over tmux:
- Native GUI integration (no separate terminal emulator needed)
- Full scrollback access via get-text
- Built-in workspaces for session organization
- Cross-platform window focus via activate-pane
- No tmux installation required

Session Naming:
WezTerm uses numeric pane-ids rather than named sessions. To maintain
the claude-{slug}-{hash} naming convention, we:
1. Use window/pane titles for identification
2. Maintain an in-memory mapping of session names to pane-ids
3. Use workspaces to group Claude sessions
"""

import hashlib
import json
import re
import shutil
import subprocess
import time
from typing import Optional

from lib.backends.base import SessionInfo, TerminalBackend
from lib.terminal_logging import create_terminal_log_entry, write_terminal_log_entry

# Cache the WezTerm availability check (cleared on module reload)
_wezterm_available: Optional[bool] = None

# Debug logging toggle - can be set by monitor.py from config
_debug_logging_enabled: bool = False

# Session name to pane-id mapping cache
# Key: session name (e.g., "claude-myproject-abc123")
# Value: pane-id (integer as string)
_session_pane_map: dict[str, str] = {}

# Session first-seen time cache (for elapsed time calculation)
# Key: session name
# Value: Unix timestamp (float) when the session was first discovered
_session_first_seen: dict[str, float] = {}


def set_debug_logging(enabled: bool) -> None:
    """Set the debug logging mode for WezTerm operations.

    Args:
        enabled: If True, full payloads are logged. If False, only events.
    """
    global _debug_logging_enabled
    _debug_logging_enabled = enabled


def get_debug_logging() -> bool:
    """Get the current debug logging mode.

    Returns:
        True if debug logging is enabled, False otherwise.
    """
    return _debug_logging_enabled


def _log_wezterm_event(
    session_name: str,
    direction: str,
    event_type: str,
    payload: Optional[str] = None,
    correlation_id: Optional[str] = None,
    success: bool = True,
) -> None:
    """Log a WezTerm operation event.

    Uses the same logging infrastructure as tmux for consistency.

    Args:
        session_name: The session name
        direction: "in" or "out"
        event_type: Type of operation
        payload: Message content
        correlation_id: Links related operations
        success: Whether operation succeeded
    """
    # Extract session_id from session name
    session_id = session_name
    if session_name.startswith("claude-"):
        session_id = session_name[7:]

    entry = create_terminal_log_entry(
        session_id=session_id,
        tmux_session_name=session_name,  # Reuse field for WezTerm session
        direction=direction,
        event_type=event_type,
        payload=payload,
        correlation_id=correlation_id,
        success=success,
        debug_enabled=_debug_logging_enabled,
        backend="wezterm",
    )
    write_terminal_log_entry(entry)


def _run_wezterm(*args: str, timeout: int = 10) -> tuple[int, str, str]:
    """Run a wezterm CLI command and return the result.

    Args:
        *args: Command arguments to pass to wezterm cli
        timeout: Command timeout in seconds

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd = ["wezterm", "cli"] + list(args)
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
    """WezTerm-based terminal backend implementation.

    This backend uses the wezterm CLI to manage sessions, send text,
    and capture terminal content. It provides cross-platform support
    and improved capabilities over tmux.
    """

    def __init__(self):
        """Initialize the WezTerm backend."""
        pass

    @property
    def backend_name(self) -> str:
        """Return the backend identifier."""
        return "wezterm"

    def is_available(self) -> bool:
        """Check if WezTerm is installed and available.

        Returns:
            True if wezterm CLI is available, False otherwise.
            Result is cached for performance.
        """
        global _wezterm_available
        if _wezterm_available is not None:
            return _wezterm_available

        _wezterm_available = shutil.which("wezterm") is not None
        return _wezterm_available

    def list_sessions(self) -> list[dict]:
        """List all active WezTerm panes.

        Uses 'wezterm cli list --format json' to get pane information.

        Returns:
            List of session dicts with keys:
            - name: Pane title (may be the session name)
            - pane_id: WezTerm pane ID
            - created: Empty (WezTerm doesn't expose creation time)
            - attached: Always True (WezTerm panes are always attached)
            - windows: Always 1
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
            # Extract pane info
            pane_id = str(pane.get("pane_id", ""))
            title = pane.get("title", "")
            tab_title = pane.get("tab_title", "")
            workspace = pane.get("workspace", "")

            # Prefer tab_title for session name when it identifies a Claude
            # session.  Tab titles persist even when Claude Code overwrites
            # the pane title to "✳ Claude Code".
            if tab_title.startswith("claude-"):
                name = tab_title
            else:
                name = title

            sessions.append({
                "name": name,
                "pane_id": pane_id,
                "title": title,  # Raw pane title (has spinner chars for activity detection)
                "created": "",  # WezTerm doesn't expose creation time
                "attached": True,
                "windows": 1,
                "workspace": workspace,
            })

            # Update session map if this looks like a Claude session
            if name.startswith("claude-"):
                _session_pane_map[name] = pane_id
                # Track first-seen time for elapsed calculation
                if name not in _session_first_seen:
                    _session_first_seen[name] = time.time()

        return sessions

    def session_exists(self, session_name: str) -> bool:
        """Check if a session with the given name exists.

        Checks both the cache and live pane list.

        Args:
            session_name: The session name to check

        Returns:
            True if session exists, False otherwise
        """
        if not self.is_available():
            return False

        # Check cache first
        if session_name in _session_pane_map:
            # Verify the pane still exists
            pane_id = _session_pane_map[session_name]
            returncode, stdout, _ = _run_wezterm("list", "--format", "json")
            if returncode == 0:
                try:
                    panes = json.loads(stdout)
                    for pane in panes:
                        if str(pane.get("pane_id", "")) == pane_id:
                            return True
                except json.JSONDecodeError:
                    pass
            # Pane no longer exists, remove from caches
            del _session_pane_map[session_name]
            _session_first_seen.pop(session_name, None)
            return False

        # Search by title in live pane list
        sessions = self.list_sessions()
        for session in sessions:
            if session.get("name") == session_name:
                return True

        return False

    def get_claude_sessions(self) -> list[SessionInfo]:
        """Get all WezTerm panes that appear to be Claude Code sessions.

        Looks for panes with titles matching the pattern 'claude-*'.

        Returns:
            List of SessionInfo objects for Claude sessions
        """
        if not self.is_available():
            return []

        all_sessions = self.list_sessions()
        claude_sessions = []

        for session in all_sessions:
            name = session.get("name", "")
            if name.startswith("claude-"):
                info = self.get_session_info(name)
                if info:
                    claude_sessions.append(info)

        return claude_sessions

    def create_session(
        self,
        session_name: str,
        working_dir: Optional[str] = None,
        command: Optional[str] = None,
    ) -> bool:
        """Create a new WezTerm pane.

        Uses 'wezterm cli spawn' to create a new window, then sets the
        tab title to the session name for persistent identification.
        Tab titles survive Claude Code overwriting the pane title.

        Args:
            session_name: Name for the new session (set as tab title)
            working_dir: Working directory for the session
            command: Optional command to run in the session

        Returns:
            True if session created successfully, False otherwise
        """
        if not self.is_available():
            return False

        if self.session_exists(session_name):
            return False  # Session already exists

        args = ["spawn", "--new-window"]

        if working_dir:
            args.extend(["--cwd", working_dir])

        args.append("--")

        if command:
            args.extend(["bash", "-c", command])
        else:
            args.append("$SHELL")

        returncode, stdout, _ = _run_wezterm(*args)

        if returncode == 0:
            # The output contains the new pane-id
            pane_id = stdout.strip()
            if pane_id:
                # Set tab title for persistent session identification
                _run_wezterm("set-tab-title", "--pane-id", pane_id, session_name)
                _session_pane_map[session_name] = pane_id
            return True

        return False

    def kill_session(self, session_name: str) -> bool:
        """Kill a WezTerm pane.

        Args:
            session_name: Name of the session to kill

        Returns:
            True if session killed successfully, False otherwise
        """
        if not self.is_available():
            return False

        pane_id = self._get_pane_id(session_name)
        if not pane_id:
            return False

        returncode, _, _ = _run_wezterm("kill-pane", "--pane-id", pane_id)

        if returncode == 0:
            # Remove from caches
            _session_pane_map.pop(session_name, None)
            _session_first_seen.pop(session_name, None)
            return True

        return False

    def send_keys(
        self,
        session_name: str,
        text: str,
        enter: bool = True,
        correlation_id: Optional[str] = None,
        log_operation: bool = False,
    ) -> bool:
        """Send text to a WezTerm pane.

        Uses 'wezterm cli send-text' to send text to the pane.

        Args:
            session_name: Target session name
            text: Text to send
            enter: If True, append Enter key after text
            correlation_id: Optional ID to link with corresponding capture
            log_operation: If True, log this operation

        Returns:
            True if send successful, False otherwise
        """
        if not self.is_available():
            if log_operation:
                _log_wezterm_event(
                    session_name=session_name,
                    direction="out",
                    event_type="send_attempted",
                    payload=text,
                    correlation_id=correlation_id,
                    success=False,
                )
            return False

        pane_id = self._get_pane_id(session_name)
        if not pane_id:
            if log_operation:
                _log_wezterm_event(
                    session_name=session_name,
                    direction="out",
                    event_type="send_attempted",
                    payload=text,
                    correlation_id=correlation_id,
                    success=False,
                )
            return False

        # Build the text to send
        send_text = text
        if enter:
            send_text += "\n"

        # Use --no-paste to send raw text (not as a paste operation)
        args = ["send-text", "--pane-id", pane_id, "--no-paste", send_text]

        returncode, _, _ = _run_wezterm(*args)
        success = returncode == 0

        if log_operation:
            _log_wezterm_event(
                session_name=session_name,
                direction="out",
                event_type="send_keys",
                payload=text,
                correlation_id=correlation_id,
                success=success,
            )

        return success

    def capture_pane(
        self,
        session_name: str,
        lines: int = 100,
        start_line: Optional[int] = None,
        correlation_id: Optional[str] = None,
        log_operation: bool = False,
    ) -> Optional[str]:
        """Capture content from a WezTerm pane.

        Uses 'wezterm cli get-text' to capture pane content.
        Unlike tmux, WezTerm supports full scrollback access.

        Args:
            session_name: Target session name
            lines: Number of lines to capture from scrollback
            start_line: Optional start line (negative for scrollback)
            correlation_id: Optional ID to link with corresponding send
            log_operation: If True, log this operation

        Returns:
            Captured text content, or None on failure
        """
        if not self.is_available():
            if log_operation:
                _log_wezterm_event(
                    session_name=session_name,
                    direction="in",
                    event_type="capture_attempted",
                    correlation_id=correlation_id,
                    success=False,
                )
            return None

        pane_id = self._get_pane_id(session_name)
        if not pane_id:
            if log_operation:
                _log_wezterm_event(
                    session_name=session_name,
                    direction="in",
                    event_type="capture_attempted",
                    correlation_id=correlation_id,
                    success=False,
                )
            return None

        args = ["get-text", "--pane-id", pane_id]

        # WezTerm uses 0 for first screen line, negative for scrollback
        if start_line is not None:
            args.extend(["--start-line", str(start_line)])
        else:
            # Default: capture last N lines from scrollback
            args.extend(["--start-line", str(-lines)])

        returncode, stdout, _ = _run_wezterm(*args)

        if returncode != 0:
            if log_operation:
                _log_wezterm_event(
                    session_name=session_name,
                    direction="in",
                    event_type="capture_attempted",
                    correlation_id=correlation_id,
                    success=False,
                )
            return None

        if log_operation:
            _log_wezterm_event(
                session_name=session_name,
                direction="in",
                event_type="capture_pane",
                payload=stdout,
                correlation_id=correlation_id,
                success=True,
            )

        return stdout

    def get_session_info(self, session_name: str) -> Optional[SessionInfo]:
        """Get detailed information about a WezTerm session.

        Args:
            session_name: Target session name

        Returns:
            SessionInfo with session details, or None if session doesn't exist
        """
        if not self.is_available():
            return None

        pane_id = self._get_pane_id(session_name)
        if not pane_id:
            return None

        # Get pane info from list
        returncode, stdout, _ = _run_wezterm("list", "--format", "json")
        if returncode != 0:
            return None

        try:
            panes = json.loads(stdout)
        except json.JSONDecodeError:
            return None

        for pane in panes:
            if str(pane.get("pane_id", "")) == pane_id:
                # Use first-seen time as creation timestamp (Unix epoch)
                # WezTerm doesn't expose pane creation time natively
                first_seen = _session_first_seen.get(session_name)
                created = str(int(first_seen)) if first_seen else ""

                return SessionInfo(
                    name=session_name,
                    pane_id=pane_id,
                    created=created,
                    attached=True,
                    windows=1,
                    pane_pid=pane.get("pid"),
                    pane_tty=pane.get("tty_name"),
                    pane_path=pane.get("cwd"),
                    pane_title=pane.get("title"),
                )

        return None

    def focus_window(self, session_name: str) -> bool:
        """Bring the WezTerm window containing this session to foreground.

        Uses 'wezterm cli activate-pane' for cross-platform window activation.

        Args:
            session_name: Name of the session to focus

        Returns:
            True if focus successful, False otherwise
        """
        if not self.is_available():
            return False

        pane_id = self._get_pane_id(session_name)
        if not pane_id:
            return False

        returncode, _, _ = _run_wezterm("activate-pane", "--pane-id", pane_id)
        if returncode == 0:
            # Also bring WezTerm application to foreground
            try:
                subprocess.run(
                    ["osascript", "-e", 'tell application "WezTerm" to activate'],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass  # Best effort - pane activation still succeeded
            return True
        return False

    def _get_pane_id(self, session_name: str) -> Optional[str]:
        """Get the pane-id for a session name.

        Checks the cache first, then queries live panes.

        Args:
            session_name: The session name to look up

        Returns:
            The pane-id string, or None if not found
        """
        # Check cache first
        if session_name in _session_pane_map:
            return _session_pane_map[session_name]

        # Query live panes
        sessions = self.list_sessions()
        for session in sessions:
            if session.get("name") == session_name:
                pane_id = session.get("pane_id")
                if pane_id:
                    _session_pane_map[session_name] = pane_id
                    return pane_id

        return None


# Module-level functions for convenience (matching tmux module pattern)

_backend_instance: Optional[WezTermBackend] = None


def _get_backend() -> WezTermBackend:
    """Get the singleton backend instance."""
    global _backend_instance
    if _backend_instance is None:
        _backend_instance = WezTermBackend()
    return _backend_instance


def is_wezterm_available() -> bool:
    """Check if WezTerm is installed and available."""
    return _get_backend().is_available()


def list_sessions() -> list[dict]:
    """List all active WezTerm sessions."""
    return _get_backend().list_sessions()


def session_exists(session_name: str) -> bool:
    """Check if a WezTerm session with the given name exists."""
    return _get_backend().session_exists(session_name)


def create_session(
    session_name: str,
    working_dir: Optional[str] = None,
    command: Optional[str] = None,
) -> bool:
    """Create a new WezTerm session."""
    return _get_backend().create_session(session_name, working_dir, command)


def kill_session(session_name: str) -> bool:
    """Kill a WezTerm session."""
    return _get_backend().kill_session(session_name)


def send_keys(
    session_name: str,
    text: str,
    enter: bool = True,
    correlation_id: Optional[str] = None,
    log_operation: bool = False,
) -> bool:
    """Send text to a WezTerm session."""
    return _get_backend().send_keys(
        session_name, text, enter, correlation_id, log_operation
    )


def capture_pane(
    session_name: str,
    lines: int = 100,
    start_line: Optional[int] = None,
    correlation_id: Optional[str] = None,
    log_operation: bool = False,
) -> Optional[str]:
    """Capture content from a WezTerm pane."""
    return _get_backend().capture_pane(
        session_name, lines, start_line, correlation_id, log_operation
    )


def get_session_info(session_name: str) -> Optional[dict]:
    """Get detailed information about a WezTerm session.

    Returns dict for API compatibility.
    """
    info = _get_backend().get_session_info(session_name)
    if info is None:
        return None

    return {
        "name": info.name,
        "created": info.created,
        "attached": info.attached,
        "windows": info.windows,
        "pane_pid": info.pane_pid,
        "pane_tty": info.pane_tty,
        "pane_path": info.pane_path,
        "pane_title": info.pane_title,
    }


def focus_window(session_name: str) -> bool:
    """Focus the WezTerm window containing this session."""
    return _get_backend().focus_window(session_name)


def get_claude_sessions() -> list[dict]:
    """Get all WezTerm sessions that appear to be Claude Code sessions.

    Returns list of dicts for API compatibility.
    """
    sessions = _get_backend().get_claude_sessions()
    return [
        {
            "name": s.name,
            "created": s.created,
            "attached": s.attached,
            "windows": s.windows,
            "pane_pid": s.pane_pid,
            "pane_tty": s.pane_tty,
            "pane_path": s.pane_path,
        }
        for s in sessions
    ]


# Reuse tmux naming utilities (same format works for both)
def slugify_project_name(name: str) -> str:
    """Convert a project name to a slug suitable for session names.

    Args:
        name: Project name (may contain spaces, special chars)

    Returns:
        Lowercase slug with hyphens (e.g., "My Project" -> "my-project")
    """
    slug = name.lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "unnamed"


def get_session_name_for_project(project_name: str) -> str:
    """Get the session name for a project.

    Uses same naming convention as tmux for consistency.

    Args:
        project_name: Project name

    Returns:
        Session name in format 'claude-<project-slug>-<hash>'
    """
    slug = slugify_project_name(project_name)
    name_hash = hashlib.md5(project_name.encode()).hexdigest()[:4]
    return f"claude-{slug}-{name_hash}"
