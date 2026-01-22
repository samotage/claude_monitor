"""Headspace management and AI prioritisation for Claude Headspace.

This module handles:
- Loading and saving the user's current focus (headspace)
- Headspace history tracking
- Priorities cache management
- AI-powered session prioritisation
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from config import load_config
from lib.projects import get_all_project_roadmaps, get_all_project_states

# Path to the headspace data file
HEADSPACE_DATA_PATH = Path(__file__).parent.parent / "data" / "headspace.yaml"

# Defaults for priority configuration
DEFAULT_PRIORITIES_POLLING_INTERVAL = 60  # seconds
DEFAULT_PRIORITIES_MODEL = "anthropic/claude-3-haiku"
# Note: We no longer use time-based cache expiration.
# Cache only invalidates when session content actually changes.

# In-memory cache for priorities
_priorities_cache: dict = {
    "priorities": None,
    "timestamp": None,
    "pending_priorities": None,  # For soft transitions
    "error": None,
    "content_hash": None  # Hash of session content for change detection
}


# =============================================================================
# Headspace Data Management
# =============================================================================


def is_headspace_enabled() -> bool:
    """Check if the headspace feature is enabled in config.

    Returns:
        True if enabled (default), False if explicitly disabled
    """
    config = load_config()
    headspace_config = config.get("headspace", {})
    return headspace_config.get("enabled", True)


def is_headspace_history_enabled() -> bool:
    """Check if headspace history tracking is enabled in config.

    Returns:
        True if enabled, False if disabled (default)
    """
    config = load_config()
    headspace_config = config.get("headspace", {})
    return headspace_config.get("history_enabled", False)


def load_headspace() -> Optional[dict]:
    """Load the current headspace from data/headspace.yaml.

    Returns:
        Dict with current_focus, constraints, updated_at or None if not set
    """
    if not HEADSPACE_DATA_PATH.exists():
        return None

    try:
        data = yaml.safe_load(HEADSPACE_DATA_PATH.read_text())
        if data and "current_focus" in data:
            return {
                "current_focus": data.get("current_focus"),
                "constraints": data.get("constraints"),
                "updated_at": data.get("updated_at")
            }
        return None
    except Exception:
        return None


def save_headspace(current_focus: str, constraints: Optional[str] = None) -> dict:
    """Save headspace data to data/headspace.yaml.

    Appends previous value to history if history tracking is enabled.

    Args:
        current_focus: The user's current focus statement (required)
        constraints: Optional constraints string

    Returns:
        The saved headspace data dict
    """
    # Ensure data directory exists
    HEADSPACE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data for history
    existing_data = {}
    if HEADSPACE_DATA_PATH.exists():
        try:
            existing_data = yaml.safe_load(HEADSPACE_DATA_PATH.read_text()) or {}
        except Exception:
            existing_data = {}

    # Append to history if enabled and there's existing data
    if is_headspace_history_enabled() and existing_data.get("current_focus"):
        append_headspace_history(existing_data)

    # Create new headspace data
    updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    new_data = {
        "current_focus": current_focus,
        "constraints": constraints,
        "updated_at": updated_at
    }

    # Preserve history in the file
    if "history" in existing_data:
        new_data["history"] = existing_data["history"]

    # Write to file
    HEADSPACE_DATA_PATH.write_text(
        yaml.dump(new_data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )

    return {
        "current_focus": current_focus,
        "constraints": constraints,
        "updated_at": updated_at
    }


def append_headspace_history(headspace_data: dict) -> None:
    """Append a headspace entry to history.

    Args:
        headspace_data: The headspace data to archive to history
    """
    if not headspace_data.get("current_focus"):
        return

    # Load existing file to preserve history
    existing = {}
    if HEADSPACE_DATA_PATH.exists():
        try:
            existing = yaml.safe_load(HEADSPACE_DATA_PATH.read_text()) or {}
        except Exception:
            existing = {}

    # Initialize history list if needed
    history = existing.get("history", [])

    # Create history entry
    history_entry = {
        "current_focus": headspace_data.get("current_focus"),
        "constraints": headspace_data.get("constraints"),
        "updated_at": headspace_data.get("updated_at")
    }

    # Prepend to history (most recent first)
    history.insert(0, history_entry)

    # Keep only last 50 entries
    history = history[:50]

    # Update the existing data with new history
    existing["history"] = history

    # Write back
    HEADSPACE_DATA_PATH.write_text(
        yaml.dump(existing, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )


def get_headspace_history() -> list:
    """Get the list of previous headspace values.

    Returns:
        List of headspace history entries, or empty list if none
    """
    if not HEADSPACE_DATA_PATH.exists():
        return []

    try:
        data = yaml.safe_load(HEADSPACE_DATA_PATH.read_text())
        return data.get("history", []) if data else []
    except Exception:
        return []


# =============================================================================
# AI Session Prioritisation
# =============================================================================


def is_priorities_enabled() -> bool:
    """Check if the priorities feature is enabled in config.

    Returns:
        True if priorities feature is enabled (default: True)
    """
    config = load_config()
    priorities_config = config.get("priorities", {})
    return priorities_config.get("enabled", True)


def get_priorities_config() -> dict:
    """Get priorities configuration from config.yaml.

    Returns:
        Dict with 'enabled', 'polling_interval', 'model'
    """
    config = load_config()
    priorities = config.get("priorities", {})

    return {
        "enabled": priorities.get("enabled", True),
        "polling_interval": priorities.get("polling_interval", DEFAULT_PRIORITIES_POLLING_INTERVAL),
        "model": priorities.get("model", DEFAULT_PRIORITIES_MODEL)
    }


def compute_sessions_hash(sessions: list[dict]) -> str:
    """Compute a hash of session data for change detection.

    Uses only stable data (session IDs and activity states) to determine
    if we need to re-prioritize. Terminal content changes constantly
    but doesn't necessarily warrant a new API call.

    Args:
        sessions: List of session dicts

    Returns:
        MD5 hash string of session state
    """
    # Build a string of stable data that affects prioritization
    # Content changes constantly, but we only need to re-call AI when:
    # - Sessions appear/disappear
    # - Activity state changes (idle -> processing -> input_needed)
    hash_parts = []
    for s in sorted(sessions, key=lambda x: x.get("session_id", "")):
        part = f"{s.get('session_id', '')}|{s.get('activity_state', '')}"
        hash_parts.append(part)

    hash_input = "||".join(hash_parts)
    return hashlib.md5(hash_input.encode()).hexdigest()


def is_cache_valid(current_sessions: list[dict] = None) -> bool:
    """Check if cached priorities are still valid.

    Cache is valid if:
    1. Cache exists
    2. Content hash matches (nothing has changed)

    Note: We intentionally do NOT expire cache based on time.
    Only call the API when sessions actually change (appear/disappear,
    activity state changes). This prevents redundant API calls for
    stale/unchanged sessions.

    Args:
        current_sessions: Current session list to compare hash against

    Returns:
        True if cache is valid and can be used
    """
    global _priorities_cache

    if _priorities_cache["priorities"] is None:
        return False

    if _priorities_cache["timestamp"] is None:
        return False

    # Only invalidate if content has actually changed
    if current_sessions is not None and _priorities_cache["content_hash"] is not None:
        current_hash = compute_sessions_hash(current_sessions)
        if current_hash != _priorities_cache["content_hash"]:
            return False  # Content changed, invalidate cache

    return True


def get_cached_priorities(current_sessions: list[dict] = None) -> Optional[dict]:
    """Get cached priorities if valid.

    Args:
        current_sessions: Current session list to compare hash against

    Returns:
        Cached priority data or None if cache invalid
    """
    global _priorities_cache

    if is_cache_valid(current_sessions):
        return {
            "priorities": _priorities_cache["priorities"],
            "timestamp": _priorities_cache["timestamp"].isoformat() if _priorities_cache["timestamp"] else None,
            "cache_hit": True,
            "soft_transition_pending": _priorities_cache["pending_priorities"] is not None
        }
    return None


def update_priorities_cache(priorities: list[dict], sessions: list[dict] = None, error: str = None) -> None:
    """Update the priorities cache.

    Args:
        priorities: List of priority dicts
        sessions: Current sessions (used to compute content hash)
        error: Error message if prioritisation failed
    """
    global _priorities_cache
    _priorities_cache["priorities"] = priorities
    _priorities_cache["timestamp"] = datetime.now(timezone.utc)
    _priorities_cache["error"] = error
    if sessions:
        _priorities_cache["content_hash"] = compute_sessions_hash(sessions)


def get_priorities_cache() -> dict:
    """Get the current priorities cache state.

    Returns:
        The raw priorities cache dict
    """
    return _priorities_cache


def apply_soft_transition(new_priorities: list[dict], sessions: list[dict]) -> tuple[list[dict], bool]:
    """Apply soft transition logic for priority updates.

    If any session is processing, store new priorities as pending and return cached.

    Args:
        new_priorities: Newly computed priorities
        sessions: Current sessions with activity states

    Returns:
        Tuple of (priorities_to_return, soft_transition_pending)
    """
    global _priorities_cache

    # Check if any session is processing
    is_processing = any(s.get("activity_state") == "processing" for s in sessions)

    if is_processing:
        # Store as pending, return cached (if available) or new
        _priorities_cache["pending_priorities"] = new_priorities
        if _priorities_cache["priorities"]:
            return _priorities_cache["priorities"], True
        return new_priorities, True

    # No session processing - apply any pending priorities
    if _priorities_cache["pending_priorities"]:
        priorities_to_apply = _priorities_cache["pending_priorities"]
        _priorities_cache["pending_priorities"] = None
        return priorities_to_apply, False

    return new_priorities, False


def build_prioritisation_prompt(context: dict) -> list[dict]:
    """Build a token-efficient prompt for AI session prioritisation.

    Args:
        context: Dict with headspace, roadmaps, states, sessions

    Returns:
        List of message dicts for OpenRouter API
    """
    headspace = context.get("headspace")
    roadmaps = context.get("roadmaps", {})
    states = context.get("states", {})
    sessions = context.get("sessions", [])

    # System prompt
    system_prompt = """You are a focus assistant helping a developer prioritise their Claude Code sessions.
Rank sessions by relevance to the user's goals. Describe what each session is doing. Return JSON only.

Ranking factors (in order):
1. Relevance to headspace/current focus (if set)
2. Activity state: input_needed > idle > processing (sessions needing attention first)
3. Roadmap urgency: sessions related to next_up items rank higher
4. Recent work context

Output format (JSON only, no markdown):
{
  "priorities": [
    {
      "project_name": "...",
      "session_id": "...",
      "priority_score": 0-100,
      "rationale": "brief prioritization reason",
      "activity_summary": "1-sentence description of current activity"
    }
  ]
}

Activity summary guidelines:
- Describe the CURRENT action based on terminal content
- Use present continuous tense: "Reading...", "Writing...", "Waiting for..."
- Be specific: mention file names, features, or tasks when visible
- If session is idle, describe what was just completed or is ready
- Keep under 100 characters"""

    # Build user prompt with context
    user_parts = []

    # Headspace context
    if headspace:
        user_parts.append(f"HEADSPACE (user's current focus):\nFocus: {headspace.get('current_focus', 'Not set')}")
        if headspace.get("constraints"):
            user_parts.append(f"Constraints: {headspace['constraints']}")
    else:
        user_parts.append("HEADSPACE: Not set. Prioritise by roadmap urgency and activity state.")

    # Sessions to rank
    user_parts.append("\nSESSIONS TO RANK:")
    for session in sessions:
        proj = session["project_name"]
        sid = session["session_id"]
        state = session["activity_state"]
        task = session.get("task_summary", "")
        content = session.get("content_snippet", "")

        # Add roadmap context for this project
        roadmap = roadmaps.get(proj, {})
        next_up = roadmap.get("next_up", {})
        next_up_title = next_up.get("title", "") if isinstance(next_up, dict) else ""

        # Add state context
        proj_state = states.get(proj, {})
        summary = proj_state.get("summary", "")

        session_line = f"- {proj} (id:{sid}, state:{state})"
        if task:
            session_line += f" - {task}"
        if next_up_title:
            session_line += f" [next_up: {next_up_title}]"
        if summary:
            session_line += f" [project: {summary[:100]}]"

        user_parts.append(session_line)

        # Add terminal content snippet for AI to analyze (truncate to 500 chars in prompt)
        if content:
            truncated_content = content[:500]
            user_parts.append(f"  [terminal output: {truncated_content}]")

    user_prompt = "\n".join(user_parts)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def parse_priority_response(response_text: str, sessions: list[dict]) -> list[dict]:
    """Parse AI response to extract structured priority data.

    Args:
        response_text: Raw response from AI
        sessions: Original session list for fallback

    Returns:
        List of priority dicts with project_name, session_id, priority_score, rationale
    """
    if not response_text:
        return default_priority_order(sessions)

    try:
        # Try to parse JSON from response
        # Handle potential markdown code blocks
        text = response_text.strip()
        if text.startswith("```"):
            # Extract JSON from code block
            lines = text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines)

        data = json.loads(text)
        priorities = data.get("priorities", [])

        if not priorities:
            return default_priority_order(sessions)

        # Build lookup for uuid_short from sessions
        uuid_lookup = {s["session_id"]: s.get("uuid_short", "") for s in sessions}

        # Validate and normalize
        result = []
        for p in priorities:
            if not isinstance(p, dict):
                continue
            session_id = str(p.get("session_id", ""))
            result.append({
                "project_name": p.get("project_name", ""),
                "session_id": session_id,
                "uuid_short": uuid_lookup.get(session_id, ""),
                "priority_score": max(0, min(100, int(p.get("priority_score", 50)))),
                "rationale": str(p.get("rationale", ""))[:200],  # Limit rationale length
                "activity_summary": str(p.get("activity_summary", ""))[:100]  # AI-generated activity description
            })

        if not result:
            return default_priority_order(sessions)

        # Ensure all sessions are included (add missing ones at the end)
        included_ids = {p["session_id"] for p in result}
        for session in sessions:
            if session["session_id"] not in included_ids:
                result.append({
                    "project_name": session["project_name"],
                    "session_id": session["session_id"],
                    "uuid_short": session.get("uuid_short", ""),
                    "priority_score": 0,
                    "rationale": "Not ranked by AI",
                    "activity_summary": ""
                })

        # Sort by priority_score descending
        result.sort(key=lambda x: x["priority_score"], reverse=True)
        return result

    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return default_priority_order(sessions)


def default_priority_order(sessions: list[dict]) -> list[dict]:
    """Create default priority order when AI fails.

    Orders by: input_needed > idle > processing > unknown, then alphabetically.

    Args:
        sessions: List of session dicts

    Returns:
        List of priority dicts
    """
    state_order = {"input_needed": 0, "idle": 1, "processing": 2, "unknown": 3}

    sorted_sessions = sorted(
        sessions,
        key=lambda s: (state_order.get(s.get("activity_state", "unknown"), 3), s.get("project_name", ""))
    )

    return [{
        "project_name": s["project_name"],
        "session_id": s["session_id"],
        "uuid_short": s.get("uuid_short", ""),
        "priority_score": 50 - (i * 5),  # Descending scores
        "rationale": f"Default ordering by activity state ({s.get('activity_state', 'unknown')})",
        "activity_summary": ""  # No AI summary when using fallback
    } for i, s in enumerate(sorted_sessions)]


def is_any_session_processing(sessions: list[dict]) -> bool:
    """Check if any session is currently processing.

    Args:
        sessions: List of session dicts with activity_state

    Returns:
        True if any session has activity_state == "processing"
    """
    return any(s.get("activity_state") == "processing" for s in sessions)


def get_sessions_with_activity() -> list[dict]:
    """Get current sessions with their activity states.

    Returns:
        List of session dicts with session_id and activity_state
    """
    # Import here to avoid circular imports
    from lib.sessions import scan_sessions

    config = load_config()
    sessions = scan_sessions(config)

    return [{
        "session_id": str(s.get("pid", "")),  # Use PID as session_id for cache lookup
        "activity_state": s.get("activity_state", "unknown")
    } for s in sessions]


def aggregate_priority_context() -> dict:
    """Aggregate all context needed for priority computation.

    Gathers:
    - Current headspace (user's focus)
    - Project roadmaps (next_up items)
    - Project states (recent work)
    - Active sessions with activity state

    Returns:
        Dict with headspace, roadmaps, states, sessions
    """
    # Import here to avoid circular imports
    from lib.sessions import scan_sessions

    config = load_config()

    # Get all context
    headspace = load_headspace()
    roadmaps = get_all_project_roadmaps()
    states = get_all_project_states()
    sessions = scan_sessions(config)

    # Format sessions for prioritisation
    formatted_sessions = [{
        "project_name": s.get("project_name", "Unknown"),
        "session_id": str(s.get("pid", "")),  # Use PID as session_id
        "uuid_short": s.get("uuid_short", ""),
        "activity_state": s.get("activity_state", "unknown"),
        "task_summary": s.get("task_summary", ""),
        "content_snippet": s.get("content_snippet", "")  # Terminal content for AI summarization
    } for s in sessions]

    return {
        "headspace": headspace,
        "roadmaps": roadmaps,
        "states": states,
        "sessions": formatted_sessions
    }
