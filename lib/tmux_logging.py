"""tmux session message logging for Claude Headspace.

This module handles:
- Log data format specification for tmux operations
- Reading/writing tmux session logs from JSONL file
- Filtering and searching log entries
- Payload truncation for large messages
- Turn pair retrieval (turn_start + turn_complete linked by correlation_id)

Event types:
- send_keys: Text sent to tmux session (direction=out)
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

# Log file path (same directory as OpenRouter logs)
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")
TMUX_LOG_FILE = os.path.join(LOG_DIR, "tmux.jsonl")

# Maximum payload size before truncation (10KB)
MAX_PAYLOAD_SIZE = 10 * 1024


@dataclass
class TmuxLogEntry:
    """Data structure for a tmux session log entry.

    Fields:
        id: Unique identifier for the log entry
        timestamp: ISO 8601 timestamp of when the operation occurred
        session_id: Identifier for the session (usually project name)
        tmux_session_name: The actual tmux session name (e.g., claude-my-project)
        direction: "in" for incoming (capture), "out" for outgoing (send)
        event_type: Type of event (send_keys, capture_pane, session_started, etc.)
        payload: Message content (None when debug logging is off)
        correlation_id: Links related send/capture operations
        truncated: Whether payload was truncated
        original_size: Original payload size in bytes (set when truncated)
        success: Whether the operation succeeded
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


def write_tmux_log_entry(entry: TmuxLogEntry) -> bool:
    """Write a log entry to the tmux log file.

    Args:
        entry: TmuxLogEntry dataclass instance

    Returns:
        True if write was successful
    """
    ensure_log_directory()

    try:
        entry_dict = asdict(entry)
        with open(TMUX_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_dict) + "\n")
        return True
    except IOError:
        return False


def create_tmux_log_entry(
    session_id: str,
    tmux_session_name: str,
    direction: str,
    event_type: str,
    payload: Optional[str] = None,
    correlation_id: Optional[str] = None,
    success: bool = True,
    debug_enabled: bool = False,
) -> TmuxLogEntry:
    """Create a new tmux log entry with auto-generated ID and timestamp.

    Args:
        session_id: Session identifier (project name)
        tmux_session_name: The tmux session name
        direction: "in" or "out"
        event_type: Type of operation
        payload: Message content (only logged if debug_enabled)
        correlation_id: Links related operations
        success: Whether operation succeeded
        debug_enabled: If False, payload is not recorded

    Returns:
        TmuxLogEntry instance
    """
    truncated = False
    original_size = None
    final_payload = None

    if debug_enabled and payload is not None:
        final_payload, truncated, original_size = truncate_payload(payload)
        if not truncated:
            original_size = None  # Only set when actually truncated

    return TmuxLogEntry(
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
    )


def read_tmux_logs() -> list[dict]:
    """Read all tmux log entries from the log file.

    Returns:
        List of log entry dicts, newest first
    """
    if not os.path.exists(TMUX_LOG_FILE):
        return []

    entries = []
    try:
        with open(TMUX_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
    except IOError:
        return []

    # Sort by timestamp descending (newest first)
    entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return entries


def get_tmux_logs_since(since_timestamp: Optional[str] = None) -> list[dict]:
    """Get log entries since a given timestamp.

    Args:
        since_timestamp: ISO 8601 timestamp. If None, returns all logs.

    Returns:
        List of log entry dicts newer than the timestamp, newest first
    """
    all_logs = read_tmux_logs()

    if since_timestamp is None:
        return all_logs

    filtered = [
        entry for entry in all_logs
        if entry.get("timestamp", "") > since_timestamp
    ]
    return filtered


def search_tmux_logs(
    query: str,
    logs: Optional[list[dict]] = None,
    session_id: Optional[str] = None,
) -> list[dict]:
    """Search log entries by query string and/or session_id.

    Searches in: session_id, tmux_session_name, event_type, payload, correlation_id

    Args:
        query: Search query (case-insensitive). Empty string matches all.
        logs: Optional list of logs to search. If None, reads all logs.
        session_id: Optional filter by session_id

    Returns:
        List of matching log entry dicts, newest first
    """
    if logs is None:
        logs = read_tmux_logs()

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
        ]

        # Check if query matches any field
        combined = " ".join(str(f) for f in searchable_fields).lower()
        if query_lower in combined:
            results.append(entry)

    return results


def get_tmux_log_stats() -> dict:
    """Get aggregate statistics from the tmux logs.

    Returns:
        Dict with total_entries, send_count, capture_count,
        success_count, failure_count, unique_sessions
    """
    logs = read_tmux_logs()

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
        logs = read_tmux_logs()

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
