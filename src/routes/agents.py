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


# =============================================================================
# Legacy Compatibility Routes
# These routes provide backward compatibility with the legacy API
# =============================================================================


@agents_bp.route("/send/<session_id>", methods=["POST"])
def send_to_session(session_id: str):
    """Legacy: Send text to a session by session_id/uuid/uuid_short.

    This route provides backward compatibility with the legacy API.
    The session_id can be:
    - terminal_session_id (e.g., pane ID)
    - agent uuid
    - agent uuid_short (first 8 chars)

    Request body:
        {
            "text": "text to send",
            "enter": true  // whether to press enter after (default: true)
        }

    Returns:
        JSON object with success status.
    """
    store = _get_store()

    # Find agent by various identifiers
    agent = _find_agent_by_session_id(store, session_id)

    if agent is None:
        return jsonify({"success": False, "error": f"Session '{session_id}' not found"}), 404

    data = request.get_json() or {}
    text = data.get("text", "")
    enter = data.get("enter", True)  # Default True for legacy compat

    if not text:
        return jsonify({"success": False, "error": "No text provided"}), 400

    backend = current_app.extensions.get("terminal_backend")
    if backend is None:
        backend = get_wezterm_backend()

    if not backend.is_available():
        return jsonify({"success": False, "error": "Terminal backend not available"}), 503

    success = backend.send_text(agent.terminal_session_id, text, enter=enter)

    return jsonify({"success": success})


@agents_bp.route("/output/<session_id>", methods=["GET"])
def output_from_session(session_id: str):
    """Legacy: Capture output from a session by session_id/uuid/uuid_short.

    This route provides backward compatibility with the legacy API.
    The session_id can be:
    - terminal_session_id (e.g., pane ID)
    - agent uuid
    - agent uuid_short (first 8 chars)

    Query params:
        lines: Number of lines to capture (default: 100)

    Returns:
        JSON object with session output.
    """
    store = _get_store()

    # Find agent by various identifiers
    agent = _find_agent_by_session_id(store, session_id)

    if agent is None:
        return jsonify({"success": False, "error": f"Session '{session_id}' not found"}), 404

    # Cap lines to prevent memory exhaustion
    config = current_app.extensions.get("config")
    max_lines = config.wezterm.max_lines if config else 10000
    lines = min(request.args.get("lines", 100, type=int), max_lines)

    backend = current_app.extensions.get("terminal_backend")
    if backend is None:
        backend = get_wezterm_backend()

    if not backend.is_available():
        return jsonify({"success": False, "error": "Terminal backend not available"}), 503

    content = backend.get_content(agent.terminal_session_id, lines=lines)

    if content is None:
        return jsonify(
            {
                "success": False,
                "error": f"Failed to capture output from session '{session_id}'",
            }
        ), 500

    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            "session_type": "wezterm",
            "output": content,
            "lines": len(content.split("\n")),
        }
    )


@agents_bp.route("/readme", methods=["GET"])
def get_readme():
    """Get README as HTML for the help modal.

    Returns:
        JSON object with:
        - html: The README rendered as HTML
    """
    from pathlib import Path

    try:
        import markdown
    except ImportError:
        return jsonify({"error": "markdown package not installed"}), 500

    # Look for README.md in the project root
    readme_path = Path(__file__).parent.parent.parent / "README.md"

    if not readme_path.exists():
        return jsonify({"html": "<p>README.md not found</p>"})

    try:
        content = readme_path.read_text()
        html = markdown.markdown(content, extensions=["tables", "fenced_code", "codehilite"])
        return jsonify({"html": html})
    except Exception as e:
        logger.error(f"Failed to render README: {e}")
        return jsonify({"html": f"<p>Error rendering README: {e}</p>"})


@agents_bp.route("/wezterm/enter-pressed", methods=["POST"])
def wezterm_enter_pressed():
    """Receive Enter-key notification from WezTerm.

    Called by the WezTerm Lua hook when the user presses Enter
    in a claude-* pane. This provides an early signal for turn
    start detection, reducing latency vs. polling.

    Request body:
        {
            "pane_id": int  // WezTerm numeric pane ID
        }

    The signal is stored for consumption by the scan loop on the next poll.
    It does NOT directly trigger state changes.

    Returns:
        JSON with processing status.
    """
    data = request.get_json(silent=True) or {}
    pane_id = data.get("pane_id")

    if pane_id is None:
        return jsonify({"success": False, "error": "pane_id required"}), 400

    # Convert to string for storage
    pane_id_str = str(pane_id)

    # Get hook receiver to record the signal
    hook_receiver = current_app.extensions.get("hook_receiver")
    if hook_receiver:
        hook_receiver.record_enter_signal(pane_id_str)

    # Get event bus to broadcast SSE event
    event_bus = current_app.extensions.get("event_bus")
    if event_bus:
        event_bus.emit(
            "session_update",
            {
                "event": "enter_pressed",
                "pane_id": pane_id_str,
            },
        )

    logger.debug(f"[WezTerm] Enter pressed in pane {pane_id_str}")

    return jsonify({"success": True, "pane_id": pane_id_str})


def _find_agent_by_session_id(store: AgentStore, session_id: str):
    """Find an agent by session_id, uuid, or uuid_short.

    Args:
        store: The agent store.
        session_id: The identifier to search for.

    Returns:
        The matching agent, or None if not found.
    """
    agents = store.list_agents()

    for agent in agents:
        # Match by terminal_session_id
        if agent.terminal_session_id == session_id:
            return agent
        # Match by full uuid
        if agent.id == session_id:
            return agent
        # Match by uuid_short (first 8 chars)
        if agent.id[:8] == session_id:
            return agent
        # Match by session_name
        if agent.session_name == session_id:
            return agent

    return None


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


# =============================================================================
# Session Summarization Routes
# =============================================================================


@agents_bp.route("/session/<session_id>/summarise", methods=["GET"])
def summarise_session_route(session_id: str):
    """Generate a summary for a session.

    This route provides session summarization by parsing JSONL logs
    and extracting activity data (files modified, commands run, errors).

    Args:
        session_id: The session identifier (agent ID or UUID).

    Returns:
        JSON object with session summary.
    """
    from src.services.summarization_service import summarise_session

    store = _get_store()

    # Find the agent/session
    agent = _find_agent_by_session_id(store, session_id)
    if agent is None:
        return jsonify({"success": False, "error": f"Session '{session_id}' not found"}), 404

    # Get the project path for this agent
    project = store.get_project(agent.project_id) if agent.project_id else None
    if project is None:
        return jsonify({"success": False, "error": "Could not determine project for session"}), 400

    # Generate summary from JSONL logs
    summary = summarise_session(project.path, agent.id)

    if summary is None:
        return jsonify(
            {"success": False, "error": "Could not find session logs for summarization"}
        ), 404

    return jsonify({"success": True, "summary": summary})


# =============================================================================
# Focus Routes (iTerm/tmux integration)
# =============================================================================

# Note: /api/focus/<pid> is handled in app.py as a legacy deprecation stub.
# The route below provides actual tmux session focusing via iTerm.


@agents_bp.route("/focus/tmux/<session_name>", methods=["POST"])
def focus_by_tmux_session(session_name: str):
    """Focus the iTerm window running a tmux session.

    This route focuses the iTerm window that has the specified tmux
    session attached. Uses tmux client info to find the TTY.

    Args:
        session_name: The tmux session name (e.g., "claude-my-project-87c165e4").

    Returns:
        JSON object with success status.
    """
    from src.backends.iterm import focus_iterm_window_by_tmux_session

    success = focus_iterm_window_by_tmux_session(session_name)

    if success:
        return jsonify({"success": True})
    else:
        return jsonify(
            {
                "success": False,
                "error": f"Could not focus tmux session '{session_name}'",
            }
        ), 404
