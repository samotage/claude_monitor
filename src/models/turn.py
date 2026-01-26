"""Turn model for tracking interactions within a task."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TurnType(str, Enum):
    """Type of turn in a task."""

    USER_COMMAND = "user_command"
    """User initiated this turn with a command."""

    AGENT_RESPONSE = "agent_response"
    """Claude's response to a user command or clarification."""


class ResponseResultType(str, Enum):
    """Type of result from an agent response turn."""

    QUESTION = "question"
    """Claude is asking for clarification - requires user input."""

    COMPLETION = "completion"
    """Claude finished the work - task may be complete."""


class Turn(BaseModel):
    """A single interaction turn within a task.

    A task consists of multiple turns:
    1. User sends a command (USER_COMMAND)
    2. Agent responds (AGENT_RESPONSE with COMPLETION or QUESTION)
    3. If QUESTION, user responds (USER_COMMAND) and cycle repeats
    4. Eventually agent responds with COMPLETION

    Note: The `inference_call_ids` field stores InferenceCall IDs.
    The actual InferenceCall objects are managed separately to avoid
    circular dependencies.
    """

    id: str = Field(..., description="Unique turn identifier (UUID)")
    task_id: str = Field(..., description="References the parent Task")
    type: TurnType = Field(..., description="Whether this is a user command or agent response")
    content: str = Field(..., description="The command text or response text")
    result_type: ResponseResultType | None = Field(
        default=None,
        description="Only for AGENT_RESPONSE turns - was it a question or completion?",
    )
    timestamp: datetime = Field(default_factory=datetime.now)
    inference_call_ids: list[str] = Field(
        default_factory=list,
        description="IDs of inference calls triggered by this turn",
    )
