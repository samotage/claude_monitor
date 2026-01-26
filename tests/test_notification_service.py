"""Tests for NotificationService."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.models.task import TaskState
from src.services.notification_service import (
    NotificationPayload,
    NotificationService,
    NotificationType,
    get_notification_service,
    reset_notification_service,
)


@pytest.fixture
def mock_backend():
    """Create a mock WezTerm backend."""
    backend = MagicMock()
    backend.is_available.return_value = True
    return backend


@pytest.fixture
def notification_service(mock_backend):
    """Create a NotificationService with mocked backend."""
    return NotificationService(backend=mock_backend, enabled=True)


class TestNotificationServiceInit:
    """Tests for NotificationService initialization."""

    def test_creates_with_defaults(self):
        """NotificationService creates with default settings."""
        with patch("src.services.notification_service.get_wezterm_backend"):
            service = NotificationService()
            assert service.enabled is True

    def test_accepts_custom_settings(self, mock_backend):
        """NotificationService accepts custom settings."""
        service = NotificationService(backend=mock_backend, enabled=False)
        assert service.enabled is False
        assert service._backend is mock_backend


class TestEnabledProperty:
    """Tests for enabled property."""

    def test_enabled_getter(self, notification_service):
        """enabled property returns current state."""
        assert notification_service.enabled is True

    def test_enabled_setter(self, notification_service):
        """enabled property can be set."""
        notification_service.enabled = False
        assert notification_service.enabled is False


class TestNotifyStateChange:
    """Tests for notify_state_change method."""

    @patch("src.services.notification_service.subprocess.run")
    def test_notifies_on_processing_to_awaiting(self, mock_run, notification_service):
        """Notification sent when PROCESSING → AWAITING_INPUT."""
        mock_run.return_value = MagicMock(returncode=0)

        result = notification_service.notify_state_change(
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.AWAITING_INPUT,
            project_name="Test Project",
        )

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "terminal-notifier" in call_args
        assert "Input Needed" in call_args

    @patch("src.services.notification_service.subprocess.run")
    def test_notifies_on_processing_to_complete(self, mock_run, notification_service):
        """Notification sent when PROCESSING → COMPLETE."""
        mock_run.return_value = MagicMock(returncode=0)

        result = notification_service.notify_state_change(
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.COMPLETE,
            project_name="Test Project",
        )

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "Task Complete" in call_args

    def test_no_notify_on_other_transitions(self, notification_service):
        """No notification for non-triggering transitions."""
        result = notification_service.notify_state_change(
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test",
            old_state=TaskState.IDLE,
            new_state=TaskState.COMMANDED,
        )

        assert result is False

    def test_no_notify_when_disabled(self, notification_service):
        """No notification when service is disabled."""
        notification_service.enabled = False

        result = notification_service.notify_state_change(
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.AWAITING_INPUT,
        )

        assert result is False

    @patch("src.services.notification_service.subprocess.run")
    def test_high_priority_notification_title(self, mock_run, notification_service):
        """High priority shows in notification title."""
        mock_run.return_value = MagicMock(returncode=0)

        notification_service.notify_state_change(
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.AWAITING_INPUT,
            priority_score=85,
        )

        call_args = mock_run.call_args[0][0]
        assert any("High Priority" in str(arg) for arg in call_args)

    @patch("src.services.notification_service.subprocess.run")
    def test_cooldown_prevents_spam(self, mock_run, notification_service):
        """Cooldown prevents notification spam."""
        mock_run.return_value = MagicMock(returncode=0)
        notification_service._cooldown_seconds = 10  # 10 second cooldown

        # First notification
        result1 = notification_service.notify_state_change(
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.AWAITING_INPUT,
        )

        # Second notification (should be blocked by cooldown)
        result2 = notification_service.notify_state_change(
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.AWAITING_INPUT,
        )

        assert result1 is True
        assert result2 is False
        assert mock_run.call_count == 1

    @patch("src.services.notification_service.subprocess.run")
    def test_cooldown_per_agent(self, mock_run, notification_service):
        """Cooldown is per-agent."""
        mock_run.return_value = MagicMock(returncode=0)
        notification_service._cooldown_seconds = 10

        # Notification for agent-1
        result1 = notification_service.notify_state_change(
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test-1",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.AWAITING_INPUT,
        )

        # Notification for agent-2 (should succeed, different agent)
        result2 = notification_service.notify_state_change(
            agent_id="agent-2",
            session_id="pane-2",
            session_name="claude-test-2",
            old_state=TaskState.PROCESSING,
            new_state=TaskState.AWAITING_INPUT,
        )

        assert result1 is True
        assert result2 is True
        assert mock_run.call_count == 2


class TestNotifyCustom:
    """Tests for notify_custom method."""

    @patch("src.services.notification_service.subprocess.run")
    def test_sends_custom_notification(self, mock_run, notification_service):
        """notify_custom sends custom notification."""
        mock_run.return_value = MagicMock(returncode=0)

        result = notification_service.notify_custom(
            title="Custom Title",
            message="Custom message",
        )

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "Custom Title" in call_args
        assert "Custom message" in call_args

    def test_no_notify_when_disabled(self, notification_service):
        """notify_custom respects enabled setting."""
        notification_service.enabled = False

        result = notification_service.notify_custom(
            title="Test",
            message="Test",
        )

        assert result is False


class TestTestNotification:
    """Tests for test_notification method."""

    @patch("src.services.notification_service.subprocess.run")
    def test_sends_test_notification(self, mock_run, notification_service):
        """test_notification sends a test notification."""
        mock_run.return_value = MagicMock(returncode=0)

        result = notification_service.test_notification()

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert any("Claude Headspace" in str(arg) for arg in call_args)
        assert any("Notifications are working" in str(arg) for arg in call_args)


class TestSendRawNotification:
    """Tests for _send_raw_notification method."""

    @patch("src.services.notification_service.subprocess.run")
    def test_handles_terminal_notifier_not_found(self, mock_run, notification_service):
        """Handles missing terminal-notifier gracefully."""
        mock_run.side_effect = FileNotFoundError("terminal-notifier not found")

        result = notification_service._send_raw_notification(
            title="Test",
            message="Test",
            session_id=None,
        )

        assert result is False

    @patch("src.services.notification_service.subprocess.run")
    def test_handles_timeout(self, mock_run, notification_service):
        """Handles subprocess timeout gracefully."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)

        result = notification_service._send_raw_notification(
            title="Test",
            message="Test",
            session_id=None,
        )

        assert result is False

    @patch("src.services.notification_service.subprocess.run")
    def test_handles_nonzero_returncode(self, mock_run, notification_service):
        """Handles non-zero return code."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")

        result = notification_service._send_raw_notification(
            title="Test",
            message="Test",
            session_id=None,
        )

        assert result is False

    @patch("src.services.notification_service.subprocess.run")
    def test_includes_click_to_focus_when_session_provided(
        self, mock_run, notification_service, mock_backend
    ):
        """Click-to-focus command included when session_id provided."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_backend.is_available.return_value = True

        notification_service._send_raw_notification(
            title="Test",
            message="Test",
            session_id="pane-123",
        )

        call_args = mock_run.call_args[0][0]
        assert "-execute" in call_args
        assert any("activate-pane" in str(arg) for arg in call_args)


class TestCooldown:
    """Tests for cooldown functionality."""

    def test_check_cooldown_first_time(self, notification_service):
        """First check always passes."""
        result = notification_service._check_cooldown("new-agent")
        assert result is True

    def test_check_cooldown_within_period(self, notification_service):
        """Check fails within cooldown period."""
        notification_service._cooldown_seconds = 60
        notification_service._last_notification["agent-1"] = datetime.now()

        result = notification_service._check_cooldown("agent-1")
        assert result is False

    def test_check_cooldown_after_period(self, notification_service):
        """Check passes after cooldown period."""
        notification_service._cooldown_seconds = 1
        notification_service._last_notification["agent-1"] = datetime.now() - timedelta(seconds=2)

        result = notification_service._check_cooldown("agent-1")
        assert result is True

    def test_reset_cooldowns(self, notification_service):
        """reset_cooldowns clears all cooldowns."""
        notification_service._last_notification = {
            "agent-1": datetime.now(),
            "agent-2": datetime.now(),
        }

        notification_service.reset_cooldowns()

        assert len(notification_service._last_notification) == 0


class TestNotificationType:
    """Tests for NotificationType enum."""

    def test_all_types_exist(self):
        """All expected notification types exist."""
        assert NotificationType.AWAITING_INPUT == "awaiting_input"
        assert NotificationType.COMPLETE == "complete"
        assert NotificationType.ERROR == "error"
        assert NotificationType.PRIORITY_CHANGE == "priority_change"


class TestNotificationPayload:
    """Tests for NotificationPayload dataclass."""

    def test_create_minimal(self):
        """NotificationPayload can be created with required fields."""
        payload = NotificationPayload(
            type=NotificationType.COMPLETE,
            title="Test",
            message="Test message",
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test",
        )

        assert payload.type == NotificationType.COMPLETE
        assert payload.is_high_priority is False

    def test_create_with_all_fields(self):
        """NotificationPayload can have all fields."""
        payload = NotificationPayload(
            type=NotificationType.AWAITING_INPUT,
            title="High Priority: Input Needed",
            message="Project X: Fix bug",
            agent_id="agent-1",
            session_id="pane-1",
            session_name="claude-test",
            project_name="Project X",
            priority_score=90,
            is_high_priority=True,
        )

        assert payload.project_name == "Project X"
        assert payload.is_high_priority is True


class TestSingleton:
    """Tests for singleton functionality."""

    def test_get_notification_service_returns_same_instance(self):
        """get_notification_service returns same instance."""
        reset_notification_service()

        with patch("src.services.notification_service.get_wezterm_backend"):
            service1 = get_notification_service()
            service2 = get_notification_service()

        assert service1 is service2

    def test_reset_notification_service_creates_new_instance(self):
        """reset_notification_service creates new instance."""
        with patch("src.services.notification_service.get_wezterm_backend"):
            service1 = get_notification_service()
            reset_notification_service()
            service2 = get_notification_service()

        assert service1 is not service2


class TestGetNotificationType:
    """Tests for _get_notification_type method."""

    def test_processing_to_awaiting(self, notification_service):
        """PROCESSING → AWAITING_INPUT returns AWAITING_INPUT."""
        result = notification_service._get_notification_type(
            TaskState.PROCESSING, TaskState.AWAITING_INPUT
        )
        assert result == NotificationType.AWAITING_INPUT

    def test_processing_to_complete(self, notification_service):
        """PROCESSING → COMPLETE returns COMPLETE."""
        result = notification_service._get_notification_type(
            TaskState.PROCESSING, TaskState.COMPLETE
        )
        assert result == NotificationType.COMPLETE

    def test_other_transitions_return_none(self, notification_service):
        """Other transitions return None."""
        assert (
            notification_service._get_notification_type(TaskState.IDLE, TaskState.COMMANDED) is None
        )
        assert (
            notification_service._get_notification_type(TaskState.COMMANDED, TaskState.PROCESSING)
            is None
        )
        assert (
            notification_service._get_notification_type(TaskState.COMPLETE, TaskState.IDLE) is None
        )
