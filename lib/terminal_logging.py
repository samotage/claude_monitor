"""Terminal session message logging for Claude Headspace.

This module handles:
- Log data format specification for terminal operations (tmux, WezTerm, etc.)
- Reading/writing terminal session logs from JSONL file
- Filtering and searching log entries
- Payload truncation for large messages
- Turn pair retrieval (turn_start + turn_complete linked by correlation_id)
- Backend identification for multi-backend support

Event types:
- send_keys: Text sent to terminal session (direction=out)
- capture_pane: Pane content captured (direction=in)
- session_started: Session lifecycle event
- turn_start: User command sent to Claude (direction=out)
  - Payload: {turn_id, command, started_at}
  - correlation_id: turn_id (links to turn_complete)
- turn_complete: Claude response finished (direction=in)
  - Payload: {turn_id, command, result_state, completion_marker, duration_seconds, started_at, response_summary}
  - correlation_id: turn_id (links to turn_start)
"""

import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

# Log file paths (same directory as OpenRouter logs)
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")
TERMINAL_LOG_FILE = os.path.join(LOG_DIR, "terminal.jsonl")
# Legacy path for backward compatibility
LEGACY_LOG_FILE = os.path.join(LOG_DIR, "tmux.jsonl")

# Maximum payload size before truncation (10KB)
MAX_PAYLOAD_SIZE = 10 * 1024

# Log rotation configuration
MAX_LOG_SIZE_MB = 10  # Rotate when file exceeds this size
MAX_LOG_FILES = 5  # Number of rotated files to keep


@dataclass
class TerminalLogEntry:
    """Data structure for a terminal session log entry.

    Fields:
        id: Unique identifier for the log entry
        timestamp: ISO 8601 timestamp of when the operation occurred
        session_id: Identifier for the session (usually project name)
        tmux_session_name: The session name (e.g., claude-my-project) - kept for compatibility
        direction: "in" for incoming (capture), "out" for outgoing (send)
        event_type: Type of event (send_keys, capture_pane, session_started, etc.)
        payload: Message content (None when debug logging is off)
        correlation_id: Links related send/capture operations
        truncated: Whether payload was truncated
        original_size: Original payload size in bytes (set when truncated)
        success: Whether the operation succeeded
        backend: Terminal backend that produced this entry ("tmux" or "wezterm")
    """
    id: str
    timestamp: str
    session_id: str
    tmux_session_name: str
    direction: str  # "in" or "out"
    event_type: str
    payload: Optional[str] = None
    correlation_id: Optional[str] = None
    truncated: bool = False
    original_size: Optional[int] = None
    success: bool = True
    backend: str = "tmux"  # Default to "tmux" for backward compatibility


# Backward compatibility aliases
TmuxLogEntry = TerminalLogEntry
TMUX_LOG_FILE = TERMINAL_LOG_FILE


def _get_active_log_file() -> str:
    """Get the path to the active log file.

    Implements backward compatibility:
    - If terminal.jsonl exists, use it
    - If only tmux.jsonl exists, use it (legacy)
    - Otherwise, use terminal.jsonl for new logs

    Returns:
        Path to the log file to use
    """
    if os.path.exists(TERMINAL_LOG_FILE):
        return TERMINAL_LOG_FILE
    if os.path.exists(LEGACY_LOG_FILE):
        return LEGACY_LOG_FILE
    return TERMINAL_LOG_FILE


def ensure_log_directory():
    """Ensure the log directory exists."""
    os.makedirs(LOG_DIR, exist_ok=True)


def truncate_payload(payload: str) -> tuple[str, bool, int]:
    """Truncate payload if it exceeds the maximum size.

    Args:
        payload: The payload string to potentially truncate

    Returns:
        Tuple of (truncated_payload, was_truncated, original_size)
    """
    if payload is None:
        return None, False, 0

    payload_bytes = payload.encode('utf-8')
    original_size = len(payload_bytes)

    if original_size <= MAX_PAYLOAD_SIZE:
        return payload, False, original_size

    # Truncate to MAX_PAYLOAD_SIZE bytes, then decode safely
    truncated_bytes = payload_bytes[:MAX_PAYLOAD_SIZE]
    # Decode with error handling in case we cut in the middle of a multi-byte char
    truncated_payload = truncated_bytes.decode('utf-8', errors='ignore')
    truncated_payload += "\n... [TRUNCATED]"

    return truncated_payload, True, original_size


def _rotate_log_if_needed(log_file: str) -> None:
    """Rotate log file if it exceeds max size.

    Rotation scheme: file.jsonl -> file.jsonl.1 -> file.jsonl.2 -> ...
    Oldest files beyond MAX_LOG_FILES are deleted.

    Args:
        log_file: Path to the log file to check
    """
    if not os.path.exists(log_file):
        return

    try:
        size_mb = os.path.getsize(log_file) / (1024 * 1024)
        if size_mb < MAX_LOG_SIZE_MB:
            return

        # Rotate existing backups (shift numbers up)
        for i in range(MAX_LOG_FILES - 1, 0, -1):
            old_name = f"{log_file}.{i}"
            new_name = f"{log_file}.{i + 1}"
            if os.path.exists(old_name):
                if i + 1 >= MAX_LOG_FILES:
                    os.remove(old_name)  # Delete oldest
                else:
                    os.rename(old_name, new_name)

        # Rotate current log to .1
        os.rename(log_file, f"{log_file}.1")
        print(f"Info: Rotated log file {os.path.basename(log_file)} (exceeded {MAX_LOG_SIZE_MB}MB)")

    except OSError as e:
        print(f"Warning: Log rotation failed: {e}")


def write_terminal_log_entry(entry: TerminalLogEntry) -> bool:
    """Write a log entry to the terminal log file.

    Automatically rotates the log file if it exceeds MAX_LOG_SIZE_MB.
    Always writes to the new terminal.jsonl file.

    Args:
        entry: TerminalLogEntry dataclass instance

    Returns:
        True if write was successful
    """
    ensure_log_directory()

    # Always write to new log file location
    _rotate_log_if_needed(TERMINAL_LOG_FILE)

    try:
        entry_dict = asdict(entry)
        with open(TERMINAL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_dict) + "\n")
        return True
    except IOError:
        return False


# Backward compatibility alias
write_tmux_log_entry = write_terminal_log_entry


def create_terminal_log_entry(
    session_id: str,
    tmux_session_name: str,
    direction: str,
    event_type: str,
    payload: Optional[str] = None,
    correlation_id: Optional[str] = None,
    success: bool = True,
    debug_enabled: bool = False,
    backend: str = "tmux",
) -> TerminalLogEntry:
    """Create a new terminal log entry with auto-generated ID and timestamp.

    Args:
        session_id: Session identifier (project name)
        tmux_session_name: The session name
        direction: "in" or "out"
        event_type: Type of operation
        payload: Message content (only logged if debug_enabled)
        correlation_id: Links related operations
        success: Whether operation succeeded
        debug_enabled: If False, payload is not recorded
        backend: Terminal backend identifier ("tmux" or "wezterm")

    Returns:
        TerminalLogEntry instance
    """
    truncated = False
    original_size = None
    final_payload = None

    if debug_enabled and payload is not None:
        final_payload, truncated, original_size = truncate_payload(payload)
        if not truncated:
            original_size = None  # Only set when actually truncated

    return TerminalLogEntry(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
        tmux_session_name=tmux_session_name,
        direction=direction,
        event_type=event_type,
        payload=final_payload,
        correlation_id=correlation_id,
        truncated=truncated,
        original_size=original_size,
        success=success,
        backend=backend,
    )


# Backward compatibility alias
create_tmux_log_entry = create_terminal_log_entry


def read_terminal_logs(backend: Optional[str] = None) -> list[dict]:
    """Read all terminal log entries from the log file.

    Args:
        backend: Optional filter by backend ("tmux" or "wezterm")

    Returns:
        List of log entry dicts, newest first
    """
    log_file = _get_active_log_file()

    if not os.path.exists(log_file):
        return []

    entries = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        # Apply default backend for legacy entries
                        if "backend" not in entry:
                            entry["backend"] = "tmux"
                        entries.append(entry)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
    except IOError:
        return []

    # Filter by backend if specified
    if backend:
        entries = [e for e in entries if e.get("backend") == backend]

    # Sort by timestamp descending (newest first)
    entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return entries


# Backward compatibility alias
read_tmux_logs = read_terminal_logs


def get_terminal_logs_since(since_timestamp: Optional[str] = None, backend: Optional[str] = None) -> list[dict]:
    """Get log entries since a given timestamp.

    Args:
        since_timestamp: ISO 8601 timestamp. If None, returns all logs.
        backend: Optional filter by backend ("tmux" or "wezterm")

    Returns:
        List of log entry dicts newer than the timestamp, newest first
    """
    all_logs = read_terminal_logs(backend=backend)

    if since_timestamp is None:
        return all_logs

    filtered = [
        entry for entry in all_logs
        if entry.get("timestamp", "") > since_timestamp
    ]
    return filtered


# Backward compatibility alias
get_tmux_logs_since = get_terminal_logs_since


def search_terminal_logs(
    query: str,
    logs: Optional[list[dict]] = None,
    session_id: Optional[str] = None,
    backend: Optional[str] = None,
) -> list[dict]:
    """Search log entries by query string and/or session_id.

    Searches in: session_id, tmux_session_name, event_type, payload, correlation_id, backend

    Args:
        query: Search query (case-insensitive). Empty string matches all.
        logs: Optional list of logs to search. If None, reads all logs.
        session_id: Optional filter by session_id
        backend: Optional filter by backend ("tmux" or "wezterm")

    Returns:
        List of matching log entry dicts, newest first
    """
    if logs is None:
        logs = read_terminal_logs(backend=backend)
    elif backend:
        logs = [e for e in logs if e.get("backend") == backend]

    # Filter by session_id first if provided
    if session_id:
        logs = [entry for entry in logs if entry.get("session_id") == session_id]

    if not query:
        return logs

    query_lower = query.lower()
    results = []

    for entry in logs:
        # Search in various fields
        searchable_fields = [
            entry.get("session_id", ""),
            entry.get("tmux_session_name", ""),
            entry.get("event_type", ""),
            entry.get("payload", "") or "",
            entry.get("correlation_id", "") or "",
            entry.get("direction", ""),
            entry.get("backend", ""),
        ]

        # Check if query matches any field
        combined = " ".join(str(f) for f in searchable_fields).lower()
        if query_lower in combined:
            results.append(entry)

    return results


# Backward compatibility alias
search_tmux_logs = search_terminal_logs


def get_terminal_log_stats(backend: Optional[str] = None) -> dict:
    """Get aggregate statistics from the terminal logs.

    Args:
        backend: Optional filter by backend ("tmux" or "wezterm")

    Returns:
        Dict with total_entries, send_count, capture_count,
        success_count, failure_count, unique_sessions
    """
    logs = read_terminal_logs(backend=backend)

    sessions = set()
    stats = {
        "total_entries": len(logs),
        "send_count": 0,
        "capture_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "unique_sessions": 0,
    }

    for entry in logs:
        direction = entry.get("direction", "")
        if direction == "out":
            stats["send_count"] += 1
        elif direction == "in":
            stats["capture_count"] += 1

        if entry.get("success", True):
            stats["success_count"] += 1
        else:
            stats["failure_count"] += 1

        session_id = entry.get("session_id")
        if session_id:
            sessions.add(session_id)

    stats["unique_sessions"] = len(sessions)
    return stats


# Backward compatibility alias
get_tmux_log_stats = get_terminal_log_stats


def clear_terminal_logs() -> bool:
    """Clear all terminal log entries by truncating the log file.

    Returns:
        True if successful, False otherwise
    """
    ensure_log_directory()
    try:
        # Truncate the terminal log file
        with open(TERMINAL_LOG_FILE, "w", encoding="utf-8") as f:
            pass  # Just open in write mode to truncate
        return True
    except IOError:
        return False


def get_turn_pairs(
    logs: Optional[list[dict]] = None,
    session_id: Optional[str] = None,
) -> list[dict]:
    """Retrieve matched turn_start/turn_complete pairs from logs.

    Turn pairs are linked by their correlation_id (which equals turn_id).
    Each pair represents a complete user command → Claude response cycle.

    Args:
        logs: Optional list of logs to search. If None, reads all logs.
        session_id: Optional filter by session_id

    Returns:
        List of turn pair dicts, newest first. Each dict contains:
        - turn_id: The unique identifier linking the pair
        - start: The turn_start log entry (or None if missing)
        - complete: The turn_complete log entry (or None if missing)
        - command: User's command (from start or complete payload)
        - duration_seconds: Turn duration (from complete payload, or None)
        - response_summary: Claude's response summary (from complete payload, or None)
    """
    if logs is None:
        logs = read_terminal_logs()

    # Filter by session_id if provided
    if session_id:
        logs = [entry for entry in logs if entry.get("session_id") == session_id]

    # Filter to turn events only
    turn_logs = [
        entry for entry in logs
        if entry.get("event_type") in ("turn_start", "turn_complete")
    ]

    # Group by correlation_id (turn_id)
    turns_by_id: dict[str, dict] = {}

    for entry in turn_logs:
        turn_id = entry.get("correlation_id")
        if not turn_id:
            continue

        if turn_id not in turns_by_id:
            turns_by_id[turn_id] = {
                "turn_id": turn_id,
                "start": None,
                "complete": None,
            }

        event_type = entry.get("event_type")
        if event_type == "turn_start":
            turns_by_id[turn_id]["start"] = entry
        elif event_type == "turn_complete":
            turns_by_id[turn_id]["complete"] = entry

    # Build result list with extracted fields
    result = []
    for turn_id, pair in turns_by_id.items():
        # Extract command from either start or complete
        command = None
        if pair["start"]:
            try:
                payload = json.loads(pair["start"].get("payload", "{}"))
                command = payload.get("command")
            except (json.JSONDecodeError, TypeError):
                pass

        if not command and pair["complete"]:
            try:
                payload = json.loads(pair["complete"].get("payload", "{}"))
                command = payload.get("command")
            except (json.JSONDecodeError, TypeError):
                pass

        # Extract duration and response_summary from complete
        duration_seconds = None
        response_summary = None
        if pair["complete"]:
            try:
                payload = json.loads(pair["complete"].get("payload", "{}"))
                duration_seconds = payload.get("duration_seconds")
                response_summary = payload.get("response_summary")
            except (json.JSONDecodeError, TypeError):
                pass

        result.append({
            "turn_id": turn_id,
            "start": pair["start"],
            "complete": pair["complete"],
            "command": command,
            "duration_seconds": duration_seconds,
            "response_summary": response_summary,
        })

    # Sort by timestamp of complete (or start if no complete), newest first
    def get_timestamp(pair: dict) -> str:
        if pair["complete"]:
            return pair["complete"].get("timestamp", "")
        if pair["start"]:
            return pair["start"].get("timestamp", "")
        return ""

    result.sort(key=get_timestamp, reverse=True)
    return result
