"""Logging routes for Claude Headspace.

Provides REST API endpoints for log management:
- OpenRouter API call logs
- Terminal session logs
- Debug logging configuration
"""

from flask import Blueprint, jsonify, request
from lib.logging import get_log_stats, get_logs_since, read_openrouter_logs, search_logs
from lib.terminal_logging import (
    clear_terminal_logs,
    get_terminal_log_stats,
    get_terminal_logs_since,
    read_terminal_logs,
    search_terminal_logs,
)

# Import debug logging from the configured backend
# Using lib.tmux for backward compatibility - it delegates to the actual backend
from lib.tmux import get_debug_logging, set_debug_logging

logging_bp = Blueprint("logging", __name__)


# =============================================================================
# OpenRouter Logs
# =============================================================================


@logging_bp.route("/logs/openrouter", methods=["GET"])
def get_openrouter_logs():
    """Get OpenRouter API call logs.

    Query parameters:
        since: ISO 8601 timestamp - only return logs after this time
        search: Search query to filter logs

    Returns:
        JSON object with:
        - success: True
        - logs: List of log entries
        - count: Number of entries returned
    """
    since = request.args.get("since")
    search_query = request.args.get("search", "").strip()

    # Get logs (optionally filtered by timestamp)
    logs = get_logs_since(since) if since else read_openrouter_logs()

    # Apply search filter if provided
    if search_query:
        logs = search_logs(search_query, logs)

    return jsonify({"success": True, "logs": logs, "count": len(logs)})


@logging_bp.route("/logs/openrouter/stats", methods=["GET"])
def get_openrouter_stats():
    """Get aggregate statistics for OpenRouter API calls.

    Returns:
        JSON object with:
        - success: True
        - stats: Dict with total_calls, successful_calls, failed_calls,
                 total_cost, total_input_tokens, total_output_tokens
    """
    stats = get_log_stats()
    return jsonify({"success": True, "stats": stats})


# =============================================================================
# Terminal Logs
# =============================================================================


@logging_bp.route("/logs/terminal", methods=["GET"])
def get_terminal_logs():
    """Get terminal session message logs.

    Query params:
        since: ISO timestamp to get logs after (optional)
        search: Search query string (optional)
        session_id: Filter by session ID (optional)
        backend: Filter by backend - "tmux" or "wezterm" (optional)

    Returns:
        JSON object with:
        - success: True
        - logs: List of log entries
        - count: Number of entries returned
    """
    since = request.args.get("since")
    search_query = request.args.get("search", "")
    session_id = request.args.get("session_id")
    backend = request.args.get("backend")

    # Get logs based on filters
    logs = (
        get_terminal_logs_since(since, backend=backend)
        if since
        else read_terminal_logs(backend=backend)
    )

    # Apply search and session_id filters
    if search_query or session_id:
        logs = search_terminal_logs(search_query, logs, session_id, backend=backend)

    return jsonify({"success": True, "logs": logs, "count": len(logs)})


@logging_bp.route("/logs/terminal", methods=["DELETE"])
def clear_logs():
    """Clear all terminal session logs.

    Returns:
        JSON object with:
        - success: True/False
        - message/error: Result message
    """
    success = clear_terminal_logs()
    if success:
        return jsonify({"success": True, "message": "All terminal logs cleared"})
    else:
        return jsonify({"success": False, "error": "Failed to clear logs"}), 500


@logging_bp.route("/logs/terminal/stats", methods=["GET"])
def get_terminal_stats():
    """Get aggregate statistics for terminal session logs.

    Query params:
        backend: Filter by backend - "tmux" or "wezterm" (optional)

    Returns:
        JSON object with:
        - success: True
        - stats: Dict with total_entries, send_count, capture_count,
                 success_count, failure_count, unique_sessions
    """
    backend = request.args.get("backend")
    stats = get_terminal_log_stats(backend=backend)
    return jsonify({"success": True, "stats": stats})


# =============================================================================
# Debug Logging
# =============================================================================


@logging_bp.route("/logs/terminal/debug", methods=["GET"])
def get_debug_state():
    """Get terminal debug logging state.

    Returns:
        JSON object with:
        - success: True
        - debug_enabled: Boolean indicating if debug logging is on
    """
    return jsonify({"success": True, "debug_enabled": get_debug_logging()})


@logging_bp.route("/logs/terminal/debug", methods=["POST"])
def set_debug_state():
    """Set terminal debug logging state.

    Request body:
        enabled: boolean - whether to enable debug logging

    Returns:
        JSON object with:
        - success: True
        - debug_enabled: New debug state
    """
    from config import load_config, save_config

    data = request.get_json() or {}
    enabled = data.get("enabled", False)

    # Update in-memory state
    set_debug_logging(enabled)

    # Also update config file for persistence
    config = load_config()
    if "terminal_logging" not in config:
        config["terminal_logging"] = {}
    config["terminal_logging"]["debug_enabled"] = enabled
    save_config(config)

    return jsonify({"success": True, "debug_enabled": get_debug_logging()})
