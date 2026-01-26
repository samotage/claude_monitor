"""HookReceiver - Service for processing Claude Code lifecycle hooks.

This service receives HTTP webhook events from Claude Code sessions and
translates them into state transitions for the monitoring system.

Events received:
- session_start: Claude Code session began
- session_end: Claude Code session closed
- stop: Claude finished a turn (primary completion signal)
- notification: Various notifications from Claude Code
- user_prompt_submit: User submitted a prompt

The hooks provide instant, certain state detection vs. the polling-based
inference approach, with confidence=1.0 for all transitions.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from src.models.task import TaskState

if TYPE_CHECKING:
    from src.services.agent_store import AgentStore
    from src.services.event_bus import EventBus
    from src.services.governing_agent import GoverningAgent

logger = logging.getLogger(__name__)


class HookEventType(str, Enum):
    """Claude Code hook event types."""

    SESSION_START = "session-start"
    SESSION_END = "session-end"
    STOP = "stop"
    NOTIFICATION = "notification"
    USER_PROMPT_SUBMIT = "user-prompt-submit"


@dataclass
class HookEvent:
    """A Claude Code hook event."""

    event_type: HookEventType
    session_id: str
    cwd: str = ""
    timestamp: int = field(default_factory=lambda: int(time.time()))
    data: dict = field(default_factory=dict)


@dataclass
class HookResult:
    """Result of processing a hook event."""

    success: bool
    agent_id: str | None = None
    new_state: TaskState | None = None
    message: str = ""


class HookReceiver:
    """Service for receiving and processing Claude Code lifecycle hooks.

    This service:
    1. Receives hook events via HTTP endpoints
    2. Correlates Claude Code sessions to monitored agents
    3. Triggers state transitions with confidence=1.0
    4. Emits SSE events for dashboard updates

    The hook-based approach provides instant, certain state detection
    compared to the polling-based inference approach.
    """

    def __init__(
        self,
        agent_store: "AgentStore",
        event_bus: "EventBus",
        governing_agent: "GoverningAgent | None" = None,
    ):
        """Initialize the HookReceiver.

        Args:
            agent_store: Store for agent/task state.
            event_bus: Event bus for SSE broadcasting.
            governing_agent: Main orchestrator (optional, for state transitions).
        """
        self._store = agent_store
        self._event_bus = event_bus
        self._governing_agent = governing_agent

        # Thread lock for protecting shared state
        self._lock = threading.Lock()

        # Session correlation map: claude_session_id -> agent_id
        self._session_map: dict[str, str] = {}

        # Track hook activity
        self._last_event_time: float = 0
        self._event_count: int = 0

        # Enter signal tracking (for WezTerm Enter key detection)
        # Maps pane_id -> timestamp of Enter press
        self._enter_signals: dict[str, float] = {}

    def set_governing_agent(self, governing_agent: "GoverningAgent") -> None:
        """Set the governing agent (for late binding).

        Args:
            governing_agent: The GoverningAgent instance.
        """
        self._governing_agent = governing_agent

    def process_event(
        self,
        event_type: str,
        session_id: str,
        cwd: str = "",
        timestamp: int | None = None,
        data: dict | None = None,
    ) -> HookResult:
        """Process a Claude Code hook event.

        This is the main entry point for hook events from the API.

        Args:
            event_type: The event type (e.g., "session-start", "stop").
            session_id: The Claude Code session ID.
            cwd: The working directory of the session.
            timestamp: Unix timestamp of the event.
            data: Additional event data.

        Returns:
            HookResult with processing outcome.
        """
        logger.debug(
            f"[HookReceiver] process_event called: type={event_type}, "
            f"session={session_id[:8]}..., cwd={cwd}"
        )

        # Update activity tracking (thread-safe)
        with self._lock:
            self._last_event_time = time.time()
            self._event_count += 1
            current_count = self._event_count

        logger.debug(f"[HookReceiver] Event count now: {current_count}")

        # Notify GoverningAgent of hook activity (for dynamic polling)
        if self._governing_agent:
            self._governing_agent.record_hook_event()

        # Normalize event type
        try:
            event_type_enum = HookEventType(event_type)
        except ValueError:
            logger.warning(f"[HookReceiver] Unknown hook event type: {event_type}")
            return HookResult(
                success=False,
                message=f"Unknown event type: {event_type}",
            )

        # Create event object
        event = HookEvent(
            event_type=event_type_enum,
            session_id=session_id,
            cwd=cwd,
            timestamp=timestamp or int(time.time()),
            data=data or {},
        )

        logger.info(f"[HookReceiver] Processing {event_type} for session {session_id[:8]}...")

        # Process based on event type
        if event_type_enum == HookEventType.SESSION_START:
            return self._handle_session_start(event)
        elif event_type_enum == HookEventType.SESSION_END:
            return self._handle_session_end(event)
        elif event_type_enum == HookEventType.STOP:
            return self._handle_stop(event)
        elif event_type_enum == HookEventType.USER_PROMPT_SUBMIT:
            return self._handle_user_prompt_submit(event)
        elif event_type_enum == HookEventType.NOTIFICATION:
            return self._handle_notification(event)
        else:
            return HookResult(success=False, message="Unhandled event type")

    def _handle_session_start(self, event: HookEvent) -> HookResult:
        """Handle a session_start event.

        Creates or finds an agent for this session and sets state to IDLE.

        Args:
            event: The hook event.

        Returns:
            HookResult with the agent ID.
        """
        agent = self._correlate_session(event.session_id, event.cwd)

        if agent is None:
            return HookResult(
                success=False,
                message="Failed to correlate session to agent",
            )

        # Emit SSE event
        self._event_bus.emit(
            "hook_session_start",
            {
                "agent_id": agent.id,
                "session_id": event.session_id,
                "cwd": event.cwd,
                "timestamp": event.timestamp,
            },
        )

        return HookResult(
            success=True,
            agent_id=agent.id,
            new_state=TaskState.IDLE,
            message="Session started",
        )

    def _handle_session_end(self, event: HookEvent) -> HookResult:
        """Handle a session_end event.

        Marks the agent as inactive and removes session mapping.

        Args:
            event: The hook event.

        Returns:
            HookResult with processing outcome.
        """
        # Get and remove session mapping (thread-safe)
        with self._lock:
            agent_id = self._session_map.pop(event.session_id, None)

        if agent_id:
            # Emit SSE event (outside lock to avoid I/O while holding lock)
            self._event_bus.emit(
                "hook_session_end",
                {
                    "agent_id": agent_id,
                    "session_id": event.session_id,
                    "timestamp": event.timestamp,
                },
            )

            return HookResult(
                success=True,
                agent_id=agent_id,
                message="Session ended",
            )

        return HookResult(
            success=True,
            message="Session not tracked (may have been created before hooks)",
        )

    def _handle_stop(self, event: HookEvent) -> HookResult:
        """Handle a stop event (Claude finished a turn).

        This is the PRIMARY signal that Claude has finished working.
        Transitions state to IDLE (turn complete).

        Args:
            event: The hook event.

        Returns:
            HookResult with the new state.
        """
        logger.debug(f"[HookReceiver] _handle_stop: session={event.session_id[:8]}...")

        agent = self._get_agent_for_session(event.session_id, event.cwd)

        if agent is None:
            logger.debug("[HookReceiver] _handle_stop: No agent for session, returning early")
            return HookResult(
                success=True,
                message="Session not tracked",
            )

        logger.debug(
            f"[HookReceiver] _handle_stop: Found agent {agent.id[:8]} ({agent.session_name})"
        )

        # Get current task state
        current_task = self._store.get_current_task(agent.id)
        old_state = current_task.state if current_task else TaskState.IDLE

        # Determine new state - stop means Claude finished, so IDLE
        new_state = TaskState.IDLE

        logger.info(
            f"[HookReceiver] _handle_stop: agent={agent.id[:8]}, "
            f"transition {old_state.value} -> {new_state.value}"
        )

        # Apply state transition if we have a governing agent
        if self._governing_agent and old_state != new_state:
            logger.debug("[HookReceiver] Calling GoverningAgent._handle_state_transition")
            self._governing_agent._handle_state_transition(
                agent_id=agent.id,
                old_state=old_state,
                new_state=new_state,
                content="",  # No content needed for hook-based detection
                interpretation_confidence=1.0,  # Hooks are certain
            )
        elif old_state == new_state:
            logger.debug(f"[HookReceiver] State unchanged ({old_state.value}), skipping transition")

        # Emit SSE event
        self._event_bus.emit(
            "hook_stop",
            {
                "agent_id": agent.id,
                "session_id": event.session_id,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "timestamp": event.timestamp,
            },
        )

        return HookResult(
            success=True,
            agent_id=agent.id,
            new_state=new_state,
            message="Turn completed",
        )

    def _handle_user_prompt_submit(self, event: HookEvent) -> HookResult:
        """Handle a user_prompt_submit event.

        The user has submitted a prompt, transitioning to PROCESSING.

        Args:
            event: The hook event.

        Returns:
            HookResult with the new state.
        """
        logger.debug(
            f"[HookReceiver] _handle_user_prompt_submit: session={event.session_id[:8]}..."
        )

        agent = self._get_agent_for_session(event.session_id, event.cwd)

        if agent is None:
            logger.debug(
                "[HookReceiver] _handle_user_prompt_submit: No agent found, returning early"
            )
            return HookResult(
                success=True,
                message="Session not tracked",
            )

        logger.debug(
            f"[HookReceiver] _handle_user_prompt_submit: Found agent {agent.id[:8]} ({agent.session_name})"
        )

        # Get current task state
        current_task = self._store.get_current_task(agent.id)
        old_state = current_task.state if current_task else TaskState.IDLE

        # User submitted prompt means Claude is now processing
        new_state = TaskState.PROCESSING

        logger.info(
            f"[HookReceiver] _handle_user_prompt_submit: agent={agent.id[:8]}, "
            f"transition {old_state.value} -> {new_state.value}"
        )

        # Apply state transition if we have a governing agent
        if self._governing_agent and old_state != new_state:
            logger.debug("[HookReceiver] Calling GoverningAgent._handle_state_transition")
            self._governing_agent._handle_state_transition(
                agent_id=agent.id,
                old_state=old_state,
                new_state=new_state,
                content="",
                interpretation_confidence=1.0,
            )
        elif old_state == new_state:
            logger.debug(f"[HookReceiver] State unchanged ({old_state.value}), skipping transition")

        # Emit SSE event
        self._event_bus.emit(
            "hook_user_prompt_submit",
            {
                "agent_id": agent.id,
                "session_id": event.session_id,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "timestamp": event.timestamp,
            },
        )

        return HookResult(
            success=True,
            agent_id=agent.id,
            new_state=new_state,
            message="Prompt submitted, processing",
        )

    def _handle_notification(self, event: HookEvent) -> HookResult:
        """Handle a notification event.

        Notifications are secondary signals used for validation,
        not primary state changes.

        Args:
            event: The hook event.

        Returns:
            HookResult with processing outcome.
        """
        agent = self._get_agent_for_session(event.session_id, event.cwd)

        if agent is None:
            return HookResult(
                success=True,
                message="Session not tracked",
            )

        # Emit SSE event for dashboard
        self._event_bus.emit(
            "hook_notification",
            {
                "agent_id": agent.id,
                "session_id": event.session_id,
                "timestamp": event.timestamp,
                "data": event.data,
            },
        )

        return HookResult(
            success=True,
            agent_id=agent.id,
            message="Notification received",
        )

    def _correlate_session(self, claude_session_id: str, cwd: str):
        """Correlate a Claude Code session to an agent.

        First checks if we've seen this session before.
        Then tries to match by working directory.
        Finally creates a new agent if no match.

        Args:
            claude_session_id: The Claude Code session ID.
            cwd: The working directory.

        Returns:
            The correlated Agent, or None if correlation failed.
        """
        logger.debug(
            f"[HookReceiver] _correlate_session: session={claude_session_id[:8]}..., cwd={cwd}"
        )

        # Check if we already have this session mapped (thread-safe)
        with self._lock:
            if claude_session_id in self._session_map:
                agent_id = self._session_map[claude_session_id]
                agent = self._store.get_agent(agent_id)
                if agent:
                    logger.debug(
                        f"[HookReceiver] Found existing mapping: session {claude_session_id[:8]} "
                        f"-> agent {agent.id[:8]} ({agent.session_name})"
                    )
                    return agent
                else:
                    logger.warning(
                        f"[HookReceiver] Session {claude_session_id[:8]} mapped to agent "
                        f"{agent_id[:8]} but agent not found in store!"
                    )

        # Normalize cwd (remove trailing slash)
        cwd = cwd.rstrip("/") if cwd else ""

        # Try to find existing agent by working directory
        all_agents = self._store.list_agents()
        logger.debug(f"[HookReceiver] Checking {len(all_agents)} agents for cwd match: {cwd}")

        for agent in all_agents:
            # Check if agent's project path matches
            if agent.project_id:
                project = self._store.get_project(agent.project_id)
                if project and project.path:
                    project_path = project.path.rstrip("/")
                    logger.debug(
                        f"[HookReceiver] Comparing agent {agent.id[:8]} project path: "
                        f"'{project_path}' vs cwd '{cwd}'"
                    )
                    if project_path == cwd:
                        with self._lock:
                            self._session_map[claude_session_id] = agent.id
                        logger.info(
                            f"[HookReceiver] Correlated session {claude_session_id[:8]} "
                            f"to agent {agent.id[:8]} by project path match"
                        )
                        return agent

        # No match found - create a new agent
        # Use cwd as session name since we don't have terminal info
        session_name = cwd.split("/")[-1] if cwd else "claude-session"
        logger.info(
            f"[HookReceiver] No matching agent found for cwd={cwd}, "
            f"creating new agent: {session_name}"
        )

        agent = self._store.create_agent(
            terminal_session_id=f"hook-{claude_session_id[:8]}",
            session_name=session_name,
        )

        # Store mapping (thread-safe)
        with self._lock:
            self._session_map[claude_session_id] = agent.id
        logger.info(
            f"[HookReceiver] Created new agent {agent.id[:8]} for session {claude_session_id[:8]}"
        )

        return agent

    def _get_agent_for_session(self, claude_session_id: str, cwd: str = ""):
        """Get agent for a session, with optional correlation.

        Args:
            claude_session_id: The Claude Code session ID.
            cwd: The working directory (used for correlation if needed).

        Returns:
            The Agent, or None if not found.
        """
        # Check existing mapping (thread-safe)
        with self._lock:
            if claude_session_id in self._session_map:
                agent_id = self._session_map[claude_session_id]
                return self._store.get_agent(agent_id)

        # Try to correlate if we have cwd
        if cwd:
            return self._correlate_session(claude_session_id, cwd)

        return None

    def get_status(self) -> dict:
        """Get hook receiver status.

        Returns:
            Status dictionary with activity metrics.
        """
        with self._lock:
            return {
                "active": self._last_event_time > 0,
                "last_event_time": self._last_event_time,
                "seconds_since_last_event": (
                    time.time() - self._last_event_time if self._last_event_time > 0 else None
                ),
                "event_count": self._event_count,
                "tracked_sessions": len(self._session_map),
            }

    def get_session_mapping(self) -> dict[str, str]:
        """Get the current session mapping.

        Returns:
            Dict mapping claude_session_id -> agent_id.
        """
        with self._lock:
            return self._session_map.copy()

    def record_enter_signal(self, pane_id: str) -> None:
        """Record that Enter was pressed in a WezTerm pane.

        Called by the /api/wezterm/enter-pressed endpoint.
        The signal can be consumed later to detect turn starts.

        Args:
            pane_id: The WezTerm pane ID (as string).
        """
        with self._lock:
            self._enter_signals[pane_id] = time.time()

        logger.debug(f"[HookReceiver] Recorded Enter signal for pane {pane_id}")

    def consume_enter_signal(self, pane_id: str, max_age_seconds: float = 10.0) -> float | None:
        """Consume and return the pending Enter signal for a pane.

        Returns the signal timestamp and removes it from the pending dict.
        Returns None if no signal is pending or if the signal is stale.

        Args:
            pane_id: The WezTerm pane ID.
            max_age_seconds: Maximum age of signal to accept (default 10s).

        Returns:
            The timestamp when Enter was pressed, or None.
        """
        with self._lock:
            signal_time = self._enter_signals.pop(pane_id, None)

        if signal_time is None:
            return None

        # Expire if older than max_age_seconds
        age = time.time() - signal_time
        if age > max_age_seconds:
            logger.debug(f"[HookReceiver] Enter signal for pane {pane_id} expired (age={age:.1f}s)")
            return None

        return signal_time

    def get_pending_enter_signals(self) -> dict[str, float]:
        """Get all pending enter signals.

        Returns:
            Dict mapping pane_id -> timestamp.
        """
        with self._lock:
            return self._enter_signals.copy()

    @staticmethod
    def validate_session_id(session_id: str) -> bool:
        """Validate that a session ID is safe to use.

        Session IDs should only contain alphanumeric chars, hyphens,
        underscores, colons, and periods (for tmux name:window.pane format).

        Args:
            session_id: The session ID to validate.

        Returns:
            True if valid, False otherwise.
        """
        if not session_id or len(session_id) > 256:
            return False
        return bool(re.match(r"^[\w\-:.]+$", session_id))
