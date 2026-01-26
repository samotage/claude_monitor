"""Tests for logging routes."""

from unittest.mock import patch

import pytest
from flask import Flask

from src.routes import register_blueprints


@pytest.fixture
def app():
    """Create test Flask application."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_blueprints(app)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestOpenRouterLogs:
    """Tests for OpenRouter log routes."""

    def test_get_openrouter_logs_empty(self, client):
        """get_openrouter_logs returns empty list when no logs."""
        with patch("src.routes.logging.read_openrouter_logs", return_value=[]):
            response = client.get("/api/logs/openrouter")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["logs"] == []
        assert data["count"] == 0

    def test_get_openrouter_logs_with_data(self, client):
        """get_openrouter_logs returns log entries."""
        mock_logs = [
            {
                "id": "123",
                "timestamp": "2025-01-26T10:00:00Z",
                "model": "claude-3-haiku",
                "success": True,
            },
            {
                "id": "124",
                "timestamp": "2025-01-26T09:00:00Z",
                "model": "claude-3-haiku",
                "success": False,
            },
        ]
        with patch("src.routes.logging.read_openrouter_logs", return_value=mock_logs):
            response = client.get("/api/logs/openrouter")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["logs"]) == 2
        assert data["count"] == 2

    def test_get_openrouter_logs_with_since(self, client):
        """get_openrouter_logs filters by since timestamp."""
        mock_logs = [{"id": "123", "timestamp": "2025-01-26T10:00:00Z"}]
        with patch("src.routes.logging.get_logs_since", return_value=mock_logs) as mock_fn:
            response = client.get("/api/logs/openrouter?since=2025-01-26T09:00:00Z")

        assert response.status_code == 200
        mock_fn.assert_called_once_with("2025-01-26T09:00:00Z")

    def test_get_openrouter_logs_with_search(self, client):
        """get_openrouter_logs applies search filter."""
        mock_logs = [{"id": "123", "model": "claude-3-haiku"}]
        with (
            patch("src.routes.logging.read_openrouter_logs", return_value=mock_logs),
            patch("src.routes.logging.search_logs", return_value=mock_logs) as mock_search,
        ):
            response = client.get("/api/logs/openrouter?search=haiku")

        assert response.status_code == 200
        mock_search.assert_called_once_with("haiku", mock_logs)

    def test_get_openrouter_stats(self, client):
        """get_openrouter_stats returns statistics."""
        mock_stats = {
            "total_calls": 10,
            "successful_calls": 8,
            "failed_calls": 2,
            "total_cost": 0.05,
        }
        with patch("src.routes.logging.get_log_stats", return_value=mock_stats):
            response = client.get("/api/logs/openrouter/stats")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["stats"]["total_calls"] == 10


class TestTerminalLogs:
    """Tests for terminal log routes."""

    def test_get_terminal_logs_empty(self, client):
        """get_terminal_logs returns empty list when no logs."""
        with patch("src.routes.logging.read_terminal_logs", return_value=[]):
            response = client.get("/api/logs/terminal")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["logs"] == []
        assert data["count"] == 0

    def test_get_terminal_logs_with_data(self, client):
        """get_terminal_logs returns log entries."""
        mock_logs = [
            {
                "id": "123",
                "timestamp": "2025-01-26T10:00:00Z",
                "session_id": "project1",
                "backend": "wezterm",
            },
        ]
        with patch("src.routes.logging.read_terminal_logs", return_value=mock_logs):
            response = client.get("/api/logs/terminal")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["logs"]) == 1

    def test_get_terminal_logs_with_backend_filter(self, client):
        """get_terminal_logs filters by backend."""
        with patch("src.routes.logging.read_terminal_logs", return_value=[]) as mock_fn:
            response = client.get("/api/logs/terminal?backend=wezterm")

        assert response.status_code == 200
        mock_fn.assert_called_once_with(backend="wezterm")

    def test_get_terminal_logs_with_session_filter(self, client):
        """get_terminal_logs filters by session_id."""
        with (
            patch("src.routes.logging.read_terminal_logs", return_value=[]),
            patch("src.routes.logging.search_terminal_logs", return_value=[]) as mock_search,
        ):
            response = client.get("/api/logs/terminal?session_id=project1")

        assert response.status_code == 200
        mock_search.assert_called_once()

    def test_clear_terminal_logs_success(self, client):
        """clear_logs clears all terminal logs."""
        with patch("src.routes.logging.clear_terminal_logs", return_value=True):
            response = client.delete("/api/logs/terminal")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "cleared" in data["message"]

    def test_clear_terminal_logs_failure(self, client):
        """clear_logs handles failure."""
        with patch("src.routes.logging.clear_terminal_logs", return_value=False):
            response = client.delete("/api/logs/terminal")

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False

    def test_get_terminal_stats(self, client):
        """get_terminal_stats returns statistics."""
        mock_stats = {
            "total_entries": 100,
            "send_count": 50,
            "capture_count": 50,
            "unique_sessions": 3,
        }
        with patch("src.routes.logging.get_terminal_log_stats", return_value=mock_stats):
            response = client.get("/api/logs/terminal/stats")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["stats"]["total_entries"] == 100


class TestDebugLogging:
    """Tests for debug logging routes."""

    def test_get_debug_state(self, client):
        """get_debug_state returns current debug state."""
        with patch("src.routes.logging.get_debug_logging", return_value=False):
            response = client.get("/api/logs/terminal/debug")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["debug_enabled"] is False

    def test_set_debug_state_enable(self, client):
        """set_debug_state enables debug logging."""
        with (
            patch("src.routes.logging.set_debug_logging") as mock_set,
            patch("src.routes.logging.get_debug_logging", return_value=True),
            patch("config.load_config", return_value={}),
            patch("config.save_config"),
        ):
            response = client.post(
                "/api/logs/terminal/debug",
                json={"enabled": True},
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["debug_enabled"] is True
        mock_set.assert_called_once_with(True)

    def test_set_debug_state_disable(self, client):
        """set_debug_state disables debug logging."""
        with (
            patch("src.routes.logging.set_debug_logging") as mock_set,
            patch("src.routes.logging.get_debug_logging", return_value=False),
            patch("config.load_config", return_value={"terminal_logging": {}}),
            patch("config.save_config"),
        ):
            response = client.post(
                "/api/logs/terminal/debug",
                json={"enabled": False},
            )

        assert response.status_code == 200
        mock_set.assert_called_once_with(False)
