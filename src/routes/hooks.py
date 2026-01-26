"""Hooks routes for Claude Code lifecycle events.

These endpoints receive HTTP POST requests from Claude Code hooks,
enabling event-driven state detection without polling.

Endpoints:
- POST /hook/session-start   - Session started
- POST /hook/session-end     - Session ended
- POST /hook/stop            - Turn completed (primary signal)
- POST /hook/notification    - Notification received
- POST /hook/user-prompt-submit - User submitted prompt
- GET  /hook/status          - Hook receiver status
"""

import json
import logging

from flask import Blueprint, current_app, jsonify, request

hooks_bp = Blueprint("hooks", __name__)

logger = logging.getLogger(__name__)


def _log_hook_request(event_type: str, data: dict) -> None:
    """Log hook request with full data for debugging."""
    session_id = data.get("session_id", "unknown")[:8] if data.get("session_id") else "unknown"
    cwd = data.get("cwd", "")
    cwd_short = cwd.split("/")[-1] if cwd else "no-cwd"
    logger.info(f"[HOOK] {event_type} | session={session_id}... | cwd={cwd_short}")
    logger.debug(f"[HOOK] {event_type} full data: {json.dumps(data, default=str)}")


def _get_hook_receiver():
    """Get the HookReceiver from app extensions."""
    return current_app.extensions.get("hook_receiver")


def _get_config():
    """Get the app config from extensions."""
    return current_app.extensions.get("config")


@hooks_bp.route("/session-start", methods=["POST"])
def hook_session_start():
    """Handle session_start hook from Claude Code.

    Called when a new Claude Code session begins.

    Request body:
        {
            "session_id": "string",
            "event": "session-start",
            "cwd": "string",
            "timestamp": int
        }

    Returns:
        JSON with processing result.
    """
    data = request.get_json(silent=True) or {}
    _log_hook_request("session-start", data)

    config = _get_config()
    if config and not config.hooks.enabled:
        logger.info("[HOOK] session-start REJECTED: hooks disabled")
        return jsonify({"status": "disabled", "message": "Hooks are disabled"}), 200

    hook_receiver = _get_hook_receiver()
    if not hook_receiver:
        logger.error("[HOOK] session-start FAILED: hook receiver not available")
        return jsonify({"status": "error", "message": "Hook receiver not available"}), 200

    result = hook_receiver.process_event(
        event_type="session-start",
        session_id=data.get("session_id", "unknown"),
        cwd=data.get("cwd", ""),
        timestamp=data.get("timestamp"),
        data=data,
    )

    logger.info(
        f"[HOOK] session-start RESULT: success={result.success}, "
        f"agent_id={result.agent_id[:8] if result.agent_id else 'none'}, "
        f"state={result.new_state.value if result.new_state else 'none'}"
    )

    return jsonify(
        {
            "status": "ok" if result.success else "error",
            "agent_id": result.agent_id,
            "state": result.new_state.value if result.new_state else None,
            "message": result.message,
        }
    )


@hooks_bp.route("/session-end", methods=["POST"])
def hook_session_end():
    """Handle session_end hook from Claude Code.

    Called when a Claude Code session closes.

    Request body:
        {
            "session_id": "string",
            "event": "session-end",
            "timestamp": int
        }

    Returns:
        JSON with processing result.
    """
    config = _get_config()
    if config and not config.hooks.enabled:
        return jsonify({"status": "disabled", "message": "Hooks are disabled"}), 200

    hook_receiver = _get_hook_receiver()
    if not hook_receiver:
        return jsonify({"status": "error", "message": "Hook receiver not available"}), 200

    data = request.get_json(silent=True) or {}

    result = hook_receiver.process_event(
        event_type="session-end",
        session_id=data.get("session_id", "unknown"),
        cwd=data.get("cwd", ""),
        timestamp=data.get("timestamp"),
        data=data,
    )

    return jsonify(
        {
            "status": "ok" if result.success else "error",
            "agent_id": result.agent_id,
            "message": result.message,
        }
    )


@hooks_bp.route("/stop", methods=["POST"])
def hook_stop():
    """Handle stop hook from Claude Code.

    This is the PRIMARY signal that Claude has finished a turn.
    Called when Claude Code completes processing and is ready for input.

    Request body:
        {
            "session_id": "string",
            "event": "stop",
            "timestamp": int
        }

    Returns:
        JSON with processing result and new state.
    """
    data = request.get_json(silent=True) or {}
    _log_hook_request("stop", data)

    config = _get_config()
    if config and not config.hooks.enabled:
        logger.info("[HOOK] stop REJECTED: hooks disabled")
        return jsonify({"status": "disabled", "message": "Hooks are disabled"}), 200

    hook_receiver = _get_hook_receiver()
    if not hook_receiver:
        logger.error("[HOOK] stop FAILED: hook receiver not available")
        return jsonify({"status": "error", "message": "Hook receiver not available"}), 200

    result = hook_receiver.process_event(
        event_type="stop",
        session_id=data.get("session_id", "unknown"),
        cwd=data.get("cwd", ""),
        timestamp=data.get("timestamp"),
        data=data,
    )

    logger.info(
        f"[HOOK] stop RESULT: success={result.success}, "
        f"agent_id={result.agent_id[:8] if result.agent_id else 'none'}, "
        f"state={result.new_state.value if result.new_state else 'none'}, "
        f"msg={result.message}"
    )

    return jsonify(
        {
            "status": "ok" if result.success else "error",
            "agent_id": result.agent_id,
            "state": result.new_state.value if result.new_state else None,
            "message": result.message,
        }
    )


@hooks_bp.route("/notification", methods=["POST"])
def hook_notification():
    """Handle notification hook from Claude Code.

    Called for various Claude Code notifications.
    Used as a secondary validation signal, not for primary state changes.

    Request body:
        {
            "session_id": "string",
            "event": "notification",
            "timestamp": int
        }

    Returns:
        JSON with processing result.
    """
    config = _get_config()
    if config and not config.hooks.enabled:
        return jsonify({"status": "disabled", "message": "Hooks are disabled"}), 200

    hook_receiver = _get_hook_receiver()
    if not hook_receiver:
        return jsonify({"status": "error", "message": "Hook receiver not available"}), 200

    data = request.get_json(silent=True) or {}

    result = hook_receiver.process_event(
        event_type="notification",
        session_id=data.get("session_id", "unknown"),
        cwd=data.get("cwd", ""),
        timestamp=data.get("timestamp"),
        data=data,
    )

    return jsonify(
        {
            "status": "ok" if result.success else "error",
            "agent_id": result.agent_id,
            "message": result.message,
        }
    )


@hooks_bp.route("/user-prompt-submit", methods=["POST"])
def hook_user_prompt_submit():
    """Handle user_prompt_submit hook from Claude Code.

    Called when the user submits a prompt to Claude Code.
    Signals the start of a new turn - transitions to PROCESSING state.

    Request body:
        {
            "session_id": "string",
            "event": "user-prompt-submit",
            "timestamp": int
        }

    Returns:
        JSON with processing result and new state.
    """
    data = request.get_json(silent=True) or {}
    _log_hook_request("user-prompt-submit", data)

    config = _get_config()
    if config and not config.hooks.enabled:
        logger.info("[HOOK] user-prompt-submit REJECTED: hooks disabled")
        return jsonify({"status": "disabled", "message": "Hooks are disabled"}), 200

    hook_receiver = _get_hook_receiver()
    if not hook_receiver:
        logger.error("[HOOK] user-prompt-submit FAILED: hook receiver not available")
        return jsonify({"status": "error", "message": "Hook receiver not available"}), 200

    result = hook_receiver.process_event(
        event_type="user-prompt-submit",
        session_id=data.get("session_id", "unknown"),
        cwd=data.get("cwd", ""),
        timestamp=data.get("timestamp"),
        data=data,
    )

    logger.info(
        f"[HOOK] user-prompt-submit RESULT: success={result.success}, "
        f"agent_id={result.agent_id[:8] if result.agent_id else 'none'}, "
        f"state={result.new_state.value if result.new_state else 'none'}"
    )

    return jsonify(
        {
            "status": "ok" if result.success else "error",
            "agent_id": result.agent_id,
            "state": result.new_state.value if result.new_state else None,
            "message": result.message,
        }
    )


@hooks_bp.route("/status", methods=["GET"])
def hook_status():
    """Get hook receiver status.

    Returns information about hook activity and health.

    Returns:
        JSON with:
        - enabled: Whether hooks are enabled in config
        - active: Whether hooks have been received recently
        - last_event_time: Unix timestamp of last event
        - seconds_since_last_event: Time since last event
        - event_count: Total events processed
        - tracked_sessions: Number of tracked Claude Code sessions
    """
    config = _get_config()
    hooks_enabled = config.hooks.enabled if config else True

    hook_receiver = _get_hook_receiver()
    if not hook_receiver:
        return jsonify(
            {
                "enabled": hooks_enabled,
                "active": False,
                "message": "Hook receiver not initialized",
            }
        )

    status = hook_receiver.get_status()
    status["enabled"] = hooks_enabled

    return jsonify(status)


# Catch-all for unknown event types
@hooks_bp.route("/<event_type>", methods=["POST"])
def hook_catchall(event_type: str):
    """Handle unknown hook event types.

    Accepts any event type for forward compatibility.
    Logs the event but doesn't fail.

    Args:
        event_type: The event type from the URL.

    Returns:
        JSON acknowledging receipt.
    """
    config = _get_config()
    if config and not config.hooks.enabled:
        return jsonify({"status": "disabled", "message": "Hooks are disabled"}), 200

    hook_receiver = _get_hook_receiver()
    if not hook_receiver:
        return jsonify({"status": "ok", "message": "Hook receiver not available"}), 200

    data = request.get_json(silent=True) or {}

    logger.info(f"Received unknown hook event type: {event_type}")

    # Process the event (may fail for unknown types, but we still return 200)
    hook_receiver.process_event(
        event_type=event_type,
        session_id=data.get("session_id", "unknown"),
        cwd=data.get("cwd", ""),
        timestamp=data.get("timestamp"),
        data=data,
    )

    return jsonify(
        {
            "status": "ok",
            "message": f"Unknown event type: {event_type}",
        }
    )
