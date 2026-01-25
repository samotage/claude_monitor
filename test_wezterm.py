"""Tests for WezTerm session integration functionality."""

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from lib.backends.wezterm import (
    is_wezterm_available,
    session_exists,
    list_sessions,
    send_keys,
    capture_pane,
    create_session,
    kill_session,
    get_session_info,
    get_claude_sessions,
    slugify_project_name,
    get_session_name_for_project,
    _run_wezterm,
    WezTermBackend,
)


@pytest.fixture(autouse=True)
def reset_wezterm_state():
    """Reset WezTerm backend state before each test."""
    import lib.backends.wezterm as wezterm_backend
    from lib.backends import reset_backend

    # Store original state
    original_available = wezterm_backend._wezterm_available
    original_debug = wezterm_backend._debug_logging_enabled
    original_map = wezterm_backend._session_pane_map.copy()

    # Reset cache so mocks can take effect
    wezterm_backend._wezterm_available = None
    wezterm_backend._session_pane_map = {}
    reset_backend()

    yield

    # Restore original state
    wezterm_backend._wezterm_available = original_available
    wezterm_backend._debug_logging_enabled = original_debug
    wezterm_backend._session_pane_map = original_map
    reset_backend()


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestSlugifyProjectName:
    """Tests for project name slugification."""

    def test_simple_name(self):
        """Simple lowercase name stays the same."""
        assert slugify_project_name("myproject") == "myproject"

    def test_uppercase_converted(self):
        """Uppercase letters are converted to lowercase."""
        assert slugify_project_name("MyProject") == "myproject"

    def test_spaces_to_hyphens(self):
        """Spaces are converted to hyphens."""
        assert slugify_project_name("my project") == "my-project"


class TestGetSessionNameForProject:
    """Tests for getting WezTerm session names from project names."""

    def test_simple_project(self):
        """Simple project name gets claude- prefix with hash suffix."""
        result = get_session_name_for_project("myproject")
        assert result.startswith("claude-myproject-")
        assert len(result) == len("claude-myproject-") + 4  # 4-char hash suffix


# =============================================================================
# WezTerm Availability Tests
# =============================================================================


class TestIsWezTermAvailable:
    """Tests for WezTerm availability checking."""

    @patch("shutil.which")
    def test_wezterm_available(self, mock_which):
        """Returns True when WezTerm is found."""
        import lib.backends.wezterm as wezterm_backend
        wezterm_backend._wezterm_available = None

        mock_which.return_value = "/usr/local/bin/wezterm"
        assert is_wezterm_available() is True
        mock_which.assert_called_once_with("wezterm")

    @patch("shutil.which")
    def test_wezterm_not_available(self, mock_which):
        """Returns False when WezTerm is not found."""
        import lib.backends.wezterm as wezterm_backend
        wezterm_backend._wezterm_available = None

        mock_which.return_value = None
        assert is_wezterm_available() is False


# =============================================================================
# WezTerm Command Execution Tests
# =============================================================================


class TestRunWezTerm:
    """Tests for the internal _run_wezterm helper."""

    @patch("lib.backends.wezterm.subprocess.run")
    def test_successful_command(self, mock_run):
        """Successfully executes a wezterm command."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"pane_id": 0}]',
            stderr=""
        )

        code, stdout, stderr = _run_wezterm("list", "--format", "json")

        assert code == 0
        assert stdout == '[{"pane_id": 0}]'
        assert stderr == ""
        mock_run.assert_called_once()

    @patch("lib.backends.wezterm.subprocess.run")
    def test_failed_command(self, mock_run):
        """Handles failed wezterm command."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error"
        )

        code, stdout, stderr = _run_wezterm("list")

        assert code == 1
        assert stderr == "error"

    @patch("lib.backends.wezterm.subprocess.run")
    def test_timeout(self, mock_run):
        """Handles command timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="wezterm", timeout=10)

        code, stdout, stderr = _run_wezterm("list")

        assert code == 1
        assert stderr == "Command timed out"

    @patch("lib.backends.wezterm.subprocess.run")
    def test_wezterm_not_found(self, mock_run):
        """Handles wezterm not being installed."""
        mock_run.side_effect = FileNotFoundError()

        code, stdout, stderr = _run_wezterm("list")

        assert code == 1
        assert stderr == "wezterm not found"


# =============================================================================
# Session Operations Tests
# =============================================================================


class TestListSessions:
    """Tests for listing WezTerm sessions."""

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_list_sessions(self, mock_run, mock_which):
        """Lists sessions successfully."""
        panes_json = json.dumps([
            {"pane_id": 0, "title": "claude-project1-abc1", "workspace": "claude-monitor"},
            {"pane_id": 1, "title": "other-session", "workspace": "default"},
        ])
        mock_run.return_value = (0, panes_json, "")

        sessions = list_sessions()

        assert len(sessions) == 2
        assert sessions[0]["name"] == "claude-project1-abc1"
        assert sessions[0]["pane_id"] == "0"
        assert sessions[1]["name"] == "other-session"

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_list_sessions_empty(self, mock_run, mock_which):
        """Returns empty list when no sessions."""
        mock_run.return_value = (0, "[]", "")

        sessions = list_sessions()
        assert sessions == []

    @patch("lib.backends.wezterm.shutil.which", return_value=None)
    def test_list_sessions_wezterm_unavailable(self, mock_which):
        """Returns empty list when WezTerm unavailable."""
        sessions = list_sessions()
        assert sessions == []


class TestSessionExists:
    """Tests for checking if a WezTerm session exists."""

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_session_exists_by_title(self, mock_run, mock_which):
        """Returns True when session title matches."""
        panes_json = json.dumps([
            {"pane_id": 0, "title": "claude-project-abc1", "workspace": "claude-monitor"},
        ])
        mock_run.return_value = (0, panes_json, "")

        assert session_exists("claude-project-abc1") is True

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_session_not_exists(self, mock_run, mock_which):
        """Returns False when session doesn't exist."""
        mock_run.return_value = (0, "[]", "")

        assert session_exists("nonexistent") is False

    @patch("lib.backends.wezterm.shutil.which", return_value=None)
    def test_wezterm_not_available(self, mock_which):
        """Returns False when WezTerm is not available."""
        assert session_exists("my-session") is False


class TestGetClaudeSessions:
    """Tests for finding Claude-specific sessions."""

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_get_claude_sessions(self, mock_run, mock_which):
        """Filters to only Claude sessions."""
        panes_json = json.dumps([
            {"pane_id": 0, "title": "claude-myproject-abc1", "workspace": "claude-monitor", "pid": 123, "tty_name": "/dev/ttys001", "cwd": "/path/to/project"},
            {"pane_id": 1, "title": "other-session", "workspace": "default", "pid": 456},
            {"pane_id": 2, "title": "claude-another-def2", "workspace": "claude-monitor", "pid": 789, "tty_name": "/dev/ttys002", "cwd": "/path/to/another"},
        ])
        mock_run.return_value = (0, panes_json, "")

        sessions = get_claude_sessions()

        assert len(sessions) == 2
        assert sessions[0]["name"] == "claude-myproject-abc1"
        assert sessions[1]["name"] == "claude-another-def2"

    @patch("lib.backends.wezterm.shutil.which", return_value=None)
    def test_get_claude_sessions_wezterm_unavailable(self, mock_which):
        """Returns empty list when WezTerm unavailable."""
        sessions = get_claude_sessions()
        assert sessions == []


class TestSendKeys:
    """Tests for sending keys to WezTerm sessions."""

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_send_keys_with_enter(self, mock_run, mock_which):
        """Sends keys with Enter."""
        panes_json = json.dumps([
            {"pane_id": 0, "title": "claude-project-abc1"},
        ])
        # First call for list (session lookup), second for send-text
        mock_run.side_effect = [(0, panes_json, ""), (0, "", "")]

        result = send_keys("claude-project-abc1", "hello world", enter=True)

        assert result is True
        # Check that send-text was called correctly
        calls = mock_run.call_args_list
        assert "send-text" in calls[-1][0]
        assert "hello world\n" in calls[-1][0]

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_send_keys_without_enter(self, mock_run, mock_which):
        """Sends keys without Enter."""
        panes_json = json.dumps([
            {"pane_id": 0, "title": "claude-project-abc1"},
        ])
        mock_run.side_effect = [(0, panes_json, ""), (0, "", "")]

        result = send_keys("claude-project-abc1", "hello", enter=False)

        assert result is True
        calls = mock_run.call_args_list
        # Should have "hello" without newline
        assert "hello" in calls[-1][0]

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_send_keys_session_not_exists(self, mock_run, mock_which):
        """Returns False when session doesn't exist."""
        mock_run.return_value = (0, "[]", "")

        result = send_keys("nonexistent", "hello")
        assert result is False

    @patch("lib.backends.wezterm.shutil.which", return_value=None)
    def test_send_keys_wezterm_unavailable(self, mock_which):
        """Returns False when WezTerm unavailable."""
        result = send_keys("my-session", "hello")
        assert result is False


class TestCapturPane:
    """Tests for capturing WezTerm pane output."""

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_capture_pane(self, mock_run, mock_which):
        """Captures pane output successfully."""
        panes_json = json.dumps([
            {"pane_id": 0, "title": "claude-project-abc1"},
        ])
        mock_run.side_effect = [
            (0, panes_json, ""),  # list sessions
            (0, "line1\nline2\nline3\n", ""),  # get-text
        ]

        output = capture_pane("claude-project-abc1", lines=100)

        assert output == "line1\nline2\nline3\n"
        # Check that get-text was called with correct args
        calls = mock_run.call_args_list
        assert "get-text" in calls[-1][0]

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_capture_pane_session_not_exists(self, mock_run, mock_which):
        """Returns None when session doesn't exist."""
        mock_run.return_value = (0, "[]", "")

        output = capture_pane("nonexistent")
        assert output is None


class TestCreateSession:
    """Tests for creating WezTerm sessions."""

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_create_session_basic(self, mock_run, mock_which):
        """Creates a basic session."""
        # First call for session_exists (returns empty), second for spawn
        mock_run.side_effect = [(0, "[]", ""), (0, "123", "")]

        result = create_session("my-session")

        assert result is True
        calls = mock_run.call_args_list
        assert "spawn" in calls[-1][0]

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_create_session_with_directory(self, mock_run, mock_which):
        """Creates session with working directory."""
        mock_run.side_effect = [(0, "[]", ""), (0, "123", "")]

        result = create_session("my-session", working_dir="/path/to/project")

        assert result is True
        calls = mock_run.call_args_list
        assert "--cwd" in calls[-1][0]
        assert "/path/to/project" in calls[-1][0]

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_create_session_already_exists(self, mock_run, mock_which):
        """Returns False when session already exists."""
        panes_json = json.dumps([
            {"pane_id": 0, "title": "my-session"},
        ])
        mock_run.return_value = (0, panes_json, "")

        result = create_session("my-session")
        assert result is False


class TestKillSession:
    """Tests for killing WezTerm sessions."""

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_kill_session(self, mock_run, mock_which):
        """Kills session successfully."""
        panes_json = json.dumps([
            {"pane_id": 0, "title": "my-session"},
        ])
        mock_run.side_effect = [(0, panes_json, ""), (0, "", "")]

        result = kill_session("my-session")

        assert result is True
        calls = mock_run.call_args_list
        assert "kill-pane" in calls[-1][0]


class TestGetSessionInfo:
    """Tests for getting detailed session info."""

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_get_session_info(self, mock_run, mock_which):
        """Gets session info successfully."""
        panes_json = json.dumps([
            {
                "pane_id": 0,
                "title": "my-session",
                "pid": 12345,
                "tty_name": "/dev/ttys001",
                "cwd": "/path/to/project",
            },
        ])
        mock_run.return_value = (0, panes_json, "")

        info = get_session_info("my-session")

        assert info is not None
        assert info["name"] == "my-session"
        assert info["pane_pid"] == 12345
        assert info["pane_tty"] == "/dev/ttys001"
        assert info["pane_path"] == "/path/to/project"

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_get_session_info_not_exists(self, mock_run, mock_which):
        """Returns None when session doesn't exist."""
        mock_run.return_value = (0, "[]", "")

        info = get_session_info("nonexistent")
        assert info is None


# =============================================================================
# Backend Class Tests
# =============================================================================


class TestWezTermBackend:
    """Tests for the WezTermBackend class."""

    def test_backend_name(self):
        """Backend name is 'wezterm'."""
        backend = WezTermBackend()
        assert backend.backend_name == "wezterm"

    @patch("lib.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    @patch("lib.backends.wezterm._run_wezterm")
    def test_focus_window(self, mock_run, mock_which):
        """focus_window uses activate-pane."""
        import lib.backends.wezterm as wezterm_backend
        wezterm_backend._wezterm_available = None

        panes_json = json.dumps([
            {"pane_id": 0, "title": "my-session"},
        ])
        mock_run.side_effect = [(0, panes_json, ""), (0, "", "")]

        backend = WezTermBackend()
        result = backend.focus_window("my-session")

        assert result is True
        calls = mock_run.call_args_list
        assert "activate-pane" in calls[-1][0]


# =============================================================================
# Backend Factory Tests
# =============================================================================


class TestBackendFactory:
    """Tests for the backend factory function."""

    def test_get_tmux_backend(self):
        """Factory returns TmuxBackend for 'tmux'."""
        from lib.backends import get_backend, reset_backend
        reset_backend()

        backend = get_backend("tmux")
        assert backend.backend_name == "tmux"

    def test_get_wezterm_backend(self):
        """Factory returns WezTermBackend for 'wezterm'."""
        from lib.backends import get_backend, reset_backend
        reset_backend()

        backend = get_backend("wezterm")
        assert backend.backend_name == "wezterm"

    def test_unknown_backend_raises(self):
        """Factory raises ValueError for unknown backend."""
        from lib.backends import get_backend, reset_backend
        reset_backend()

        with pytest.raises(ValueError) as exc_info:
            get_backend("unknown")
        assert "Unknown terminal backend" in str(exc_info.value)
