"""Tests for HookReceiver service."""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.models.project import Project
from src.models.task import TaskState
from src.services.agent_store import AgentStore
from src.services.event_bus import EventBus
from src.services.hook_receiver import (
    HookEvent,
    HookEventType,
    HookReceiver,
    HookResult,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for state files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def store(temp_dir):
    """Create an AgentStore with temporary storage."""
    return AgentStore(data_dir=temp_dir)


@pytest.fixture
def event_bus():
    """Create a fresh EventBus for testing."""
    return EventBus()


@pytest.fixture
def receiver(store, event_bus):
    """Create a HookReceiver for testing."""
    return HookReceiver(
        agent_store=store,
        event_bus=event_bus,
        governing_agent=None,
    )


@pytest.fixture
def project():
    """Create a test project."""
    return Project(
        id="proj-1",
        name="test-project",
        path="/home/user/test-project",
    )


class TestHookEventType:
    """Tests for HookEventType enum."""

    def test_all_event_types_defined(self):
        """All expected event types are defined."""
        assert HookEventType.SESSION_START.value == "session-start"
        assert HookEventType.SESSION_END.value == "session-end"
        assert HookEventType.STOP.value == "stop"
        assert HookEventType.NOTIFICATION.value == "notification"
        assert HookEventType.USER_PROMPT_SUBMIT.value == "user-prompt-submit"

    def test_event_type_from_string(self):
        """Event types can be created from strings."""
        assert HookEventType("session-start") == HookEventType.SESSION_START
        assert HookEventType("stop") == HookEventType.STOP


class TestHookEvent:
    """Tests for HookEvent dataclass."""

    def test_create_event(self):
        """HookEvent can be created with required fields."""
        event = HookEvent(
            event_type=HookEventType.SESSION_START,
            session_id="test-session-123",
        )
        assert event.session_id == "test-session-123"
        assert event.cwd == ""
        assert event.timestamp > 0

    def test_event_with_all_fields(self):
        """HookEvent can be created with all fields."""
        event = HookEvent(
            event_type=HookEventType.STOP,
            session_id="test-session",
            cwd="/home/user/project",
            timestamp=1234567890,
            data={"extra": "info"},
        )
        assert event.cwd == "/home/user/project"
        assert event.timestamp == 1234567890
        assert event.data == {"extra": "info"}


class TestHookResult:
    """Tests for HookResult dataclass."""

    def test_success_result(self):
        """HookResult can indicate success."""
        result = HookResult(
            success=True,
            agent_id="agent-123",
            new_state=TaskState.PROCESSING,
            message="OK",
        )
        assert result.success is True
        assert result.agent_id == "agent-123"
        assert result.new_state == TaskState.PROCESSING

    def test_failure_result(self):
        """HookResult can indicate failure."""
        result = HookResult(
            success=False,
            message="Unknown event type",
        )
        assert result.success is False
        assert result.agent_id is None


class TestSessionStart:
    """Tests for session_start event processing."""

    def test_session_start_creates_agent(self, receiver, store):
        """session_start creates a new agent when none exists."""
        result = receiver.process_event(
            event_type="session-start",
            session_id="new-session-123",
            cwd="/home/user/project",
        )

        assert result.success is True
        assert result.agent_id is not None
        assert result.new_state == TaskState.IDLE

        # Verify agent was created
        agent = store.get_agent(result.agent_id)
        assert agent is not None
        assert agent.session_name == "project"

    def test_session_start_correlates_existing_agent(self, receiver, store, project):
        """session_start correlates to existing agent by project path."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="wezterm-pane-1",
            session_name="test-session",
            project_id="proj-1",
        )

        result = receiver.process_event(
            event_type="session-start",
            session_id="claude-session-456",
            cwd="/home/user/test-project",  # Matches project.path
        )

        assert result.success is True
        assert result.agent_id == agent.id

    def test_session_start_emits_event(self, receiver, event_bus):
        """session_start emits SSE event."""
        events = []
        event_bus.subscribe("hook_session_start", lambda e: events.append(e))

        receiver.process_event(
            event_type="session-start",
            session_id="new-session-123",
            cwd="/home/user/project",
        )

        assert len(events) == 1
        assert events[0].data["session_id"] == "new-session-123"


class TestSessionEnd:
    """Tests for session_end event processing."""

    def test_session_end_removes_mapping(self, receiver, store):  # noqa: ARG002
        """session_end removes session mapping."""
        # First create a session
        receiver.process_event(
            event_type="session-start",
            session_id="session-to-end",
            cwd="/home/user/project",
        )

        # Then end it
        result = receiver.process_event(
            event_type="session-end",
            session_id="session-to-end",
        )

        assert result.success is True
        # Session should no longer be mapped
        assert receiver._session_map.get("session-to-end") is None

    def test_session_end_unknown_session(self, receiver):
        """session_end handles unknown session gracefully."""
        result = receiver.process_event(
            event_type="session-end",
            session_id="unknown-session",
        )

        assert result.success is True
        assert "not tracked" in result.message.lower()

    def test_session_end_emits_event(self, receiver, event_bus):
        """session_end emits SSE event for tracked session."""
        events = []
        event_bus.subscribe("hook_session_end", lambda e: events.append(e))

        # Create then end session
        receiver.process_event(
            event_type="session-start",
            session_id="session-123",
            cwd="/project",
        )
        receiver.process_event(
            event_type="session-end",
            session_id="session-123",
        )

        assert len(events) == 1
        assert events[0].data["session_id"] == "session-123"


class TestStop:
    """Tests for stop event processing (turn completion)."""

    def test_stop_transitions_to_idle(self, receiver, store):
        """stop event transitions agent to IDLE state."""
        # Create session and simulate a processing state
        result = receiver.process_event(
            event_type="session-start",
            session_id="active-session",
            cwd="/project",
        )

        # Get the agent via the result (which has the agent_id)
        agent = store.get_agent(result.agent_id)
        task = store.create_task(agent.id)
        task.state = TaskState.PROCESSING
        store.update_task(task)

        # Process stop event
        stop_result = receiver.process_event(
            event_type="stop",
            session_id="active-session",
        )

        assert stop_result.success is True
        assert stop_result.new_state == TaskState.IDLE

    def test_stop_unknown_session(self, receiver):
        """stop handles unknown session gracefully."""
        result = receiver.process_event(
            event_type="stop",
            session_id="unknown-session",
        )

        assert result.success is True
        assert "not tracked" in result.message.lower()

    def test_stop_emits_event(self, receiver, event_bus):
        """stop emits SSE event."""
        events = []
        event_bus.subscribe("hook_stop", lambda e: events.append(e))

        receiver.process_event(
            event_type="session-start",
            session_id="session-123",
            cwd="/project",
        )
        receiver.process_event(
            event_type="stop",
            session_id="session-123",
        )

        assert len(events) == 1
        assert events[0].data["session_id"] == "session-123"


class TestUserPromptSubmit:
    """Tests for user_prompt_submit event processing."""

    def test_user_prompt_submit_transitions_to_processing(self, receiver, store):  # noqa: ARG002
        """user_prompt_submit transitions agent to PROCESSING state."""
        receiver.process_event(
            event_type="session-start",
            session_id="session-123",
            cwd="/project",
        )

        result = receiver.process_event(
            event_type="user-prompt-submit",
            session_id="session-123",
        )

        assert result.success is True
        assert result.new_state == TaskState.PROCESSING

    def test_user_prompt_submit_unknown_session(self, receiver):
        """user_prompt_submit handles unknown session gracefully."""
        result = receiver.process_event(
            event_type="user-prompt-submit",
            session_id="unknown-session",
        )

        assert result.success is True
        assert "not tracked" in result.message.lower()

    def test_user_prompt_submit_emits_event(self, receiver, event_bus):
        """user_prompt_submit emits SSE event."""
        events = []
        event_bus.subscribe("hook_user_prompt_submit", lambda e: events.append(e))

        receiver.process_event(
            event_type="session-start",
            session_id="session-123",
            cwd="/project",
        )
        receiver.process_event(
            event_type="user-prompt-submit",
            session_id="session-123",
        )

        assert len(events) == 1


class TestNotification:
    """Tests for notification event processing."""

    def test_notification_updates_timestamp(self, receiver):
        """notification event updates last event time."""
        receiver.process_event(
            event_type="session-start",
            session_id="session-123",
            cwd="/project",
        )

        old_time = receiver._last_event_time

        time.sleep(0.01)  # Small delay

        receiver.process_event(
            event_type="notification",
            session_id="session-123",
        )

        assert receiver._last_event_time > old_time

    def test_notification_emits_event(self, receiver, event_bus):
        """notification emits SSE event."""
        events = []
        event_bus.subscribe("hook_notification", lambda e: events.append(e))

        receiver.process_event(
            event_type="session-start",
            session_id="session-123",
            cwd="/project",
        )
        receiver.process_event(
            event_type="notification",
            session_id="session-123",
        )

        assert len(events) == 1


class TestUnknownEventType:
    """Tests for unknown event type handling."""

    def test_unknown_event_type_returns_failure(self, receiver):
        """Unknown event types are rejected gracefully."""
        result = receiver.process_event(
            event_type="unknown-event-type",
            session_id="session-123",
        )

        assert result.success is False
        assert "unknown" in result.message.lower()


class TestSessionCorrelation:
    """Tests for session correlation logic."""

    def test_correlate_by_exact_path_match(self, receiver, store, project):
        """Session is correlated by exact project path match."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="wezterm-pane-1",
            session_name="test",
            project_id="proj-1",
        )

        result = receiver.process_event(
            event_type="session-start",
            session_id="new-claude-session",
            cwd="/home/user/test-project",
        )

        assert result.agent_id == agent.id

    def test_correlate_handles_trailing_slash(self, receiver, store, project):
        """Session correlation handles trailing slashes."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="wezterm-pane-1",
            session_name="test",
            project_id="proj-1",
        )

        result = receiver.process_event(
            event_type="session-start",
            session_id="new-claude-session",
            cwd="/home/user/test-project/",  # Note trailing slash
        )

        assert result.agent_id == agent.id

    def test_correlate_creates_new_agent_no_match(self, receiver, store, project):
        """New agent is created when no project path matches."""
        store.add_project(project)

        result = receiver.process_event(
            event_type="session-start",
            session_id="new-claude-session",
            cwd="/home/user/different-project",
        )

        assert result.success is True
        assert result.agent_id is not None
        # Should be a new agent, not the project's agent
        agents = store.list_agents()
        assert len(agents) == 1  # Only the new one

    def test_same_session_id_returns_same_agent(self, receiver, store):  # noqa: ARG002
        """Same session ID always returns the same agent."""
        result1 = receiver.process_event(
            event_type="session-start",
            session_id="session-abc",
            cwd="/project",
        )

        result2 = receiver.process_event(
            event_type="session-start",
            session_id="session-abc",
            cwd="/project",
        )

        assert result1.agent_id == result2.agent_id


class TestActivityTracking:
    """Tests for hook activity tracking."""

    def test_event_count_increments(self, receiver):
        """Event count increments with each event."""
        assert receiver._event_count == 0

        receiver.process_event(
            event_type="session-start",
            session_id="s1",
            cwd="/p",
        )
        assert receiver._event_count == 1

        receiver.process_event(
            event_type="stop",
            session_id="s1",
        )
        assert receiver._event_count == 2

    def test_last_event_time_updates(self, receiver):
        """Last event time is updated on each event."""
        assert receiver._last_event_time == 0

        receiver.process_event(
            event_type="session-start",
            session_id="s1",
            cwd="/p",
        )

        assert receiver._last_event_time > 0

    def test_get_status_returns_metrics(self, receiver):
        """get_status returns activity metrics."""
        receiver.process_event(
            event_type="session-start",
            session_id="s1",
            cwd="/p",
        )

        status = receiver.get_status()

        assert status["active"] is True
        assert status["event_count"] == 1
        assert status["tracked_sessions"] == 1
        assert status["seconds_since_last_event"] is not None


class TestGoverningAgentIntegration:
    """Tests for GoverningAgent integration."""

    def test_governing_agent_notified_on_event(self, store, event_bus):
        """GoverningAgent.record_hook_event is called on each event."""
        mock_governing = MagicMock()
        receiver = HookReceiver(
            agent_store=store,
            event_bus=event_bus,
            governing_agent=mock_governing,
        )

        receiver.process_event(
            event_type="session-start",
            session_id="s1",
            cwd="/p",
        )

        mock_governing.record_hook_event.assert_called_once()

    def test_set_governing_agent_late_binding(self, receiver):
        """GoverningAgent can be set after construction."""
        mock_governing = MagicMock()
        receiver.set_governing_agent(mock_governing)

        receiver.process_event(
            event_type="session-start",
            session_id="s1",
            cwd="/p",
        )

        mock_governing.record_hook_event.assert_called_once()
