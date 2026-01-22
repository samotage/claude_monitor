"""OpenRouter API call logging for Claude Headspace.

This module handles:
- Log data format specification
- Reading OpenRouter API call logs from JSONL file
- Filtering and searching log entries
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

# Log file path
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")
OPENROUTER_LOG_FILE = os.path.join(LOG_DIR, "openrouter.jsonl")


@dataclass
class LogEntry:
    """Data structure for an OpenRouter API call log entry.

    Fields:
        id: Unique identifier for the log entry
        timestamp: ISO 8601 timestamp of when the call was made
        model: Model identifier (e.g., "anthropic/claude-3-haiku")
        request_messages: List of message dicts sent to the API
        response_content: Text content returned from the API (None if failed)
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost: Cost in USD (calculated from tokens and model pricing)
        success: Whether the API call succeeded
        error: Error message if the call failed (None if success)
        caller: Optional identifier for what triggered the call (e.g., "compression", "priorities")
    """
    id: str
    timestamp: str
    model: str
    request_messages: list
    response_content: Optional[str]
    input_tokens: int
    output_tokens: int
    cost: float
    success: bool
    error: Optional[str] = None
    caller: Optional[str] = None


def ensure_log_directory():
    """Ensure the log directory exists."""
    os.makedirs(LOG_DIR, exist_ok=True)


def read_openrouter_logs() -> list[dict]:
    """Read all OpenRouter API call logs from the log file.

    Returns:
        List of log entry dicts, newest first
    """
    if not os.path.exists(OPENROUTER_LOG_FILE):
        return []

    entries = []
    try:
        with open(OPENROUTER_LOG_FILE, "r", encoding="utf-8") as f:
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


def get_logs_since(since_timestamp: Optional[str] = None) -> list[dict]:
    """Get log entries since a given timestamp.

    Args:
        since_timestamp: ISO 8601 timestamp. If None, returns all logs.

    Returns:
        List of log entry dicts newer than the timestamp, newest first
    """
    all_logs = read_openrouter_logs()

    if since_timestamp is None:
        return all_logs

    filtered = [
        entry for entry in all_logs
        if entry.get("timestamp", "") > since_timestamp
    ]
    return filtered


def search_logs(query: str, logs: Optional[list[dict]] = None) -> list[dict]:
    """Search log entries by query string.

    Searches in: model, response_content, error, caller, and request_messages content.

    Args:
        query: Search query (case-insensitive)
        logs: Optional list of logs to search. If None, reads all logs.

    Returns:
        List of matching log entry dicts, newest first
    """
    if logs is None:
        logs = read_openrouter_logs()

    if not query:
        return logs

    query_lower = query.lower()
    results = []

    for entry in logs:
        # Search in various fields
        searchable_fields = [
            entry.get("model", ""),
            entry.get("response_content", "") or "",
            entry.get("error", "") or "",
            entry.get("caller", "") or "",
        ]

        # Also search in request messages
        for msg in entry.get("request_messages", []):
            searchable_fields.append(msg.get("content", "") or "")

        # Check if query matches any field
        combined = " ".join(str(f) for f in searchable_fields).lower()
        if query_lower in combined:
            results.append(entry)

    return results


def write_log_entry(entry: LogEntry) -> bool:
    """Write a log entry to the log file.

    Args:
        entry: LogEntry dataclass instance

    Returns:
        True if write was successful
    """
    ensure_log_directory()

    try:
        entry_dict = asdict(entry)
        with open(OPENROUTER_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_dict) + "\n")
        return True
    except IOError:
        return False


def create_log_entry(
    model: str,
    request_messages: list,
    response_content: Optional[str],
    input_tokens: int,
    output_tokens: int,
    cost: float,
    success: bool,
    error: Optional[str] = None,
    caller: Optional[str] = None,
) -> LogEntry:
    """Create a new log entry with auto-generated ID and timestamp.

    Args:
        model: Model identifier
        request_messages: List of message dicts sent to API
        response_content: Response text (None if failed)
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost: Cost in USD
        success: Whether call succeeded
        error: Error message if failed
        caller: What triggered the call

    Returns:
        LogEntry instance
    """
    import uuid

    return LogEntry(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        model=model,
        request_messages=request_messages,
        response_content=response_content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        success=success,
        error=error,
        caller=caller,
    )


def get_log_stats() -> dict:
    """Get aggregate statistics from the logs.

    Returns:
        Dict with total_calls, successful_calls, failed_calls,
        total_cost, total_input_tokens, total_output_tokens
    """
    logs = read_openrouter_logs()

    stats = {
        "total_calls": len(logs),
        "successful_calls": 0,
        "failed_calls": 0,
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }

    for entry in logs:
        if entry.get("success"):
            stats["successful_calls"] += 1
        else:
            stats["failed_calls"] += 1
        stats["total_cost"] += entry.get("cost", 0) or 0
        stats["total_input_tokens"] += entry.get("input_tokens", 0) or 0
        stats["total_output_tokens"] += entry.get("output_tokens", 0) or 0

    return stats
