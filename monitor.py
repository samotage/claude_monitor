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
from flask import Flask, jsonify, render_template, request

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
    apply_soft_transition,
    build_prioritisation_prompt,
    default_priority_order,
    get_cached_priorities,
    get_priorities_config,
    get_sessions_with_activity,
    is_headspace_enabled,
    is_priorities_enabled,
    load_headspace,
    parse_priority_response,
    save_headspace,
    get_headspace_history,
    update_priorities_cache,
)
from lib.iterm import focus_iterm_window_by_pid, get_pid_tty
from lib.notifications import (
    check_state_changes_and_notify,
    is_notifications_enabled,
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
    """API endpoint to focus an iTerm window by PID."""
    success = focus_iterm_window_by_pid(pid)
    return jsonify({"success": success})


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
# Routes - Debug API
# =============================================================================


@app.route("/api/debug/content/<int:pid>")
def api_debug_content(pid: int):
    """Debug endpoint to see terminal content for a specific PID."""
    from lib.iterm import get_iterm_windows
    from lib.sessions import parse_activity_state

    tty = get_pid_tty(pid)
    if not tty:
        return jsonify({"error": "PID not found or no TTY"})

    iterm_windows = get_iterm_windows()
    window_info = iterm_windows.get(tty, {})

    return jsonify({
        "pid": pid,
        "tty": tty,
        "window_title": window_info.get("title", ""),
        "content_tail": window_info.get("content_tail", "")[:500],  # First 500 chars for display
        "detected_state": parse_activity_state(
            window_info.get("title", ""),
            window_info.get("content_tail", "")
        )[0]
    })


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
    if not force_refresh:
        cached = get_cached_priorities(sessions)
        if cached:
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
                    "soft_transition_pending": cached["soft_transition_pending"]
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
                "soft_transition_pending": False
            }
        }

    # Build prompt and call AI
    messages = build_prioritisation_prompt(context)
    config = get_priorities_config()

    response_text, error = call_openrouter(messages, model=config["model"])

    if error:
        # Fallback to default ordering
        priorities = default_priority_order(sessions)
        update_priorities_cache(priorities, sessions=sessions, error=error)

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
                "soft_transition_pending": False,
                "error": f"AI unavailable ({error}), using default ordering"
            }
        }

    # Parse response
    priorities = parse_priority_response(response_text, sessions)

    # Apply soft transitions
    priorities, soft_pending = apply_soft_transition(priorities, sessions)

    # Update cache with content hash for change detection
    update_priorities_cache(priorities, sessions=sessions)

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
            "soft_transition_pending": soft_pending
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
# Application Entry Point
# =============================================================================


def main():
    """Run the monitor web server."""
    config = load_config()
    print(f"Claude Headspace starting...")
    print(f"Monitoring {len(config.get('projects', []))} projects")
    print(f"Refresh interval: {config.get('scan_interval', 2)}s")

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

    print(f"\nOpen http://localhost:5050 in your browser")
    print("Press Ctrl+C to stop\n")

    app.run(host="0.0.0.0", port=5050, debug=False)


if __name__ == "__main__":
    main()
