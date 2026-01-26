"""Tests for GoverningAgent."""

from unittest.mock import MagicMock, patch

import pytest

from src.backends.base import SessionInfo
from src.models.task import TaskState
from src.services.governing_agent import AgentSnapshot, GoverningAgent


@pytest.fixture
def mock_backend():
    """Create a mock WezTerm backend."""
    backend = MagicMock()
    backend.is_available.return_value = True
    backend.get_claude_sessions.return_value = []
    backend.get_content.return_value = "Terminal content"
    return backend


@pytest.fixture
def mock_store():
    """Create a mock AgentStore."""
    store = MagicMock()
    store.get_agent_by_terminal_session_id.return_value = None
    store.get_current_task.return_value = None
    store.get_headspace.return_value = None
    store.list_agents.return_value = []
    return store


@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus."""
    return MagicMock()


@pytest.fixture
def mock_inference():
    """Create a mock InferenceService."""
    service = MagicMock()
    service.call.return_value = MagicMock(result={"content": "Test result"})
    return service


@pytest.fixture
def mock_interpreter():
    """Create a mock StateInterpreter."""
    interpreter = MagicMock()
    interpreter.interpret.return_value = MagicMock(
        state=TaskState.IDLE,
        confidence=0.9,
    )
    return interpreter


@pytest.fixture
def mock_notifications():
    """Create a mock NotificationService."""
    service = MagicMock()
    service.notify_state_change.return_value = True
    return service


@pytest.fixture
def governing_agent(
    mock_store, mock_event_bus, mock_inference, mock_interpreter, mock_backend, mock_notifications
):
    """Create a GoverningAgent with all dependencies mocked."""
    return GoverningAgent(
        agent_store=mock_store,
        event_bus=mock_event_bus,
        inference_service=mock_inference,
        state_interpreter=mock_interpreter,
        backend=mock_backend,
        notification_service=mock_notifications,
    )


class TestGoverningAgentInit:
    """Tests for GoverningAgent initialization."""

    def test_creates_with_defaults(self):
        """GoverningAgent creates with default dependencies."""
        with (
            patch("src.services.governing_agent.AgentStore"),
            patch("src.services.governing_agent.get_event_bus"),
            patch("src.services.governing_agent.InferenceService"),
            patch("src.services.governing_agent.StateInterpreter"),
            patch("src.services.governing_agent.get_wezterm_backend"),
            patch("src.services.governing_agent.get_notification_service"),
        ):
            agent = GoverningAgent()
            assert agent is not None

    def test_accepts_custom_dependencies(
        self,
        mock_store,
        mock_event_bus,
        mock_inference,
        mock_interpreter,
        mock_backend,
        mock_notifications,
    ):
        """GoverningAgent accepts custom dependencies."""
        agent = GoverningAgent(
            agent_store=mock_store,
            event_bus=mock_event_bus,
            inference_service=mock_inference,
            state_interpreter=mock_interpreter,
            backend=mock_backend,
            notification_service=mock_notifications,
        )
        assert agent._store is mock_store
        assert agent._event_bus is mock_event_bus
        assert agent._notifications is mock_notifications


class TestStartStop:
    """Tests for start/stop functionality."""

    def test_start_begins_polling(self, governing_agent):
        """start() begins the polling loop."""
        governing_agent.start()

        assert governing_agent.is_running is True
        assert governing_agent._poll_thread is not None

        governing_agent.stop()

    def test_stop_ends_polling(self, governing_agent):
        """stop() ends the polling loop."""
        governing_agent.start()
        governing_agent.stop()

        assert governing_agent.is_running is False

    def test_start_idempotent(self, governing_agent):
        """Multiple start() calls don't create multiple threads."""
        governing_agent.start()
        thread1 = governing_agent._poll_thread

        governing_agent.start()  # Second call
        thread2 = governing_agent._poll_thread

        assert thread1 is thread2

        governing_agent.stop()


class TestPollAgents:
    """Tests for poll_agents functionality."""

    def test_poll_agents_when_backend_unavailable(self, governing_agent, mock_backend):
        """poll_agents does nothing when backend unavailable."""
        mock_backend.is_available.return_value = False

        governing_agent.poll_agents()

        mock_backend.get_claude_sessions.assert_not_called()

    def test_poll_agents_gets_sessions(self, governing_agent, mock_backend):
        """poll_agents gets Claude sessions from backend."""
        mock_backend.get_claude_sessions.return_value = []

        governing_agent.poll_agents()

        mock_backend.get_claude_sessions.assert_called_once()

    def test_poll_agents_creates_agent_for_new_session(
        self, governing_agent, mock_backend, mock_store
    ):
        """poll_agents creates agent for new session."""
        session = SessionInfo(
            session_id="pane-1",
            name="claude-test-abc1",
            pid=12345,
        )
        mock_backend.get_claude_sessions.return_value = [session]
        mock_store.get_agent_by_terminal_session_id.return_value = None

        # Mock agent creation
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_store.create_agent.return_value = mock_agent

        governing_agent.poll_agents()

        mock_store.create_agent.assert_called_once_with(
            terminal_session_id="pane-1",
            session_name="claude-test-abc1",
        )

    def test_poll_agents_interprets_terminal_content(
        self, governing_agent, mock_backend, mock_store, mock_interpreter
    ):
        """poll_agents uses interpreter for state detection."""
        session = SessionInfo(session_id="pane-1", name="claude-test-abc1")
        mock_backend.get_claude_sessions.return_value = [session]
        mock_backend.get_content.return_value = "Terminal content"

        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_store.get_agent_by_terminal_session_id.return_value = mock_agent

        governing_agent.poll_agents()

        mock_interpreter.interpret.assert_called_once_with("Terminal content")


class TestStateTransitions:
    """Tests for state transition handling."""

    def test_state_change_emits_event(
        self, governing_agent, mock_backend, mock_store, mock_interpreter, mock_event_bus
    ):
        """State changes emit task_state_changed event."""
        session = SessionInfo(session_id="pane-1", name="claude-test-abc1")
        mock_backend.get_claude_sessions.return_value = [session]

        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_store.get_agent_by_terminal_session_id.return_value = mock_agent

        mock_task = MagicMock()
        mock_task.id = "task-1"
        mock_task.state = TaskState.IDLE
        mock_store.get_current_task.return_value = mock_task

        # Simulate state change to PROCESSING
        mock_interpreter.interpret.return_value = MagicMock(
            state=TaskState.PROCESSING,
            confidence=0.95,
        )

        governing_agent.poll_agents()

        # Check event was emitted
        mock_event_bus.emit.assert_called()
        call_args = mock_event_bus.emit.call_args_list
        state_changed_calls = [c for c in call_args if c[0][0] == "task_state_changed"]
        assert len(state_changed_calls) > 0

    def test_idle_to_commanded_triggers_summarize(
        self, governing_agent, mock_store, mock_inference
    ):
        """IDLE → COMMANDED triggers SUMMARIZE_COMMAND."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_store.get_agent.return_value = mock_agent

        mock_task = MagicMock()
        mock_task.id = "task-1"
        mock_task.agent_id = "agent-1"
        mock_store.get_current_task.return_value = mock_task

        governing_agent._trigger_activity_matrix_actions(
            agent_id="agent-1",
            old_state=TaskState.IDLE,
            new_state=TaskState.COMMANDED,
            content="user command here",
        )

        # Verify SUMMARIZE_COMMAND was called
        mock_inference.call.assert_called()
        call = mock_inference.call.call_args
        assert call[1]["purpose"].value == "summarize_command"

    def test_processing_to_awaiting_triggers_classify(
        self, governing_agent, mock_store, mock_inference
    ):
        """PROCESSING → AWAITING_INPUT triggers CLASSIFY_RESPONSE."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_store.get_agent.return_value = mock_agent

        governing_agent._trigger_activity_matrix_actions(
            agent_id="agent-1",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.AWAITING_INPUT,
            content="Claude asking a question?",
        )

        # Verify CLASSIFY_RESPONSE was called
        mock_inference.call.assert_called()
        call = mock_inference.call.call_args
        assert call[1]["purpose"].value == "classify_response"

    def test_processing_to_complete_triggers_quick_priority(
        self, governing_agent, mock_store, mock_inference
    ):
        """PROCESSING → COMPLETE triggers QUICK_PRIORITY."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_agent.session_name = "claude-test"
        mock_store.get_agent.return_value = mock_agent

        mock_task = MagicMock()
        mock_task.id = "task-1"
        mock_store.get_current_task.return_value = mock_task

        governing_agent._trigger_activity_matrix_actions(
            agent_id="agent-1",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.COMPLETE,
            content="Task completed",
        )

        # Verify QUICK_PRIORITY was called
        mock_inference.call.assert_called()
        call = mock_inference.call.call_args
        assert call[1]["purpose"].value == "quick_priority"


class TestPriorityComputation:
    """Tests for priority computation."""

    def test_invalidate_priorities_sets_flag(self, governing_agent):
        """invalidate_priorities sets the stale flag."""
        governing_agent._priorities_stale = False

        governing_agent.invalidate_priorities()

        assert governing_agent._priorities_stale is True

    def test_invalidate_priorities_emits_event(self, governing_agent, mock_event_bus):
        """invalidate_priorities emits priorities_invalidated event."""
        governing_agent.invalidate_priorities()

        mock_event_bus.emit.assert_called()
        call = mock_event_bus.emit.call_args
        assert call[0][0] == "priorities_invalidated"

    def test_compute_priorities_calls_inference(self, governing_agent, mock_store, mock_inference):
        """compute_priorities triggers FULL_PRIORITY inference."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_agent.session_name = "claude-test"
        mock_agent.project_id = "proj-1"
        mock_store.list_agents.return_value = [mock_agent]

        mock_task = MagicMock()
        mock_task.state = TaskState.PROCESSING
        mock_store.get_current_task.return_value = mock_task

        mock_inference.call.return_value = MagicMock(result={"priorities": {"agent-1": 85}})

        priorities = governing_agent.compute_priorities()

        # Verify FULL_PRIORITY was called
        mock_inference.call.assert_called()
        call = mock_inference.call.call_args
        assert call[1]["purpose"].value == "full_priority"

        assert priorities == {"agent-1": 85}

    def test_compute_priorities_clears_stale_flag(self, governing_agent, mock_store):
        """compute_priorities clears the stale flag."""
        governing_agent._priorities_stale = True
        mock_store.list_agents.return_value = []

        governing_agent.compute_priorities()

        assert governing_agent._priorities_stale is False

    def test_compute_priorities_emits_event(
        self, governing_agent, mock_store, mock_event_bus, mock_inference
    ):
        """compute_priorities emits priorities_computed event."""
        # Need at least one agent for event to be emitted
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_agent.session_name = "claude-test"
        mock_agent.project_id = "proj-1"
        mock_store.list_agents.return_value = [mock_agent]

        mock_task = MagicMock()
        mock_task.state = TaskState.IDLE
        mock_store.get_current_task.return_value = mock_task

        mock_inference.call.return_value = MagicMock(result={"priorities": {"agent-1": 50}})

        governing_agent.compute_priorities()

        mock_event_bus.emit.assert_called()
        calls = [c for c in mock_event_bus.emit.call_args_list if c[0][0] == "priorities_computed"]
        assert len(calls) > 0


class TestWeztermEvents:
    """Tests for WezTerm event handling."""

    def test_handle_wezterm_event_ignores_unknown_agent(self, governing_agent, mock_store):
        """handle_wezterm_event ignores events for unknown agents."""
        mock_store.get_agent_by_terminal_session_id.return_value = None

        # Should not raise
        governing_agent.handle_wezterm_event("command_sent", "pane-1", {"command": "test"})

    def test_handle_wezterm_event_command_sent(self, governing_agent, mock_store, mock_event_bus):
        """handle_wezterm_event handles command_sent events."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_store.get_agent_by_terminal_session_id.return_value = mock_agent

        mock_task = MagicMock()
        mock_task.id = "task-1"
        mock_task.state = TaskState.IDLE
        mock_store.get_current_task.return_value = mock_task

        governing_agent.handle_wezterm_event("command_sent", "pane-1", {"command": "test command"})

        # Verify state change event was emitted
        mock_event_bus.emit.assert_called()


class TestStateChangeCallbacks:
    """Tests for state change callback registration."""

    def test_on_state_change_registers_callback(self, governing_agent):
        """on_state_change registers a callback."""
        callback = MagicMock()
        governing_agent.on_state_change(callback)

        assert callback in governing_agent._on_state_change_callbacks

    def test_callbacks_called_on_state_change(self, governing_agent, mock_store):
        """Registered callbacks are called on state change."""
        callback = MagicMock()
        governing_agent.on_state_change(callback)

        mock_task = MagicMock()
        mock_task.id = "task-1"
        mock_task.state = TaskState.IDLE  # Set actual TaskState
        mock_store.get_current_task.return_value = mock_task

        governing_agent._handle_state_transition(
            agent_id="agent-1",
            old_state=TaskState.IDLE,
            new_state=TaskState.COMMANDED,
            content="test",
            interpretation_confidence=1.0,
        )

        callback.assert_called_once_with("agent-1", TaskState.IDLE, TaskState.COMMANDED)

    def test_callback_error_doesnt_break_processing(self, governing_agent, mock_store):
        """Callback errors don't break state transition processing."""

        def bad_callback(agent_id, old_state, new_state):
            raise RuntimeError("Callback error")

        governing_agent.on_state_change(bad_callback)

        mock_task = MagicMock()
        mock_task.id = "task-1"
        mock_task.state = TaskState.IDLE  # Set actual TaskState
        mock_store.get_current_task.return_value = mock_task

        # Should not raise
        governing_agent._handle_state_transition(
            agent_id="agent-1",
            old_state=TaskState.IDLE,
            new_state=TaskState.COMMANDED,
            content="test",
            interpretation_confidence=1.0,
        )


class TestAgentSnapshot:
    """Tests for AgentSnapshot dataclass."""

    def test_snapshot_creation(self):
        """AgentSnapshot can be created with required fields."""
        snapshot = AgentSnapshot(
            agent_id="agent-1",
            session_id="pane-1",
            task_state=TaskState.IDLE,
            last_content_hash="abc123",
        )

        assert snapshot.agent_id == "agent-1"
        assert snapshot.task_state == TaskState.IDLE

    def test_snapshot_has_timestamp(self):
        """AgentSnapshot has a last_seen timestamp."""
        snapshot = AgentSnapshot(
            agent_id="agent-1",
            session_id="pane-1",
            task_state=TaskState.IDLE,
            last_content_hash="abc123",
        )

        assert snapshot.last_seen is not None


class TestProperties:
    """Tests for GoverningAgent properties."""

    def test_agent_count(self, governing_agent):
        """agent_count returns number of tracked agents."""
        governing_agent._snapshots = {
            "agent-1": MagicMock(),
            "agent-2": MagicMock(),
        }

        assert governing_agent.agent_count == 2

    def test_priorities_stale(self, governing_agent):
        """priorities_stale returns the flag value."""
        governing_agent._priorities_stale = True
        assert governing_agent.priorities_stale is True

        governing_agent._priorities_stale = False
        assert governing_agent.priorities_stale is False


class TestNotifications:
    """Tests for notification integration."""

    def test_processing_to_awaiting_sends_notification(
        self, governing_agent, mock_store, mock_notifications
    ):
        """PROCESSING → AWAITING_INPUT sends notification."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_agent.terminal_session_id = "pane-1"
        mock_agent.session_name = "claude-test"
        mock_agent.project_id = None
        mock_store.get_agent.return_value = mock_agent

        mock_task = MagicMock()
        mock_task.id = "task-1"
        mock_task.state = TaskState.PROCESSING
        mock_task.summary = "Working on feature"
        mock_task.priority_score = 75
        mock_store.get_current_task.return_value = mock_task

        governing_agent._send_state_notification(
            agent_id="agent-1",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.AWAITING_INPUT,
            current_task=mock_task,
        )

        mock_notifications.notify_state_change.assert_called_once_with(
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.AWAITING_INPUT,
            project_name=None,
            task_summary="Working on feature",
            priority_score=75,
        )

    def test_processing_to_complete_sends_notification(
        self, governing_agent, mock_store, mock_notifications
    ):
        """PROCESSING → COMPLETE sends notification."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_agent.terminal_session_id = "pane-1"
        mock_agent.session_name = "claude-test"
        mock_agent.project_id = "proj-1"
        mock_store.get_agent.return_value = mock_agent

        mock_project = MagicMock()
        mock_project.name = "test-project"
        mock_store.get_project.return_value = mock_project

        mock_task = MagicMock()
        mock_task.id = "task-1"
        mock_task.state = TaskState.PROCESSING
        mock_task.summary = None
        mock_task.priority_score = None
        mock_store.get_current_task.return_value = mock_task

        governing_agent._send_state_notification(
            agent_id="agent-1",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.COMPLETE,
            current_task=mock_task,
        )

        mock_notifications.notify_state_change.assert_called_once()
        call_kwargs = mock_notifications.notify_state_change.call_args[1]
        assert call_kwargs["project_name"] == "test-project"
        assert call_kwargs["new_state"] == TaskState.COMPLETE

    def test_notification_skipped_for_unknown_agent(
        self, governing_agent, mock_store, mock_notifications
    ):
        """Notification is skipped when agent not found."""
        mock_store.get_agent.return_value = None

        governing_agent._send_state_notification(
            agent_id="unknown",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.COMPLETE,
            current_task=None,
        )

        mock_notifications.notify_state_change.assert_not_called()

    def test_notification_integrated_in_state_transition(
        self, governing_agent, mock_store, mock_notifications
    ):
        """Notification is called during _handle_state_transition."""
        mock_agent = MagicMock()
        mock_agent.id = "agent-1"
        mock_agent.terminal_session_id = "pane-1"
        mock_agent.session_name = "claude-test"
        mock_agent.project_id = None
        mock_store.get_agent.return_value = mock_agent

        mock_task = MagicMock()
        mock_task.id = "task-1"
        mock_task.state = TaskState.PROCESSING
        mock_task.summary = None
        mock_task.priority_score = None
        mock_store.get_current_task.return_value = mock_task

        governing_agent._handle_state_transition(
            agent_id="agent-1",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.COMPLETE,
            content="task done",
            interpretation_confidence=1.0,
        )

        # Verify notification was called
        mock_notifications.notify_state_change.assert_called()
