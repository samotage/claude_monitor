"""History compression for Claude Monitor.

This module handles:
- OpenRouter API integration
- Compression queue management
- Background compression worker thread
- Session-to-history compression
"""

import threading
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from config import load_config
from lib.projects import load_project_data, save_project_data

# Default OpenRouter configuration
DEFAULT_OPENROUTER_MODEL = "anthropic/claude-3-haiku"
DEFAULT_COMPRESSION_INTERVAL = 300  # 5 minutes
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_TIMEOUT = 30  # seconds

# Retry configuration
RETRY_DELAYS = [60, 300, 1800]  # 1min, 5min, 30min

# Background thread reference
_compression_thread: Optional[threading.Thread] = None
_compression_stop_event = threading.Event()


# =============================================================================
# Compression Queue Management
# =============================================================================


def add_to_compression_queue(project_name: str, session_summary: dict) -> bool:
    """Add a session to the project's pending compression queue.

    Args:
        project_name: Name of the project
        session_summary: Session summary dict to queue for compression

    Returns:
        True if session was added to queue
    """
    project_data = load_project_data(project_name)
    if project_data is None:
        return False

    # Initialize pending_compressions if not present
    if "pending_compressions" not in project_data:
        project_data["pending_compressions"] = []

    # Check if already queued
    queued_ids = [s.get("session_id") for s in project_data["pending_compressions"]]
    if session_summary.get("session_id") in queued_ids:
        return True  # Already queued

    # Add to queue with metadata
    queue_entry = {
        **session_summary,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0
    }
    project_data["pending_compressions"].append(queue_entry)

    return save_project_data(project_name, project_data)


def get_pending_compressions(project_name: str) -> list[dict]:
    """Get all sessions pending compression for a project.

    Args:
        project_name: Name of the project

    Returns:
        List of session summaries pending compression
    """
    project_data = load_project_data(project_name)
    if project_data is None:
        return []

    return project_data.get("pending_compressions", [])


def remove_from_compression_queue(project_name: str, session_id: str) -> bool:
    """Remove a session from the compression queue after successful compression.

    Args:
        project_name: Name of the project
        session_id: ID of the session to remove

    Returns:
        True if session was removed
    """
    project_data = load_project_data(project_name)
    if project_data is None:
        return False

    if "pending_compressions" not in project_data:
        return True  # Nothing to remove

    original_count = len(project_data["pending_compressions"])
    project_data["pending_compressions"] = [
        s for s in project_data["pending_compressions"]
        if s.get("session_id") != session_id
    ]

    if len(project_data["pending_compressions"]) < original_count:
        return save_project_data(project_name, project_data)

    return True  # Session wasn't in queue


# =============================================================================
# Project History Management
# =============================================================================


def get_project_history(project_name: str) -> dict:
    """Get the compressed history for a project.

    Args:
        project_name: Name of the project

    Returns:
        Dict with 'summary' and 'last_compressed_at' (empty if no history)
    """
    project_data = load_project_data(project_name)
    if project_data is None:
        return {"summary": "", "last_compressed_at": None}

    history = project_data.get("history", {})
    return {
        "summary": history.get("summary", ""),
        "last_compressed_at": history.get("last_compressed_at")
    }


def update_project_history(project_name: str, summary: str) -> bool:
    """Update the project's compressed history.

    Args:
        project_name: Name of the project
        summary: The new compressed summary

    Returns:
        True if update was successful
    """
    project_data = load_project_data(project_name)
    if project_data is None:
        return False

    project_data["history"] = {
        "summary": summary,
        "last_compressed_at": datetime.now(timezone.utc).isoformat()
    }

    return save_project_data(project_name, project_data)


# =============================================================================
# OpenRouter API
# =============================================================================


def get_openrouter_config() -> dict:
    """Get OpenRouter configuration from config.yaml.

    Returns:
        Dict with 'api_key', 'model', 'compression_interval'
        Returns empty api_key if not configured.
    """
    config = load_config()
    openrouter = config.get("openrouter", {})

    return {
        "api_key": openrouter.get("api_key", ""),
        "model": openrouter.get("model", DEFAULT_OPENROUTER_MODEL),
        "compression_interval": openrouter.get("compression_interval", DEFAULT_COMPRESSION_INTERVAL)
    }


def call_openrouter(messages: list[dict], model: str = None) -> tuple[Optional[str], Optional[str]]:
    """Call OpenRouter chat completion API.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model to use (defaults to config or DEFAULT_OPENROUTER_MODEL)

    Returns:
        Tuple of (response_text, error_message)
        - On success: (response_text, None)
        - On error: (None, error_message)

    Note: API key is never logged or included in error messages.
    """
    config = get_openrouter_config()
    api_key = config["api_key"]

    if not api_key:
        return None, "OpenRouter API key not configured"

    if model is None:
        model = config["model"]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/samotage/claude_monitor",
        "X-Title": "Claude Monitor"
    }

    payload = {
        "model": model,
        "messages": messages
    }

    try:
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=OPENROUTER_TIMEOUT
        )

        if response.status_code == 429:
            return None, "rate_limited"

        if response.status_code == 401:
            return None, "authentication_failed"

        if response.status_code != 200:
            return None, f"API error: HTTP {response.status_code}"

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return None, "Empty response from API"

        return content, None

    except requests.Timeout:
        return None, "timeout"
    except requests.RequestException as e:
        # Sanitize error message to avoid leaking sensitive info
        return None, f"Request failed: {type(e).__name__}"


# =============================================================================
# Compression Logic
# =============================================================================


def build_compression_prompt(session_data: dict, existing_history: str = "") -> list[dict]:
    """Build the prompt for compressing a session into history.

    Args:
        session_data: Session summary dict with files_modified, commands_run, errors, etc.
        existing_history: Existing history summary to merge with (empty for first compression)

    Returns:
        List of message dicts for OpenRouter API
    """
    system_prompt = """You are a concise technical writer. Compress session activity into a narrative summary.
Focus on: what was worked on, key decisions, blockers encountered, current status.
Keep it brief but meaningful. Use past tense. No bullet points - write prose."""

    session_info = []
    if session_data.get("started_at"):
        session_info.append(f"Started: {session_data['started_at']}")
    if session_data.get("ended_at"):
        session_info.append(f"Ended: {session_data['ended_at']}")
    if session_data.get("files_modified"):
        files = session_data["files_modified"][:10]  # Limit to 10 files
        session_info.append(f"Files modified: {', '.join(files)}")
    if session_data.get("commands_run"):
        cmds = session_data["commands_run"][:5]  # Limit to 5 commands
        session_info.append(f"Commands: {', '.join(cmds)}")
    if session_data.get("errors"):
        errors = session_data["errors"][:3]  # Limit to 3 errors
        session_info.append(f"Errors: {'; '.join(errors)}")
    if session_data.get("summary"):
        session_info.append(f"Session summary: {session_data['summary']}")

    user_content = "Compress this session into the project history:\n\n"
    user_content += "\n".join(session_info)

    if existing_history:
        user_content += f"\n\nExisting history to merge with:\n{existing_history}"
        user_content += "\n\nMerge the new session into the existing history, maintaining narrative flow."
    else:
        user_content += "\n\nThis is the first session - create the initial history narrative."

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]


def compress_session(project_name: str, session_data: dict) -> tuple[bool, Optional[str]]:
    """Compress a session and update project history.

    Args:
        project_name: Name of the project
        session_data: Session summary dict to compress

    Returns:
        Tuple of (success, error_message)
    """
    # Get existing history
    history = get_project_history(project_name)
    existing_summary = history.get("summary", "")

    # Build and send compression request
    messages = build_compression_prompt(session_data, existing_summary)
    response, error = call_openrouter(messages)

    if error:
        return False, error

    # Update history with new compressed summary
    if update_project_history(project_name, response):
        return True, None
    else:
        return False, "Failed to save history"


def _increment_retry_count(project_name: str, session_id: str) -> None:
    """Increment the retry count for a queued session."""
    project_data = load_project_data(project_name)
    if project_data is None:
        return

    pending = project_data.get("pending_compressions", [])
    for session in pending:
        if session.get("session_id") == session_id:
            session["retry_count"] = session.get("retry_count", 0) + 1
            session["last_retry_at"] = datetime.now(timezone.utc).isoformat()
            break

    save_project_data(project_name, project_data)


def process_compression_queue(project_name: str) -> dict:
    """Process all pending compressions for a project.

    Handles retries with exponential backoff.

    Args:
        project_name: Name of the project

    Returns:
        Dict with 'processed', 'failed', 'remaining' counts
    """
    pending = get_pending_compressions(project_name)
    results = {"processed": 0, "failed": 0, "remaining": 0}

    for session in pending:
        session_id = session.get("session_id", "unknown")
        retry_count = session.get("retry_count", 0)

        success, error = compress_session(project_name, session)

        if success:
            remove_from_compression_queue(project_name, session_id)
            results["processed"] += 1
            print(f"Info: Compressed session {session_id[:8]}... for {project_name}")
        else:
            # Handle retry logic
            if error in ["rate_limited", "timeout"]:
                # Increment retry count for next cycle
                _increment_retry_count(project_name, session_id)
                results["remaining"] += 1
                print(f"Warning: Compression retry needed for {session_id[:8]}... ({error})")
            elif error == "authentication_failed":
                # Don't retry auth errors, but keep queued
                results["failed"] += 1
                print(f"Error: OpenRouter authentication failed (check API key)")
            else:
                # Other errors - increment retry count
                _increment_retry_count(project_name, session_id)
                results["remaining"] += 1
                print(f"Warning: Compression failed for {session_id[:8]}... ({error})")

    return results


# =============================================================================
# Background Compression Thread
# =============================================================================


def _compression_worker() -> None:
    """Background worker that processes compression queues periodically."""
    while not _compression_stop_event.is_set():
        config = get_openrouter_config()
        interval = config.get("compression_interval", DEFAULT_COMPRESSION_INTERVAL)

        # Process all projects
        main_config = load_config()
        projects = main_config.get("projects", [])

        for project in projects:
            project_name = project.get("name")
            if project_name:
                pending = get_pending_compressions(project_name)
                if pending:
                    process_compression_queue(project_name)

        # Wait for next cycle (check stop event periodically)
        for _ in range(int(interval)):
            if _compression_stop_event.is_set():
                break
            time.sleep(1)


def start_compression_thread() -> bool:
    """Start the background compression thread.

    Returns:
        True if thread was started, False if already running
    """
    global _compression_thread

    if _compression_thread is not None and _compression_thread.is_alive():
        return False  # Already running

    _compression_stop_event.clear()
    _compression_thread = threading.Thread(target=_compression_worker, daemon=True)
    _compression_thread.start()
    print("Info: Background compression thread started")
    return True


def stop_compression_thread() -> bool:
    """Stop the background compression thread.

    Returns:
        True if thread was stopped, False if not running
    """
    global _compression_thread

    if _compression_thread is None or not _compression_thread.is_alive():
        return False

    _compression_stop_event.set()
    _compression_thread.join(timeout=5)
    _compression_thread = None
    print("Info: Background compression thread stopped")
    return True
