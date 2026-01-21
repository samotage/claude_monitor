"""Tests for project data management functionality."""

import os
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

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
