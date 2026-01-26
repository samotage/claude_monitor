"""GoverningAgent orchestrator for Claude Headspace.

The central coordinator that monitors agents, detects state transitions,
triggers inference calls, and manages priorities.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from src.backends.base import SessionInfo
from src.backends.wezterm import WezTermBackend, get_wezterm_backend
from src.models.inference import InferencePurpose
from src.models.task import TaskState
from src.services.agent_store import AgentStore
from src.services.event_bus import EventBus, get_event_bus
from src.services.inference_service import InferenceService
from src.services.notification_service import NotificationService, get_notification_service
from src.services.state_interpreter import StateInterpreter
from src.services.task_state_machine import TaskStateMachine, TransitionTrigger

if True:  # TYPE_CHECKING equivalent without import overhead
    from src.models.config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class AgentSnapshot:
    """Snapshot of an agent's state for comparison."""

    agent_id: str
    session_id: str
    task_state: TaskState
    last_content_hash: str
    last_seen: datetime = field(default_factory=datetime.now)


class GoverningAgent:
    """Central orchestrator for Claude Headspace.

    Responsibilities:
    1. Monitor project agents via WezTerm backend
    2. Detect state transitions using StateInterpreter
    3. Trigger inference calls per Activity Matrix
    4. Compute priorities based on headspace alignment
    5. Emit events via EventBus
    6. Support hybrid polling + hooks mode
    """

    # Polling interval for state detection (normal mode) - defaults, overridden by config
    DEFAULT_POLL_INTERVAL_SECONDS = 2.0
    DEFAULT_POLL_INTERVAL_WITH_HOOKS_SECONDS = 60.0
    DEFAULT_HOOK_TIMEOUT_SECONDS = 300.0

    def __init__(
        self,
        agent_store: AgentStore | None = None,
        event_bus: EventBus | None = None,
        inference_service: InferenceService | None = None,
        state_interpreter: StateInterpreter | None = None,
        backend: WezTermBackend | None = None,
        notification_service: NotificationService | None = None,
        config: "AppConfig | None" = None,
    ):
        """Initialize the GoverningAgent.

        Args:
            agent_store: Store for agent/task state. Uses singleton if not provided.
            event_bus: Event bus for SSE. Uses singleton if not provided.
            inference_service: Service for LLM calls.
            state_interpreter: For state detection.
            backend: WezTerm backend for terminal interaction.
            notification_service: Service for macOS notifications.
            config: Application configuration for polling/hook timeouts.
        """
        self._config = config
        self._store = agent_store or AgentStore()
        self._event_bus = event_bus or get_event_bus()
        self._inference = inference_service or InferenceService()
        self._interpreter = state_interpreter or StateInterpreter(self._inference)
        self._backend = backend or get_wezterm_backend()
        self._notifications = notification_service or get_notification_service()
        self._state_machine = TaskStateMachine()

        # Agent tracking
        self._snapshots: dict[str, AgentSnapshot] = {}

        # Threading
        self._running = False
        self._poll_thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Priority tracking
        self._priorities_stale = True
        self._last_priority_computation: datetime | None = None

        # Hook integration tracking
        self._last_hook_event_time: float = 0
        self._hooks_enabled: bool = True

        # Callbacks for extension
        self._on_state_change_callbacks: list[Callable] = []

    @property
    def poll_interval_seconds(self) -> float:
        """Get poll interval from config or use default."""
        if self._config:
            return float(self._config.scan_interval)
        return self.DEFAULT_POLL_INTERVAL_SECONDS

    @property
    def poll_interval_with_hooks_seconds(self) -> float:
        """Get reduced poll interval when hooks are active."""
        if self._config:
            return float(self._config.hooks.polling_interval_with_hooks)
        return self.DEFAULT_POLL_INTERVAL_WITH_HOOKS_SECONDS

    @property
    def hook_timeout_seconds(self) -> float:
        """Get hook timeout from config or use default."""
        if self._config:
            return float(self._config.hooks.session_timeout)
        return self.DEFAULT_HOOK_TIMEOUT_SECONDS

    def start(self) -> None:
        """Start the monitoring loop."""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._poll_thread.start()
            logger.info("GoverningAgent started")

    def stop(self) -> None:
        """Stop the monitoring loop."""
        with self._lock:
            self._running = False
            if self._poll_thread:
                self._poll_thread.join(timeout=5.0)
                self._poll_thread = None
            logger.info("GoverningAgent stopped")

    @property
    def is_running(self) -> bool:
        """Check if the monitoring loop is running."""
        return self._running

    def poll_agents(self) -> None:
        """Poll all agents and detect state changes.

        This is the main polling function called every POLL_INTERVAL_SECONDS.
        It:
        1. Gets all Claude sessions from the backend
        2. Captures terminal content
        3. Interprets state using StateInterpreter
        4. Triggers state transitions
        5. Emits events for changes
        """
        if not self._backend.is_available():
            return

        sessions = self._backend.get_claude_sessions()

        for session in sessions:
            self._process_session(session)

        # Clean up stale snapshots (sessions that no longer exist)
        current_session_ids = {s.session_id for s in sessions}
        stale_ids = [
            agent_id
            for agent_id, snapshot in self._snapshots.items()
            if snapshot.session_id not in current_session_ids
        ]
        for agent_id in stale_ids:
            del self._snapshots[agent_id]

    def _process_session(self, session: SessionInfo) -> None:
        """Process a single session for state changes.

        Args:
            session: The session to process.
        """
        # Get or create agent for this session
        agent = self._store.get_agent_by_terminal_session_id(session.session_id)
        if agent is None:
            # Create new agent for this session
            agent = self._store.create_agent(
                terminal_session_id=session.session_id,
                session_name=session.name,
            )
            logger.info(f"Created agent {agent.id} for session {session.name}")

        # Get terminal content
        content = self._backend.get_content(session.session_id, lines=100)
        if content is None:
            return

        # Compute content hash for change detection
        content_hash = str(hash(content))

        # Get previous snapshot
        prev_snapshot = self._snapshots.get(agent.id)

        # Trigger DETECT_STATE (Fast Tier, per poll cycle)
        interpretation = self._interpreter.interpret(content)
        new_state = interpretation.state

        # Get current task state
        current_task = self._store.get_current_task(agent.id)
        old_state = current_task.state if current_task else TaskState.IDLE

        # Detect state change
        state_changed = new_state != old_state
        content_changed = prev_snapshot is None or prev_snapshot.last_content_hash != content_hash

        if state_changed or content_changed:
            self._handle_state_transition(
                agent_id=agent.id,
                old_state=old_state,
                new_state=new_state,
                content=content,
                interpretation_confidence=interpretation.confidence,
            )

        # Update snapshot
        self._snapshots[agent.id] = AgentSnapshot(
            agent_id=agent.id,
            session_id=session.session_id,
            task_state=new_state,
            last_content_hash=content_hash,
        )

    def _handle_state_transition(
        self,
        agent_id: str,
        old_state: TaskState,
        new_state: TaskState,
        content: str,
        interpretation_confidence: float,
    ) -> None:
        """Handle a state transition and trigger appropriate actions.

        Implements the Activity Matrix from §6:
        - IDLE → COMMANDED: trigger SUMMARIZE_COMMAND
        - PROCESSING → AWAITING_INPUT: trigger CLASSIFY_RESPONSE
        - PROCESSING → COMPLETE: trigger QUICK_PRIORITY

        Args:
            agent_id: The agent ID.
            old_state: Previous state.
            new_state: New state.
            content: Terminal content.
            interpretation_confidence: Confidence of state interpretation.
        """
        if old_state == new_state:
            return

        logger.info(f"Agent {agent_id}: {old_state.value} → {new_state.value}")

        # Get or create current task
        current_task = self._store.get_current_task(agent_id)
        if current_task is None:
            current_task = self._store.create_task(agent_id=agent_id)

        # Determine transition trigger
        trigger = self._determine_trigger(old_state, new_state)

        # Apply state transition
        if trigger:
            transition = self._state_machine.transition(current_task, new_state, trigger)
            if transition.success:
                current_task.state = new_state
                self._store.update_task(current_task)

        # Emit event
        self._event_bus.emit(
            "task_state_changed",
            {
                "agent_id": agent_id,
                "task_id": current_task.id,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "confidence": interpretation_confidence,
            },
        )

        # Trigger Activity Matrix actions
        self._trigger_activity_matrix_actions(
            agent_id=agent_id,
            old_state=old_state,
            new_state=new_state,
            content=content,
        )

        # Send notifications for appropriate state changes
        # (PROCESSING → AWAITING_INPUT, PROCESSING → COMPLETE)
        self._send_state_notification(
            agent_id=agent_id,
            old_state=old_state,
            new_state=new_state,
            current_task=current_task,
        )

        # Call registered callbacks
        for callback in self._on_state_change_callbacks:
            try:
                callback(agent_id, old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")

    def _determine_trigger(
        self, old_state: TaskState, new_state: TaskState
    ) -> TransitionTrigger | None:
        """Determine the transition trigger for a state change.

        Args:
            old_state: Previous state.
            new_state: New state.

        Returns:
            The appropriate TransitionTrigger, or None if not a valid transition.
        """
        trigger_map = {
            (TaskState.IDLE, TaskState.COMMANDED): TransitionTrigger.USER_PRESSED_ENTER,
            (TaskState.COMMANDED, TaskState.PROCESSING): TransitionTrigger.LLM_STARTED,
            (TaskState.PROCESSING, TaskState.AWAITING_INPUT): TransitionTrigger.LLM_ASKED_QUESTION,
            (TaskState.PROCESSING, TaskState.COMPLETE): TransitionTrigger.LLM_FINISHED,
            (TaskState.AWAITING_INPUT, TaskState.PROCESSING): TransitionTrigger.USER_RESPONDED,
            (TaskState.COMPLETE, TaskState.IDLE): TransitionTrigger.NEW_TASK_STARTED,
        }
        return trigger_map.get((old_state, new_state))

    def _trigger_activity_matrix_actions(
        self,
        agent_id: str,
        old_state: TaskState,
        new_state: TaskState,
        content: str,
    ) -> None:
        """Trigger inference calls based on the Activity Matrix.

        Fast Tier (Real-time, per-turn):
        - IDLE → COMMANDED: SUMMARIZE_COMMAND
        - PROCESSING → AWAITING_INPUT: CLASSIFY_RESPONSE
        - PROCESSING → COMPLETE: QUICK_PRIORITY

        Args:
            agent_id: The agent ID.
            old_state: Previous state.
            new_state: New state.
            content: Terminal content.
        """
        agent = self._store.get_agent(agent_id)
        if agent is None:
            return

        # IDLE → COMMANDED: Summarize the command
        if old_state == TaskState.IDLE and new_state == TaskState.COMMANDED:
            self._trigger_summarize_command(agent_id, content)

        # PROCESSING → AWAITING_INPUT: Classify the question/request
        elif old_state == TaskState.PROCESSING and new_state == TaskState.AWAITING_INPUT:
            self._trigger_classify_response(agent_id, content)

        # PROCESSING → COMPLETE: Quick priority update
        elif old_state == TaskState.PROCESSING and new_state == TaskState.COMPLETE:
            self._trigger_quick_priority(agent_id)
            self.invalidate_priorities()

    def _trigger_summarize_command(self, agent_id: str, content: str) -> None:
        """Trigger SUMMARIZE_COMMAND inference.

        Args:
            agent_id: The agent ID.
            content: Terminal content containing the command.
        """
        current_task = self._store.get_current_task(agent_id)
        if current_task is None:
            return

        # Get agent to access project_id
        agent = self._store.get_agent(agent_id)
        project_id = agent.project_id if agent else None

        result = self._inference.call(
            purpose=InferencePurpose.SUMMARIZE_COMMAND,
            input_data={"terminal_content": content[-2000:]},
            user_prompt="Summarize the user's command in 1-2 sentences.",
            turn_id=None,
            project_id=project_id,
        )

        # Store the result
        if "error" not in result.result:
            summary = result.result.get("content", "")
            current_task.command_summary = summary
            self._store.update_task(current_task)
            logger.debug(f"Command summary for {agent_id}: {summary}")

    def _trigger_classify_response(self, agent_id: str, content: str) -> None:
        """Trigger CLASSIFY_RESPONSE inference.

        Args:
            agent_id: The agent ID.
            content: Terminal content with the response.
        """
        result = self._inference.call(
            purpose=InferencePurpose.CLASSIFY_RESPONSE,
            input_data={"terminal_content": content[-2000:]},
            user_prompt=(
                "Classify this response type: "
                "QUESTION (needs user answer), "
                "PERMISSION (needs approval), "
                "ERROR (needs debugging), "
                "INFO (just informational). "
                'Respond with JSON: {"type": "...", "urgency": "high|medium|low"}'
            ),
        )

        if "error" not in result.result:
            response_type = result.result.get("type", "INFO")
            urgency = result.result.get("urgency", "low")

            self._event_bus.emit(
                "response_classified",
                {
                    "agent_id": agent_id,
                    "type": response_type,
                    "urgency": urgency,
                },
            )

    def _send_state_notification(
        self,
        agent_id: str,
        old_state: TaskState,
        new_state: TaskState,
        current_task,
    ) -> None:
        """Send macOS notification for state changes that need user attention.

        Notifications are sent for:
        - PROCESSING → AWAITING_INPUT (Claude is asking a question)
        - PROCESSING → COMPLETE (Task finished)

        Args:
            agent_id: The agent ID.
            old_state: Previous state.
            new_state: New state.
            current_task: The current task object.
        """
        agent = self._store.get_agent(agent_id)
        if agent is None:
            return

        # Get project info for notification
        project_name = None
        if agent.project_id:
            project = self._store.get_project(agent.project_id)
            if project:
                project_name = project.name

        # Get task summary if available
        task_summary = current_task.summary if current_task else None

        # Send notification
        self._notifications.notify_state_change(
            agent_id=agent_id,
            session_id=agent.terminal_session_id,
            session_name=agent.session_name,
            old_state=old_state,
            new_state=new_state,
            project_name=project_name,
            task_summary=task_summary,
            priority_score=current_task.priority_score if current_task else None,
        )

    def _trigger_quick_priority(self, agent_id: str) -> None:
        """Trigger QUICK_PRIORITY inference.

        Args:
            agent_id: The agent ID.
        """
        agent = self._store.get_agent(agent_id)
        if agent is None:
            return

        # Get headspace for context
        headspace = self._store.get_headspace()
        headspace_focus = headspace.focus if headspace else "No specific focus"

        result = self._inference.call(
            purpose=InferencePurpose.QUICK_PRIORITY,
            input_data={
                "agent_id": agent_id,
                "session_name": agent.session_name,
                "headspace_focus": headspace_focus,
            },
            user_prompt=(
                f"Rate priority 0-100 for this completed task. "
                f"Current focus: {headspace_focus}. "
                f'Respond with JSON: {{"priority": 0-100, "reason": "..."}}'
            ),
        )

        if "error" not in result.result:
            priority = result.result.get("priority", 50)
            current_task = self._store.get_current_task(agent_id)
            if current_task:
                current_task.priority_score = priority
                self._store.update_task(current_task)

    def invalidate_priorities(self) -> None:
        """Mark priorities as stale, triggering recalculation."""
        with self._lock:
            self._priorities_stale = True

        self._event_bus.emit(
            "priorities_invalidated",
            {
                "timestamp": datetime.now().isoformat(),
            },
        )

    def compute_priorities(self) -> dict[str, int]:
        """Compute full priorities for all agents.

        Deep Tier operation - runs FULL_PRIORITY inference.

        Returns:
            Dict mapping agent_id to priority score.
        """
        with self._lock:
            self._priorities_stale = False
            self._last_priority_computation = datetime.now()

        agents = self._store.list_agents()
        headspace = self._store.get_headspace()
        headspace_focus = headspace.focus if headspace else "No specific focus"

        # Build context for all agents
        agent_contexts = []
        for agent in agents:
            current_task = self._store.get_current_task(agent.id)
            agent_contexts.append(
                {
                    "agent_id": agent.id,
                    "session_name": agent.session_name,
                    "state": current_task.state.value if current_task else "idle",
                    "project_id": agent.project_id,
                }
            )

        if not agent_contexts:
            return {}

        result = self._inference.call(
            purpose=InferencePurpose.FULL_PRIORITY,
            input_data={
                "agents": agent_contexts,
                "headspace_focus": headspace_focus,
            },
            user_prompt=(
                f"Rank these agents by priority (0-100). "
                f"Current focus: {headspace_focus}. "
                f'Respond with JSON: {{"priorities": {{"agent_id": score, ...}}}}'
            ),
        )

        priorities = {}
        if "error" not in result.result:
            priorities = result.result.get("priorities", {})

            # Update tasks with computed priorities
            for agent_id, score in priorities.items():
                task = self._store.get_current_task(agent_id)
                if task:
                    task.priority_score = score
                    self._store.update_task(task)

        self._event_bus.emit(
            "priorities_computed",
            {
                "priorities": priorities,
                "timestamp": datetime.now().isoformat(),
            },
        )

        return priorities

    def handle_wezterm_event(self, event_type: str, pane_id: str, data: dict | None = None) -> None:
        """Handle an event from WezTerm Lua hooks.

        This is called by the Lua hook integration when terminal events occur.

        Args:
            event_type: Type of event (e.g., "command_sent", "output_received").
            pane_id: The WezTerm pane ID.
            data: Additional event data.
        """
        agent = self._store.get_agent_by_terminal_session_id(pane_id)
        if agent is None:
            return

        logger.debug(f"WezTerm event: {event_type} for pane {pane_id}")

        # Handle specific event types
        if event_type == "command_sent":
            # User pressed Enter - transition to COMMANDED
            current_task = self._store.get_current_task(agent.id)
            if current_task and current_task.state == TaskState.IDLE:
                self._handle_state_transition(
                    agent_id=agent.id,
                    old_state=TaskState.IDLE,
                    new_state=TaskState.COMMANDED,
                    content=data.get("command", "") if data else "",
                    interpretation_confidence=1.0,
                )

        elif event_type == "output_started":
            # Claude started producing output - transition to PROCESSING
            current_task = self._store.get_current_task(agent.id)
            if current_task and current_task.state == TaskState.COMMANDED:
                self._handle_state_transition(
                    agent_id=agent.id,
                    old_state=TaskState.COMMANDED,
                    new_state=TaskState.PROCESSING,
                    content="",
                    interpretation_confidence=1.0,
                )

    def on_state_change(self, callback: Callable) -> None:
        """Register a callback for state changes.

        Args:
            callback: Function(agent_id, old_state, new_state) to call.
        """
        self._on_state_change_callbacks.append(callback)

    def _poll_loop(self) -> None:
        """Background polling loop.

        Uses dynamic polling interval based on hook activity:
        - If hooks are active (received within timeout): Poll every 60 seconds
        - If hooks are inactive: Poll every 2 seconds (normal mode)
        """
        while self._running:
            try:
                self.poll_agents()

                # Compute priorities if stale
                if self._priorities_stale:
                    self.compute_priorities()

            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            # Use dynamic interval based on hook activity
            interval = self._get_poll_interval()
            time.sleep(interval)

    def _get_poll_interval(self) -> float:
        """Get the current polling interval based on hook activity.

        Returns:
            Polling interval in seconds.
        """
        if not self._hooks_enabled:
            return self.poll_interval_seconds

        # Check if hooks are active (received events recently)
        if self._last_hook_event_time > 0:
            elapsed = time.time() - self._last_hook_event_time
            if elapsed < self.hook_timeout_seconds:
                # Hooks are active, use reduced polling
                return self.poll_interval_with_hooks_seconds

        # Hooks inactive or never received, use normal polling
        return self.poll_interval_seconds

    def record_hook_event(self) -> None:
        """Record that a hook event was received.

        Called by HookReceiver when processing events to update
        the last hook event timestamp for dynamic polling.
        """
        self._last_hook_event_time = time.time()

    def get_hook_status(self) -> dict:
        """Get hook integration status.

        Returns:
            Dict with hook status information.
        """
        hooks_active = False
        elapsed = None

        if self._last_hook_event_time > 0:
            elapsed = time.time() - self._last_hook_event_time
            hooks_active = elapsed < self.hook_timeout_seconds

        return {
            "hooks_enabled": self._hooks_enabled,
            "hooks_active": hooks_active,
            "last_hook_event_time": self._last_hook_event_time,
            "seconds_since_last_hook": elapsed,
            "current_poll_interval": self._get_poll_interval(),
        }

    @property
    def agent_count(self) -> int:
        """Get the number of tracked agents."""
        return len(self._snapshots)

    @property
    def priorities_stale(self) -> bool:
        """Check if priorities need recalculation."""
        return self._priorities_stale
