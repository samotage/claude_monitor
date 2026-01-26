"""Headspace routes for Claude Headspace.

Provides REST API endpoints for headspace management:
- Get current headspace focus
- Update headspace focus
- Get headspace history
"""

from flask import Blueprint, jsonify, request

from src.services.agent_store import AgentStore

headspace_bp = Blueprint("headspace", __name__)


def _get_store() -> AgentStore:
    """Get the agent store singleton."""
    return AgentStore()


@headspace_bp.route("/headspace", methods=["GET"])
def get_headspace():
    """Get the current headspace focus.

    Returns:
        JSON object with:
        - focus: The current focus objective
        - constraints: Any constraints on work
        - updated_at: When the focus was last updated
    """
    store = _get_store()
    headspace = store.get_headspace()

    if headspace is None:
        return jsonify(
            {
                "focus": None,
                "constraints": None,
                "updated_at": None,
            }
        )

    return jsonify(
        {
            "focus": headspace.current_focus,
            "constraints": headspace.constraints,
            "updated_at": headspace.updated_at.isoformat(),
        }
    )


@headspace_bp.route("/headspace", methods=["POST"])
def update_headspace():
    """Update the headspace focus.

    Request body:
        {
            "focus": "New focus objective",
            "constraints": "Optional constraints"
        }

    Returns:
        JSON object with the updated headspace.
    """
    data = request.get_json() or {}
    focus = data.get("focus")
    constraints = data.get("constraints")

    if not focus:
        return jsonify({"error": "Focus is required"}), 400

    store = _get_store()
    # update_headspace handles both create (if none) and update cases
    headspace = store.update_headspace(focus, constraints)

    return jsonify(
        {
            "focus": headspace.current_focus,
            "constraints": headspace.constraints,
            "updated_at": headspace.updated_at.isoformat(),
        }
    )


@headspace_bp.route("/headspace/history", methods=["GET"])
def get_headspace_history():
    """Get the history of headspace focus changes.

    Query params:
        limit: Maximum number of entries to return (default: 10)

    Returns:
        JSON array of historical focus entries.
    """
    limit = request.args.get("limit", 10, type=int)
    store = _get_store()
    headspace = store.get_headspace()

    if headspace is None or not headspace.history:
        return jsonify({"history": []})

    history = [
        {
            "focus": entry.focus,
            "constraints": entry.constraints,
            "started_at": entry.started_at.isoformat(),
            "ended_at": entry.ended_at.isoformat(),
        }
        for entry in headspace.history[:limit]
    ]

    return jsonify({"history": history})
