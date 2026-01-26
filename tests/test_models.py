"""Tests for domain models."""

from datetime import datetime, timedelta

import pytest

from src.models import (
    Agent,
    AppConfig,
    HeadspaceFocus,
    HeadspaceHistoryEntry,
    InferenceCall,
    InferenceConfig,
    InferencePurpose,
    NotificationConfig,
    Project,
    ProjectConfig,
    ProjectContext,
    ProjectStatus,
    ResponseResultType,
    Roadmap,
    RoadmapItem,
    Task,
    TaskState,
    Turn,
    TurnType,
    WezTermConfig,
)


class TestHeadspaceFocus:
    """Tests for HeadspaceFocus model."""

    def test_create_headspace_focus(self):
        """Test basic HeadspaceFocus creation."""
        focus = HeadspaceFocus(current_focus="Ship billing feature by Thursday")
        assert focus.current_focus == "Ship billing feature by Thursday"
        assert focus.constraints is None
        assert focus.history == []
        assert focus.updated_at is not None

    def test_create_with_constraints(self):
        """Test HeadspaceFocus with constraints."""
        focus = HeadspaceFocus(
            current_focus="Ship billing feature",
            constraints="No breaking API changes",
        )
        assert focus.constraints == "No breaking API changes"

    def test_update_focus_archives_history(self):
        """Test that updating focus archives the previous one."""
        focus = HeadspaceFocus(current_focus="First focus")
        original_time = focus.updated_at

        focus.update_focus("Second focus", "New constraints")

        assert focus.current_focus == "Second focus"
        assert focus.constraints == "New constraints"
        assert focus.updated_at > original_time
        assert len(focus.history) == 1
        assert focus.history[0].focus == "First focus"

    def test_history_limit_50(self):
        """Test that history is limited to 50 entries."""
        focus = HeadspaceFocus(current_focus="Initial")

        # Update 55 times
        for i in range(55):
            focus.update_focus(f"Focus {i}")

        assert len(focus.history) == 50
        # Most recent should be first
        assert focus.history[0].focus == "Focus 53"


class TestHeadspaceHistoryEntry:
    """Tests for HeadspaceHistoryEntry model."""

    def test_create_history_entry(self):
        """Test basic history entry creation."""
        now = datetime.now()
        entry = HeadspaceHistoryEntry(
            focus="Old focus",
            constraints="Old constraints",
            started_at=now - timedelta(hours=1),
            ended_at=now,
        )
        assert entry.focus == "Old focus"
        assert entry.constraints == "Old constraints"


class TestProject:
    """Tests for Project and related models."""

    def test_create_project(self):
        """Test basic Project creation."""
        project = Project(
            id="proj-1",
            name="my-project",
            path="/home/user/my-project",
        )
        assert project.id == "proj-1"
        assert project.name == "my-project"
        assert project.path == "/home/user/my-project"
        assert project.goal is None
        assert project.state.status == ProjectStatus.ACTIVE

    def test_project_with_all_fields(self):
        """Test Project with all fields populated."""
        project = Project(
            id="proj-1",
            name="my-project",
            path="/home/user/my-project",
            goal="Build the best app",
            context=ProjectContext(
                tech_stack=["Python", "Flask"],
                target_users="Developers",
            ),
            roadmap=Roadmap(
                next_up=RoadmapItem(title="Add auth"),
                upcoming=["Add tests", "Add docs"],
            ),
            git_repo_path="/home/user/my-project/.git",
        )
        assert project.goal == "Build the best app"
        assert project.context.tech_stack == ["Python", "Flask"]
        assert project.roadmap.next_up.title == "Add auth"

    def test_get_git_path_defaults_to_project_path(self):
        """Test get_git_path returns project path if git_repo_path not set."""
        project = Project(id="proj-1", name="test", path="/home/user/test")
        assert project.get_git_path() == "/home/user/test"

    def test_get_git_path_returns_explicit_git_path(self):
        """Test get_git_path returns explicit git_repo_path if set."""
        project = Project(
            id="proj-1",
            name="test",
            path="/home/user/test",
            git_repo_path="/home/user/test-repo",
        )
        assert project.get_git_path() == "/home/user/test-repo"


class TestRoadmap:
    """Tests for Roadmap and RoadmapItem models."""

    def test_create_empty_roadmap(self):
        """Test empty Roadmap creation."""
        roadmap = Roadmap()
        assert roadmap.next_up is None
        assert roadmap.upcoming == []
        assert roadmap.later == []
        assert roadmap.not_now == []
        assert roadmap.recently_completed is None

    def test_create_roadmap_item(self):
        """Test RoadmapItem creation."""
        item = RoadmapItem(
            title="Add authentication",
            why="Users need secure access",
            definition_of_done="Login/logout works with tests",
        )
        assert item.title == "Add authentication"
        assert item.why == "Users need secure access"


class TestProjectStatus:
    """Tests for ProjectStatus enum."""

    def test_all_status_values(self):
        """Test all ProjectStatus enum values exist."""
        assert ProjectStatus.ACTIVE == "active"
        assert ProjectStatus.PAUSED == "paused"
        assert ProjectStatus.ARCHIVED == "archived"


class TestTaskState:
    """Tests for TaskState enum."""

    def test_all_task_states_exist(self):
        """Test all 5 TaskState values exist."""
        states = [s.value for s in TaskState]
        assert "idle" in states
        assert "commanded" in states
        assert "processing" in states
        assert "awaiting_input" in states
        assert "complete" in states
        assert len(states) == 5


class TestTask:
    """Tests for Task model."""

    def test_create_task(self):
        """Test basic Task creation."""
        task = Task(id="task-1", agent_id="agent-1")
        assert task.id == "task-1"
        assert task.agent_id == "agent-1"
        assert task.state == TaskState.IDLE
        assert task.turn_ids == []
        assert task.completed_at is None

    def test_task_with_priority(self):
        """Test Task with priority fields."""
        task = Task(
            id="task-1",
            agent_id="agent-1",
            priority_score=85,
            priority_rationale="Aligns with current headspace focus",
        )
        assert task.priority_score == 85
        assert task.priority_rationale == "Aligns with current headspace focus"

    def test_priority_score_bounds(self):
        """Test priority_score validation (0-100)."""
        # Valid
        task = Task(id="t1", agent_id="a1", priority_score=0)
        assert task.priority_score == 0

        task = Task(id="t2", agent_id="a1", priority_score=100)
        assert task.priority_score == 100

        # Invalid - below 0
        with pytest.raises(ValueError):
            Task(id="t3", agent_id="a1", priority_score=-1)

        # Invalid - above 100
        with pytest.raises(ValueError):
            Task(id="t4", agent_id="a1", priority_score=101)


class TestTurn:
    """Tests for Turn model."""

    def test_create_user_command_turn(self):
        """Test creating a user command turn."""
        turn = Turn(
            id="turn-1",
            task_id="task-1",
            type=TurnType.USER_COMMAND,
            content="Add authentication to the app",
        )
        assert turn.type == TurnType.USER_COMMAND
        assert turn.content == "Add authentication to the app"
        assert turn.result_type is None  # Only for agent responses

    def test_create_agent_response_turn(self):
        """Test creating an agent response turn with result type."""
        turn = Turn(
            id="turn-2",
            task_id="task-1",
            type=TurnType.AGENT_RESPONSE,
            content="I've added authentication. The tests pass.",
            result_type=ResponseResultType.COMPLETION,
        )
        assert turn.type == TurnType.AGENT_RESPONSE
        assert turn.result_type == ResponseResultType.COMPLETION

    def test_create_question_turn(self):
        """Test creating an agent response that asks a question."""
        turn = Turn(
            id="turn-3",
            task_id="task-1",
            type=TurnType.AGENT_RESPONSE,
            content="Should I use OAuth or JWT for authentication?",
            result_type=ResponseResultType.QUESTION,
        )
        assert turn.result_type == ResponseResultType.QUESTION


class TestTurnType:
    """Tests for TurnType enum."""

    def test_all_turn_types(self):
        """Test all TurnType values."""
        assert TurnType.USER_COMMAND == "user_command"
        assert TurnType.AGENT_RESPONSE == "agent_response"


class TestResponseResultType:
    """Tests for ResponseResultType enum."""

    def test_all_result_types(self):
        """Test all ResponseResultType values."""
        assert ResponseResultType.QUESTION == "question"
        assert ResponseResultType.COMPLETION == "completion"


class TestAgent:
    """Tests for Agent model."""

    def test_create_agent(self):
        """Test basic Agent creation."""
        agent = Agent(
            id="agent-1",
            project_id="proj-1",
            terminal_session_id="wezterm-pane-123",
            session_name="claude-test-abc",
        )
        assert agent.id == "agent-1"
        assert agent.project_id == "proj-1"
        assert agent.terminal_session_id == "wezterm-pane-123"
        assert agent.session_name == "claude-test-abc"
        assert agent.current_task_id is None

    def test_agent_state_defaults_to_idle(self):
        """Test agent state is IDLE when no current task."""
        agent = Agent(
            id="agent-1",
            project_id="proj-1",
            terminal_session_id="wezterm-pane-123",
            session_name="claude-test-abc",
        )
        assert agent.get_state() == TaskState.IDLE

    def test_agent_state_can_be_set(self):
        """Test agent state can be updated."""
        agent = Agent(
            id="agent-1",
            project_id="proj-1",
            terminal_session_id="wezterm-pane-123",
            session_name="claude-test-abc",
        )
        agent.set_state(TaskState.PROCESSING)
        assert agent.get_state() == TaskState.PROCESSING

    def test_agent_state_returns_to_idle(self):
        """Test agent state can return to IDLE."""
        agent = Agent(
            id="agent-1",
            project_id="proj-1",
            terminal_session_id="wezterm-pane-123",
            session_name="claude-test-abc",
        )
        agent.set_state(TaskState.PROCESSING)
        agent.set_state(TaskState.IDLE)
        assert agent.get_state() == TaskState.IDLE


class TestInferencePurpose:
    """Tests for InferencePurpose enum."""

    def test_all_8_purposes_exist(self):
        """Test all 8 InferencePurpose values exist."""
        purposes = [p.value for p in InferencePurpose]
        # Fast tier
        assert "detect_state" in purposes
        assert "summarize_command" in purposes
        assert "classify_response" in purposes
        assert "quick_priority" in purposes
        # Deep tier
        assert "generate_progress_narrative" in purposes
        assert "full_priority" in purposes
        assert "roadmap_analysis" in purposes
        assert "brain_reboot" in purposes
        assert len(purposes) == 8


class TestInferenceConfig:
    """Tests for InferenceConfig model."""

    def test_default_models(self):
        """Test default model assignments."""
        config = InferenceConfig()
        # Fast tier defaults to Haiku
        assert "haiku" in config.detect_state
        assert "haiku" in config.summarize_command
        # Deep tier defaults to Sonnet
        assert "sonnet" in config.full_priority
        assert "sonnet" in config.brain_reboot

    def test_get_model(self):
        """Test get_model method."""
        config = InferenceConfig()
        assert config.get_model(InferencePurpose.DETECT_STATE) == "anthropic/claude-3-haiku"
        assert config.get_model(InferencePurpose.FULL_PRIORITY) == "anthropic/claude-3-sonnet"

    def test_is_fast_tier(self):
        """Test is_fast_tier classification."""
        config = InferenceConfig()
        # Fast tier
        assert config.is_fast_tier(InferencePurpose.DETECT_STATE) is True
        assert config.is_fast_tier(InferencePurpose.SUMMARIZE_COMMAND) is True
        assert config.is_fast_tier(InferencePurpose.CLASSIFY_RESPONSE) is True
        assert config.is_fast_tier(InferencePurpose.QUICK_PRIORITY) is True
        # Deep tier
        assert config.is_fast_tier(InferencePurpose.FULL_PRIORITY) is False
        assert config.is_fast_tier(InferencePurpose.BRAIN_REBOOT) is False

    def test_custom_models(self):
        """Test custom model configuration."""
        config = InferenceConfig(
            detect_state="openai/gpt-4o-mini",
            full_priority="anthropic/claude-3-opus",
        )
        assert config.get_model(InferencePurpose.DETECT_STATE) == "openai/gpt-4o-mini"
        assert config.get_model(InferencePurpose.FULL_PRIORITY) == "anthropic/claude-3-opus"


class TestInferenceCall:
    """Tests for InferenceCall model."""

    def test_create_inference_call(self):
        """Test basic InferenceCall creation."""
        call = InferenceCall(
            id="call-1",
            turn_id="turn-1",
            purpose=InferencePurpose.DETECT_STATE,
            model="anthropic/claude-3-haiku",
            input_hash="abc123",
            result={"state": "processing"},
            latency_ms=150,
        )
        assert call.id == "call-1"
        assert call.purpose == InferencePurpose.DETECT_STATE
        assert call.result == {"state": "processing"}
        assert call.cached is False

    def test_cached_inference_call(self):
        """Test cached InferenceCall."""
        call = InferenceCall(
            id="call-2",
            purpose=InferencePurpose.SUMMARIZE_COMMAND,
            model="anthropic/claude-3-haiku",
            input_hash="def456",
            result={"summary": "Add auth"},
            latency_ms=0,
            cached=True,
        )
        assert call.cached is True
        assert call.latency_ms == 0


class TestAppConfig:
    """Tests for AppConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AppConfig()
        assert config.projects == []
        assert config.scan_interval == 2
        assert config.terminal_backend == "wezterm"
        assert config.port == 5050
        assert config.debug is False

    def test_config_with_projects(self):
        """Test configuration with projects."""
        config = AppConfig(
            projects=[
                ProjectConfig(name="proj1", path="/home/user/proj1"),
                ProjectConfig(name="proj2", path="/home/user/proj2"),
            ]
        )
        assert len(config.projects) == 2
        assert config.projects[0].name == "proj1"

    def test_scan_interval_bounds(self):
        """Test scan_interval validation (1-60)."""
        # Valid
        config = AppConfig(scan_interval=1)
        assert config.scan_interval == 1

        config = AppConfig(scan_interval=60)
        assert config.scan_interval == 60

        # Invalid
        with pytest.raises(ValueError):
            AppConfig(scan_interval=0)

        with pytest.raises(ValueError):
            AppConfig(scan_interval=61)

    def test_terminal_backend_validation(self):
        """Test terminal_backend must be wezterm or tmux."""
        config = AppConfig(terminal_backend="wezterm")
        assert config.terminal_backend == "wezterm"

        config = AppConfig(terminal_backend="tmux")
        assert config.terminal_backend == "tmux"

        with pytest.raises(ValueError):
            AppConfig(terminal_backend="iterm")

    def test_port_bounds(self):
        """Test port validation (1024-65535)."""
        config = AppConfig(port=1024)
        assert config.port == 1024

        config = AppConfig(port=65535)
        assert config.port == 65535

        with pytest.raises(ValueError):
            AppConfig(port=80)  # Below 1024

        with pytest.raises(ValueError):
            AppConfig(port=70000)  # Above 65535

    def test_nested_config(self):
        """Test nested configuration objects."""
        config = AppConfig(
            wezterm=WezTermConfig(workspace="my-workspace"),
            notifications=NotificationConfig(enabled=False),
            inference=InferenceConfig(detect_state="custom/model"),
        )
        assert config.wezterm.workspace == "my-workspace"
        assert config.notifications.enabled is False
        assert config.inference.detect_state == "custom/model"


class TestWezTermConfig:
    """Tests for WezTermConfig model."""

    def test_default_values(self):
        """Test default WezTerm configuration."""
        config = WezTermConfig()
        assert config.workspace == "claude-monitor"
        assert config.full_scrollback is True


class TestNotificationConfig:
    """Tests for NotificationConfig model."""

    def test_default_values(self):
        """Test default notification configuration."""
        config = NotificationConfig()
        assert config.enabled is True
        assert config.on_awaiting_input is True
        assert config.on_complete is True

    def test_disable_specific_notifications(self):
        """Test disabling specific notification types."""
        config = NotificationConfig(
            enabled=True,
            on_awaiting_input=False,
            on_complete=True,
        )
        assert config.on_awaiting_input is False
        assert config.on_complete is True
