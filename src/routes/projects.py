"""Project routes for Claude Headspace.

Provides REST API endpoints for project management:
- Get/update project roadmap
- Get brain refresh briefing
- Get recently completed narrative
"""

import time
from collections import defaultdict
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from src.models.inference import InferencePurpose
from src.models.project import RoadmapItem
from src.services.agent_store import AgentStore
from src.services.git_analyzer import GitAnalyzer
from src.services.inference_service import InferenceService

projects_bp = Blueprint("projects", __name__)

# Simple rate limiting for expensive operations
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def rate_limit(max_requests: int | None = None, window_seconds: int | None = None):
    """Simple rate limiter decorator.

    Args:
        max_requests: Maximum requests allowed in window (defaults to config or 10).
        window_seconds: Time window in seconds (defaults to config or 60).
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Get limits from config or use defaults
            config = current_app.extensions.get("config")
            actual_max = max_requests
            actual_window = window_seconds

            if config:
                if actual_max is None:
                    actual_max = config.api_limits.rate_limit_requests
                if actual_window is None:
                    actual_window = config.api_limits.rate_limit_window
            else:
                actual_max = actual_max or 10
                actual_window = actual_window or 60

            key = f"{request.remote_addr}:{f.__name__}"
            now = time.time()

            # Clean old entries
            _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < actual_window]

            if len(_rate_limit_store[key]) >= actual_max:
                return jsonify({"error": "Rate limit exceeded. Try again later."}), 429

            _rate_limit_store[key].append(now)
            return f(*args, **kwargs)

        return wrapper

    return decorator


def _get_store() -> AgentStore:
    """Get the agent store singleton."""
    return AgentStore()


def _get_git_analyzer() -> GitAnalyzer:
    """Get a git analyzer instance."""
    return GitAnalyzer()


def _get_inference_service() -> InferenceService:
    """Get an inference service instance."""
    return InferenceService()


# =============================================================================
# Legacy Compatibility Routes - these use project NAME instead of ID
# =============================================================================


@projects_bp.route("/project/<name>/roadmap", methods=["GET"])
def legacy_get_roadmap_by_name(name: str):
    """Legacy: Get roadmap by project name.

    Provides backward compatibility with the legacy API which used
    project names instead of IDs.

    Args:
        name: The project name.

    Returns:
        JSON object with the roadmap.
    """
    store = _get_store()
    project = store.get_project_by_name(name)

    if project is None:
        return jsonify({"success": False, "error": f"Project '{name}' not found"}), 404

    return jsonify(
        {
            "success": True,
            "roadmap": {
                "next_up": {
                    "title": project.roadmap.next_up.title,
                    "why": project.roadmap.next_up.why,
                    "definition_of_done": project.roadmap.next_up.definition_of_done,
                }
                if project.roadmap.next_up
                else None,
                "upcoming": project.roadmap.upcoming,
                "later": project.roadmap.later,
                "not_now": project.roadmap.not_now,
                "recently_completed": project.roadmap.recently_completed,
            },
        }
    )


@projects_bp.route("/project/<name>/roadmap", methods=["POST"])
def legacy_update_roadmap_by_name(name: str):
    """Legacy: Update roadmap by project name.

    Provides backward compatibility with the legacy API.

    Args:
        name: The project name.

    Returns:
        JSON object with the updated roadmap.
    """
    store = _get_store()
    project = store.get_project_by_name(name)

    if project is None:
        return jsonify({"success": False, "error": f"Project '{name}' not found"}), 404

    data = request.get_json() or {}

    # Update next_up
    if "next_up" in data:
        next_up_data = data["next_up"]
        if next_up_data:
            project.roadmap.next_up = RoadmapItem(
                title=next_up_data.get("title", ""),
                why=next_up_data.get("why"),
                definition_of_done=next_up_data.get("definition_of_done"),
            )
        else:
            project.roadmap.next_up = None

    # Update lists
    if "upcoming" in data:
        project.roadmap.upcoming = data["upcoming"]
    if "later" in data:
        project.roadmap.later = data["later"]
    if "not_now" in data:
        project.roadmap.not_now = data["not_now"]

    store.update_project(project)

    return jsonify(
        {
            "success": True,
            "roadmap": {
                "next_up": {
                    "title": project.roadmap.next_up.title,
                    "why": project.roadmap.next_up.why,
                    "definition_of_done": project.roadmap.next_up.definition_of_done,
                }
                if project.roadmap.next_up
                else None,
                "upcoming": project.roadmap.upcoming,
                "later": project.roadmap.later,
                "not_now": project.roadmap.not_now,
            },
        }
    )


@projects_bp.route("/project/<name>/brain-refresh", methods=["GET"])
@rate_limit()
def legacy_brain_refresh_by_name(name: str):
    """Legacy: Get brain refresh briefing by project name.

    Args:
        name: The project name.

    Returns:
        JSON object with brain refresh briefing.
    """
    store = _get_store()
    project = store.get_project_by_name(name)

    if project is None:
        return jsonify({"success": False, "error": f"Project '{name}' not found"}), 404

    # Delegate to the ID-based route logic
    refresh = request.args.get("refresh_narrative", "false").lower() == "true"

    git_analyzer = _get_git_analyzer()
    narrative = git_analyzer.generate_progress_narrative(project, use_cache=not refresh)

    project.roadmap.recently_completed = narrative
    store.update_project(project)

    headspace = store.get_headspace()

    agents = [a for a in store.list_agents() if a.project_id == project.id]
    active_agents = []
    for agent in agents:
        task = store.get_current_task(agent.id)
        active_agents.append(
            {
                "id": agent.id,
                "session_name": agent.session_name,
                "state": task.state.value if task else "unknown",
            }
        )

    return jsonify(
        {
            "success": True,
            "headspace": {
                "focus": headspace.current_focus if headspace else None,
                "constraints": headspace.constraints if headspace else None,
            }
            if headspace
            else None,
            "roadmap": {
                "next_up": {
                    "title": project.roadmap.next_up.title,
                    "why": project.roadmap.next_up.why,
                }
                if project.roadmap.next_up
                else None,
                "upcoming": project.roadmap.upcoming[:5],
            },
            "recently_completed": narrative,
            "active_agents": active_agents,
        }
    )


# =============================================================================
# New Architecture Routes - these use project ID
# =============================================================================


@projects_bp.route("/projects", methods=["GET"])
def list_projects():
    """List all configured projects.

    Returns:
        JSON array of project objects.
    """
    store = _get_store()
    projects = store.list_projects()

    return jsonify(
        {
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "path": p.path,
                    "status": p.state.status.value,
                    "agent_count": len([a for a in store.list_agents() if a.project_id == p.id]),
                }
                for p in projects
            ]
        }
    )


@projects_bp.route("/projects/<project_id>", methods=["GET"])
def get_project(project_id: str):
    """Get detailed information about a project.

    Args:
        project_id: The project ID.

    Returns:
        JSON object with full project details.
    """
    store = _get_store()
    project = store.get_project(project_id)

    if project is None:
        return jsonify({"error": "Project not found"}), 404

    return jsonify(
        {
            "id": project.id,
            "name": project.name,
            "path": project.path,
            "goal": project.goal,
            "context": {
                "tech_stack": project.context.tech_stack,
                "target_users": project.context.target_users,
                "description": project.context.description,
            },
            "roadmap": {
                "next_up": {
                    "title": project.roadmap.next_up.title,
                    "why": project.roadmap.next_up.why,
                    "definition_of_done": project.roadmap.next_up.definition_of_done,
                }
                if project.roadmap.next_up
                else None,
                "upcoming": project.roadmap.upcoming,
                "later": project.roadmap.later,
                "not_now": project.roadmap.not_now,
                "recently_completed": project.roadmap.recently_completed,
                "recently_completed_at": project.roadmap.recently_completed_at.isoformat()
                if project.roadmap.recently_completed_at
                else None,
            },
            "state": {
                "status": project.state.status.value,
                "last_activity_at": project.state.last_activity_at.isoformat()
                if project.state.last_activity_at
                else None,
            },
        }
    )


@projects_bp.route("/projects/<project_id>/roadmap", methods=["GET"])
def get_roadmap(project_id: str):
    """Get the roadmap for a project.

    Args:
        project_id: The project ID.

    Returns:
        JSON object with the roadmap.
    """
    store = _get_store()
    project = store.get_project(project_id)

    if project is None:
        return jsonify({"error": "Project not found"}), 404

    return jsonify(
        {
            "next_up": {
                "title": project.roadmap.next_up.title,
                "why": project.roadmap.next_up.why,
                "definition_of_done": project.roadmap.next_up.definition_of_done,
            }
            if project.roadmap.next_up
            else None,
            "upcoming": project.roadmap.upcoming,
            "later": project.roadmap.later,
            "not_now": project.roadmap.not_now,
            "recently_completed": project.roadmap.recently_completed,
        }
    )


@projects_bp.route("/projects/<project_id>/roadmap", methods=["POST"])
def update_roadmap(project_id: str):
    """Update the roadmap for a project.

    Args:
        project_id: The project ID.

    Request body:
        {
            "next_up": {"title": "...", "why": "...", "definition_of_done": "..."},
            "upcoming": ["item1", "item2"],
            "later": ["item3"],
            "not_now": ["item4"]
        }

    Returns:
        JSON object with the updated roadmap.
    """
    store = _get_store()
    project = store.get_project(project_id)

    if project is None:
        return jsonify({"error": "Project not found"}), 404

    data = request.get_json() or {}

    # Update next_up
    if "next_up" in data:
        next_up_data = data["next_up"]
        if next_up_data:
            project.roadmap.next_up = RoadmapItem(
                title=next_up_data.get("title", ""),
                why=next_up_data.get("why"),
                definition_of_done=next_up_data.get("definition_of_done"),
            )
        else:
            project.roadmap.next_up = None

    # Update lists
    if "upcoming" in data:
        project.roadmap.upcoming = data["upcoming"]
    if "later" in data:
        project.roadmap.later = data["later"]
    if "not_now" in data:
        project.roadmap.not_now = data["not_now"]

    store.update_project(project)

    return jsonify(
        {
            "next_up": {
                "title": project.roadmap.next_up.title,
                "why": project.roadmap.next_up.why,
                "definition_of_done": project.roadmap.next_up.definition_of_done,
            }
            if project.roadmap.next_up
            else None,
            "upcoming": project.roadmap.upcoming,
            "later": project.roadmap.later,
            "not_now": project.roadmap.not_now,
        }
    )


@projects_bp.route("/projects/<project_id>/brain-refresh", methods=["GET"])
@rate_limit()  # Uses config defaults
def brain_refresh(project_id: str):
    """Get a brain refresh briefing for a project.

    This generates a context briefing for quickly spinning up on a project
    after being away for days or weeks.

    Args:
        project_id: The project ID.

    Query params:
        refresh_narrative: If true, regenerate the recently_completed narrative

    Returns:
        JSON object with:
        - headspace: Current focus
        - roadmap: Project roadmap
        - recently_completed: Git-derived narrative
        - active_agents: Currently active agents on this project
    """
    refresh = request.args.get("refresh_narrative", "false").lower() == "true"

    store = _get_store()
    project = store.get_project(project_id)

    if project is None:
        return jsonify({"error": "Project not found"}), 404

    # Get or refresh the recently_completed narrative
    git_analyzer = _get_git_analyzer()
    narrative = git_analyzer.generate_progress_narrative(project, use_cache=not refresh)

    # Update the project's roadmap with the narrative
    project.roadmap.recently_completed = narrative
    store.update_project(project)

    # Get headspace
    headspace = store.get_headspace()

    # Get active agents for this project
    agents = [a for a in store.list_agents() if a.project_id == project_id]
    active_agents = []
    for agent in agents:
        task = store.get_current_task(agent.id)
        active_agents.append(
            {
                "id": agent.id,
                "session_name": agent.session_name,
                "state": task.state.value if task else "unknown",
            }
        )

    return jsonify(
        {
            "headspace": {
                "focus": headspace.current_focus if headspace else None,
                "constraints": headspace.constraints if headspace else None,
            }
            if headspace
            else None,
            "roadmap": {
                "next_up": {
                    "title": project.roadmap.next_up.title,
                    "why": project.roadmap.next_up.why,
                }
                if project.roadmap.next_up
                else None,
                "upcoming": project.roadmap.upcoming[:5],
            },
            "recently_completed": narrative,
            "active_agents": active_agents,
        }
    )


@projects_bp.route("/projects/<project_id>/brain-reboot", methods=["GET"])
@rate_limit(max_requests=5)  # Stricter limit for expensive LLM operation
def brain_reboot(project_id: str):
    """Get a comprehensive brain reboot briefing for a project.

    This is an enhanced version of brain-refresh that uses LLM inference
    (BRAIN_REBOOT purpose) to generate a comprehensive context briefing
    for quickly spinning up on a project after being away.

    Args:
        project_id: The project ID.

    Query params:
        refresh: If true, regenerate all narratives (bypass cache)

    Returns:
        JSON object with:
        - briefing: LLM-generated comprehensive briefing
        - headspace: Current focus and constraints
        - roadmap: Project roadmap with next_up item
        - recently_completed: Git-derived progress narrative
        - active_agents: Currently active agents on this project
    """
    refresh = request.args.get("refresh", "false").lower() == "true"

    store = _get_store()
    project = store.get_project(project_id)

    if project is None:
        return jsonify({"error": "Project not found"}), 404

    # Get or refresh the recently_completed narrative from git
    git_analyzer = _get_git_analyzer()
    narrative = git_analyzer.generate_progress_narrative(project, use_cache=not refresh)

    # Update the project's roadmap with the narrative
    project.roadmap.recently_completed = narrative
    store.update_project(project)

    # Get headspace
    headspace = store.get_headspace()

    # Get active agents for this project
    agents = [a for a in store.list_agents() if a.project_id == project_id]
    active_agents = []
    for agent in agents:
        task = store.get_current_task(agent.id)
        active_agents.append(
            {
                "id": agent.id,
                "session_name": agent.session_name,
                "state": task.state.value if task else "unknown",
            }
        )

    # Use BRAIN_REBOOT inference to generate a comprehensive briefing
    inference = _get_inference_service()
    briefing_result = inference.call(
        purpose=InferencePurpose.BRAIN_REBOOT,
        input_data={
            "project_name": project.name,
            "project_goal": project.goal,
            "headspace_focus": headspace.current_focus if headspace else None,
            "headspace_constraints": headspace.constraints if headspace else None,
            "next_up": project.roadmap.next_up.title if project.roadmap.next_up else None,
            "next_up_why": project.roadmap.next_up.why if project.roadmap.next_up else None,
            "upcoming": project.roadmap.upcoming[:5],
            "recently_completed": narrative,
            "active_agent_count": len(active_agents),
            "active_states": [a["state"] for a in active_agents],
        },
        user_prompt=(
            f"Generate a brief context briefing (3-5 sentences) for returning to work on '{project.name}'. "
            f"Include: what the project does, current focus, recent progress, and what to work on next. "
            f"Be concise and actionable."
        ),
        project_id=project_id,
        use_cache=not refresh,
    )

    # Extract briefing from result
    if "error" in briefing_result.result:
        briefing = f"Project: {project.name}. Recent work: {narrative}"
    else:
        briefing = briefing_result.result.get(
            "content", briefing_result.result.get("briefing", str(briefing_result.result))
        )

    return jsonify(
        {
            "briefing": briefing,
            "headspace": {
                "focus": headspace.current_focus if headspace else None,
                "constraints": headspace.constraints if headspace else None,
            }
            if headspace
            else None,
            "roadmap": {
                "next_up": {
                    "title": project.roadmap.next_up.title,
                    "why": project.roadmap.next_up.why,
                    "definition_of_done": project.roadmap.next_up.definition_of_done,
                }
                if project.roadmap.next_up
                else None,
                "upcoming": project.roadmap.upcoming[:5],
            },
            "recently_completed": narrative,
            "active_agents": active_agents,
        }
    )
