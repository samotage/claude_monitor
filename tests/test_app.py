"""Tests for Flask application factory."""

import tempfile
from pathlib import Path

import pytest

from src.app import _load_dotenv, create_app


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config_file(temp_dir):
    """Create a test config file."""
    config_path = temp_dir / "config.yaml"
    config_path.write_text(
        """
projects:
  - name: test-project
    path: /tmp/test

scan_interval: 5
terminal_backend: wezterm
port: 5050
"""
    )
    return str(config_path)


class TestCreateApp:
    """Tests for create_app factory."""

    def test_create_app_returns_flask_app(self, config_file):
        """create_app returns a Flask application."""
        app = create_app(config_file)
        assert app is not None
        assert app.name == "src.app"

    def test_app_has_index_route(self, config_file):
        """App has index route."""
        app = create_app(config_file)
        client = app.test_client()

        response = client.get("/")
        assert response.status_code == 200

    def test_app_has_extensions(self, config_file):
        """App has required extensions."""
        app = create_app(config_file)

        assert "config" in app.extensions
        assert "config_service" in app.extensions
        assert "agent_store" in app.extensions
        assert "event_bus" in app.extensions
        assert "inference_service" in app.extensions
        assert "state_interpreter" in app.extensions
        assert "notification_service" in app.extensions
        assert "terminal_backend" in app.extensions
        assert "governing_agent" in app.extensions


class TestLegacyRoutes:
    """Tests for legacy compatibility routes."""

    def test_legacy_sessions_route(self, config_file):
        """Legacy /api/sessions route works."""
        app = create_app(config_file)
        client = app.test_client()

        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = response.get_json()
        assert "sessions" in data
        assert "projects" in data

    def test_legacy_focus_pid_deprecated(self, config_file):
        """Legacy /api/focus/<pid> returns deprecation message."""
        app = create_app(config_file)
        client = app.test_client()

        response = client.post("/api/focus/12345")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is False
        assert "deprecated" in data["error"].lower()

    def test_legacy_focus_session(self, config_file):
        """Legacy /api/focus/session/<name> route exists."""
        app = create_app(config_file)
        client = app.test_client()

        response = client.post("/api/focus/session/test-session")
        # May fail if backend unavailable, but route should exist
        assert response.status_code in (200, 503)


class TestLoadDotenv:
    """Tests for _load_dotenv helper."""

    def test_load_dotenv_parses_file(self, temp_dir, monkeypatch):
        """_load_dotenv parses .env file."""
        import os

        # Create .env file
        env_file = temp_dir / ".env"
        env_file.write_text(
            """
# Comment line
TEST_VAR=test_value
ANOTHER_VAR="quoted value"
"""
        )

        # Change to temp dir
        monkeypatch.chdir(temp_dir)

        # Clear any existing value
        if "TEST_VAR" in os.environ:
            del os.environ["TEST_VAR"]

        _load_dotenv()

        assert os.environ.get("TEST_VAR") == "test_value"
        assert os.environ.get("ANOTHER_VAR") == "quoted value"

    def test_load_dotenv_does_not_override(self, temp_dir, monkeypatch):
        """_load_dotenv does not override existing vars."""
        import os

        # Set existing value
        os.environ["EXISTING_VAR"] = "original"

        # Create .env file
        env_file = temp_dir / ".env"
        env_file.write_text("EXISTING_VAR=new_value\n")

        monkeypatch.chdir(temp_dir)
        _load_dotenv()

        assert os.environ.get("EXISTING_VAR") == "original"

        # Clean up
        del os.environ["EXISTING_VAR"]

    def test_load_dotenv_handles_missing_file(self, temp_dir, monkeypatch):
        """_load_dotenv handles missing .env file gracefully."""
        monkeypatch.chdir(temp_dir)

        # Should not raise
        _load_dotenv()


class TestNewAgentRoutes:
    """Tests for new agent API routes."""

    def test_agents_list_route(self, config_file):
        """GET /api/agents returns agent list."""
        app = create_app(config_file)
        client = app.test_client()

        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.get_json()
        assert "agents" in data

    def test_headspace_route(self, config_file):
        """GET /api/headspace returns headspace data."""
        app = create_app(config_file)
        client = app.test_client()

        response = client.get("/api/headspace")
        assert response.status_code == 200

    def test_notifications_route(self, config_file):
        """GET /api/notifications returns settings."""
        app = create_app(config_file)
        client = app.test_client()

        response = client.get("/api/notifications")
        assert response.status_code == 200

    def test_priorities_route(self, config_file):
        """GET /api/priorities returns priorities."""
        app = create_app(config_file)
        client = app.test_client()

        response = client.get("/api/priorities")
        assert response.status_code == 200

    def test_projects_route(self, config_file):
        """GET /api/projects returns project list."""
        app = create_app(config_file)
        client = app.test_client()

        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.get_json()
        assert "projects" in data
