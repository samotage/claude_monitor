"""Tests for config API routes."""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.app import create_app
from src.services.config_service import reset_config_service


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the config service singleton between tests."""
    reset_config_service()
    yield
    reset_config_service()


@pytest.fixture
def app_with_config(temp_config_dir):
    """Create a Flask app with a config file."""
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(
        """
projects:
  - name: test-project
    path: /home/user/test

scan_interval: 3
terminal_backend: wezterm
port: 5050
"""
    )

    # Also create the data directory
    data_dir = temp_config_dir / "data"
    data_dir.mkdir()

    app = create_app(str(config_file))
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app_with_config):
    """Create a test client."""
    return app_with_config.test_client()


class TestGetConfig:
    """Tests for GET /api/config."""

    def test_get_config_returns_current_config(self, client):
        """GET /api/config returns current configuration."""
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.get_json()

        assert "projects" in data
        assert "scan_interval" in data
        assert "terminal_backend" in data
        assert data["scan_interval"] == 3
        assert data["terminal_backend"] == "wezterm"

    def test_get_config_includes_projects(self, client):
        """GET /api/config includes project list."""
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.get_json()

        assert len(data["projects"]) == 1
        assert data["projects"][0]["name"] == "test-project"
        assert data["projects"][0]["path"] == "/home/user/test"


class TestUpdateConfig:
    """Tests for POST /api/config."""

    def test_update_config_changes_scan_interval(self, client):
        """POST /api/config can update scan_interval."""
        response = client.post(
            "/api/config",
            json={"scan_interval": 5},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["scan_interval"] == 5

        # Verify it persists
        get_response = client.get("/api/config")
        assert get_response.get_json()["scan_interval"] == 5

    def test_update_config_adds_project(self, client):
        """POST /api/config can add a new project."""
        response = client.post(
            "/api/config",
            json={
                "projects": [
                    {"name": "test-project", "path": "/home/user/test"},
                    {"name": "new-project", "path": "/home/user/new"},
                ]
            },
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["projects"]) == 2
        assert data["projects"][1]["name"] == "new-project"

    def test_update_config_removes_project(self, client):
        """POST /api/config can remove a project."""
        response = client.post(
            "/api/config",
            json={"projects": []},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["projects"]) == 0

    def test_update_config_updates_project(self, client):
        """POST /api/config can update existing project."""
        response = client.post(
            "/api/config",
            json={
                "projects": [
                    {"name": "renamed-project", "path": "/new/path"},
                ]
            },
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["projects"][0]["name"] == "renamed-project"
        assert data["projects"][0]["path"] == "/new/path"

    def test_update_config_rejects_invalid_scan_interval(self, client):
        """POST /api/config rejects invalid scan_interval."""
        response = client.post(
            "/api/config",
            json={"scan_interval": 1000},  # Max is 60
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_update_config_preserves_unset_fields(self, client):
        """POST /api/config preserves fields not in request."""
        # Update only scan_interval
        response = client.post(
            "/api/config",
            json={"scan_interval": 5},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()

        # Projects should still be there
        assert len(data["projects"]) == 1
        assert data["projects"][0]["name"] == "test-project"

    def test_update_config_persists_to_disk(self, client, temp_config_dir):
        """POST /api/config persists changes to disk."""
        response = client.post(
            "/api/config",
            json={"scan_interval": 7},
            content_type="application/json",
        )

        assert response.status_code == 200

        # Read the config file directly
        config_file = temp_config_dir / "config.yaml"
        with open(config_file) as f:
            saved = yaml.safe_load(f)

        assert saved["scan_interval"] == 7


class TestConfigWithEmptyFile:
    """Tests for config with no initial file."""

    def test_get_config_returns_defaults(self, temp_config_dir):
        """GET /api/config returns defaults when no file exists."""
        reset_config_service()

        # Create data dir but no config file
        data_dir = temp_config_dir / "data"
        data_dir.mkdir()

        config_path = temp_config_dir / "nonexistent.yaml"
        app = create_app(str(config_path))
        app.config["TESTING"] = True
        client = app.test_client()

        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.get_json()

        # Should have defaults
        assert data["scan_interval"] == 2
        assert data["terminal_backend"] == "wezterm"
        assert data["projects"] == []
