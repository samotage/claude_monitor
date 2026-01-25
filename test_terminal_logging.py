"""Tests for terminal session message logging functionality."""

import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from lib.terminal_logging import (
    TerminalLogEntry,
    truncate_payload,
    write_terminal_log_entry,
    create_terminal_log_entry,
    read_terminal_logs,
    get_terminal_logs_since,
    search_terminal_logs,
    get_terminal_log_stats,
    clear_terminal_logs,
    MAX_PAYLOAD_SIZE,
    TERMINAL_LOG_FILE,
)


# =============================================================================
# TerminalLogEntry Dataclass Tests
# =============================================================================


class TestTerminalLogEntry:
    """Tests for TerminalLogEntry dataclass."""

    def test_create_entry_all_fields(self):
        """Creates entry with all fields."""
        entry = TerminalLogEntry(
            id="test-id-123",
            timestamp="2026-01-24T10:00:00+00:00",
            session_id="my-project",
            tmux_session_name="claude-my-project",
            direction="out",
            event_type="send_keys",
            payload="Hello, world!",
            correlation_id="corr-123",
            truncated=False,
            original_size=None,
            success=True,
            backend="tmux",
        )

        assert entry.id == "test-id-123"
        assert entry.session_id == "my-project"
        assert entry.direction == "out"
        assert entry.event_type == "send_keys"
        assert entry.payload == "Hello, world!"
        assert entry.correlation_id == "corr-123"
        assert entry.truncated is False
        assert entry.success is True
        assert entry.backend == "tmux"

    def test_create_entry_minimal(self):
        """Creates entry with minimal required fields."""
        entry = TerminalLogEntry(
            id="test-id",
            timestamp="2026-01-24T10:00:00+00:00",
            session_id="project",
            tmux_session_name="claude-project",
            direction="in",
            event_type="capture_pane",
        )

        assert entry.payload is None
        assert entry.correlation_id is None
        assert entry.truncated is False
        assert entry.original_size is None
        assert entry.success is True
        assert entry.backend == "tmux"  # Default value

    def test_create_entry_wezterm_backend(self):
        """Creates entry with wezterm backend."""
        entry = TerminalLogEntry(
            id="test-id",
            timestamp="2026-01-24T10:00:00+00:00",
            session_id="project",
            tmux_session_name="claude-project",
            direction="in",
            event_type="capture_pane",
            backend="wezterm",
        )

        assert entry.backend == "wezterm"


# =============================================================================
# Payload Truncation Tests
# =============================================================================


class TestTruncatePayload:
    """Tests for payload truncation logic."""

    def test_no_truncation_needed(self):
        """Small payload is not truncated."""
        payload = "Hello, world!"
        result, was_truncated, original_size = truncate_payload(payload)

        assert result == "Hello, world!"
        assert was_truncated is False
        assert original_size == len(payload.encode('utf-8'))

    def test_truncate_large_payload(self):
        """Large payload is truncated to MAX_PAYLOAD_SIZE."""
        # Create a payload larger than MAX_PAYLOAD_SIZE
        payload = "x" * (MAX_PAYLOAD_SIZE + 1000)
        result, was_truncated, original_size = truncate_payload(payload)

        assert was_truncated is True
        assert original_size == len(payload.encode('utf-8'))
        assert len(result.encode('utf-8')) <= MAX_PAYLOAD_SIZE + 20  # Allow for truncation marker
        assert "[TRUNCATED]" in result

    def test_truncate_exactly_at_limit(self):
        """Payload exactly at limit is not truncated."""
        payload = "x" * MAX_PAYLOAD_SIZE
        result, was_truncated, original_size = truncate_payload(payload)

        assert was_truncated is False
        assert result == payload

    def test_truncate_none_payload(self):
        """None payload returns None."""
        result, was_truncated, original_size = truncate_payload(None)

        assert result is None
        assert was_truncated is False
        assert original_size == 0

    def test_truncate_multibyte_chars(self):
        """Handles multi-byte characters correctly."""
        # Unicode string with multi-byte characters (emoji is 4 bytes each)
        # Need enough to exceed MAX_PAYLOAD_SIZE (10KB = 10240 bytes)
        emoji = "\U0001F600"  # Grinning face emoji (4 bytes in UTF-8)
        payload = emoji * ((MAX_PAYLOAD_SIZE // 4) + 1000)
        result, was_truncated, original_size = truncate_payload(payload)

        # Should truncate without crashing on multi-byte boundary
        assert was_truncated is True
        assert "[TRUNCATED]" in result


# =============================================================================
# Log Entry Creation Tests
# =============================================================================


class TestCreateTerminalLogEntry:
    """Tests for creating terminal log entries."""

    def test_create_entry_debug_enabled(self):
        """Creates entry with payload when debug enabled."""
        entry = create_terminal_log_entry(
            session_id="my-project",
            tmux_session_name="claude-my-project",
            direction="out",
            event_type="send_keys",
            payload="Hello, world!",
            correlation_id="corr-123",
            success=True,
            debug_enabled=True,
        )

        assert entry.session_id == "my-project"
        assert entry.payload == "Hello, world!"
        assert entry.correlation_id == "corr-123"
        assert entry.id is not None
        assert entry.timestamp is not None
        assert entry.backend == "tmux"  # Default

    def test_create_entry_debug_disabled(self):
        """Creates entry without payload when debug disabled."""
        entry = create_terminal_log_entry(
            session_id="my-project",
            tmux_session_name="claude-my-project",
            direction="out",
            event_type="send_keys",
            payload="Hello, world!",
            debug_enabled=False,
        )

        assert entry.payload is None
        assert entry.truncated is False

    def test_create_entry_truncates_large_payload(self):
        """Truncates large payload and sets truncated flag."""
        large_payload = "x" * (MAX_PAYLOAD_SIZE + 5000)
        entry = create_terminal_log_entry(
            session_id="my-project",
            tmux_session_name="claude-my-project",
            direction="in",
            event_type="capture_pane",
            payload=large_payload,
            debug_enabled=True,
        )

        assert entry.truncated is True
        assert entry.original_size == len(large_payload.encode('utf-8'))
        assert "[TRUNCATED]" in entry.payload

    def test_create_entry_with_backend(self):
        """Creates entry with specified backend."""
        entry = create_terminal_log_entry(
            session_id="my-project",
            tmux_session_name="claude-my-project",
            direction="out",
            event_type="send_keys",
            debug_enabled=False,
            backend="wezterm",
        )

        assert entry.backend == "wezterm"


# =============================================================================
# Log File Read/Write Tests
# =============================================================================


class TestWriteAndReadLogs:
    """Tests for writing and reading log entries."""

    def test_write_and_read_entry(self, tmp_path, monkeypatch):
        """Writes entry and reads it back."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        entry = TerminalLogEntry(
            id="test-id-123",
            timestamp="2026-01-24T10:00:00+00:00",
            session_id="my-project",
            tmux_session_name="claude-my-project",
            direction="out",
            event_type="send_keys",
            payload="Hello!",
            success=True,
        )

        # Write
        result = write_terminal_log_entry(entry)
        assert result is True
        assert log_file.exists()

        # Read
        logs = read_terminal_logs()
        assert len(logs) == 1
        assert logs[0]["id"] == "test-id-123"
        assert logs[0]["payload"] == "Hello!"
        assert logs[0]["backend"] == "tmux"  # Default applied

    def test_read_empty_file(self, tmp_path, monkeypatch):
        """Returns empty list when log file doesn't exist."""
        log_file = tmp_path / "nonexistent.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LEGACY_LOG_FILE", str(tmp_path / "legacy.jsonl"))

        logs = read_terminal_logs()
        assert logs == []

    def test_read_multiple_entries_sorted(self, tmp_path, monkeypatch):
        """Reads multiple entries sorted by timestamp descending."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        # Write entries with different timestamps
        entry1 = TerminalLogEntry(
            id="1", timestamp="2026-01-24T09:00:00+00:00",
            session_id="p", tmux_session_name="claude-p",
            direction="out", event_type="send_keys"
        )
        entry2 = TerminalLogEntry(
            id="2", timestamp="2026-01-24T11:00:00+00:00",
            session_id="p", tmux_session_name="claude-p",
            direction="out", event_type="send_keys"
        )
        entry3 = TerminalLogEntry(
            id="3", timestamp="2026-01-24T10:00:00+00:00",
            session_id="p", tmux_session_name="claude-p",
            direction="out", event_type="send_keys"
        )

        write_terminal_log_entry(entry1)
        write_terminal_log_entry(entry2)
        write_terminal_log_entry(entry3)

        logs = read_terminal_logs()
        assert len(logs) == 3
        # Should be sorted newest first
        assert logs[0]["id"] == "2"  # 11:00
        assert logs[1]["id"] == "3"  # 10:00
        assert logs[2]["id"] == "1"  # 09:00

    def test_read_with_backend_filter(self, tmp_path, monkeypatch):
        """Filters logs by backend."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        entry1 = TerminalLogEntry(
            id="1", timestamp="2026-01-24T09:00:00+00:00",
            session_id="p", tmux_session_name="claude-p",
            direction="out", event_type="send_keys",
            backend="tmux"
        )
        entry2 = TerminalLogEntry(
            id="2", timestamp="2026-01-24T10:00:00+00:00",
            session_id="p", tmux_session_name="claude-p",
            direction="out", event_type="send_keys",
            backend="wezterm"
        )

        write_terminal_log_entry(entry1)
        write_terminal_log_entry(entry2)

        # Filter by tmux
        tmux_logs = read_terminal_logs(backend="tmux")
        assert len(tmux_logs) == 1
        assert tmux_logs[0]["backend"] == "tmux"

        # Filter by wezterm
        wezterm_logs = read_terminal_logs(backend="wezterm")
        assert len(wezterm_logs) == 1
        assert wezterm_logs[0]["backend"] == "wezterm"

        # No filter - all logs
        all_logs = read_terminal_logs()
        assert len(all_logs) == 2


# =============================================================================
# Log Filtering Tests
# =============================================================================


class TestGetTerminalLogsSince:
    """Tests for filtering logs by timestamp."""

    def test_get_logs_since(self, tmp_path, monkeypatch):
        """Returns only logs after the given timestamp."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        entries = [
            TerminalLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys"),
            TerminalLogEntry(id="2", timestamp="2026-01-24T11:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys"),
            TerminalLogEntry(id="3", timestamp="2026-01-24T10:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys"),
        ]
        for e in entries:
            write_terminal_log_entry(e)

        logs = get_terminal_logs_since("2026-01-24T09:30:00+00:00")

        assert len(logs) == 2
        ids = [log["id"] for log in logs]
        assert "2" in ids
        assert "3" in ids
        assert "1" not in ids

    def test_get_logs_since_none(self, tmp_path, monkeypatch):
        """Returns all logs when since is None."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        entry = TerminalLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                            session_id="p", tmux_session_name="claude-p",
                            direction="out", event_type="send_keys")
        write_terminal_log_entry(entry)

        logs = get_terminal_logs_since(None)
        assert len(logs) == 1


class TestSearchTerminalLogs:
    """Tests for searching/filtering logs."""

    def test_search_by_session_id(self, tmp_path, monkeypatch):
        """Filters logs by session_id."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        entries = [
            TerminalLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                        session_id="project-a", tmux_session_name="claude-project-a",
                        direction="out", event_type="send_keys"),
            TerminalLogEntry(id="2", timestamp="2026-01-24T10:00:00+00:00",
                        session_id="project-b", tmux_session_name="claude-project-b",
                        direction="out", event_type="send_keys"),
        ]
        for e in entries:
            write_terminal_log_entry(e)

        logs = search_terminal_logs("", session_id="project-a")

        assert len(logs) == 1
        assert logs[0]["session_id"] == "project-a"

    def test_search_by_query(self, tmp_path, monkeypatch):
        """Searches logs by query string in fields."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        entries = [
            TerminalLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                        session_id="my-project", tmux_session_name="claude-my-project",
                        direction="out", event_type="send_keys",
                        payload="Hello world"),
            TerminalLogEntry(id="2", timestamp="2026-01-24T10:00:00+00:00",
                        session_id="other", tmux_session_name="claude-other",
                        direction="in", event_type="capture_pane",
                        payload="Goodbye world"),
        ]
        for e in entries:
            write_terminal_log_entry(e)

        logs = search_terminal_logs("Hello")

        assert len(logs) == 1
        assert logs[0]["id"] == "1"

    def test_search_empty_query(self, tmp_path, monkeypatch):
        """Empty query returns all logs."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        entry = TerminalLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                            session_id="p", tmux_session_name="claude-p",
                            direction="out", event_type="send_keys")
        write_terminal_log_entry(entry)

        logs = search_terminal_logs("")
        assert len(logs) == 1

    def test_search_by_backend(self, tmp_path, monkeypatch):
        """Searches logs filtered by backend."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        entries = [
            TerminalLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys",
                        backend="tmux"),
            TerminalLogEntry(id="2", timestamp="2026-01-24T10:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys",
                        backend="wezterm"),
        ]
        for e in entries:
            write_terminal_log_entry(e)

        logs = search_terminal_logs("", backend="wezterm")
        assert len(logs) == 1
        assert logs[0]["backend"] == "wezterm"


# =============================================================================
# Log Statistics Tests
# =============================================================================


class TestGetTerminalLogStats:
    """Tests for aggregate log statistics."""

    def test_stats_calculation(self, tmp_path, monkeypatch):
        """Calculates correct statistics."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        entries = [
            TerminalLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                        session_id="project-a", tmux_session_name="claude-project-a",
                        direction="out", event_type="send_keys", success=True),
            TerminalLogEntry(id="2", timestamp="2026-01-24T10:00:00+00:00",
                        session_id="project-a", tmux_session_name="claude-project-a",
                        direction="in", event_type="capture_pane", success=True),
            TerminalLogEntry(id="3", timestamp="2026-01-24T11:00:00+00:00",
                        session_id="project-b", tmux_session_name="claude-project-b",
                        direction="out", event_type="send_keys", success=False),
        ]
        for e in entries:
            write_terminal_log_entry(e)

        stats = get_terminal_log_stats()

        assert stats["total_entries"] == 3
        assert stats["send_count"] == 2
        assert stats["capture_count"] == 1
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 1
        assert stats["unique_sessions"] == 2

    def test_stats_empty_logs(self, tmp_path, monkeypatch):
        """Returns zero stats when no logs."""
        log_file = tmp_path / "nonexistent.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LEGACY_LOG_FILE", str(tmp_path / "legacy.jsonl"))

        stats = get_terminal_log_stats()

        assert stats["total_entries"] == 0
        assert stats["send_count"] == 0
        assert stats["capture_count"] == 0

    def test_stats_with_backend_filter(self, tmp_path, monkeypatch):
        """Calculates stats filtered by backend."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        entries = [
            TerminalLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys",
                        backend="tmux"),
            TerminalLogEntry(id="2", timestamp="2026-01-24T10:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys",
                        backend="wezterm"),
            TerminalLogEntry(id="3", timestamp="2026-01-24T11:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys",
                        backend="wezterm"),
        ]
        for e in entries:
            write_terminal_log_entry(e)

        tmux_stats = get_terminal_log_stats(backend="tmux")
        assert tmux_stats["total_entries"] == 1

        wezterm_stats = get_terminal_log_stats(backend="wezterm")
        assert wezterm_stats["total_entries"] == 2


# =============================================================================
# Clear Logs Tests
# =============================================================================


class TestClearTerminalLogs:
    """Tests for clearing terminal logs."""

    def test_clear_logs(self, tmp_path, monkeypatch):
        """Clears all log entries."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        # Write some entries
        entry = TerminalLogEntry(
            id="1", timestamp="2026-01-24T09:00:00+00:00",
            session_id="p", tmux_session_name="claude-p",
            direction="out", event_type="send_keys"
        )
        write_terminal_log_entry(entry)

        # Verify entry exists
        logs = read_terminal_logs()
        assert len(logs) == 1

        # Clear logs
        result = clear_terminal_logs()
        assert result is True

        # Verify logs are cleared
        logs = read_terminal_logs()
        assert len(logs) == 0

    def test_clear_logs_empty_file(self, tmp_path, monkeypatch):
        """Clearing empty file succeeds."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        result = clear_terminal_logs()
        assert result is True


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Tests for backward compatibility with legacy tmux.jsonl file."""

    def test_read_from_legacy_file(self, tmp_path, monkeypatch):
        """Reads from legacy tmux.jsonl if terminal.jsonl doesn't exist."""
        legacy_file = tmp_path / "tmux.jsonl"
        terminal_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(terminal_file))
        monkeypatch.setattr("lib.terminal_logging.LEGACY_LOG_FILE", str(legacy_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        # Write directly to legacy file (simulating old data)
        entry_data = {
            "id": "legacy-1",
            "timestamp": "2026-01-24T09:00:00+00:00",
            "session_id": "p",
            "tmux_session_name": "claude-p",
            "direction": "out",
            "event_type": "send_keys",
            "success": True,
        }
        with open(legacy_file, "w") as f:
            f.write(json.dumps(entry_data) + "\n")

        # Read should find the legacy file
        logs = read_terminal_logs()
        assert len(logs) == 1
        assert logs[0]["id"] == "legacy-1"
        assert logs[0]["backend"] == "tmux"  # Default applied

    def test_legacy_entries_get_default_backend(self, tmp_path, monkeypatch):
        """Legacy entries without backend field get 'tmux' as default."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        # Write entry without backend field (simulating legacy data)
        entry_data = {
            "id": "old-entry",
            "timestamp": "2026-01-24T09:00:00+00:00",
            "session_id": "p",
            "tmux_session_name": "claude-p",
            "direction": "out",
            "event_type": "send_keys",
            "success": True,
            # No "backend" field
        }
        with open(log_file, "w") as f:
            f.write(json.dumps(entry_data) + "\n")

        logs = read_terminal_logs()
        assert len(logs) == 1
        assert logs[0]["backend"] == "tmux"  # Default applied


# =============================================================================
# Integration Tests with lib/tmux.py
# =============================================================================


class TestTerminalLoggingIntegration:
    """Integration tests for terminal logging with send_keys/capture_pane."""

    def test_send_keys_logs_event(self, tmp_path, monkeypatch):
        """send_keys creates log entry."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        # Reset backend state
        import lib.backends.tmux as tmux_backend
        from lib.backends import reset_backend
        tmux_backend._tmux_available = None
        reset_backend()

        # Mock tmux functions at backends level
        with patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux"), \
             patch("lib.backends.tmux._run_tmux") as mock_run:
            # First call for session_exists, second for send-keys
            mock_run.side_effect = [(0, "", ""), (0, "", "")]

            from lib.tmux import send_keys, set_debug_logging
            set_debug_logging(True)

            # log_operation=True to enable logging for this test
            result = send_keys("claude-test", "Hello!", correlation_id="corr-123", log_operation=True)

            assert result is True

            logs = read_terminal_logs()
            assert len(logs) == 1
            assert logs[0]["direction"] == "out"
            assert logs[0]["event_type"] == "send_keys"
            assert logs[0]["payload"] == "Hello!"
            assert logs[0]["correlation_id"] == "corr-123"
            assert logs[0]["backend"] == "tmux"

    def test_capture_pane_logs_event(self, tmp_path, monkeypatch):
        """capture_pane creates log entry."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        captured_output = "Line 1\nLine 2\nLine 3"

        # Reset backend state
        import lib.backends.tmux as tmux_backend
        from lib.backends import reset_backend
        tmux_backend._tmux_available = None
        reset_backend()

        with patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux"), \
             patch("lib.backends.tmux._run_tmux") as mock_run:
            # First call for session_exists, second for capture-pane
            mock_run.side_effect = [(0, "", ""), (0, captured_output, "")]

            from lib.tmux import capture_pane, set_debug_logging
            set_debug_logging(True)

            # log_operation=True to enable logging for this test
            result = capture_pane("claude-test", correlation_id="corr-456", log_operation=True)

            assert result == captured_output

            logs = read_terminal_logs()
            assert len(logs) == 1
            assert logs[0]["direction"] == "in"
            assert logs[0]["event_type"] == "capture_pane"
            assert logs[0]["payload"] == captured_output
            assert logs[0]["correlation_id"] == "corr-456"

    def test_debug_off_no_payload(self, tmp_path, monkeypatch):
        """Debug off logs events but not payloads."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        # Reset backend state
        import lib.backends.tmux as tmux_backend
        from lib.backends import reset_backend
        tmux_backend._tmux_available = None
        reset_backend()

        with patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux"), \
             patch("lib.backends.tmux._run_tmux") as mock_run:
            # First call for session_exists, second for send-keys
            mock_run.side_effect = [(0, "", ""), (0, "", "")]

            from lib.tmux import send_keys, set_debug_logging
            set_debug_logging(False)

            # log_operation=True to enable logging for this test
            send_keys("claude-test", "Secret message", log_operation=True)

            logs = read_terminal_logs()
            assert len(logs) == 1
            assert logs[0]["payload"] is None  # No payload when debug off

    def test_correlation_id_links_operations(self, tmp_path, monkeypatch):
        """Correlation ID links send and capture operations."""
        log_file = tmp_path / "terminal.jsonl"
        monkeypatch.setattr("lib.terminal_logging.TERMINAL_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.terminal_logging.LOG_DIR", str(tmp_path))

        # Reset backend state
        import lib.backends.tmux as tmux_backend
        from lib.backends import reset_backend
        tmux_backend._tmux_available = None
        reset_backend()

        with patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux"), \
             patch("lib.backends.tmux._run_tmux") as mock_run:
            # Calls: session_exists (send), send-keys, session_exists (capture), capture-pane
            mock_run.side_effect = [(0, "", ""), (0, "", ""), (0, "", ""), (0, "response", "")]

            from lib.tmux import send_keys, capture_pane, set_debug_logging
            set_debug_logging(True)

            corr_id = "my-correlation-id"

            # log_operation=True to enable logging for this test
            send_keys("claude-test", "Request", correlation_id=corr_id, log_operation=True)
            capture_pane("claude-test", correlation_id=corr_id, log_operation=True)

            logs = read_terminal_logs()
            assert len(logs) == 2

            # Both should have the same correlation ID
            corr_ids = [log["correlation_id"] for log in logs]
            assert corr_ids == [corr_id, corr_id]

            # One should be out, one in
            directions = set(log["direction"] for log in logs)
            assert directions == {"out", "in"}
