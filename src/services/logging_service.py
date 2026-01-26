"""OpenRouter API call logging service for Claude Headspace.

Provides functionality for reading, writing, and searching OpenRouter API call logs.
Migrated from lib/logging.py to use Pydantic models and service pattern.
"""

import json
import logging
from pathlib import Path

from src.models.log_entry import OpenRouterLogEntry, OpenRouterLogStats

logger = logging.getLogger(__name__)

# Log file path
LOG_DIR = Path(__file__).parent.parent.parent / "data" / "logs"
OPENROUTER_LOG_FILE = LOG_DIR / "openrouter.jsonl"


class LoggingService:
    """Service for managing OpenRouter API call logs.

    Handles:
    - Reading JSONL log entries
    - Writing new log entries with rotation
    - Filtering and searching logs
    - Computing aggregate statistics
    """

    def __init__(
        self,
        log_dir: Path | None = None,
        max_log_size_mb: int = 10,
        max_log_files: int = 5,
    ):
        """Initialize the logging service.

        Args:
            log_dir: Directory for log files. Defaults to data/logs.
            max_log_size_mb: Rotate when file exceeds this size.
            max_log_files: Number of rotated files to keep.
        """
        self.log_dir = log_dir or LOG_DIR
        self.log_file = self.log_dir / "openrouter.jsonl"
        self.max_log_size_mb = max_log_size_mb
        self.max_log_files = max_log_files

    def ensure_log_directory(self) -> None:
        """Ensure the log directory exists."""
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def read_logs(self) -> list[dict]:
        """Read all OpenRouter API call logs from the log file.

        Returns:
            List of log entry dicts, newest first.
        """
        if not self.log_file.exists():
            return []

        entries = []
        try:
            with open(self.log_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            entries.append(entry)
                        except json.JSONDecodeError:
                            # Skip malformed lines
                            continue
        except OSError as e:
            logger.warning(f"Error reading log file: {e}")
            return []

        # Sort by timestamp descending (newest first)
        entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return entries

    def get_logs_since(self, since_timestamp: str | None = None) -> list[dict]:
        """Get log entries since a given timestamp.

        Args:
            since_timestamp: ISO 8601 timestamp. If None, returns all logs.

        Returns:
            List of log entry dicts newer than the timestamp, newest first.
        """
        all_logs = self.read_logs()

        if since_timestamp is None:
            return all_logs

        return [entry for entry in all_logs if entry.get("timestamp", "") > since_timestamp]

    def search_logs(
        self,
        query: str,
        logs: list[dict] | None = None,
    ) -> list[dict]:
        """Search log entries by query string.

        Searches in: model, response_content, error, caller, and request_messages.

        Args:
            query: Search query (case-insensitive).
            logs: Optional list of logs to search. If None, reads all logs.

        Returns:
            List of matching log entry dicts, newest first.
        """
        if logs is None:
            logs = self.read_logs()

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

    def write_log_entry(self, entry: OpenRouterLogEntry) -> bool:
        """Write a log entry to the log file.

        Automatically rotates the log file if it exceeds max size.

        Args:
            entry: OpenRouterLogEntry instance.

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

    def get_stats(self) -> OpenRouterLogStats:
        """Get aggregate statistics from the logs.

        Returns:
            OpenRouterLogStats with totals for calls, tokens, cost.
        """
        logs = self.read_logs()

        stats = OpenRouterLogStats()

        for entry in logs:
            stats.total_calls += 1
            if entry.get("success"):
                stats.successful_calls += 1
            else:
                stats.failed_calls += 1
            stats.total_cost += entry.get("cost", 0) or 0
            stats.total_input_tokens += entry.get("input_tokens", 0) or 0
            stats.total_output_tokens += entry.get("output_tokens", 0) or 0

        return stats


# Module-level functions for backward compatibility
_logging_service: LoggingService | None = None


def get_logging_service() -> LoggingService:
    """Get the global logging service instance.

    Returns:
        LoggingService singleton.
    """
    global _logging_service
    if _logging_service is None:
        _logging_service = LoggingService()
    return _logging_service


def reset_logging_service() -> None:
    """Reset the global logging service (for testing)."""
    global _logging_service
    _logging_service = None


# Backward-compatible module-level functions
def read_openrouter_logs() -> list[dict]:
    """Read all OpenRouter API call logs."""
    return get_logging_service().read_logs()


def get_logs_since(since_timestamp: str | None = None) -> list[dict]:
    """Get log entries since a given timestamp."""
    return get_logging_service().get_logs_since(since_timestamp)


def search_logs(query: str, logs: list[dict] | None = None) -> list[dict]:
    """Search log entries by query string."""
    return get_logging_service().search_logs(query, logs)


def get_log_stats() -> dict:
    """Get aggregate statistics from the logs."""
    return get_logging_service().get_stats().model_dump()


def write_log_entry(entry: OpenRouterLogEntry) -> bool:
    """Write a log entry to the log file."""
    return get_logging_service().write_log_entry(entry)


def create_log_entry(
    model: str,
    request_messages: list,
    response_content: str | None,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    success: bool,
    error: str | None = None,
    caller: str | None = None,
) -> OpenRouterLogEntry:
    """Create a new log entry with auto-generated ID and timestamp.

    Args:
        model: Model identifier.
        request_messages: List of message dicts sent to API.
        response_content: Response text (None if failed).
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cost: Cost in USD.
        success: Whether call succeeded.
        error: Error message if failed.
        caller: What triggered the call.

    Returns:
        OpenRouterLogEntry instance.
    """
    return OpenRouterLogEntry(
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
