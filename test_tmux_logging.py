"""Tests for tmux session message logging functionality."""

import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from lib.tmux_logging import (
    TmuxLogEntry,
    truncate_payload,
    write_tmux_log_entry,
    create_tmux_log_entry,
    read_tmux_logs,
    get_tmux_logs_since,
    search_tmux_logs,
    get_tmux_log_stats,
    MAX_PAYLOAD_SIZE,
    TMUX_LOG_FILE,
)


# =============================================================================
# TmuxLogEntry Dataclass Tests
# =============================================================================


class TestTmuxLogEntry:
    """Tests for TmuxLogEntry dataclass."""

    def test_create_entry_all_fields(self):
        """Creates entry with all fields."""
        entry = TmuxLogEntry(
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
        )

        assert entry.id == "test-id-123"
        assert entry.session_id == "my-project"
        assert entry.direction == "out"
        assert entry.event_type == "send_keys"
        assert entry.payload == "Hello, world!"
        assert entry.correlation_id == "corr-123"
        assert entry.truncated is False
        assert entry.success is True

    def test_create_entry_minimal(self):
        """Creates entry with minimal required fields."""
        entry = TmuxLogEntry(
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


class TestCreateTmuxLogEntry:
    """Tests for creating tmux log entries."""

    def test_create_entry_debug_enabled(self):
        """Creates entry with payload when debug enabled."""
        entry = create_tmux_log_entry(
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

    def test_create_entry_debug_disabled(self):
        """Creates entry without payload when debug disabled."""
        entry = create_tmux_log_entry(
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
        entry = create_tmux_log_entry(
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


# =============================================================================
# Log File Read/Write Tests
# =============================================================================


class TestWriteAndReadLogs:
    """Tests for writing and reading log entries."""

    def test_write_and_read_entry(self, tmp_path, monkeypatch):
        """Writes entry and reads it back."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        entry = TmuxLogEntry(
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
        result = write_tmux_log_entry(entry)
        assert result is True
        assert log_file.exists()

        # Read
        logs = read_tmux_logs()
        assert len(logs) == 1
        assert logs[0]["id"] == "test-id-123"
        assert logs[0]["payload"] == "Hello!"

    def test_read_empty_file(self, tmp_path, monkeypatch):
        """Returns empty list when log file doesn't exist."""
        log_file = tmp_path / "nonexistent.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))

        logs = read_tmux_logs()
        assert logs == []

    def test_read_multiple_entries_sorted(self, tmp_path, monkeypatch):
        """Reads multiple entries sorted by timestamp descending."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        # Write entries with different timestamps
        entry1 = TmuxLogEntry(
            id="1", timestamp="2026-01-24T09:00:00+00:00",
            session_id="p", tmux_session_name="claude-p",
            direction="out", event_type="send_keys"
        )
        entry2 = TmuxLogEntry(
            id="2", timestamp="2026-01-24T11:00:00+00:00",
            session_id="p", tmux_session_name="claude-p",
            direction="out", event_type="send_keys"
        )
        entry3 = TmuxLogEntry(
            id="3", timestamp="2026-01-24T10:00:00+00:00",
            session_id="p", tmux_session_name="claude-p",
            direction="out", event_type="send_keys"
        )

        write_tmux_log_entry(entry1)
        write_tmux_log_entry(entry2)
        write_tmux_log_entry(entry3)

        logs = read_tmux_logs()
        assert len(logs) == 3
        # Should be sorted newest first
        assert logs[0]["id"] == "2"  # 11:00
        assert logs[1]["id"] == "3"  # 10:00
        assert logs[2]["id"] == "1"  # 09:00


# =============================================================================
# Log Filtering Tests
# =============================================================================


class TestGetTmuxLogsSince:
    """Tests for filtering logs by timestamp."""

    def test_get_logs_since(self, tmp_path, monkeypatch):
        """Returns only logs after the given timestamp."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        entries = [
            TmuxLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys"),
            TmuxLogEntry(id="2", timestamp="2026-01-24T11:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys"),
            TmuxLogEntry(id="3", timestamp="2026-01-24T10:00:00+00:00",
                        session_id="p", tmux_session_name="claude-p",
                        direction="out", event_type="send_keys"),
        ]
        for e in entries:
            write_tmux_log_entry(e)

        logs = get_tmux_logs_since("2026-01-24T09:30:00+00:00")

        assert len(logs) == 2
        ids = [log["id"] for log in logs]
        assert "2" in ids
        assert "3" in ids
        assert "1" not in ids

    def test_get_logs_since_none(self, tmp_path, monkeypatch):
        """Returns all logs when since is None."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        entry = TmuxLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                            session_id="p", tmux_session_name="claude-p",
                            direction="out", event_type="send_keys")
        write_tmux_log_entry(entry)

        logs = get_tmux_logs_since(None)
        assert len(logs) == 1


class TestSearchTmuxLogs:
    """Tests for searching/filtering logs."""

    def test_search_by_session_id(self, tmp_path, monkeypatch):
        """Filters logs by session_id."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        entries = [
            TmuxLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                        session_id="project-a", tmux_session_name="claude-project-a",
                        direction="out", event_type="send_keys"),
            TmuxLogEntry(id="2", timestamp="2026-01-24T10:00:00+00:00",
                        session_id="project-b", tmux_session_name="claude-project-b",
                        direction="out", event_type="send_keys"),
        ]
        for e in entries:
            write_tmux_log_entry(e)

        logs = search_tmux_logs("", session_id="project-a")

        assert len(logs) == 1
        assert logs[0]["session_id"] == "project-a"

    def test_search_by_query(self, tmp_path, monkeypatch):
        """Searches logs by query string in fields."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        entries = [
            TmuxLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                        session_id="my-project", tmux_session_name="claude-my-project",
                        direction="out", event_type="send_keys",
                        payload="Hello world"),
            TmuxLogEntry(id="2", timestamp="2026-01-24T10:00:00+00:00",
                        session_id="other", tmux_session_name="claude-other",
                        direction="in", event_type="capture_pane",
                        payload="Goodbye world"),
        ]
        for e in entries:
            write_tmux_log_entry(e)

        logs = search_tmux_logs("Hello")

        assert len(logs) == 1
        assert logs[0]["id"] == "1"

    def test_search_empty_query(self, tmp_path, monkeypatch):
        """Empty query returns all logs."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        entry = TmuxLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                            session_id="p", tmux_session_name="claude-p",
                            direction="out", event_type="send_keys")
        write_tmux_log_entry(entry)

        logs = search_tmux_logs("")
        assert len(logs) == 1


# =============================================================================
# Log Statistics Tests
# =============================================================================


class TestGetTmuxLogStats:
    """Tests for aggregate log statistics."""

    def test_stats_calculation(self, tmp_path, monkeypatch):
        """Calculates correct statistics."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        entries = [
            TmuxLogEntry(id="1", timestamp="2026-01-24T09:00:00+00:00",
                        session_id="project-a", tmux_session_name="claude-project-a",
                        direction="out", event_type="send_keys", success=True),
            TmuxLogEntry(id="2", timestamp="2026-01-24T10:00:00+00:00",
                        session_id="project-a", tmux_session_name="claude-project-a",
                        direction="in", event_type="capture_pane", success=True),
            TmuxLogEntry(id="3", timestamp="2026-01-24T11:00:00+00:00",
                        session_id="project-b", tmux_session_name="claude-project-b",
                        direction="out", event_type="send_keys", success=False),
        ]
        for e in entries:
            write_tmux_log_entry(e)

        stats = get_tmux_log_stats()

        assert stats["total_entries"] == 3
        assert stats["send_count"] == 2
        assert stats["capture_count"] == 1
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 1
        assert stats["unique_sessions"] == 2

    def test_stats_empty_logs(self, tmp_path, monkeypatch):
        """Returns zero stats when no logs."""
        log_file = tmp_path / "nonexistent.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))

        stats = get_tmux_log_stats()

        assert stats["total_entries"] == 0
        assert stats["send_count"] == 0
        assert stats["capture_count"] == 0


# =============================================================================
# Integration Tests with lib/tmux.py
# =============================================================================


class TestTmuxLoggingIntegration:
    """Integration tests for tmux logging with send_keys/capture_pane."""

    def test_send_keys_logs_event(self, tmp_path, monkeypatch):
        """send_keys creates log entry."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        # Mock tmux functions
        with patch("lib.tmux.is_tmux_available", return_value=True), \
             patch("lib.tmux.session_exists", return_value=True), \
             patch("lib.tmux._run_tmux", return_value=(0, "", "")):

            from lib.tmux import send_keys, set_debug_logging
            set_debug_logging(True)

            # log_operation=True to enable logging for this test
            result = send_keys("claude-test", "Hello!", correlation_id="corr-123", log_operation=True)

            assert result is True

            logs = read_tmux_logs()
            assert len(logs) == 1
            assert logs[0]["direction"] == "out"
            assert logs[0]["event_type"] == "send_keys"
            assert logs[0]["payload"] == "Hello!"
            assert logs[0]["correlation_id"] == "corr-123"

    def test_capture_pane_logs_event(self, tmp_path, monkeypatch):
        """capture_pane creates log entry."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        captured_output = "Line 1\nLine 2\nLine 3"

        with patch("lib.tmux.is_tmux_available", return_value=True), \
             patch("lib.tmux.session_exists", return_value=True), \
             patch("lib.tmux._run_tmux", return_value=(0, captured_output, "")):

            from lib.tmux import capture_pane, set_debug_logging
            set_debug_logging(True)

            # log_operation=True to enable logging for this test
            result = capture_pane("claude-test", correlation_id="corr-456", log_operation=True)

            assert result == captured_output

            logs = read_tmux_logs()
            assert len(logs) == 1
            assert logs[0]["direction"] == "in"
            assert logs[0]["event_type"] == "capture_pane"
            assert logs[0]["payload"] == captured_output
            assert logs[0]["correlation_id"] == "corr-456"

    def test_debug_off_no_payload(self, tmp_path, monkeypatch):
        """Debug off logs events but not payloads."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        with patch("lib.tmux.is_tmux_available", return_value=True), \
             patch("lib.tmux.session_exists", return_value=True), \
             patch("lib.tmux._run_tmux", return_value=(0, "", "")):

            from lib.tmux import send_keys, set_debug_logging
            set_debug_logging(False)

            # log_operation=True to enable logging for this test
            send_keys("claude-test", "Secret message", log_operation=True)

            logs = read_tmux_logs()
            assert len(logs) == 1
            assert logs[0]["payload"] is None  # No payload when debug off

    def test_correlation_id_links_operations(self, tmp_path, monkeypatch):
        """Correlation ID links send and capture operations."""
        log_file = tmp_path / "tmux.jsonl"
        monkeypatch.setattr("lib.tmux_logging.TMUX_LOG_FILE", str(log_file))
        monkeypatch.setattr("lib.tmux_logging.LOG_DIR", str(tmp_path))

        with patch("lib.tmux.is_tmux_available", return_value=True), \
             patch("lib.tmux.session_exists", return_value=True), \
             patch("lib.tmux._run_tmux", return_value=(0, "response", "")):

            from lib.tmux import send_keys, capture_pane, set_debug_logging
            set_debug_logging(True)

            corr_id = "my-correlation-id"

            # log_operation=True to enable logging for this test
            send_keys("claude-test", "Request", correlation_id=corr_id, log_operation=True)
            capture_pane("claude-test", correlation_id=corr_id, log_operation=True)

            logs = read_tmux_logs()
            assert len(logs) == 2

            # Both should have the same correlation ID
            corr_ids = [log["correlation_id"] for log in logs]
            assert corr_ids == [corr_id, corr_id]

            # One should be out, one in
            directions = set(log["direction"] for log in logs)
            assert directions == {"out", "in"}
