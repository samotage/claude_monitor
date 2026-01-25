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
from lib.sessions import (
    clear_previous_activity_states,
    get_previous_activity_states,
    set_previous_activity_states,
)

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
    "error": None,
    "content_hash": None  # Hash of session content for change detection
}

# Event-driven invalidation tracking
# When this timestamp changes, clients know to fetch fresh priorities
_priorities_invalidated_at: Optional[datetime] = None

# NOTE: Activity state tracking is now consolidated in lib/sessions.py
# Use get_previous_activity_states(), set_previous_activity_states(), clear_previous_activity_states()


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

    # Signal that priorities should refresh due to headspace change
    emit_priorities_invalidation(reason="headspace_update")

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

    Includes session IDs, activity states, and a hash of terminal content
    to ensure AI summaries are refreshed when session activity changes.

    Args:
        sessions: List of session dicts

    Returns:
        MD5 hash string of session state
    """
    # Build a string of data that affects prioritization
    # Include content_snippet so summaries refresh when terminal changes
    hash_parts = []
    for s in sorted(sessions, key=lambda x: x.get("session_id", "")):
        # Include content_snippet hash to detect activity changes
        content = s.get("content_snippet", "")
        # Use first 500 chars of content for hash stability
        # (full content changes too frequently with minor updates)
        content_hash = hashlib.md5(content[:500].encode()).hexdigest()[:8]
        part = f"{s.get('session_id', '')}|{s.get('activity_state', '')}|{content_hash}"
        hash_parts.append(part)

    hash_input = "||".join(hash_parts)
    return hashlib.md5(hash_input.encode()).hexdigest()


def is_cache_valid(current_sessions: list[dict] = None) -> tuple[bool, dict]:
    """Check if cached priorities are still valid.

    Cache is valid if:
    1. Cache exists
    2. No meaningful state transitions occurred

    State transitions that invalidate cache:
    - processing -> idle/input_needed (turn completed)
    - input_needed -> processing (user responded)
    - New session appeared
    - Session disappeared

    This approach saves API costs by only calling OpenRouter when
    Claude finishes a turn or user interaction changes, not on
    every terminal content update during processing.

    Args:
        current_sessions: Current session list to check for transitions

    Returns:
        Tuple of (is_valid, new_states)
        - is_valid: True if cache is valid and can be used
        - new_states: Current states dict (pass to update_activity_states after refresh)
    """
    global _priorities_cache

    if _priorities_cache["priorities"] is None:
        new_states = {}
        if current_sessions is not None:
            _, new_states = should_refresh_priorities(current_sessions)
        return False, new_states

    if _priorities_cache["timestamp"] is None:
        new_states = {}
        if current_sessions is not None:
            _, new_states = should_refresh_priorities(current_sessions)
        return False, new_states

    # Only invalidate on meaningful state transitions
    if current_sessions is not None:
        needs_refresh, new_states = should_refresh_priorities(current_sessions)
        if needs_refresh:
            return False, new_states  # State transition occurred, invalidate cache
        return True, new_states

    return True, {}


def get_cached_priorities(current_sessions: list[dict] = None) -> tuple[Optional[dict], dict]:
    """Get cached priorities if valid.

    Args:
        current_sessions: Current session list to compare hash against

    Returns:
        Tuple of (cached_priorities, new_states)
        - cached_priorities: Cached priority data or None if cache invalid
        - new_states: Current states dict (pass to update_activity_states after refresh)
    """
    global _priorities_cache

    is_valid, new_states = is_cache_valid(current_sessions)
    if is_valid:
        return {
            "priorities": _priorities_cache["priorities"],
            "timestamp": _priorities_cache["timestamp"].isoformat() if _priorities_cache["timestamp"] else None,
            "cache_hit": True,
        }, new_states
    return None, new_states


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


def reset_priorities_cache() -> None:
    """Reset the priorities cache to initial state.

    Clears all cached priorities and content hashes so sessions
    will be re-prioritized fresh on the next API call.
    """
    global _priorities_cache
    _priorities_cache["priorities"] = None
    _priorities_cache["timestamp"] = None
    _priorities_cache["error"] = None
    _priorities_cache["content_hash"] = None
    clear_previous_activity_states()


# =============================================================================
# Event-Driven Priorities Invalidation
# =============================================================================


def emit_priorities_invalidation(reason: str = "unknown") -> None:
    """Signal that priorities should be refreshed.

    Called when events occur that affect priority rankings:
    - Turn completion (processing -> idle/input_needed)
    - Headspace update
    - Session start/end

    This function:
    1. Updates the invalidation timestamp
    2. Triggers eager priority recomputation in a background thread
    3. Broadcasts an SSE event to connected dashboard clients

    Args:
        reason: Description of why invalidation occurred (for logging)
    """
    import threading

    global _priorities_invalidated_at
    _priorities_invalidated_at = datetime.now(timezone.utc)

    # Trigger eager priority recomputation in background thread
    # This ensures fresh data is ready when the client polls after receiving SSE
    def recompute():
        try:
            from monitor import compute_priorities
            compute_priorities(force_refresh=True)
        except Exception:
            pass  # Best effort - client will trigger refresh anyway

    threading.Thread(target=recompute, daemon=True).start()

    # Broadcast SSE event to connected dashboard clients
    try:
        from lib.sse import broadcast
        broadcast("priorities_invalidated", {"reason": reason})
    except Exception:
        pass  # SSE not critical - client can still poll


def get_last_invalidation_time() -> Optional[str]:
    """Get the timestamp of the last priorities invalidation event.

    Returns:
        ISO format timestamp string, or None if no invalidation has occurred
    """
    if _priorities_invalidated_at is None:
        return None
    return _priorities_invalidated_at.isoformat()


def should_refresh_priorities(sessions: list[dict]) -> tuple[bool, dict]:
    """Determine if we should call OpenRouter based on state transitions.

    This is a PURE function that does NOT mutate global state.
    Use update_activity_states() to commit the new state after cache refresh.

    Only triggers refresh on meaningful state changes to save API costs:
    - processing -> idle/input_needed (turn completed)
    - input_needed -> processing (user responded, new turn starting)
    - New session appeared
    - Session disappeared

    Args:
        sessions: Current session list with activity_state

    Returns:
        Tuple of (needs_refresh, new_states_dict)
        - needs_refresh: True if OpenRouter should be called
        - new_states_dict: The current state map (for passing to update_activity_states)
    """
    should_refresh = False
    current_states: dict[str, str] = {}

    # Get previous states from the consolidated tracking in lib/sessions.py
    previous_states = get_previous_activity_states()

    # Build current state map
    for session in sessions:
        sid = session.get("session_id", "")
        current_state = session.get("activity_state", "unknown")
        current_states[sid] = current_state

        previous_state = previous_states.get(sid)

        # Check for meaningful transitions
        if previous_state is None:
            # New session appeared
            should_refresh = True
        elif previous_state == "processing" and current_state in ("idle", "input_needed"):
            # Turn completed - Claude finished working
            should_refresh = True
        elif previous_state == "input_needed" and current_state == "processing":
            # User responded, new turn starting
            should_refresh = True

    # Check for disappeared sessions
    for sid in previous_states:
        if sid not in current_states:
            # Session disappeared
            should_refresh = True
            break

    return should_refresh, current_states


def update_activity_states(new_states: dict) -> None:
    """Explicitly update the activity states tracking after cache refresh.

    Call this AFTER a successful priorities refresh to commit the new state.
    This separation ensures is_cache_valid() is idempotent.

    Uses the consolidated state tracking in lib/sessions.py.

    Args:
        new_states: The new states dict from should_refresh_priorities()
    """
    set_previous_activity_states(new_states)


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
- For PROCESSING sessions with turn_command: leave activity_summary EMPTY (UI will show the command)
- For IDLE sessions: describe what was just completed based on terminal content
- For INPUT_NEEDED sessions: describe what question/decision is waiting
- Use past tense for completed work: "Fixed auth bug", "Added dark mode"
- Be specific: mention file names, features, or tasks when visible
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
        turn_command = session.get("turn_command", "")

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
        if turn_command:
            session_line += f" [turn_command: {turn_command[:80]}]"
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
        "content_snippet": s.get("content_snippet", ""),  # Terminal content for AI summarization
        "turn_command": s.get("turn_command", ""),  # User's command that started current turn (if processing)
    } for s in sessions]

    return {
        "headspace": headspace,
        "roadmaps": roadmaps,
        "states": states,
        "sessions": formatted_sessions
    }
