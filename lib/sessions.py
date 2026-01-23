"""Session scanning and activity state parsing for Claude Headspace.

This module handles:
- Scanning project directories for active Claude sessions (iTerm and tmux)
- Parsing activity state from terminal window titles and content
- Formatting session information
- Turn completion detection for state transition tracking
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Debug logger for activity state detection
logger = logging.getLogger(__name__)

# Complete list of Claude Code spinner verbs (past tense for turn completion)
# These appear as "✻ <Verb> for Xm Xs" when Claude finishes a turn
# Source: Claude Code CLI internal verb list
TURN_COMPLETE_VERBS = [
    "Accomplished", "Actioned", "Actualized", "Baked", "Booped", "Brewed",
    "Calculated", "Cerebrated", "Channelled", "Churned", "Clauded", "Coalesced",
    "Cogitated", "Combobulated", "Computed", "Concocted", "Conjured", "Considered",
    "Contemplated", "Cooked", "Crafted", "Created", "Crunched", "Deciphered",
    "Deliberated", "Determined", "Discombobulated", "Divined", "Done", "Effected",
    "Elucidated", "Enchanted", "Envisioned", "Finagled", "Flibbertigibbeted",
    "Forged", "Formed", "Frolicked", "Generated", "Germinated", "Hatched",
    "Herded", "Honked", "Hustled", "Ideated", "Imagined", "Incubated", "Inferred",
    "Jived", "Manifested", "Marinated", "Meandered", "Moseyed", "Mulled",
    "Mustered", "Mused", "Noodled", "Percolated", "Perused", "Philosophised",
    "Pondered", "Pontificated", "Processed", "Puttered", "Puzzled", "Reticulated",
    "Ruminated", "Sautéed", "Schemed", "Schlepped", "Shimmied", "Shucked", "Simmered",
    "Smooshed", "Spelunked", "Spun", "Stewed", "Sussed", "Synthesized", "Thought",
    "Tinkered", "Transmuted", "Unfurled", "Unravelled", "Vibed", "Wandered",
    "Whirred", "Wibbled", "Whisked", "Wizarded", "Worked", "Wrangled"
]


def is_turn_complete(content: str) -> bool:
    """Check if Claude's turn just completed based on completion marker.

    Claude Code displays "✻ <Verb> for Xm Xs" when a turn completes.

    Args:
        content: Terminal content to check

    Returns:
        True if a turn completion marker is found in recent content
    """
    if not content:
        return False
    # Check last 300 chars for completion pattern
    tail = content[-300:]
    return any(f"✻ {verb} for" in tail for verb in TURN_COMPLETE_VERBS)

from lib.iterm import get_iterm_windows, get_pid_tty, is_claude_process
from lib.summarization import prepare_content_for_summary
from lib.tmux import (
    capture_pane,
    get_session_info,
    is_tmux_available,
    session_exists as tmux_session_exists,
)


def extract_last_message(content_tail: str, max_chars: int = 500) -> str:
    """Extract the last Claude message/response from terminal content.

    Looks for the most recent substantial block of text that represents
    what Claude last said. This is useful for showing in tooltips.

    Args:
        content_tail: Raw terminal content (last ~5000 chars from iTerm)
        max_chars: Maximum characters to return

    Returns:
        The last message text, cleaned and truncated
    """
    if not content_tail:
        return ""

    # First clean the content using existing function
    cleaned = prepare_content_for_summary(content_tail, max_chars=2000)

    if not cleaned:
        return ""

    # Split into lines and work backwards to find last substantial content
    lines = cleaned.strip().split('\n')

    # Filter out empty lines and very short lines (likely prompts or UI)
    substantial_lines = []
    for line in reversed(lines):
        line = line.strip()
        # Skip empty lines, prompts, and very short lines
        if not line:
            continue
        # Skip lines that look like prompts (common prompt patterns)
        if line in ('>', '$', '❯', '%', '#') or len(line) < 5:
            continue
        # Skip lines that are just UI elements
        if line.startswith('---') or line.startswith('==='):
            continue
        substantial_lines.insert(0, line)
        # Stop after collecting enough lines (last meaningful paragraph)
        if len('\n'.join(substantial_lines)) > max_chars:
            break

    if not substantial_lines:
        return ""

    result = '\n'.join(substantial_lines)

    # Truncate if needed
    if len(result) > max_chars:
        result = result[:max_chars].rsplit(' ', 1)[0] + '...'

    return result.strip()


def scan_tmux_session(
    state: dict,
    project: dict,
    iterm_windows: dict,
) -> Optional[dict]:
    """Scan a tmux-based session and return session info.

    Args:
        state: State dict from the session state file
        project: Project config from config.yaml
        iterm_windows: Dict of iTerm windows by TTY (for fallback)

    Returns:
        Session dict if session is active, None otherwise
    """
    session_uuid = state.get("uuid", "").lower()
    tmux_session_name = state.get("tmux_session")

    if not tmux_session_name:
        return None

    # Check if tmux session still exists
    if not is_tmux_available() or not tmux_session_exists(tmux_session_name):
        return None

    # Get tmux session info
    tmux_info = get_session_info(tmux_session_name)
    if not tmux_info:
        return None

    # Capture terminal content from tmux
    content_tail = capture_pane(tmux_session_name, lines=200) or ""

    # For tmux sessions, we don't have a window title like iTerm
    # Try to extract activity state from content alone
    # Use empty string for title, rely on content-based detection
    window_title = ""  # tmux doesn't have window titles like iTerm

    # Parse started_at
    started_at = state.get("started_at", "")
    try:
        start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        elapsed = datetime.now(timezone.utc) - start_time
        elapsed_str = format_elapsed(elapsed.total_seconds())
    except Exception:
        elapsed_str = "unknown"

    # Extract activity state from content
    activity_state, task_summary = parse_activity_state(window_title, content_tail)

    # Prepare terminal content for AI summarization
    content_snippet = prepare_content_for_summary(content_tail)

    # Extract last message for tooltip display
    last_message = extract_last_message(content_tail)

    return {
        "uuid": session_uuid,
        "uuid_short": session_uuid[-8:] if session_uuid else "unknown",
        "project_name": project["name"],
        "project_dir": state.get("project_dir", project["path"]),
        "started_at": started_at,
        "elapsed": elapsed_str,
        "pid": tmux_info.get("pane_pid"),
        "tty": tmux_info.get("pane_tty"),
        "status": "active",
        "activity_state": activity_state,
        "window_title": window_title,
        "task_summary": task_summary if task_summary else f"tmux: {tmux_session_name}",
        "content_snippet": content_snippet,
        "last_message": last_message,
        # tmux-specific fields
        "session_type": "tmux",
        "tmux_session": tmux_session_name,
        "tmux_attached": tmux_info.get("attached", False),
    }


def scan_iterm_session(
    state: dict,
    project: dict,
    iterm_windows: dict,
) -> Optional[dict]:
    """Scan an iTerm-based session and return session info.

    Args:
        state: State dict from the session state file
        project: Project config from config.yaml
        iterm_windows: Dict of iTerm windows by TTY

    Returns:
        Session dict if session is active, None otherwise
    """
    session_uuid = state.get("uuid", "").lower()
    session_pid = state.get("pid")

    # Check if session has an iTerm window by matching PID to TTY
    window_info = None
    session_tty = None
    if session_pid:
        # First verify this is actually a Claude process (prevents PID reuse issues)
        if not is_claude_process(session_pid):
            # PID was reused by another process - this session is dead
            return None

        session_tty = get_pid_tty(session_pid)
        if session_tty:
            window_info = iterm_windows.get(session_tty)

    # Only show sessions that have an active iTerm window
    # Sessions without windows are not displayed (window closed = session gone)
    if not window_info:
        return None

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

    # Extract last message for tooltip display
    last_message = extract_last_message(content_tail)

    return {
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
        "last_message": last_message,
        # iTerm-specific fields
        "session_type": "iterm",
    }


def scan_sessions(config: dict) -> list[dict]:
    """Scan all registered project directories for active sessions.

    Supports both iTerm and tmux session types. Session type is determined
    by the 'session_type' field in the state file.

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
                session_type = state.get("session_type", "iterm")

                if session_type == "tmux":
                    session = scan_tmux_session(state, project, iterm_windows)
                else:
                    session = scan_iterm_session(state, project, iterm_windows)

                if session:
                    sessions.append(session)

            except Exception:
                continue

    return sessions


def parse_activity_state(window_title: str, content_tail: str = "") -> tuple[str, str]:
    """Parse Claude Code window title and terminal content to extract activity state.

    Args:
        window_title: The iTerm window title (may be empty for tmux sessions)
        content_tail: The last ~5000 characters of terminal content

    Returns:
        Tuple of (activity_state, task_summary)

    Activity states:
    - "processing": Claude is actively working (spinner showing)
    - "input_needed": Claude is blocked waiting for user response (question/permission)
    - "idle": Session is idle, ready for new task
    - "unknown": Can't determine state
    """
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

    # Check RECENT content for input_needed patterns (not entire history)
    # Old questions/prompts in the terminal buffer can cause false positives
    # Only check last ~1500 chars where current prompts would appear
    recent_content = content_tail[-1500:].lower() if content_tail else ""
    is_input_needed = any(pattern.lower() in recent_content for pattern in input_needed_patterns)

    # For content-based detection, only check RECENT content (last ~1500 chars)
    # to avoid false positives from old tool executions in history
    recent_content_raw = content_tail[-1500:] if content_tail else ""

    # ACTIVE processing indicators - must be in recent content with "esc to interrupt"
    # These indicate Claude is CURRENTLY working, not just that it worked earlier
    is_actively_processing = (
        "(esc to interrupt" in recent_content_raw and
        any(p in recent_content_raw for p in ["Running…", "Waiting…", "thinking"])
    )

    # COMPLETION indicators - "✻ Baked for", "✻ Brewed for" etc. mean Claude finished
    # Use the complete TURN_COMPLETE_VERBS list
    is_completed = is_turn_complete(recent_content_raw)

    # Check last few lines for idle prompt (❯)
    last_lines = content_tail.strip().split("\n")[-10:] if content_tail else []

    # Look for ❯ prompt in any of the last lines (not just the absolute last)
    # tmux may have status bars or empty lines after the prompt
    has_idle_prompt = any(
        line.strip().startswith("❯") or line.strip() == "❯"
        for line in last_lines
    )

    if first_char in spinner_chars:
        activity_state = "processing"
    elif first_char in idle_chars:
        # Check terminal content to distinguish input_needed vs idle
        activity_state = "input_needed" if is_input_needed else "idle"
    elif is_input_needed:
        # If content shows input prompts, mark as input_needed
        activity_state = "input_needed"
    elif not window_title and content_tail:
        # For tmux sessions without window title, use content-based detection
        # Priority: active processing > idle prompt
        # Active processing = "(esc to interrupt" present AND no idle prompt after it
        if is_actively_processing:
            activity_state = "processing"
        elif has_idle_prompt:
            activity_state = "idle"
        else:
            activity_state = "unknown"
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
