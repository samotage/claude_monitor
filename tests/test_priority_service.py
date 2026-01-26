"""Tests for PriorityService."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.models.headspace import HeadspaceFocus
from src.models.task import TaskState
from src.services.priority_service import AgentContext, PriorityResult, PriorityService


@pytest.fixture
def mock_inference():
    """Create a mock InferenceService."""
    service = MagicMock()
    service.call.return_value = MagicMock(
        result={
            "priorities": {
                "agent-1": {"score": 85, "rationale": "High priority task"},
                "agent-2": {"score": 50, "rationale": "Medium priority"},
            }
        }
    )
    return service


@pytest.fixture
def priority_service(mock_inference):
    """Create a PriorityService with mocked inference."""
    return PriorityService(inference_service=mock_inference)


@pytest.fixture
def sample_agents():
    """Create sample agent contexts."""
    return [
        AgentContext(
            agent_id="agent-1",
            session_name="claude-project-a",
            project_id="proj-1",
            project_name="Project A",
            state=TaskState.PROCESSING,
        ),
        AgentContext(
            agent_id="agent-2",
            session_name="claude-project-b",
            project_id="proj-2",
            project_name="Project B",
            state=TaskState.IDLE,
        ),
    ]


@pytest.fixture
def sample_headspace():
    """Create a sample headspace."""
    return HeadspaceFocus(
        current_focus="Ship the billing feature by Friday",
        constraints="No breaking API changes",
    )


class TestComputeFullPriorities:
    """Tests for compute_full_priorities method."""

    def test_returns_priorities_for_all_agents(
        self, priority_service, sample_agents, sample_headspace
    ):
        """compute_full_priorities returns priorities for all agents."""
        result = priority_service.compute_full_priorities(sample_agents, sample_headspace)

        assert len(result) == 2
        assert "agent-1" in result
        assert "agent-2" in result

    def test_priorities_have_correct_fields(
        self, priority_service, sample_agents, sample_headspace
    ):
        """Priority results have correct fields."""
        result = priority_service.compute_full_priorities(sample_agents, sample_headspace)

        for agent_id, priority in result.items():
            assert isinstance(priority, PriorityResult)
            assert priority.agent_id == agent_id
            assert 0 <= priority.score <= 100
            assert priority.computed_at is not None

    def test_calls_inference_with_full_priority_purpose(
        self, priority_service, sample_agents, sample_headspace, mock_inference
    ):
        """compute_full_priorities uses FULL_PRIORITY purpose."""
        from src.models.inference import InferencePurpose

        priority_service.compute_full_priorities(sample_agents, sample_headspace)

        mock_inference.call.assert_called_once()
        call_args = mock_inference.call.call_args
        assert call_args[1]["purpose"] == InferencePurpose.FULL_PRIORITY

    def test_returns_empty_for_no_agents(self, priority_service, sample_headspace):
        """compute_full_priorities returns empty dict for no agents."""
        result = priority_service.compute_full_priorities([], sample_headspace)

        assert result == {}

    def test_uses_cache(self, priority_service, sample_agents, sample_headspace, mock_inference):
        """compute_full_priorities uses cached results."""
        # First call
        priority_service.compute_full_priorities(sample_agents, sample_headspace)
        # Second call (should use cache)
        priority_service.compute_full_priorities(sample_agents, sample_headspace)

        assert mock_inference.call.call_count == 1

    def test_force_refresh_bypasses_cache(
        self, priority_service, sample_agents, sample_headspace, mock_inference
    ):
        """force_refresh=True bypasses cache."""
        # First call
        priority_service.compute_full_priorities(sample_agents, sample_headspace)
        # Second call with force_refresh
        priority_service.compute_full_priorities(
            sample_agents, sample_headspace, force_refresh=True
        )

        assert mock_inference.call.call_count == 2

    def test_handles_inference_error(
        self, priority_service, sample_agents, sample_headspace, mock_inference
    ):
        """compute_full_priorities handles inference errors gracefully."""
        mock_inference.call.return_value = MagicMock(result={"error": "LLM error"})

        result = priority_service.compute_full_priorities(sample_agents, sample_headspace)

        # Should return default priorities for all agents
        assert len(result) == 2
        for priority in result.values():
            assert "Default priority" in (priority.rationale or "")

    def test_handles_none_headspace(self, priority_service, sample_agents, mock_inference):
        """compute_full_priorities works with None headspace."""
        result = priority_service.compute_full_priorities(sample_agents, None)

        assert len(result) == 2
        # Should have called inference with "No specific focus"
        mock_inference.call.assert_called_once()

    def test_clamps_scores_to_valid_range(
        self, priority_service, sample_agents, sample_headspace, mock_inference
    ):
        """Priority scores are clamped to 0-100."""
        mock_inference.call.return_value = MagicMock(
            result={
                "priorities": {
                    "agent-1": {"score": 150, "rationale": "Way too high"},
                    "agent-2": {"score": -10, "rationale": "Negative"},
                }
            }
        )

        result = priority_service.compute_full_priorities(sample_agents, sample_headspace)

        assert result["agent-1"].score == 100
        assert result["agent-2"].score == 0

    def test_handles_simple_score_format(
        self, priority_service, sample_agents, sample_headspace, mock_inference
    ):
        """Handles priorities as simple integers."""
        mock_inference.call.return_value = MagicMock(
            result={
                "priorities": {
                    "agent-1": 75,
                    "agent-2": 45,
                }
            }
        )

        result = priority_service.compute_full_priorities(sample_agents, sample_headspace)

        assert result["agent-1"].score == 75
        assert result["agent-2"].score == 45


class TestComputeQuickPriority:
    """Tests for compute_quick_priority method."""

    def test_returns_priority_result(self, priority_service, sample_headspace, mock_inference):
        """compute_quick_priority returns a PriorityResult."""
        mock_inference.call.return_value = MagicMock(
            result={"score": 80, "rationale": "Important work"}
        )

        agent = AgentContext(
            agent_id="agent-1",
            session_name="claude-test",
            project_id="proj-1",
            project_name="Test Project",
            state=TaskState.COMPLETE,
        )

        result = priority_service.compute_quick_priority(agent, sample_headspace)

        assert isinstance(result, PriorityResult)
        assert result.agent_id == "agent-1"
        assert result.score == 80
        assert result.rationale == "Important work"

    def test_uses_quick_priority_purpose(self, priority_service, sample_headspace, mock_inference):
        """compute_quick_priority uses QUICK_PRIORITY purpose."""
        from src.models.inference import InferencePurpose

        mock_inference.call.return_value = MagicMock(result={"score": 50, "rationale": "Default"})

        agent = AgentContext(
            agent_id="agent-1",
            session_name="claude-test",
            project_id="proj-1",
            project_name="Test Project",
            state=TaskState.COMPLETE,
        )

        priority_service.compute_quick_priority(agent, sample_headspace)

        call_args = mock_inference.call.call_args
        assert call_args[1]["purpose"] == InferencePurpose.QUICK_PRIORITY

    def test_includes_task_outcome_in_prompt(
        self, priority_service, sample_headspace, mock_inference
    ):
        """Task outcome is included in the prompt."""
        mock_inference.call.return_value = MagicMock(
            result={"score": 90, "rationale": "Just completed important work"}
        )

        agent = AgentContext(
            agent_id="agent-1",
            session_name="claude-test",
            project_id="proj-1",
            project_name="Test Project",
            state=TaskState.COMPLETE,
        )

        priority_service.compute_quick_priority(
            agent, sample_headspace, task_outcome="Fixed the critical bug"
        )

        call_args = mock_inference.call.call_args
        assert "Fixed the critical bug" in call_args[1]["user_prompt"]

    def test_handles_inference_error(self, priority_service, sample_headspace, mock_inference):
        """compute_quick_priority handles inference errors."""
        mock_inference.call.return_value = MagicMock(result={"error": "LLM error"})

        agent = AgentContext(
            agent_id="agent-1",
            session_name="claude-test",
            project_id="proj-1",
            project_name="Test Project",
            state=TaskState.COMPLETE,
        )

        result = priority_service.compute_quick_priority(agent, sample_headspace)

        assert result.score == 30  # Default for COMPLETE state
        assert "Default priority" in result.rationale


class TestInvalidateCache:
    """Tests for invalidate_cache method."""

    def test_clears_cache_on_headspace_change(
        self, priority_service, sample_agents, sample_headspace
    ):
        """Cache is cleared when headspace changes."""
        # Populate cache
        priority_service.compute_full_priorities(sample_agents, sample_headspace)
        assert priority_service.cache_size == 1

        # Invalidate with new headspace
        new_headspace = HeadspaceFocus(
            current_focus="Different focus now",
            constraints=None,
        )
        count = priority_service.invalidate_cache(new_headspace)

        assert count == 1
        assert priority_service.cache_size == 0

    def test_no_clear_if_headspace_unchanged(
        self, priority_service, sample_agents, sample_headspace
    ):
        """Cache not cleared if headspace is the same."""
        # Populate cache
        priority_service.compute_full_priorities(sample_agents, sample_headspace)

        # Invalidate with same headspace (simulating TTL check)
        count = priority_service.invalidate_cache(sample_headspace)

        assert count == 0  # No stale entries yet

    def test_clears_stale_entries(self, priority_service, sample_agents, sample_headspace):
        """Stale cache entries are cleared."""
        # Populate cache with old timestamp
        cache_key = priority_service._compute_cache_key(sample_agents, sample_headspace)
        old_time = datetime.now() - timedelta(seconds=priority_service.CACHE_TTL_SECONDS + 1)
        priority_service._cache[cache_key] = ({}, old_time)
        priority_service._last_headspace_hash = priority_service._hash_headspace(sample_headspace)

        # Invalidate
        count = priority_service.invalidate_cache(sample_headspace)

        assert count == 1
        assert priority_service.cache_size == 0


class TestDefaultPriorityForState:
    """Tests for _default_priority_for_state method."""

    def test_awaiting_input_highest(self, priority_service):
        """AWAITING_INPUT has highest default priority."""
        score = priority_service._default_priority_for_state(TaskState.AWAITING_INPUT)
        assert score == 90

    def test_complete_lowest(self, priority_service):
        """COMPLETE has lowest default priority."""
        score = priority_service._default_priority_for_state(TaskState.COMPLETE)
        assert score == 30

    def test_processing_medium(self, priority_service):
        """PROCESSING has medium priority."""
        score = priority_service._default_priority_for_state(TaskState.PROCESSING)
        assert score == 60


class TestAgentContext:
    """Tests for AgentContext dataclass."""

    def test_create_minimal(self):
        """AgentContext can be created with required fields."""
        context = AgentContext(
            agent_id="agent-1",
            session_name="claude-test",
            project_id=None,
            project_name=None,
            state=TaskState.IDLE,
        )

        assert context.agent_id == "agent-1"
        assert context.task_summary is None

    def test_create_with_all_fields(self):
        """AgentContext can be created with all fields."""
        context = AgentContext(
            agent_id="agent-1",
            session_name="claude-test",
            project_id="proj-1",
            project_name="Test Project",
            state=TaskState.PROCESSING,
            task_summary="Working on feature X",
        )

        assert context.project_name == "Test Project"
        assert context.task_summary == "Working on feature X"


class TestPriorityResult:
    """Tests for PriorityResult dataclass."""

    def test_create_with_defaults(self):
        """PriorityResult can be created with defaults."""
        result = PriorityResult(
            agent_id="agent-1",
            score=75,
        )

        assert result.agent_id == "agent-1"
        assert result.score == 75
        assert result.rationale is None
        assert result.computed_at is not None

    def test_create_with_rationale(self):
        """PriorityResult can include rationale."""
        result = PriorityResult(
            agent_id="agent-1",
            score=90,
            rationale="Aligned with current focus",
        )

        assert result.rationale == "Aligned with current focus"


class TestCacheKeyComputation:
    """Tests for cache key computation."""

    def test_same_agents_same_headspace_same_key(
        self, priority_service, sample_agents, sample_headspace
    ):
        """Same inputs produce same cache key."""
        key1 = priority_service._compute_cache_key(sample_agents, sample_headspace)
        key2 = priority_service._compute_cache_key(sample_agents, sample_headspace)

        assert key1 == key2

    def test_different_agents_different_key(self, priority_service, sample_headspace):
        """Different agents produce different cache key."""
        agents1 = [
            AgentContext(
                agent_id="agent-1",
                session_name="test",
                project_id=None,
                project_name=None,
                state=TaskState.IDLE,
            )
        ]
        agents2 = [
            AgentContext(
                agent_id="agent-2",
                session_name="test",
                project_id=None,
                project_name=None,
                state=TaskState.IDLE,
            )
        ]

        key1 = priority_service._compute_cache_key(agents1, sample_headspace)
        key2 = priority_service._compute_cache_key(agents2, sample_headspace)

        assert key1 != key2

    def test_different_headspace_different_key(self, priority_service, sample_agents):
        """Different headspace produces different cache key."""
        headspace1 = HeadspaceFocus(current_focus="Focus A", constraints=None)
        headspace2 = HeadspaceFocus(current_focus="Focus B", constraints=None)

        key1 = priority_service._compute_cache_key(sample_agents, headspace1)
        key2 = priority_service._compute_cache_key(sample_agents, headspace2)

        assert key1 != key2

    def test_none_headspace_consistent(self, priority_service, sample_agents):
        """None headspace produces consistent cache key."""
        key1 = priority_service._compute_cache_key(sample_agents, None)
        key2 = priority_service._compute_cache_key(sample_agents, None)

        assert key1 == key2

    def test_agent_state_affects_key(self, priority_service, sample_headspace):
        """Agent state change affects cache key."""
        agent1 = AgentContext(
            agent_id="agent-1",
            session_name="test",
            project_id=None,
            project_name=None,
            state=TaskState.IDLE,
        )
        agent2 = AgentContext(
            agent_id="agent-1",
            session_name="test",
            project_id=None,
            project_name=None,
            state=TaskState.PROCESSING,
        )

        key1 = priority_service._compute_cache_key([agent1], sample_headspace)
        key2 = priority_service._compute_cache_key([agent2], sample_headspace)

        assert key1 != key2
