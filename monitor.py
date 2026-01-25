#!/usr/bin/env python3
"""Claude Headspace - Kanban-style dashboard for tracking Claude Code sessions.

This is the main Flask application entry point. Business logic is organized
in modules under lib/:
- lib/iterm.py - iTerm AppleScript integration
- lib/sessions.py - Session scanning and activity state parsing
- lib/headspace.py - Headspace and priorities management
- lib/notifications.py - macOS notification handling
- lib/projects.py - Project data, roadmap, and CLAUDE.md parsing
- lib/summarization.py - JSONL parsing and session summarization
- lib/compression.py - History compression with OpenRouter API

Configuration is in config.py.
HTML template is in templates/index.html.

Usage:
    python monitor.py
    # Then open http://localhost:5050 in your browser
"""

from datetime import datetime, timezone

import markdown
from flask import Flask, Response, jsonify, render_template, request

# Configuration
from config import load_config, save_config

# Library modules
from lib.compression import (
    DEFAULT_COMPRESSION_INTERVAL,
    add_to_compression_queue,
    get_openrouter_config,
    start_compression_thread,
)
from lib.headspace import (
    aggregate_priority_context,
    build_prioritisation_prompt,
    default_priority_order,
    get_cached_priorities,
    get_headspace_history,
    get_last_invalidation_time,
    get_priorities_config,
    get_sessions_with_activity,
    is_headspace_enabled,
    is_priorities_enabled,
    load_headspace,
    parse_priority_response,
    reset_priorities_cache,
    save_headspace,
    update_activity_states,
    update_priorities_cache,
)
from lib.iterm import focus_iterm_window_by_pid, focus_iterm_window_by_tmux_session, get_pid_tty
from lib.notifications import (
    check_state_changes_and_notify,
    is_notifications_enabled,
    reset_notification_state,
    send_macos_notification,
    set_notifications_enabled,
)
from lib.projects import (
    calculate_staleness,
    generate_reboot_briefing,
    get_readme_content,
    load_project_data,
    normalize_roadmap,
    register_all_projects,
    save_project_data,
    validate_roadmap_data,
)
from lib.sessions import scan_sessions
from lib.summarization import (
    find_session_log_file,
    summarise_session,
    update_project_state,
    add_recent_session,
)
from lib.compression import call_openrouter
from lib.session_sync import start_session_sync_thread

# Flask application
app = Flask(__name__, template_folder='templates', static_folder='static')


# =============================================================================
# Routes - Dashboard
# =============================================================================


@app.route("/")
def index():
    """Serve the main kanban dashboard."""
    config = load_config()
    return render_template(
        "index.html",
        scan_interval=config.get("scan_interval", 2),
    )


@app.route("/logging")
def logging_popout():
    """Serve the logging panel in standalone pop-out mode."""
    config = load_config()
    return render_template(
        "logging.html",
        scan_interval=config.get("scan_interval", 2),
    )


# =============================================================================
# Routes - Sessions API
# =============================================================================


@app.route("/api/sessions")
def api_sessions():
    """API endpoint to get all sessions."""
    config = load_config()
    sessions = scan_sessions(config)
    # Check for state changes and send macOS notifications
    check_state_changes_and_notify(sessions)
    return jsonify({
        "sessions": sessions,
        "projects": config.get("projects", []),
    })


@app.route("/api/focus/<int:pid>", methods=["POST"])
def api_focus(pid: int):
    """API endpoint to focus a terminal window by PID.

    Supports both iTerm (via AppleScript) and WezTerm (via CLI activate-pane).
    """
    config = load_config()
    backend_name = config.get("terminal_backend", "tmux")

    if backend_name == "wezterm":
        # Find session by PID and use WezTerm focus
        sessions = scan_sessions(config)
        for session in sessions:
            if session.get("pid") == pid and session.get("tmux_session"):
                from lib.backends.wezterm import focus_window as wezterm_focus
                success = wezterm_focus(session["tmux_session"])
                return jsonify({"success": success})
        return jsonify({"success": False})

    # iTerm/tmux: First try direct TTY matching (works for non-tmux sessions)
    success = focus_iterm_window_by_pid(pid)
    if success:
        return jsonify({"success": True})

    # For tmux sessions, look up the session name and search by content
    sessions = scan_sessions(config)
    for session in sessions:
        if session.get("pid") == pid and session.get("tmux_session"):
            success = focus_iterm_window_by_tmux_session(session["tmux_session"])
            return jsonify({"success": success})

    return jsonify({"success": False})


@app.route("/api/focus/tmux/<session_name>", methods=["POST"])
def api_focus_tmux(session_name: str):
    """API endpoint to focus an iTerm window by tmux session name."""
    success = focus_iterm_window_by_tmux_session(session_name)
    return jsonify({"success": success})


@app.route("/api/focus/session/<session_name>", methods=["POST"])
def api_focus_session(session_name: str):
    """API endpoint to focus a terminal window by session name.

    Backend-aware: uses WezTerm CLI or iTerm AppleScript as appropriate.
    """
    config = load_config()
    backend_name = config.get("terminal_backend", "tmux")

    if backend_name == "wezterm":
        from lib.backends.wezterm import focus_window as wezterm_focus
        success = wezterm_focus(session_name)
    else:
        success = focus_iterm_window_by_tmux_session(session_name)

    return jsonify({"success": success})


# =============================================================================
# Routes - Server-Sent Events API
# =============================================================================


@app.route("/api/events")
def api_events():
    """SSE endpoint for real-time dashboard updates.

    Clients connect here to receive push notifications for:
    - session_update: When Enter is pressed in WezTerm (immediate session refresh)
    - priorities_invalidated: When a turn completes (refresh AI priorities)

    The connection uses SSE (Server-Sent Events) which is a simple,
    HTTP-based streaming protocol for server-to-client push.
    """
    from lib.sse import add_client, remove_client, event_stream

    def stream():
        client_queue = add_client()
        try:
            yield from event_stream(client_queue)
        finally:
            remove_client(client_queue)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering if behind nginx
        }
    )


@app.route("/api/events/test", methods=["POST"])
def api_events_test():
    """Test endpoint to broadcast an SSE event (development only)."""
    from lib.sse import broadcast, get_client_count

    client_count = get_client_count()
    broadcast("session_update", {"session": "test", "event": "manual_test"})

    return jsonify({
        "success": True,
        "clients": client_count,
        "message": "Broadcast sent"
    })


# =============================================================================
# Routes - Notifications API
# =============================================================================


@app.route("/api/notifications", methods=["GET"])
def api_notifications_get():
    """Get notification settings."""
    return jsonify({"enabled": is_notifications_enabled()})


@app.route("/api/notifications", methods=["POST"])
def api_notifications_post():
    """Toggle notifications."""
    data = request.get_json() or {}
    set_notifications_enabled(data.get("enabled", True))
    return jsonify({"enabled": is_notifications_enabled()})


@app.route("/api/notifications/test", methods=["POST"])
def api_notifications_test():
    """Send a test notification."""
    success = send_macos_notification("Test Notification", "Notifications are working")
    return jsonify({"success": success})


@app.route("/api/notifications/test/<int:pid>", methods=["POST"])
def api_notifications_test_pid(pid: int):
    """Send a test notification for a specific session (with click-to-focus)."""
    config = load_config()
    sessions = scan_sessions(config)
    session = next((s for s in sessions if s.get("pid") == pid), None)
    if not session:
        return jsonify({"success": False, "error": "Session not found"})

    project = session.get("project_name", "Unknown")
    task = session.get("task_summary", "")[:50]
    success = send_macos_notification(
        "Test: Input Needed",
        f"{project}: {task}",
        pid=pid
    )
    return jsonify({"success": success, "project": project, "task": task})


# =============================================================================
# Routes - Reset API
# =============================================================================


def reset_working_state() -> dict:
    """Reset all in-memory working state.

    Clears:
    - Notification tracking state (previous session states)
    - Priorities cache (AI-computed priorities)
    - Turn tracking state (active and completed turns)
    - Activity state tracking (previous states for transition detection)
    - Enter signals (pending WezTerm signals)

    Returns:
        Dict with reset status information
    """
    from lib.sessions import (
        clear_previous_activity_states,
        clear_turn_tracking,
        clear_enter_signals,
        clear_scan_sessions_cache,
    )

    reset_notification_state()
    reset_priorities_cache()
    clear_previous_activity_states()
    clear_turn_tracking()
    clear_enter_signals()
    clear_scan_sessions_cache()

    return {
        "notification_state": "cleared",
        "priorities_cache": "cleared",
        "turn_tracking": "cleared",
        "activity_states": "cleared",
        "enter_signals": "cleared",
        "scan_cache": "cleared",
    }


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Reset all working state (sessions, priorities, notifications).

    Clears in-memory state so sessions are rediscovered fresh.
    """
    try:
        result = reset_working_state()
        print("Working state reset via API")
        return jsonify({
            "success": True,
            "message": "Working state reset successfully",
            "details": result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Routes - README API
# =============================================================================


@app.route("/api/readme")
def api_readme():
    """API endpoint to get README as HTML."""
    content = get_readme_content()
    html = markdown.markdown(
        content,
        extensions=["tables", "fenced_code", "codehilite"]
    )
    return jsonify({"html": html})


# =============================================================================
# Routes - Help Documentation API
# =============================================================================


@app.route("/api/help")
def api_help_index():
    """Get index of all help documentation pages."""
    from lib.help import load_help_index
    pages = load_help_index()
    return jsonify({
        "success": True,
        "pages": pages
    })


@app.route("/api/help/search")
def api_help_search():
    """Search help documentation."""
    from lib.help import search_help
    query = request.args.get("q", "")
    results = search_help(query)
    return jsonify({
        "success": True,
        "query": query,
        "results": results
    })


@app.route("/api/help/<slug>")
def api_help_page(slug: str):
    """Get a specific help page as HTML."""
    from lib.help import load_help_page
    page = load_help_page(slug)

    if page is None:
        return jsonify({
            "success": False,
            "error": f"Help page '{slug}' not found"
        }), 404

    # Convert markdown to HTML
    html = markdown.markdown(
        page["content"],
        extensions=["tables", "fenced_code", "codehilite"]
    )

    return jsonify({
        "success": True,
        "page": {
            "slug": page["slug"],
            "title": page["title"],
            "html": html,
            "keywords": page["keywords"],
            "headings": page["headings"]
        }
    })


# =============================================================================
# Routes - Logging API
# =============================================================================


@app.route("/api/logs/openrouter")
def api_logs_openrouter():
    """Get OpenRouter API call logs.

    Query parameters:
        since: ISO 8601 timestamp - only return logs after this time
        search: Search query to filter logs
    """
    from lib.logging import read_openrouter_logs, get_logs_since, search_logs

    since = request.args.get("since")
    search_query = request.args.get("search", "").strip()

    # Get logs (optionally filtered by timestamp)
    if since:
        logs = get_logs_since(since)
    else:
        logs = read_openrouter_logs()

    # Apply search filter if provided
    if search_query:
        logs = search_logs(search_query, logs)

    return jsonify({
        "success": True,
        "logs": logs,
        "count": len(logs)
    })


@app.route("/api/logs/openrouter/stats")
def api_logs_openrouter_stats():
    """Get aggregate statistics for OpenRouter API calls."""
    from lib.logging import get_log_stats

    stats = get_log_stats()
    return jsonify({
        "success": True,
        "stats": stats
    })


@app.route("/api/logs/tmux")
def api_logs_tmux():
    """Get tmux session message logs.

    Query params:
        since: ISO timestamp to get logs after (optional)
        search: Search query string (optional)
        session_id: Filter by session ID (optional)
    """
    from lib.tmux_logging import read_tmux_logs, get_tmux_logs_since, search_tmux_logs

    since = request.args.get("since")
    search_query = request.args.get("search", "")
    session_id = request.args.get("session_id")

    # Get logs based on filters
    if since:
        logs = get_tmux_logs_since(since)
    else:
        logs = read_tmux_logs()

    # Apply search and session_id filters
    if search_query or session_id:
        logs = search_tmux_logs(search_query, logs, session_id)

    return jsonify({
        "success": True,
        "logs": logs,
        "count": len(logs)
    })


@app.route("/api/logs/tmux/stats")
def api_logs_tmux_stats():
    """Get aggregate statistics for tmux session logs."""
    from lib.tmux_logging import get_tmux_log_stats

    stats = get_tmux_log_stats()
    return jsonify({
        "success": True,
        "stats": stats
    })


@app.route("/api/logs/tmux/debug", methods=["GET"])
def api_logs_tmux_debug_get():
    """Get tmux debug logging state."""
    from lib.tmux import get_debug_logging

    return jsonify({
        "success": True,
        "debug_enabled": get_debug_logging()
    })


@app.route("/api/logs/tmux/debug", methods=["POST"])
def api_logs_tmux_debug_post():
    """Set tmux debug logging state.

    Request body:
        enabled: boolean - whether to enable debug logging
    """
    from lib.tmux import set_debug_logging, get_debug_logging

    data = request.get_json() or {}
    enabled = data.get("enabled", False)

    # Update in-memory state
    set_debug_logging(enabled)

    # Also update config file for persistence
    config = load_config()
    if "tmux_logging" not in config:
        config["tmux_logging"] = {}
    config["tmux_logging"]["debug_enabled"] = enabled
    save_config(config)

    return jsonify({
        "success": True,
        "debug_enabled": get_debug_logging()
    })


# =============================================================================
# Routes - Roadmap API
# =============================================================================


@app.route("/api/project/<name>/roadmap", methods=["GET"])
def api_project_roadmap_get(name: str):
    """Get a project's roadmap data."""
    project_data = load_project_data(name)
    if project_data is None:
        return jsonify({
            "success": False,
            "error": f"Project '{name}' not found"
        }), 404

    roadmap = project_data.get("roadmap", {})
    normalized = normalize_roadmap(roadmap)

    return jsonify({
        "success": True,
        "data": normalized,
        "project_name": project_data.get("name", name)
    })


@app.route("/api/project/<name>/roadmap", methods=["POST"])
def api_project_roadmap_post(name: str):
    """Update a project's roadmap data."""
    # Load existing project data
    project_data = load_project_data(name)
    if project_data is None:
        return jsonify({
            "success": False,
            "error": f"Project '{name}' not found"
        }), 404

    # Parse request body
    try:
        roadmap_data = request.get_json()
        if roadmap_data is None:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Invalid JSON: {str(e)}"
        }), 400

    # Validate roadmap structure
    is_valid, error_msg = validate_roadmap_data(roadmap_data)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": error_msg
        }), 400

    # Update only the roadmap section, preserving other data
    project_data["roadmap"] = roadmap_data

    # Save the updated project data
    if save_project_data(name, project_data):
        normalized = normalize_roadmap(roadmap_data)
        return jsonify({
            "success": True,
            "data": normalized,
            "project_name": project_data.get("name", name)
        })
    else:
        return jsonify({
            "success": False,
            "error": "Failed to save roadmap data"
        }), 500


# =============================================================================
# Routes - Brain Refresh API
# =============================================================================


@app.route("/api/project/<permalink>/brain-refresh", methods=["GET"])
def api_project_brain_refresh(permalink: str):
    """Get a project's brain refresh briefing for quick context reload.

    Query params:
        session_id: Optional session UUID for session-specific context
    """
    # Get optional session_id from query params
    session_id = request.args.get("session_id")

    # Generate the briefing (permalink is the slugified project name)
    briefing = generate_reboot_briefing(permalink, session_id=session_id)
    if briefing is None:
        return jsonify({
            "success": False,
            "error": f"Project '{permalink}' not found"
        }), 404

    # Calculate staleness information
    staleness = calculate_staleness(permalink)

    return jsonify({
        "success": True,
        "briefing": briefing,
        "meta": staleness
    })


# =============================================================================
# Routes - Headspace API
# =============================================================================


@app.route("/api/headspace", methods=["GET"])
def api_headspace_get():
    """Get the current headspace data."""
    if not is_headspace_enabled():
        return jsonify({
            "success": False,
            "error": "Headspace feature is disabled"
        }), 404

    headspace = load_headspace()
    return jsonify({
        "success": True,
        "data": headspace
    })


@app.route("/api/headspace", methods=["POST"])
def api_headspace_post():
    """Update the headspace."""
    if not is_headspace_enabled():
        return jsonify({
            "success": False,
            "error": "Headspace feature is disabled"
        }), 404

    data = request.get_json() or {}
    current_focus = data.get("current_focus", "").strip()

    if not current_focus:
        return jsonify({
            "success": False,
            "error": "current_focus is required"
        }), 400

    constraints = data.get("constraints")
    if constraints:
        constraints = constraints.strip() or None

    saved = save_headspace(current_focus, constraints)
    return jsonify({
        "success": True,
        "data": saved
    })


@app.route("/api/headspace/history", methods=["GET"])
def api_headspace_history():
    """Get the headspace history."""
    if not is_headspace_enabled():
        return jsonify({
            "success": False,
            "error": "Headspace feature is disabled"
        }), 404

    history = get_headspace_history()
    return jsonify({
        "success": True,
        "data": history
    })


# =============================================================================
# Routes - Priorities API
# =============================================================================


@app.route("/api/priorities", methods=["GET"])
def api_priorities():
    """Get AI-ranked session priorities."""
    if not is_priorities_enabled():
        return jsonify({
            "success": False,
            "error": "Priorities feature is disabled"
        }), 404

    # Check for refresh parameter
    force_refresh = request.args.get("refresh", "").lower() == "true"

    result = compute_priorities(force_refresh=force_refresh)
    return jsonify(result)


def compute_priorities(force_refresh: bool = False) -> dict:
    """Compute session priorities using AI.

    Args:
        force_refresh: If True, bypass cache

    Returns:
        Dict with priorities, metadata, and any errors
    """
    # Check feature enabled
    if not is_priorities_enabled():
        return {
            "success": False,
            "error": "Priorities feature is disabled",
            "priorities": []
        }

    # Get current sessions FIRST (needed for content-based cache validation)
    context = aggregate_priority_context()
    sessions = context["sessions"]

    # Check cache unless forced refresh
    # Pass sessions so cache can check if content has changed
    # get_cached_priorities returns (cached_data, new_states) tuple
    cached, new_states = get_cached_priorities(sessions)
    if not force_refresh and cached:
        # CRITICAL: Update activity states even on cache hit
        # This prevents the same transition from being detected repeatedly
        # (Fixes issue where cache hit skipped state update, causing redundant refreshes)
        update_activity_states(new_states)

        # Get session states for filtering
        session_states = {s["session_id"]: s["activity_state"] for s in sessions}

        # Only include priorities for sessions that still exist
        valid_priorities = []
        for p in cached["priorities"]:
            if p["session_id"] in session_states:
                p["activity_state"] = session_states[p["session_id"]]
                valid_priorities.append(p)

        return {
            "success": True,
            "priorities": valid_priorities,
            "metadata": {
                "timestamp": cached["timestamp"],
                "headspace_summary": None,  # Not fetched for cache hit
                "cache_hit": True,
                "last_invalidated": get_last_invalidation_time(),
            }
        }

    if not sessions:
        return {
            "success": True,
            "priorities": [],
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "headspace_summary": context.get("headspace", {}).get("current_focus") if context.get("headspace") else None,
                "cache_hit": False,
                "last_invalidated": get_last_invalidation_time(),
            }
        }

    # Build prompt and call AI
    messages = build_prioritisation_prompt(context)
    config = get_priorities_config()

    response_text, error = call_openrouter(messages, model=config["model"], caller="priorities")

    if error:
        # Fallback to default ordering
        priorities = default_priority_order(sessions)
        update_priorities_cache(priorities, sessions=sessions, error=error)
        # Commit the activity state changes after cache update
        update_activity_states(new_states)

        # Add activity_state
        session_states = {s["session_id"]: s["activity_state"] for s in sessions}
        for p in priorities:
            p["activity_state"] = session_states.get(p["session_id"], "unknown")

        return {
            "success": True,
            "priorities": priorities,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "headspace_summary": context.get("headspace", {}).get("current_focus") if context.get("headspace") else None,
                "cache_hit": False,
                "error": f"AI unavailable ({error}), using default ordering",
                "last_invalidated": get_last_invalidation_time(),
            }
        }

    # Parse response
    priorities = parse_priority_response(response_text, sessions)

    # Update cache with content hash for change detection
    update_priorities_cache(priorities, sessions=sessions)
    # Commit the activity state changes after cache update
    update_activity_states(new_states)

    # Add activity_state to each priority
    session_states = {s["session_id"]: s["activity_state"] for s in sessions}
    for p in priorities:
        p["activity_state"] = session_states.get(p["session_id"], "unknown")

    headspace = context.get("headspace")
    headspace_summary = headspace.get("current_focus") if headspace else None

    return {
        "success": True,
        "priorities": priorities,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "headspace_summary": headspace_summary,
            "cache_hit": False,
            "last_invalidated": get_last_invalidation_time(),
        }
    }


# =============================================================================
# Routes - Session Summarization API
# =============================================================================


@app.route("/api/session/<session_id>/summarise", methods=["POST"])
def api_session_summarise(session_id: str):
    """Manually trigger summarisation for a specific session."""
    # Find which project this session belongs to
    config = load_config()
    projects = config.get("projects", [])

    # Search through all projects for a matching session
    for project in projects:
        project_path = project.get("path", "")
        project_name = project.get("name", "")

        if not project_path:
            continue

        # Check if session log exists for this project
        log_file = find_session_log_file(project_path, session_id)
        if log_file:
            # Found the session, generate summary
            summary = summarise_session(project_path, session_id)
            if summary:
                # Update project YAML
                update_project_state(project_name, summary)
                add_recent_session(project_name, summary)

                return jsonify({
                    "success": True,
                    "data": summary,
                    "project_name": project_name
                })
            else:
                return jsonify({
                    "success": False,
                    "error": f"Failed to generate summary for session {session_id}"
                }), 500

    # Session not found in any project
    return jsonify({
        "success": False,
        "error": f"Session '{session_id}' not found in any monitored project"
    }), 404


# =============================================================================
# Routes - Configuration API
# =============================================================================


@app.route("/api/config", methods=["GET"])
def api_config_get():
    """API endpoint to get current configuration."""
    config = load_config()
    return jsonify(config)


@app.route("/api/config", methods=["POST"])
def api_config_post():
    """API endpoint to save configuration."""
    try:
        new_config = request.get_json()
        if not new_config:
            return jsonify({"success": False, "error": "No data provided"})

        success = save_config(new_config)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to write config file"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# =============================================================================
# Routes - tmux Session Control API
# =============================================================================


@app.route("/api/send/<session_id>", methods=["POST"])
def api_send_to_session(session_id: str):
    """Send text to a tmux session.

    Request body:
        text: Text to send to the session
        enter: Whether to press Enter after sending (default: true)

    Only works with tmux sessions. iTerm sessions return an error.
    """
    from lib.tmux import send_keys, is_tmux_available

    if not is_tmux_available():
        return jsonify({
            "success": False,
            "error": "tmux is not available on this system"
        }), 400

    # Get request data
    data = request.get_json() or {}
    text = data.get("text", "")
    enter = data.get("enter", True)

    if not text:
        return jsonify({
            "success": False,
            "error": "No text provided"
        }), 400

    # Find the session
    config = load_config()
    sessions = scan_sessions(config)

    session = None
    for s in sessions:
        if s.get("session_id") == session_id or s.get("uuid") == session_id or s.get("uuid_short") == session_id:
            session = s
            break

    if not session:
        return jsonify({
            "success": False,
            "error": f"Session '{session_id}' not found"
        }), 404

    # Check if it's a tmux session
    if session.get("session_type") != "tmux":
        return jsonify({
            "success": False,
            "error": "Send is only supported for tmux sessions. This session is using iTerm (read-only)."
        }), 400

    tmux_session = session.get("tmux_session")
    if not tmux_session:
        return jsonify({
            "success": False,
            "error": "tmux session name not found"
        }), 400

    # Send the text (log_operation=True for user-initiated API calls)
    success = send_keys(tmux_session, text, enter=enter, log_operation=True)

    if success:
        return jsonify({
            "success": True,
            "session_id": session_id,
            "tmux_session": tmux_session
        })
    else:
        return jsonify({
            "success": False,
            "error": f"Failed to send text to tmux session '{tmux_session}'"
        }), 500


@app.route("/api/output/<session_id>", methods=["GET"])
def api_output_from_session(session_id: str):
    """Capture output from a session.

    Query params:
        lines: Number of lines to capture (default: 100)

    Works with both tmux and iTerm sessions.
    """
    from lib.tmux import capture_pane, is_tmux_available

    # Get query params
    try:
        lines = int(request.args.get("lines", 100))
    except ValueError:
        lines = 100

    # Find the session
    config = load_config()
    sessions = scan_sessions(config)

    session = None
    for s in sessions:
        if s.get("session_id") == session_id or s.get("uuid") == session_id or s.get("uuid_short") == session_id:
            session = s
            break

    if not session:
        return jsonify({
            "success": False,
            "error": f"Session '{session_id}' not found"
        }), 404

    # Get output based on session type
    if session.get("session_type") == "tmux":
        tmux_session = session.get("tmux_session")
        if not tmux_session:
            return jsonify({
                "success": False,
                "error": "tmux session name not found"
            }), 400

        if not is_tmux_available():
            return jsonify({
                "success": False,
                "error": "tmux is not available on this system"
            }), 400

        # log_operation=True for user-initiated API calls
        output = capture_pane(tmux_session, lines=lines, log_operation=True)
        if output is None:
            return jsonify({
                "success": False,
                "error": f"Failed to capture output from tmux session '{tmux_session}'"
            }), 500

        return jsonify({
            "success": True,
            "session_id": session_id,
            "session_type": "tmux",
            "output": output,
            "lines": lines
        })
    else:
        # iTerm session - use content_snippet from session data
        return jsonify({
            "success": True,
            "session_id": session_id,
            "session_type": "iterm",
            "output": session.get("content_snippet", ""),
            "lines": lines,
            "note": "iTerm sessions have limited output capture (last ~5000 chars)"
        })


# =============================================================================
# Routes - WezTerm Event API
# =============================================================================


@app.route("/api/wezterm/enter-pressed", methods=["POST"])
def api_wezterm_enter_pressed():
    """Receive Enter-key notification from WezTerm.

    Called by the WezTerm Lua hook when the user presses Enter
    in a claude-* pane. This provides an early signal for turn
    start detection, reducing latency vs. polling.

    Request body:
        pane_id: WezTerm numeric pane ID (int)

    The signal is stored for consumption by track_turn_cycle()
    on the next poll. It does NOT directly trigger state changes.
    """
    import time
    from lib.sessions import record_enter_signal, get_previous_activity_state

    data = request.get_json(silent=True) or {}
    pane_id = data.get("pane_id")

    if pane_id is None:
        return jsonify({"success": False, "error": "pane_id required"}), 400

    pane_id_str = str(pane_id)

    # Look up session name from pane_id
    session_name = _resolve_pane_to_session(pane_id_str)
    if not session_name:
        return jsonify({"success": False, "error": "unknown pane"}), 404

    # Check if the session is in input_needed or idle state
    # (Enter during processing is likely noise -- e.g., scrolling)
    current_state = get_previous_activity_state(session_name)
    if current_state not in ("idle", "input_needed", None):
        return jsonify({"success": True, "ignored": True, "reason": "not awaiting input"}), 200

    # Record the signal (also clears scan cache)
    record_enter_signal(session_name)

    # Small delay to allow Claude Code to start processing
    # The Enter key was sent after the curl was spawned, so Claude
    # should be starting to process by now, but give it a moment
    time.sleep(0.15)  # 150ms delay

    # Broadcast SSE event to connected dashboard clients
    # This triggers immediate session refresh instead of waiting for poll cycle
    from lib.sse import broadcast
    broadcast("session_update", {"session": session_name, "event": "enter_pressed"})
    print(f"[SSE] Enter-pressed for {session_name}, broadcast sent", flush=True)

    return jsonify({"success": True, "session": session_name}), 200


def _resolve_pane_to_session(pane_id_str: str):
    """Resolve a WezTerm pane_id to a session name.

    Uses the WezTerm backend's session_pane_map (reversed) and
    falls back to a live query if needed.

    Args:
        pane_id_str: The pane ID as a string

    Returns:
        Session name (e.g., "claude-myproject-abc123") or None
    """
    try:
        from lib.backends.wezterm import _session_pane_map, list_sessions as wezterm_list_sessions

        # Reverse lookup in cached map
        for name, pid in _session_pane_map.items():
            if pid == pane_id_str:
                return name

        # Cache miss: query WezTerm live (also populates _session_pane_map)
        wezterm_list_sessions()
        for name, pid in _session_pane_map.items():
            if pid == pane_id_str:
                return name
    except ImportError:
        pass

    return None


# =============================================================================
# Application Entry Point
# =============================================================================


def main():
    """Run the monitor web server."""
    config = load_config()
    print(f"Claude Headspace starting...")
    print(f"Monitoring {len(config.get('projects', []))} projects")
    print(f"Refresh interval: {config.get('scan_interval', 2)}s")

    # Reset working state on startup for clean slate
    reset_working_state()
    print("Working state reset (clean startup)")

    # Register all projects from config (creates YAML data files if missing)
    register_all_projects()

    # Start background compression thread if OpenRouter is configured
    openrouter_config = get_openrouter_config()
    if openrouter_config.get("api_key"):
        start_compression_thread()
        interval = openrouter_config.get("compression_interval", DEFAULT_COMPRESSION_INTERVAL)
        print(f"History compression enabled (interval: {interval}s)")
    else:
        print("History compression disabled (no OpenRouter API key)")

    # Start session sync thread if enabled
    session_sync_config = config.get("session_sync", {})
    if session_sync_config.get("enabled", True):
        start_session_sync_thread()
        interval = session_sync_config.get("interval", 60)
        print(f"Session sync enabled (interval: {interval}s)")
    else:
        print("Session sync disabled")

    # Configure tmux debug logging from config
    from lib.tmux import set_debug_logging
    tmux_logging_config = config.get("tmux_logging", {})
    debug_enabled = tmux_logging_config.get("debug_enabled", False)
    set_debug_logging(debug_enabled)
    if debug_enabled:
        print("tmux debug logging enabled (full payloads)")
    else:
        print("tmux debug logging disabled (events only)")

    print(f"\nOpen http://localhost:5050 in your browser")
    print("Press Ctrl+C to stop\n")

    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)


if __name__ == "__main__":
    main()
