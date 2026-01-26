"""Tests for the terminal logging service."""

import json
import tempfile
from pathlib import Path

import pytest

from src.models.log_entry import TerminalLogEntry
from src.services.terminal_logging_service import (
    TerminalLoggingService,
    get_debug_logging,
    get_terminal_logging_service,
    reset_terminal_logging_service,
    set_debug_logging,
)


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def terminal_service(temp_log_dir):
    """Create a terminal logging service with temporary directory."""
    return TerminalLoggingService(log_dir=temp_log_dir, debug_enabled=True)


class TestTerminalLoggingServiceInit:
    """Tests for TerminalLoggingService initialization."""

    def test_creates_with_defaults(self, temp_log_dir):
        """TerminalLoggingService initializes with default values."""
        service = TerminalLoggingService(log_dir=temp_log_dir)
        assert service.max_log_size_mb == 10
        assert service.max_log_files == 5
        assert service.max_payload_size == 10 * 1024
        assert service.debug_enabled is False

    def test_creates_with_custom_values(self, temp_log_dir):
        """TerminalLoggingService accepts custom configuration."""
        service = TerminalLoggingService(
            log_dir=temp_log_dir,
            max_log_size_mb=5,
            max_log_files=3,
            max_payload_size=5 * 1024,
            debug_enabled=True,
        )
        assert service.max_log_size_mb == 5
        assert service.max_log_files == 3
        assert service.max_payload_size == 5 * 1024
        assert service.debug_enabled is True


class TestDebugLoggingState:
    """Tests for debug logging state."""

    def test_get_debug_enabled(self, terminal_service):
        """debug_enabled property returns current state."""
        assert terminal_service.debug_enabled is True

    def test_set_debug_enabled(self, terminal_service):
        """debug_enabled property can be set."""
        terminal_service.debug_enabled = False
        assert terminal_service.debug_enabled is False


class TestTruncatePayload:
    """Tests for payload truncation."""

    def test_truncate_payload_none(self, terminal_service):
        """truncate_payload handles None payload."""
        result, truncated, size = terminal_service.truncate_payload(None)
        assert result is None
        assert truncated is False
        assert size == 0

    def test_truncate_payload_small(self, terminal_service):
        """truncate_payload returns small payloads unchanged."""
        payload = "Hello, world!"
        result, truncated, size = terminal_service.truncate_payload(payload)
        assert result == payload
        assert truncated is False
        assert size == len(payload.encode("utf-8"))

    def test_truncate_payload_large(self, temp_log_dir):
        """truncate_payload truncates large payloads."""
        service = TerminalLoggingService(
            log_dir=temp_log_dir,
            max_payload_size=100,
        )
        payload = "x" * 200
        result, truncated, size = service.truncate_payload(payload)
        assert truncated is True
        assert size == 200
        assert "[TRUNCATED]" in result
        assert len(result.encode("utf-8")) < 200


class TestCreateLogEntry:
    """Tests for creating log entries."""

    def test_create_log_entry_basic(self, terminal_service):
        """create_log_entry creates entry with required fields."""
        entry = terminal_service.create_log_entry(
            session_id="project1",
            tmux_session_name="claude-project1",
            direction="out",
            event_type="send_keys",
        )
        assert entry.session_id == "project1"
        assert entry.tmux_session_name == "claude-project1"
        assert entry.direction == "out"
        assert entry.event_type == "send_keys"
        assert entry.id is not None
        assert entry.timestamp is not None

    def test_create_log_entry_with_payload_debug_on(self, terminal_service):
        """create_log_entry includes payload when debug is on."""
        entry = terminal_service.create_log_entry(
            session_id="project1",
            tmux_session_name="claude-project1",
            direction="out",
            event_type="send_keys",
            payload="test message",
        )
        assert entry.payload == "test message"

    def test_create_log_entry_with_payload_debug_off(self, temp_log_dir):
        """create_log_entry excludes payload when debug is off."""
        service = TerminalLoggingService(
            log_dir=temp_log_dir,
            debug_enabled=False,
        )
        entry = service.create_log_entry(
            session_id="project1",
            tmux_session_name="claude-project1",
            direction="out",
            event_type="send_keys",
            payload="test message",
        )
        assert entry.payload is None

    def test_create_log_entry_with_backend(self, terminal_service):
        """create_log_entry sets backend field."""
        entry = terminal_service.create_log_entry(
            session_id="project1",
            tmux_session_name="claude-project1",
            direction="in",
            event_type="capture_pane",
            backend="wezterm",
        )
        assert entry.backend == "wezterm"


class TestWriteLogEntry:
    """Tests for writing log entries."""

    def test_write_log_entry_creates_file(self, terminal_service):
        """write_log_entry creates log file if it doesn't exist."""
        entry = TerminalLogEntry(
            session_id="project1",
            tmux_session_name="claude-project1",
            direction="out",
            event_type="send_keys",
        )

        result = terminal_service.write_log_entry(entry)
        assert result is True
        assert terminal_service.log_file.exists()

    def test_write_log_entry_appends(self, terminal_service):
        """write_log_entry appends to existing file."""
        entry1 = TerminalLogEntry(
            session_id="project1",
            tmux_session_name="claude-project1",
            direction="out",
            event_type="send_keys",
        )
        entry2 = TerminalLogEntry(
            session_id="project2",
            tmux_session_name="claude-project2",
            direction="in",
            event_type="capture_pane",
        )

        terminal_service.write_log_entry(entry1)
        terminal_service.write_log_entry(entry2)

        logs = terminal_service.read_logs()
        assert len(logs) == 2


class TestReadLogs:
    """Tests for reading log files."""

    def test_read_logs_empty_when_no_file(self, terminal_service):
        """read_logs returns empty list when log file doesn't exist."""
        logs = terminal_service.read_logs()
        assert logs == []

    def test_read_logs_returns_entries(self, terminal_service):
        """read_logs returns entries from log file."""
        log_file = terminal_service.log_file
        terminal_service.ensure_log_directory()

        entries = [
            {
                "id": "1",
                "timestamp": "2025-01-26T10:00:00Z",
                "session_id": "p1",
                "backend": "tmux",
            },
            {
                "id": "2",
                "timestamp": "2025-01-26T11:00:00Z",
                "session_id": "p2",
                "backend": "wezterm",
            },
        ]
        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        logs = terminal_service.read_logs()
        assert len(logs) == 2
        # Should be sorted newest first
        assert logs[0]["id"] == "2"

    def test_read_logs_filters_by_backend(self, terminal_service):
        """read_logs filters by backend."""
        log_file = terminal_service.log_file
        terminal_service.ensure_log_directory()

        entries = [
            {
                "id": "1",
                "timestamp": "2025-01-26T10:00:00Z",
                "session_id": "p1",
                "backend": "tmux",
            },
            {
                "id": "2",
                "timestamp": "2025-01-26T11:00:00Z",
                "session_id": "p2",
                "backend": "wezterm",
            },
        ]
        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        logs = terminal_service.read_logs(backend="wezterm")
        assert len(logs) == 1
        assert logs[0]["backend"] == "wezterm"

    def test_read_logs_adds_default_backend(self, terminal_service):
        """read_logs adds default backend for legacy entries."""
        log_file = terminal_service.log_file
        terminal_service.ensure_log_directory()

        # Entry without backend field (legacy)
        entry = {"id": "1", "timestamp": "2025-01-26T10:00:00Z", "session_id": "p1"}
        with open(log_file, "w") as f:
            f.write(json.dumps(entry) + "\n")

        logs = terminal_service.read_logs()
        assert len(logs) == 1
        assert logs[0]["backend"] == "tmux"


class TestSearchLogs:
    """Tests for searching logs."""

    def test_search_logs_returns_all_when_empty_query(self, terminal_service):
        """search_logs returns all logs when query is empty."""
        logs = [
            {"id": "1", "session_id": "project1", "event_type": "send_keys"},
            {"id": "2", "session_id": "project2", "event_type": "capture_pane"},
        ]
        result = terminal_service.search_logs("", logs)
        assert len(result) == 2

    def test_search_logs_filters_by_session_id(self, terminal_service):
        """search_logs filters by session_id."""
        logs = [
            {"id": "1", "session_id": "project1", "event_type": "send_keys"},
            {"id": "2", "session_id": "project2", "event_type": "send_keys"},
        ]
        result = terminal_service.search_logs("", logs, session_id="project1")
        assert len(result) == 1
        assert result[0]["session_id"] == "project1"

    def test_search_logs_filters_by_query(self, terminal_service):
        """search_logs filters by query string."""
        logs = [
            {"id": "1", "session_id": "project1", "event_type": "send_keys"},
            {"id": "2", "session_id": "project2", "event_type": "capture_pane"},
        ]
        result = terminal_service.search_logs("capture", logs)
        assert len(result) == 1
        assert result[0]["event_type"] == "capture_pane"

    def test_search_logs_searches_payload(self, terminal_service):
        """search_logs searches in payload content."""
        logs = [
            {"id": "1", "session_id": "p1", "payload": "Hello world"},
            {"id": "2", "session_id": "p2", "payload": "Goodbye"},
        ]
        result = terminal_service.search_logs("hello", logs)
        assert len(result) == 1


class TestGetStats:
    """Tests for aggregate statistics."""

    def test_get_stats_empty_logs(self, terminal_service):
        """get_stats returns zeros for empty logs."""
        stats = terminal_service.get_stats()
        assert stats.total_entries == 0
        assert stats.send_count == 0
        assert stats.capture_count == 0
        assert stats.unique_sessions == 0

    def test_get_stats_counts_correctly(self, terminal_service):
        """get_stats calculates correct statistics."""
        log_file = terminal_service.log_file
        terminal_service.ensure_log_directory()

        entries = [
            {
                "id": "1",
                "timestamp": "2025-01-26T10:00:00Z",
                "session_id": "p1",
                "direction": "out",
                "success": True,
            },
            {
                "id": "2",
                "timestamp": "2025-01-26T11:00:00Z",
                "session_id": "p1",
                "direction": "in",
                "success": True,
            },
            {
                "id": "3",
                "timestamp": "2025-01-26T12:00:00Z",
                "session_id": "p2",
                "direction": "out",
                "success": False,
            },
        ]
        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        stats = terminal_service.get_stats()
        assert stats.total_entries == 3
        assert stats.send_count == 2  # direction="out"
        assert stats.capture_count == 1  # direction="in"
        assert stats.success_count == 2
        assert stats.failure_count == 1
        assert stats.unique_sessions == 2


class TestClearLogs:
    """Tests for clearing logs."""

    def test_clear_logs_empties_file(self, terminal_service):
        """clear_logs empties the log file."""
        # Write some entries
        entry = TerminalLogEntry(
            session_id="project1",
            tmux_session_name="claude-project1",
            direction="out",
            event_type="send_keys",
        )
        terminal_service.write_log_entry(entry)

        # Clear
        result = terminal_service.clear_logs()
        assert result is True

        # Verify empty
        logs = terminal_service.read_logs()
        assert len(logs) == 0


class TestTurnPairs:
    """Tests for turn pair retrieval."""

    def test_get_turn_pairs_empty(self, terminal_service):
        """get_turn_pairs returns empty list when no turn events."""
        pairs = terminal_service.get_turn_pairs()
        assert pairs == []

    def test_get_turn_pairs_matches_by_correlation_id(self, terminal_service):
        """get_turn_pairs matches start/complete by correlation_id."""
        log_file = terminal_service.log_file
        terminal_service.ensure_log_directory()

        entries = [
            {
                "id": "1",
                "timestamp": "2025-01-26T10:00:00Z",
                "session_id": "p1",
                "event_type": "turn_start",
                "correlation_id": "turn-123",
                "payload": json.dumps({"command": "fix bug"}),
            },
            {
                "id": "2",
                "timestamp": "2025-01-26T10:05:00Z",
                "session_id": "p1",
                "event_type": "turn_complete",
                "correlation_id": "turn-123",
                "payload": json.dumps(
                    {
                        "command": "fix bug",
                        "duration_seconds": 300,
                        "response_summary": "Fixed the bug",
                    }
                ),
            },
        ]
        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        pairs = terminal_service.get_turn_pairs()
        assert len(pairs) == 1
        assert pairs[0].turn_id == "turn-123"
        assert pairs[0].command == "fix bug"
        assert pairs[0].duration_seconds == 300
        assert pairs[0].response_summary == "Fixed the bug"

    def test_get_turn_pairs_filters_by_session(self, terminal_service):
        """get_turn_pairs filters by session_id."""
        log_file = terminal_service.log_file
        terminal_service.ensure_log_directory()

        entries = [
            {
                "id": "1",
                "timestamp": "2025-01-26T10:00:00Z",
                "session_id": "p1",
                "event_type": "turn_start",
                "correlation_id": "turn-1",
            },
            {
                "id": "2",
                "timestamp": "2025-01-26T11:00:00Z",
                "session_id": "p2",
                "event_type": "turn_start",
                "correlation_id": "turn-2",
            },
        ]
        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        pairs = terminal_service.get_turn_pairs(session_id="p1")
        assert len(pairs) == 1
        assert pairs[0].turn_id == "turn-1"


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_terminal_logging_service_returns_singleton(self):
        """get_terminal_logging_service returns same instance."""
        reset_terminal_logging_service()
        service1 = get_terminal_logging_service()
        service2 = get_terminal_logging_service()
        assert service1 is service2

    def test_reset_terminal_logging_service_creates_new_instance(self):
        """reset_terminal_logging_service creates new instance."""
        service1 = get_terminal_logging_service()
        reset_terminal_logging_service()
        service2 = get_terminal_logging_service()
        assert service1 is not service2


class TestModuleLevelDebugFunctions:
    """Tests for module-level debug functions."""

    def test_set_and_get_debug_logging(self):
        """set_debug_logging and get_debug_logging work correctly."""
        reset_terminal_logging_service()

        set_debug_logging(True)
        assert get_debug_logging() is True

        set_debug_logging(False)
        assert get_debug_logging() is False
