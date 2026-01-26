"""Agent model - represents a Claude Code session in a terminal."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.task import TaskState


class Agent(BaseModel):
    """An AI agent running in a terminal session.

    Each Agent has a 1:1 relationship with a WezTerm pane (terminal session).
    The agent's state is derived from its current task's state.

    Terminology note: This replaces the legacy "Session" concept.

    Note: The current task is referenced by ID. The actual Task object
    and state derivation are managed by AgentStore.
    """

    id: str = Field(..., description="Unique agent identifier (UUID)")
    project_id: str | None = Field(
        default=None,
        description="References the parent Project (optional until assigned)",
    )
    terminal_session_id: str = Field(
        ...,
        description="WezTerm pane ID for this agent's terminal",
    )
    session_name: str = Field(
        ...,
        description="Terminal session name (e.g., 'claude-project-abc')",
    )
    current_task_id: str | None = Field(
        default=None,
        description="ID of the currently active task (if any)",
    )
    created_at: datetime = Field(default_factory=datetime.now)
    # State is stored directly since we can't derive it without the Task object
    # AgentStore is responsible for keeping this in sync
    _cached_state: TaskState = TaskState.IDLE

    def get_state(self) -> TaskState:
        """Get the agent's current state.

        This returns the cached state. AgentStore is responsible for
        updating this when the current task's state changes.
        """
        return self._cached_state

    def set_state(self, state: TaskState) -> None:
        """Set the agent's state (called by AgentStore)."""
        self._cached_state = state
