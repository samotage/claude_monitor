"""Tests for Flask routes."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.models.agent import Agent
from src.models.headspace import HeadspaceFocus
from src.models.task import Task, TaskState
from src.routes import register_blueprints


@pytest.fixture
def app():
    """Create a Flask test app with all blueprints."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_blueprints(app)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_store():
    """Create a mock AgentStore."""
    store = MagicMock()

    # Default returns
    store.list_agents.return_value = []
    store.get_agent.return_value = None
    store.get_current_task.return_value = None
    store.get_headspace.return_value = None
    store.list_projects.return_value = []
    store.get_project.return_value = None

    return store


@pytest.fixture
def sample_agent():
    """Create a sample agent."""
    return Agent(
        id="agent-1",
        terminal_session_id="pane-123",
        session_name="claude-test-abc",
        project_id="proj-1",
    )


@pytest.fixture
def sample_task():
    """Create a sample task."""
    return Task(
        id="task-1",
        agent_id="agent-1",
        state=TaskState.PROCESSING,
        started_at=datetime.now(),
    )


class TestAgentRoutes:
    """Tests for agent routes."""

    def test_list_agents_empty(self, client, mock_store):
        """list_agents returns empty list when no agents."""
        with patch("src.routes.agents._get_store", return_value=mock_store):
            response = client.get("/api/agents")

        assert response.status_code == 200
        data = response.get_json()
        assert data["agents"] == []

    def test_list_agents_with_agents(self, client, mock_store, sample_agent, sample_task):
        """list_agents returns agents with their tasks."""
        mock_store.list_agents.return_value = [sample_agent]
        mock_store.get_current_task.return_value = sample_task

        with patch("src.routes.agents._get_store", return_value=mock_store):
            response = client.get("/api/agents")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["agents"]) == 1
        assert data["agents"][0]["id"] == "agent-1"
        assert data["agents"][0]["current_task"]["state"] == "processing"

    def test_get_agent_not_found(self, client, mock_store):
        """get_agent returns 404 for unknown agent."""
        with patch("src.routes.agents._get_store", return_value=mock_store):
            response = client.get("/api/agents/unknown")

        assert response.status_code == 404

    def test_get_agent_found(self, client, mock_store, sample_agent, sample_task):
        """get_agent returns agent details."""
        mock_store.get_agent.return_value = sample_agent
        mock_store.get_current_task.return_value = sample_task

        with patch("src.routes.agents._get_store", return_value=mock_store):
            response = client.get("/api/agents/agent-1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == "agent-1"
        assert data["session_name"] == "claude-test-abc"

    def test_focus_agent_not_found(self, client, mock_store):
        """focus_agent returns 404 for unknown agent."""
        with patch("src.routes.agents._get_store", return_value=mock_store):
            response = client.post("/api/agents/unknown/focus")

        assert response.status_code == 404

    def test_focus_agent_backend_unavailable(self, client, mock_store, sample_agent):
        """focus_agent returns 503 when backend unavailable."""
        mock_store.get_agent.return_value = sample_agent
        mock_backend = MagicMock()
        mock_backend.is_available.return_value = False

        with (
            patch("src.routes.agents._get_store", return_value=mock_store),
            patch("src.routes.agents.get_wezterm_backend", return_value=mock_backend),
        ):
            response = client.post("/api/agents/agent-1/focus")

        assert response.status_code == 503

    def test_focus_agent_success(self, client, mock_store, sample_agent):
        """focus_agent focuses the terminal window."""
        mock_store.get_agent.return_value = sample_agent
        mock_backend = MagicMock()
        mock_backend.is_available.return_value = True
        mock_backend.focus_pane.return_value = True

        with (
            patch("src.routes.agents._get_store", return_value=mock_store),
            patch("src.routes.agents.get_wezterm_backend", return_value=mock_backend),
        ):
            response = client.post("/api/agents/agent-1/focus")

        assert response.status_code == 200
        assert response.get_json()["status"] == "focused"

    def test_send_to_agent_no_text(self, client, mock_store, sample_agent):
        """send_to_agent returns 400 when no text provided."""
        mock_store.get_agent.return_value = sample_agent

        with patch("src.routes.agents._get_store", return_value=mock_store):
            response = client.post(
                "/api/agents/agent-1/send",
                json={},
            )

        assert response.status_code == 400


class TestHeadspaceRoutes:
    """Tests for headspace routes."""

    def test_get_headspace_none(self, client, mock_store):
        """get_headspace returns null values when no headspace."""
        with patch("src.routes.headspace._get_store", return_value=mock_store):
            response = client.get("/api/headspace")

        assert response.status_code == 200
        data = response.get_json()
        assert data["focus"] is None

    def test_get_headspace_with_value(self, client, mock_store):
        """get_headspace returns current headspace."""
        headspace = HeadspaceFocus(
            current_focus="Ship billing by Friday",
            constraints="No breaking changes",
        )
        mock_store.get_headspace.return_value = headspace

        with patch("src.routes.headspace._get_store", return_value=mock_store):
            response = client.get("/api/headspace")

        assert response.status_code == 200
        data = response.get_json()
        assert data["focus"] == "Ship billing by Friday"
        assert data["constraints"] == "No breaking changes"

    def test_update_headspace_no_focus(self, client, mock_store):
        """update_headspace returns 400 when no focus provided."""
        with patch("src.routes.headspace._get_store", return_value=mock_store):
            response = client.post("/api/headspace", json={})

        assert response.status_code == 400

    def test_update_headspace_creates_new(self, client, mock_store):
        """update_headspace creates headspace when none exists."""
        # update_headspace returns the created/updated headspace
        new_headspace = HeadspaceFocus(
            current_focus="New focus",
            constraints=None,
        )
        mock_store.update_headspace.return_value = new_headspace

        with patch("src.routes.headspace._get_store", return_value=mock_store):
            response = client.post(
                "/api/headspace",
                json={"focus": "New focus"},
            )

        assert response.status_code == 200
        mock_store.update_headspace.assert_called_once_with("New focus", None)
        data = response.get_json()
        assert data["focus"] == "New focus"

    def test_update_headspace_with_constraints(self, client, mock_store):
        """update_headspace passes constraints correctly."""
        updated_headspace = HeadspaceFocus(
            current_focus="Ship feature",
            constraints="No breaking changes",
        )
        mock_store.update_headspace.return_value = updated_headspace

        with patch("src.routes.headspace._get_store", return_value=mock_store):
            response = client.post(
                "/api/headspace",
                json={"focus": "Ship feature", "constraints": "No breaking changes"},
            )

        assert response.status_code == 200
        mock_store.update_headspace.assert_called_once_with("Ship feature", "No breaking changes")
        data = response.get_json()
        assert data["constraints"] == "No breaking changes"


class TestNotificationRoutes:
    """Tests for notification routes."""

    def test_get_notification_settings(self, client):
        """get_notification_settings returns current settings."""
        mock_service = MagicMock()
        mock_service.enabled = True

        with patch(
            "src.routes.notifications.get_notification_service",
            return_value=mock_service,
        ):
            response = client.get("/api/notifications")

        assert response.status_code == 200
        data = response.get_json()
        assert data["enabled"] is True

    def test_update_notification_settings(self, client):
        """update_notification_settings updates settings."""
        mock_service = MagicMock()
        mock_service.enabled = True

        with patch(
            "src.routes.notifications.get_notification_service",
            return_value=mock_service,
        ):
            response = client.post(
                "/api/notifications",
                json={"enabled": False},
            )

        assert response.status_code == 200
        # Check that enabled was set to False
        assert mock_service.enabled is False

    def test_update_notification_settings_missing_enabled(self, client):
        """update_notification_settings returns 400 when enabled missing."""
        response = client.post("/api/notifications", json={})
        assert response.status_code == 400

    def test_send_test_notification_success(self, client):
        """send_test_notification sends a test notification."""
        mock_service = MagicMock()
        mock_service.enabled = True
        mock_service.test_notification.return_value = True

        with patch(
            "src.routes.notifications.get_notification_service",
            return_value=mock_service,
        ):
            response = client.post(
                "/api/notifications/test",
                json={},  # Provide JSON body to avoid 415
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "sent"


class TestPriorityRoutes:
    """Tests for priority routes."""

    def test_get_priorities_empty(self, client, mock_store):
        """get_priorities returns empty list when no agents."""
        with patch("src.routes.priorities._get_store", return_value=mock_store):
            response = client.get("/api/priorities")

        assert response.status_code == 200
        data = response.get_json()
        assert data["priorities"] == []

    def test_invalidate_priorities(self, client, mock_store):
        """invalidate_priorities clears the cache."""
        mock_priority_service = MagicMock()
        mock_priority_service.invalidate_cache.return_value = 2

        with (
            patch("src.routes.priorities._get_store", return_value=mock_store),
            patch(
                "src.routes.priorities._get_priority_service",
                return_value=mock_priority_service,
            ),
        ):
            response = client.post("/api/priorities/invalidate")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "invalidated"
        assert data["entries_cleared"] == 2


class TestEventRoutes:
    """Tests for event routes."""

    def test_test_event(self, client):
        """test_event emits a test event."""
        mock_event_bus = MagicMock()

        with patch(
            "src.routes.events.get_event_bus",
            return_value=mock_event_bus,
        ):
            response = client.post("/api/events/test")

        assert response.status_code == 200
        mock_event_bus.emit.assert_called_once_with("test", {"message": "Test event from API"})


class TestProjectRoutes:
    """Tests for project routes."""

    def test_list_projects_empty(self, client, mock_store):
        """list_projects returns empty list when no projects."""
        with patch("src.routes.projects._get_store", return_value=mock_store):
            response = client.get("/api/projects")

        assert response.status_code == 200
        data = response.get_json()
        assert data["projects"] == []

    def test_get_project_not_found(self, client, mock_store):
        """get_project returns 404 for unknown project."""
        with patch("src.routes.projects._get_store", return_value=mock_store):
            response = client.get("/api/projects/unknown")

        assert response.status_code == 404

    def test_brain_refresh_not_found(self, client, mock_store):
        """brain_refresh returns 404 for unknown project."""
        with patch("src.routes.projects._get_store", return_value=mock_store):
            response = client.get("/api/projects/unknown/brain-refresh")

        assert response.status_code == 404

    def test_brain_reboot_not_found(self, client, mock_store):
        """brain_reboot returns 404 for unknown project."""
        with patch("src.routes.projects._get_store", return_value=mock_store):
            response = client.get("/api/projects/unknown/brain-reboot")

        assert response.status_code == 404

    def test_brain_reboot_returns_briefing(self, client, mock_store):
        """brain_reboot returns comprehensive briefing with all context."""
        from src.models.project import Project, ProjectContext, ProjectState, Roadmap

        project = Project(
            id="proj-1",
            name="test-project",
            path="/test/path",
            goal="Test goal",
            context=ProjectContext(tech_stack=["Python"]),
            roadmap=Roadmap(),
            state=ProjectState(),
        )
        mock_store.get_project.return_value = project
        mock_store.list_agents.return_value = []
        mock_store.get_headspace.return_value = None

        mock_git_analyzer = MagicMock()
        mock_git_analyzer.generate_progress_narrative.return_value = "Recent work summary"

        mock_inference = MagicMock()
        mock_inference.call.return_value = MagicMock(result={"content": "Generated briefing text"})

        with (
            patch("src.routes.projects._get_store", return_value=mock_store),
            patch("src.routes.projects._get_git_analyzer", return_value=mock_git_analyzer),
            patch("src.routes.projects._get_inference_service", return_value=mock_inference),
        ):
            response = client.get("/api/projects/proj-1/brain-reboot")

        assert response.status_code == 200
        data = response.get_json()
        assert "briefing" in data
        assert data["briefing"] == "Generated briefing text"
        assert data["recently_completed"] == "Recent work summary"


class TestHookEventRoutes:
    """Tests for WezTerm hook event routes."""

    def test_hook_event_missing_payload(self, client):
        """hook_event returns 400 when no JSON payload."""
        response = client.post(
            "/api/events/hook",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_hook_event_missing_event_type(self, client):
        """hook_event returns 400 when event_type missing."""
        response = client.post("/api/events/hook", json={"data": {}})
        assert response.status_code == 400

    def test_hook_event_state_changed(self, app, client, mock_store):
        """hook_event processes state_changed events."""
        # Create a mock agent
        agent = Agent(
            id="agent-1",
            terminal_session_id="pane-1",
            session_name="claude-test",
            created_at=datetime.now(),
        )
        mock_store.list_agents.return_value = [agent]

        # Set the agent_store on the app extensions
        app.extensions["agent_store"] = mock_store

        response = client.post(
            "/api/events/hook",
            json={
                "event_type": "state_changed",
                "data": {
                    "pane_id": 1,
                    "session_id": "claude-test",
                    "previous_state": "idle",
                    "current_state": "processing",
                },
                "timestamp": 1234567890,
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "received"
        assert data["event_type"] == "state_changed"

    def test_hook_event_pane_focused(self, client):
        """hook_event processes pane_focused events."""
        response = client.post(
            "/api/events/hook",
            json={
                "event_type": "pane_focused",
                "data": {
                    "pane_id": 1,
                    "session_id": "claude-test",
                },
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "received"
        assert data["event_type"] == "pane_focused"

    def test_hook_event_bell(self, client):
        """hook_event processes bell events."""
        response = client.post(
            "/api/events/hook",
            json={
                "event_type": "bell",
                "data": {
                    "pane_id": 1,
                    "session_id": "claude-test",
                },
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "received"
        assert data["event_type"] == "bell"
