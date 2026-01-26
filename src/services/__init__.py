"""Services for Claude Headspace."""

from src.services.agent_store import AgentStore
from src.services.compression_service import (
    CompressionService,
    get_compression_service,
    reset_compression_service,
)
from src.services.config_service import (
    ConfigService,
    get_config_service,
    reset_config_service,
)
from src.services.event_bus import Event, EventBus, get_event_bus, reset_event_bus
from src.services.git_analyzer import Commit, GitActivity, GitAnalyzer
from src.services.governing_agent import AgentSnapshot, GoverningAgent
from src.services.hook_receiver import (
    HookEvent,
    HookEventType,
    HookReceiver,
    HookResult,
)
from src.services.inference_service import CacheEntry, InferenceService
from src.services.logging_service import (
    LoggingService,
    get_logging_service,
    reset_logging_service,
)
from src.services.notification_service import (
    NotificationPayload,
    NotificationService,
    NotificationType,
    get_notification_service,
    reset_notification_service,
)
from src.services.priority_service import AgentContext, PriorityResult, PriorityService
from src.services.session_sync_service import (
    KnownSession,
    LiveContext,
    SessionSyncService,
    get_session_sync_service,
    reset_session_sync_service,
)
from src.services.state_interpreter import (
    InterpretationMethod,
    InterpretationResult,
    StateInterpreter,
)
from src.services.summarization_service import (
    SummarizationService,
    get_summarization_service,
    prepare_content_for_summary,
    reset_summarization_service,
    summarise_session,
)
from src.services.task_state_machine import (
    InvalidTransitionError,
    TaskStateMachine,
    TransitionResult,
    TransitionTrigger,
)
from src.services.terminal_logging_service import (
    TerminalLoggingService,
    get_terminal_logging_service,
    reset_terminal_logging_service,
)

__all__ = [
    "AgentContext",
    "AgentSnapshot",
    "AgentStore",
    "CacheEntry",
    "Commit",
    "ConfigService",
    "Event",
    "EventBus",
    "get_config_service",
    "get_event_bus",
    "get_logging_service",
    "get_notification_service",
    "get_terminal_logging_service",
    "reset_config_service",
    "reset_event_bus",
    "reset_logging_service",
    "reset_notification_service",
    "reset_terminal_logging_service",
    "GitActivity",
    "GitAnalyzer",
    "GoverningAgent",
    "HookEvent",
    "HookEventType",
    "HookReceiver",
    "HookResult",
    "InferenceService",
    "InterpretationMethod",
    "InterpretationResult",
    "InvalidTransitionError",
    "LoggingService",
    "NotificationPayload",
    "NotificationService",
    "NotificationType",
    "PriorityResult",
    "PriorityService",
    "StateInterpreter",
    "TaskStateMachine",
    "TerminalLoggingService",
    "TransitionResult",
    "TransitionTrigger",
    # Summarization service
    "SummarizationService",
    "get_summarization_service",
    "reset_summarization_service",
    "prepare_content_for_summary",
    "summarise_session",
    # Compression service
    "CompressionService",
    "get_compression_service",
    "reset_compression_service",
    # Session sync service
    "SessionSyncService",
    "get_session_sync_service",
    "reset_session_sync_service",
    "LiveContext",
    "KnownSession",
]
