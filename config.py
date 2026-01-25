"""Configuration management for Claude Headspace.

This module handles loading and saving the config.yaml file.
"""

from pathlib import Path

import yaml

# Path to the configuration file
CONFIG_PATH = Path(__file__).parent / "config.yaml"

# Default configuration values
DEFAULT_CONFIG = {
    "projects": [],
    "scan_interval": 2,
    "idle_timeout_minutes": 60,
    "stale_threshold_hours": 4,
    "openrouter": {
        "api_key": "",
        "model": "anthropic/claude-3-haiku",
        "compression_interval": 300,
    },
    "headspace": {
        "enabled": True,
        "history_enabled": True,
    },
    "priorities": {
        "enabled": True,
        # DEPRECATED: polling_interval is ignored; priorities refresh is event-driven.
        # Kept for backwards compatibility with existing config.yaml files.
        "polling_interval": 60,
        "model": "",
    },
    "session_sync": {
        "enabled": True,
        "interval": 60,
        "jsonl_tail_entries": 20,
    },
    "terminal_backend": "tmux",
    "wezterm": {
        "workspace": "claude-monitor",
        "full_scrollback": True,
    },
    "tmux_logging": {
        "debug_enabled": False,
    },
}


def load_config() -> dict:
    """Load configuration from config.yaml.

    Returns:
        Configuration dict with projects and settings.
        Returns default config if file doesn't exist.
    """
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text())
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Save configuration to config.yaml.

    Args:
        config: Configuration dict to save

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        CONFIG_PATH.write_text(
            yaml.dump(config, default_flow_style=False, sort_keys=False)
        )
        return True
    except Exception:
        return False
