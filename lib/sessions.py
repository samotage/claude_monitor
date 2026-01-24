"""Session scanning and activity state parsing for Claude Headspace.

This module handles:
- Scanning project directories for active Claude sessions (iTerm and tmux)
- Parsing activity state from terminal window titles and content
- Formatting session information
- Turn completion detection for state transition tracking
- Last activity tracking for session cards
"""

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Debug logger for activity state detection
logger = logging.getLogger(__name__)

# Track last activity per session (content hash -> timestamp)
# Key: session identifier (uuid or tmux_session_name)
# Value: {"content_hash": str, "last_activity_at": str (ISO format)}
_session_activity_cache: dict[str, dict] = {}

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

from lib.iterm import get_pid_tty, focus_iterm_window_by_pid
from lib.summarization import prepare_content_for_summary
from lib.tmux import (
    capture_pane,
    get_session_info,
    is_tmux_available,
    list_sessions as tmux_list_sessions,
    session_exists as tmux_session_exists,
    slugify_project_name,
)


def track_session_activity(session_id: str, content: str) -> str:
    """Track last activity for a session by detecting content changes.

    Updates the activity cache when content hash changes.

    Args:
        session_id: Unique session identifier (uuid or tmux_session_name)
        content: Current terminal content

    Returns:
        ISO format timestamp of last activity
    """
    global _session_activity_cache

    # Compute hash of content (use last 2000 chars for efficiency)
    content_sample = content[-2000:] if content else ""
    content_hash = hashlib.md5(content_sample.encode()).hexdigest()

    now = datetime.now(timezone.utc).isoformat()

    if session_id not in _session_activity_cache:
        # First time seeing this session
        _session_activity_cache[session_id] = {
            "content_hash": content_hash,
            "last_activity_at": now,
        }
    elif _session_activity_cache[session_id]["content_hash"] != content_hash:
        # Content changed - update timestamp
        _session_activity_cache[session_id]["content_hash"] = content_hash
        _session_activity_cache[session_id]["last_activity_at"] = now

    return _session_activity_cache[session_id]["last_activity_at"]


def format_time_ago(iso_timestamp: str) -> str:
    """Format an ISO timestamp as human-readable time ago.

    Args:
        iso_timestamp: ISO 8601 format timestamp

    Returns:
        Human-readable string like "2m ago", "1h ago", "just now"
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        seconds = delta.total_seconds()

        if seconds < 10:
            return "just now"
        elif seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        else:
            days = int(seconds / 86400)
            return f"{days}d ago"
    except Exception:
        return "unknown"


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


def parse_session_name(session_name: str) -> tuple[Optional[str], Optional[str]]:
    """Parse a tmux session name into project slug and uuid8.

    Session names follow the pattern: claude-{project-slug}-{uuid8}
    Example: claude-claude-monitor-87c165e4

    Args:
        session_name: The tmux session name

    Returns:
        Tuple of (project_slug, uuid8), or (None, None) if parsing fails
    """
    if not session_name or not session_name.startswith("claude-"):
        return None, None

    # Remove "claude-" prefix
    remainder = session_name[7:]  # len("claude-") = 7

    # The uuid8 is the last 8 characters after the last hyphen
    # But we need to be careful: project slugs can contain hyphens
    # Pattern: claude-{project-slug}-{uuid8} where uuid8 is exactly 8 hex chars
    parts = remainder.rsplit("-", 1)
    if len(parts) != 2:
        return None, None

    project_slug = parts[0]
    uuid8 = parts[1]

    # Validate uuid8 is 8 hex characters
    if len(uuid8) != 8 or not all(c in "0123456789abcdef" for c in uuid8.lower()):
        # Maybe the entire remainder is the project slug with no uuid
        return remainder, None

    return project_slug, uuid8


def match_project(slug: str, projects: list[dict]) -> Optional[dict]:
    """Match a project slug to a config project.

    Tries to match by:
    1. Slugified project name
    2. Slugified directory name

    Args:
        slug: The project slug from the session name
        projects: List of project dicts from config

    Returns:
        Matched project dict, or None if no match
    """
    if not slug:
        return None

    for project in projects:
        # Match by slugified project name
        if slugify_project_name(project.get("name", "")) == slug:
            return project
        # Match by slugified directory name
        dir_name = Path(project.get("path", "")).name
        if slugify_project_name(dir_name) == slug:
            return project

    return None


def scan_tmux_session_direct(
    tmux_info: dict,
    project: Optional[dict],
    project_slug: str,
    uuid8: Optional[str],
) -> Optional[dict]:
    """Scan a tmux session directly (without state file) and return session info.

    This is the new tmux-first approach where we get session info directly
    from tmux, not from state files.

    Args:
        tmux_info: Session info dict from get_session_info()
        project: Matched project config from config.yaml (may be None)
        project_slug: The project slug extracted from session name
        uuid8: The short UUID extracted from session name (may be None)

    Returns:
        Session dict if session is active, None otherwise
    """
    session_name = tmux_info.get("name")
    if not session_name:
        return None

    # Capture terminal content from tmux
    content_tail = capture_pane(session_name, lines=200) or ""

    # For tmux sessions, we don't have a window title like iTerm
    window_title = ""

    # Use tmux created time for elapsed calculation
    created_timestamp = tmux_info.get("created", "")
    try:
        # tmux returns Unix timestamp
        start_time = datetime.fromtimestamp(int(created_timestamp), tz=timezone.utc)
        elapsed = datetime.now(timezone.utc) - start_time
        elapsed_str = format_elapsed(elapsed.total_seconds())
        started_at = start_time.isoformat()
    except Exception:
        elapsed_str = "unknown"
        started_at = ""

    # Extract activity state from content
    activity_state, task_summary = parse_activity_state(window_title, content_tail)

    # Prepare terminal content for AI summarization
    content_snippet = prepare_content_for_summary(content_tail)

    # Extract last message for tooltip display
    last_message = extract_last_message(content_tail)

    # Determine project info
    if project:
        project_name = project.get("name", project_slug)
        project_dir = project.get("path", "")
    else:
        # Unknown project - use slug as name
        project_name = project_slug or "Unknown"
        project_dir = tmux_info.get("pane_path", "")

    # Track last activity (content change detection)
    session_id = session_name  # Use tmux session name as identifier
    last_activity_at = track_session_activity(session_id, content_tail)
    last_activity_ago = format_time_ago(last_activity_at)

    return {
        "uuid": uuid8 or "unknown",
        "uuid_short": uuid8 or "unknown",
        "project_name": project_name,
        "project_dir": project_dir,
        "started_at": started_at,
        "elapsed": elapsed_str,
        "last_activity_at": last_activity_at,
        "last_activity_ago": last_activity_ago,
        "pid": tmux_info.get("pane_pid"),
        "tty": tmux_info.get("pane_tty"),
        "status": "active",
        "activity_state": activity_state,
        "window_title": window_title,
        "task_summary": task_summary if task_summary else f"tmux: {session_name}",
        "content_snippet": content_snippet,
        "last_message": last_message,
        # tmux-specific fields
        "session_type": "tmux",
        "tmux_session": session_name,
        "tmux_attached": tmux_info.get("attached", False),
    }


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

    # Track last activity (content change detection)
    session_id = tmux_session_name  # Use tmux session name as identifier
    last_activity_at = track_session_activity(session_id, content_tail)
    last_activity_ago = format_time_ago(last_activity_at)

    return {
        "uuid": session_uuid,
        "uuid_short": session_uuid[-8:] if session_uuid else "unknown",
        "project_name": project["name"],
        "project_dir": state.get("project_dir", project["path"]),
        "started_at": started_at,
        "elapsed": elapsed_str,
        "last_activity_at": last_activity_at,
        "last_activity_ago": last_activity_ago,
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

    # Track last activity (content change detection)
    session_id = session_uuid  # Use session UUID as identifier for iTerm
    last_activity_at = track_session_activity(session_id, content_tail)
    last_activity_ago = format_time_ago(last_activity_at)

    return {
        "uuid": session_uuid,
        "uuid_short": session_uuid[-8:] if session_uuid else "unknown",
        "project_name": project["name"],  # Use config name, not state file
        "project_dir": state.get("project_dir", project["path"]),
        "started_at": started_at,
        "elapsed": elapsed_str,
        "last_activity_at": last_activity_at,
        "last_activity_ago": last_activity_ago,
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


def cleanup_stale_state_files(config: dict, active_session_names: set[str]) -> None:
    """Clean up state files that reference non-existent tmux sessions.

    Also cleans up legacy iTerm-only state files (no tmux_session field)
    since iTerm-only mode is deprecated.

    Args:
        config: Configuration dict with 'projects' list
        active_session_names: Set of currently active tmux session names
    """
    for project in config.get("projects", []):
        project_path = Path(project.get("path", ""))
        if not project_path.exists():
            continue

        # Find all .claude-monitor-*.json files
        for state_file in project_path.glob(".claude-monitor-*.json"):
            try:
                state = json.loads(state_file.read_text())
                tmux_session_name = state.get("tmux_session")
                session_type = state.get("session_type", "iterm")

                should_delete = False

                # Delete iTerm-only state files (deprecated)
                if session_type == "iterm" or not tmux_session_name:
                    should_delete = True
                    logger.info(f"Cleaning up legacy iTerm state file: {state_file.name}")
                # Delete tmux state files that reference non-existent sessions
                elif tmux_session_name not in active_session_names:
                    should_delete = True
                    logger.info(f"Cleaning up stale tmux state file: {state_file.name}")

                if should_delete:
                    state_file.unlink()

            except Exception as e:
                logger.warning(f"Error processing state file {state_file}: {e}")


def scan_sessions(config: dict) -> list[dict]:
    """Scan for active Claude Code sessions using tmux as the source of truth.

    This is the tmux-first approach: we discover sessions by querying tmux
    directly, not by scanning for state files. State files are only used
    for iTerm window focus, not for session discovery.

    Stale state files (referencing dead tmux sessions) are automatically cleaned up.

    Args:
        config: Configuration dict with 'projects' list

    Returns:
        List of session dicts with status info
    """
    sessions = []
    projects = config.get("projects", [])

    # Get all tmux sessions (source of truth)
    if not is_tmux_available():
        logger.warning("tmux not available - no sessions will be discovered")
        return sessions

    all_tmux_sessions = tmux_list_sessions()
    active_session_names = {s.get("name", "") for s in all_tmux_sessions}

    # Clean up stale state files
    cleanup_stale_state_files(config, active_session_names)

    # Filter to claude-* sessions only
    claude_sessions = [s for s in all_tmux_sessions if s.get("name", "").startswith("claude-")]

    for tmux_sess in claude_sessions:
        session_name = tmux_sess.get("name", "")

        # Parse session name to get project slug and uuid8
        project_slug, uuid8 = parse_session_name(session_name)

        # Match to config project
        matched_project = match_project(project_slug, projects) if project_slug else None

        # Get detailed session info from tmux
        tmux_info = get_session_info(session_name)
        if not tmux_info:
            continue

        # Build session info directly from tmux
        session = scan_tmux_session_direct(tmux_info, matched_project, project_slug or "", uuid8)
        if session:
            sessions.append(session)

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

    # ACTIVE processing indicators in recent content
    # These indicate Claude is CURRENTLY working
    # Note: Claude Code UI shows the ❯ prompt BELOW the processing output,
    # so we can't use line position to determine state.
    #
    # IMPORTANT distinctions:
    # - "· thinking)" = ACTIVE (present tense)
    # - "· thought for" = COMPLETED (past tense)
    # - "⎿  Running…" = completed command showing output (NOT active)
    # - "⏺ ... Running…" without ⎿ prefix = ACTIVE command

    # Check for ACTIVE processing - must be currently happening
    # "thinking)" without "thought for" means ongoing
    has_active_thinking = "thinking)" in recent_content_raw and "thought for" not in recent_content_raw

    # Check for active command execution
    # "Running…" is active ONLY if it's not prefixed by ⎿ (which indicates completed output)
    has_active_running = False
    for line in recent_content_raw.split("\n"):
        # Active running: line contains Running… but doesn't start with output prefix ⎿
        if "Running…" in line and not line.strip().startswith("⎿"):
            has_active_running = True
            break

    # Waiting indicator (rare but possible)
    has_active_waiting = "Waiting…" in recent_content_raw and "thought for" not in recent_content_raw

    is_actively_processing = has_active_thinking or has_active_running or has_active_waiting

    # COMPLETION indicators - "✻ Baked for", "✻ Brewed for" etc. mean Claude finished
    # Use the complete TURN_COMPLETE_VERBS list
    is_completed = is_turn_complete(recent_content_raw)

    # Check last few lines for idle state
    # We're idle if the last meaningful content shows completion (✻ Verb for Xm Xs)
    # and there's no active processing indicator
    last_lines = content_tail.strip().split("\n") if content_tail else []

    # Find if there's an idle prompt (❯) that represents waiting for NEW input
    # This is only valid if there's NO active processing indicator
    has_idle_prompt = False
    if not is_actively_processing:
        # Check if last few lines show the prompt with no processing after
        for line in reversed(last_lines[-10:]):
            stripped = line.strip()
            # Skip empty lines and status bar lines
            if not stripped or stripped.startswith("samotage@") or stripped.startswith("⏵"):
                continue
            # If we hit a prompt line first (before any processing), we're idle
            if stripped.startswith("❯") or stripped == "❯":
                has_idle_prompt = True
                break
            # If we hit processing output, not idle
            if any(p in stripped for p in ["⏺", "⎿", "✢", "✻"]):
                break

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
