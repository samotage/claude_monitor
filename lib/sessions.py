"""Session scanning and activity state parsing for Claude Headspace.

This module handles:
- Scanning project directories for active Claude sessions
- Parsing activity state from iTerm window titles
- Formatting session information
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from lib.iterm import get_iterm_windows, get_pid_tty, is_claude_process
from lib.summarization import prepare_content_for_summary


def scan_sessions(config: dict) -> list[dict]:
    """Scan all registered project directories for active sessions.

    Args:
        config: Configuration dict with 'projects' list

    Returns:
        List of session dicts with status info
    """
    sessions = []
    iterm_windows = get_iterm_windows()  # Returns {tty: {"title": str, "content_tail": str}}

    for project in config.get("projects", []):
        project_path = Path(project["path"])
        if not project_path.exists():
            continue

        # Find all .claude-monitor-*.json files
        for state_file in project_path.glob(".claude-monitor-*.json"):
            try:
                state = json.loads(state_file.read_text())
                session_uuid = state.get("uuid", "").lower()
                session_pid = state.get("pid")

                # Check if session has an iTerm window by matching PID to TTY
                window_info = None
                session_tty = None
                if session_pid:
                    # First verify this is actually a Claude process (prevents PID reuse issues)
                    if not is_claude_process(session_pid):
                        # PID was reused by another process - this session is dead
                        continue

                    session_tty = get_pid_tty(session_pid)
                    if session_tty:
                        window_info = iterm_windows.get(session_tty)

                # Only show sessions that have an active iTerm window
                # Sessions without windows are not displayed (window closed = session gone)
                if not window_info:
                    continue

                window_title = window_info.get("title", "")
                content_tail = window_info.get("content_tail", "")

                # Parse started_at
                started_at = state.get("started_at", "")
                try:
                    start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    elapsed = datetime.now(timezone.utc) - start_time
                    elapsed_str = format_elapsed(elapsed.total_seconds())
                except Exception:
                    elapsed_str = "unknown"

                # Extract activity state and task summary from window title + content
                activity_state, task_summary = parse_activity_state(window_title, content_tail)

                # Prepare terminal content for AI summarization
                content_snippet = prepare_content_for_summary(content_tail)

                sessions.append({
                    "uuid": session_uuid,
                    "uuid_short": session_uuid[-8:] if session_uuid else "unknown",
                    "project_name": project["name"],  # Use config name, not state file
                    "project_dir": state.get("project_dir", project["path"]),
                    "started_at": started_at,
                    "elapsed": elapsed_str,
                    "pid": session_pid,
                    "tty": session_tty,
                    "status": "active",
                    "activity_state": activity_state,
                    "window_title": window_title,
                    "task_summary": task_summary,
                    "content_snippet": content_snippet,
                })
            except Exception:
                continue

    return sessions


def parse_activity_state(window_title: str, content_tail: str = "") -> tuple[str, str]:
    """Parse Claude Code window title and terminal content to extract activity state.

    Args:
        window_title: The iTerm window title
        content_tail: The last ~5000 characters of terminal content

    Returns:
        Tuple of (activity_state, task_summary)

    Activity states:
    - "processing": Claude is actively working (spinner showing)
    - "input_needed": Claude is blocked waiting for user response (question/permission)
    - "idle": Session is idle, ready for new task
    - "unknown": Can't determine state
    """
    if not window_title:
        return ("unknown", "Unknown")

    # Braille spinner characters indicate processing (Claude's turn - working)
    # Full Unicode braille pattern range
    spinner_chars = set("⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿⡀⡄⡆⡇")
    # Also common loading spinners
    spinner_chars |= set("◐◑◒◓◴◵◶◷⣾⣽⣻⢿⡿⣟⣯⣷⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")

    # Star/asterisk/prompt indicators = session not processing
    idle_chars = set("✳✱✲✴✵✶✷✸*›❯>$▶")

    # Permission/warning characters (used for title cleanup)
    permission_chars = set("?❓⚠️🔒⏸")

    # Patterns in terminal content that indicate Claude is waiting for user input
    # These appear when Claude asks a question or needs permission
    input_needed_patterns = [
        # Claude Code built-in UI patterns
        "Esc to cancel",
        "Tab to add additional instructions",
        "Do you want to proceed?",
        "Yes, and don't ask again",
        "Yes, and always allow",
        "Allow once",
        "Allow for this session",
        "❯ 1.",  # Numbered choice prompt
        "❯ Yes",
        "❯ No",
        # AskUserQuestion tool patterns
        "Enter to select",
        "to navigate",
        "Type something",
        # Yes/no prompt variations
        "[y/n]",
        "[Y/n]",
        "[y/N]",
        "(y/n)",
        "(Y/n)",
        "(y/N)",
        "[yes/no]",
        "(yes/no)",
        "yes or no",
        "y or n?",
        # Proceed/continue prompts
        "proceed?",
        "continue?",
        "should I proceed",
        "should I continue",
        "shall I proceed",
        "shall I continue",
        "want me to proceed",
        "want me to continue",
        "ready to proceed",
        # Confirmation prompts
        "confirm?",
        "is this correct",
        "is that correct",
        "does this look",
        "sound good?",
        "look good?",
        "looks good?",
        "make sense?",
        "what do you think",
        # Choice/selection prompts
        "which option",
        "which approach",
        "what would you prefer",
        "would you prefer",
        "please choose",
        "please select",
        "your choice",
        # Permission prompts
        "may I",
        "can I proceed",
        "shall I",
        "would you like me to",
        "do you want me to",
        # Waiting for input
        "waiting for your",
        "let me know",
        "please respond",
        "your input",
        "your feedback",
        "awaiting your",
        # Checkpoint patterns (like the example)
        "CHECKPOINT:",
        "checkpoint:",
    ]

    # Get the first character to determine base state
    first_char = window_title[0] if window_title else ""

    # Check content for input_needed patterns
    content_lower = content_tail.lower()
    is_input_needed = any(pattern.lower() in content_lower for pattern in input_needed_patterns)

    if first_char in spinner_chars:
        activity_state = "processing"
    elif first_char in idle_chars:
        # Check terminal content to distinguish input_needed vs idle
        activity_state = "input_needed" if is_input_needed else "idle"
    elif is_input_needed:
        # Even if first char is unrecognized, if content shows input prompts, mark as input_needed
        activity_state = "input_needed"
    else:
        activity_state = "unknown"

    # Extract task summary (remove status prefix and clean up)
    # Remove the UUID from the title if present
    uuid_pattern = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        re.IGNORECASE,
    )
    cleaned = uuid_pattern.sub("", window_title).strip()

    # Remove the status prefix character
    if cleaned and cleaned[0] in spinner_chars | idle_chars | permission_chars:
        cleaned = cleaned[1:].strip()

    # Clean up common prefixes/suffixes
    cleaned = cleaned.strip("- |:")

    return (activity_state, cleaned if cleaned else window_title)


def extract_task_summary(window_title: str) -> str:
    """Extract meaningful task summary from iTerm window title.

    Args:
        window_title: The iTerm window title

    Returns:
        Cleaned task summary string
    """
    _, summary = parse_activity_state(window_title, "")
    return summary


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as human-readable string.

    Args:
        seconds: Number of elapsed seconds

    Returns:
        Formatted string like "5s", "12m", or "2h 30m"
    """
    if seconds < 0:
        return "just now"
    elif seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}m"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
