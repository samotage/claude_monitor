"""Tests for the OpenRouter logging service."""

import json
import tempfile
from pathlib import Path

import pytest

from src.models.log_entry import OpenRouterLogEntry
from src.services.logging_service import (
    LoggingService,
    create_log_entry,
    get_logging_service,
    reset_logging_service,
)


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def logging_service(temp_log_dir):
    """Create a logging service with temporary directory."""
    return LoggingService(log_dir=temp_log_dir)


class TestLoggingServiceInit:
    """Tests for LoggingService initialization."""

    def test_creates_with_defaults(self, temp_log_dir):
        """LoggingService initializes with default values."""
        service = LoggingService(log_dir=temp_log_dir)
        assert service.max_log_size_mb == 10
        assert service.max_log_files == 5
        assert service.log_file == temp_log_dir / "openrouter.jsonl"

    def test_creates_with_custom_values(self, temp_log_dir):
        """LoggingService accepts custom configuration."""
        service = LoggingService(
            log_dir=temp_log_dir,
            max_log_size_mb=5,
            max_log_files=3,
        )
        assert service.max_log_size_mb == 5
        assert service.max_log_files == 3


class TestReadLogs:
    """Tests for reading log files."""

    def test_read_logs_empty_when_no_file(self, logging_service):
        """read_logs returns empty list when log file doesn't exist."""
        logs = logging_service.read_logs()
        assert logs == []

    def test_read_logs_returns_entries(self, logging_service):
        """read_logs returns entries from log file."""
        # Write some test entries
        log_file = logging_service.log_file
        logging_service.ensure_log_directory()

        entries = [
            {"id": "1", "timestamp": "2025-01-26T10:00:00Z", "model": "test"},
            {"id": "2", "timestamp": "2025-01-26T11:00:00Z", "model": "test"},
        ]
        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        logs = logging_service.read_logs()
        assert len(logs) == 2
        # Should be sorted newest first
        assert logs[0]["id"] == "2"
        assert logs[1]["id"] == "1"

    def test_read_logs_skips_malformed_lines(self, logging_service):
        """read_logs skips malformed JSON lines."""
        log_file = logging_service.log_file
        logging_service.ensure_log_directory()

        with open(log_file, "w") as f:
            f.write('{"id": "1", "timestamp": "2025-01-26T10:00:00Z"}\n')
            f.write("not valid json\n")
            f.write('{"id": "2", "timestamp": "2025-01-26T11:00:00Z"}\n')

        logs = logging_service.read_logs()
        assert len(logs) == 2


class TestGetLogsSince:
    """Tests for filtering logs by timestamp."""

    def test_get_logs_since_returns_all_when_no_timestamp(self, logging_service):
        """get_logs_since returns all logs when no timestamp provided."""
        log_file = logging_service.log_file
        logging_service.ensure_log_directory()

        entries = [
            {"id": "1", "timestamp": "2025-01-26T10:00:00Z"},
            {"id": "2", "timestamp": "2025-01-26T11:00:00Z"},
        ]
        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        logs = logging_service.get_logs_since(None)
        assert len(logs) == 2

    def test_get_logs_since_filters_by_timestamp(self, logging_service):
        """get_logs_since returns only logs after timestamp."""
        log_file = logging_service.log_file
        logging_service.ensure_log_directory()

        entries = [
            {"id": "1", "timestamp": "2025-01-26T10:00:00Z"},
            {"id": "2", "timestamp": "2025-01-26T11:00:00Z"},
            {"id": "3", "timestamp": "2025-01-26T12:00:00Z"},
        ]
        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        logs = logging_service.get_logs_since("2025-01-26T10:30:00Z")
        assert len(logs) == 2
        assert all(log["timestamp"] > "2025-01-26T10:30:00Z" for log in logs)


class TestSearchLogs:
    """Tests for searching logs."""

    def test_search_logs_returns_all_when_empty_query(self, logging_service):
        """search_logs returns all logs when query is empty."""
        logs = [
            {"id": "1", "model": "claude-3-haiku"},
            {"id": "2", "model": "claude-3-sonnet"},
        ]
        result = logging_service.search_logs("", logs)
        assert len(result) == 2

    def test_search_logs_filters_by_model(self, logging_service):
        """search_logs filters by model name."""
        logs = [
            {"id": "1", "model": "claude-3-haiku"},
            {"id": "2", "model": "claude-3-sonnet"},
        ]
        result = logging_service.search_logs("haiku", logs)
        assert len(result) == 1
        assert result[0]["model"] == "claude-3-haiku"

    def test_search_logs_is_case_insensitive(self, logging_service):
        """search_logs is case insensitive."""
        logs = [
            {"id": "1", "model": "CLAUDE-3-HAIKU"},
        ]
        result = logging_service.search_logs("haiku", logs)
        assert len(result) == 1

    def test_search_logs_searches_response_content(self, logging_service):
        """search_logs searches in response content."""
        logs = [
            {"id": "1", "model": "test", "response_content": "Hello world"},
            {"id": "2", "model": "test", "response_content": "Goodbye"},
        ]
        result = logging_service.search_logs("hello", logs)
        assert len(result) == 1

    def test_search_logs_searches_error(self, logging_service):
        """search_logs searches in error field."""
        logs = [
            {"id": "1", "model": "test", "error": "Rate limit exceeded"},
            {"id": "2", "model": "test", "error": None},
        ]
        result = logging_service.search_logs("rate limit", logs)
        assert len(result) == 1

    def test_search_logs_searches_request_messages(self, logging_service):
        """search_logs searches in request messages."""
        logs = [
            {
                "id": "1",
                "model": "test",
                "request_messages": [{"content": "What is Python?"}],
            },
            {"id": "2", "model": "test", "request_messages": [{"content": "Hello"}]},
        ]
        result = logging_service.search_logs("python", logs)
        assert len(result) == 1


class TestWriteLogEntry:
    """Tests for writing log entries."""

    def test_write_log_entry_creates_file(self, logging_service):
        """write_log_entry creates log file if it doesn't exist."""
        entry = OpenRouterLogEntry(
            model="test",
            request_messages=[],
            response_content="test",
            input_tokens=10,
            output_tokens=20,
            cost=0.01,
            success=True,
        )

        result = logging_service.write_log_entry(entry)
        assert result is True
        assert logging_service.log_file.exists()

    def test_write_log_entry_appends(self, logging_service):
        """write_log_entry appends to existing file."""
        entry1 = OpenRouterLogEntry(
            model="test1",
            request_messages=[],
            response_content="test1",
            input_tokens=10,
            output_tokens=20,
            cost=0.01,
            success=True,
        )
        entry2 = OpenRouterLogEntry(
            model="test2",
            request_messages=[],
            response_content="test2",
            input_tokens=10,
            output_tokens=20,
            cost=0.01,
            success=True,
        )

        logging_service.write_log_entry(entry1)
        logging_service.write_log_entry(entry2)

        logs = logging_service.read_logs()
        assert len(logs) == 2


class TestGetStats:
    """Tests for aggregate statistics."""

    def test_get_stats_empty_logs(self, logging_service):
        """get_stats returns zeros for empty logs."""
        stats = logging_service.get_stats()
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0
        assert stats.total_cost == 0.0

    def test_get_stats_counts_correctly(self, logging_service):
        """get_stats calculates correct statistics."""
        log_file = logging_service.log_file
        logging_service.ensure_log_directory()

        entries = [
            {
                "id": "1",
                "timestamp": "2025-01-26T10:00:00Z",
                "success": True,
                "cost": 0.01,
                "input_tokens": 100,
                "output_tokens": 50,
            },
            {
                "id": "2",
                "timestamp": "2025-01-26T11:00:00Z",
                "success": True,
                "cost": 0.02,
                "input_tokens": 200,
                "output_tokens": 100,
            },
            {
                "id": "3",
                "timestamp": "2025-01-26T12:00:00Z",
                "success": False,
                "cost": 0,
                "input_tokens": 50,
                "output_tokens": 0,
            },
        ]
        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        stats = logging_service.get_stats()
        assert stats.total_calls == 3
        assert stats.successful_calls == 2
        assert stats.failed_calls == 1
        assert stats.total_cost == 0.03
        assert stats.total_input_tokens == 350
        assert stats.total_output_tokens == 150


class TestCreateLogEntry:
    """Tests for create_log_entry helper."""

    def test_create_log_entry_generates_id(self):
        """create_log_entry generates unique ID."""
        entry = create_log_entry(
            model="test",
            request_messages=[],
            response_content="test",
            input_tokens=10,
            output_tokens=20,
            cost=0.01,
            success=True,
        )
        assert entry.id is not None
        assert len(entry.id) > 0

    def test_create_log_entry_generates_timestamp(self):
        """create_log_entry generates timestamp."""
        entry = create_log_entry(
            model="test",
            request_messages=[],
            response_content="test",
            input_tokens=10,
            output_tokens=20,
            cost=0.01,
            success=True,
        )
        assert entry.timestamp is not None
        assert "T" in entry.timestamp  # ISO format

    def test_create_log_entry_with_error(self):
        """create_log_entry handles error field."""
        entry = create_log_entry(
            model="test",
            request_messages=[],
            response_content=None,
            input_tokens=10,
            output_tokens=0,
            cost=0.0,
            success=False,
            error="Rate limit exceeded",
        )
        assert entry.success is False
        assert entry.error == "Rate limit exceeded"


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_logging_service_returns_singleton(self):
        """get_logging_service returns same instance."""
        reset_logging_service()
        service1 = get_logging_service()
        service2 = get_logging_service()
        assert service1 is service2

    def test_reset_logging_service_creates_new_instance(self):
        """reset_logging_service creates new instance."""
        service1 = get_logging_service()
        reset_logging_service()
        service2 = get_logging_service()
        assert service1 is not service2
