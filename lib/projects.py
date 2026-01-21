"""Project data management for Claude Monitor.

This module handles:
- Project YAML data loading and saving
- Roadmap validation and normalization
- CLAUDE.md parsing for project metadata
- Project registration
- Brain reboot briefings
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from config import load_config

# Path to project data directory
PROJECT_DATA_DIR = Path(__file__).parent.parent / "data" / "projects"

# Brain Reboot defaults
DEFAULT_STALE_THRESHOLD_HOURS = 4


# =============================================================================
# Project Data CRUD
# =============================================================================


def slugify_name(name: str) -> str:
    """Convert a project name to a slug for filename use.

    Converts to lowercase and replaces spaces with hyphens.
    Example: "My Project" -> "my-project"

    Args:
        name: Project name

    Returns:
        Slugified name for use in filenames
    """
    return name.lower().replace(" ", "-")


def get_project_data_path(name: str) -> Path:
    """Get the path to a project's YAML data file.

    Args:
        name: Project name (will be slugified)

    Returns:
        Path to data/projects/<slug>.yaml
    """
    slug = slugify_name(name)
    return PROJECT_DATA_DIR / f"{slug}.yaml"


def load_project_data(name_or_path: str) -> Optional[dict]:
    """Load a project's YAML data.

    Args:
        name_or_path: Project name or direct path to YAML file

    Returns:
        Project data dict or None if not found
    """
    # If it looks like a path, use directly
    if name_or_path.endswith(".yaml") or "/" in name_or_path:
        path = Path(name_or_path)
    else:
        path = get_project_data_path(name_or_path)

    if path.exists():
        try:
            return yaml.safe_load(path.read_text())
        except Exception:
            return None
    return None


def save_project_data(name: str, data: dict) -> bool:
    """Save a project's YAML data.

    Updates the refreshed_at timestamp automatically.

    Args:
        name: Project name (will be slugified)
        data: Project data dict

    Returns:
        True if saved successfully
    """
    path = get_project_data_path(name)

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Update refreshed_at timestamp
    if "context" not in data:
        data["context"] = {}
    data["context"]["refreshed_at"] = datetime.now(timezone.utc).isoformat()

    try:
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True))
        return True
    except Exception as e:
        print(f"Warning: Failed to save project data for {name}: {e}")
        return False


def list_project_data() -> list[dict]:
    """List all registered projects with their data.

    Returns:
        List of project data dicts
    """
    projects = []
    if PROJECT_DATA_DIR.exists():
        for yaml_file in PROJECT_DATA_DIR.glob("*.yaml"):
            data = load_project_data(str(yaml_file))
            if data:
                projects.append(data)
    return projects


# =============================================================================
# Roadmap Management
# =============================================================================


def validate_roadmap_data(roadmap: dict) -> tuple[bool, str]:
    """Validate roadmap data structure.

    Args:
        roadmap: Roadmap dict to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(roadmap, dict):
        return False, "Roadmap must be an object"

    # Validate next_up if present
    if "next_up" in roadmap:
        next_up = roadmap["next_up"]
        if next_up is not None and not isinstance(next_up, dict):
            return False, "next_up must be an object or null"
        if isinstance(next_up, dict):
            for field in ["title", "why", "definition_of_done"]:
                if field in next_up and not isinstance(next_up[field], (str, type(None))):
                    return False, f"next_up.{field} must be a string or null"

    # Validate list fields
    for field in ["upcoming", "later", "not_now"]:
        if field in roadmap:
            value = roadmap[field]
            if value is not None and not isinstance(value, list):
                return False, f"{field} must be an array or null"
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if not isinstance(item, str):
                        return False, f"{field}[{i}] must be a string"

    return True, ""


def normalize_roadmap(roadmap: Optional[dict]) -> dict:
    """Normalize roadmap data, ensuring consistent structure.

    Handles empty `{}` and missing fields by providing defaults.

    Args:
        roadmap: Raw roadmap dict (may be None or {})

    Returns:
        Normalized roadmap dict with all fields present
    """
    if roadmap is None:
        roadmap = {}

    return {
        "next_up": roadmap.get("next_up") or {
            "title": "",
            "why": "",
            "definition_of_done": ""
        },
        "upcoming": roadmap.get("upcoming") or [],
        "later": roadmap.get("later") or [],
        "not_now": roadmap.get("not_now") or [],
    }


# =============================================================================
# CLAUDE.md Parsing
# =============================================================================


def parse_claude_md(project_path: str) -> dict:
    """Parse a project's CLAUDE.md file to extract goal and tech stack.

    Args:
        project_path: Path to the project directory

    Returns:
        Dict with 'goal' and 'tech_stack' keys (empty strings if not found)
    """
    result = {"goal": "", "tech_stack": ""}

    claude_md_path = Path(project_path) / "CLAUDE.md"
    if not claude_md_path.exists():
        print(f"Info: No CLAUDE.md found at {project_path}")
        return result

    try:
        content = claude_md_path.read_text()
    except Exception as e:
        print(f"Warning: Could not read CLAUDE.md at {project_path}: {e}")
        return result

    # Extract Project Overview section for goal
    goal_match = re.search(
        r'##\s*Project\s*Overview\s*\n+(.*?)(?=\n##|\n---|\Z)',
        content,
        re.IGNORECASE | re.DOTALL
    )
    if goal_match:
        # Get first paragraph/meaningful content
        goal_text = goal_match.group(1).strip()
        # Take first non-empty line or first paragraph
        lines = [l.strip() for l in goal_text.split('\n') if l.strip()]
        if lines:
            result["goal"] = lines[0]

    # Extract Tech Stack section
    tech_match = re.search(
        r'##\s*Tech\s*Stack\s*\n+(.*?)(?=\n##|\n---|\Z)',
        content,
        re.IGNORECASE | re.DOTALL
    )
    if tech_match:
        tech_text = tech_match.group(1).strip()
        # Take first line or consolidate bullet points
        lines = [l.strip().lstrip('- ').lstrip('* ') for l in tech_text.split('\n') if l.strip()]
        if lines:
            # If multiple lines, join with commas
            result["tech_stack"] = ", ".join(lines[:5])  # Limit to first 5 items

    return result


# =============================================================================
# Project Registration
# =============================================================================


def register_project(name: str, path: str) -> bool:
    """Register a project by creating its YAML data file.

    Idempotent: Will not overwrite existing data.
    Seeds new projects with goal and tech_stack from CLAUDE.md.

    Args:
        name: Project display name
        path: Absolute path to project directory

    Returns:
        True if registration succeeded (new or existing)
    """
    data_path = get_project_data_path(name)

    # Idempotent: skip if already exists
    if data_path.exists():
        print(f"Info: Project '{name}' already registered at {data_path}")
        return True

    # Parse CLAUDE.md for goal and tech_stack
    claude_info = parse_claude_md(path)

    # Create project data structure
    data = {
        "name": name,
        "path": path,
        "goal": claude_info["goal"],
        "context": {
            "tech_stack": claude_info["tech_stack"],
            "target_users": "",
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
        "roadmap": {},
        "state": {},
        "recent_sessions": [],
        "history": {},
    }

    if save_project_data(name, data):
        print(f"Info: Registered project '{name}' at {data_path}")
        return True
    return False


def register_all_projects() -> None:
    """Register all projects from config.yaml that don't have data files.

    Called on monitor startup to ensure all configured projects have data files.
    """
    config = load_config()
    registered_count = 0

    for project in config.get("projects", []):
        name = project.get("name")
        path = project.get("path")

        if not name or not path:
            print(f"Warning: Skipping project with missing name or path: {project}")
            continue

        if register_project(name, path):
            registered_count += 1

    if registered_count > 0:
        print(f"Info: Project registration complete ({registered_count} projects)")


def get_readme_content() -> str:
    """Get README.md content.

    Returns:
        Content of README.md or a default message if not found
    """
    readme_path = Path(__file__).parent.parent / "README.md"
    if readme_path.exists():
        return readme_path.read_text()
    return "# README\n\nNo README.md found."


# =============================================================================
# Brain Reboot - Context Reload Feature
# =============================================================================


def get_stale_threshold_hours() -> float:
    """Get the configured stale threshold in hours.

    Returns:
        Stale threshold hours from config, or default of 4
    """
    config = load_config()
    return config.get("stale_threshold_hours", DEFAULT_STALE_THRESHOLD_HOURS)


def calculate_staleness(project_name: str) -> dict:
    """Calculate staleness information for a project.

    Args:
        project_name: Name of the project

    Returns:
        Dict with:
            - is_stale: bool - whether project exceeds stale threshold
            - last_activity: str or None - ISO timestamp of last activity
            - staleness_hours: float or None - hours since last activity
    """
    project_data = load_project_data(project_name)
    if project_data is None:
        return {
            "is_stale": False,
            "last_activity": None,
            "staleness_hours": None
        }

    # Try to get last activity from state.last_session_ended
    state = project_data.get("state", {})
    last_session_ended = state.get("last_session_ended")

    # Fallback to most recent session if state doesn't have timestamp
    if not last_session_ended:
        recent_sessions = project_data.get("recent_sessions", [])
        if recent_sessions:
            # Get the most recent session's ended_at
            last_session_ended = recent_sessions[0].get("ended_at")

    if not last_session_ended:
        return {
            "is_stale": False,
            "last_activity": None,
            "staleness_hours": None
        }

    # Parse the timestamp and calculate staleness
    try:
        if isinstance(last_session_ended, str):
            last_activity = datetime.fromisoformat(last_session_ended.replace("Z", "+00:00"))
        else:
            last_activity = last_session_ended

        now = datetime.now(timezone.utc)
        delta = now - last_activity
        staleness_hours = delta.total_seconds() / 3600

        threshold = get_stale_threshold_hours()
        is_stale = staleness_hours >= threshold

        return {
            "is_stale": is_stale,
            "last_activity": last_activity.isoformat(),
            "staleness_hours": round(staleness_hours, 1)
        }
    except Exception:
        return {
            "is_stale": False,
            "last_activity": None,
            "staleness_hours": None
        }


def generate_reboot_briefing(project_name: str) -> Optional[dict]:
    """Generate a structured briefing for quick context reload.

    Args:
        project_name: Name of the project

    Returns:
        Dict with briefing sections, or None if project not found
    """
    project_data = load_project_data(project_name)
    if project_data is None:
        return None

    # Extract roadmap section
    roadmap = project_data.get("roadmap", {})
    next_up = roadmap.get("next_up", {}) or {}
    upcoming = roadmap.get("upcoming", []) or []

    roadmap_briefing = {
        "focus": next_up.get("title") if next_up else None,
        "why": next_up.get("why") if next_up else None,
        "next_steps": upcoming[:3] if upcoming else []  # First 3 upcoming items
    }

    # Extract state section
    state = project_data.get("state", {})
    state_briefing = {
        "status": state.get("status"),
        "last_action": state.get("last_session_summary"),
        "last_session_time": state.get("last_session_ended")
    }

    # Extract recent sessions (condensed)
    recent_sessions = project_data.get("recent_sessions", [])
    recent_briefing = []
    for session in recent_sessions[:5]:  # Max 5 recent sessions
        ended_at = session.get("ended_at", "")
        # Format the date nicely
        try:
            if ended_at:
                dt = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                date_str = dt.strftime("%b %d")
            else:
                date_str = "Unknown"
        except Exception:
            date_str = "Unknown"

        recent_briefing.append({
            "date": date_str,
            "summary": session.get("summary", "")[:100],  # Truncate long summaries
            "files_count": session.get("files_changed", 0)
        })

    # Extract history section
    history = project_data.get("history", {})
    history_briefing = {
        "narrative": history.get("summary"),
        "period": history.get("last_compressed_at")
    }

    return {
        "roadmap": roadmap_briefing,
        "state": state_briefing,
        "recent": recent_briefing,
        "history": history_briefing
    }


# =============================================================================
# Priority Context Helpers
# =============================================================================


def get_all_project_roadmaps() -> dict:
    """Gather roadmap data for all registered projects.

    Returns:
        Dict mapping project_name to roadmap data (next_up, upcoming)
    """
    roadmaps = {}
    projects = list_project_data()

    for project in projects:
        name = project.get("name", "unknown")
        roadmap = project.get("roadmap", {})
        if roadmap:
            roadmaps[name] = {
                "next_up": roadmap.get("next_up"),
                "upcoming": roadmap.get("upcoming", [])
            }

    return roadmaps


def get_all_project_states() -> dict:
    """Gather current state summary for all registered projects.

    Returns:
        Dict mapping project_name to state data (summary, recent context)
    """
    states = {}
    projects = list_project_data()

    for project in projects:
        name = project.get("name", "unknown")
        state = project.get("state", {})
        recent_sessions = project.get("recent_sessions", [])

        states[name] = {
            "summary": state.get("summary"),
            "recent_sessions": recent_sessions[:3] if recent_sessions else []  # Last 3 sessions
        }

    return states
