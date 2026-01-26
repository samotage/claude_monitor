"""Tests for deprecated tmux backend."""

import warnings
from unittest.mock import MagicMock, patch

import pytest

from src.backends.tmux import (
    TmuxBackend,
    _run_tmux,
    get_tmux_backend,
    reset_tmux_backend,
)


@pytest.fixture(autouse=True)
def reset_backend():
    """Reset the backend singleton before each test."""
    reset_tmux_backend()
    yield
    reset_tmux_backend()


@pytest.fixture
def mock_tmux_available():
    """Mock tmux as available."""
    with (
        patch("src.backends.tmux.shutil.which") as mock_which,
        patch("src.backends.tmux._run_tmux") as mock_run,
    ):
        mock_which.return_value = "/usr/bin/tmux"
        mock_run.return_value = (0, "", "")  # Server running
        yield mock_which, mock_run


class TestTmuxBackendDeprecation:
    """Tests for deprecation warnings."""

    def test_init_emits_deprecation_warning(self):
        """TmuxBackend init emits DeprecationWarning."""
        with (
            patch("src.backends.tmux.shutil.which") as mock_which,
            warnings.catch_warnings(record=True) as w,
        ):
            mock_which.return_value = "/usr/bin/tmux"
            warnings.simplefilter("always")
            TmuxBackend()

            assert len(w) >= 1
            assert any(issubclass(warning.category, DeprecationWarning) for warning in w)

    def test_get_tmux_backend_emits_warning(self):
        """get_tmux_backend emits deprecation warning."""
        with (
            patch("src.backends.tmux.shutil.which") as mock_which,
            warnings.catch_warnings(record=True) as w,
        ):
            mock_which.return_value = "/usr/bin/tmux"
            warnings.simplefilter("always")
            get_tmux_backend()

            assert len(w) >= 1


class TestTmuxBackendInit:
    """Tests for TmuxBackend initialization."""

    def test_backend_name(self):
        """Backend name is 'tmux'."""
        with (
            patch("src.backends.tmux.shutil.which") as mock_which,
            warnings.catch_warnings(),
        ):
            mock_which.return_value = "/usr/bin/tmux"
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            assert backend.backend_name == "tmux"

    def test_is_available_when_installed_and_running(self, mock_tmux_available):  # noqa: ARG002
        """is_available returns True when tmux is installed and server running."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            assert backend.is_available() is True

    def test_is_available_when_not_installed(self):
        """is_available returns False when tmux is not installed."""
        with (
            patch("src.backends.tmux.shutil.which") as mock_which,
            warnings.catch_warnings(),
        ):
            mock_which.return_value = None
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            assert backend.is_available() is False


class TestListSessions:
    """Tests for list_sessions method."""

    def test_list_sessions_empty_when_not_available(self):
        """list_sessions returns empty list when tmux not available."""
        with (
            patch("src.backends.tmux.shutil.which") as mock_which,
            warnings.catch_warnings(),
        ):
            mock_which.return_value = None
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            sessions = backend.list_sessions()
            assert sessions == []

    def test_list_sessions_parses_output(self, mock_tmux_available):
        """list_sessions parses tmux output correctly."""
        mock_which, mock_run = mock_tmux_available
        mock_run.side_effect = [
            (0, "", ""),  # is_available check
            (0, "session1|$1|12345|/dev/ttys001|/home/user|bash\n", ""),  # list-panes
        ]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            sessions = backend.list_sessions()

            assert len(sessions) == 1
            assert sessions[0].name == "session1"
            assert sessions[0].session_id == "$1"
            assert sessions[0].pid == 12345


class TestGetContent:
    """Tests for get_content method."""

    def test_get_content_returns_none_when_not_available(self):
        """get_content returns None when tmux not available."""
        with (
            patch("src.backends.tmux.shutil.which") as mock_which,
            warnings.catch_warnings(),
        ):
            mock_which.return_value = None
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            content = backend.get_content("$1")
            assert content is None

    def test_get_content_captures_pane(self, mock_tmux_available):
        """get_content captures pane content."""
        mock_which, mock_run = mock_tmux_available
        mock_run.side_effect = [
            (0, "", ""),  # is_available
            (0, "line1\nline2\n", ""),  # capture-pane
        ]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            content = backend.get_content("$1", lines=50)

            assert content == "line1\nline2\n"


class TestSendText:
    """Tests for send_text method."""

    def test_send_text_returns_false_when_not_available(self):
        """send_text returns False when tmux not available."""
        with (
            patch("src.backends.tmux.shutil.which") as mock_which,
            warnings.catch_warnings(),
        ):
            mock_which.return_value = None
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            result = backend.send_text("$1", "hello")
            assert result is False

    def test_send_text_sends_keys(self, mock_tmux_available):
        """send_text sends keys to pane."""
        mock_which, mock_run = mock_tmux_available
        mock_run.side_effect = [
            (0, "", ""),  # is_available
            (0, "", ""),  # send-keys
        ]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            result = backend.send_text("$1", "hello")

            assert result is True


class TestFocusPane:
    """Tests for focus_pane method."""

    def test_focus_pane_returns_false_when_not_available(self):
        """focus_pane returns False when tmux not available."""
        with (
            patch("src.backends.tmux.shutil.which") as mock_which,
            warnings.catch_warnings(),
        ):
            mock_which.return_value = None
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            result = backend.focus_pane("$1")
            assert result is False

    def test_focus_pane_selects_pane(self, mock_tmux_available):
        """focus_pane selects the pane."""
        mock_which, mock_run = mock_tmux_available
        mock_run.side_effect = [
            (0, "", ""),  # is_available
            (0, "", ""),  # select-pane
        ]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            backend = TmuxBackend()
            result = backend.focus_pane("$1")

            assert result is True


class TestRunTmux:
    """Tests for _run_tmux helper function."""

    @patch("src.backends.tmux.subprocess.run")
    def test_run_tmux_success(self, mock_subprocess):
        """_run_tmux returns success result."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="output",
            stderr="",
        )

        returncode, stdout, stderr = _run_tmux("list-sessions")

        assert returncode == 0
        assert stdout == "output"

    @patch("src.backends.tmux.subprocess.run")
    def test_run_tmux_timeout(self, mock_subprocess):
        """_run_tmux handles timeout."""
        import subprocess

        mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 10)

        returncode, stdout, stderr = _run_tmux("list-sessions")

        assert returncode == 1
        assert "timed out" in stderr.lower()

    @patch("src.backends.tmux.subprocess.run")
    def test_run_tmux_not_found(self, mock_subprocess):
        """_run_tmux handles command not found."""
        mock_subprocess.side_effect = FileNotFoundError()

        returncode, stdout, stderr = _run_tmux("list-sessions")

        assert returncode == 1
        assert "not found" in stderr.lower()


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_tmux_backend_returns_same_instance(self, mock_tmux_available):  # noqa: ARG002
        """get_tmux_backend returns the same instance."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            backend1 = get_tmux_backend()
            backend2 = get_tmux_backend()

            assert backend1 is backend2

    def test_reset_tmux_backend_creates_new_instance(self, mock_tmux_available):  # noqa: ARG002
        """reset_tmux_backend allows new instance creation."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            backend1 = get_tmux_backend()
            reset_tmux_backend()
            backend2 = get_tmux_backend()

            assert backend1 is not backend2
