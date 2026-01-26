"""Agent routes for Claude Headspace.

Provides REST API endpoints for agent management:
- List all agents
- Get agent details
- Focus agent's terminal window
"""

import logging

from flask import Blueprint, current_app, jsonify, request

from src.backends.wezterm import get_wezterm_backend
from src.services.agent_store import AgentStore
from src.services.notification_service import get_notification_service

logger = logging.getLogger(__name__)

agents_bp = Blueprint("agents", __name__)


def _get_store() -> AgentStore:
    """Get the agent store from app extensions (shared instance)."""
    store = current_app.extensions.get("agent_store")
    if store is None:
        logger.warning("AgentStore not in extensions, creating new instance (TEST MODE)")
        store = AgentStore()
    return store


@agents_bp.route("/agents", methods=["GET"])
def list_agents():
    """List all agents with their current state.

    Returns:
        JSON list of agent objects with:
        - id: Agent ID
        - session_id: Terminal session ID
        - session_name: Terminal session name
        - project_id: Associated project ID (if any)
        - current_task: Current task state (if any)
        - created_at: When the agent was created
    """
    store = _get_store()
    agents = store.list_agents()

    logger.debug(f"[API] GET /agents - found {len(agents)} agents in store")

    result = []
    for agent in agents:
        current_task = store.get_current_task(agent.id)
        task_state = current_task.state.value if current_task else "no_task"

        logger.debug(
            f"[API] Agent {agent.id[:8]}: session={agent.session_name}, "
            f"task_state={task_state}, task_id={current_task.id[:8] if current_task else 'none'}"
        )

        result.append(
            {
                "id": agent.id,
                "session_id": agent.terminal_session_id,
                "session_name": agent.session_name,
                "project_id": agent.project_id,
                "current_task": {
                    "id": current_task.id,
                    "state": current_task.state.value,
                    "started_at": current_task.started_at.isoformat(),
                    "summary": current_task.summary,
                    "priority_score": current_task.priority_score,
                }
                if current_task
                else None,
                "created_at": agent.created_at.isoformat(),
            }
        )

    logger.debug(f"[API] GET /agents - returning {len(result)} agents")
    return jsonify({"agents": result})


@agents_bp.route("/agents/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    """Get detailed information about an agent.

    Args:
        agent_id: The agent ID.

    Returns:
        JSON object with full agent details and task history.
    """
    store = _get_store()
    agent = store.get_agent(agent_id)

    if agent is None:
        return jsonify({"error": "Agent not found"}), 404

    current_task = store.get_current_task(agent_id)

    return jsonify(
        {
            "id": agent.id,
            "session_id": agent.terminal_session_id,
            "session_name": agent.session_name,
            "project_id": agent.project_id,
            "current_task": {
                "id": current_task.id,
                "state": current_task.state.value,
                "started_at": current_task.started_at.isoformat(),
                "completed_at": current_task.completed_at.isoformat()
                if current_task.completed_at
                else None,
                "summary": current_task.summary,
                "priority_score": current_task.priority_score,
                "priority_rationale": current_task.priority_rationale,
            }
            if current_task
            else None,
            "created_at": agent.created_at.isoformat(),
        }
    )


@agents_bp.route("/agents/<agent_id>/focus", methods=["POST"])
def focus_agent(agent_id: str):
    """Focus the terminal window for an agent.

    Args:
        agent_id: The agent ID.

    Returns:
        JSON object with success status.
    """
    store = _get_store()
    agent = store.get_agent(agent_id)

    if agent is None:
        return jsonify({"error": "Agent not found"}), 404

    backend = get_wezterm_backend()

    if not backend.is_available():
        return jsonify({"error": "WezTerm backend not available"}), 503

    success = backend.focus_pane(agent.terminal_session_id)

    if success:
        return jsonify({"status": "focused"})
    else:
        return jsonify({"error": "Failed to focus terminal"}), 500


@agents_bp.route("/agents/<agent_id>/send", methods=["POST"])
def send_to_agent(agent_id: str):
    """Send text to an agent's terminal.

    Args:
        agent_id: The agent ID.

    Request body:
        {
            "text": "text to send",
            "enter": true  // whether to press enter after
        }

    Returns:
        JSON object with success status.
    """
    store = _get_store()
    agent = store.get_agent(agent_id)

    if agent is None:
        return jsonify({"error": "Agent not found"}), 404

    data = request.get_json() or {}
    text = data.get("text", "")
    enter = data.get("enter", False)

    if not text:
        return jsonify({"error": "No text provided"}), 400

    backend = get_wezterm_backend()

    if not backend.is_available():
        return jsonify({"error": "WezTerm backend not available"}), 503

    success = backend.send_text(agent.terminal_session_id, text, enter=enter)

    if success:
        return jsonify({"status": "sent"})
    else:
        return jsonify({"error": "Failed to send text"}), 500


@agents_bp.route("/agents/<agent_id>/content", methods=["GET"])
def get_agent_content(agent_id: str):
    """Get the terminal content for an agent.

    Args:
        agent_id: The agent ID.

    Query params:
        lines: Number of lines to retrieve (default: 100)

    Returns:
        JSON object with terminal content.
    """
    store = _get_store()
    agent = store.get_agent(agent_id)

    if agent is None:
        return jsonify({"error": "Agent not found"}), 404

    # Cap lines to prevent memory exhaustion (DoS protection)
    config = current_app.extensions.get("config")
    max_lines = config.wezterm.max_lines if config else 10000
    lines = min(request.args.get("lines", 100, type=int), max_lines)
    backend = get_wezterm_backend()

    if not backend.is_available():
        return jsonify({"error": "WezTerm backend not available"}), 503

    content = backend.get_content(agent.terminal_session_id, lines=lines)

    if content is None:
        return jsonify({"error": "Failed to get terminal content"}), 500

    return jsonify(
        {
            "content": content,
            "lines": len(content.split("\n")),
        }
    )


@agents_bp.route("/reset", methods=["POST"])
def reset_working_state():
    """Reset all working state for a clean slate.

    Clears:
    - All agents and tasks
    - Notification cooldowns
    - Inference caches

    This is useful when the dashboard gets into a bad state or
    when you want to start fresh without restarting the server.

    Returns:
        JSON object with reset status details.
    """
    try:
        store = _get_store()
        store.clear()

        notification_service = get_notification_service()
        notification_service.reset_cooldowns()

        return jsonify(
            {
                "success": True,
                "message": "Working state reset successfully",
                "details": {
                    "agents": "cleared",
                    "tasks": "cleared",
                    "notifications": "cooldowns_cleared",
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
