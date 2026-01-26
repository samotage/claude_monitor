"""Task model with state machine states."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    """Task state machine states.

    State transitions:
    - IDLE → COMMANDED (User presses Enter)
    - COMMANDED → PROCESSING (LLM starts)
    - PROCESSING → AWAITING_INPUT (LLM asks question)
    - PROCESSING → COMPLETE (LLM finishes)
    - AWAITING_INPUT → PROCESSING (User responds)
    - COMPLETE → IDLE (New task begins)
    """

    IDLE = "idle"
    """No active work, awaiting command."""

    COMMANDED = "commanded"
    """Command sent, processing not yet started."""

    PROCESSING = "processing"
    """LLM actively working."""

    AWAITING_INPUT = "awaiting_input"
    """Waiting for user response to a question."""

    COMPLETE = "complete"
    """Task finished (terminal state for this task)."""


class Task(BaseModel):
    """A unit of work being performed by an agent.

    A task represents a single user request and all the turns (interactions)
    needed to complete it. Tasks are sequential within an agent - only one
    task is active at a time.

    Note: The `turns` field stores Turn IDs. The actual Turn objects are
    managed by AgentStore to avoid circular dependencies.
    """

    id: str = Field(..., description="Unique task identifier (UUID)")
    agent_id: str = Field(..., description="References the owning Agent")
    state: TaskState = Field(
        default=TaskState.IDLE,
        description="Current state in the task lifecycle",
    )
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = Field(
        default=None,
        description="When the task reached COMPLETE state",
    )
    turn_ids: list[str] = Field(
        default_factory=list,
        description="IDs of turns in this task (managed by AgentStore)",
    )
    summary: str | None = Field(
        default=None,
        description="LLM-generated summary of what this task accomplished",
    )
    priority_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Priority score (0-100) relative to headspace focus",
    )
    priority_rationale: str | None = Field(
        default=None,
        description="Explanation of the priority score",
    )
