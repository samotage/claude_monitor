"""Notification routes for Claude Headspace.

Provides REST API endpoints for notification management:
- Get notification settings
- Update notification settings
- Send test notification
"""

import logging

from flask import Blueprint, current_app, jsonify, request

from src.services.notification_service import get_notification_service

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications", methods=["GET"])
def get_notification_settings():
    """Get current notification settings.

    Returns:
        JSON object with:
        - enabled: Whether notifications are enabled
    """
    service = get_notification_service()

    return jsonify(
        {
            "enabled": service.enabled,
        }
    )


@notifications_bp.route("/notifications", methods=["POST"])
def update_notification_settings():
    """Update notification settings.

    Request body:
        {
            "enabled": true/false
        }

    Returns:
        JSON object with updated settings.
    """
    data = request.get_json() or {}
    enabled = data.get("enabled")

    if enabled is None:
        return jsonify({"error": "'enabled' field is required"}), 400

    service = get_notification_service()
    service.enabled = bool(enabled)

    return jsonify(
        {
            "enabled": service.enabled,
        }
    )


@notifications_bp.route("/notifications/test", methods=["POST"])
def send_test_notification():
    """Send a test notification.

    Request body (optional):
        {
            "title": "Custom title",
            "message": "Custom message"
        }

    Returns:
        JSON object with status.
    """
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    message = data.get("message")

    service = get_notification_service()

    # Force enable temporarily for test
    was_enabled = service.enabled
    service.enabled = True

    try:
        if title or message:
            success = service.notify_custom(
                title=title or "Test Notification",
                message=message or "This is a test notification",
            )
        else:
            success = service.test_notification()
    finally:
        service.enabled = was_enabled

    if success:
        return jsonify({"status": "sent"})
    else:
        return jsonify(
            {"error": "Failed to send notification. Is terminal-notifier installed?"}
        ), 500


@notifications_bp.route("/notifications/test/<int:pid>", methods=["POST"])
def send_test_notification_for_session(pid: int):
    """Send a test notification for a specific session (with click-to-focus).

    This allows testing the click-to-focus functionality by sending a notification
    that, when clicked, will focus the terminal window for the given session.

    Args:
        pid: The process ID (terminal_session_id) of the session.

    Returns:
        JSON object with status and session info.
    """
    # Find the session/agent with this terminal_session_id
    store = current_app.extensions.get("agent_store")
    if store is None:
        return jsonify({"success": False, "error": "Agent store not available"}), 503

    # Find agent by terminal_session_id
    agents = store.list_agents()
    agent = None
    for a in agents:
        try:
            if a.terminal_session_id and int(a.terminal_session_id) == pid:
                agent = a
                break
        except (ValueError, TypeError):
            continue

    if agent is None:
        return jsonify({"success": False, "error": "Session not found"}), 404

    # Get project name
    project_name = "Unknown"
    if agent.project_id:
        project = store.get_project(agent.project_id)
        if project:
            project_name = project.name

    # Get task summary
    task = store.get_current_task(agent.id)
    task_summary = (task.summary or "")[:50] if task else ""

    service = get_notification_service()

    # Force enable temporarily for test
    was_enabled = service.enabled
    service.enabled = True

    try:
        success = service.notify_input_needed(
            project_name=project_name,
            context=task_summary or "Test notification",
            session_id=str(pid),
        )
    finally:
        service.enabled = was_enabled

    return jsonify(
        {
            "success": success,
            "project": project_name,
            "task": task_summary,
        }
    )
