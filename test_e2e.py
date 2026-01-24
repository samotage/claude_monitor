"""End-to-End Integration Tests for Claude Headspace.

This module provides E2E tests that:
- Bring up the Flask service in test mode
- Drive API/UI flows: session discovery, reset, notifications, logging toggles
- Use mocked tmux layer for deterministic tests (no real tmux required)
- Verify state changes across multiple API calls

These tests verify the complete request/response cycle and state management
without requiring actual tmux sessions or macOS-specific functionality.
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import yaml


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory for testing."""
    # Create temp directories for data
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    projects_dir = data_dir / "projects"
    projects_dir.mkdir()
    logs_dir = data_dir / "logs"
    logs_dir.mkdir()

    # Create a test config file
    config_path = tmp_path / "config.yaml"
    test_config = {
        "projects": [
            {"name": "Test Project", "path": str(tmp_path / "test-project")},
            {"name": "Another Project", "path": str(tmp_path / "another-project")},
        ],
        "scan_interval": 2,
        "openrouter": {"api_key": ""},
    }
    config_path.write_text(yaml.dump(test_config))

    # Create project directories
    (tmp_path / "test-project").mkdir()
    (tmp_path / "another-project").mkdir()

    # Patch the config path
    monkeypatch.setattr("config.CONFIG_PATH", config_path)
    monkeypatch.setattr("lib.projects.PROJECT_DATA_DIR", projects_dir)

    return tmp_path


@pytest.fixture
def client(temp_config_dir, monkeypatch):
    """Create Flask test client with mocked external dependencies."""
    from monitor import app

    # Mock tmux availability to avoid actual tmux calls
    monkeypatch.setattr("lib.sessions.is_tmux_available", lambda: True)

    # Mock tmux session listing - return empty list by default
    monkeypatch.setattr("lib.sessions.tmux_list_sessions", lambda: [])

    # Mock iTerm focus functions - don't actually call AppleScript
    monkeypatch.setattr("lib.iterm.focus_iterm_window_by_pid", lambda pid: True)
    monkeypatch.setattr("lib.iterm.focus_iterm_window_by_tmux_session", lambda name: True)
    monkeypatch.setattr("lib.iterm.get_pid_tty", lambda pid: "/dev/ttys001")

    # Mock notifications - don't actually send macOS notifications
    monkeypatch.setattr("lib.notifications.send_macos_notification",
                       lambda title, body, pid=None: True)

    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def mock_tmux_sessions():
    """Factory fixture to create mock tmux session data."""
    def _create_sessions(session_list):
        """Create mock session info.

        Args:
            session_list: List of dicts with session name and optional state

        Returns:
            Tuple of (list_sessions_return, get_session_info_func, session_exists_func)
        """
        sessions_by_name = {s["name"]: s for s in session_list}

        def get_session_info(name):
            session = sessions_by_name.get(name)
            if not session:
                return None
            return {
                "name": name,
                "created": str(int(datetime.now(timezone.utc).timestamp())),
                "pane_pid": session.get("pid", 12345),
                "pane_tty": session.get("tty", "/dev/ttys001"),
                "pane_path": session.get("path", "/tmp"),
                "attached": session.get("attached", False),
            }

        def session_exists(name):
            return name in sessions_by_name

        # Return the list for tmux_list_sessions
        list_return = [{"name": s["name"]} for s in session_list]

        return list_return, get_session_info, session_exists

    return _create_sessions


# =============================================================================
# E2E Tests - Basic Routes
# =============================================================================


class TestE2EBasicRoutes:
    """E2E tests for basic Flask routes."""

    def test_index_returns_html(self, client):
        """GET / returns the dashboard HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data or b"<html" in response.data

    def test_logging_page_returns_html(self, client):
        """GET /logging returns the logging panel HTML."""
        response = client.get("/logging")
        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data or b"<html" in response.data

    def test_api_readme_returns_json(self, client, temp_config_dir):
        """GET /api/readme returns JSON with HTML content."""
        # Create a README.md
        readme_path = temp_config_dir / "README.md"
        readme_path.write_text("# Test README\n\nSome content here.")

        response = client.get("/api/readme")
        assert response.status_code == 200
        data = response.get_json()
        assert "html" in data


# =============================================================================
# E2E Tests - Session Discovery Flow
# =============================================================================


class TestE2ESessionDiscovery:
    """E2E tests for session discovery via /api/sessions."""

    def test_sessions_empty_when_no_tmux_sessions(self, client, monkeypatch):
        """Sessions list is empty when no tmux sessions exist."""
        monkeypatch.setattr("lib.sessions.tmux_list_sessions", lambda: [])

        response = client.get("/api/sessions")
        assert response.status_code == 200

        data = response.get_json()
        assert "sessions" in data
        assert data["sessions"] == []
        assert "projects" in data

    def test_sessions_discovered_from_tmux(self, client, monkeypatch, mock_tmux_sessions, temp_config_dir):
        """Sessions are discovered from tmux and matched to projects."""
        # Create mock tmux sessions matching project names
        sessions = [
            {"name": "claude-test-project-abcd1234", "pid": 1001},
            {"name": "claude-another-project-efgh5678", "pid": 1002},
        ]
        list_ret, get_info, exists = mock_tmux_sessions(sessions)

        monkeypatch.setattr("lib.sessions.tmux_list_sessions", lambda: list_ret)
        monkeypatch.setattr("lib.sessions.get_session_info", get_info)
        monkeypatch.setattr("lib.sessions.tmux_session_exists", exists)
        # Mock capture_pane to return content indicating idle state
        monkeypatch.setattr("lib.sessions.capture_pane",
                           lambda name, lines=200: "✻ Ready\n❯")

        response = client.get("/api/sessions")
        assert response.status_code == 200

        data = response.get_json()
        assert len(data["sessions"]) == 2

        # Verify session structure
        session = data["sessions"][0]
        assert "project_name" in session
        assert "activity_state" in session
        assert "session_type" in session
        assert session["session_type"] == "tmux"

    def test_unmatched_sessions_still_displayed(self, client, monkeypatch, mock_tmux_sessions):
        """Sessions without matching projects are still shown with slug as name."""
        sessions = [
            {"name": "claude-unknown-project-12345678", "pid": 1001},
        ]
        list_ret, get_info, exists = mock_tmux_sessions(sessions)

        monkeypatch.setattr("lib.sessions.tmux_list_sessions", lambda: list_ret)
        monkeypatch.setattr("lib.sessions.get_session_info", get_info)
        monkeypatch.setattr("lib.sessions.tmux_session_exists", exists)
        monkeypatch.setattr("lib.sessions.capture_pane",
                           lambda name, lines=200: "✻ Ready\n❯")

        response = client.get("/api/sessions")
        assert response.status_code == 200

        data = response.get_json()
        assert len(data["sessions"]) == 1
        # Project name should be the slug since no config match
        assert data["sessions"][0]["project_name"] == "unknown-project"


# =============================================================================
# E2E Tests - Reset Flow
# =============================================================================


class TestE2EResetFlow:
    """E2E tests for the /api/reset endpoint."""

    def test_reset_clears_state(self, client):
        """POST /api/reset clears notification and priority state."""
        response = client.post("/api/reset")
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert "details" in data
        assert data["details"]["notification_state"] == "cleared"
        assert data["details"]["priorities_cache"] == "cleared"

    def test_reset_is_idempotent(self, client):
        """Multiple resets succeed without error."""
        for _ in range(3):
            response = client.post("/api/reset")
            assert response.status_code == 200
            assert response.get_json()["success"] is True

    def test_reset_affects_subsequent_session_scan(self, client, monkeypatch, mock_tmux_sessions):
        """After reset, session scan starts fresh without cached state."""
        # First, populate some session state
        sessions = [{"name": "claude-test-12345678", "pid": 1001}]
        list_ret, get_info, exists = mock_tmux_sessions(sessions)

        monkeypatch.setattr("lib.sessions.tmux_list_sessions", lambda: list_ret)
        monkeypatch.setattr("lib.sessions.get_session_info", get_info)
        monkeypatch.setattr("lib.sessions.tmux_session_exists", exists)
        monkeypatch.setattr("lib.sessions.capture_pane",
                           lambda name, lines=200: "✻ Ready\n❯")

        # Initial scan
        response1 = client.get("/api/sessions")
        assert response1.status_code == 200

        # Reset
        reset_response = client.post("/api/reset")
        assert reset_response.status_code == 200

        # Second scan should work normally
        response2 = client.get("/api/sessions")
        assert response2.status_code == 200


# =============================================================================
# E2E Tests - Notification Toggle Flow
# =============================================================================


class TestE2ENotificationFlow:
    """E2E tests for notification enable/disable flow."""

    def test_get_notification_state(self, client):
        """GET /api/notifications returns current state."""
        response = client.get("/api/notifications")
        assert response.status_code == 200

        data = response.get_json()
        assert "enabled" in data
        assert isinstance(data["enabled"], bool)

    def test_disable_notifications(self, client):
        """POST /api/notifications can disable notifications."""
        response = client.post(
            "/api/notifications",
            json={"enabled": False},
            content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["enabled"] is False

        # Verify state persisted
        get_response = client.get("/api/notifications")
        assert get_response.get_json()["enabled"] is False

    def test_enable_notifications(self, client):
        """POST /api/notifications can enable notifications."""
        # First disable
        client.post("/api/notifications", json={"enabled": False},
                   content_type="application/json")

        # Then enable
        response = client.post(
            "/api/notifications",
            json={"enabled": True},
            content_type="application/json"
        )
        assert response.status_code == 200
        assert response.get_json()["enabled"] is True

    def test_notification_toggle_cycle(self, client):
        """Full toggle cycle: enable -> disable -> enable."""
        # Enable
        client.post("/api/notifications", json={"enabled": True},
                   content_type="application/json")
        assert client.get("/api/notifications").get_json()["enabled"] is True

        # Disable
        client.post("/api/notifications", json={"enabled": False},
                   content_type="application/json")
        assert client.get("/api/notifications").get_json()["enabled"] is False

        # Enable again
        client.post("/api/notifications", json={"enabled": True},
                   content_type="application/json")
        assert client.get("/api/notifications").get_json()["enabled"] is True

    def test_notification_test_endpoint(self, client):
        """POST /api/notifications/test sends a test notification."""
        response = client.post("/api/notifications/test")
        assert response.status_code == 200

        data = response.get_json()
        assert "success" in data
        # Should succeed since we mocked send_macos_notification


# =============================================================================
# E2E Tests - Logging Toggle Flow
# =============================================================================


class TestE2ELoggingToggleFlow:
    """E2E tests for tmux debug logging toggle."""

    def test_get_logging_debug_state(self, client):
        """GET /api/logs/tmux/debug returns current debug state."""
        response = client.get("/api/logs/tmux/debug")
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert "debug_enabled" in data
        assert isinstance(data["debug_enabled"], bool)

    def test_enable_debug_logging(self, client):
        """POST /api/logs/tmux/debug enables debug logging."""
        response = client.post(
            "/api/logs/tmux/debug",
            json={"enabled": True},
            content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert data["debug_enabled"] is True

    def test_disable_debug_logging(self, client):
        """POST /api/logs/tmux/debug disables debug logging."""
        response = client.post(
            "/api/logs/tmux/debug",
            json={"enabled": False},
            content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert data["debug_enabled"] is False

    def test_logging_toggle_persists(self, client):
        """Debug logging state persists across requests."""
        # Enable
        client.post("/api/logs/tmux/debug", json={"enabled": True},
                   content_type="application/json")

        # Verify
        response = client.get("/api/logs/tmux/debug")
        assert response.get_json()["debug_enabled"] is True

        # Disable
        client.post("/api/logs/tmux/debug", json={"enabled": False},
                   content_type="application/json")

        # Verify
        response = client.get("/api/logs/tmux/debug")
        assert response.get_json()["debug_enabled"] is False


# =============================================================================
# E2E Tests - Config API
# =============================================================================


class TestE2EConfigAPI:
    """E2E tests for configuration API."""

    def test_get_config(self, client, temp_config_dir):
        """GET /api/config returns current configuration."""
        response = client.get("/api/config")
        assert response.status_code == 200

        data = response.get_json()
        assert "projects" in data
        assert len(data["projects"]) == 2
        assert "scan_interval" in data

    def test_update_config(self, client, temp_config_dir):
        """POST /api/config updates configuration."""
        new_config = {
            "projects": [
                {"name": "Updated Project", "path": "/updated/path"}
            ],
            "scan_interval": 5,
        }

        response = client.post(
            "/api/config",
            json=new_config,
            content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data.get("success") is True or "projects" in data

        # Verify the change persisted
        get_response = client.get("/api/config")
        config = get_response.get_json()
        assert config["scan_interval"] == 5


# =============================================================================
# E2E Tests - Priorities API
# =============================================================================


class TestE2EPrioritiesAPI:
    """E2E tests for priorities API."""

    def test_priorities_when_disabled(self, client, monkeypatch):
        """GET /api/priorities returns 404 when disabled."""
        monkeypatch.setattr("monitor.is_priorities_enabled", lambda: False)

        response = client.get("/api/priorities")
        assert response.status_code == 404

        data = response.get_json()
        assert data["success"] is False

    def test_priorities_with_no_sessions(self, client, monkeypatch):
        """GET /api/priorities returns empty list when no sessions."""
        monkeypatch.setattr("lib.headspace.is_priorities_enabled", lambda: True)
        monkeypatch.setattr("lib.sessions.tmux_list_sessions", lambda: [])

        response = client.get("/api/priorities")
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert data["priorities"] == []


# =============================================================================
# E2E Tests - Activity State Transitions
# =============================================================================


class TestE2EActivityStateTransitions:
    """E2E tests for activity state changes across scan cycles."""

    def test_state_change_idle_to_processing(self, client, monkeypatch, mock_tmux_sessions):
        """Session state change from idle to processing is detected."""
        sessions = [{"name": "claude-test-12345678", "pid": 1001}]
        list_ret, get_info, exists = mock_tmux_sessions(sessions)

        monkeypatch.setattr("lib.sessions.tmux_list_sessions", lambda: list_ret)
        monkeypatch.setattr("lib.sessions.get_session_info", get_info)
        monkeypatch.setattr("lib.sessions.tmux_session_exists", exists)

        # First scan - idle state
        monkeypatch.setattr("lib.sessions.capture_pane",
                           lambda name, lines=200: "✻ Ready\n❯")
        response1 = client.get("/api/sessions")
        data1 = response1.get_json()
        assert data1["sessions"][0]["activity_state"] == "idle"

        # Second scan - processing state
        monkeypatch.setattr("lib.sessions.capture_pane",
                           lambda name, lines=200: "Working... (esc to interrupt)")
        response2 = client.get("/api/sessions")
        data2 = response2.get_json()
        assert data2["sessions"][0]["activity_state"] == "processing"

    def test_state_change_processing_to_idle(self, client, monkeypatch, mock_tmux_sessions):
        """Session state change from processing to idle is detected."""
        sessions = [{"name": "claude-test-12345678", "pid": 1001}]
        list_ret, get_info, exists = mock_tmux_sessions(sessions)

        monkeypatch.setattr("lib.sessions.tmux_list_sessions", lambda: list_ret)
        monkeypatch.setattr("lib.sessions.get_session_info", get_info)
        monkeypatch.setattr("lib.sessions.tmux_session_exists", exists)

        # First scan - processing state
        monkeypatch.setattr("lib.sessions.capture_pane",
                           lambda name, lines=200: "Working... (esc to interrupt)")
        response1 = client.get("/api/sessions")
        data1 = response1.get_json()
        assert data1["sessions"][0]["activity_state"] == "processing"

        # Second scan - idle state after completion
        monkeypatch.setattr("lib.sessions.capture_pane",
                           lambda name, lines=200: "Done!\n\n✻ Baked for 2m 30s\n❯")
        response2 = client.get("/api/sessions")
        data2 = response2.get_json()
        assert data2["sessions"][0]["activity_state"] == "idle"


# =============================================================================
# E2E Tests - Log Endpoints
# =============================================================================


class TestE2ELogEndpoints:
    """E2E tests for log retrieval endpoints."""

    def test_get_tmux_logs_empty(self, client, temp_config_dir):
        """GET /api/logs/tmux returns empty list when no logs."""
        response = client.get("/api/logs/tmux")
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert "logs" in data
        assert "count" in data

    def test_get_openrouter_logs_empty(self, client, temp_config_dir):
        """GET /api/logs/openrouter returns empty list when no logs."""
        response = client.get("/api/logs/openrouter")
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert "logs" in data


# =============================================================================
# E2E Tests - Headspace API
# =============================================================================


class TestE2EHeadspaceAPI:
    """E2E tests for headspace (current focus) API."""

    def test_get_headspace_empty(self, client, monkeypatch):
        """GET /api/headspace returns empty when not set."""
        monkeypatch.setattr("lib.headspace.load_headspace", lambda: None)

        response = client.get("/api/headspace")
        assert response.status_code == 200

        data = response.get_json()
        # Should return null or empty when no headspace set
        assert data is None or data == {} or data.get("current_focus") is None

    def test_set_headspace(self, client, temp_config_dir, monkeypatch):
        """POST /api/headspace sets current focus."""
        # Create headspace data directory
        headspace_file = temp_config_dir / "data" / "headspace.yaml"
        monkeypatch.setattr("lib.headspace.HEADSPACE_DATA_PATH", headspace_file)

        response = client.post(
            "/api/headspace",
            json={"current_focus": "Ship authentication feature"},
            content_type="application/json"
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["current_focus"] == "Ship authentication feature"


# =============================================================================
# E2E Tests - Full User Flows
# =============================================================================


class TestE2EFullUserFlows:
    """E2E tests simulating complete user interaction flows."""

    def test_full_session_monitoring_flow(self, client, monkeypatch, mock_tmux_sessions):
        """Simulate a complete session monitoring flow:
        1. Start with no sessions
        2. Session appears (tmux session started)
        3. Session shows as processing
        4. Session shows as idle after completion
        5. Reset clears state
        """
        sessions = [{"name": "claude-my-project-abcd1234", "pid": 2001}]
        list_ret, get_info, exists = mock_tmux_sessions(sessions)

        # Step 1: No sessions initially
        monkeypatch.setattr("lib.sessions.tmux_list_sessions", lambda: [])
        response = client.get("/api/sessions")
        assert response.get_json()["sessions"] == []

        # Step 2 & 3: Session appears and is processing
        monkeypatch.setattr("lib.sessions.tmux_list_sessions", lambda: list_ret)
        monkeypatch.setattr("lib.sessions.get_session_info", get_info)
        monkeypatch.setattr("lib.sessions.tmux_session_exists", exists)
        monkeypatch.setattr("lib.sessions.capture_pane",
                           lambda name, lines=200: "Running task... (esc to interrupt)")

        response = client.get("/api/sessions")
        data = response.get_json()
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["activity_state"] == "processing"

        # Step 4: Session completes and is idle
        monkeypatch.setattr("lib.sessions.capture_pane",
                           lambda name, lines=200: "Task complete.\n\n✻ Worked for 5m\n❯")

        response = client.get("/api/sessions")
        data = response.get_json()
        assert data["sessions"][0]["activity_state"] == "idle"

        # Step 5: Reset clears state
        reset_response = client.post("/api/reset")
        assert reset_response.get_json()["success"] is True

        # Session still exists after reset
        response = client.get("/api/sessions")
        assert len(response.get_json()["sessions"]) == 1

    def test_notification_settings_flow(self, client):
        """Simulate a user configuring notifications:
        1. Check current state
        2. Disable notifications
        3. Try to send test notification (should still work - test always sends)
        4. Enable notifications
        5. Send test notification
        """
        # Step 1: Check initial state
        response = client.get("/api/notifications")
        initial_state = response.get_json()["enabled"]

        # Step 2: Disable
        client.post("/api/notifications", json={"enabled": False},
                   content_type="application/json")
        assert client.get("/api/notifications").get_json()["enabled"] is False

        # Step 3: Test notification (works regardless of enabled state)
        test_response = client.post("/api/notifications/test")
        assert test_response.get_json()["success"] is True

        # Step 4: Enable
        client.post("/api/notifications", json={"enabled": True},
                   content_type="application/json")
        assert client.get("/api/notifications").get_json()["enabled"] is True

        # Step 5: Test notification
        test_response = client.post("/api/notifications/test")
        assert test_response.get_json()["success"] is True

    def test_logging_configuration_flow(self, client):
        """Simulate a user configuring debug logging:
        1. Check current debug state
        2. Enable debug logging
        3. Verify enabled
        4. Disable debug logging
        5. Verify disabled
        """
        # Step 1: Check initial
        response = client.get("/api/logs/tmux/debug")
        assert response.get_json()["success"] is True

        # Step 2: Enable
        response = client.post("/api/logs/tmux/debug", json={"enabled": True},
                              content_type="application/json")
        assert response.get_json()["debug_enabled"] is True

        # Step 3: Verify enabled
        response = client.get("/api/logs/tmux/debug")
        assert response.get_json()["debug_enabled"] is True

        # Step 4: Disable
        response = client.post("/api/logs/tmux/debug", json={"enabled": False},
                              content_type="application/json")
        assert response.get_json()["debug_enabled"] is False

        # Step 5: Verify disabled
        response = client.get("/api/logs/tmux/debug")
        assert response.get_json()["debug_enabled"] is False
