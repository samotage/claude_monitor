"""Tests for tmux session integration functionality."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from lib.tmux import (
    is_tmux_available,
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
    _run_tmux,
)


@pytest.fixture(autouse=True)
def reset_tmux_state():
    """Reset tmux backend state before each test."""
    import lib.backends.tmux as tmux_backend
    from lib.backends import reset_backend

    # Store original state
    original_available = tmux_backend._tmux_available
    original_debug = tmux_backend._debug_logging_enabled

    # Reset cache so mocks can take effect
    tmux_backend._tmux_available = None
    reset_backend()

    yield

    # Restore original state
    tmux_backend._tmux_available = original_available
    tmux_backend._debug_logging_enabled = original_debug
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

    def test_underscores_to_hyphens(self):
        """Underscores are converted to hyphens."""
        assert slugify_project_name("my_project") == "my-project"

    def test_special_chars_removed(self):
        """Special characters are removed."""
        assert slugify_project_name("my!@#project") == "myproject"

    def test_multiple_hyphens_collapsed(self):
        """Multiple consecutive hyphens are collapsed."""
        assert slugify_project_name("my  project") == "my-project"

    def test_leading_trailing_hyphens_removed(self):
        """Leading and trailing hyphens are removed."""
        assert slugify_project_name("-my-project-") == "my-project"

    def test_empty_returns_unnamed(self):
        """Empty string returns 'unnamed'."""
        assert slugify_project_name("") == "unnamed"

    def test_special_only_returns_unnamed(self):
        """String with only special chars returns 'unnamed'."""
        assert slugify_project_name("!@#$%") == "unnamed"


class TestGetSessionNameForProject:
    """Tests for getting tmux session names from project names."""

    def test_simple_project(self):
        """Simple project name gets claude- prefix with hash suffix."""
        result = get_session_name_for_project("myproject")
        assert result.startswith("claude-myproject-")
        assert len(result) == len("claude-myproject-") + 4  # 4-char hash suffix

    def test_complex_project_name(self):
        """Complex project name is slugified with claude- prefix and hash suffix."""
        result = get_session_name_for_project("My Project Name")
        assert result.startswith("claude-my-project-name-")
        assert len(result) == len("claude-my-project-name-") + 4  # 4-char hash suffix

    def test_collision_prevention(self):
        """Different project names with same slug get different session names."""
        # These would collide without hash suffix
        name1 = get_session_name_for_project("My Project")
        name2 = get_session_name_for_project("my_project")
        name3 = get_session_name_for_project("MY PROJECT")
        # All slugify to "my-project" but should have different hashes
        assert name1 != name2
        assert name2 != name3
        assert name1 != name3


# =============================================================================
# tmux Availability Tests
# =============================================================================


class TestIsTmuxAvailable:
    """Tests for tmux availability checking."""

    @patch("shutil.which")
    def test_tmux_available(self, mock_which):
        """Returns True when tmux is found."""
        # Reset the cached value in the backends module
        import lib.backends.tmux as tmux_backend
        tmux_backend._tmux_available = None

        mock_which.return_value = "/usr/local/bin/tmux"
        assert is_tmux_available() is True
        mock_which.assert_called_once_with("tmux")

    @patch("shutil.which")
    def test_tmux_not_available(self, mock_which):
        """Returns False when tmux is not found."""
        import lib.backends.tmux as tmux_backend
        tmux_backend._tmux_available = None

        mock_which.return_value = None
        assert is_tmux_available() is False


# =============================================================================
# tmux Command Execution Tests
# =============================================================================


class TestRunTmux:
    """Tests for the internal _run_tmux helper."""

    @patch("lib.backends.tmux.subprocess.run")
    def test_successful_command(self, mock_run):
        """Successfully executes a tmux command."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="session1\nsession2\n",
            stderr=""
        )

        code, stdout, stderr = _run_tmux("list-sessions")

        assert code == 0
        assert stdout == "session1\nsession2\n"
        assert stderr == ""
        mock_run.assert_called_once()

    @patch("lib.backends.tmux.subprocess.run")
    def test_failed_command(self, mock_run):
        """Handles failed tmux command."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="no server running"
        )

        code, stdout, stderr = _run_tmux("list-sessions")

        assert code == 1
        assert stderr == "no server running"

    @patch("lib.backends.tmux.subprocess.run")
    def test_timeout(self, mock_run):
        """Handles command timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=10)

        code, stdout, stderr = _run_tmux("list-sessions")

        assert code == 1
        assert stderr == "Command timed out"

    @patch("lib.backends.tmux.subprocess.run")
    def test_tmux_not_found(self, mock_run):
        """Handles tmux not being installed."""
        mock_run.side_effect = FileNotFoundError()

        code, stdout, stderr = _run_tmux("list-sessions")

        assert code == 1
        assert stderr == "tmux not found"


# =============================================================================
# Session Operations Tests
# =============================================================================


class TestSessionExists:
    """Tests for checking if a tmux session exists."""

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_session_exists(self, mock_run, mock_which):
        """Returns True when session exists."""
        mock_run.return_value = (0, "", "")

        assert session_exists("my-session") is True
        mock_run.assert_called_once_with("has-session", "-t", "my-session")

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_session_not_exists(self, mock_run, mock_which):
        """Returns False when session doesn't exist."""
        mock_run.return_value = (1, "", "session not found")

        assert session_exists("my-session") is False

    @patch("lib.backends.tmux.shutil.which", return_value=None)
    def test_tmux_not_available(self, mock_which):
        """Returns False when tmux is not available."""
        assert session_exists("my-session") is False


class TestListSessions:
    """Tests for listing tmux sessions."""

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_list_sessions(self, mock_run, mock_which):
        """Lists sessions successfully."""
        mock_run.return_value = (0, "session1:1234567890:0:1\nsession2:1234567891:1:2\n", "")

        sessions = list_sessions()

        assert len(sessions) == 2
        assert sessions[0]["name"] == "session1"
        assert sessions[0]["attached"] is False
        assert sessions[1]["name"] == "session2"
        assert sessions[1]["attached"] is True

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_list_sessions_empty(self, mock_run, mock_which):
        """Returns empty list when no sessions."""
        mock_run.return_value = (1, "", "no server running")

        sessions = list_sessions()
        assert sessions == []

    @patch("lib.backends.tmux.shutil.which", return_value=None)
    def test_list_sessions_tmux_unavailable(self, mock_which):
        """Returns empty list when tmux unavailable."""
        sessions = list_sessions()
        assert sessions == []


class TestSendKeys:
    """Tests for sending keys to tmux sessions."""

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_send_keys_with_enter(self, mock_run, mock_which):
        """Sends keys with Enter."""
        # First call for session_exists (has-session), second for send-keys
        mock_run.side_effect = [(0, "", ""), (0, "", "")]

        result = send_keys("my-session", "hello world", enter=True)

        assert result is True
        # Check that send-keys was called correctly (second call)
        calls = mock_run.call_args_list
        assert calls[-1] == (("send-keys", "-t", "my-session", "hello world", "Enter"),)

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_send_keys_without_enter(self, mock_run, mock_which):
        """Sends keys without Enter."""
        # First call for session_exists, second for send-keys
        mock_run.side_effect = [(0, "", ""), (0, "", "")]

        result = send_keys("my-session", "hello", enter=False)

        assert result is True
        # Check that send-keys was called correctly (second call)
        calls = mock_run.call_args_list
        assert calls[-1] == (("send-keys", "-t", "my-session", "hello"),)

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_send_keys_session_not_exists(self, mock_run, mock_which):
        """Returns False when session doesn't exist."""
        mock_run.return_value = (1, "", "session not found")

        result = send_keys("my-session", "hello")
        assert result is False

    @patch("lib.backends.tmux.shutil.which", return_value=None)
    def test_send_keys_tmux_unavailable(self, mock_which):
        """Returns False when tmux unavailable."""
        result = send_keys("my-session", "hello")
        assert result is False


class TestCapturPane:
    """Tests for capturing tmux pane output."""

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_capture_pane(self, mock_run, mock_which):
        """Captures pane output successfully."""
        # First call for session_exists, second for capture-pane
        mock_run.side_effect = [(0, "", ""), (0, "line1\nline2\nline3\n", "")]

        output = capture_pane("my-session", lines=100)

        assert output == "line1\nline2\nline3\n"
        # Check that capture-pane was called correctly (second call)
        calls = mock_run.call_args_list
        assert calls[-1] == (("capture-pane", "-t", "my-session", "-p", "-S", "-100"),)

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_capture_pane_session_not_exists(self, mock_run, mock_which):
        """Returns None when session doesn't exist."""
        mock_run.return_value = (1, "", "session not found")

        output = capture_pane("my-session")
        assert output is None


class TestCreateSession:
    """Tests for creating tmux sessions."""

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_create_session_basic(self, mock_run, mock_which):
        """Creates a basic session."""
        # First call for session_exists (returns not found), second for new-session
        mock_run.side_effect = [(1, "", "session not found"), (0, "", "")]

        result = create_session("my-session")

        assert result is True
        # Check that new-session was called correctly (second call)
        calls = mock_run.call_args_list
        assert calls[-1] == (("new-session", "-d", "-s", "my-session"),)

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_create_session_with_directory(self, mock_run, mock_which):
        """Creates session with working directory."""
        # First call for session_exists (returns not found), second for new-session
        mock_run.side_effect = [(1, "", "session not found"), (0, "", "")]

        result = create_session("my-session", working_dir="/path/to/project")

        assert result is True
        # Check that new-session was called correctly (second call)
        calls = mock_run.call_args_list
        assert calls[-1] == (("new-session", "-d", "-s", "my-session", "-c", "/path/to/project"),)

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_create_session_already_exists(self, mock_run, mock_which):
        """Returns False when session already exists."""
        mock_run.return_value = (0, "", "")  # session_exists returns True

        result = create_session("my-session")
        assert result is False


class TestKillSession:
    """Tests for killing tmux sessions."""

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_kill_session(self, mock_run, mock_which):
        """Kills session successfully."""
        mock_run.return_value = (0, "", "")

        result = kill_session("my-session")

        assert result is True
        mock_run.assert_called_once_with("kill-session", "-t", "my-session")


# =============================================================================
# Session Info Tests
# =============================================================================


class TestGetSessionInfo:
    """Tests for getting detailed session info."""

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_get_session_info(self, mock_run, mock_which):
        """Gets session info successfully."""
        # First call for session_exists, second for list-panes
        mock_run.side_effect = [
            (0, "", ""),  # session_exists
            (0, "my-session:1234567890:1:1:12345:/dev/ttys001:/path/to/project\n", ""),  # list-panes
        ]

        info = get_session_info("my-session")

        assert info is not None
        assert info["name"] == "my-session"
        assert info["attached"] is True
        assert info["pane_pid"] == 12345
        assert info["pane_tty"] == "/dev/ttys001"
        assert info["pane_path"] == "/path/to/project"

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_get_session_info_not_exists(self, mock_run, mock_which):
        """Returns None when session doesn't exist."""
        mock_run.return_value = (1, "", "session not found")

        info = get_session_info("my-session")
        assert info is None


class TestGetClaudeSessions:
    """Tests for finding Claude-specific sessions."""

    @patch("lib.backends.tmux.shutil.which", return_value="/usr/local/bin/tmux")
    @patch("lib.backends.tmux._run_tmux")
    def test_get_claude_sessions(self, mock_run, mock_which):
        """Filters to only Claude sessions."""
        # list_sessions call, then session_exists + list-panes for each claude session
        mock_run.side_effect = [
            # list_sessions
            (0, "claude-myproject:1234567890:1:1\nother-session:1234567891:0:1\nclaude-another:1234567892:0:1\n", ""),
            # get_session_info for claude-myproject: session_exists then list-panes
            (0, "", ""),
            (0, "claude-myproject:1234567890:1:1:123:/dev/ttys001:/path1\n", ""),
            # get_session_info for claude-another: session_exists then list-panes
            (0, "", ""),
            (0, "claude-another:1234567892:0:1:456:/dev/ttys002:/path2\n", ""),
        ]

        sessions = get_claude_sessions()

        assert len(sessions) == 2
        assert sessions[0]["name"] == "claude-myproject"
        assert sessions[1]["name"] == "claude-another"

    @patch("lib.backends.tmux.shutil.which", return_value=None)
    def test_get_claude_sessions_tmux_unavailable(self, mock_which):
        """Returns empty list when tmux unavailable."""
        sessions = get_claude_sessions()
        assert sessions == []
