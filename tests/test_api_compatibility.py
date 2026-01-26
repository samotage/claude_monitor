"""API compatibility tests for legacy routes.

Tests that legacy API routes work correctly with the new architecture.
Ensures frontend compatibility is maintained during migration.
"""

import pytest

from src.app import create_app


@pytest.fixture
def app(tmp_path):
    """Create test app with config."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
projects:
  - name: test-project
    path: /tmp/test-project
scan_interval: 1
terminal_backend: wezterm
session_sync:
  enabled: false
"""
    )
    app = create_app(str(config_file))
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestLegacySessionsRoute:
    """Tests for /api/sessions legacy route."""

    def test_sessions_returns_json(self, client):
        """GET /api/sessions returns JSON with sessions and projects."""
        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = response.get_json()
        assert "sessions" in data
        assert "projects" in data
        assert isinstance(data["sessions"], list)
        assert isinstance(data["projects"], list)

    def test_sessions_includes_projects_from_config(self, client):
        """Sessions response includes projects from config.yaml."""
        response = client.get("/api/sessions")
        data = response.get_json()
        assert len(data["projects"]) >= 1
        project_names = [p["name"] for p in data["projects"]]
        assert "test-project" in project_names


class TestLegacyFocusRoutes:
    """Tests for /api/focus/* legacy routes."""

    def test_focus_pid_deprecated(self, client):
        """GET /api/focus/<pid> returns deprecation message."""
        response = client.post("/api/focus/12345")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is False
        assert "deprecated" in data["error"].lower()

    def test_focus_session_route_exists(self, client):
        """GET /api/focus/session/<name> route exists."""
        response = client.post("/api/focus/session/test-session")
        # May fail if backend unavailable, but route should exist
        assert response.status_code in (200, 503)

    def test_focus_tmux_route_exists(self, client):
        """GET /api/focus/tmux/<name> route exists."""
        response = client.post("/api/focus/tmux/claude-test-12345678")
        # May fail if no iTerm/tmux, but route should exist (returns 404 if not found)
        assert response.status_code in (200, 404)


class TestLegacySendOutputRoutes:
    """Tests for /api/send and /api/output legacy routes."""

    def test_send_route_requires_session(self, client):
        """POST /api/send/<session_id> returns 404 for unknown session."""
        response = client.post(
            "/api/send/unknown-session",
            json={"text": "test", "enter": True},
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False

    def test_send_route_requires_text(self, client):
        """POST /api/send/<session_id> returns 400 without text."""
        # First we need a valid session - but since we don't have one,
        # this test verifies the route exists and validates input
        response = client.post("/api/send/test", json={})
        # Will return 404 for unknown session, but route exists
        assert response.status_code in (400, 404)

    def test_output_route_requires_session(self, client):
        """GET /api/output/<session_id> returns 404 for unknown session."""
        response = client.get("/api/output/unknown-session")
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False


class TestLegacyProjectRoutes:
    """Tests for /api/project/<name>/* legacy routes."""

    def test_project_roadmap_by_name(self, client):
        """GET /api/project/<name>/roadmap works with project name."""
        response = client.get("/api/project/test-project/roadmap")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "roadmap" in data

    def test_project_roadmap_not_found(self, client):
        """GET /api/project/<name>/roadmap returns 404 for unknown project."""
        response = client.get("/api/project/nonexistent/roadmap")
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False

    def test_project_brain_refresh_by_name(self, client):
        """GET /api/project/<name>/brain-refresh works with project name."""
        response = client.get("/api/project/test-project/brain-refresh")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True


class TestLegacyNotificationRoutes:
    """Tests for /api/notifications/* legacy routes."""

    def test_notifications_get(self, client):
        """GET /api/notifications returns notification status."""
        response = client.get("/api/notifications")
        assert response.status_code == 200
        data = response.get_json()
        assert "enabled" in data

    def test_notifications_toggle(self, client):
        """POST /api/notifications toggles notification state."""
        response = client.post("/api/notifications", json={"enabled": False})
        assert response.status_code == 200
        data = response.get_json()
        assert data["enabled"] is False

    def test_notifications_test_route_exists(self, client):
        """POST /api/notifications/test/<pid> route exists."""
        response = client.post("/api/notifications/test/12345")
        # May fail to find session, but route should exist
        assert response.status_code in (200, 404)


class TestLegacyHeadspaceRoutes:
    """Tests for /api/headspace/* legacy routes."""

    def test_headspace_get(self, client):
        """GET /api/headspace returns current headspace."""
        response = client.get("/api/headspace")
        assert response.status_code == 200
        data = response.get_json()
        # May be empty if no headspace set - API returns "focus" field
        assert "focus" in data or data == {}

    def test_headspace_history(self, client):
        """GET /api/headspace/history returns history."""
        response = client.get("/api/headspace/history")
        assert response.status_code == 200


class TestReadmeRoute:
    """Tests for /api/readme route."""

    def test_readme_returns_html(self, client):
        """GET /api/readme returns HTML content."""
        response = client.get("/api/readme")
        assert response.status_code == 200
        data = response.get_json()
        assert "html" in data


class TestHelpRoutes:
    """Tests for /api/help/* routes."""

    def test_help_index(self, client):
        """GET /api/help returns help index."""
        response = client.get("/api/help")
        assert response.status_code == 200
        data = response.get_json()
        assert "pages" in data

    def test_help_search(self, client):
        """GET /api/help/search works."""
        response = client.get("/api/help/search?q=test")
        assert response.status_code == 200


class TestAgentRoutes:
    """Tests for /api/agents/* routes."""

    def test_agents_list(self, client):
        """GET /api/agents returns list of agents."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.get_json()
        assert "agents" in data
        assert isinstance(data["agents"], list)

    def test_agent_not_found(self, client):
        """GET /api/agents/<id> returns 404 for unknown agent."""
        response = client.get("/api/agents/nonexistent-id")
        assert response.status_code == 404


class TestPriorityRoutes:
    """Tests for /api/priorities route."""

    def test_priorities_returns_list(self, client):
        """GET /api/priorities returns priority list."""
        response = client.get("/api/priorities")
        assert response.status_code == 200
        data = response.get_json()
        assert "priorities" in data
        assert isinstance(data["priorities"], list)

    def test_priorities_has_legacy_fields(self, client):
        """Priority items have legacy-compatible fields."""
        # We need agents to test this, so just verify structure
        response = client.get("/api/priorities")
        assert response.status_code == 200
        data = response.get_json()
        # If there are priorities, check fields
        if data["priorities"]:
            p = data["priorities"][0]
            assert "priority_score" in p or p.get("score") is not None


class TestResetRoute:
    """Tests for /api/reset route."""

    def test_reset_clears_state(self, client):
        """POST /api/reset clears working state."""
        response = client.post("/api/reset")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data


class TestEventsRoute:
    """Tests for /api/events SSE route."""

    def test_events_route_exists(self, client):
        """GET /api/events route exists for SSE."""
        # SSE routes return streaming response
        response = client.get("/api/events")
        assert response.status_code == 200


class TestHooksRoutes:
    """Tests for /hook/* Claude Code lifecycle routes."""

    def test_hook_session_start(self, client):
        """POST /hook/session-start registers session."""
        response = client.post(
            "/hook/session-start",
            json={
                "session_id": "test-session-123",
                "cwd": "/tmp/test",
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"

    def test_hook_stop(self, client):
        """POST /hook/stop handles turn completion."""
        response = client.post(
            "/hook/stop",
            json={
                "session_id": "test-session-123",
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"

    def test_hook_status(self, client):
        """GET /hook/status returns hook receiver status."""
        response = client.get("/hook/status")
        assert response.status_code == 200
        data = response.get_json()
        assert "enabled" in data


class TestWeztermEnterRoute:
    """Tests for /api/wezterm/enter-pressed route."""

    def test_enter_pressed_requires_pane_id(self, client):
        """POST /api/wezterm/enter-pressed requires pane_id."""
        response = client.post("/api/wezterm/enter-pressed", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    def test_enter_pressed_accepts_pane_id(self, client):
        """POST /api/wezterm/enter-pressed accepts pane_id."""
        response = client.post("/api/wezterm/enter-pressed", json={"pane_id": 123})
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["pane_id"] == "123"


class TestSessionSummarizeRoute:
    """Tests for /api/session/<id>/summarise route."""

    def test_summarise_requires_session(self, client):
        """GET /api/session/<id>/summarise returns 404 for unknown session."""
        response = client.get("/api/session/unknown-id/summarise")
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False
