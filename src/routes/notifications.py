"""Notification routes for Claude Headspace.

Provides REST API endpoints for notification management:
- Get notification settings
- Update notification settings
- Send test notification
"""

from flask import Blueprint, jsonify, request

from src.services.notification_service import get_notification_service

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
    data = request.get_json() or {}
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
