"""Config routes for Claude Headspace.

Provides REST API endpoints for configuration management:
- GET /api/config - Get current configuration
- POST /api/config - Update configuration
"""

import logging

from flask import Blueprint, current_app, jsonify, request

from src.models.config import AppConfig
from src.services.config_service import ConfigService

config_bp = Blueprint("config", __name__)

logger = logging.getLogger(__name__)


def _get_config_service() -> ConfigService:
    """Get the config service from app extensions."""
    return current_app.extensions.get("config_service")


def _get_config() -> AppConfig:
    """Get the current config from app extensions."""
    return current_app.extensions.get("config")


@config_bp.route("/config", methods=["GET"])
def get_config():
    """Get the current configuration.

    Returns:
        JSON object with all configuration values.
    """
    config = _get_config()
    if not config:
        return jsonify({"error": "Config not loaded"}), 500

    return jsonify(config.model_dump(mode="json"))


@config_bp.route("/config", methods=["POST"])
def update_config():
    """Update the configuration.

    Request body should contain configuration fields to update.
    Only provided fields will be updated; others remain unchanged.

    Request body:
        {
            "projects": [...],
            "scan_interval": 2,
            "terminal_backend": "wezterm",
            ...
        }

    Returns:
        JSON object with the updated configuration.
    """
    config_service = _get_config_service()
    if not config_service:
        return jsonify({"error": "Config service not available"}), 500

    data = request.get_json(silent=True) or {}

    # Get current config
    current_config = config_service.get_config()

    # Build updated config dict
    updated_data = current_config.model_dump(mode="json")

    # Update with provided values
    for key, value in data.items():
        if key in updated_data:
            updated_data[key] = value

    # Validate and create new config
    try:
        new_config = AppConfig(**updated_data)
    except Exception as e:
        logger.warning(f"Config validation error: {e}")
        return jsonify({"error": f"Invalid configuration: {e}"}), 400

    # Save to disk
    if not config_service.save(new_config):
        return jsonify({"error": "Failed to save configuration"}), 500

    # Update the cached config
    config_service._config = new_config
    current_app.extensions["config"] = new_config

    logger.info(f"Configuration updated: {len(new_config.projects)} projects")

    return jsonify(new_config.model_dump(mode="json"))
