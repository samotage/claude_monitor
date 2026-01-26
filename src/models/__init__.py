"""Domain models for Claude Headspace.

All entities from Conceptual Design §4.
"""

from src.models.agent import Agent
from src.models.config import (
    ApiLimitsConfig,
    AppConfig,
    HookConfig,
    NotificationConfig,
    ProjectConfig,
    TerminalLoggingConfig,
    WezTermConfig,
)
from src.models.headspace import HeadspaceFocus, HeadspaceHistoryEntry
from src.models.inference import InferenceCall, InferenceConfig, InferencePurpose
from src.models.log_entry import (
    OpenRouterLogEntry,
    OpenRouterLogStats,
    TerminalLogEntry,
    TerminalLogStats,
    TurnPair,
)
from src.models.project import (
    Project,
    ProjectContext,
    ProjectState,
    ProjectStatus,
    Roadmap,
    RoadmapItem,
)
from src.models.task import Task, TaskState
from src.models.turn import ResponseResultType, Turn, TurnType

__all__ = [
    # Headspace
    "HeadspaceFocus",
    "HeadspaceHistoryEntry",
    # Project
    "Project",
    "ProjectContext",
    "ProjectState",
    "ProjectStatus",
    "Roadmap",
    "RoadmapItem",
    # Agent
    "Agent",
    # Task
    "Task",
    "TaskState",
    # Turn
    "Turn",
    "TurnType",
    "ResponseResultType",
    # Inference
    "InferenceCall",
    "InferenceConfig",
    "InferencePurpose",
    # Config
    "ApiLimitsConfig",
    "AppConfig",
    "HookConfig",
    "ProjectConfig",
    "WezTermConfig",
    "NotificationConfig",
    "TerminalLoggingConfig",
    # Log entries
    "OpenRouterLogEntry",
    "OpenRouterLogStats",
    "TerminalLogEntry",
    "TerminalLogStats",
    "TurnPair",
]
