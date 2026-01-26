"""Tests for hooks API routes."""

import json
import tempfile
from pathlib import Path

import pytest
from flask import Flask

from src.models.config import AppConfig, HookConfig
from src.routes.hooks import hooks_bp
from src.services.agent_store import AgentStore
from src.services.event_bus import EventBus
from src.services.hook_receiver import HookReceiver


@pytest.fixture
def temp_dir():
    """Create a temporary directory for state files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def app(temp_dir):
    """Create a test Flask application."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    # Create test services
    store = AgentStore(data_dir=temp_dir)
    event_bus = EventBus()
    config = AppConfig()

    hook_receiver = HookReceiver(
        agent_store=store,
        event_bus=event_bus,
    )

    # Register services in extensions
    app.extensions["agent_store"] = store
    app.extensions["event_bus"] = event_bus
    app.extensions["config"] = config
    app.extensions["hook_receiver"] = hook_receiver

    # Register blueprint
    app.register_blueprint(hooks_bp, url_prefix="/hook")

    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestEndpointAvailability:
    """Tests that all hook endpoints exist and accept POST."""

    def test_session_start_endpoint_exists(self, client):
        """POST /hook/session-start is available."""
        response = client.post(
            "/hook/session-start",
            data=json.dumps({"session_id": "test"}),
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_session_end_endpoint_exists(self, client):
        """POST /hook/session-end is available."""
        response = client.post(
            "/hook/session-end",
            data=json.dumps({"session_id": "test"}),
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_stop_endpoint_exists(self, client):
        """POST /hook/stop is available."""
        response = client.post(
            "/hook/stop",
            data=json.dumps({"session_id": "test"}),
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_notification_endpoint_exists(self, client):
        """POST /hook/notification is available."""
        response = client.post(
            "/hook/notification",
            data=json.dumps({"session_id": "test"}),
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_user_prompt_submit_endpoint_exists(self, client):
        """POST /hook/user-prompt-submit is available."""
        response = client.post(
            "/hook/user-prompt-submit",
            data=json.dumps({"session_id": "test"}),
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_status_endpoint_exists(self, client):
        """GET /hook/status is available."""
        response = client.get("/hook/status")
        assert response.status_code == 200


class TestRequestHandling:
    """Tests for request parsing and handling."""

    def test_valid_payload_returns_ok(self, client):
        """Valid JSON payload returns status ok."""
        response = client.post(
            "/hook/session-start",
            data=json.dumps(
                {
                    "session_id": "test-123",
                    "event": "session-start",
                    "cwd": "/home/user/project",
                    "timestamp": 1234567890,
                }
            ),
            content_type="application/json",
        )

        data = json.loads(response.data)
        assert response.status_code == 200
        assert data["status"] == "ok"

    def test_missing_session_id_still_returns_200(self, client):
        """Missing session_id still returns 200 (graceful)."""
        response = client.post(
            "/hook/session-start",
            data=json.dumps({"event": "session-start"}),
            content_type="application/json",
        )

        # Must not block Claude Code, so always return 200
        assert response.status_code == 200

    def test_invalid_json_still_returns_200(self, client):
        """Invalid JSON still returns 200 (graceful)."""
        response = client.post(
            "/hook/session-start",
            data="not valid json",
            content_type="application/json",
        )

        # Must not block Claude Code
        assert response.status_code == 200

    def test_empty_body_still_returns_200(self, client):
        """Empty body still returns 200 (graceful)."""
        response = client.post(
            "/hook/session-start",
            data="",
            content_type="application/json",
        )

        assert response.status_code == 200


class TestResponseFormat:
    """Tests for response format."""

    def test_response_includes_status(self, client):
        """Response includes status field."""
        response = client.post(
            "/hook/session-start",
            data=json.dumps({"session_id": "test"}),
            content_type="application/json",
        )

        data = json.loads(response.data)
        assert "status" in data

    def test_response_includes_agent_id_when_correlated(self, client):
        """Response includes agent_id when session is correlated."""
        response = client.post(
            "/hook/session-start",
            data=json.dumps(
                {
                    "session_id": "test-123",
                    "cwd": "/project",
                }
            ),
            content_type="application/json",
        )

        data = json.loads(response.data)
        assert "agent_id" in data
        assert data["agent_id"] is not None

    def test_response_includes_state_on_state_change(self, client):
        """Response includes new state when state changes."""
        # Start session first
        client.post(
            "/hook/session-start",
            data=json.dumps({"session_id": "test", "cwd": "/p"}),
            content_type="application/json",
        )

        # Submit prompt
        response = client.post(
            "/hook/user-prompt-submit",
            data=json.dumps({"session_id": "test"}),
            content_type="application/json",
        )

        data = json.loads(response.data)
        assert "state" in data
        assert data["state"] == "processing"


class TestStatusEndpoint:
    """Tests for GET /hook/status endpoint."""

    def test_status_returns_enabled(self, client):
        """Status includes whether hooks are enabled."""
        response = client.get("/hook/status")
        data = json.loads(response.data)

        assert "enabled" in data
        assert data["enabled"] is True

    def test_status_returns_activity_info(self, client):
        """Status includes activity information."""
        # Send an event first
        client.post(
            "/hook/session-start",
            data=json.dumps({"session_id": "test", "cwd": "/p"}),
            content_type="application/json",
        )

        response = client.get("/hook/status")
        data = json.loads(response.data)

        assert "active" in data
        assert "event_count" in data
        assert data["event_count"] >= 1


class TestHooksDisabled:
    """Tests for when hooks are disabled in config."""

    @pytest.fixture
    def disabled_app(self, temp_dir):
        """Create app with hooks disabled."""
        app = Flask(__name__)
        app.config["TESTING"] = True

        # Create config with hooks disabled
        config = AppConfig(
            hooks=HookConfig(enabled=False),
        )

        store = AgentStore(data_dir=temp_dir)
        event_bus = EventBus()
        hook_receiver = HookReceiver(agent_store=store, event_bus=event_bus)

        app.extensions["agent_store"] = store
        app.extensions["event_bus"] = event_bus
        app.extensions["config"] = config
        app.extensions["hook_receiver"] = hook_receiver

        app.register_blueprint(hooks_bp, url_prefix="/hook")
        return app

    def test_hooks_disabled_returns_disabled_status(self, disabled_app):
        """Hooks return disabled status when config disabled."""
        client = disabled_app.test_client()

        response = client.post(
            "/hook/session-start",
            data=json.dumps({"session_id": "test"}),
            content_type="application/json",
        )

        data = json.loads(response.data)
        assert data["status"] == "disabled"

    def test_status_shows_disabled(self, disabled_app):
        """Status endpoint shows hooks are disabled."""
        client = disabled_app.test_client()

        response = client.get("/hook/status")
        data = json.loads(response.data)

        assert data["enabled"] is False


class TestCatchallEndpoint:
    """Tests for the catch-all endpoint for unknown event types."""

    def test_unknown_event_type_accepted(self, client):
        """Unknown event types are accepted (for forward compatibility)."""
        response = client.post(
            "/hook/future-event-type",
            data=json.dumps({"session_id": "test"}),
            content_type="application/json",
        )

        assert response.status_code == 200

    def test_unknown_event_type_returns_ok(self, client):
        """Unknown event types return ok status."""
        response = client.post(
            "/hook/future-event-type",
            data=json.dumps({"session_id": "test"}),
            content_type="application/json",
        )

        data = json.loads(response.data)
        assert data["status"] == "ok"


class TestIntegration:
    """Integration tests for hook event flow."""

    def test_full_session_lifecycle(self, client):
        """Test complete session lifecycle via hooks."""
        session_id = "lifecycle-test-session"

        # 1. Session start
        response = client.post(
            "/hook/session-start",
            data=json.dumps(
                {
                    "session_id": session_id,
                    "cwd": "/project",
                }
            ),
            content_type="application/json",
        )
        data = json.loads(response.data)
        assert data["status"] == "ok"
        assert data["agent_id"] is not None

        # 2. User submits prompt
        response = client.post(
            "/hook/user-prompt-submit",
            data=json.dumps({"session_id": session_id}),
            content_type="application/json",
        )
        data = json.loads(response.data)
        assert data["state"] == "processing"

        # 3. Claude finishes (stop)
        response = client.post(
            "/hook/stop",
            data=json.dumps({"session_id": session_id}),
            content_type="application/json",
        )
        data = json.loads(response.data)
        assert data["state"] == "idle"

        # 4. Session end
        response = client.post(
            "/hook/session-end",
            data=json.dumps({"session_id": session_id}),
            content_type="application/json",
        )
        data = json.loads(response.data)
        assert data["status"] == "ok"

    def test_multiple_sessions(self, client):
        """Multiple sessions can be tracked simultaneously."""
        sessions = ["session-a", "session-b", "session-c"]

        for sid in sessions:
            response = client.post(
                "/hook/session-start",
                data=json.dumps({"session_id": sid, "cwd": f"/{sid}"}),
                content_type="application/json",
            )
            assert json.loads(response.data)["status"] == "ok"

        # Check status shows all sessions
        response = client.get("/hook/status")
        data = json.loads(response.data)
        assert data["tracked_sessions"] == 3
