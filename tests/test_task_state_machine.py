"""Tests for TaskStateMachine.

This module requires 100% test coverage as specified in the task requirements.
"""

import pytest

from src.models.task import Task, TaskState
from src.services.task_state_machine import (
    VALID_TRANSITIONS,
    InvalidTransitionError,
    TaskStateMachine,
    TransitionTrigger,
)


@pytest.fixture
def state_machine():
    """Create a TaskStateMachine instance."""
    return TaskStateMachine()


@pytest.fixture
def idle_task():
    """Create a task in IDLE state."""
    return Task(id="task-1", agent_id="agent-1", state=TaskState.IDLE)


@pytest.fixture
def commanded_task():
    """Create a task in COMMANDED state."""
    return Task(id="task-2", agent_id="agent-1", state=TaskState.COMMANDED)


@pytest.fixture
def processing_task():
    """Create a task in PROCESSING state."""
    return Task(id="task-3", agent_id="agent-1", state=TaskState.PROCESSING)


@pytest.fixture
def awaiting_input_task():
    """Create a task in AWAITING_INPUT state."""
    return Task(id="task-4", agent_id="agent-1", state=TaskState.AWAITING_INPUT)


@pytest.fixture
def complete_task():
    """Create a task in COMPLETE state."""
    return Task(id="task-5", agent_id="agent-1", state=TaskState.COMPLETE)


class TestValidTransitions:
    """Test the 6 valid state transitions."""

    def test_idle_to_commanded(self, state_machine, idle_task):
        """Test transition 1: IDLE → COMMANDED (User presses Enter)."""
        result = state_machine.transition(
            idle_task, TaskState.COMMANDED, TransitionTrigger.USER_PRESSED_ENTER
        )

        assert result.success is True
        assert result.from_state == TaskState.IDLE
        assert result.to_state == TaskState.COMMANDED
        assert result.trigger == TransitionTrigger.USER_PRESSED_ENTER
        assert idle_task.state == TaskState.COMMANDED

    def test_commanded_to_processing(self, state_machine, commanded_task):
        """Test transition 2: COMMANDED → PROCESSING (LLM starts)."""
        result = state_machine.transition(
            commanded_task, TaskState.PROCESSING, TransitionTrigger.LLM_STARTED
        )

        assert result.success is True
        assert result.from_state == TaskState.COMMANDED
        assert result.to_state == TaskState.PROCESSING
        assert result.trigger == TransitionTrigger.LLM_STARTED
        assert commanded_task.state == TaskState.PROCESSING

    def test_processing_to_awaiting_input(self, state_machine, processing_task):
        """Test transition 3: PROCESSING → AWAITING_INPUT (LLM asks question)."""
        result = state_machine.transition(
            processing_task, TaskState.AWAITING_INPUT, TransitionTrigger.LLM_ASKED_QUESTION
        )

        assert result.success is True
        assert result.from_state == TaskState.PROCESSING
        assert result.to_state == TaskState.AWAITING_INPUT
        assert result.trigger == TransitionTrigger.LLM_ASKED_QUESTION
        assert processing_task.state == TaskState.AWAITING_INPUT

    def test_processing_to_complete(self, state_machine, processing_task):
        """Test transition 4: PROCESSING → COMPLETE (LLM finishes)."""
        result = state_machine.transition(
            processing_task, TaskState.COMPLETE, TransitionTrigger.LLM_FINISHED
        )

        assert result.success is True
        assert result.from_state == TaskState.PROCESSING
        assert result.to_state == TaskState.COMPLETE
        assert result.trigger == TransitionTrigger.LLM_FINISHED
        assert processing_task.state == TaskState.COMPLETE
        # Verify completed_at is set
        assert processing_task.completed_at is not None

    def test_awaiting_input_to_processing(self, state_machine, awaiting_input_task):
        """Test transition 5: AWAITING_INPUT → PROCESSING (User responds)."""
        result = state_machine.transition(
            awaiting_input_task, TaskState.PROCESSING, TransitionTrigger.USER_RESPONDED
        )

        assert result.success is True
        assert result.from_state == TaskState.AWAITING_INPUT
        assert result.to_state == TaskState.PROCESSING
        assert result.trigger == TransitionTrigger.USER_RESPONDED
        assert awaiting_input_task.state == TaskState.PROCESSING

    def test_complete_to_idle(self, state_machine, complete_task):
        """Test transition 6: COMPLETE → IDLE (New task begins)."""
        result = state_machine.transition(
            complete_task, TaskState.IDLE, TransitionTrigger.NEW_TASK_STARTED
        )

        assert result.success is True
        assert result.from_state == TaskState.COMPLETE
        assert result.to_state == TaskState.IDLE
        assert result.trigger == TransitionTrigger.NEW_TASK_STARTED
        assert complete_task.state == TaskState.IDLE


class TestInvalidTransitions:
    """Test that invalid transitions raise errors."""

    def test_idle_to_processing_invalid(self, state_machine, idle_task):
        """Cannot go directly from IDLE to PROCESSING."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            state_machine.transition(idle_task, TaskState.PROCESSING, TransitionTrigger.LLM_STARTED)

        assert exc_info.value.from_state == TaskState.IDLE
        assert exc_info.value.to_state == TaskState.PROCESSING

    def test_idle_to_complete_invalid(self, state_machine, idle_task):
        """Cannot go directly from IDLE to COMPLETE."""
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(idle_task, TaskState.COMPLETE, TransitionTrigger.LLM_FINISHED)

    def test_idle_to_awaiting_input_invalid(self, state_machine, idle_task):
        """Cannot go directly from IDLE to AWAITING_INPUT."""
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(
                idle_task, TaskState.AWAITING_INPUT, TransitionTrigger.LLM_ASKED_QUESTION
            )

    def test_commanded_to_complete_invalid(self, state_machine, commanded_task):
        """Cannot go directly from COMMANDED to COMPLETE."""
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(
                commanded_task, TaskState.COMPLETE, TransitionTrigger.LLM_FINISHED
            )

    def test_commanded_to_awaiting_input_invalid(self, state_machine, commanded_task):
        """Cannot go directly from COMMANDED to AWAITING_INPUT."""
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(
                commanded_task, TaskState.AWAITING_INPUT, TransitionTrigger.LLM_ASKED_QUESTION
            )

    def test_processing_to_commanded_invalid(self, state_machine, processing_task):
        """Cannot go from PROCESSING to COMMANDED."""
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(
                processing_task, TaskState.COMMANDED, TransitionTrigger.USER_PRESSED_ENTER
            )

    def test_awaiting_input_to_complete_invalid(self, state_machine, awaiting_input_task):
        """Cannot go directly from AWAITING_INPUT to COMPLETE."""
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(
                awaiting_input_task, TaskState.COMPLETE, TransitionTrigger.LLM_FINISHED
            )

    def test_complete_to_processing_invalid(self, state_machine, complete_task):
        """Cannot go from COMPLETE to PROCESSING."""
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(
                complete_task, TaskState.PROCESSING, TransitionTrigger.LLM_STARTED
            )

    def test_wrong_trigger_for_valid_transition(self, state_machine, idle_task):
        """Valid transition with wrong trigger should fail."""
        with pytest.raises(InvalidTransitionError):
            # IDLE → COMMANDED requires USER_PRESSED_ENTER, not LLM_STARTED
            state_machine.transition(idle_task, TaskState.COMMANDED, TransitionTrigger.LLM_STARTED)


class TestCanTransition:
    """Test the can_transition method."""

    def test_can_transition_valid(self, state_machine, idle_task):
        """can_transition returns True for valid transitions."""
        assert state_machine.can_transition(idle_task, TaskState.COMMANDED) is True

    def test_can_transition_invalid(self, state_machine, idle_task):
        """can_transition returns False for invalid transitions."""
        # IDLE can transition to COMMANDED (polling) or PROCESSING (hooks)
        # but not to COMPLETE or AWAITING_INPUT
        assert state_machine.can_transition(idle_task, TaskState.COMPLETE) is False
        assert state_machine.can_transition(idle_task, TaskState.AWAITING_INPUT) is False

    def test_can_transition_all_states(self, state_machine):
        """Test can_transition for all state combinations."""
        for from_state in TaskState:
            task = Task(id="test", agent_id="agent-1", state=from_state)
            for to_state in TaskState:
                expected = (from_state, to_state) in VALID_TRANSITIONS
                assert state_machine.can_transition(task, to_state) == expected


class TestGetValidTransitions:
    """Test the get_valid_transitions method."""

    def test_get_valid_from_idle(self, state_machine, idle_task):
        """IDLE can transition to COMMANDED (polling) or PROCESSING (hooks)."""
        valid = state_machine.get_valid_transitions(idle_task)
        assert TaskState.COMMANDED in valid
        assert TaskState.PROCESSING in valid
        assert len(valid) == 2

    def test_get_valid_from_commanded(self, state_machine, commanded_task):
        """COMMANDED can only transition to PROCESSING."""
        valid = state_machine.get_valid_transitions(commanded_task)
        assert valid == [TaskState.PROCESSING]

    def test_get_valid_from_processing(self, state_machine, processing_task):
        """PROCESSING can transition to AWAITING_INPUT, COMPLETE, or IDLE (hooks)."""
        valid = state_machine.get_valid_transitions(processing_task)
        assert TaskState.AWAITING_INPUT in valid
        assert TaskState.COMPLETE in valid
        assert TaskState.IDLE in valid  # Hook-based transition
        assert len(valid) == 3

    def test_get_valid_from_awaiting_input(self, state_machine, awaiting_input_task):
        """AWAITING_INPUT can only transition to PROCESSING."""
        valid = state_machine.get_valid_transitions(awaiting_input_task)
        assert valid == [TaskState.PROCESSING]

    def test_get_valid_from_complete(self, state_machine, complete_task):
        """COMPLETE can only transition to IDLE."""
        valid = state_machine.get_valid_transitions(complete_task)
        assert valid == [TaskState.IDLE]


class TestGetRequiredTrigger:
    """Test the get_required_trigger method."""

    def test_get_trigger_idle_to_commanded(self, state_machine):
        """IDLE → COMMANDED requires USER_PRESSED_ENTER."""
        trigger = state_machine.get_required_trigger(TaskState.IDLE, TaskState.COMMANDED)
        assert trigger == TransitionTrigger.USER_PRESSED_ENTER

    def test_get_trigger_commanded_to_processing(self, state_machine):
        """COMMANDED → PROCESSING requires LLM_STARTED."""
        trigger = state_machine.get_required_trigger(TaskState.COMMANDED, TaskState.PROCESSING)
        assert trigger == TransitionTrigger.LLM_STARTED

    def test_get_trigger_processing_to_awaiting(self, state_machine):
        """PROCESSING → AWAITING_INPUT requires LLM_ASKED_QUESTION."""
        trigger = state_machine.get_required_trigger(TaskState.PROCESSING, TaskState.AWAITING_INPUT)
        assert trigger == TransitionTrigger.LLM_ASKED_QUESTION

    def test_get_trigger_processing_to_complete(self, state_machine):
        """PROCESSING → COMPLETE requires LLM_FINISHED."""
        trigger = state_machine.get_required_trigger(TaskState.PROCESSING, TaskState.COMPLETE)
        assert trigger == TransitionTrigger.LLM_FINISHED

    def test_get_trigger_awaiting_to_processing(self, state_machine):
        """AWAITING_INPUT → PROCESSING requires USER_RESPONDED."""
        trigger = state_machine.get_required_trigger(TaskState.AWAITING_INPUT, TaskState.PROCESSING)
        assert trigger == TransitionTrigger.USER_RESPONDED

    def test_get_trigger_complete_to_idle(self, state_machine):
        """COMPLETE → IDLE requires NEW_TASK_STARTED."""
        trigger = state_machine.get_required_trigger(TaskState.COMPLETE, TaskState.IDLE)
        assert trigger == TransitionTrigger.NEW_TASK_STARTED

    def test_get_trigger_invalid_transition(self, state_machine):
        """Invalid transition raises error."""
        with pytest.raises(InvalidTransitionError):
            state_machine.get_required_trigger(TaskState.IDLE, TaskState.COMPLETE)


class TestConvenienceMethods:
    """Test the convenience transition methods."""

    def test_transition_to_idle(self, state_machine, complete_task):
        """transition_to_idle works from COMPLETE."""
        result = state_machine.transition_to_idle(complete_task)
        assert result.success is True
        assert complete_task.state == TaskState.IDLE

    def test_transition_to_commanded(self, state_machine, idle_task):
        """transition_to_commanded works from IDLE."""
        result = state_machine.transition_to_commanded(idle_task)
        assert result.success is True
        assert idle_task.state == TaskState.COMMANDED

    def test_transition_to_processing_from_commanded(self, state_machine, commanded_task):
        """transition_to_processing works from COMMANDED."""
        result = state_machine.transition_to_processing(commanded_task)
        assert result.success is True
        assert commanded_task.state == TaskState.PROCESSING

    def test_transition_to_processing_from_awaiting(self, state_machine, awaiting_input_task):
        """transition_to_processing works from AWAITING_INPUT."""
        result = state_machine.transition_to_processing(awaiting_input_task)
        assert result.success is True
        assert awaiting_input_task.state == TaskState.PROCESSING

    def test_transition_to_processing_invalid_state(self, state_machine, idle_task):
        """transition_to_processing fails from IDLE."""
        with pytest.raises(InvalidTransitionError):
            state_machine.transition_to_processing(idle_task)

    def test_transition_to_awaiting_input(self, state_machine, processing_task):
        """transition_to_awaiting_input works from PROCESSING."""
        result = state_machine.transition_to_awaiting_input(processing_task)
        assert result.success is True
        assert processing_task.state == TaskState.AWAITING_INPUT

    def test_transition_to_complete(self, state_machine, processing_task):
        """transition_to_complete works from PROCESSING."""
        result = state_machine.transition_to_complete(processing_task)
        assert result.success is True
        assert processing_task.state == TaskState.COMPLETE
        assert processing_task.completed_at is not None


class TestTransitionResult:
    """Test TransitionResult attributes."""

    def test_result_has_timestamp(self, state_machine, idle_task):
        """TransitionResult includes timestamp."""
        result = state_machine.transition_to_commanded(idle_task)
        assert result.timestamp is not None

    def test_result_error_is_none_on_success(self, state_machine, idle_task):
        """TransitionResult.error is None on success."""
        result = state_machine.transition_to_commanded(idle_task)
        assert result.error is None


class TestFullTaskLifecycle:
    """Test complete task lifecycle through all states."""

    def test_full_lifecycle_without_question(self, state_machine):
        """Test: IDLE → COMMANDED → PROCESSING → COMPLETE → IDLE."""
        task = Task(id="lifecycle-1", agent_id="agent-1", state=TaskState.IDLE)

        # Step 1: User enters command
        state_machine.transition_to_commanded(task)
        assert task.state == TaskState.COMMANDED

        # Step 2: LLM starts processing
        state_machine.transition_to_processing(task)
        assert task.state == TaskState.PROCESSING

        # Step 3: LLM completes work
        state_machine.transition_to_complete(task)
        assert task.state == TaskState.COMPLETE
        assert task.completed_at is not None

        # Step 4: New task begins
        state_machine.transition_to_idle(task)
        assert task.state == TaskState.IDLE

    def test_full_lifecycle_with_question(self, state_machine):
        """Test: IDLE → COMMANDED → PROCESSING → AWAITING → PROCESSING → COMPLETE."""
        task = Task(id="lifecycle-2", agent_id="agent-1", state=TaskState.IDLE)

        # Step 1: User enters command
        state_machine.transition_to_commanded(task)
        assert task.state == TaskState.COMMANDED

        # Step 2: LLM starts processing
        state_machine.transition_to_processing(task)
        assert task.state == TaskState.PROCESSING

        # Step 3: LLM asks a question
        state_machine.transition_to_awaiting_input(task)
        assert task.state == TaskState.AWAITING_INPUT

        # Step 4: User responds
        state_machine.transition_to_processing(task)
        assert task.state == TaskState.PROCESSING

        # Step 5: LLM completes work
        state_machine.transition_to_complete(task)
        assert task.state == TaskState.COMPLETE

    def test_multiple_questions_cycle(self, state_machine):
        """Test multiple question-answer cycles."""
        task = Task(id="lifecycle-3", agent_id="agent-1", state=TaskState.PROCESSING)

        # First question
        state_machine.transition_to_awaiting_input(task)
        state_machine.transition_to_processing(task)

        # Second question
        state_machine.transition_to_awaiting_input(task)
        state_machine.transition_to_processing(task)

        # Third question
        state_machine.transition_to_awaiting_input(task)
        state_machine.transition_to_processing(task)

        # Finally complete
        state_machine.transition_to_complete(task)
        assert task.state == TaskState.COMPLETE


class TestInvalidTransitionErrorMessage:
    """Test InvalidTransitionError message formatting."""

    def test_error_message_format(self):
        """Error message includes all relevant information."""
        error = InvalidTransitionError(
            TaskState.IDLE, TaskState.COMPLETE, TransitionTrigger.LLM_FINISHED
        )
        message = str(error)

        assert "idle" in message
        assert "complete" in message
        assert "llm_finished" in message


class TestTransitionTriggerEnum:
    """Test TransitionTrigger enum values."""

    def test_all_triggers_exist(self):
        """All 8 triggers are defined (6 polling + 2 hook-based)."""
        triggers = [t.value for t in TransitionTrigger]
        # Polling-based triggers
        assert "user_pressed_enter" in triggers
        assert "llm_started" in triggers
        assert "llm_asked_question" in triggers
        assert "llm_finished" in triggers
        assert "user_responded" in triggers
        assert "new_task_started" in triggers
        # Hook-based triggers
        assert "hook_prompt_submitted" in triggers
        assert "hook_turn_complete" in triggers
        assert len(triggers) == 8


class TestValidTransitionsDict:
    """Test the VALID_TRANSITIONS constant."""

    def test_exactly_8_valid_transitions(self):
        """There are exactly 8 valid transitions defined (6 polling + 2 hooks)."""
        assert len(VALID_TRANSITIONS) == 8

    def test_all_transitions_have_unique_trigger(self):
        """Each transition has a specific trigger."""
        triggers_used = list(VALID_TRANSITIONS.values())
        # All 8 triggers should be used exactly once
        assert len(set(triggers_used)) == 8
