"""Tests for ConfigService."""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.services.config_service import (
    ConfigService,
    get_config_service,
    reset_config_service,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the config service singleton between tests."""
    reset_config_service()
    yield
    reset_config_service()


class TestConfigServiceLoad:
    """Tests for loading configuration."""

    def test_load_defaults_when_no_file(self, temp_dir):
        """Returns default config when file doesn't exist."""
        service = ConfigService(temp_dir / "nonexistent.yaml")
        config = service.load()

        assert config.scan_interval == 2
        assert config.terminal_backend == "wezterm"
        assert config.port == 5050
        assert config.projects == []

    def test_load_from_yaml(self, temp_dir):
        """Loads config from YAML file."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
projects:
  - name: test-project
    path: /home/user/test

scan_interval: 5
terminal_backend: wezterm
port: 8080
"""
        )

        service = ConfigService(config_file)
        config = service.load()

        assert len(config.projects) == 1
        assert config.projects[0].name == "test-project"
        assert config.scan_interval == 5
        assert config.port == 8080

    def test_load_handles_invalid_yaml(self, temp_dir):
        """Returns defaults for invalid YAML."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")

        service = ConfigService(config_file)
        config = service.load()

        # Should use defaults
        assert config.scan_interval == 2

    def test_load_handles_validation_error(self, temp_dir):
        """Returns defaults for invalid config values."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
scan_interval: 1000  # Invalid - max is 60
"""
        )

        service = ConfigService(config_file)
        config = service.load()

        # Should use defaults due to validation error
        assert config.scan_interval == 2

    def test_get_config_loads_once(self, temp_dir):
        """get_config only loads once."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("scan_interval: 5")

        service = ConfigService(config_file)

        config1 = service.get_config()
        config_file.write_text("scan_interval: 10")  # Change file
        config2 = service.get_config()

        # Should be same object (not reloaded)
        assert config1 is config2
        assert config1.scan_interval == 5

    def test_reload_forces_reload(self, temp_dir):
        """reload forces re-reading from disk."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("scan_interval: 5")

        service = ConfigService(config_file)
        config1 = service.get_config()
        assert config1.scan_interval == 5

        config_file.write_text("scan_interval: 10")
        config2 = service.reload()

        assert config2.scan_interval == 10


class TestConfigMigration:
    """Tests for migrating legacy config formats."""

    def test_migrate_projects(self, temp_dir):
        """Projects are migrated correctly."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
projects:
  - name: project1
    path: /path/to/project1
  - name: project2
    path: /path/to/project2
    goal: Build something
"""
        )

        service = ConfigService(config_file)
        config = service.load()

        assert len(config.projects) == 2
        assert config.projects[0].name == "project1"
        assert config.projects[1].goal == "Build something"

    def test_migrate_terminal_backend(self, temp_dir):
        """terminal_backend is migrated."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("terminal_backend: tmux")

        service = ConfigService(config_file)
        config = service.load()

        assert config.terminal_backend == "tmux"

    def test_migrate_unknown_backend_defaults_to_wezterm(self, temp_dir):
        """Unknown backend defaults to wezterm."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("terminal_backend: iterm")

        service = ConfigService(config_file)
        config = service.load()

        assert config.terminal_backend == "wezterm"

    def test_migrate_wezterm_config(self, temp_dir):
        """WezTerm config is migrated."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
wezterm:
  workspace: my-workspace
  full_scrollback: false
"""
        )

        service = ConfigService(config_file)
        config = service.load()

        assert config.wezterm.workspace == "my-workspace"
        assert config.wezterm.full_scrollback is False

    def test_migrate_openrouter_model_to_inference(self, temp_dir):
        """Legacy openrouter.model migrates to inference config."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
openrouter:
  model: anthropic/claude-3-haiku
"""
        )

        service = ConfigService(config_file)
        config = service.load()

        # Legacy model should populate fast tier
        assert config.inference.detect_state == "anthropic/claude-3-haiku"
        assert config.inference.summarize_command == "anthropic/claude-3-haiku"

    def test_migrate_priorities_model_to_inference(self, temp_dir):
        """Legacy priorities.model migrates to inference config."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
priorities:
  model: anthropic/claude-3-opus
"""
        )

        service = ConfigService(config_file)
        config = service.load()

        # Priority model should populate deep tier
        assert config.inference.full_priority == "anthropic/claude-3-opus"

    def test_deprecated_fields_ignored(self, temp_dir):
        """Deprecated fields are silently ignored."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text(
            """
idle_timeout_minutes: 60
stale_threshold_hours: 4
headspace:
  enabled: true
session_sync:
  enabled: true
tmux_logging:
  debug_enabled: true
"""
        )

        service = ConfigService(config_file)
        config = service.load()

        # Should load without error, use defaults
        assert config.scan_interval == 2


class TestConfigSave:
    """Tests for saving configuration."""

    def test_save_creates_file(self, temp_dir):
        """save creates config file."""
        config_file = temp_dir / "config.yaml"
        service = ConfigService(config_file)
        service.load()

        result = service.save()

        assert result is True
        assert config_file.exists()

    def test_save_writes_current_config(self, temp_dir):
        """save writes current config values."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("scan_interval: 5")

        service = ConfigService(config_file)
        config = service.load()
        config.scan_interval = 10
        service.save()

        # Re-read to verify
        with open(config_file) as f:
            saved = yaml.safe_load(f)

        assert saved["scan_interval"] == 10


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_config_service_returns_same_instance(self):
        """get_config_service returns same instance."""
        service1 = get_config_service()
        service2 = get_config_service()

        assert service1 is service2

    def test_reset_config_service_clears_instance(self):
        """reset_config_service creates new instance."""
        service1 = get_config_service()
        reset_config_service()
        service2 = get_config_service()

        assert service1 is not service2
