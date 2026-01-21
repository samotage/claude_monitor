"""Tests for project data management functionality."""

import os
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml
import requests

# Import the functions we're testing
from monitor import (
    slugify_name,
    get_project_data_path,
    load_project_data,
    save_project_data,
    list_project_data,
    parse_claude_md,
    register_project,
    register_all_projects,
    PROJECT_DATA_DIR,
    # History Compression functions
    add_to_compression_queue,
    get_pending_compressions,
    remove_from_compression_queue,
    get_project_history,
    update_project_history,
    get_openrouter_config,
    call_openrouter,
    build_compression_prompt,
    compress_session,
    process_compression_queue,
    add_recent_session,
)


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Create a temporary data directory for testing."""
    temp_projects_dir = tmp_path / "data" / "projects"
    temp_projects_dir.mkdir(parents=True)
    monkeypatch.setattr("monitor.PROJECT_DATA_DIR", temp_projects_dir)
    return temp_projects_dir


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory for testing."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    return project_dir


class TestSlugifyName:
    """Tests for slugify_name() function."""

    def test_lowercase_conversion(self):
        """Test that names are converted to lowercase."""
        assert slugify_name("MyProject") == "myproject"
        assert slugify_name("UPPERCASE") == "uppercase"

    def test_spaces_to_hyphens(self):
        """Test that spaces are converted to hyphens."""
        assert slugify_name("My Project") == "my-project"
        assert slugify_name("A B C") == "a-b-c"

    def test_combined_conversion(self):
        """Test both lowercase and hyphen conversion together."""
        assert slugify_name("My Cool Project") == "my-cool-project"

    def test_already_slugified(self):
        """Test that already slugified names are unchanged."""
        assert slugify_name("already-slugified") == "already-slugified"

    def test_empty_string(self):
        """Test handling of empty string."""
        assert slugify_name("") == ""


class TestProjectDataPath:
    """Tests for get_project_data_path() function."""

    def test_returns_correct_path(self, temp_data_dir, monkeypatch):
        """Test that correct path is returned."""
        path = get_project_data_path("my-project")
        assert path == temp_data_dir / "my-project.yaml"

    def test_slugifies_name(self, temp_data_dir, monkeypatch):
        """Test that name is slugified in path."""
        path = get_project_data_path("My Project")
        assert path == temp_data_dir / "my-project.yaml"


class TestLoadProjectData:
    """Tests for load_project_data() function."""

    def test_load_existing_file(self, temp_data_dir):
        """Test loading an existing project data file."""
        # Create a test file
        test_data = {"name": "Test", "path": "/test", "goal": "Test goal"}
        test_file = temp_data_dir / "test.yaml"
        test_file.write_text(yaml.dump(test_data))

        result = load_project_data("test")
        assert result is not None
        assert result["name"] == "Test"
        assert result["goal"] == "Test goal"

    def test_load_missing_file(self, temp_data_dir):
        """Test loading a non-existent file returns None."""
        result = load_project_data("nonexistent")
        assert result is None

    def test_load_by_path(self, temp_data_dir):
        """Test loading by direct file path."""
        test_data = {"name": "PathTest", "path": "/path-test"}
        test_file = temp_data_dir / "path-test.yaml"
        test_file.write_text(yaml.dump(test_data))

        result = load_project_data(str(test_file))
        assert result is not None
        assert result["name"] == "PathTest"


class TestSaveProjectData:
    """Tests for save_project_data() function."""

    def test_creates_valid_yaml(self, temp_data_dir):
        """Test that valid YAML is created."""
        test_data = {
            "name": "SaveTest",
            "path": "/save-test",
            "goal": "Test saving",
            "context": {},
        }

        result = save_project_data("save-test", test_data)
        assert result is True

        # Verify file exists and is valid YAML
        saved_file = temp_data_dir / "save-test.yaml"
        assert saved_file.exists()

        loaded = yaml.safe_load(saved_file.read_text())
        assert loaded["name"] == "SaveTest"

    def test_updates_refreshed_at(self, temp_data_dir):
        """Test that refreshed_at is updated on save."""
        test_data = {
            "name": "RefreshTest",
            "path": "/refresh-test",
            "context": {"refreshed_at": "2020-01-01T00:00:00+00:00"},
        }

        before = datetime.now(timezone.utc)
        save_project_data("refresh-test", test_data)
        after = datetime.now(timezone.utc)

        saved_file = temp_data_dir / "refresh-test.yaml"
        loaded = yaml.safe_load(saved_file.read_text())

        refreshed = datetime.fromisoformat(loaded["context"]["refreshed_at"])
        assert before <= refreshed <= after


class TestListProjectData:
    """Tests for list_project_data() function."""

    def test_returns_all_projects(self, temp_data_dir):
        """Test that all project data files are returned."""
        # Create test files
        for name in ["project-a", "project-b", "project-c"]:
            test_file = temp_data_dir / f"{name}.yaml"
            test_file.write_text(yaml.dump({"name": name, "path": f"/{name}"}))

        result = list_project_data()
        assert len(result) == 3
        names = {p["name"] for p in result}
        assert names == {"project-a", "project-b", "project-c"}

    def test_empty_directory(self, temp_data_dir):
        """Test handling of empty directory."""
        result = list_project_data()
        assert result == []


class TestParseClaudeMd:
    """Tests for parse_claude_md() function."""

    def test_parses_valid_claude_md(self, temp_project_dir):
        """Test parsing a valid CLAUDE.md file."""
        claude_md = temp_project_dir / "CLAUDE.md"
        claude_md.write_text("""# Project Name

## Project Overview

This is a test project for demonstration.

## Tech Stack

- Python 3.10+
- Flask
- PyYAML

## Other Section

More content here.
""")

        result = parse_claude_md(str(temp_project_dir))
        assert result["goal"] == "This is a test project for demonstration."
        assert "Python 3.10+" in result["tech_stack"]
        assert "Flask" in result["tech_stack"]

    def test_missing_claude_md(self, temp_project_dir):
        """Test handling of missing CLAUDE.md."""
        result = parse_claude_md(str(temp_project_dir))
        assert result["goal"] == ""
        assert result["tech_stack"] == ""

    def test_missing_sections(self, temp_project_dir):
        """Test handling of CLAUDE.md with missing expected sections."""
        claude_md = temp_project_dir / "CLAUDE.md"
        claude_md.write_text("""# Project Name

## Some Other Section

Content here.
""")

        result = parse_claude_md(str(temp_project_dir))
        assert result["goal"] == ""
        assert result["tech_stack"] == ""

    def test_malformed_claude_md(self, temp_project_dir):
        """Test handling of malformed CLAUDE.md content."""
        claude_md = temp_project_dir / "CLAUDE.md"
        claude_md.write_text("Just some random text without any headers")

        result = parse_claude_md(str(temp_project_dir))
        assert result["goal"] == ""
        assert result["tech_stack"] == ""


class TestRegisterProject:
    """Tests for register_project() function."""

    def test_new_project_creates_file(self, temp_data_dir, temp_project_dir):
        """Test that registering a new project creates a data file."""
        result = register_project("new-project", str(temp_project_dir))
        assert result is True

        data_file = temp_data_dir / "new-project.yaml"
        assert data_file.exists()

    def test_reregistration_does_not_overwrite(self, temp_data_dir, temp_project_dir):
        """Test that re-registering doesn't overwrite existing data."""
        # First registration
        register_project("existing", str(temp_project_dir))

        # Modify the data
        data_file = temp_data_dir / "existing.yaml"
        data = yaml.safe_load(data_file.read_text())
        data["goal"] = "Modified goal"
        data_file.write_text(yaml.dump(data))

        # Re-register
        result = register_project("existing", str(temp_project_dir))
        assert result is True

        # Verify data wasn't overwritten
        reloaded = yaml.safe_load(data_file.read_text())
        assert reloaded["goal"] == "Modified goal"

    def test_registration_with_missing_claude_md(self, temp_data_dir, temp_project_dir):
        """Test that registration succeeds even without CLAUDE.md."""
        result = register_project("no-claude", str(temp_project_dir))
        assert result is True

        data_file = temp_data_dir / "no-claude.yaml"
        assert data_file.exists()

        data = yaml.safe_load(data_file.read_text())
        assert data["goal"] == ""
        assert data["context"]["tech_stack"] == ""

    def test_registration_creates_placeholder_sections(self, temp_data_dir, temp_project_dir):
        """Test that registration creates placeholder sections."""
        register_project("with-placeholders", str(temp_project_dir))

        data_file = temp_data_dir / "with-placeholders.yaml"
        data = yaml.safe_load(data_file.read_text())

        assert data["roadmap"] == {}
        assert data["state"] == {}
        assert data["recent_sessions"] == []
        assert data["history"] == {}


class TestRegisterAllProjects:
    """Tests for register_all_projects() function."""

    def test_processes_all_config_projects(self, temp_data_dir, tmp_path, monkeypatch):
        """Test that all projects from config are registered."""
        # Create temp project directories
        proj_a = tmp_path / "project-a"
        proj_b = tmp_path / "project-b"
        proj_a.mkdir()
        proj_b.mkdir()

        # Mock load_config
        mock_config = {
            "projects": [
                {"name": "Project A", "path": str(proj_a)},
                {"name": "Project B", "path": str(proj_b)},
            ]
        }
        monkeypatch.setattr("monitor.load_config", lambda: mock_config)

        register_all_projects()

        # Check both projects were registered
        assert (temp_data_dir / "project-a.yaml").exists()
        assert (temp_data_dir / "project-b.yaml").exists()


# =============================================================================
# History Compression Tests
# =============================================================================


class TestCompressionQueue:
    """Tests for compression queue operations."""

    def test_add_to_compression_queue(self, temp_data_dir):
        """Test adding a session to the compression queue."""
        # Create a project data file
        test_data = {"name": "queue-test", "path": "/queue-test"}
        test_file = temp_data_dir / "queue-test.yaml"
        test_file.write_text(yaml.dump(test_data))

        session = {
            "session_id": "test-session-123",
            "started_at": "2024-01-01T00:00:00Z",
            "summary": "Test session"
        }

        result = add_to_compression_queue("queue-test", session)
        assert result is True

        # Verify it was added
        data = yaml.safe_load(test_file.read_text())
        assert "pending_compressions" in data
        assert len(data["pending_compressions"]) == 1
        assert data["pending_compressions"][0]["session_id"] == "test-session-123"
        assert "queued_at" in data["pending_compressions"][0]

    def test_add_to_compression_queue_no_duplicates(self, temp_data_dir):
        """Test that duplicate sessions aren't added to queue."""
        test_data = {"name": "dup-test", "path": "/dup-test"}
        test_file = temp_data_dir / "dup-test.yaml"
        test_file.write_text(yaml.dump(test_data))

        session = {"session_id": "dup-session", "summary": "Test"}

        # Add twice
        add_to_compression_queue("dup-test", session)
        add_to_compression_queue("dup-test", session)

        data = yaml.safe_load(test_file.read_text())
        assert len(data["pending_compressions"]) == 1

    def test_get_pending_compressions(self, temp_data_dir):
        """Test retrieving pending compressions."""
        test_data = {
            "name": "pending-test",
            "path": "/pending-test",
            "pending_compressions": [
                {"session_id": "s1", "summary": "First"},
                {"session_id": "s2", "summary": "Second"},
            ]
        }
        test_file = temp_data_dir / "pending-test.yaml"
        test_file.write_text(yaml.dump(test_data))

        result = get_pending_compressions("pending-test")
        assert len(result) == 2
        assert result[0]["session_id"] == "s1"

    def test_get_pending_compressions_empty(self, temp_data_dir):
        """Test getting pending compressions from empty queue."""
        test_data = {"name": "empty-test", "path": "/empty-test"}
        test_file = temp_data_dir / "empty-test.yaml"
        test_file.write_text(yaml.dump(test_data))

        result = get_pending_compressions("empty-test")
        assert result == []

    def test_remove_from_compression_queue(self, temp_data_dir):
        """Test removing a session from the compression queue."""
        test_data = {
            "name": "remove-test",
            "path": "/remove-test",
            "pending_compressions": [
                {"session_id": "keep-me", "summary": "Keep"},
                {"session_id": "remove-me", "summary": "Remove"},
            ]
        }
        test_file = temp_data_dir / "remove-test.yaml"
        test_file.write_text(yaml.dump(test_data))

        result = remove_from_compression_queue("remove-test", "remove-me")
        assert result is True

        data = yaml.safe_load(test_file.read_text())
        assert len(data["pending_compressions"]) == 1
        assert data["pending_compressions"][0]["session_id"] == "keep-me"


class TestHistoryOperations:
    """Tests for history get/update operations."""

    def test_get_project_history_empty(self, temp_data_dir):
        """Test getting history from project with no history."""
        test_data = {"name": "no-history", "path": "/no-history"}
        test_file = temp_data_dir / "no-history.yaml"
        test_file.write_text(yaml.dump(test_data))

        result = get_project_history("no-history")
        assert result["summary"] == ""
        assert result["last_compressed_at"] is None

    def test_get_project_history_existing(self, temp_data_dir):
        """Test getting existing history."""
        test_data = {
            "name": "has-history",
            "path": "/has-history",
            "history": {
                "summary": "Previous work summary",
                "last_compressed_at": "2024-01-01T00:00:00Z"
            }
        }
        test_file = temp_data_dir / "has-history.yaml"
        test_file.write_text(yaml.dump(test_data))

        result = get_project_history("has-history")
        assert result["summary"] == "Previous work summary"
        assert result["last_compressed_at"] == "2024-01-01T00:00:00Z"

    def test_update_project_history(self, temp_data_dir):
        """Test updating project history."""
        test_data = {"name": "update-hist", "path": "/update-hist"}
        test_file = temp_data_dir / "update-hist.yaml"
        test_file.write_text(yaml.dump(test_data))

        result = update_project_history("update-hist", "New summary narrative")
        assert result is True

        data = yaml.safe_load(test_file.read_text())
        assert data["history"]["summary"] == "New summary narrative"
        assert "last_compressed_at" in data["history"]


class TestOpenRouterClient:
    """Tests for OpenRouter API client with mocked responses."""

    def test_get_openrouter_config_defaults(self, monkeypatch):
        """Test default config values when not configured."""
        monkeypatch.setattr("monitor.load_config", lambda: {})

        result = get_openrouter_config()
        assert result["api_key"] == ""
        assert result["model"] == "anthropic/claude-3-haiku"
        assert result["compression_interval"] == 300

    def test_get_openrouter_config_custom(self, monkeypatch):
        """Test custom config values."""
        mock_config = {
            "openrouter": {
                "api_key": "test-key",
                "model": "custom/model",
                "compression_interval": 600
            }
        }
        monkeypatch.setattr("monitor.load_config", lambda: mock_config)

        result = get_openrouter_config()
        assert result["api_key"] == "test-key"
        assert result["model"] == "custom/model"
        assert result["compression_interval"] == 600

    def test_call_openrouter_no_api_key(self, monkeypatch):
        """Test that missing API key returns error."""
        monkeypatch.setattr("monitor.load_config", lambda: {})

        result, error = call_openrouter([{"role": "user", "content": "test"}])
        assert result is None
        assert error == "OpenRouter API key not configured"

    @patch("monitor.requests.post")
    def test_call_openrouter_success(self, mock_post, monkeypatch):
        """Test successful API call."""
        mock_config = {"openrouter": {"api_key": "test-key"}}
        monkeypatch.setattr("monitor.load_config", lambda: mock_config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_post.return_value = mock_response

        result, error = call_openrouter([{"role": "user", "content": "test"}])
        assert result == "Test response"
        assert error is None

    @patch("monitor.requests.post")
    def test_call_openrouter_rate_limited(self, mock_post, monkeypatch):
        """Test rate limiting (429) handling."""
        mock_config = {"openrouter": {"api_key": "test-key"}}
        monkeypatch.setattr("monitor.load_config", lambda: mock_config)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response

        result, error = call_openrouter([{"role": "user", "content": "test"}])
        assert result is None
        assert error == "rate_limited"

    @patch("monitor.requests.post")
    def test_call_openrouter_auth_error(self, mock_post, monkeypatch):
        """Test authentication error (401) handling."""
        mock_config = {"openrouter": {"api_key": "bad-key"}}
        monkeypatch.setattr("monitor.load_config", lambda: mock_config)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result, error = call_openrouter([{"role": "user", "content": "test"}])
        assert result is None
        assert error == "authentication_failed"

    @patch("monitor.requests.post")
    def test_call_openrouter_timeout(self, mock_post, monkeypatch):
        """Test timeout handling."""
        mock_config = {"openrouter": {"api_key": "test-key"}}
        monkeypatch.setattr("monitor.load_config", lambda: mock_config)

        mock_post.side_effect = requests.Timeout()

        result, error = call_openrouter([{"role": "user", "content": "test"}])
        assert result is None
        assert error == "timeout"


class TestCompressionPrompt:
    """Tests for compression prompt building."""

    def test_build_compression_prompt_basic(self):
        """Test basic prompt building."""
        session_data = {
            "started_at": "2024-01-01T00:00:00Z",
            "ended_at": "2024-01-01T01:00:00Z",
            "files_modified": ["file1.py", "file2.py"],
            "commands_run": ["pytest"],
            "summary": "Fixed bug"
        }

        messages = build_compression_prompt(session_data)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "file1.py" in messages[1]["content"]
        assert "first session" in messages[1]["content"]

    def test_build_compression_prompt_with_history(self):
        """Test prompt building with existing history."""
        session_data = {"summary": "New work"}
        existing_history = "Previous work on authentication"

        messages = build_compression_prompt(session_data, existing_history)
        assert "Previous work on authentication" in messages[1]["content"]
        assert "Merge" in messages[1]["content"]


class TestRetryLogic:
    """Tests for retry logic with exponential backoff."""

    @patch("monitor.call_openrouter")
    def test_process_compression_queue_success(self, mock_call, temp_data_dir):
        """Test successful queue processing."""
        test_data = {
            "name": "retry-test",
            "path": "/retry-test",
            "pending_compressions": [
                {"session_id": "s1", "summary": "Test", "retry_count": 0}
            ]
        }
        test_file = temp_data_dir / "retry-test.yaml"
        test_file.write_text(yaml.dump(test_data))

        mock_call.return_value = ("Compressed summary", None)

        result = process_compression_queue("retry-test")
        assert result["processed"] == 1
        assert result["failed"] == 0

        # Verify session was removed from queue
        data = yaml.safe_load(test_file.read_text())
        assert len(data["pending_compressions"]) == 0

    @patch("monitor.call_openrouter")
    def test_process_compression_queue_retry_on_timeout(self, mock_call, temp_data_dir):
        """Test that timeout triggers retry."""
        test_data = {
            "name": "timeout-test",
            "path": "/timeout-test",
            "pending_compressions": [
                {"session_id": "s1", "summary": "Test", "retry_count": 0}
            ]
        }
        test_file = temp_data_dir / "timeout-test.yaml"
        test_file.write_text(yaml.dump(test_data))

        mock_call.return_value = (None, "timeout")

        result = process_compression_queue("timeout-test")
        assert result["processed"] == 0
        assert result["remaining"] == 1

        # Verify session still in queue with incremented retry count
        data = yaml.safe_load(test_file.read_text())
        assert len(data["pending_compressions"]) == 1
        assert data["pending_compressions"][0]["retry_count"] == 1


class TestAddRecentSessionWithCompression:
    """Tests for add_recent_session returning removed sessions."""

    def test_add_recent_session_returns_removed(self, temp_data_dir):
        """Test that FIFO removal returns removed sessions."""
        # Create project with 5 sessions
        test_data = {
            "name": "fifo-test",
            "path": "/fifo-test",
            "recent_sessions": [
                {"session_id": f"s{i}", "summary": f"Session {i}"}
                for i in range(5)
            ]
        }
        test_file = temp_data_dir / "fifo-test.yaml"
        test_file.write_text(yaml.dump(test_data))

        # Add a 6th session
        new_session = {"session_id": "s-new", "summary": "New session"}
        success, removed = add_recent_session("fifo-test", new_session)

        assert success is True
        assert len(removed) == 1
        assert removed[0]["session_id"] == "s4"  # The oldest was removed

        # Verify state
        data = yaml.safe_load(test_file.read_text())
        assert len(data["recent_sessions"]) == 5
        assert data["recent_sessions"][0]["session_id"] == "s-new"

    def test_add_recent_session_no_removal_when_under_limit(self, temp_data_dir):
        """Test that no sessions removed when under limit."""
        test_data = {
            "name": "under-limit",
            "path": "/under-limit",
            "recent_sessions": [
                {"session_id": "s1", "summary": "Session 1"}
            ]
        }
        test_file = temp_data_dir / "under-limit.yaml"
        test_file.write_text(yaml.dump(test_data))

        new_session = {"session_id": "s2", "summary": "Session 2"}
        success, removed = add_recent_session("under-limit", new_session)

        assert success is True
        assert removed == []

        data = yaml.safe_load(test_file.read_text())
        assert len(data["recent_sessions"]) == 2
