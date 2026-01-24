"""tmux session integration for Claude Headspace.

This module provides functions for:
- Discovering tmux sessions
- Sending input to sessions (send-keys)
- Capturing output from sessions (capture-pane)
- Creating and managing sessions

tmux enables bidirectional communication with Claude Code sessions,
unlocking features like voice bridge and remote control that aren't
possible with iTerm AppleScript alone.
"""

import re
import shutil
import subprocess
from functools import lru_cache
from typing import Optional

from lib.tmux_logging import create_tmux_log_entry, write_tmux_log_entry

# Cache the tmux availability check (cleared on module reload)
_tmux_available: Optional[bool] = None

# Debug logging toggle - can be set by monitor.py from config
_debug_logging_enabled: bool = False


def set_debug_logging(enabled: bool) -> None:
    """Set the debug logging mode for tmux operations.

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


def _log_tmux_event(
    session_name: str,
    direction: str,
    event_type: str,
    payload: Optional[str] = None,
    correlation_id: Optional[str] = None,
    success: bool = True,
) -> None:
    """Log a tmux operation event.

    Args:
        session_name: The tmux session name
        direction: "in" or "out"
        event_type: Type of operation
        payload: Message content
        correlation_id: Links related operations
        success: Whether operation succeeded
    """
    # Extract session_id from tmux session name (e.g., claude-my-project -> my-project)
    session_id = session_name
    if session_name.startswith("claude-"):
        session_id = session_name[7:]  # Remove "claude-" prefix

    entry = create_tmux_log_entry(
        session_id=session_id,
        tmux_session_name=session_name,
        direction=direction,
        event_type=event_type,
        payload=payload,
        correlation_id=correlation_id,
        success=success,
        debug_enabled=_debug_logging_enabled,
    )
    write_tmux_log_entry(entry)


def is_tmux_available() -> bool:
    """Check if tmux is installed and available.

    Returns:
        True if tmux is available, False otherwise.
        Result is cached for performance.
    """
    global _tmux_available
    if _tmux_available is not None:
        return _tmux_available

    _tmux_available = shutil.which("tmux") is not None
    return _tmux_available


def _run_tmux(*args: str, check: bool = False, capture: bool = True) -> tuple[int, str, str]:
    """Run a tmux command and return the result.

    Args:
        *args: Command arguments to pass to tmux
        check: If True, raise CalledProcessError on non-zero exit
        capture: If True, capture stdout/stderr

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd = ["tmux"] + list(args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=10,
        )
        return (result.returncode, result.stdout or "", result.stderr or "")
    except subprocess.TimeoutExpired:
        return (1, "", "Command timed out")
    except FileNotFoundError:
        return (1, "", "tmux not found")


def list_sessions() -> list[dict]:
    """List all active tmux sessions.

    Returns:
        List of session dicts with keys:
        - name: Session name
        - created: Creation timestamp
        - attached: Whether session is attached
        - windows: Number of windows
    """
    if not is_tmux_available():
        return []

    # Format: name:created:attached:windows
    format_str = "#{session_name}:#{session_created}:#{session_attached}:#{session_windows}"
    returncode, stdout, _ = _run_tmux("list-sessions", "-F", format_str)

    if returncode != 0:
        return []

    sessions = []
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 4:
            sessions.append({
                "name": parts[0],
                "created": parts[1],
                "attached": parts[2] == "1",
                "windows": int(parts[3]) if parts[3].isdigit() else 1,
            })

    return sessions


def session_exists(session_name: str) -> bool:
    """Check if a tmux session with the given name exists.

    Args:
        session_name: The session name to check

    Returns:
        True if session exists, False otherwise
    """
    if not is_tmux_available():
        return False

    returncode, _, _ = _run_tmux("has-session", "-t", session_name)
    return returncode == 0


def create_session(
    session_name: str,
    working_dir: Optional[str] = None,
    command: Optional[str] = None,
) -> bool:
    """Create a new tmux session.

    Args:
        session_name: Name for the new session
        working_dir: Working directory for the session
        command: Optional command to run in the session

    Returns:
        True if session created successfully, False otherwise
    """
    if not is_tmux_available():
        return False

    if session_exists(session_name):
        return False  # Session already exists

    args = ["new-session", "-d", "-s", session_name]

    if working_dir:
        args.extend(["-c", working_dir])

    if command:
        args.append(command)

    returncode, _, _ = _run_tmux(*args)
    return returncode == 0


def kill_session(session_name: str) -> bool:
    """Kill a tmux session.

    Args:
        session_name: Name of the session to kill

    Returns:
        True if session killed successfully, False otherwise
    """
    if not is_tmux_available():
        return False

    returncode, _, _ = _run_tmux("kill-session", "-t", session_name)
    return returncode == 0


def send_keys(
    session_name: str,
    text: str,
    enter: bool = True,
    correlation_id: Optional[str] = None,
    log_operation: bool = False,
) -> bool:
    """Send text to a tmux session.

    Args:
        session_name: Target session name
        text: Text to send
        enter: If True, append Enter key after text
        correlation_id: Optional ID to link with corresponding capture
        log_operation: If True, log this operation (for user-initiated API calls)

    Returns:
        True if send successful, False otherwise
    """
    if not is_tmux_available():
        if log_operation:
            _log_tmux_event(
                session_name=session_name,
                direction="out",
                event_type="send_attempted",
                payload=text,
                correlation_id=correlation_id,
                success=False,
            )
        return False

    if not session_exists(session_name):
        if log_operation:
            _log_tmux_event(
                session_name=session_name,
                direction="out",
                event_type="send_attempted",
                payload=text,
                correlation_id=correlation_id,
                success=False,
            )
        return False

    args = ["send-keys", "-t", session_name, text]
    if enter:
        args.append("Enter")

    returncode, _, _ = _run_tmux(*args)
    success = returncode == 0

    if log_operation:
        _log_tmux_event(
            session_name=session_name,
            direction="out",
            event_type="send_keys",
            payload=text,
            correlation_id=correlation_id,
            success=success,
        )

    return success


def capture_pane(
    session_name: str,
    lines: int = 100,
    start_line: Optional[int] = None,
    correlation_id: Optional[str] = None,
    log_operation: bool = False,
) -> Optional[str]:
    """Capture the content of a tmux pane.

    Args:
        session_name: Target session name
        lines: Number of lines to capture from scrollback (default 100)
        start_line: Optional start line (negative for scrollback)
        correlation_id: Optional ID to link with corresponding send
        log_operation: If True, log this operation (for user-initiated API calls)

    Returns:
        Captured text content, or None on failure
    """
    if not is_tmux_available():
        if log_operation:
            _log_tmux_event(
                session_name=session_name,
                direction="in",
                event_type="capture_attempted",
                correlation_id=correlation_id,
                success=False,
            )
        return None

    if not session_exists(session_name):
        if log_operation:
            _log_tmux_event(
                session_name=session_name,
                direction="in",
                event_type="capture_attempted",
                correlation_id=correlation_id,
                success=False,
            )
        return None

    # -p prints to stdout, -S specifies start line
    # Negative values go into scrollback history
    args = ["capture-pane", "-t", session_name, "-p"]

    if start_line is not None:
        args.extend(["-S", str(start_line)])
    else:
        # Default: capture last N lines from scrollback
        args.extend(["-S", f"-{lines}"])

    returncode, stdout, _ = _run_tmux(*args)

    if returncode != 0:
        if log_operation:
            _log_tmux_event(
                session_name=session_name,
                direction="in",
                event_type="capture_attempted",
                correlation_id=correlation_id,
                success=False,
            )
        return None

    if log_operation:
        _log_tmux_event(
            session_name=session_name,
            direction="in",
            event_type="capture_pane",
            payload=stdout,
            correlation_id=correlation_id,
            success=True,
        )

    return stdout


def get_session_info(session_name: str) -> Optional[dict]:
    """Get detailed information about a tmux session.

    Args:
        session_name: Target session name

    Returns:
        Dict with session info, or None if session doesn't exist
    """
    if not is_tmux_available():
        return None

    if not session_exists(session_name):
        return None

    # Get comprehensive session info
    format_str = (
        "#{session_name}:"
        "#{session_created}:"
        "#{session_attached}:"
        "#{session_windows}:"
        "#{pane_pid}:"
        "#{pane_tty}:"
        "#{pane_current_path}"
    )

    returncode, stdout, _ = _run_tmux(
        "list-panes", "-t", session_name, "-F", format_str
    )

    if returncode != 0 or not stdout.strip():
        return None

    # Parse the first pane (main pane)
    line = stdout.strip().split("\n")[0]
    parts = line.split(":")

    if len(parts) < 7:
        return None

    return {
        "name": parts[0],
        "created": parts[1],
        "attached": parts[2] == "1",
        "windows": int(parts[3]) if parts[3].isdigit() else 1,
        "pane_pid": int(parts[4]) if parts[4].isdigit() else None,
        "pane_tty": parts[5],
        "pane_path": parts[6],
    }


def get_claude_sessions() -> list[dict]:
    """Get all tmux sessions that appear to be Claude Code sessions.

    Looks for sessions with names matching the pattern 'claude-*'.

    Returns:
        List of session info dicts for Claude sessions
    """
    if not is_tmux_available():
        return []

    all_sessions = list_sessions()
    claude_sessions = []

    for session in all_sessions:
        name = session.get("name", "")
        # Match sessions created by our wrapper: claude-<project-slug>
        if name.startswith("claude-"):
            info = get_session_info(name)
            if info:
                claude_sessions.append(info)

    return claude_sessions


def slugify_project_name(name: str) -> str:
    """Convert a project name to a slug suitable for tmux session names.

    Args:
        name: Project name (may contain spaces, special chars)

    Returns:
        Lowercase slug with hyphens (e.g., "My Project" -> "my-project")
    """
    # Convert to lowercase
    slug = name.lower()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove any characters that aren't alphanumeric or hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug or "unnamed"


def get_session_name_for_project(project_name: str) -> str:
    """Get the tmux session name for a project.

    Args:
        project_name: Project name

    Returns:
        tmux session name in format 'claude-<project-slug>'
    """
    return f"claude-{slugify_project_name(project_name)}"
