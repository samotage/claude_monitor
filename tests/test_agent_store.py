"""Tests for AgentStore."""

import tempfile
from pathlib import Path

import pytest

from src.models.inference import InferenceCall, InferencePurpose
from src.models.project import Project
from src.models.task import TaskState
from src.models.turn import Turn, TurnType
from src.services.agent_store import AgentStore


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
def project():
    """Create a test project."""
    return Project(
        id="proj-1",
        name="test-project",
        path="/home/user/test-project",
    )


class TestHeadspaceFocus:
    """Tests for HeadspaceFocus management."""

    def test_get_headspace_initially_none(self, store):
        """Headspace is None before being set."""
        assert store.get_headspace() is None

    def test_update_headspace_creates_new(self, store):
        """update_headspace creates a new HeadspaceFocus."""
        headspace = store.update_headspace("Ship feature X")
        assert headspace.current_focus == "Ship feature X"
        assert store.get_headspace() is headspace

    def test_update_headspace_with_constraints(self, store):
        """update_headspace accepts constraints."""
        headspace = store.update_headspace("Ship feature X", "No breaking changes")
        assert headspace.constraints == "No breaking changes"

    def test_update_headspace_archives_history(self, store):
        """Updating headspace archives the previous focus."""
        store.update_headspace("First focus")
        store.update_headspace("Second focus")
        headspace = store.get_headspace()

        assert headspace.current_focus == "Second focus"
        assert len(headspace.history) == 1
        assert headspace.history[0].focus == "First focus"


class TestProjectCRUD:
    """Tests for Project CRUD operations."""

    def test_add_project(self, store, project):
        """add_project stores a project."""
        result = store.add_project(project)
        assert result.id == project.id
        assert store.get_project("proj-1") is project

    def test_get_project_not_found(self, store):
        """get_project returns None for unknown ID."""
        assert store.get_project("unknown") is None

    def test_get_project_by_name(self, store, project):
        """get_project_by_name finds project by name."""
        store.add_project(project)
        found = store.get_project_by_name("test-project")
        assert found is project

    def test_get_project_by_name_not_found(self, store):
        """get_project_by_name returns None for unknown name."""
        assert store.get_project_by_name("unknown") is None

    def test_list_projects(self, store, project):
        """list_projects returns all projects."""
        store.add_project(project)
        projects = store.list_projects()
        assert len(projects) == 1
        assert projects[0] is project

    def test_update_project(self, store, project):
        """update_project updates a project."""
        store.add_project(project)
        project.goal = "New goal"
        store.update_project(project)
        updated = store.get_project("proj-1")
        assert updated.goal == "New goal"

    def test_remove_project(self, store, project):
        """remove_project removes a project."""
        store.add_project(project)
        result = store.remove_project("proj-1")
        assert result is True
        assert store.get_project("proj-1") is None

    def test_remove_project_not_found(self, store):
        """remove_project returns False for unknown ID."""
        assert store.remove_project("unknown") is False


class TestAgentCRUD:
    """Tests for Agent CRUD operations."""

    def test_create_agent(self, store, project):
        """create_agent creates a new agent."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="wezterm-pane-123",
            session_name="claude-test-abc",
            project_id="proj-1",
        )

        assert agent.project_id == "proj-1"
        assert agent.terminal_session_id == "wezterm-pane-123"
        assert agent.session_name == "claude-test-abc"
        assert agent.id is not None

    def test_get_agent(self, store, project):
        """get_agent retrieves an agent by ID."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="wezterm-pane-123",
            session_name="claude-test-abc",
            project_id="proj-1",
        )
        retrieved = store.get_agent(agent.id)
        assert retrieved is agent

    def test_get_agent_not_found(self, store):
        """get_agent returns None for unknown ID."""
        assert store.get_agent("unknown") is None

    def test_get_agent_by_terminal_session_id(self, store, project):
        """get_agent_by_terminal_session_id finds agent by session ID."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="wezterm-pane-123",
            session_name="claude-test-abc",
            project_id="proj-1",
        )
        found = store.get_agent_by_terminal_session_id("wezterm-pane-123")
        assert found is agent

    def test_get_agent_by_terminal_session_id_not_found(self, store):
        """get_agent_by_terminal_session_id returns None for unknown session."""
        assert store.get_agent_by_terminal_session_id("unknown") is None

    def test_get_agents_by_project(self, store, project):
        """get_agents_by_project returns all agents for a project."""
        store.add_project(project)
        agent1 = store.create_agent(
            terminal_session_id="pane-1",
            session_name="claude-test-1",
            project_id="proj-1",
        )
        agent2 = store.create_agent(
            terminal_session_id="pane-2",
            session_name="claude-test-2",
            project_id="proj-1",
        )

        agents = store.get_agents_by_project("proj-1")
        assert len(agents) == 2
        assert agent1 in agents
        assert agent2 in agents

    def test_list_agents(self, store, project):
        """list_agents returns all agents."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1",
            session_name="claude-test-abc",
            project_id="proj-1",
        )
        agents = store.list_agents()
        assert len(agents) == 1
        assert agents[0] is agent

    def test_update_agent(self, store, project):
        """update_agent updates an agent."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1",
            session_name="claude-test-abc",
            project_id="proj-1",
        )
        agent.terminal_session_id = "pane-2"
        store.update_agent(agent)
        updated = store.get_agent(agent.id)
        assert updated.terminal_session_id == "pane-2"

    def test_remove_agent(self, store, project):
        """remove_agent removes an agent."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        result = store.remove_agent(agent.id)
        assert result is True
        assert store.get_agent(agent.id) is None

    def test_remove_agent_not_found(self, store):
        """remove_agent returns False for unknown ID."""
        assert store.remove_agent("unknown") is False

    def test_remove_agent_removes_tasks(self, store, project):
        """remove_agent removes associated tasks."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)

        store.remove_agent(agent.id)
        assert store.get_task(task.id) is None


class TestTaskCRUD:
    """Tests for Task CRUD operations."""

    def test_create_task(self, store, project):
        """create_task creates a new task."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)

        assert task.agent_id == agent.id
        assert task.state == TaskState.IDLE
        assert agent.current_task_id == task.id

    def test_get_task(self, store, project):
        """get_task retrieves a task by ID."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)
        retrieved = store.get_task(task.id)
        assert retrieved is task

    def test_get_task_not_found(self, store):
        """get_task returns None for unknown ID."""
        assert store.get_task("unknown") is None

    def test_get_current_task(self, store, project):
        """get_current_task returns the agent's current task."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)
        current = store.get_current_task(agent.id)
        assert current is task

    def test_get_current_task_no_task(self, store, project):
        """get_current_task returns None if no task."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        assert store.get_current_task(agent.id) is None

    def test_get_active_tasks(self, store, project):
        """get_active_tasks returns non-idle/complete tasks."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)
        task.state = TaskState.PROCESSING
        store.update_task(task)

        active = store.get_active_tasks()
        assert len(active) == 1
        assert active[0] is task

    def test_get_active_tasks_excludes_complete(self, store, project):
        """get_active_tasks excludes COMPLETE tasks."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)
        task.state = TaskState.COMPLETE
        store.update_task(task)

        assert store.get_active_tasks() == []

    def test_list_tasks(self, store, project):
        """list_tasks returns all tasks."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)
        tasks = store.list_tasks()
        assert len(tasks) == 1
        assert tasks[0] is task

    def test_update_task_syncs_agent_state(self, store, project):
        """update_task syncs the agent's state."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)

        task.state = TaskState.PROCESSING
        store.update_task(task)

        assert agent.get_state() == TaskState.PROCESSING

    def test_remove_task(self, store, project):
        """remove_task removes a task."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)

        result = store.remove_task(task.id)
        assert result is True
        assert store.get_task(task.id) is None
        assert agent.current_task_id is None

    def test_remove_task_not_found(self, store):
        """remove_task returns False for unknown ID."""
        assert store.remove_task("unknown") is False


class TestTurnCRUD:
    """Tests for Turn CRUD operations."""

    def test_create_turn(self, store, project):
        """create_turn adds a turn to a task."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)

        turn = Turn(
            id="",  # Will be assigned
            task_id=task.id,
            type=TurnType.USER_COMMAND,
            content="Add authentication",
        )
        created = store.create_turn(task.id, turn)

        assert created.id != ""
        assert created in store.get_turns_for_task(task.id)

    def test_get_turn(self, store, project):
        """get_turn retrieves a turn by ID."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)

        turn = Turn(
            id="turn-1",
            task_id=task.id,
            type=TurnType.USER_COMMAND,
            content="Test",
        )
        store.create_turn(task.id, turn)
        retrieved = store.get_turn("turn-1")
        assert retrieved is turn

    def test_get_turn_not_found(self, store):
        """get_turn returns None for unknown ID."""
        assert store.get_turn("unknown") is None

    def test_get_turns_for_task(self, store, project):
        """get_turns_for_task returns all turns for a task."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)

        turn1 = Turn(id="t1", task_id=task.id, type=TurnType.USER_COMMAND, content="A")
        turn2 = Turn(id="t2", task_id=task.id, type=TurnType.AGENT_RESPONSE, content="B")
        store.create_turn(task.id, turn1)
        store.create_turn(task.id, turn2)

        turns = store.get_turns_for_task(task.id)
        assert len(turns) == 2

    def test_get_turns_for_task_not_found(self, store):
        """get_turns_for_task returns empty list for unknown task."""
        assert store.get_turns_for_task("unknown") == []

    def test_update_turn(self, store, project):
        """update_turn updates a turn."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)

        turn = Turn(id="t1", task_id=task.id, type=TurnType.USER_COMMAND, content="A")
        store.create_turn(task.id, turn)

        turn.content = "Updated"
        store.update_turn(turn)
        updated = store.get_turn("t1")
        assert updated.content == "Updated"


class TestInferenceCallCRUD:
    """Tests for InferenceCall CRUD operations."""

    def test_add_inference_call(self, store):
        """add_inference_call stores an inference call."""
        call = InferenceCall(
            id="call-1",
            purpose=InferencePurpose.DETECT_STATE,
            model="anthropic/claude-3-haiku",
            input_hash="abc123",
            result={"state": "processing"},
            latency_ms=150,
        )
        result = store.add_inference_call(call)
        assert result is call
        assert store.get_inference_call("call-1") is call

    def test_add_inference_call_links_to_turn(self, store, project):
        """add_inference_call links to turn if turn_id provided."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)
        turn = Turn(id="t1", task_id=task.id, type=TurnType.USER_COMMAND, content="A")
        store.create_turn(task.id, turn)

        call = InferenceCall(
            id="call-1",
            turn_id="t1",
            purpose=InferencePurpose.SUMMARIZE_COMMAND,
            model="anthropic/claude-3-haiku",
            input_hash="abc123",
            result={"summary": "test"},
            latency_ms=100,
        )
        store.add_inference_call(call)

        updated_turn = store.get_turn("t1")
        assert "call-1" in updated_turn.inference_call_ids

    def test_get_inference_call_not_found(self, store):
        """get_inference_call returns None for unknown ID."""
        assert store.get_inference_call("unknown") is None

    def test_list_inference_calls(self, store):
        """list_inference_calls returns all calls."""
        call = InferenceCall(
            id="call-1",
            purpose=InferencePurpose.DETECT_STATE,
            model="anthropic/claude-3-haiku",
            input_hash="abc123",
            result={},
            latency_ms=100,
        )
        store.add_inference_call(call)
        calls = store.list_inference_calls()
        assert len(calls) == 1


class TestEventSystem:
    """Tests for the event subscription system."""

    def test_subscribe_and_emit(self, store):
        """Events are emitted to subscribers."""
        events = []
        store.subscribe("test_event", lambda data: events.append(data))
        store._emit("test_event", {"key": "value"})

        assert len(events) == 1
        assert events[0]["key"] == "value"
        assert events[0]["event_type"] == "test_event"

    def test_wildcard_subscriber(self, store):
        """Wildcard subscribers receive all events."""
        events = []
        store.subscribe("*", lambda data: events.append(data))
        store._emit("any_event", {"key": "value"})

        assert len(events) == 1

    def test_unsubscribe(self, store):
        """unsubscribe removes a listener."""
        events = []

        def callback(data):
            events.append(data)

        store.subscribe("test_event", callback)
        store.unsubscribe("test_event", callback)
        store._emit("test_event", {"key": "value"})

        assert len(events) == 0

    def test_headspace_change_emits_event(self, store):
        """Updating headspace emits headspace_changed event."""
        events = []
        store.subscribe("headspace_changed", lambda data: events.append(data))
        store.update_headspace("New focus")

        assert len(events) == 1
        assert "headspace" in events[0]

    def test_agent_created_emits_event(self, store, project):
        """Creating an agent emits agent_created event."""
        store.add_project(project)
        events = []
        store.subscribe("agent_created", lambda data: events.append(data))
        store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )

        assert len(events) == 1
        assert "agent_id" in events[0]

    def test_task_state_changed_emits_event(self, store, project):
        """Updating task state emits task_state_changed event."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)

        events = []
        store.subscribe("task_state_changed", lambda data: events.append(data))
        task.state = TaskState.PROCESSING
        store.update_task(task)

        assert len(events) == 1
        assert events[0]["state"] == "processing"

    def test_listener_error_doesnt_break_store(self, store):
        """Errors in listeners don't break the store."""

        def bad_listener(data):
            raise RuntimeError("Listener error")

        store.subscribe("test_event", bad_listener)
        # Should not raise
        store._emit("test_event", {"key": "value"})


class TestPersistence:
    """Tests for state persistence."""

    def test_state_persisted_on_changes(self, temp_dir):
        """State is saved to disk on changes."""
        store = AgentStore(data_dir=temp_dir)
        store.update_headspace("Test focus")

        # Create new store and verify state loaded
        store2 = AgentStore(data_dir=temp_dir)
        assert store2.get_headspace().current_focus == "Test focus"

    def test_projects_persisted(self, temp_dir, project):
        """Projects are persisted."""
        store = AgentStore(data_dir=temp_dir)
        store.add_project(project)

        store2 = AgentStore(data_dir=temp_dir)
        loaded = store2.get_project("proj-1")
        assert loaded is not None
        assert loaded.name == "test-project"

    def test_agents_persisted(self, temp_dir, project):
        """Agents are persisted."""
        store = AgentStore(data_dir=temp_dir)
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )

        store2 = AgentStore(data_dir=temp_dir)
        loaded = store2.get_agent(agent.id)
        assert loaded is not None
        assert loaded.terminal_session_id == "pane-1"

    def test_tasks_persisted(self, temp_dir, project):
        """Tasks are persisted."""
        store = AgentStore(data_dir=temp_dir)
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        task = store.create_task(agent.id)
        task.state = TaskState.PROCESSING
        store.update_task(task)

        store2 = AgentStore(data_dir=temp_dir)
        loaded = store2.get_task(task.id)
        assert loaded is not None
        assert loaded.state == TaskState.PROCESSING

    def test_clear_removes_all_state(self, store, project):
        """clear() removes all state."""
        store.add_project(project)
        agent = store.create_agent(
            terminal_session_id="pane-1", session_name="claude-test", project_id="proj-1"
        )
        store.create_task(agent.id)
        store.update_headspace("Focus")

        store.clear()

        assert store.list_projects() == []
        assert store.list_agents() == []
        assert store.list_tasks() == []
        assert store.get_headspace() is None

    def test_corrupted_state_file_handled(self, temp_dir):
        """Corrupted state file is handled gracefully."""
        state_file = temp_dir / "state.yaml"
        state_file.write_text("invalid: yaml: content: [")

        # Should not raise
        store = AgentStore(data_dir=temp_dir)
        assert store.list_projects() == []
