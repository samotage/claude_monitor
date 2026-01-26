"""Tests for WezTerm backend."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.backends.wezterm import (
    WezTermBackend,
    _run_wezterm,
    get_wezterm_backend,
    reset_wezterm_backend,
)


@pytest.fixture(autouse=True)
def reset_backend():
    """Reset the backend singleton before each test."""
    reset_wezterm_backend()
    yield
    reset_wezterm_backend()


@pytest.fixture
def mock_wezterm_available():
    """Mock wezterm as available."""
    with patch("src.backends.wezterm.shutil.which") as mock_which:
        mock_which.return_value = "/usr/local/bin/wezterm"
        yield mock_which


@pytest.fixture
def backend(mock_wezterm_available):
    """Create a WezTerm backend with mocked availability."""
    return WezTermBackend()


class TestWezTermBackendInit:
    """Tests for WezTermBackend initialization."""

    def test_backend_name(self, backend):
        """Backend name is 'wezterm'."""
        assert backend.backend_name == "wezterm"

    def test_is_available_when_installed(self, mock_wezterm_available):  # noqa: ARG002
        """is_available returns True when wezterm is installed."""
        backend = WezTermBackend()
        assert backend.is_available() is True

    def test_is_available_when_not_installed(self):
        """is_available returns False when wezterm is not installed."""
        with patch("src.backends.wezterm.shutil.which") as mock_which:
            mock_which.return_value = None
            backend = WezTermBackend()
            assert backend.is_available() is False


class TestListSessions:
    """Tests for list_sessions method."""

    @patch("src.backends.wezterm._run_wezterm")
    def test_list_sessions_returns_panes(self, mock_run, backend):
        """list_sessions returns SessionInfo for each pane."""
        mock_run.return_value = (
            0,
            json.dumps(
                [
                    {
                        "pane_id": 1,
                        "title": "bash",
                        "tab_title": "claude-myproject-abc1",
                        "pid": 12345,
                        "tty_name": "/dev/ttys001",
                        "cwd": "/Users/test/project",
                    },
                    {
                        "pane_id": 2,
                        "title": "vim",
                        "tab_title": "",
                        "pid": 12346,
                        "tty_name": "/dev/ttys002",
                        "cwd": "/Users/test",
                    },
                ]
            ),
            "",
        )

        sessions = backend.list_sessions()

        assert len(sessions) == 2
        assert sessions[0].session_id == "1"
        assert sessions[0].name == "claude-myproject-abc1"
        assert sessions[0].pid == 12345
        assert sessions[0].tty == "/dev/ttys001"
        assert sessions[0].cwd == "/Users/test/project"

    @patch("src.backends.wezterm._run_wezterm")
    def test_list_sessions_empty_when_not_available(self, mock_run):  # noqa: ARG002
        """list_sessions returns empty list when wezterm not available."""
        with patch("src.backends.wezterm.shutil.which") as mock_which:
            mock_which.return_value = None
            backend = WezTermBackend()
            sessions = backend.list_sessions()
            assert sessions == []

    @patch("src.backends.wezterm._run_wezterm")
    def test_list_sessions_empty_on_error(self, mock_run, backend):
        """list_sessions returns empty list on command error."""
        mock_run.return_value = (1, "", "error")
        sessions = backend.list_sessions()
        assert sessions == []

    @patch("src.backends.wezterm._run_wezterm")
    def test_list_sessions_prefers_tab_title(self, mock_run, backend):
        """list_sessions uses tab_title for claude sessions."""
        mock_run.return_value = (
            0,
            json.dumps(
                [
                    {
                        "pane_id": 1,
                        "title": "✳ Claude Code",  # Claude overwrites pane title
                        "tab_title": "claude-myproject-abc1",  # But tab title persists
                        "pid": 12345,
                    },
                ]
            ),
            "",
        )

        sessions = backend.list_sessions()

        assert len(sessions) == 1
        assert sessions[0].name == "claude-myproject-abc1"
        assert sessions[0].title == "✳ Claude Code"  # Raw title preserved


class TestGetContent:
    """Tests for get_content method."""

    @patch("src.backends.wezterm._run_wezterm")
    def test_get_content_returns_text(self, mock_run, backend):
        """get_content returns captured text."""
        mock_run.return_value = (0, "Line 1\nLine 2\nLine 3\n", "")

        content = backend.get_content("1", lines=100)

        assert content == "Line 1\nLine 2\nLine 3\n"
        mock_run.assert_called_once_with("get-text", "--pane-id", "1", "--start-line", "-100")

    @patch("src.backends.wezterm._run_wezterm")
    def test_get_content_returns_none_on_error(self, mock_run, backend):
        """get_content returns None on command error."""
        mock_run.return_value = (1, "", "error")

        content = backend.get_content("1")

        assert content is None

    def test_get_content_returns_none_when_not_available(self):
        """get_content returns None when wezterm not available."""
        with patch("src.backends.wezterm.shutil.which") as mock_which:
            mock_which.return_value = None
            backend = WezTermBackend()
            content = backend.get_content("1")
            assert content is None


class TestSendText:
    """Tests for send_text method."""

    @patch("src.backends.wezterm._run_wezterm")
    def test_send_text_with_enter(self, mock_run, backend):
        """send_text sends text with newline."""
        mock_run.return_value = (0, "", "")

        result = backend.send_text("1", "hello", enter=True)

        assert result is True
        mock_run.assert_called_once_with("send-text", "--pane-id", "1", "--no-paste", "hello\n")

    @patch("src.backends.wezterm._run_wezterm")
    def test_send_text_without_enter(self, mock_run, backend):
        """send_text sends text without newline when enter=False."""
        mock_run.return_value = (0, "", "")

        result = backend.send_text("1", "hello", enter=False)

        assert result is True
        mock_run.assert_called_once_with("send-text", "--pane-id", "1", "--no-paste", "hello")

    @patch("src.backends.wezterm._run_wezterm")
    def test_send_text_returns_false_on_error(self, mock_run, backend):
        """send_text returns False on command error."""
        mock_run.return_value = (1, "", "error")

        result = backend.send_text("1", "hello")

        assert result is False

    def test_send_text_returns_false_when_not_available(self):
        """send_text returns False when wezterm not available."""
        with patch("src.backends.wezterm.shutil.which") as mock_which:
            mock_which.return_value = None
            backend = WezTermBackend()
            result = backend.send_text("1", "hello")
            assert result is False


class TestFocusPane:
    """Tests for focus_pane method."""

    @patch("src.backends.wezterm.subprocess.run")
    @patch("src.backends.wezterm._run_wezterm")
    def test_focus_pane_activates_pane_and_app(self, mock_run, mock_subprocess, backend):
        """focus_pane activates pane and brings app to foreground."""
        mock_run.return_value = (0, "", "")

        result = backend.focus_pane("1")

        assert result is True
        mock_run.assert_called_once_with("activate-pane", "--pane-id", "1")
        # Also calls osascript to activate WezTerm app
        mock_subprocess.assert_called_once()

    @patch("src.backends.wezterm._run_wezterm")
    def test_focus_pane_returns_false_on_error(self, mock_run, backend):
        """focus_pane returns False on command error."""
        mock_run.return_value = (1, "", "error")

        result = backend.focus_pane("1")

        assert result is False

    def test_focus_pane_returns_false_when_not_available(self):
        """focus_pane returns False when wezterm not available."""
        with patch("src.backends.wezterm.shutil.which") as mock_which:
            mock_which.return_value = None
            backend = WezTermBackend()
            result = backend.focus_pane("1")
            assert result is False


class TestGetClaudeSessions:
    """Tests for get_claude_sessions method."""

    @patch("src.backends.wezterm._run_wezterm")
    def test_get_claude_sessions_filters_by_prefix(self, mock_run, backend):
        """get_claude_sessions returns only sessions with claude- prefix."""
        mock_run.return_value = (
            0,
            json.dumps(
                [
                    {"pane_id": 1, "title": "claude-proj1-abc1", "tab_title": "", "pid": 1},
                    {"pane_id": 2, "title": "bash", "tab_title": "", "pid": 2},
                    {"pane_id": 3, "title": "vim", "tab_title": "claude-proj2-def2", "pid": 3},
                ]
            ),
            "",
        )

        sessions = backend.get_claude_sessions()

        assert len(sessions) == 2
        names = [s.name for s in sessions]
        assert "claude-proj1-abc1" in names
        assert "claude-proj2-def2" in names


class TestGetSessionByName:
    """Tests for get_session_by_name method."""

    @patch("src.backends.wezterm._run_wezterm")
    def test_get_session_by_name_found(self, mock_run, backend):
        """get_session_by_name returns session when found."""
        mock_run.return_value = (
            0,
            json.dumps(
                [
                    {"pane_id": 1, "title": "claude-myproject-abc1", "tab_title": "", "pid": 123},
                ]
            ),
            "",
        )

        session = backend.get_session_by_name("claude-myproject-abc1")

        assert session is not None
        assert session.session_id == "1"
        assert session.name == "claude-myproject-abc1"

    @patch("src.backends.wezterm._run_wezterm")
    def test_get_session_by_name_not_found(self, mock_run, backend):
        """get_session_by_name returns None when not found."""
        mock_run.return_value = (
            0,
            json.dumps(
                [
                    {"pane_id": 1, "title": "bash", "tab_title": "", "pid": 123},
                ]
            ),
            "",
        )

        session = backend.get_session_by_name("claude-nonexistent")

        assert session is None

    @patch("src.backends.wezterm._run_wezterm")
    def test_get_session_by_name_uses_cache(self, mock_run, backend):
        """get_session_by_name uses cache for repeated lookups."""
        mock_run.return_value = (
            0,
            json.dumps(
                [
                    {"pane_id": 1, "title": "claude-myproject-abc1", "tab_title": "", "pid": 123},
                ]
            ),
            "",
        )

        # First lookup populates cache
        session1 = backend.get_session_by_name("claude-myproject-abc1")
        # Second lookup should still work
        session2 = backend.get_session_by_name("claude-myproject-abc1")

        assert session1 is not None
        assert session2 is not None


class TestConvenienceMethods:
    """Tests for convenience methods that work with session names."""

    @patch("src.backends.wezterm._run_wezterm")
    def test_get_content_by_name(self, mock_run, backend):
        """get_content_by_name captures content by session name."""
        # First call: list sessions
        # Second call: get-text
        mock_run.side_effect = [
            (
                0,
                json.dumps(
                    [
                        {"pane_id": 1, "title": "claude-proj-abc1", "tab_title": "", "pid": 123},
                    ]
                ),
                "",
            ),
            (0, "Terminal content\n", ""),
        ]

        content = backend.get_content_by_name("claude-proj-abc1", lines=50)

        assert content == "Terminal content\n"

    @patch("src.backends.wezterm._run_wezterm")
    def test_send_text_by_name(self, mock_run, backend):
        """send_text_by_name sends text by session name."""
        mock_run.side_effect = [
            (
                0,
                json.dumps(
                    [
                        {"pane_id": 1, "title": "claude-proj-abc1", "tab_title": "", "pid": 123},
                    ]
                ),
                "",
            ),
            (0, "", ""),  # send-text result
        ]

        result = backend.send_text_by_name("claude-proj-abc1", "hello")

        assert result is True

    @patch("src.backends.wezterm.subprocess.run")
    @patch("src.backends.wezterm._run_wezterm")
    def test_focus_by_name(self, mock_run, mock_subprocess, backend):  # noqa: ARG002
        """focus_by_name focuses pane by session name."""
        mock_run.side_effect = [
            (
                0,
                json.dumps(
                    [
                        {"pane_id": 1, "title": "claude-proj-abc1", "tab_title": "", "pid": 123},
                    ]
                ),
                "",
            ),
            (0, "", ""),  # activate-pane result
        ]

        result = backend.focus_by_name("claude-proj-abc1")

        assert result is True


class TestRunWezterm:
    """Tests for _run_wezterm helper function."""

    @patch("src.backends.wezterm.subprocess.run")
    def test_run_wezterm_success(self, mock_subprocess):
        """_run_wezterm returns success result."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="output",
            stderr="",
        )

        returncode, stdout, stderr = _run_wezterm("list")

        assert returncode == 0
        assert stdout == "output"
        assert stderr == ""

    @patch("src.backends.wezterm.subprocess.run")
    def test_run_wezterm_timeout(self, mock_subprocess):
        """_run_wezterm handles timeout."""
        import subprocess

        mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 10)

        returncode, stdout, stderr = _run_wezterm("list")

        assert returncode == 1
        assert "timed out" in stderr.lower()

    @patch("src.backends.wezterm.subprocess.run")
    def test_run_wezterm_not_found(self, mock_subprocess):
        """_run_wezterm handles command not found."""
        mock_subprocess.side_effect = FileNotFoundError()

        returncode, stdout, stderr = _run_wezterm("list")

        assert returncode == 1
        assert "not found" in stderr.lower()


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_wezterm_backend_returns_same_instance(self, mock_wezterm_available):  # noqa: ARG002
        """get_wezterm_backend returns the same instance."""
        backend1 = get_wezterm_backend()
        backend2 = get_wezterm_backend()

        assert backend1 is backend2

    def test_reset_wezterm_backend_creates_new_instance(self, mock_wezterm_available):  # noqa: ARG002
        """reset_wezterm_backend allows new instance creation."""
        backend1 = get_wezterm_backend()
        reset_wezterm_backend()
        backend2 = get_wezterm_backend()

        assert backend1 is not backend2


class TestErrorHandling:
    """Tests for error handling edge cases."""

    @patch("src.backends.wezterm._run_wezterm")
    def test_list_sessions_handles_invalid_json(self, mock_run, backend):
        """list_sessions handles invalid JSON response."""
        mock_run.return_value = (0, "not valid json", "")

        sessions = backend.list_sessions()

        assert sessions == []

    @patch("src.backends.wezterm._run_wezterm")
    def test_get_session_by_name_removes_stale_cache(self, mock_run, backend):
        """get_session_by_name removes stale cache entries."""
        # First call: populate cache with session
        mock_run.return_value = (
            0,
            json.dumps(
                [
                    {"pane_id": 1, "title": "claude-proj-abc1", "tab_title": "", "pid": 123},
                ]
            ),
            "",
        )
        backend.list_sessions()  # Populate cache

        # Session no longer exists
        mock_run.return_value = (0, json.dumps([]), "")

        session = backend.get_session_by_name("claude-proj-abc1")

        # Should return None and clean cache
        assert session is None
