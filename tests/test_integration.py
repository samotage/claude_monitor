"""End-to-end integration tests for Claude Headspace.

These tests verify that all components work together correctly,
testing the full flow from the Flask app through services.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.app import create_app
from src.models import TaskState
from src.services import AgentStore, EventBus
from src.services.task_state_machine import TaskStateMachine, TransitionTrigger


class TestFullApplicationFlow:
    """Test the complete application flow."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_file(self, temp_dir):
        """Create a minimal config file."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(
            """
projects:
  - name: test-project
    path: /tmp/test-project

scan_interval: 1
terminal_backend: wezterm
notifications:
  enabled: false
"""
        )
        return str(config_path)

    @pytest.fixture
    def app(self, config_file, temp_dir):
        """Create the Flask application."""
        app = create_app(config_file)
        # Replace agent_store with fresh one using temp dir
        app.extensions["agent_store"] = AgentStore(data_dir=temp_dir)
        app.config["TESTING"] = True
        yield app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return app.test_client()

    def test_app_creates_all_services(self, app):
        """Application factory creates all required services."""
        assert "config" in app.extensions
        assert "config_service" in app.extensions
        assert "agent_store" in app.extensions
        assert "event_bus" in app.extensions
        assert "inference_service" in app.extensions
        assert "state_interpreter" in app.extensions
        assert "notification_service" in app.extensions
        assert "terminal_backend" in app.extensions
        assert "governing_agent" in app.extensions

    def test_services_are_wired_correctly(self, app):
        """Services are properly wired together."""
        governing_agent = app.extensions["governing_agent"]
        event_bus = app.extensions["event_bus"]

        # Verify GoverningAgent has dependencies (not checking identity since we replace store)
        assert governing_agent._store is not None
        assert governing_agent._event_bus is event_bus

    def test_dashboard_loads(self, client):
        """Main dashboard loads successfully."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Claude Headspace" in response.data or b"html" in response.data

    def test_agents_endpoint_empty(self, client):
        """Agents endpoint returns empty list initially."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "agents" in data
        assert data["agents"] == []

    def test_legacy_sessions_endpoint(self, client):
        """Legacy sessions endpoint works for backward compatibility."""
        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "sessions" in data
        assert "projects" in data


class TestAgentLifecycle:
    """Test the full agent lifecycle."""

    @pytest.fixture
    def store(self):
        """Create an AgentStore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentStore(data_dir=tmpdir)
            yield store

    def test_agent_creation(self, store):
        """Test creating an agent."""
        agent = store.create_agent(
            terminal_session_id="pane-1",
            session_name="test-session",
            project_id="test-project",
        )
        assert agent.id is not None
        assert agent.session_name == "test-session"

        # Agent starts with no task
        task = store.get_current_task(agent.id)
        assert task is None

    def test_task_creation(self, store):
        """Test creating a task for an agent."""
        agent = store.create_agent(
            terminal_session_id="pane-2",
            session_name="task-test",
        )
        task = store.create_task(agent_id=agent.id)
        assert task.state == TaskState.IDLE
        assert store.get_current_task(agent.id) is not None

    def test_task_state_transitions(self, store):
        """Test task state transitions using TaskStateMachine."""
        agent = store.create_agent(
            terminal_session_id="pane-3",
            session_name="transition-test",
        )
        task = store.create_task(agent_id=agent.id)
        state_machine = TaskStateMachine()

        # IDLE -> COMMANDED
        result = state_machine.transition(
            task, TaskState.COMMANDED, TransitionTrigger.USER_PRESSED_ENTER
        )
        assert result.success
        assert task.state == TaskState.COMMANDED
        store.update_task(task)

        # COMMANDED -> PROCESSING
        result = state_machine.transition(task, TaskState.PROCESSING, TransitionTrigger.LLM_STARTED)
        assert result.success
        assert task.state == TaskState.PROCESSING
        store.update_task(task)

        # PROCESSING -> AWAITING_INPUT
        result = state_machine.transition(
            task, TaskState.AWAITING_INPUT, TransitionTrigger.LLM_ASKED_QUESTION
        )
        assert result.success
        assert task.state == TaskState.AWAITING_INPUT
        store.update_task(task)

        # AWAITING_INPUT -> PROCESSING (user responds)
        result = state_machine.transition(
            task, TaskState.PROCESSING, TransitionTrigger.USER_RESPONDED
        )
        assert result.success
        assert task.state == TaskState.PROCESSING
        store.update_task(task)

        # PROCESSING -> COMPLETE
        result = state_machine.transition(task, TaskState.COMPLETE, TransitionTrigger.LLM_FINISHED)
        assert result.success
        assert task.state == TaskState.COMPLETE
        store.update_task(task)

        # COMPLETE -> IDLE (new task)
        result = state_machine.transition(task, TaskState.IDLE, TransitionTrigger.NEW_TASK_STARTED)
        assert result.success
        assert task.state == TaskState.IDLE

    def test_agent_persistence(self, store):
        """Test that agents persist across store instances."""
        agent = store.create_agent(
            terminal_session_id="pane-persist",
            session_name="persist-test",
            project_id="test-project",
        )
        agent_id = agent.id

        # Force save
        store._save_state()

        # Create new store with same directory
        store2 = AgentStore(data_dir=store.data_dir)

        # Agent should exist
        loaded_agent = store2.get_agent(agent_id)
        assert loaded_agent is not None
        assert loaded_agent.session_name == "persist-test"

    def test_events_emitted_on_agent_create(self, store):
        """Test that events are emitted when agents are created."""
        events = []

        def on_event(data):
            events.append(data)

        store.subscribe("agent_created", on_event)

        store.create_agent(
            terminal_session_id="pane-event",
            session_name="event-test",
        )

        assert len(events) == 1
        assert "agent_id" in events[0]


class TestSSEEvents:
    """Test Server-Sent Events functionality."""

    @pytest.fixture
    def event_bus(self):
        """Create an EventBus."""
        return EventBus()

    def test_emit_and_subscribe(self, event_bus):
        """Test basic emit and subscribe."""
        received = []

        def handler(event):
            received.append(event)

        event_bus.subscribe("test_event", handler)
        event_bus.emit("test_event", {"key": "value"})

        assert len(received) == 1
        # Event is an Event object
        assert received[0].event_type == "test_event"
        assert received[0].data["key"] == "value"

    def test_event_has_correct_properties(self, event_bus):
        """Test emitted events have correct properties."""
        received = []

        def handler(event):
            received.append(event)

        event_bus.subscribe("state_changed", handler)
        event_bus.emit("state_changed", {"agent_id": "123"})

        assert len(received) == 1
        event = received[0]
        assert hasattr(event, "event_type")
        assert hasattr(event, "data")
        assert hasattr(event, "id")


class TestConfigMigration:
    """Test configuration migration from legacy format."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_legacy_config_migrates(self, temp_dir):
        """Legacy config format is migrated to new format."""
        from src.services.config_service import ConfigService

        config_path = temp_dir / "config.yaml"
        config_path.write_text(
            """
projects:
  - name: old-project
    path: /path/to/project
    tmux: true

scan_interval: 5
terminal_backend: tmux

openrouter:
  api_key: test-key
  model: anthropic/claude-3-haiku

headspace:
  enabled: true
"""
        )

        service = ConfigService(str(config_path))
        config = service.get_config()

        assert len(config.projects) == 1
        assert config.projects[0].name == "old-project"
        assert config.scan_interval == 5
        assert config.terminal_backend == "tmux"

    def test_new_config_format_works(self, temp_dir):
        """New config format loads correctly."""
        from src.services.config_service import ConfigService

        config_path = temp_dir / "config.yaml"
        config_path.write_text(
            """
projects:
  - name: new-project
    path: /path/to/project

scan_interval: 2
terminal_backend: wezterm

wezterm:
  workspace: test-workspace
  full_scrollback: true

inference:
  detect_state: anthropic/claude-3-haiku
  full_priority: anthropic/claude-3-sonnet

notifications:
  enabled: true
"""
        )

        service = ConfigService(str(config_path))
        config = service.get_config()

        assert config.terminal_backend == "wezterm"
        assert config.wezterm.workspace == "test-workspace"
        assert config.inference.detect_state == "anthropic/claude-3-haiku"
        assert config.notifications.enabled is True


class TestNotificationIntegration:
    """Test notification service integration."""

    def test_notification_service_enabled_state(self):
        """Notification service respects enabled state."""
        from src.services.notification_service import NotificationService

        service = NotificationService()
        service.enabled = False

        result = service.notify_custom("Test", "Test message")
        assert result is False

    def test_notification_service_mock_send(self):
        """Notification service can be mocked for testing."""
        from src.services.notification_service import NotificationService

        service = NotificationService()
        service.enabled = True

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = service.notify_custom("Test", "Test message")
            assert result is True
            mock_run.assert_called_once()


class TestTaskStateMachineIntegration:
    """Integration tests for task state transitions."""

    @pytest.fixture
    def store(self):
        """Create an AgentStore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AgentStore(data_dir=tmpdir)
            yield store

    @pytest.fixture
    def state_machine(self):
        """Create a TaskStateMachine."""
        return TaskStateMachine()

    def test_full_state_cycle(self, store, state_machine):
        """Test a complete task state cycle."""
        agent = store.create_agent(
            terminal_session_id="pane-cycle",
            session_name="cycle-test",
        )

        task = store.create_task(agent_id=agent.id)
        assert task.state == TaskState.IDLE

        # User sends command
        state_machine.transition(task, TaskState.COMMANDED, TransitionTrigger.USER_PRESSED_ENTER)
        assert task.state == TaskState.COMMANDED

        # Agent starts processing
        state_machine.transition(task, TaskState.PROCESSING, TransitionTrigger.LLM_STARTED)
        assert task.state == TaskState.PROCESSING

        # Agent completes -> COMPLETE
        state_machine.transition(task, TaskState.COMPLETE, TransitionTrigger.LLM_FINISHED)
        assert task.state == TaskState.COMPLETE

        # COMPLETE -> IDLE (new task)
        state_machine.transition(task, TaskState.IDLE, TransitionTrigger.NEW_TASK_STARTED)
        assert task.state == TaskState.IDLE

    def test_input_cycle(self, store, state_machine):
        """Test state cycle with input needed."""
        agent = store.create_agent(
            terminal_session_id="pane-input",
            session_name="input-test",
        )
        task = store.create_task(agent_id=agent.id)

        # Get to processing state
        state_machine.transition(task, TaskState.COMMANDED, TransitionTrigger.USER_PRESSED_ENTER)
        state_machine.transition(task, TaskState.PROCESSING, TransitionTrigger.LLM_STARTED)

        # Agent needs input
        state_machine.transition(
            task, TaskState.AWAITING_INPUT, TransitionTrigger.LLM_ASKED_QUESTION
        )
        assert task.state == TaskState.AWAITING_INPUT

        # User responds
        state_machine.transition(task, TaskState.PROCESSING, TransitionTrigger.USER_RESPONDED)
        assert task.state == TaskState.PROCESSING

        # Agent completes -> COMPLETE
        state_machine.transition(task, TaskState.COMPLETE, TransitionTrigger.LLM_FINISHED)
        assert task.state == TaskState.COMPLETE

        # COMPLETE -> IDLE (new task)
        state_machine.transition(task, TaskState.IDLE, TransitionTrigger.NEW_TASK_STARTED)
        assert task.state == TaskState.IDLE


class TestRouteIntegration:
    """Integration tests for API routes."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_file(self, temp_dir):
        """Create a minimal config file."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(
            """
projects:
  - name: test-project
    path: /tmp/test-project

scan_interval: 1
terminal_backend: wezterm
notifications:
  enabled: false
"""
        )
        return str(config_path)

    @pytest.fixture
    def app(self, config_file, temp_dir):
        """Create the Flask application."""
        app = create_app(config_file)
        # Replace agent_store with fresh one using temp dir
        app.extensions["agent_store"] = AgentStore(data_dir=temp_dir)
        app.config["TESTING"] = True
        yield app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return app.test_client()

    def test_create_and_list_agents(self, client, app):
        """Test creating an agent via store and listing via API."""
        # Use the governing agent's store (the one routes actually use)
        governing_agent = app.extensions["governing_agent"]
        store = governing_agent._store

        # Create an agent directly
        agent = store.create_agent(
            terminal_session_id="pane-api",
            session_name="api-test",
        )

        # List via API
        response = client.get("/api/agents")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert len(data["agents"]) >= 1
        # Find our agent in the list
        our_agent = next((a for a in data["agents"] if a["id"] == agent.id), None)
        assert our_agent is not None
        assert our_agent["session_name"] == "api-test"

    def test_notifications_endpoint(self, client):
        """Test notifications endpoint."""
        response = client.get("/api/notifications")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert "enabled" in data
