"""Inference models for LLM call tracking and configuration."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class InferencePurpose(str, Enum):
    """Purpose categories for inference calls.

    Fast tier (Haiku) - high frequency, low latency:
    - DETECT_STATE: LLM-based state detection (every 2s per agent)
    - SUMMARIZE_COMMAND: Quick command summary (on user command)
    - CLASSIFY_RESPONSE: Question vs completion (on agent response)
    - QUICK_PRIORITY: Within-session priority update (on turn complete)

    Deep tier (Sonnet/Opus) - low frequency, high quality:
    - GENERATE_PROGRESS_NARRATIVE: Git → narrative (on git change / daily)
    - FULL_PRIORITY: Cross-project priority computation (on invalidation)
    - ROADMAP_ANALYSIS: Roadmap progress analysis (on roadmap view)
    - BRAIN_REBOOT: Context briefing generation (on demand)
    """

    # Fast tier
    DETECT_STATE = "detect_state"
    SUMMARIZE_COMMAND = "summarize_command"
    CLASSIFY_RESPONSE = "classify_response"
    QUICK_PRIORITY = "quick_priority"

    # Deep tier
    GENERATE_PROGRESS_NARRATIVE = "generate_progress_narrative"
    FULL_PRIORITY = "full_priority"
    ROADMAP_ANALYSIS = "roadmap_analysis"
    BRAIN_REBOOT = "brain_reboot"


class InferenceCall(BaseModel):
    """Record of an LLM inference call.

    Tracks all inference calls for cost monitoring, debugging, and caching.
    """

    id: str = Field(..., description="Unique inference call identifier")
    turn_id: str | None = Field(
        default=None,
        description="Associated turn ID (None for project-level calls)",
    )
    project_id: str | None = Field(
        default=None,
        description="Associated project ID (for project-level calls)",
    )
    purpose: InferencePurpose = Field(..., description="Why this inference was made")
    model: str = Field(..., description="Model used (resolved from InferenceConfig)")
    input_hash: str = Field(..., description="Hash of input for caching")
    result: dict[str, Any] = Field(..., description="Structured output from LLM")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When this inference call was made",
    )
    latency_ms: int = Field(..., description="Time taken for the call in milliseconds")
    cost_cents: float | None = Field(
        default=None,
        description="Estimated cost in cents (if available)",
    )
    cached: bool = Field(
        default=False,
        description="Whether this result was served from cache",
    )


class InferenceConfig(BaseModel):
    """Per-purpose model configuration for inference calls.

    Allows tuning model selection based on:
    - Latency requirements (fast tier for real-time, deep for batch)
    - Quality requirements (deep tier for complex reasoning)
    - Cost constraints (fast tier is cheaper)

    Models are specified in OpenRouter format: provider/model-name
    """

    # Fast tier - high frequency, low latency (default: claude-3-haiku)
    detect_state: str = Field(
        default="anthropic/claude-3-haiku",
        description="Model for state detection (every 2s)",
    )
    summarize_command: str = Field(
        default="anthropic/claude-3-haiku",
        description="Model for command summarization",
    )
    classify_response: str = Field(
        default="anthropic/claude-3-haiku",
        description="Model for response classification",
    )
    quick_priority: str = Field(
        default="anthropic/claude-3-haiku",
        description="Model for quick priority updates",
    )

    # Deep tier - low frequency, high quality (default: claude-3-sonnet)
    generate_progress_narrative: str = Field(
        default="anthropic/claude-3-sonnet",
        description="Model for git narrative generation",
    )
    full_priority: str = Field(
        default="anthropic/claude-3-sonnet",
        description="Model for full priority computation",
    )
    roadmap_analysis: str = Field(
        default="anthropic/claude-3-sonnet",
        description="Model for roadmap analysis",
    )
    brain_reboot: str = Field(
        default="anthropic/claude-3-sonnet",
        description="Model for brain reboot briefings",
    )

    def get_model(self, purpose: InferencePurpose) -> str:
        """Resolve model for a given purpose."""
        return getattr(self, purpose.value)

    def is_fast_tier(self, purpose: InferencePurpose) -> bool:
        """Check if a purpose is in the fast tier."""
        return purpose in {
            InferencePurpose.DETECT_STATE,
            InferencePurpose.SUMMARIZE_COMMAND,
            InferencePurpose.CLASSIFY_RESPONSE,
            InferencePurpose.QUICK_PRIORITY,
        }
