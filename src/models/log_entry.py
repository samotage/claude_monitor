"""Log entry models for Claude Headspace.

Pydantic models for OpenRouter API call logs and terminal session logs.
Migrated from lib/logging.py and lib/terminal_logging.py.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class OpenRouterLogEntry(BaseModel):
    """Data structure for an OpenRouter API call log entry.

    Attributes:
        id: Unique identifier for the log entry.
        timestamp: ISO 8601 timestamp of when the call was made.
        model: Model identifier (e.g., "anthropic/claude-3-haiku").
        request_messages: List of message dicts sent to the API.
        response_content: Text content returned from the API (None if failed).
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cost: Cost in USD (calculated from tokens and model pricing).
        success: Whether the API call succeeded.
        error: Error message if the call failed (None if success).
        caller: Optional identifier for what triggered the call.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model: str
    request_messages: list[dict[str, Any]]
    response_content: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    success: bool = True
    error: str | None = None
    caller: str | None = None


class TerminalLogEntry(BaseModel):
    """Data structure for a terminal session log entry.

    Attributes:
        id: Unique identifier for the log entry.
        timestamp: ISO 8601 timestamp of when the operation occurred.
        session_id: Identifier for the session (usually project name).
        tmux_session_name: The session name (kept for compatibility).
        direction: "in" for incoming (capture), "out" for outgoing (send).
        event_type: Type of event (send_keys, capture_pane, etc.).
        payload: Message content (None when debug logging is off).
        correlation_id: Links related send/capture operations.
        truncated: Whether payload was truncated.
        original_size: Original payload size in bytes (set when truncated).
        success: Whether the operation succeeded.
        backend: Terminal backend ("tmux" or "wezterm").
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str
    tmux_session_name: str
    direction: str  # "in" or "out"
    event_type: str
    payload: str | None = None
    correlation_id: str | None = None
    truncated: bool = False
    original_size: int | None = None
    success: bool = True
    backend: str = "tmux"


class OpenRouterLogStats(BaseModel):
    """Aggregate statistics for OpenRouter API calls.

    Attributes:
        total_calls: Total number of API calls.
        successful_calls: Number of successful calls.
        failed_calls: Number of failed calls.
        total_cost: Total cost in USD.
        total_input_tokens: Total input tokens used.
        total_output_tokens: Total output tokens used.
    """

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class TerminalLogStats(BaseModel):
    """Aggregate statistics for terminal session logs.

    Attributes:
        total_entries: Total number of log entries.
        send_count: Number of outgoing (send) operations.
        capture_count: Number of incoming (capture) operations.
        success_count: Number of successful operations.
        failure_count: Number of failed operations.
        unique_sessions: Number of unique sessions.
    """

    total_entries: int = 0
    send_count: int = 0
    capture_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    unique_sessions: int = 0


class TurnPair(BaseModel):
    """A matched turn_start/turn_complete pair.

    Turn pairs are linked by their correlation_id (turn_id).
    Represents a complete user command -> Claude response cycle.

    Attributes:
        turn_id: The unique identifier linking the pair.
        start: The turn_start log entry (or None if missing).
        complete: The turn_complete log entry (or None if missing).
        command: User's command (from start or complete payload).
        duration_seconds: Turn duration (from complete payload).
        response_summary: Claude's response summary (from complete payload).
    """

    turn_id: str
    start: dict[str, Any] | None = None
    complete: dict[str, Any] | None = None
    command: str | None = None
    duration_seconds: float | None = None
    response_summary: str | None = None
