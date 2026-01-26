"""Priority routes for Claude Headspace.

Provides REST API endpoints for priority management:
- Get computed priorities for all agents
- Force priority recomputation
"""

from flask import Blueprint, jsonify, request

from src.services.agent_store import AgentStore
from src.services.priority_service import AgentContext, PriorityService

priorities_bp = Blueprint("priorities", __name__)


def _get_store() -> AgentStore:
    """Get the agent store singleton."""
    return AgentStore()


def _get_priority_service() -> PriorityService:
    """Get the priority service singleton."""
    return PriorityService()


@priorities_bp.route("/priorities", methods=["GET"])
def get_priorities():
    """Get priorities for all agents.

    Query params:
        force_refresh: If true, bypass cache and recompute (default: false)

    Returns:
        JSON object with:
        - priorities: Array of agent priority objects
        - headspace_focus: Current headspace focus
        - cached: Whether the result was from cache
    """
    force_refresh = request.args.get("force_refresh", "false").lower() == "true"

    store = _get_store()
    priority_service = _get_priority_service()

    # Get all agents
    agents = store.list_agents()
    headspace = store.get_headspace()

    if not agents:
        return jsonify(
            {
                "priorities": [],
                "headspace_focus": headspace.current_focus if headspace else None,
                "cached": False,
            }
        )

    # Build agent contexts
    agent_contexts = []
    for agent in agents:
        current_task = store.get_current_task(agent.id)
        agent_contexts.append(
            AgentContext(
                agent_id=agent.id,
                session_name=agent.session_name,
                project_id=agent.project_id,
                project_name=None,  # TODO: Get from project store
                state=current_task.state if current_task else None,
                task_summary=current_task.summary if current_task else None,
            )
        )

    # Compute priorities
    results = priority_service.compute_full_priorities(
        agents=agent_contexts,
        headspace=headspace,
        force_refresh=force_refresh,
    )

    # Format response with legacy-compatible field names for frontend
    # Frontend expects: priority_score, uuid_short, project_name, session_id,
    # activity_state, activity_summary, rationale
    priorities = []
    for agent_id, result in results.items():
        agent = next((a for a in agents if a.id == agent_id), None)
        current_task = store.get_current_task(agent_id) if agent else None

        # Get project name
        project = store.get_project(agent.project_id) if agent and agent.project_id else None
        project_name = project.name if project else "Unknown"

        # Map 5-state to legacy 3-state for frontend
        task_state = current_task.state.value if current_task else "idle"
        legacy_state_map = {
            "idle": "idle",
            "commanded": "processing",
            "processing": "processing",
            "awaiting_input": "input_needed",
            "complete": "idle",
        }
        activity_state = legacy_state_map.get(task_state, "idle")

        # Get terminal session ID (used as PID for legacy compatibility)
        terminal_id = agent.terminal_session_id if agent else None
        try:
            session_id = int(terminal_id) if terminal_id and terminal_id.isdigit() else None
        except (ValueError, AttributeError):
            session_id = None

        priorities.append(
            {
                # Legacy-compatible field names
                "priority_score": result.score,
                "uuid_short": agent_id[:8] if agent_id else "",
                "project_name": project_name,
                "session_id": session_id,
                "activity_state": activity_state,
                "activity_summary": current_task.summary if current_task else None,
                "rationale": result.rationale,
                # Also include new fields for completeness
                "agent_id": agent_id,
                "session_name": agent.session_name if agent else "Unknown",
                "state": task_state,
                "computed_at": result.computed_at.isoformat(),
            }
        )

    # Sort by priority score (highest first)
    priorities.sort(key=lambda p: p["priority_score"], reverse=True)

    return jsonify(
        {
            "priorities": priorities,
            "headspace_focus": headspace.current_focus if headspace else None,
            "cached": not force_refresh and priority_service.cache_size > 0,
        }
    )


@priorities_bp.route("/priorities/invalidate", methods=["POST"])
def invalidate_priorities():
    """Invalidate the priority cache.

    This will cause the next priority request to recompute all priorities.

    Returns:
        JSON object with invalidation status.
    """
    store = _get_store()
    priority_service = _get_priority_service()
    headspace = store.get_headspace()

    count = priority_service.invalidate_cache(headspace)

    return jsonify(
        {
            "status": "invalidated",
            "entries_cleared": count,
        }
    )
