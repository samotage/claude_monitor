"""Task State Machine for managing task state transitions.

Implements the state machine from Conceptual Design §5.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.models.task import Task, TaskState


class TransitionTrigger(str, Enum):
    """Triggers that cause state transitions."""

    USER_PRESSED_ENTER = "user_pressed_enter"
    """User pressed Enter to send a command (IDLE → COMMANDED)."""

    LLM_STARTED = "llm_started"
    """LLM began processing (COMMANDED → PROCESSING)."""

    LLM_ASKED_QUESTION = "llm_asked_question"
    """LLM asked a clarifying question (PROCESSING → AWAITING_INPUT)."""

    LLM_FINISHED = "llm_finished"
    """LLM completed the work (PROCESSING → COMPLETE)."""

    USER_RESPONDED = "user_responded"
    """User responded to a question (AWAITING_INPUT → PROCESSING)."""

    NEW_TASK_STARTED = "new_task_started"
    """A new task began (COMPLETE → IDLE)."""


@dataclass
class TransitionResult:
    """Result of a state transition."""

    success: bool
    from_state: TaskState
    to_state: TaskState
    trigger: TransitionTrigger
    timestamp: datetime
    error: str | None = None


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, from_state: TaskState, to_state: TaskState, trigger: TransitionTrigger):
        self.from_state = from_state
        self.to_state = to_state
        self.trigger = trigger
        super().__init__(
            f"Invalid transition: {from_state.value} → {to_state.value} "
            f"(trigger: {trigger.value})"
        )


# Valid transitions: (from_state, to_state) → required_trigger
VALID_TRANSITIONS: dict[tuple[TaskState, TaskState], TransitionTrigger] = {
    # 1. IDLE → COMMANDED: User presses Enter
    (TaskState.IDLE, TaskState.COMMANDED): TransitionTrigger.USER_PRESSED_ENTER,
    # 2. COMMANDED → PROCESSING: LLM starts
    (TaskState.COMMANDED, TaskState.PROCESSING): TransitionTrigger.LLM_STARTED,
    # 3. PROCESSING → AWAITING_INPUT: LLM asks question
    (TaskState.PROCESSING, TaskState.AWAITING_INPUT): TransitionTrigger.LLM_ASKED_QUESTION,
    # 4. PROCESSING → COMPLETE: LLM finishes
    (TaskState.PROCESSING, TaskState.COMPLETE): TransitionTrigger.LLM_FINISHED,
    # 5. AWAITING_INPUT → PROCESSING: User responds
    (TaskState.AWAITING_INPUT, TaskState.PROCESSING): TransitionTrigger.USER_RESPONDED,
    # 6. COMPLETE → IDLE: New task begins
    (TaskState.COMPLETE, TaskState.IDLE): TransitionTrigger.NEW_TASK_STARTED,
}


class TaskStateMachine:
    """Manages state transitions for Tasks.

    Implements the state machine from Conceptual Design §5:

    ```
    IDLE → COMMANDED → PROCESSING → AWAITING_INPUT → PROCESSING (loop)
                                 → COMPLETE → IDLE (new task)
    ```

    All 6 valid transitions:
    1. IDLE → COMMANDED (User presses Enter)
    2. COMMANDED → PROCESSING (LLM starts)
    3. PROCESSING → AWAITING_INPUT (LLM asks question)
    4. PROCESSING → COMPLETE (LLM finishes)
    5. AWAITING_INPUT → PROCESSING (User responds)
    6. COMPLETE → IDLE (New task begins)
    """

    def can_transition(self, task: Task, to_state: TaskState) -> bool:
        """Check if a transition from the task's current state to to_state is valid.

        Args:
            task: The task to check.
            to_state: The target state.

        Returns:
            True if the transition is valid, False otherwise.
        """
        return (task.state, to_state) in VALID_TRANSITIONS

    def get_valid_transitions(self, task: Task) -> list[TaskState]:
        """Get all valid target states from the task's current state.

        Args:
            task: The task to check.

        Returns:
            List of valid target states.
        """
        valid = []
        for (from_state, to_state), _ in VALID_TRANSITIONS.items():
            if from_state == task.state:
                valid.append(to_state)
        return valid

    def get_required_trigger(self, from_state: TaskState, to_state: TaskState) -> TransitionTrigger:
        """Get the required trigger for a transition.

        Args:
            from_state: The source state.
            to_state: The target state.

        Returns:
            The required trigger for this transition.

        Raises:
            InvalidTransitionError: If the transition is not valid.
        """
        key = (from_state, to_state)
        if key not in VALID_TRANSITIONS:
            raise InvalidTransitionError(
                from_state,
                to_state,
                TransitionTrigger.USER_PRESSED_ENTER,  # dummy trigger
            )
        return VALID_TRANSITIONS[key]

    def transition(
        self, task: Task, to_state: TaskState, trigger: TransitionTrigger
    ) -> TransitionResult:
        """Attempt to transition a task to a new state.

        Args:
            task: The task to transition.
            to_state: The target state.
            trigger: The trigger causing this transition.

        Returns:
            TransitionResult with success status and metadata.

        Raises:
            InvalidTransitionError: If the transition is not valid.
        """
        from_state = task.state
        now = datetime.now()

        # Check if transition is valid
        key = (from_state, to_state)
        if key not in VALID_TRANSITIONS:
            raise InvalidTransitionError(from_state, to_state, trigger)

        # Check if trigger matches expected trigger
        expected_trigger = VALID_TRANSITIONS[key]
        if trigger != expected_trigger:
            raise InvalidTransitionError(from_state, to_state, trigger)

        # Perform the transition
        task.state = to_state

        # Handle special cases
        if to_state == TaskState.COMPLETE:
            task.completed_at = now

        return TransitionResult(
            success=True,
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            timestamp=now,
        )

    def transition_to_idle(self, task: Task) -> TransitionResult:
        """Convenience method: Transition from COMPLETE to IDLE for a new task.

        Args:
            task: The task to transition.

        Returns:
            TransitionResult with success status.
        """
        return self.transition(task, TaskState.IDLE, TransitionTrigger.NEW_TASK_STARTED)

    def transition_to_commanded(self, task: Task) -> TransitionResult:
        """Convenience method: Transition from IDLE to COMMANDED.

        Args:
            task: The task to transition.

        Returns:
            TransitionResult with success status.
        """
        return self.transition(task, TaskState.COMMANDED, TransitionTrigger.USER_PRESSED_ENTER)

    def transition_to_processing(self, task: Task) -> TransitionResult:
        """Convenience method: Transition to PROCESSING.

        Works from either COMMANDED or AWAITING_INPUT.

        Args:
            task: The task to transition.

        Returns:
            TransitionResult with success status.
        """
        if task.state == TaskState.COMMANDED:
            return self.transition(task, TaskState.PROCESSING, TransitionTrigger.LLM_STARTED)
        elif task.state == TaskState.AWAITING_INPUT:
            return self.transition(task, TaskState.PROCESSING, TransitionTrigger.USER_RESPONDED)
        else:
            raise InvalidTransitionError(
                task.state, TaskState.PROCESSING, TransitionTrigger.LLM_STARTED
            )

    def transition_to_awaiting_input(self, task: Task) -> TransitionResult:
        """Convenience method: Transition from PROCESSING to AWAITING_INPUT.

        Args:
            task: The task to transition.

        Returns:
            TransitionResult with success status.
        """
        return self.transition(task, TaskState.AWAITING_INPUT, TransitionTrigger.LLM_ASKED_QUESTION)

    def transition_to_complete(self, task: Task) -> TransitionResult:
        """Convenience method: Transition from PROCESSING to COMPLETE.

        Args:
            task: The task to transition.

        Returns:
            TransitionResult with success status.
        """
        return self.transition(task, TaskState.COMPLETE, TransitionTrigger.LLM_FINISHED)
