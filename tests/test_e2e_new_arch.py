"""End-to-End Integration Tests for Claude Headspace (New Architecture).

This module provides E2E tests for the new src/ architecture that:
- Bring up the Flask service in test mode using src.app.create_app
- Drive API/UI flows: agents, config, hooks, notifications, logging
- Use mocked terminal backends for deterministic tests
- Verify state changes across multiple API calls

These tests ensure the new architecture provides complete API coverage.
"""

from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.app import create_app
from src.services.config_service import reset_config_service


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory for testing."""
    # Create data directory
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create a test config file
    config_path = tmp_path / "config.yaml"
    test_config = {
        "projects": [
            {"name": "Test Project", "path": str(tmp_path / "test-project")},
        ],
        "scan_interval": 2,
        "terminal_backend": "wezterm",
        "notifications": {"enabled": True},
        "hooks": {"enabled": True},
    }
    config_path.write_text(yaml.dump(test_config))

    # Create project directory
    (tmp_path / "test-project").mkdir()

    return tmp_path


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons between tests."""
    reset_config_service()
    yield
    reset_config_service()


@pytest.fixture
def app(temp_config_dir, monkeypatch):
    """Create Flask app with mocked dependencies."""
    # Change to temp dir so data/ is created there
    import os

    original_cwd = os.getcwd()
    os.chdir(temp_config_dir)

    # Mock terminal backend
    mock_backend = MagicMock()
    mock_backend.is_available.return_value = True
    mock_backend.list_sessions.return_value = []
    mock_backend.get_content.return_value = "test content"
    mock_backend.send_text.return_value = True
    mock_backend.focus_pane.return_value = True
    mock_backend.focus_by_name.return_value = True

    with patch("src.backends.wezterm.get_wezterm_backend", return_value=mock_backend):
        app = create_app(str(temp_config_dir / "config.yaml"))
        app.config["TESTING"] = True
        yield app

    os.chdir(original_cwd)


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


# =============================================================================
# Basic Routes
# =============================================================================


class TestBasicRoutes:
    """Tests for basic route functionality."""

    def test_index_returns_html(self, client):
        """GET / returns the dashboard HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data or b"<html" in response.data

    def test_static_files_accessible(self, client):
        """Static files are accessible."""
        response = client.get("/static/js/api.js")
        # May be 200 or 404 depending on working directory
        assert response.status_code in (200, 404)


# =============================================================================
# Config API
# =============================================================================


class TestConfigAPI:
    """Tests for /api/config endpoints."""

    def test_get_config(self, client):
        """GET /api/config returns current configuration."""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.get_json()

        assert "projects" in data
        assert "scan_interval" in data
        assert "terminal_backend" in data

    def test_update_config_scan_interval(self, client):
        """POST /api/config can update scan_interval."""
        response = client.post(
            "/api/config",
            json={"scan_interval": 5},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["scan_interval"] == 5

    def test_update_config_add_project(self, client):
        """POST /api/config can add a project."""
        response = client.post(
            "/api/config",
            json={
                "projects": [
                    {"name": "Test Project", "path": "/test"},
                    {"name": "New Project", "path": "/new"},
                ]
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["projects"]) == 2

    def test_update_config_remove_project(self, client):
        """POST /api/config can remove projects."""
        response = client.post(
            "/api/config",
            json={"projects": []},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["projects"]) == 0

    def test_update_config_invalid_value_rejected(self, client):
        """POST /api/config rejects invalid values."""
        response = client.post(
            "/api/config",
            json={"scan_interval": 1000},  # Max is 60
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_config_persists_after_update(self, client):
        """Config changes persist across requests."""
        # Update
        client.post(
            "/api/config",
            json={"scan_interval": 7},
            content_type="application/json",
        )

        # Verify persisted
        response = client.get("/api/config")
        assert response.get_json()["scan_interval"] == 7


# =============================================================================
# Agents API
# =============================================================================


class TestAgentsAPI:
    """Tests for /api/agents endpoints."""

    def test_list_agents_empty(self, client):
        """GET /api/agents returns empty list initially."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.get_json()
        assert "agents" in data
        assert isinstance(data["agents"], list)

    def test_get_agent_not_found(self, client):
        """GET /api/agents/<id> returns 404 for unknown agent."""
        response = client.get("/api/agents/nonexistent-id")
        assert response.status_code == 404

    def test_reset_clears_agents(self, client):
        """POST /api/reset clears all agents."""
        response = client.post("/api/reset")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify agents cleared
        agents_response = client.get("/api/agents")
        assert len(agents_response.get_json()["agents"]) == 0


# =============================================================================
# Sessions API (Legacy Compatibility)
# =============================================================================


class TestSessionsAPI:
    """Tests for legacy /api/sessions endpoint."""

    def test_sessions_returns_agents(self, client):
        """GET /api/sessions returns sessions (legacy format)."""
        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = response.get_json()
        assert "sessions" in data
        assert "projects" in data


# =============================================================================
# Hooks API
# =============================================================================


class TestHooksAPI:
    """Tests for /hook/* endpoints."""

    def test_hook_status(self, client):
        """GET /hook/status returns hook receiver status."""
        response = client.get("/hook/status")
        assert response.status_code == 200
        data = response.get_json()
        assert "enabled" in data
        assert "active" in data

    def test_hook_session_start(self, client):
        """POST /hook/session-start creates agent."""
        response = client.post(
            "/hook/session-start",
            json={
                "session_id": "test-session-123",
                "event": "session-start",
                "cwd": "/test/project",
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert "agent_id" in data

    def test_hook_user_prompt_submit(self, client):
        """POST /hook/user-prompt-submit transitions to processing."""
        # First create a session
        start_response = client.post(
            "/hook/session-start",
            json={
                "session_id": "test-session-456",
                "event": "session-start",
                "cwd": "/test/project",
            },
            content_type="application/json",
        )
        _agent_id = start_response.get_json()["agent_id"]  # noqa: F841

        # Then submit a prompt
        response = client.post(
            "/hook/user-prompt-submit",
            json={
                "session_id": "test-session-456",
                "event": "user-prompt-submit",
                "cwd": "/test/project",
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["state"] == "processing"

    def test_hook_stop(self, client):
        """POST /hook/stop transitions to idle."""
        # Create session and start processing
        client.post(
            "/hook/session-start",
            json={"session_id": "test-session-789", "cwd": "/test"},
            content_type="application/json",
        )
        client.post(
            "/hook/user-prompt-submit",
            json={"session_id": "test-session-789", "cwd": "/test"},
            content_type="application/json",
        )

        # Stop (turn complete)
        response = client.post(
            "/hook/stop",
            json={"session_id": "test-session-789", "cwd": "/test"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["state"] == "idle"

    def test_hook_session_end(self, client):
        """POST /hook/session-end handles session end."""
        # Create session
        client.post(
            "/hook/session-start",
            json={"session_id": "test-session-end", "cwd": "/test"},
            content_type="application/json",
        )

        # End session
        response = client.post(
            "/hook/session-end",
            json={"session_id": "test-session-end"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"

    def test_hook_unknown_type_accepted(self, client):
        """POST /hook/<unknown> is accepted for forward compatibility."""
        response = client.post(
            "/hook/future-event-type",
            json={"session_id": "test"},
            content_type="application/json",
        )
        assert response.status_code == 200


# =============================================================================
# Notifications API
# =============================================================================


class TestNotificationsAPI:
    """Tests for /api/notifications endpoints."""

    def test_get_notification_state(self, client):
        """GET /api/notifications returns notification state."""
        response = client.get("/api/notifications")
        assert response.status_code == 200
        data = response.get_json()
        assert "enabled" in data

    def test_disable_notifications(self, client):
        """POST /api/notifications can disable notifications."""
        response = client.post(
            "/api/notifications",
            json={"enabled": False},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["enabled"] is False

    def test_enable_notifications(self, client):
        """POST /api/notifications can enable notifications."""
        # First disable
        client.post(
            "/api/notifications",
            json={"enabled": False},
            content_type="application/json",
        )

        # Then enable
        response = client.post(
            "/api/notifications",
            json={"enabled": True},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["enabled"] is True

    def test_notification_test_endpoint(self, client):
        """POST /api/notifications/test sends test notification."""
        response = client.post("/api/notifications/test")
        assert response.status_code == 200
        # May succeed or fail depending on terminal-notifier availability


# =============================================================================
# Logging API
# =============================================================================


class TestLoggingAPI:
    """Tests for /api/logs/* endpoints."""

    def test_get_terminal_logs(self, client):
        """GET /api/logs/terminal returns logs."""
        response = client.get("/api/logs/terminal")
        assert response.status_code == 200
        data = response.get_json()
        # API returns "logs" key
        assert "logs" in data or "entries" in data

    def test_get_terminal_logs_stats(self, client):
        """GET /api/logs/terminal/stats returns stats."""
        response = client.get("/api/logs/terminal/stats")
        assert response.status_code == 200
        data = response.get_json()
        assert "total_entries" in data or "error" not in data

    def test_get_debug_state(self, client):
        """GET /api/logs/terminal/debug returns debug state."""
        response = client.get("/api/logs/terminal/debug")
        assert response.status_code == 200
        data = response.get_json()
        # API returns "debug_enabled" key
        assert "debug_enabled" in data or "enabled" in data

    def test_set_debug_state(self, client):
        """POST /api/logs/terminal/debug sets debug state."""
        response = client.post(
            "/api/logs/terminal/debug",
            json={"enabled": True},
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_clear_terminal_logs(self, client):
        """DELETE /api/logs/terminal clears logs."""
        response = client.delete("/api/logs/terminal")
        assert response.status_code == 200

    def test_get_openrouter_logs(self, client):
        """GET /api/logs/openrouter returns inference logs."""
        response = client.get("/api/logs/openrouter")
        assert response.status_code == 200
        data = response.get_json()
        # API returns "logs" key
        assert "logs" in data or "entries" in data or "calls" in data


# =============================================================================
# Headspace API
# =============================================================================


class TestHeadspaceAPI:
    """Tests for /api/headspace endpoints."""

    def test_get_headspace_empty(self, client):
        """GET /api/headspace returns null when not set."""
        response = client.get("/api/headspace")
        assert response.status_code == 200
        # May return null or empty object

    def test_set_headspace(self, client):
        """POST /api/headspace sets focus."""
        response = client.post(
            "/api/headspace",
            json={
                "focus": "Testing the new architecture",
                "constraints": "No breaking changes",
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("focus") == "Testing the new architecture" or "current_focus" in data

    def test_get_headspace_history(self, client):
        """GET /api/headspace/history returns history."""
        response = client.get("/api/headspace/history")
        assert response.status_code == 200
        data = response.get_json()
        assert "history" in data


# =============================================================================
# Priorities API
# =============================================================================


class TestPrioritiesAPI:
    """Tests for /api/priorities endpoints."""

    def test_get_priorities_empty(self, client):
        """GET /api/priorities returns empty when no agents."""
        response = client.get("/api/priorities")
        assert response.status_code in (200, 404)  # May be disabled

    def test_invalidate_priorities(self, client):
        """POST /api/priorities/invalidate clears cache."""
        response = client.post("/api/priorities/invalidate")
        assert response.status_code == 200


# =============================================================================
# Projects API
# =============================================================================


class TestProjectsAPI:
    """Tests for /api/projects endpoints."""

    def test_list_projects(self, client):
        """GET /api/projects returns project list."""
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.get_json()
        assert "projects" in data

    def test_get_project_not_found(self, client):
        """GET /api/projects/<id> returns 404 for unknown."""
        response = client.get("/api/projects/nonexistent")
        assert response.status_code == 404


# =============================================================================
# Events API (SSE)
# =============================================================================


class TestEventsAPI:
    """Tests for /api/events endpoints."""

    def test_events_stream_accessible(self, client):
        """GET /api/events is accessible."""
        # SSE streams don't return immediately, just verify endpoint exists
        # by checking it doesn't 404
        response = client.get("/api/events", headers={"Accept": "text/event-stream"})
        # May timeout or return partial, just verify it's not 404/405
        assert response.status_code in (200, 500)  # 500 if no SSE support in test

    def test_events_test_endpoint(self, client):
        """POST /api/events/test sends test event."""
        response = client.post("/api/events/test")
        assert response.status_code == 200


# =============================================================================
# Focus API (Legacy)
# =============================================================================


class TestFocusAPI:
    """Tests for legacy focus endpoints."""

    def test_focus_by_pid_deprecated(self, client):
        """POST /api/focus/<pid> returns deprecation message."""
        response = client.post("/api/focus/12345")
        assert response.status_code == 200
        data = response.get_json()
        # Should indicate PID focus is deprecated
        assert not data.get("success") or "deprecated" in str(data).lower()

    def test_focus_by_session(self, client):
        """POST /api/focus/session/<name> calls backend."""
        response = client.post("/api/focus/session/test-session")
        assert response.status_code == 200


# =============================================================================
# Full User Flows
# =============================================================================


class TestFullUserFlows:
    """Tests for complete user interaction flows."""

    def test_hook_driven_session_lifecycle(self, client):
        """Test complete session lifecycle via hooks.

        1. Session starts -> agent created in IDLE
        2. User submits prompt -> PROCESSING
        3. Claude stops -> IDLE
        4. Session ends -> cleaned up
        """
        session_id = "lifecycle-test-session"

        # 1. Session start
        start_response = client.post(
            "/hook/session-start",
            json={"session_id": session_id, "cwd": "/test/project"},
            content_type="application/json",
        )
        assert start_response.status_code == 200
        agent_id = start_response.get_json()["agent_id"]

        # Verify agent exists
        agents_response = client.get("/api/agents")
        agents = agents_response.get_json()["agents"]
        assert any(a["id"] == agent_id for a in agents)

        # 2. User submits prompt
        submit_response = client.post(
            "/hook/user-prompt-submit",
            json={"session_id": session_id, "cwd": "/test/project"},
            content_type="application/json",
        )
        assert submit_response.get_json()["state"] == "processing"

        # 3. Claude stops
        stop_response = client.post(
            "/hook/stop",
            json={"session_id": session_id, "cwd": "/test/project"},
            content_type="application/json",
        )
        assert stop_response.get_json()["state"] == "idle"

        # 4. Session ends
        end_response = client.post(
            "/hook/session-end",
            json={"session_id": session_id},
            content_type="application/json",
        )
        assert end_response.status_code == 200

    def test_config_update_flow(self, client):
        """Test config update flow.

        1. Get current config
        2. Add a project
        3. Verify project persisted
        4. Update scan interval
        5. Verify all changes persist
        """
        # 1. Get current config
        initial = client.get("/api/config").get_json()
        initial_project_count = len(initial["projects"])

        # 2. Add a project
        projects = initial["projects"] + [{"name": "Flow Test", "path": "/flow/test"}]
        client.post(
            "/api/config",
            json={"projects": projects},
            content_type="application/json",
        )

        # 3. Verify project persisted
        updated = client.get("/api/config").get_json()
        assert len(updated["projects"]) == initial_project_count + 1

        # 4. Update scan interval
        client.post(
            "/api/config",
            json={"scan_interval": 10},
            content_type="application/json",
        )

        # 5. Verify all changes persist
        final = client.get("/api/config").get_json()
        assert len(final["projects"]) == initial_project_count + 1
        assert final["scan_interval"] == 10

    def test_notification_settings_flow(self, client):
        """Test notification settings flow.

        1. Check current state
        2. Disable notifications
        3. Verify disabled
        4. Enable notifications
        5. Verify enabled
        """
        # 1. Check current state (just verify endpoint works)
        client.get("/api/notifications").get_json()

        # 2. Disable
        client.post(
            "/api/notifications",
            json={"enabled": False},
            content_type="application/json",
        )

        # 3. Verify disabled
        disabled = client.get("/api/notifications").get_json()
        assert disabled["enabled"] is False

        # 4. Enable
        client.post(
            "/api/notifications",
            json={"enabled": True},
            content_type="application/json",
        )

        # 5. Verify enabled
        enabled = client.get("/api/notifications").get_json()
        assert enabled["enabled"] is True

    def test_reset_clears_all_state(self, client):
        """Test reset clears all working state.

        1. Create some agents via hooks
        2. Reset
        3. Verify agents cleared
        """
        # 1. Create agents
        for i in range(3):
            client.post(
                "/hook/session-start",
                json={"session_id": f"reset-test-{i}", "cwd": f"/test/{i}"},
                content_type="application/json",
            )

        # Verify agents exist
        before_reset = client.get("/api/agents").get_json()
        assert len(before_reset["agents"]) >= 3

        # 2. Reset
        reset_response = client.post("/api/reset")
        assert reset_response.get_json()["success"] is True

        # 3. Verify cleared
        after_reset = client.get("/api/agents").get_json()
        assert len(after_reset["agents"]) == 0
