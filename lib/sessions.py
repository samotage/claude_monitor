"""Session scanning and activity state parsing for Claude Headspace.

This module handles:
- Scanning project directories for active Claude sessions (iTerm and tmux)
- Parsing activity state from terminal window titles and content
- Formatting session information
- Turn completion detection for state transition tracking
- Last activity tracking for session cards
- Turn cycle logging for tracking user commands and Claude responses
"""

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Debug logger for activity state detection
logger = logging.getLogger(__name__)

# Track last activity per session (content hash -> timestamp)
# Key: session identifier (uuid or tmux_session_name)
# Value: {"content_hash": str, "last_activity_at": str (ISO format)}
_session_activity_cache: dict[str, dict] = {}


# =============================================================================
# Turn Cycle Tracking
# =============================================================================

@dataclass
class TurnState:
    """Track the state of a turn (user command → Claude response cycle).

    A turn starts when the user sends a command (activity_state transitions TO processing)
    and ends when Claude finishes (activity_state transitions FROM processing).

    The turn_id links the turn_start and turn_complete log entries together.
    The logged_* flags prevent duplicate log entries from state flickering.
    """
    turn_id: str              # UUID linking start/complete log entries
    command: str              # User's command that started the turn
    started_at: datetime      # When processing began
    previous_state: str       # State before processing started (idle/input_needed)
    logged_start: bool = False       # Prevent duplicate start logs
    logged_completion: bool = False  # Prevent duplicate completion logs


# Track turn state per session
# Key: session_id (tmux_session_name or uuid)
# Value: TurnState or None if not in a turn
_turn_tracking: dict[str, Optional[TurnState]] = {}

# Track the most recently completed turn per session
# This allows us to tell the AI what command was just completed when session is idle
# Key: session_id
# Value: dict with command, result_state, completion_marker, duration_seconds
_last_completed_turn: dict[str, dict] = {}

# Track previous activity state per session for transition detection
# Key: session_id
# Value: previous activity_state string
# NOTE: This is the single source of truth for activity state tracking.
# lib/headspace.py imports accessor functions to use this state.
_previous_activity_states: dict[str, str] = {}

# Early turn start signals from WezTerm Enter-key notifications
# Key: session_id (session_name, e.g., "claude-myproject-abc123")
# Value: datetime of the Enter keypress (UTC)
_enter_signals: dict[str, datetime] = {}


def record_enter_signal(session_id: str) -> None:
    """Record that Enter was pressed in a session.

    Called by the /api/wezterm/enter-pressed endpoint.
    The signal is consumed by track_turn_cycle() on the next poll.

    Args:
        session_id: The session name
    """
    _enter_signals[session_id] = datetime.now(timezone.utc)


def consume_enter_signal(session_id: str) -> Optional[datetime]:
    """Consume and return the pending Enter signal for a session.

    Returns the signal timestamp and removes it from the pending dict.
    Returns None if no signal is pending or if the signal is stale (>10s).

    Args:
        session_id: The session name

    Returns:
        The datetime when Enter was pressed, or None
    """
    signal_time = _enter_signals.pop(session_id, None)
    if signal_time is None:
        return None
    # Expire if older than 10 seconds (probably wasn't a real turn start)
    age = (datetime.now(timezone.utc) - signal_time).total_seconds()
    if age > 10:
        return None
    return signal_time


def get_previous_activity_states() -> dict[str, str]:
    """Get a copy of the current activity states tracking dict.

    Returns:
        Copy of the session_id -> activity_state mapping
    """
    return _previous_activity_states.copy()


def get_previous_activity_state(session_id: str) -> str | None:
    """Get the previous activity state for a session.

    Args:
        session_id: The session identifier

    Returns:
        Previous activity state string, or None if not tracked
    """
    return _previous_activity_states.get(session_id)


def set_previous_activity_states(states: dict[str, str]) -> None:
    """Replace the entire activity states tracking dict.

    Args:
        states: New session_id -> activity_state mapping
    """
    global _previous_activity_states
    _previous_activity_states = states


def clear_previous_activity_states() -> None:
    """Clear all tracked activity states."""
    global _previous_activity_states
    _previous_activity_states = {}


def clear_turn_tracking() -> None:
    """Clear all turn tracking state (active and completed turns)."""
    global _turn_tracking, _last_completed_turn
    _turn_tracking.clear()
    _last_completed_turn.clear()


def clear_enter_signals() -> None:
    """Clear all pending Enter signals from WezTerm."""
    global _enter_signals
    _enter_signals.clear()


def cleanup_stale_session_data(active_session_ids: set[str]) -> int:
    """Remove tracking data for sessions that are no longer active.

    This prevents unbounded growth of in-memory tracking dicts when
    sessions end without explicit cleanup.

    Args:
        active_session_ids: Set of currently active session IDs

    Returns:
        Number of stale entries cleaned up
    """
    global _turn_tracking, _last_completed_turn, _previous_activity_states, _enter_signals

    cleaned_count = 0

    # Clean up turn tracking
    stale_turn_ids = [sid for sid in _turn_tracking if sid not in active_session_ids]
    for sid in stale_turn_ids:
        del _turn_tracking[sid]
        cleaned_count += 1

    # Clean up last completed turns
    stale_completed_ids = [sid for sid in _last_completed_turn if sid not in active_session_ids]
    for sid in stale_completed_ids:
        del _last_completed_turn[sid]
        cleaned_count += 1

    # Clean up activity states
    stale_state_ids = [sid for sid in _previous_activity_states if sid not in active_session_ids]
    for sid in stale_state_ids:
        del _previous_activity_states[sid]
        cleaned_count += 1

    # Clean up stale enter signals
    stale_signal_ids = [sid for sid in _enter_signals if sid not in active_session_ids]
    for sid in stale_signal_ids:
        del _enter_signals[sid]
        cleaned_count += 1

    return cleaned_count


# Complete list of Claude Code spinner verbs (past tense for turn completion)
# These appear as "✻ <Verb> for Xm Xs" when Claude finishes a turn
# Source: Claude Code CLI internal verb list
TURN_COMPLETE_VERBS = [
    "Accomplished", "Actioned", "Actualized", "Baked", "Booped", "Brewed",
    "Calculated", "Cerebrated", "Channelled", "Churned", "Clauded", "Coalesced",
    "Cogitated", "Combobulated", "Computed", "Concocted", "Conjured", "Considered",
    "Contemplated", "Cooked", "Crafted", "Created", "Crunched", "Deciphered",
    "Deliberated", "Determined", "Discombobulated", "Divined", "Done", "Effected",
    "Elucidated", "Enchanted", "Envisioned", "Finagled", "Flibbertigibbeted",
    "Forged", "Formed", "Frolicked", "Generated", "Germinated", "Hatched",
    "Herded", "Honked", "Hustled", "Ideated", "Imagined", "Incubated", "Inferred",
    "Jived", "Manifested", "Marinated", "Meandered", "Moseyed", "Mulled",
    "Mustered", "Mused", "Noodled", "Percolated", "Perused", "Philosophised",
    "Pondered", "Pontificated", "Processed", "Puttered", "Puzzled", "Reticulated",
    "Ruminated", "Sautéed", "Schemed", "Schlepped", "Shimmied", "Shucked", "Simmered",
    "Smooshed", "Spelunked", "Spun", "Stewed", "Sussed", "Synthesized", "Thought",
    "Tinkered", "Transmuted", "Unfurled", "Unravelled", "Vibed", "Wandered",
    "Whirred", "Wibbled", "Whisked", "Wizarded", "Worked", "Wrangled"
]


def is_turn_complete(content: str) -> bool:
    """Check if Claude's turn just completed based on completion marker.

    Claude Code displays "✻ <Verb> for Xm Xs" when a turn completes.

    Args:
        content: Terminal content to check

    Returns:
        True if a turn completion marker is found in recent content
    """
    if not content:
        return False
    # Check last 800 chars for completion pattern (status bar can be 300+ chars)
    tail = content[-800:]
    return any(f"✻ {verb} for" in tail for verb in TURN_COMPLETE_VERBS)


def extract_turn_command(content: str, max_chars: int = 100) -> str:
    """Extract the user's command from terminal content.

    Looks for the most recent line after the ❯ prompt that represents
    what the user typed to start this turn.

    Args:
        content: Terminal content to search
        max_chars: Maximum characters to return

    Returns:
        The extracted command, truncated if needed, or empty string if not found
    """
    if not content:
        return ""

    lines = content.strip().split("\n")

    # Search backwards for the last ❯ prompt line with content after it
    for i, line in enumerate(reversed(lines)):
        # Check if line starts with or contains ❯ prompt
        if "❯" in line:
            # Extract text after the prompt
            prompt_idx = line.rfind("❯")
            command = line[prompt_idx + 1:].strip()

            # If there's content on the same line, that's the command
            if command:
                if len(command) > max_chars:
                    return command[:max_chars] + "..."
                return command

    return ""


def extract_completion_marker(content: str) -> str:
    """Extract the completion marker from terminal content.

    Looks for patterns like "✻ Baked for 2m 30s" in recent content.

    Args:
        content: Terminal content to search

    Returns:
        The completion marker string (e.g., "✻ Baked for 2m 30s") or empty string
    """
    if not content:
        return ""

    # Check last 300 chars
    tail = content[-300:]

    # Build pattern to match "✻ Verb for Xm Xs" or "✻ Verb for Xs"
    for verb in TURN_COMPLETE_VERBS:
        pattern = f"✻ {verb} for"
        if pattern in tail:
            # Find the full marker (includes time)
            start = tail.find(pattern)
            # Extract until end of line or next newline
            end = tail.find("\n", start)
            if end == -1:
                return tail[start:].strip()
            return tail[start:end].strip()

    return ""


def track_turn_cycle(
    session_id: str,
    tmux_session_name: str,
    current_state: str,
    content: str,
) -> Optional[dict]:
    """Track turn cycle transitions and log atomic turn pairs.

    Logs two linked entries per turn:
    - turn_start (direction=out) when user sends command
    - turn_complete (direction=in) when Claude finishes, with response summary

    Both entries share the same turn_id via correlation_id field.
    Duplicate prevention: logged_completion flag prevents re-logging on state flicker.

    Args:
        session_id: Session identifier
        tmux_session_name: The tmux session name for logging
        current_state: Current activity state (processing/idle/input_needed)
        content: Terminal content for extracting command/completion marker

    Returns:
        Turn data dict if a turn just completed, None otherwise
    """
    global _turn_tracking, _previous_activity_states

    previous_state = _previous_activity_states.get(session_id, "unknown")
    _previous_activity_states[session_id] = current_state

    # Turn START: transition TO processing (genuine new turn)
    if current_state == "processing" and previous_state in ("idle", "input_needed", "unknown"):
        # Extract the command that started this turn
        command = extract_turn_command(content)

        # Generate unique turn_id for linking start/complete entries
        turn_id = str(uuid.uuid4())

        # Check if we have an early Enter signal with a more accurate timestamp
        enter_timestamp = consume_enter_signal(session_id)
        actual_start_time = enter_timestamp or datetime.now(timezone.utc)

        turn_state = TurnState(
            turn_id=turn_id,
            command=command,
            started_at=actual_start_time,
            previous_state=previous_state,
            logged_start=False,
            logged_completion=False,
        )
        _turn_tracking[session_id] = turn_state

        # Log turn start immediately
        _log_turn_start(session_id, tmux_session_name, turn_state)
        turn_state.logged_start = True

        logger.debug(
            f"Turn started for {session_id}: '{command[:50]}...' "
            f"(turn_id={turn_id[:8]}, push={'yes' if enter_timestamp else 'no'})"
        )
        return None

    # Turn END: transition FROM processing
    if previous_state == "processing" and current_state in ("idle", "input_needed"):
        turn_state = _turn_tracking.get(session_id)
        if turn_state and not turn_state.logged_completion:
            # Calculate duration
            duration_seconds = (datetime.now(timezone.utc) - turn_state.started_at).total_seconds()
            completion_marker = extract_completion_marker(content)

            # Extract response summary from Claude's output
            response_summary = extract_last_message(content)

            # Build turn data for logging
            turn_data = {
                "command": turn_state.command,
                "result_state": current_state,
                "completion_marker": completion_marker,
                "duration_seconds": round(duration_seconds, 1),
                "started_at": turn_state.started_at.isoformat(),
            }

            # Store as last completed turn (for AI context when idle)
            _last_completed_turn[session_id] = turn_data

            # Log the turn completion with response summary
            _log_turn_completion(session_id, tmux_session_name, turn_state, turn_data, response_summary)

            # Mark as logged to prevent duplicates on state flicker
            turn_state.logged_completion = True

            # Note: We keep turn_state in _turn_tracking until a genuinely NEW turn starts
            # This prevents state flicker from creating duplicate completion logs

            # Emit priorities invalidation event (late import to avoid circular dependency)
            from lib.headspace import emit_priorities_invalidation
            emit_priorities_invalidation(reason="turn_completed")

            logger.debug(f"Turn completed for {session_id}: {duration_seconds:.1f}s, result={current_state} (turn_id={turn_state.turn_id[:8]})")
            return turn_data

    return None


def get_last_completed_turn(session_id: str) -> Optional[dict]:
    """Get the most recently completed turn for a session.

    This is useful for providing context to the AI when describing
    what a session just completed.

    Args:
        session_id: Session identifier

    Returns:
        Dict with command, result_state, completion_marker, etc. or None
    """
    return _last_completed_turn.get(session_id)


def _log_turn_start(session_id: str, tmux_session_name: str, turn_state: TurnState) -> None:
    """Log a turn start to the tmux log file.

    Creates a log entry with event_type="turn_start" and direction="out" (user command).
    The turn_id in correlation_id links this to the corresponding turn_complete entry.

    Args:
        session_id: Session identifier
        tmux_session_name: The tmux session name
        turn_state: TurnState with turn_id, command, started_at
    """
    from lib.tmux_logging import create_tmux_log_entry, write_tmux_log_entry

    payload = {
        "turn_id": turn_state.turn_id,
        "command": turn_state.command,
        "started_at": turn_state.started_at.isoformat(),
    }

    entry = create_tmux_log_entry(
        session_id=session_id,
        tmux_session_name=tmux_session_name,
        direction="out",  # User command is outgoing
        event_type="turn_start",
        payload=json.dumps(payload),
        correlation_id=turn_state.turn_id,
        debug_enabled=True,  # Always log turn data
    )

    write_tmux_log_entry(entry)


def _log_turn_completion(session_id: str, tmux_session_name: str, turn_state: TurnState, turn_data: dict, response_summary: str) -> None:
    """Log a turn completion to the tmux log file.

    Creates a log entry with event_type="turn_complete" and direction="in" (Claude response).
    The turn_id in correlation_id links this to the corresponding turn_start entry.

    Args:
        session_id: Session identifier
        tmux_session_name: The tmux session name
        turn_state: TurnState with turn_id for correlation
        turn_data: Dict with command, result_state, completion_marker, duration_seconds, started_at
        response_summary: Summary of Claude's response (extracted from terminal content)
    """
    from lib.tmux_logging import create_tmux_log_entry, write_tmux_log_entry

    # Add turn_id and response_summary to payload
    payload = {
        "turn_id": turn_state.turn_id,
        **turn_data,
        "response_summary": response_summary,
    }

    entry = create_tmux_log_entry(
        session_id=session_id,
        tmux_session_name=tmux_session_name,
        direction="in",  # Claude's response is incoming
        event_type="turn_complete",
        payload=json.dumps(payload),
        correlation_id=turn_state.turn_id,
        debug_enabled=True,  # Always log turn data
    )

    write_tmux_log_entry(entry)


def get_current_turn_command(session_id: str) -> Optional[str]:
    """Get the command for the current in-progress turn.

    Args:
        session_id: Session identifier

    Returns:
        The command string if a turn is in progress, None otherwise
    """
    turn_state = _turn_tracking.get(session_id)
    if turn_state:
        return turn_state.command
    return None


from lib.iterm import get_pid_tty, focus_iterm_window_by_pid
from lib.summarization import prepare_content_for_summary
from lib.tmux import (
    capture_pane,
    get_session_info,
    is_tmux_available,
    list_sessions as tmux_list_sessions,
    session_exists as tmux_session_exists,
    slugify_project_name,
)


def track_session_activity(session_id: str, content: str) -> str:
    """Track last activity for a session by detecting content changes.

    Updates the activity cache when content hash changes.

    Args:
        session_id: Unique session identifier (uuid or tmux_session_name)
        content: Current terminal content

    Returns:
        ISO format timestamp of last activity
    """
    global _session_activity_cache

    # Compute hash of content (use last 2000 chars for efficiency)
    content_sample = content[-2000:] if content else ""
    content_hash = hashlib.md5(content_sample.encode()).hexdigest()

    now = datetime.now(timezone.utc).isoformat()

    if session_id not in _session_activity_cache:
        # First time seeing this session
        _session_activity_cache[session_id] = {
            "content_hash": content_hash,
            "last_activity_at": now,
        }
    elif _session_activity_cache[session_id]["content_hash"] != content_hash:
        # Content changed - update timestamp
        _session_activity_cache[session_id]["content_hash"] = content_hash
        _session_activity_cache[session_id]["last_activity_at"] = now

    return _session_activity_cache[session_id]["last_activity_at"]


def format_time_ago(iso_timestamp: str) -> str:
    """Format an ISO timestamp as human-readable time ago.

    Args:
        iso_timestamp: ISO 8601 format timestamp

    Returns:
        Human-readable string like "2m ago", "1h ago", "just now"
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        seconds = delta.total_seconds()

        if seconds < 10:
            return "just now"
        elif seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        else:
            days = int(seconds / 86400)
            return f"{days}d ago"
    except Exception:
        return "unknown"


def extract_last_message(content_tail: str, max_chars: int = 500) -> str:
    """Extract the last Claude message/response from terminal content.

    Looks for the most recent substantial block of text that represents
    what Claude last said. This is useful for showing in tooltips.

    Args:
        content_tail: Raw terminal content (last ~5000 chars from iTerm)
        max_chars: Maximum characters to return

    Returns:
        The last message text, cleaned and truncated
    """
    if not content_tail:
        return ""

    # First clean the content using existing function
    cleaned = prepare_content_for_summary(content_tail, max_chars=2000)

    if not cleaned:
        return ""

    # Split into lines and work backwards to find last substantial content
    lines = cleaned.strip().split('\n')

    # Filter out empty lines and very short lines (likely prompts or UI)
    substantial_lines = []
    for line in reversed(lines):
        line = line.strip()
        # Skip empty lines, prompts, and very short lines
        if not line:
            continue
        # Skip lines that look like prompts (common prompt patterns)
        if line in ('>', '$', '❯', '%', '#') or len(line) < 5:
            continue
        # Skip lines that are just UI elements
        if line.startswith('---') or line.startswith('==='):
            continue
        substantial_lines.insert(0, line)
        # Stop after collecting enough lines (last meaningful paragraph)
        if len('\n'.join(substantial_lines)) > max_chars:
            break

    if not substantial_lines:
        return ""

    result = '\n'.join(substantial_lines)

    # Truncate if needed
    if len(result) > max_chars:
        result = result[:max_chars].rsplit(' ', 1)[0] + '...'

    return result.strip()


def parse_session_name(session_name: str) -> tuple[Optional[str], Optional[str]]:
    """Parse a tmux session name into project slug and uuid8.

    Session names follow the pattern: claude-{project-slug}-{uuid8}
    Example: claude-claude-monitor-87c165e4

    Args:
        session_name: The tmux session name

    Returns:
        Tuple of (project_slug, uuid8), or (None, None) if parsing fails
    """
    if not session_name or not session_name.startswith("claude-"):
        return None, None

    # Remove "claude-" prefix
    remainder = session_name[7:]  # len("claude-") = 7

    # The uuid8 is the last 8 characters after the last hyphen
    # But we need to be careful: project slugs can contain hyphens
    # Pattern: claude-{project-slug}-{uuid8} where uuid8 is exactly 8 hex chars
    parts = remainder.rsplit("-", 1)
    if len(parts) != 2:
        return None, None

    project_slug = parts[0]
    uuid8 = parts[1]

    # Validate uuid8 is 8 hex characters
    if len(uuid8) != 8 or not all(c in "0123456789abcdef" for c in uuid8.lower()):
        # Maybe the entire remainder is the project slug with no uuid
        return remainder, None

    return project_slug, uuid8


def match_project(slug: str, projects: list[dict]) -> Optional[dict]:
    """Match a project slug to a config project.

    Tries to match by:
    1. Slugified project name
    2. Slugified directory name

    Args:
        slug: The project slug from the session name
        projects: List of project dicts from config

    Returns:
        Matched project dict, or None if no match
    """
    if not slug:
        return None

    for project in projects:
        # Match by slugified project name
        if slugify_project_name(project.get("name", "")) == slug:
            return project
        # Match by slugified directory name
        dir_name = Path(project.get("path", "")).name
        if slugify_project_name(dir_name) == slug:
            return project

    return None


def scan_backend_session(
    session_info: dict,
    project: Optional[dict],
    project_slug: str,
    uuid8: Optional[str],
    capture_fn=None,
    session_type: str = "tmux",
) -> Optional[dict]:
    """Scan a terminal session from any backend and return session info.

    Works with both tmux and WezTerm backends.

    Args:
        session_info: Session info dict from backend's get_session_info()
        project: Matched project config from config.yaml (may be None)
        project_slug: The project slug extracted from session name
        uuid8: The short UUID extracted from session name (may be None)
        capture_fn: Function to capture terminal content (defaults to tmux capture_pane)
        session_type: Backend type ("tmux" or "wezterm")

    Returns:
        Session dict if session is active, None otherwise
    """
    if capture_fn is None:
        capture_fn = capture_pane

    session_name = session_info.get("name")
    if not session_name:
        return None

    # Capture terminal content from backend
    content_tail = capture_fn(session_name, lines=200) or ""

    # Use pane title from backend if available (WezTerm provides rich titles
    # with spinner chars for activity detection; tmux does not)
    window_title = session_info.get("pane_title", "") or ""

    # Use tmux created time for elapsed calculation
    created_timestamp = session_info.get("created", "")
    try:
        # tmux returns Unix timestamp
        start_time = datetime.fromtimestamp(int(created_timestamp), tz=timezone.utc)
        elapsed = datetime.now(timezone.utc) - start_time
        elapsed_str = format_elapsed(elapsed.total_seconds())
        started_at = start_time.isoformat()
    except Exception:
        elapsed_str = "unknown"
        started_at = ""

    # Extract activity state from content
    activity_state, task_summary = parse_activity_state(window_title, content_tail)

    # Track turn cycle (logs when turn completes, returns turn data)
    # Use session_name as the session_id for consistency
    track_turn_cycle(session_name, session_name, activity_state, content_tail)

    # Get turn command for display:
    # - If processing: show the current turn's command
    # - If idle: show the last completed turn's command (for AI context)
    if activity_state == "processing":
        turn_command = get_current_turn_command(session_name)
    else:
        last_turn = get_last_completed_turn(session_name)
        turn_command = last_turn.get("command") if last_turn else None

    # Prepare terminal content for AI summarization
    content_snippet = prepare_content_for_summary(content_tail)

    # Extract last message for tooltip display
    last_message = extract_last_message(content_tail)

    # Determine project info
    if project:
        project_name = project.get("name", project_slug)
        project_dir = project.get("path", "")
    else:
        # Unknown project - use slug as name
        project_name = project_slug or "Unknown"
        project_dir = session_info.get("pane_path", "")

    # Track last activity (content change detection)
    session_id = session_name  # Use tmux session name as identifier
    last_activity_at = track_session_activity(session_id, content_tail)
    last_activity_ago = format_time_ago(last_activity_at)

    session_uuid = uuid8 or "unknown"
    return {
        # Standardized session identifiers (preferred)
        "session_id": session_uuid,
        "session_id_short": session_uuid[-8:] if session_uuid != "unknown" else "unknown",
        # Legacy fields (maintained for backwards compatibility)
        "uuid": session_uuid,
        "uuid_short": session_uuid[-8:] if session_uuid != "unknown" else "unknown",
        "project_name": project_name,
        "project_dir": project_dir,
        "started_at": started_at,
        "elapsed": elapsed_str,
        "last_activity_at": last_activity_at,
        "last_activity_ago": last_activity_ago,
        "pid": session_info.get("pane_pid"),
        "tty": session_info.get("pane_tty"),
        "status": "active",
        "activity_state": activity_state,
        "window_title": window_title,
        "task_summary": task_summary if task_summary else f"{session_type}: {session_name}",
        "content_snippet": content_snippet,
        "last_message": last_message,
        "turn_command": turn_command,  # Current turn's user command (if processing)
        # Backend fields
        "session_type": session_type,
        "tmux_session": session_name,
        "tmux_attached": session_info.get("attached", False),
    }


def scan_iterm_session(
    state: dict,
    project: dict,
    iterm_windows: dict,
) -> Optional[dict]:
    """Scan an iTerm-based session and return session info.

    Args:
        state: State dict from the session state file
        project: Project config from config.yaml
        iterm_windows: Dict of iTerm windows by TTY

    Returns:
        Session dict if session is active, None otherwise
    """
    session_uuid = state.get("uuid", "").lower()
    session_pid = state.get("pid")

    # Check if session has an iTerm window by matching PID to TTY
    window_info = None
    session_tty = None
    if session_pid:
        # First verify this is actually a Claude process (prevents PID reuse issues)
        if not is_claude_process(session_pid):
            # PID was reused by another process - this session is dead
            return None

        session_tty = get_pid_tty(session_pid)
        if session_tty:
            window_info = iterm_windows.get(session_tty)

    # Only show sessions that have an active iTerm window
    # Sessions without windows are not displayed (window closed = session gone)
    if not window_info:
        return None

    window_title = window_info.get("title", "")
    content_tail = window_info.get("content_tail", "")

    # Parse started_at
    started_at = state.get("started_at", "")
    try:
        start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        elapsed = datetime.now(timezone.utc) - start_time
        elapsed_str = format_elapsed(elapsed.total_seconds())
    except Exception:
        elapsed_str = "unknown"

    # Extract activity state and task summary from window title + content
    activity_state, task_summary = parse_activity_state(window_title, content_tail)

    # Prepare terminal content for AI summarization
    content_snippet = prepare_content_for_summary(content_tail)

    # Extract last message for tooltip display
    last_message = extract_last_message(content_tail)

    # Track last activity (content change detection)
    session_id = session_uuid  # Use session UUID as identifier for iTerm
    last_activity_at = track_session_activity(session_id, content_tail)
    last_activity_ago = format_time_ago(last_activity_at)

    return {
        # Standardized session identifiers (preferred)
        "session_id": session_uuid,
        "session_id_short": session_uuid[-8:] if session_uuid else "unknown",
        # Legacy fields (maintained for backwards compatibility)
        "uuid": session_uuid,
        "uuid_short": session_uuid[-8:] if session_uuid else "unknown",
        "project_name": project["name"],  # Use config name, not state file
        "project_dir": state.get("project_dir", project["path"]),
        "started_at": started_at,
        "elapsed": elapsed_str,
        "last_activity_at": last_activity_at,
        "last_activity_ago": last_activity_ago,
        "pid": session_pid,
        "tty": session_tty,
        "status": "active",
        "activity_state": activity_state,
        "window_title": window_title,
        "task_summary": task_summary,
        "content_snippet": content_snippet,
        "last_message": last_message,
        # iTerm-specific fields
        "session_type": "iterm",
    }


def cleanup_stale_state_files(config: dict, active_session_names: set[str]) -> None:
    """Clean up state files that reference non-existent tmux sessions.

    Also cleans up legacy iTerm-only state files (no tmux_session field)
    since iTerm-only mode is deprecated.

    Args:
        config: Configuration dict with 'projects' list
        active_session_names: Set of currently active tmux session names
    """
    for project in config.get("projects", []):
        project_path = Path(project.get("path", ""))
        if not project_path.exists():
            continue

        # Find all .claude-monitor-*.json files
        for state_file in project_path.glob(".claude-monitor-*.json"):
            try:
                state = json.loads(state_file.read_text())
                tmux_session_name = state.get("tmux_session")
                session_type = state.get("session_type", "iterm")

                should_delete = False

                # Delete iTerm-only state files (deprecated)
                if session_type == "iterm" or not tmux_session_name:
                    should_delete = True
                    logger.info(f"Cleaning up legacy iTerm state file: {state_file.name}")
                # Delete tmux state files that reference non-existent sessions
                elif tmux_session_name not in active_session_names:
                    should_delete = True
                    logger.info(f"Cleaning up stale tmux state file: {state_file.name}")

                if should_delete:
                    state_file.unlink()

            except Exception as e:
                logger.warning(f"Error processing state file {state_file}: {e}")


def scan_sessions(config: dict) -> list[dict]:
    """Scan for active Claude Code sessions using the configured terminal backend.

    Discovers sessions by querying the terminal backend (tmux or WezTerm)
    directly, not by scanning for state files. State files are only used
    for iTerm window focus, not for session discovery.

    Stale state files (referencing dead sessions) are automatically cleaned up.

    Args:
        config: Configuration dict with 'projects' list

    Returns:
        List of session dicts with status info
    """
    sessions = []
    projects = config.get("projects", [])
    backend_name = config.get("terminal_backend", "tmux")

    # Select backend functions based on configuration
    if backend_name == "wezterm":
        from lib.backends.wezterm import (
            is_wezterm_available,
            list_sessions as backend_list_sessions,
            get_session_info as backend_get_session_info,
            capture_pane as backend_capture_pane,
        )
        if not is_wezterm_available():
            logger.warning("WezTerm not available - no sessions will be discovered")
            return sessions
        session_type = "wezterm"
    else:
        backend_list_sessions = tmux_list_sessions
        backend_get_session_info = get_session_info
        backend_capture_pane = capture_pane
        if not is_tmux_available():
            logger.warning("tmux not available - no sessions will be discovered")
            return sessions
        session_type = "tmux"

    all_sessions = backend_list_sessions()
    active_session_names = {s.get("name", "") for s in all_sessions}

    # Clean up stale state files
    cleanup_stale_state_files(config, active_session_names)

    # Filter to claude-* sessions only
    claude_sessions = [s for s in all_sessions if s.get("name", "").startswith("claude-")]

    for sess in claude_sessions:
        session_name = sess.get("name", "")

        # Parse session name to get project slug and uuid8
        project_slug, uuid8 = parse_session_name(session_name)

        # Match to config project
        matched_project = match_project(project_slug, projects) if project_slug else None

        # Get detailed session info from backend
        sess_info = backend_get_session_info(session_name)
        if not sess_info:
            continue

        # Build session info
        session = scan_backend_session(
            sess_info, matched_project, project_slug or "", uuid8,
            capture_fn=backend_capture_pane, session_type=session_type,
        )
        if session:
            sessions.append(session)

    return sessions


def parse_activity_state(window_title: str, content_tail: str = "") -> tuple[str, str]:
    """Parse Claude Code window title and terminal content to extract activity state.

    Args:
        window_title: The iTerm window title (may be empty for tmux sessions)
        content_tail: The last ~5000 characters of terminal content

    Returns:
        Tuple of (activity_state, task_summary)

    Activity states:
    - "processing": Claude is actively working (spinner showing)
    - "input_needed": Claude is blocked waiting for user response (question/permission)
    - "idle": Session is idle, ready for new task
    - "unknown": Can't determine state
    """
    # Braille spinner characters indicate processing (Claude's turn - working)
    # Full Unicode braille pattern range
    spinner_chars = set("⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿⡀⡄⡆⡇")
    # Also common loading spinners
    spinner_chars |= set("◐◑◒◓◴◵◶◷⣾⣽⣻⢿⡿⣟⣯⣷⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")

    # Star/asterisk/prompt indicators = session not processing
    idle_chars = set("✳✱✲✴✵✶✷✸*›❯>$▶")

    # Permission/warning characters (used for title cleanup)
    permission_chars = set("?❓⚠️🔒⏸")

    # Patterns in terminal content that indicate Claude is waiting for user input
    # ONLY specific Claude Code UI elements - nothing that could appear in response text
    input_needed_patterns = [
        # Claude Code permission dialog - ONLY these exact UI strings
        "Yes, and don't ask again",
        "Yes, and always allow",
        "Allow once",
        "Allow for this session",
        # Claude Code choice selector (with prompt character)
        "❯ Yes",
        "❯ No",
        "❯ 1.",
        "❯ 2.",
        "❯ 3.",
        # AskUserQuestion tool UI
        "Enter to select",
        "↑↓ to navigate",
    ]

    # Get the first character to determine base state
    first_char = window_title[0] if window_title else ""

    # Check RECENT content for input_needed patterns (not entire history)
    # Old questions/prompts in the terminal buffer can cause false positives
    # Only check last ~1500 chars where current prompts would appear
    recent_content = content_tail[-1500:].lower() if content_tail else ""
    is_input_needed = any(pattern.lower() in recent_content for pattern in input_needed_patterns)

    # For content-based detection, only check RECENT content (last ~1500 chars)
    # to avoid false positives from old tool executions in history
    recent_content_raw = content_tail[-1500:] if content_tail else ""

    # ACTIVE processing indicators in recent content
    # These indicate Claude is CURRENTLY working
    # Note: Claude Code UI shows the ❯ prompt BELOW the processing output,
    # so we can't use line position to determine state.
    #
    # IMPORTANT distinctions:
    # - "· thinking)" = ACTIVE (present tense)
    # - "· thought for" = COMPLETED (past tense)
    # - "⎿  Running…" = completed command showing output (NOT active)
    # - "⏺ ... Running…" without ⎿ prefix = ACTIVE command

    # Check for ACTIVE processing - must be currently happening
    # The "(esc to interrupt)" indicator appears ABOVE the prompt and status bar
    # Status bar + prompt can be 400+ chars, so check last 800 chars
    tail_content = content_tail[-800:] if content_tail else ""
    has_esc_to_interrupt = "(esc to interrupt" in tail_content

    # If "(esc to interrupt)" is in the tail, Claude is actively processing
    is_actively_processing = has_esc_to_interrupt

    # COMPLETION indicators override processing - if turn is complete, not processing
    # "✻ Baked for", "✻ Brewed for" etc. mean Claude finished
    is_completed = is_turn_complete(recent_content_raw)

    # Check last few lines for idle state
    # We're idle if the last meaningful content shows completion (✻ Verb for Xm Xs)
    last_lines = content_tail.strip().split("\n") if content_tail else []

    # Find if there's an idle prompt (❯) that represents waiting for NEW input
    # Check regardless of processing state - use completion marker as deciding factor
    # Note: Claude Code UI has ~5-10 lines of chrome below the prompt (dividers, status bar)
    # so we need to check more than 10 lines to reliably find the prompt
    has_idle_prompt = False
    for line in reversed(last_lines[-25:]):
        stripped = line.strip()
        # Skip empty lines and status bar lines
        if not stripped or stripped.startswith("samotage@") or stripped.startswith("⏵"):
            continue
        # If we hit a prompt line first (before any processing), we're idle
        if stripped.startswith("❯") or stripped == "❯":
            has_idle_prompt = True
            break
        # If we hit processing output, not idle
        if any(p in stripped for p in ["⏺", "⎿", "✢", "✻"]):
            break

    # Override processing detection if turn is completed
    # If we see a completion marker (✻ Baked for...) in recent content,
    # old "thinking)" or "Running…" patterns are from completed work, not active
    if is_completed:
        is_actively_processing = False

    if first_char in spinner_chars:
        activity_state = "processing"
    elif first_char in idle_chars:
        # Check terminal content to distinguish input_needed vs idle
        activity_state = "input_needed" if is_input_needed else "idle"
    elif is_input_needed:
        # If content shows input prompts, mark as input_needed
        activity_state = "input_needed"
    elif not window_title and content_tail:
        # For tmux sessions without window title, use content-based detection
        # Priority: active processing > completed turn > idle prompt
        if is_actively_processing:
            activity_state = "processing"
        elif is_completed or has_idle_prompt:
            activity_state = "idle"
        else:
            activity_state = "unknown"
    else:
        activity_state = "unknown"

    # Extract task summary (remove status prefix and clean up)
    # Remove the UUID from the title if present
    uuid_pattern = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        re.IGNORECASE,
    )
    cleaned = uuid_pattern.sub("", window_title).strip()

    # Remove the status prefix character
    if cleaned and cleaned[0] in spinner_chars | idle_chars | permission_chars:
        cleaned = cleaned[1:].strip()

    # Clean up common prefixes/suffixes
    cleaned = cleaned.strip("- |:")

    return (activity_state, cleaned if cleaned else window_title)


def extract_task_summary(window_title: str) -> str:
    """Extract meaningful task summary from iTerm window title.

    Args:
        window_title: The iTerm window title

    Returns:
        Cleaned task summary string
    """
    _, summary = parse_activity_state(window_title, "")
    return summary


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as human-readable string.

    Args:
        seconds: Number of elapsed seconds

    Returns:
        Formatted string like "5s", "12m", or "2h 30m"
    """
    if seconds < 0:
        return "just now"
    elif seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}m"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
