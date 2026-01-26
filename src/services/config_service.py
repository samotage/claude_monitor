"""Configuration loading and migration service.

Handles loading config.yaml and migrating from legacy formats to the new schema.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from src.models.config import AppConfig

logger = logging.getLogger(__name__)


class ConfigService:
    """Service for loading and managing application configuration.

    Handles:
    - Loading config from config.yaml
    - Validating against Pydantic schema
    - Migrating from legacy formats
    - Saving updated config
    """

    def __init__(self, config_path: str | Path = "config.yaml"):
        """Initialize the config service.

        Args:
            config_path: Path to the config file.
        """
        self.config_path = Path(config_path)
        self._config: AppConfig | None = None

    def load(self) -> AppConfig:
        """Load and validate configuration.

        Returns:
            Validated AppConfig instance.
        """
        if not self.config_path.exists():
            logger.info(f"Config file not found at {self.config_path}, using defaults")
            self._config = AppConfig()
            return self._config

        try:
            with open(self.config_path) as f:
                raw_config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Error reading config file: {e}, using defaults")
            self._config = AppConfig()
            return self._config

        # Migrate legacy config format
        migrated = self._migrate_config(raw_config)

        # Validate and create config
        try:
            self._config = AppConfig(**migrated)
        except Exception as e:
            logger.warning(f"Config validation error: {e}, using defaults")
            self._config = AppConfig()

        return self._config

    def get_config(self) -> AppConfig:
        """Get the current configuration.

        Loads from disk if not already loaded.
        """
        if self._config is None:
            return self.load()
        return self._config

    def reload(self) -> AppConfig:
        """Force reload configuration from disk."""
        self._config = None
        return self.load()

    def save(self, config: AppConfig | None = None) -> bool:
        """Save configuration to disk.

        Args:
            config: Config to save. Uses current config if not provided.

        Returns:
            True if save succeeded.
        """
        config = config or self._config
        if config is None:
            return False

        try:
            config_dict = config.model_dump(mode="json")
            with open(self.config_path, "w") as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    def _migrate_config(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Migrate legacy config format to new schema.

        Handles:
        - Renaming fields
        - Restructuring nested configs
        - Setting defaults for new fields
        - Removing deprecated fields

        Args:
            raw: Raw config dictionary from YAML.

        Returns:
            Migrated config dictionary.
        """
        migrated: dict[str, Any] = {}

        # Projects - mostly compatible
        if "projects" in raw:
            projects = []
            for p in raw["projects"]:
                project: dict[str, Any] = {
                    "name": p.get("name", "unknown"),
                    "path": p.get("path", ""),
                }
                if "goal" in p:
                    project["goal"] = p["goal"]
                if "git_repo_path" in p:
                    project["git_repo_path"] = p["git_repo_path"]
                # Ignore legacy per-project terminal_backend - now global only
                projects.append(project)
            migrated["projects"] = projects

        # scan_interval - direct mapping
        if "scan_interval" in raw:
            migrated["scan_interval"] = raw["scan_interval"]

        # terminal_backend - direct mapping
        if "terminal_backend" in raw:
            backend = raw["terminal_backend"]
            # Normalize to valid values
            if backend in ("wezterm", "tmux"):
                migrated["terminal_backend"] = backend
            else:
                logger.warning(f"Unknown terminal_backend '{backend}', defaulting to wezterm")
                migrated["terminal_backend"] = "wezterm"

        # WezTerm config - direct mapping
        if "wezterm" in raw:
            migrated["wezterm"] = {
                "workspace": raw["wezterm"].get("workspace", "claude-monitor"),
                "full_scrollback": raw["wezterm"].get("full_scrollback", True),
            }

        # Inference config - migrate from openrouter/priorities
        inference: dict[str, Any] = {}
        if "openrouter" in raw:
            or_config = raw["openrouter"]
            # Legacy model -> all fast tier purposes
            if "model" in or_config:
                model = or_config["model"]
                inference["detect_state"] = model
                inference["summarize_command"] = model
                inference["classify_response"] = model
                inference["quick_priority"] = model

        if "priorities" in raw and raw["priorities"].get("model"):
            # Priority-specific model -> deep tier
            model = raw["priorities"]["model"]
            inference["full_priority"] = model

        if inference:
            migrated["inference"] = inference

        # Notifications - migrate if present
        if "notifications" in raw:
            migrated["notifications"] = {
                "enabled": raw["notifications"].get("enabled", True),
                "on_awaiting_input": raw["notifications"].get("on_awaiting_input", True),
                "on_complete": raw["notifications"].get("on_complete", True),
            }

        # Port and debug
        if "port" in raw:
            migrated["port"] = raw["port"]
        if "debug" in raw:
            migrated["debug"] = raw["debug"]

        # Log deprecated fields that were ignored
        deprecated = [
            "idle_timeout_minutes",
            "stale_threshold_hours",
            "headspace",
            "session_sync",
            "tmux_logging",
        ]
        for field in deprecated:
            if field in raw:
                logger.info(f"Ignoring deprecated config field: {field}")

        return migrated


# Module-level singleton
_config_service: ConfigService | None = None


def get_config_service(config_path: str | Path = "config.yaml") -> ConfigService:
    """Get the global config service instance.

    Args:
        config_path: Path to config file (only used on first call).

    Returns:
        ConfigService singleton.
    """
    global _config_service
    if _config_service is None:
        _config_service = ConfigService(config_path)
    return _config_service


def reset_config_service() -> None:
    """Reset the global config service (for testing)."""
    global _config_service
    _config_service = None
