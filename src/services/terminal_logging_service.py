"""Terminal session message logging service for Claude Headspace.

Provides functionality for reading, writing, and searching terminal session logs.
Migrated from lib/terminal_logging.py to use Pydantic models and service pattern.

Event types:
- send_keys: Text sent to terminal session (direction=out)
- capture_pane: Pane content captured (direction=in)
- session_started: Session lifecycle event
- turn_start: User command sent to Claude (direction=out)
- turn_complete: Claude response finished (direction=in)
"""

import json
import logging
from pathlib import Path

from src.models.log_entry import TerminalLogEntry, TerminalLogStats, TurnPair

logger = logging.getLogger(__name__)

# Log file paths
LOG_DIR = Path(__file__).parent.parent.parent / "data" / "logs"
TERMINAL_LOG_FILE = LOG_DIR / "terminal.jsonl"
LEGACY_LOG_FILE = LOG_DIR / "tmux.jsonl"


class TerminalLoggingService:
    """Service for managing terminal session logs.

    Handles:
    - Reading JSONL log entries with backend filtering
    - Writing new log entries with rotation
    - Filtering and searching logs
    - Computing aggregate statistics
    - Retrieving turn pairs (start/complete cycles)
    """

    def __init__(
        self,
        log_dir: Path | None = None,
        max_log_size_mb: int = 10,
        max_log_files: int = 5,
        max_payload_size: int = 10 * 1024,
        debug_enabled: bool = False,
    ):
        """Initialize the terminal logging service.

        Args:
            log_dir: Directory for log files. Defaults to data/logs.
            max_log_size_mb: Rotate when file exceeds this size.
            max_log_files: Number of rotated files to keep.
            max_payload_size: Maximum payload size before truncation.
            debug_enabled: Whether to log payload content.
        """
        self.log_dir = log_dir or LOG_DIR
        self.log_file = self.log_dir / "terminal.jsonl"
        self.legacy_log_file = self.log_dir / "tmux.jsonl"
        self.max_log_size_mb = max_log_size_mb
        self.max_log_files = max_log_files
        self.max_payload_size = max_payload_size
        self._debug_enabled = debug_enabled

    @property
    def debug_enabled(self) -> bool:
        """Get debug logging state."""
        return self._debug_enabled

    @debug_enabled.setter
    def debug_enabled(self, value: bool) -> None:
        """Set debug logging state."""
        self._debug_enabled = value

    def _get_active_log_file(self) -> Path:
        """Get the path to the active log file.

        Implements backward compatibility:
        - If terminal.jsonl exists, use it
        - If only tmux.jsonl exists, use it (legacy)
        - Otherwise, use terminal.jsonl for new logs

        Returns:
            Path to the log file to use.
        """
        if self.log_file.exists():
            return self.log_file
        if self.legacy_log_file.exists():
            return self.legacy_log_file
        return self.log_file

    def ensure_log_directory(self) -> None:
        """Ensure the log directory exists."""
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def truncate_payload(self, payload: str | None) -> tuple[str | None, bool, int]:
        """Truncate payload if it exceeds the maximum size.

        Args:
            payload: The payload string to potentially truncate.

        Returns:
            Tuple of (truncated_payload, was_truncated, original_size).
        """
        if payload is None:
            return None, False, 0

        payload_bytes = payload.encode("utf-8")
        original_size = len(payload_bytes)

        if original_size <= self.max_payload_size:
            return payload, False, original_size

        # Truncate to max size bytes, then decode safely
        truncated_bytes = payload_bytes[: self.max_payload_size]
        # Decode with error handling in case we cut in middle of multi-byte char
        truncated_payload = truncated_bytes.decode("utf-8", errors="ignore")
        truncated_payload += "\n... [TRUNCATED]"

        return truncated_payload, True, original_size

    def _rotate_log_if_needed(self) -> None:
        """Rotate log file if it exceeds max size.

        Rotation scheme: file.jsonl -> file.jsonl.1 -> file.jsonl.2 -> ...
        Oldest files beyond max_log_files are deleted.
        """
        if not self.log_file.exists():
            return

        try:
            size_mb = self.log_file.stat().st_size / (1024 * 1024)
            if size_mb < self.max_log_size_mb:
                return

            # Rotate existing backups (shift numbers up)
            for i in range(self.max_log_files - 1, 0, -1):
                old_name = Path(f"{self.log_file}.{i}")
                new_name = Path(f"{self.log_file}.{i + 1}")
                if old_name.exists():
                    if i + 1 >= self.max_log_files:
                        old_name.unlink()  # Delete oldest
                    else:
                        old_name.rename(new_name)

            # Rotate current log to .1
            self.log_file.rename(Path(f"{self.log_file}.1"))
            logger.info(
                f"Rotated log file {self.log_file.name} " f"(exceeded {self.max_log_size_mb}MB)"
            )

        except OSError as e:
            logger.warning(f"Log rotation failed: {e}")

    def create_log_entry(
        self,
        session_id: str,
        tmux_session_name: str,
        direction: str,
        event_type: str,
        payload: str | None = None,
        correlation_id: str | None = None,
        success: bool = True,
        backend: str = "tmux",
    ) -> TerminalLogEntry:
        """Create a new terminal log entry with auto-generated ID and timestamp.

        Args:
            session_id: Session identifier (project name).
            tmux_session_name: The session name.
            direction: "in" or "out".
            event_type: Type of operation.
            payload: Message content (only logged if debug_enabled).
            correlation_id: Links related operations.
            success: Whether operation succeeded.
            backend: Terminal backend identifier ("tmux" or "wezterm").

        Returns:
            TerminalLogEntry instance.
        """
        truncated = False
        original_size = None
        final_payload = None

        if self._debug_enabled and payload is not None:
            final_payload, truncated, orig_size = self.truncate_payload(payload)
            original_size = None if not truncated else orig_size

        return TerminalLogEntry(
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

    def write_log_entry(self, entry: TerminalLogEntry) -> bool:
        """Write a log entry to the terminal log file.

        Automatically rotates the log file if it exceeds max size.
        Always writes to the new terminal.jsonl file.

        Args:
            entry: TerminalLogEntry instance.

        Returns:
            True if write was successful.
        """
        self.ensure_log_directory()

        # Check if rotation is needed before writing
        self._rotate_log_if_needed()

        try:
            entry_dict = entry.model_dump(mode="json")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry_dict) + "\n")
            return True
        except OSError as e:
            logger.error(f"Error writing log entry: {e}")
            return False

    def read_logs(self, backend: str | None = None) -> list[dict]:
        """Read all terminal log entries from the log file.

        Args:
            backend: Optional filter by backend ("tmux" or "wezterm").

        Returns:
            List of log entry dicts, newest first.
        """
        log_file = self._get_active_log_file()

        if not log_file.exists():
            return []

        entries = []
        try:
            with open(log_file, encoding="utf-8") as f:
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
        except OSError as e:
            logger.warning(f"Error reading log file: {e}")
            return []

        # Filter by backend if specified
        if backend:
            entries = [e for e in entries if e.get("backend") == backend]

        # Sort by timestamp descending (newest first)
        entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return entries

    def get_logs_since(
        self,
        since_timestamp: str | None = None,
        backend: str | None = None,
    ) -> list[dict]:
        """Get log entries since a given timestamp.

        Args:
            since_timestamp: ISO 8601 timestamp. If None, returns all logs.
            backend: Optional filter by backend ("tmux" or "wezterm").

        Returns:
            List of log entry dicts newer than the timestamp, newest first.
        """
        all_logs = self.read_logs(backend=backend)

        if since_timestamp is None:
            return all_logs

        return [entry for entry in all_logs if entry.get("timestamp", "") > since_timestamp]

    def search_logs(
        self,
        query: str,
        logs: list[dict] | None = None,
        session_id: str | None = None,
        backend: str | None = None,
    ) -> list[dict]:
        """Search log entries by query string and/or session_id.

        Searches in: session_id, tmux_session_name, event_type, payload,
        correlation_id, direction, backend.

        Args:
            query: Search query (case-insensitive). Empty string matches all.
            logs: Optional list of logs to search. If None, reads all logs.
            session_id: Optional filter by session_id.
            backend: Optional filter by backend ("tmux" or "wezterm").

        Returns:
            List of matching log entry dicts, newest first.
        """
        if logs is None:
            logs = self.read_logs(backend=backend)
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

    def get_stats(self, backend: str | None = None) -> TerminalLogStats:
        """Get aggregate statistics from the terminal logs.

        Args:
            backend: Optional filter by backend ("tmux" or "wezterm").

        Returns:
            TerminalLogStats with totals for entries, operations, sessions.
        """
        logs = self.read_logs(backend=backend)

        sessions: set[str] = set()
        stats = TerminalLogStats()

        for entry in logs:
            stats.total_entries += 1
            direction = entry.get("direction", "")
            if direction == "out":
                stats.send_count += 1
            elif direction == "in":
                stats.capture_count += 1

            if entry.get("success", True):
                stats.success_count += 1
            else:
                stats.failure_count += 1

            session_id = entry.get("session_id")
            if session_id:
                sessions.add(session_id)

        stats.unique_sessions = len(sessions)
        return stats

    def clear_logs(self) -> bool:
        """Clear all terminal log entries by truncating the log file.

        Returns:
            True if successful, False otherwise.
        """
        self.ensure_log_directory()
        try:
            # Truncate the terminal log file
            with open(self.log_file, "w", encoding="utf-8"):
                pass  # Just open in write mode to truncate
            return True
        except OSError as e:
            logger.error(f"Error clearing logs: {e}")
            return False

    def get_turn_pairs(
        self,
        logs: list[dict] | None = None,
        session_id: str | None = None,
    ) -> list[TurnPair]:
        """Retrieve matched turn_start/turn_complete pairs from logs.

        Turn pairs are linked by their correlation_id (which equals turn_id).
        Each pair represents a complete user command -> Claude response cycle.

        Args:
            logs: Optional list of logs to search. If None, reads all logs.
            session_id: Optional filter by session_id.

        Returns:
            List of TurnPair objects, newest first.
        """
        if logs is None:
            logs = self.read_logs()

        # Filter by session_id if provided
        if session_id:
            logs = [entry for entry in logs if entry.get("session_id") == session_id]

        # Filter to turn events only
        turn_logs = [
            entry for entry in logs if entry.get("event_type") in ("turn_start", "turn_complete")
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
                    payload = json.loads(pair["start"].get("payload", "{}") or "{}")
                    command = payload.get("command")
                except (json.JSONDecodeError, TypeError):
                    pass

            if not command and pair["complete"]:
                try:
                    payload = json.loads(pair["complete"].get("payload", "{}") or "{}")
                    command = payload.get("command")
                except (json.JSONDecodeError, TypeError):
                    pass

            # Extract duration and response_summary from complete
            duration_seconds = None
            response_summary = None
            if pair["complete"]:
                try:
                    payload = json.loads(pair["complete"].get("payload", "{}") or "{}")
                    duration_seconds = payload.get("duration_seconds")
                    response_summary = payload.get("response_summary")
                except (json.JSONDecodeError, TypeError):
                    pass

            result.append(
                TurnPair(
                    turn_id=turn_id,
                    start=pair["start"],
                    complete=pair["complete"],
                    command=command,
                    duration_seconds=duration_seconds,
                    response_summary=response_summary,
                )
            )

        # Sort by timestamp of complete (or start if no complete), newest first
        def get_timestamp(pair: TurnPair) -> str:
            if pair.complete:
                return pair.complete.get("timestamp", "")
            if pair.start:
                return pair.start.get("timestamp", "")
            return ""

        result.sort(key=get_timestamp, reverse=True)
        return result


# Module-level singleton
_terminal_logging_service: TerminalLoggingService | None = None


def get_terminal_logging_service() -> TerminalLoggingService:
    """Get the global terminal logging service instance.

    Returns:
        TerminalLoggingService singleton.
    """
    global _terminal_logging_service
    if _terminal_logging_service is None:
        _terminal_logging_service = TerminalLoggingService()
    return _terminal_logging_service


def reset_terminal_logging_service() -> None:
    """Reset the global terminal logging service (for testing)."""
    global _terminal_logging_service
    _terminal_logging_service = None


# Backward-compatible module-level functions
def get_debug_logging() -> bool:
    """Get debug logging state."""
    return get_terminal_logging_service().debug_enabled


def set_debug_logging(enabled: bool) -> None:
    """Set debug logging state."""
    get_terminal_logging_service().debug_enabled = enabled


def read_terminal_logs(backend: str | None = None) -> list[dict]:
    """Read all terminal log entries from the log file."""
    return get_terminal_logging_service().read_logs(backend=backend)


def get_terminal_logs_since(
    since_timestamp: str | None = None,
    backend: str | None = None,
) -> list[dict]:
    """Get log entries since a given timestamp."""
    return get_terminal_logging_service().get_logs_since(since_timestamp, backend)


def search_terminal_logs(
    query: str,
    logs: list[dict] | None = None,
    session_id: str | None = None,
    backend: str | None = None,
) -> list[dict]:
    """Search log entries by query string and/or session_id."""
    return get_terminal_logging_service().search_logs(query, logs, session_id, backend)


def get_terminal_log_stats(backend: str | None = None) -> dict:
    """Get aggregate statistics from the terminal logs."""
    return get_terminal_logging_service().get_stats(backend).model_dump()


def clear_terminal_logs() -> bool:
    """Clear all terminal log entries."""
    return get_terminal_logging_service().clear_logs()


def create_terminal_log_entry(
    session_id: str,
    tmux_session_name: str,
    direction: str,
    event_type: str,
    payload: str | None = None,
    correlation_id: str | None = None,
    success: bool = True,
    debug_enabled: bool = False,
    backend: str = "tmux",
) -> TerminalLogEntry:
    """Create a new terminal log entry with auto-generated ID and timestamp.

    Args:
        session_id: Session identifier (project name).
        tmux_session_name: The session name.
        direction: "in" or "out".
        event_type: Type of operation.
        payload: Message content (only logged if debug_enabled).
        correlation_id: Links related operations.
        success: Whether operation succeeded.
        debug_enabled: If False, payload is not recorded.
        backend: Terminal backend identifier ("tmux" or "wezterm").

    Returns:
        TerminalLogEntry instance.
    """
    service = get_terminal_logging_service()
    # Temporarily set debug state for this call
    original_debug = service.debug_enabled
    service.debug_enabled = debug_enabled
    try:
        return service.create_log_entry(
            session_id=session_id,
            tmux_session_name=tmux_session_name,
            direction=direction,
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
            success=success,
            backend=backend,
        )
    finally:
        service.debug_enabled = original_debug


def write_terminal_log_entry(entry: TerminalLogEntry) -> bool:
    """Write a log entry to the terminal log file."""
    return get_terminal_logging_service().write_log_entry(entry)


def get_turn_pairs(
    logs: list[dict] | None = None,
    session_id: str | None = None,
) -> list[dict]:
    """Retrieve matched turn_start/turn_complete pairs from logs.

    Returns list of dicts for backward compatibility.
    """
    pairs = get_terminal_logging_service().get_turn_pairs(logs, session_id)
    return [p.model_dump() for p in pairs]
