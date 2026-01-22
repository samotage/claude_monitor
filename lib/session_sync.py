"""Session state synchronization for Claude Headspace.

This module handles:
- Background thread for periodic session state sync
- Live session context extraction from JSONL logs
- Session end detection and summarization triggering
- Project state updates with live activity data
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import load_config
from lib.projects import load_project_data, save_project_data
from lib.sessions import scan_sessions
from lib.summarization import (
    find_session_log_file,
    get_claude_logs_directory,
    parse_jsonl_line,
    process_session_end,
)


# =============================================================================
# Constants and Configuration
# =============================================================================

DEFAULT_SYNC_INTERVAL = 60  # seconds
DEFAULT_JSONL_TAIL_ENTRIES = 20


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class LiveContext:
    """Context extracted from recent JSONL entries for display."""

    recent_files: List[str] = field(default_factory=list)
    recent_commands: List[str] = field(default_factory=list)
    current_task: str = ""
    tool_in_progress: Optional[str] = None
    last_activity: Optional[datetime] = None


@dataclass
class KnownSession:
    """Tracked session state for detecting lifecycle events."""

    uuid: str
    project_name: str
    project_path: str
    pid: int
    first_seen: datetime
    last_seen: datetime
    last_jsonl_position: int = 0
    last_jsonl_mtime: float = 0.0
    activity_snapshot: Optional[LiveContext] = None


# =============================================================================
# Thread State
# =============================================================================

_sync_thread: Optional[threading.Thread] = None
_sync_stop_event = threading.Event()
_known_sessions: Dict[str, KnownSession] = {}


# =============================================================================
# Configuration Helpers
# =============================================================================


def get_sync_config() -> dict:
    """Get session sync configuration from config.yaml.

    Returns:
        Dict with 'enabled', 'interval', 'jsonl_tail_entries'
    """
    config = load_config()
    sync_config = config.get("session_sync", {})

    return {
        "enabled": sync_config.get("enabled", True),
        "interval": sync_config.get("interval", DEFAULT_SYNC_INTERVAL),
        "jsonl_tail_entries": sync_config.get(
            "jsonl_tail_entries", DEFAULT_JSONL_TAIL_ENTRIES
        ),
    }


# =============================================================================
# JSONL File Discovery
# =============================================================================


def find_most_recent_log_file(project_path: str) -> Optional[Path]:
    """Find the most recently modified JSONL log file for a project.

    This is useful for active sessions where we don't know the exact
    session UUID but want to read the current session's log.

    Args:
        project_path: Absolute path to the project

    Returns:
        Path to the most recently modified JSONL file, or None
    """
    logs_dir = get_claude_logs_directory(project_path)
    if not logs_dir:
        return None

    try:
        # Find all JSONL files and sort by modification time
        jsonl_files = list(logs_dir.glob("*.jsonl"))
        if not jsonl_files:
            return None

        # Sort by modification time, newest first
        jsonl_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return jsonl_files[0]
    except Exception:
        return None


# =============================================================================
# JSONL Tail Reading
# =============================================================================


def read_jsonl_tail(
    log_file: Path, last_position: int = 0, max_entries: int = 20
) -> Tuple[List[dict], int]:
    """Read recent entries from JSONL file without loading entire file.

    Uses file position to read only new content since last check.

    Args:
        log_file: Path to JSONL file
        last_position: Last read position in file
        max_entries: Maximum entries to return

    Returns:
        Tuple of (list of parsed entries, new file position)
    """
    try:
        file_size = log_file.stat().st_size

        if file_size <= last_position:
            return [], last_position  # No new content

        # Read from last position to end
        with open(log_file, "r", encoding="utf-8") as f:
            f.seek(last_position)
            entries = []
            for line in f:
                parsed = parse_jsonl_line(line)
                if parsed:
                    entries.append(parsed)
            new_position = f.tell()

        # Return only the last N entries
        return entries[-max_entries:], new_position

    except Exception as e:
        print(f"Warning: Error reading JSONL tail: {e}")
        return [], last_position


# =============================================================================
# Live Context Extraction
# =============================================================================


def extract_live_context(
    entries: List[dict], max_files: int = 5, max_activity: int = 3
) -> LiveContext:
    """Extract displayable context from recent JSONL entries.

    Args:
        entries: Recent JSONL entries (newest last)
        max_files: Max files to track
        max_activity: Max activity summaries to track

    Returns:
        LiveContext with recent activity
    """
    files = set()
    recent_activity = []
    current_task = ""
    last_activity = None

    for entry in entries:
        # Track timestamp
        if "timestamp" in entry:
            try:
                last_activity = datetime.fromisoformat(
                    entry["timestamp"].replace("Z", "+00:00")
                )
            except Exception:
                pass

        # Extract from assistant messages
        if entry.get("type") == "assistant" and "message" in entry:
            message = entry.get("message", {})
            content = message.get("content", [])

            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})

                        # Track files
                        if tool_name in ("Edit", "Write", "Read"):
                            file_path = tool_input.get("file_path")
                            if file_path:
                                # Just filename for display
                                files.add(Path(file_path).name)

                    # Extract text content as activity summary
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        # Look for summary-like content (first sentence or line)
                        if text and len(text) > 20:
                            # Get first meaningful line
                            first_line = text.split("\n")[0].strip()
                            if first_line and len(first_line) > 15 and len(first_line) < 150:
                                # Avoid adding duplicates
                                if first_line not in recent_activity:
                                    recent_activity.append(first_line)

        # Extract user messages for task context
        if entry.get("type") == "user" and "message" in entry:
            msg = entry.get("message", {})
            msg_content = msg.get("content")
            if isinstance(msg_content, str) and msg_content:
                # Only use as task if it looks like a user message (not tool result)
                if not msg_content.startswith("{") and len(msg_content) > 10:
                    current_task = msg_content[:100]

    return LiveContext(
        recent_files=list(files)[:max_files],
        recent_commands=recent_activity[-max_activity:],  # Reuse field for activity
        current_task=current_task,
        tool_in_progress=None,  # Removed - not meaningful for users
        last_activity=last_activity,
    )


# =============================================================================
# Session Lifecycle Handlers
# =============================================================================


def _create_known_session(session: dict) -> KnownSession:
    """Create a KnownSession from a scan_sessions result."""
    now = datetime.now(timezone.utc)
    return KnownSession(
        uuid=session["uuid"],
        project_name=session["project_name"],
        project_path=session.get("project_dir", ""),
        pid=session.get("pid", 0),
        first_seen=now,
        last_seen=now,
    )


def _handle_session_end(known_session: KnownSession) -> None:
    """Handle a session that has ended.

    Triggers full summarization and state updates.
    """
    # Import here to avoid circular imports
    from lib.compression import add_to_compression_queue

    print(
        f"Info: Session {known_session.uuid[:8]}... ended for {known_session.project_name}"
    )

    # Process the session end (generates summary, updates state)
    summary = process_session_end(
        project_name=known_session.project_name,
        project_path=known_session.project_path,
        session_uuid=known_session.uuid,
        compression_queue_callback=add_to_compression_queue,
    )

    if summary:
        print(f"Info: Summarized ended session for {known_session.project_name}")


def _update_live_context(known_session: KnownSession, session: dict) -> None:
    """Update a session's live context from its JSONL log."""
    config = get_sync_config()
    max_entries = config["jsonl_tail_entries"]

    # Find the most recently modified JSONL log file for this project
    # (the wrapper UUID doesn't match Claude Code's internal session ID)
    log_file = find_most_recent_log_file(known_session.project_path)
    if not log_file:
        return

    # Check if file has changed
    try:
        mtime = log_file.stat().st_mtime
        if mtime == known_session.last_jsonl_mtime:
            return  # No changes
        known_session.last_jsonl_mtime = mtime
    except Exception:
        return

    # Read recent entries
    entries, new_position = read_jsonl_tail(
        log_file, known_session.last_jsonl_position, max_entries
    )
    known_session.last_jsonl_position = new_position

    if entries:
        known_session.activity_snapshot = extract_live_context(entries)


def _update_project_states_with_live_data(sessions: List[dict]) -> None:
    """Update project YAML state sections with live session context.

    For each active session, updates the project's `state` section with:
    - status: "active"
    - current_session_id: the active session UUID (primary)
    - live_context: recent files, commands, task (for display)
    - sessions_context: per-session context keyed by UUID
    """
    # Group sessions by project
    sessions_by_project: Dict[str, List[dict]] = {}
    for s in sessions:
        proj = s["project_name"]
        if proj not in sessions_by_project:
            sessions_by_project[proj] = []
        sessions_by_project[proj].append(s)

    for project_name, project_sessions in sessions_by_project.items():
        project_data = load_project_data(project_name)
        if not project_data:
            continue

        # Get existing state to preserve historical data
        existing_state = project_data.get("state", {})

        # Build per-session context for all active sessions
        sessions_context = {}
        for session in project_sessions:
            known = _known_sessions.get(session["uuid"])
            session_context = {
                "activity_state": session.get("activity_state", "unknown"),
                "task_summary": session.get("task_summary", ""),
                "pid": session.get("pid"),
            }
            if known and known.activity_snapshot:
                ctx = known.activity_snapshot
                session_context["live_context"] = {
                    "recent_files": ctx.recent_files,
                    "recent_commands": ctx.recent_commands,
                    "current_task": ctx.current_task,
                    "last_activity": ctx.last_activity.isoformat()
                    if ctx.last_activity
                    else None,
                }
            sessions_context[session["uuid"]] = session_context

        # Get live context for the primary session (backwards compatibility)
        primary_session = project_sessions[0]  # Most recent
        known = _known_sessions.get(primary_session["uuid"])

        live_context = {}
        if known and known.activity_snapshot:
            ctx = known.activity_snapshot
            live_context = {
                "recent_files": ctx.recent_files,
                "recent_commands": ctx.recent_commands,
                "current_task": ctx.current_task,
                "tool_in_progress": ctx.tool_in_progress,
                "last_activity": ctx.last_activity.isoformat()
                if ctx.last_activity
                else None,
            }

        # Update state section
        project_data["state"] = {
            "status": "active",
            "current_session_id": primary_session["uuid"],
            "activity_state": primary_session.get("activity_state", "unknown"),
            "task_summary": primary_session.get("task_summary", ""),
            "live_context": live_context,
            "sessions_context": sessions_context,  # Per-session context
            # Preserve last session info for context
            "last_session_id": existing_state.get("last_session_id"),
            "last_session_ended": existing_state.get("last_session_ended"),
            "last_session_summary": existing_state.get("last_session_summary"),
        }

        save_project_data(project_name, project_data)


# =============================================================================
# Core Sync Cycle
# =============================================================================


def _perform_sync_cycle() -> None:
    """Perform one sync cycle: detect changes, update state."""
    global _known_sessions

    config = load_config()

    # 1. Get current active sessions from scan_sessions()
    current_sessions = scan_sessions(config)
    current_session_uuids = {s["uuid"] for s in current_sessions}

    # 2. Detect ended sessions (in known but not in current)
    ended_session_uuids = set(_known_sessions.keys()) - current_session_uuids
    for uuid in ended_session_uuids:
        _handle_session_end(_known_sessions[uuid])
        del _known_sessions[uuid]

    # 3. Process active sessions
    for session in current_sessions:
        uuid = session["uuid"]

        if uuid not in _known_sessions:
            # New session
            _known_sessions[uuid] = _create_known_session(session)
            print(f"Info: New session detected: {uuid[:8]}... for {session['project_name']}")

        # Update live context from JSONL
        _update_live_context(_known_sessions[uuid], session)
        _known_sessions[uuid].last_seen = datetime.now(timezone.utc)

    # 4. Update project state with live session data
    if current_sessions:
        _update_project_states_with_live_data(current_sessions)


# =============================================================================
# Thread Management
# =============================================================================


def _session_sync_worker() -> None:
    """Background worker that syncs session state periodically."""
    while not _sync_stop_event.is_set():
        try:
            _perform_sync_cycle()
        except Exception as e:
            print(f"Warning: Session sync error: {e}")

        # Wait for next cycle (check stop event every second)
        config = get_sync_config()
        interval = config["interval"]
        for _ in range(interval):
            if _sync_stop_event.is_set():
                break
            time.sleep(1)


def start_session_sync_thread() -> bool:
    """Start the background session sync thread.

    Returns:
        True if thread was started, False if already running
    """
    global _sync_thread

    if _sync_thread is not None and _sync_thread.is_alive():
        return False  # Already running

    _sync_stop_event.clear()
    _sync_thread = threading.Thread(target=_session_sync_worker, daemon=True)
    _sync_thread.start()
    print("Info: Session sync thread started")
    return True


def stop_session_sync_thread() -> bool:
    """Stop the background session sync thread.

    Returns:
        True if thread was stopped, False if not running
    """
    global _sync_thread

    if _sync_thread is None or not _sync_thread.is_alive():
        return False

    _sync_stop_event.set()
    _sync_thread.join(timeout=5)
    _sync_thread = None
    print("Info: Session sync thread stopped")
    return True


def is_session_sync_running() -> bool:
    """Check if the session sync thread is running.

    Returns:
        True if thread is alive
    """
    return _sync_thread is not None and _sync_thread.is_alive()


def get_known_sessions() -> Dict[str, KnownSession]:
    """Get the current known sessions (for debugging/testing).

    Returns:
        Dict mapping session UUID to KnownSession
    """
    return _known_sessions.copy()
