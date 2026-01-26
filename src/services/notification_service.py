"""NotificationService for macOS notifications.

Sends native macOS notifications when agents require attention,
with click-to-focus functionality via WezTerm backend.
"""

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.backends.wezterm import WezTermBackend, get_wezterm_backend
from src.models.task import TaskState

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications."""

    AWAITING_INPUT = "awaiting_input"  # Claude is asking a question
    COMPLETE = "complete"  # Task finished successfully
    ERROR = "error"  # Task encountered an error
    PRIORITY_CHANGE = "priority_change"  # High priority task changed


@dataclass
class NotificationPayload:
    """Data for a notification."""

    type: NotificationType
    title: str
    message: str
    agent_id: str
    session_id: str
    session_name: str
    project_name: str | None = None
    priority_score: int | None = None
    is_high_priority: bool = False


class NotificationService:
    """Sends macOS notifications for agent state changes.

    Uses terminal-notifier for native macOS notifications with
    click-to-focus functionality via WezTerm.
    """

    # Priority threshold for "high priority" notifications
    HIGH_PRIORITY_THRESHOLD = 70

    def __init__(
        self,
        backend: WezTermBackend | None = None,
        enabled: bool = True,
    ):
        """Initialize the NotificationService.

        Args:
            backend: WezTerm backend for focus functionality.
            enabled: Whether notifications are enabled.
        """
        self._backend = backend or get_wezterm_backend()
        self._enabled = enabled
        self._last_notification: dict[str, datetime] = {}

        # Cooldown to prevent notification spam (seconds)
        self._cooldown_seconds = 5.0

    @property
    def enabled(self) -> bool:
        """Check if notifications are enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set notifications enabled state."""
        self._enabled = value

    def notify_state_change(
        self,
        agent_id: str,
        session_id: str,
        session_name: str,
        old_state: TaskState,
        new_state: TaskState,
        project_name: str | None = None,
        task_summary: str | None = None,
        priority_score: int | None = None,
    ) -> bool:
        """Send notification for a state change if appropriate.

        Notifications are sent for:
        - PROCESSING → AWAITING_INPUT (needs user attention)
        - PROCESSING → COMPLETE (task finished)

        Args:
            agent_id: The agent ID.
            session_id: The terminal session ID (pane ID).
            session_name: The session name for display.
            old_state: Previous task state.
            new_state: New task state.
            project_name: Optional project name.
            task_summary: Optional task description.
            priority_score: Optional priority score (0-100).

        Returns:
            True if notification was sent, False otherwise.
        """
        if not self._enabled:
            return False

        # Check for rate limiting
        if not self._check_cooldown(agent_id):
            return False

        # Determine if we should notify
        notification_type = self._get_notification_type(old_state, new_state)
        if notification_type is None:
            return False

        # Build the notification
        is_high_priority = (priority_score or 0) >= self.HIGH_PRIORITY_THRESHOLD
        payload = self._build_payload(
            notification_type=notification_type,
            agent_id=agent_id,
            session_id=session_id,
            session_name=session_name,
            project_name=project_name,
            task_summary=task_summary,
            priority_score=priority_score,
            is_high_priority=is_high_priority,
        )

        # Send it
        success = self._send_notification(payload)

        if success:
            self._last_notification[agent_id] = datetime.now()

        return success

    def notify_custom(
        self,
        title: str,
        message: str,
        agent_id: str | None = None,
        session_id: str | None = None,
        sound: bool = True,
    ) -> bool:
        """Send a custom notification.

        Args:
            title: Notification title.
            message: Notification body.
            agent_id: Optional agent ID for rate limiting.
            session_id: Optional session ID for click-to-focus.
            sound: Whether to play notification sound.

        Returns:
            True if sent successfully.
        """
        if not self._enabled:
            return False

        if agent_id and not self._check_cooldown(agent_id):
            return False

        return self._send_raw_notification(
            title=title,
            message=message,
            session_id=session_id,
            sound=sound,
        )

    def test_notification(self) -> bool:
        """Send a test notification to verify the system works.

        Returns:
            True if sent successfully.
        """
        return self._send_raw_notification(
            title="Claude Headspace",
            message="Notifications are working!",
            session_id=None,
            sound=True,
        )

    def _get_notification_type(
        self, old_state: TaskState, new_state: TaskState
    ) -> NotificationType | None:
        """Determine if a state transition should trigger a notification.

        Args:
            old_state: Previous state.
            new_state: New state.

        Returns:
            NotificationType if should notify, None otherwise.
        """
        # PROCESSING → AWAITING_INPUT: Claude needs input
        if old_state == TaskState.PROCESSING and new_state == TaskState.AWAITING_INPUT:
            return NotificationType.AWAITING_INPUT

        # PROCESSING → COMPLETE: Task finished
        if old_state == TaskState.PROCESSING and new_state == TaskState.COMPLETE:
            return NotificationType.COMPLETE

        return None

    def _build_payload(
        self,
        notification_type: NotificationType,
        agent_id: str,
        session_id: str,
        session_name: str,
        project_name: str | None,
        task_summary: str | None,
        priority_score: int | None,
        is_high_priority: bool,
    ) -> NotificationPayload:
        """Build a notification payload.

        Args:
            notification_type: Type of notification.
            agent_id: Agent ID.
            session_id: Session ID.
            session_name: Session name.
            project_name: Project name.
            task_summary: Task description.
            priority_score: Priority score.
            is_high_priority: Whether high priority.

        Returns:
            NotificationPayload ready to send.
        """
        # Build title based on type and priority
        if notification_type == NotificationType.AWAITING_INPUT:
            title = "High Priority: Input Needed" if is_high_priority else "Input Needed"
        elif notification_type == NotificationType.COMPLETE:
            title = "High Priority: Task Complete" if is_high_priority else "Task Complete"
        else:
            title = "Claude Headspace"

        # Build message
        project_text = project_name or "Unknown project"
        if task_summary:
            message = f"{project_text}: {task_summary[:50]}"
        else:
            message = f"{project_text}: {session_name}"

        return NotificationPayload(
            type=notification_type,
            title=title,
            message=message,
            agent_id=agent_id,
            session_id=session_id,
            session_name=session_name,
            project_name=project_name,
            priority_score=priority_score,
            is_high_priority=is_high_priority,
        )

    def _send_notification(self, payload: NotificationPayload) -> bool:
        """Send a notification from a payload.

        Args:
            payload: The notification payload.

        Returns:
            True if sent successfully.
        """
        return self._send_raw_notification(
            title=payload.title,
            message=payload.message,
            session_id=payload.session_id,
            sound=True,
        )

    def _send_raw_notification(
        self,
        title: str,
        message: str,
        session_id: str | None,
        sound: bool = True,
    ) -> bool:
        """Send a raw notification via terminal-notifier.

        Args:
            title: Notification title.
            message: Notification body.
            session_id: Optional session ID for click-to-focus.
            sound: Whether to play sound.

        Returns:
            True if sent successfully.
        """
        try:
            cmd = [
                "terminal-notifier",
                "-title",
                title,
                "-message",
                message,
                "-sender",
                "com.github.wez.wezterm",  # WezTerm icon
            ]

            if sound:
                cmd.extend(["-sound", "default"])

            # If session_id provided, clicking focuses that WezTerm pane
            if session_id and self._backend.is_available():
                # Use wezterm cli to focus the pane
                focus_cmd = f"wezterm cli activate-pane --pane-id {session_id}"
                cmd.extend(["-execute", focus_cmd])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.warning(f"Notification error: {result.stderr}")
                return False

            logger.debug(f"Notification sent: {title}")
            return True

        except FileNotFoundError:
            logger.warning(
                "terminal-notifier not found. Install with: brew install terminal-notifier"
            )
            return False
        except subprocess.TimeoutExpired:
            logger.warning("Notification timed out")
            return False
        except Exception as e:
            logger.error(f"Notification exception: {e}")
            return False

    def _check_cooldown(self, agent_id: str) -> bool:
        """Check if enough time has passed since the last notification.

        Args:
            agent_id: The agent ID.

        Returns:
            True if cooldown has passed, False if should skip.
        """
        last = self._last_notification.get(agent_id)
        if last is None:
            return True

        elapsed = (datetime.now() - last).total_seconds()
        return elapsed >= self._cooldown_seconds

    def reset_cooldowns(self) -> None:
        """Clear all notification cooldowns."""
        self._last_notification.clear()


# Singleton instance
_notification_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    """Get the singleton NotificationService instance.

    Returns:
        The shared NotificationService instance.
    """
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


def reset_notification_service() -> None:
    """Reset the singleton NotificationService instance."""
    global _notification_service
    _notification_service = None
