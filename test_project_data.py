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
    # Headspace functions
    HEADSPACE_DATA_PATH,
    load_headspace,
    save_headspace,
    get_headspace_history,
    is_headspace_enabled,
    is_headspace_history_enabled,
    # Priorities functions
    is_priorities_enabled,
    get_priorities_config,
    get_all_project_roadmaps,
    get_all_project_states,
    aggregate_priority_context,
    build_prioritisation_prompt,
    parse_priority_response,
    is_cache_valid,
    is_any_session_processing,
    _default_priority_order,
    compute_priorities,
    _priorities_cache,
    update_priorities_cache,
    apply_soft_transition,
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


# =============================================================================
# Headspace Tests
# =============================================================================


@pytest.fixture
def temp_headspace_path(tmp_path, monkeypatch):
    """Create a temporary headspace file path for testing."""
    headspace_file = tmp_path / "data" / "headspace.yaml"
    headspace_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("monitor.HEADSPACE_DATA_PATH", headspace_file)
    return headspace_file


class TestLoadHeadspace:
    """Tests for load_headspace() function."""

    def test_load_nonexistent_file(self, temp_headspace_path):
        """Test loading when no headspace file exists."""
        result = load_headspace()
        assert result is None

    def test_load_existing_headspace(self, temp_headspace_path):
        """Test loading existing headspace data."""
        test_data = {
            "current_focus": "Ship auth feature",
            "constraints": "No new features until CI green",
            "updated_at": "2026-01-21T10:00:00Z"
        }
        temp_headspace_path.write_text(yaml.dump(test_data))

        result = load_headspace()
        assert result is not None
        assert result["current_focus"] == "Ship auth feature"
        assert result["constraints"] == "No new features until CI green"
        assert result["updated_at"] == "2026-01-21T10:00:00Z"

    def test_load_headspace_without_constraints(self, temp_headspace_path):
        """Test loading headspace without optional constraints."""
        test_data = {
            "current_focus": "Fix critical bug",
            "updated_at": "2026-01-21T10:00:00Z"
        }
        temp_headspace_path.write_text(yaml.dump(test_data))

        result = load_headspace()
        assert result is not None
        assert result["current_focus"] == "Fix critical bug"
        assert result["constraints"] is None

    def test_load_empty_file(self, temp_headspace_path):
        """Test loading an empty file returns None."""
        temp_headspace_path.write_text("")
        result = load_headspace()
        assert result is None


class TestSaveHeadspace:
    """Tests for save_headspace() function."""

    def test_save_new_headspace(self, temp_headspace_path):
        """Test saving headspace when no file exists."""
        result = save_headspace("Build new dashboard", "Must be responsive")

        assert result["current_focus"] == "Build new dashboard"
        assert result["constraints"] == "Must be responsive"
        assert "updated_at" in result

        # Verify file was created
        assert temp_headspace_path.exists()
        data = yaml.safe_load(temp_headspace_path.read_text())
        assert data["current_focus"] == "Build new dashboard"

    def test_save_headspace_without_constraints(self, temp_headspace_path):
        """Test saving headspace without constraints."""
        result = save_headspace("Simple task")

        assert result["current_focus"] == "Simple task"
        assert result["constraints"] is None

    def test_save_overwrites_existing(self, temp_headspace_path):
        """Test that saving overwrites existing headspace."""
        # Create initial headspace
        save_headspace("First focus", "First constraint")

        # Overwrite with new headspace
        result = save_headspace("Second focus", "Second constraint")

        assert result["current_focus"] == "Second focus"
        assert result["constraints"] == "Second constraint"

        # Verify file has new data
        data = yaml.safe_load(temp_headspace_path.read_text())
        assert data["current_focus"] == "Second focus"

    def test_save_updates_timestamp(self, temp_headspace_path):
        """Test that saving updates the timestamp."""
        result1 = save_headspace("First focus")
        timestamp1 = result1["updated_at"]

        # Small delay to ensure different timestamp
        import time
        time.sleep(0.01)

        result2 = save_headspace("Second focus")
        timestamp2 = result2["updated_at"]

        assert timestamp1 != timestamp2


class TestHeadspaceHistory:
    """Tests for headspace history functions."""

    def test_get_history_empty(self, temp_headspace_path):
        """Test getting history when no history exists."""
        result = get_headspace_history()
        assert result == []

    def test_get_history_from_file(self, temp_headspace_path):
        """Test getting history from file."""
        test_data = {
            "current_focus": "Current task",
            "history": [
                {"current_focus": "Old task 1", "updated_at": "2026-01-20T10:00:00Z"},
                {"current_focus": "Old task 2", "updated_at": "2026-01-19T10:00:00Z"}
            ]
        }
        temp_headspace_path.write_text(yaml.dump(test_data))

        result = get_headspace_history()
        assert len(result) == 2
        assert result[0]["current_focus"] == "Old task 1"

    def test_history_preserved_on_save(self, temp_headspace_path):
        """Test that history is preserved when saving new headspace."""
        # Create initial data with history
        initial_data = {
            "current_focus": "Current task",
            "updated_at": "2026-01-20T10:00:00Z",
            "history": [
                {"current_focus": "Old task", "updated_at": "2026-01-19T10:00:00Z"}
            ]
        }
        temp_headspace_path.write_text(yaml.dump(initial_data))

        # Save new headspace (without history enabled)
        save_headspace("New task")

        # Verify history is preserved
        data = yaml.safe_load(temp_headspace_path.read_text())
        assert "history" in data
        assert len(data["history"]) == 1


class TestHeadspaceConfiguration:
    """Tests for headspace configuration helpers."""

    def test_is_headspace_enabled_default(self, monkeypatch):
        """Test headspace enabled by default."""
        monkeypatch.setattr("monitor.load_config", lambda: {})
        assert is_headspace_enabled() is True

    def test_is_headspace_enabled_true(self, monkeypatch):
        """Test headspace explicitly enabled."""
        monkeypatch.setattr("monitor.load_config", lambda: {"headspace": {"enabled": True}})
        assert is_headspace_enabled() is True

    def test_is_headspace_enabled_false(self, monkeypatch):
        """Test headspace explicitly disabled."""
        monkeypatch.setattr("monitor.load_config", lambda: {"headspace": {"enabled": False}})
        assert is_headspace_enabled() is False

    def test_is_history_enabled_default(self, monkeypatch):
        """Test history disabled by default."""
        monkeypatch.setattr("monitor.load_config", lambda: {})
        assert is_headspace_history_enabled() is False

    def test_is_history_enabled_true(self, monkeypatch):
        """Test history explicitly enabled."""
        monkeypatch.setattr("monitor.load_config", lambda: {"headspace": {"history_enabled": True}})
        assert is_headspace_history_enabled() is True


# =============================================================================
# Priorities Tests
# =============================================================================

class TestPrioritiesConfiguration:
    """Tests for priorities configuration helpers."""

    def test_is_priorities_enabled_default(self, monkeypatch):
        """Test priorities enabled by default."""
        monkeypatch.setattr("monitor.load_config", lambda: {})
        assert is_priorities_enabled() is True

    def test_is_priorities_enabled_true(self, monkeypatch):
        """Test priorities explicitly enabled."""
        monkeypatch.setattr("monitor.load_config", lambda: {"priorities": {"enabled": True}})
        assert is_priorities_enabled() is True

    def test_is_priorities_enabled_false(self, monkeypatch):
        """Test priorities explicitly disabled."""
        monkeypatch.setattr("monitor.load_config", lambda: {"priorities": {"enabled": False}})
        assert is_priorities_enabled() is False

    def test_get_priorities_config_defaults(self, monkeypatch):
        """Test default priorities config values."""
        monkeypatch.setattr("monitor.load_config", lambda: {})
        config = get_priorities_config()
        assert config["enabled"] is True
        assert config["polling_interval"] == 60
        assert "model" in config

    def test_get_priorities_config_custom(self, monkeypatch):
        """Test custom priorities config values."""
        monkeypatch.setattr("monitor.load_config", lambda: {
            "priorities": {
                "enabled": False,
                "polling_interval": 120,
                "model": "custom-model"
            }
        })
        config = get_priorities_config()
        assert config["enabled"] is False
        assert config["polling_interval"] == 120
        assert config["model"] == "custom-model"


class TestContextAggregation:
    """Tests for priority context aggregation functions."""

    def test_get_all_project_roadmaps(self, monkeypatch):
        """Test gathering roadmap data from projects."""
        mock_projects = [
            {"name": "project-a", "roadmap": {"next_up": {"title": "Feature X"}, "upcoming": ["Y", "Z"]}},
            {"name": "project-b", "roadmap": {"next_up": {"title": "Feature Y"}}},
            {"name": "project-c"}  # No roadmap
        ]
        monkeypatch.setattr("monitor.list_project_data", lambda: mock_projects)

        roadmaps = get_all_project_roadmaps()
        assert "project-a" in roadmaps
        assert "project-b" in roadmaps
        assert "project-c" not in roadmaps
        assert roadmaps["project-a"]["next_up"]["title"] == "Feature X"

    def test_get_all_project_states(self, monkeypatch):
        """Test gathering state data from projects."""
        mock_projects = [
            {"name": "project-a", "state": {"summary": "Working on tests"}, "recent_sessions": [1, 2, 3, 4, 5]},
            {"name": "project-b", "state": {"summary": "Bug fixes"}},
        ]
        monkeypatch.setattr("monitor.list_project_data", lambda: mock_projects)

        states = get_all_project_states()
        assert states["project-a"]["summary"] == "Working on tests"
        assert len(states["project-a"]["recent_sessions"]) == 3  # Limited to 3

    def test_aggregate_priority_context(self, monkeypatch):
        """Test aggregating all priority context."""
        monkeypatch.setattr("monitor.load_headspace", lambda: {"current_focus": "Testing"})
        monkeypatch.setattr("monitor.list_project_data", lambda: [])
        monkeypatch.setattr("monitor.load_config", lambda: {"projects": []})
        monkeypatch.setattr("monitor.scan_sessions", lambda c: [])

        context = aggregate_priority_context()
        assert "headspace" in context
        assert "roadmaps" in context
        assert "states" in context
        assert "sessions" in context
        assert context["headspace"]["current_focus"] == "Testing"


class TestBuildPrioritisationPrompt:
    """Tests for prompt construction."""

    def test_prompt_with_headspace(self):
        """Test prompt includes headspace when set."""
        context = {
            "headspace": {"current_focus": "Ship billing feature", "constraints": "By Friday"},
            "roadmaps": {},
            "states": {},
            "sessions": [
                {"project_name": "billing", "session_id": "123", "activity_state": "idle", "task_summary": ""}
            ]
        }
        messages = build_prioritisation_prompt(context)
        assert len(messages) == 2
        assert "system" in messages[0]["role"]
        assert "Ship billing feature" in messages[1]["content"]
        assert "By Friday" in messages[1]["content"]

    def test_prompt_without_headspace(self):
        """Test prompt handles missing headspace."""
        context = {
            "headspace": None,
            "roadmaps": {},
            "states": {},
            "sessions": [
                {"project_name": "api", "session_id": "456", "activity_state": "processing", "task_summary": ""}
            ]
        }
        messages = build_prioritisation_prompt(context)
        assert "Not set" in messages[1]["content"]
        assert "roadmap urgency" in messages[1]["content"].lower()

    def test_prompt_includes_activity_state(self):
        """Test prompt includes activity state for each session."""
        context = {
            "headspace": None,
            "roadmaps": {},
            "states": {},
            "sessions": [
                {"project_name": "frontend", "session_id": "789", "activity_state": "input_needed", "task_summary": "Waiting for approval"}
            ]
        }
        messages = build_prioritisation_prompt(context)
        assert "input_needed" in messages[1]["content"]


class TestParsePriorityResponse:
    """Tests for parsing AI responses."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        sessions = [
            {"project_name": "api", "session_id": "123", "activity_state": "idle"},
            {"project_name": "web", "session_id": "456", "activity_state": "processing"}
        ]
        response = '{"priorities": [{"project_name": "api", "session_id": "123", "priority_score": 90, "rationale": "High priority"}]}'

        result = parse_priority_response(response, sessions)
        assert len(result) == 2  # All sessions included
        assert result[0]["priority_score"] == 90
        assert result[0]["rationale"] == "High priority"

    def test_parse_json_in_code_block(self):
        """Test parsing JSON wrapped in markdown code block."""
        sessions = [{"project_name": "test", "session_id": "1", "activity_state": "idle"}]
        response = '```json\n{"priorities": [{"project_name": "test", "session_id": "1", "priority_score": 75, "rationale": "Test"}]}\n```'

        result = parse_priority_response(response, sessions)
        assert result[0]["priority_score"] == 75

    def test_parse_malformed_response(self):
        """Test fallback on malformed response."""
        sessions = [
            {"project_name": "a", "session_id": "1", "activity_state": "input_needed"},
            {"project_name": "b", "session_id": "2", "activity_state": "idle"}
        ]
        response = "This is not JSON"

        result = parse_priority_response(response, sessions)
        assert len(result) == 2
        # input_needed should be first in default ordering
        assert result[0]["project_name"] == "a"

    def test_parse_empty_response(self):
        """Test fallback on empty response."""
        sessions = [{"project_name": "x", "session_id": "1", "activity_state": "idle"}]

        result = parse_priority_response("", sessions)
        assert len(result) == 1
        assert "Default ordering" in result[0]["rationale"]

    def test_parse_clamps_priority_score(self):
        """Test priority score is clamped to 0-100."""
        sessions = [{"project_name": "test", "session_id": "1", "activity_state": "idle"}]
        response = '{"priorities": [{"project_name": "test", "session_id": "1", "priority_score": 150, "rationale": "Over"}]}'

        result = parse_priority_response(response, sessions)
        assert result[0]["priority_score"] == 100  # Clamped


class TestDefaultPriorityOrder:
    """Tests for default priority ordering."""

    def test_order_by_activity_state(self):
        """Test sessions ordered by activity state."""
        sessions = [
            {"project_name": "a", "session_id": "1", "activity_state": "idle"},
            {"project_name": "b", "session_id": "2", "activity_state": "input_needed"},
            {"project_name": "c", "session_id": "3", "activity_state": "processing"},
        ]

        result = _default_priority_order(sessions)
        assert result[0]["project_name"] == "b"  # input_needed first
        assert result[1]["project_name"] == "a"  # idle second
        assert result[2]["project_name"] == "c"  # processing last

    def test_alphabetical_within_state(self):
        """Test alphabetical order within same state."""
        sessions = [
            {"project_name": "zebra", "session_id": "1", "activity_state": "idle"},
            {"project_name": "apple", "session_id": "2", "activity_state": "idle"},
        ]

        result = _default_priority_order(sessions)
        assert result[0]["project_name"] == "apple"
        assert result[1]["project_name"] == "zebra"


class TestCacheValidity:
    """Tests for cache validity logic."""

    def test_cache_invalid_when_empty(self, monkeypatch):
        """Test cache is invalid when no priorities cached."""
        import monitor
        monkeypatch.setattr("monitor._priorities_cache", {
            "priorities": None,
            "timestamp": None,
            "pending_priorities": None,
            "error": None
        })
        assert is_cache_valid() is False

    def test_cache_valid_within_interval(self, monkeypatch):
        """Test cache is valid within polling interval."""
        import monitor
        now = datetime.now(timezone.utc)
        monkeypatch.setattr("monitor._priorities_cache", {
            "priorities": [{"test": "data"}],
            "timestamp": now,
            "pending_priorities": None,
            "error": None
        })
        monkeypatch.setattr("monitor.get_priorities_config", lambda: {"polling_interval": 60})
        assert is_cache_valid() is True


class TestSoftTransitions:
    """Tests for soft transition detection and handling."""

    def test_is_any_session_processing_true(self):
        """Test detecting processing session."""
        sessions = [
            {"activity_state": "idle"},
            {"activity_state": "processing"},
        ]
        assert is_any_session_processing(sessions) is True

    def test_is_any_session_processing_false(self):
        """Test no processing sessions."""
        sessions = [
            {"activity_state": "idle"},
            {"activity_state": "input_needed"},
        ]
        assert is_any_session_processing(sessions) is False

    def test_apply_soft_transition_with_processing(self, monkeypatch):
        """Test soft transition stores pending when processing."""
        import monitor
        monkeypatch.setattr("monitor._priorities_cache", {
            "priorities": [{"old": "data"}],
            "timestamp": datetime.now(timezone.utc),
            "pending_priorities": None,
            "error": None
        })

        new_priorities = [{"new": "data"}]
        sessions = [{"activity_state": "processing"}]

        result, pending = apply_soft_transition(new_priorities, sessions)
        assert pending is True
        assert result[0]["old"] == "data"  # Returns old

    def test_apply_soft_transition_no_processing(self, monkeypatch):
        """Test soft transition applies immediately when not processing."""
        import monitor
        monkeypatch.setattr("monitor._priorities_cache", {
            "priorities": None,
            "timestamp": None,
            "pending_priorities": None,
            "error": None
        })

        new_priorities = [{"new": "data"}]
        sessions = [{"activity_state": "idle"}]

        result, pending = apply_soft_transition(new_priorities, sessions)
        assert pending is False
        assert result[0]["new"] == "data"


class TestComputePriorities:
    """Tests for compute_priorities integration."""

    def test_compute_when_disabled(self, monkeypatch):
        """Test compute returns error when disabled."""
        monkeypatch.setattr("monitor.is_priorities_enabled", lambda: False)

        result = compute_priorities()
        assert result["success"] is False
        assert "disabled" in result["error"]

    def test_compute_with_no_sessions(self, monkeypatch):
        """Test compute handles no active sessions."""
        monkeypatch.setattr("monitor.is_priorities_enabled", lambda: True)
        monkeypatch.setattr("monitor.is_cache_valid", lambda: False)
        monkeypatch.setattr("monitor.aggregate_priority_context", lambda: {
            "headspace": None,
            "roadmaps": {},
            "states": {},
            "sessions": []
        })

        result = compute_priorities(force_refresh=True)
        assert result["success"] is True
        assert result["priorities"] == []

    def test_compute_with_openrouter_error(self, monkeypatch):
        """Test graceful degradation when OpenRouter fails."""
        import monitor
        monkeypatch.setattr("monitor.is_priorities_enabled", lambda: True)
        monkeypatch.setattr("monitor.is_cache_valid", lambda: False)
        monkeypatch.setattr("monitor._priorities_cache", {
            "priorities": None,
            "timestamp": None,
            "pending_priorities": None,
            "error": None
        })
        monkeypatch.setattr("monitor.aggregate_priority_context", lambda: {
            "headspace": {"current_focus": "Testing"},
            "roadmaps": {},
            "states": {},
            "sessions": [{"project_name": "test", "session_id": "1", "activity_state": "idle", "task_summary": ""}]
        })
        monkeypatch.setattr("monitor.get_priorities_config", lambda: {"model": "test"})
        monkeypatch.setattr("monitor.call_openrouter", lambda m, model: (None, "API error"))

        result = compute_priorities(force_refresh=True)
        assert result["success"] is True  # Still succeeds with fallback
        assert len(result["priorities"]) == 1
        assert "error" in result["metadata"]


class TestApiPrioritiesEndpoint:
    """Tests for the /api/priorities endpoint."""

    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        from monitor import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_priorities_endpoint_disabled(self, client, monkeypatch):
        """Test endpoint returns 404 when disabled."""
        monkeypatch.setattr("monitor.is_priorities_enabled", lambda: False)

        response = client.get("/api/priorities")
        assert response.status_code == 404
        data = response.get_json()
        assert data["success"] is False

    def test_priorities_endpoint_success(self, client, monkeypatch):
        """Test endpoint returns priorities."""
        import monitor
        monkeypatch.setattr("monitor.is_priorities_enabled", lambda: True)
        monkeypatch.setattr("monitor.compute_priorities", lambda force_refresh=False: {
            "success": True,
            "priorities": [
                {"project_name": "test", "session_id": "1", "priority_score": 80, "rationale": "High", "activity_state": "idle"}
            ],
            "metadata": {
                "timestamp": "2024-01-01T00:00:00Z",
                "headspace_summary": "Focus",
                "cache_hit": False,
                "soft_transition_pending": False
            }
        })

        response = client.get("/api/priorities")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["priorities"]) == 1

    def test_priorities_refresh_param(self, client, monkeypatch):
        """Test refresh parameter triggers cache bypass."""
        calls = []

        def mock_compute(force_refresh=False):
            calls.append(force_refresh)
            return {"success": True, "priorities": [], "metadata": {}}

        monkeypatch.setattr("monitor.is_priorities_enabled", lambda: True)
        monkeypatch.setattr("monitor.compute_priorities", mock_compute)

        client.get("/api/priorities?refresh=true")
        assert calls[-1] is True
