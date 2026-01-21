"""Configuration management for Claude Monitor.

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
    "iterm_focus_delay": 0.1,
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
