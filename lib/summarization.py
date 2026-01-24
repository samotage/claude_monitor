"""Session summarization for Claude Headspace.

This module handles:
- JSONL session log parsing
- Session activity extraction (files, commands, errors)
- Summary text generation
- Project state and recent sessions updates
- Terminal content preparation for AI summarization
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Optional

from config import load_config
from lib.projects import load_project_data, save_project_data


# =============================================================================
# Terminal Content Preparation for AI
# =============================================================================


def prepare_content_for_summary(content_tail: str, max_chars: int = 1500) -> str:
    """Prepare terminal content for AI summarization.

    Cleans and truncates terminal content to be suitable for inclusion
    in an AI prompt for generating activity summaries.

    Args:
        content_tail: Raw terminal content (up to 5000 chars from iTerm)
        max_chars: Maximum characters to return (default 1500 for token efficiency)

    Returns:
        Cleaned and truncated content suitable for AI prompt
    """
    if not content_tail:
        return ""

    text = content_tail

    # 1. Strip ANSI escape codes (colors, cursor movement, etc.)
    ansi_pattern = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[PX^_][^\x1b]*\x1b\\')
    text = ansi_pattern.sub('', text)

    # 2. Remove common box-drawing and UI chrome characters used by Claude Code TUI
    # Box drawing: ─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼ ═ ║ ╔ ╗ ╚ ╝ ╠ ╣ ╦ ╩ ╬
    # Block elements: █ ▀ ▄ ▌ ▐ ░ ▒ ▓
    ui_chrome_pattern = re.compile(r'[─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬█▀▄▌▐░▒▓◀▶▲▼●○◉◎■□▪▫]+')
    text = ui_chrome_pattern.sub(' ', text)

    # 3. Remove spinner/progress characters (braille patterns used by Claude Code)
    spinner_pattern = re.compile(r'[⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿⡀⡄⡆⡇◐◑◒◓◴◵◶◷⣾⣽⣻⢿⡿⣟⣯⣷]+')
    text = spinner_pattern.sub('', text)

    # 4. Collapse multiple whitespace/newlines into single space or newline
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
    text = re.sub(r'\n{3,}', '\n\n', text)  # 3+ newlines to 2
    text = re.sub(r' *\n *', '\n', text)  # Trim spaces around newlines

    # 5. Strip leading/trailing whitespace
    text = text.strip()

    # 6. Take the last max_chars characters (most recent activity)
    if len(text) > max_chars:
        text = text[-max_chars:]
        # Remove partial line at the start (find first newline)
        first_newline = text.find('\n')
        if first_newline > 0 and first_newline < 200:  # Only if reasonably close to start
            text = text[first_newline + 1:]

    return text.strip()

# Path to Claude Code's projects directory
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Session summarization defaults
DEFAULT_IDLE_TIMEOUT_MINUTES = 60
MAX_RECENT_SESSIONS = 5


# =============================================================================
# Claude Code Log File Access
# =============================================================================


def encode_project_path(project_path: str) -> str:
    """Encode a project path to Claude Code's directory format.

    Claude Code stores logs in ~/.claude/projects/<encoded-path>/
    where the path has forward slashes and underscores replaced with hyphens.

    Args:
        project_path: Absolute path to the project (e.g., /Users/sam/my_project)

    Returns:
        Encoded path string (e.g., -Users-sam-my-project)
    """
    # Ensure we're working with an absolute path
    path = Path(project_path).resolve()
    # Replace forward slashes and underscores with hyphens
    encoded = str(path).replace("/", "-").replace("_", "-")
    return encoded


def get_claude_logs_directory(project_path: str) -> Optional[Path]:
    """Get the Claude Code logs directory for a project.

    Tries multiple encoding strategies to find the logs directory,
    since Claude Code's actual encoding may vary.

    Args:
        project_path: Absolute path to the project

    Returns:
        Path to the logs directory, or None if it doesn't exist
    """
    path = Path(project_path).resolve()

    # Try multiple encoding strategies
    encodings = [
        encode_project_path(project_path),  # Current approach: replace / and _ with -
        str(path).replace("/", "-"),  # Without underscore replacement
    ]

    for encoded in encodings:
        logs_dir = CLAUDE_PROJECTS_DIR / encoded
        if logs_dir.exists() and logs_dir.is_dir():
            return logs_dir

    return None


def find_session_log_file(project_path: str, session_uuid: str) -> Optional[Path]:
    """Find the JSONL log file for a specific session.

    Args:
        project_path: Absolute path to the project
        session_uuid: UUID of the session to find

    Returns:
        Path to the JSONL file, or None if not found
    """
    logs_dir = get_claude_logs_directory(project_path)
    if not logs_dir:
        return None

    log_file = logs_dir / f"{session_uuid}.jsonl"
    if log_file.exists():
        return log_file
    return None


# =============================================================================
# JSONL Parsing
# =============================================================================


def parse_jsonl_line(line: str) -> Optional[dict]:
    """Parse a single line of JSONL data.

    Args:
        line: A single line from a JSONL file

    Returns:
        Parsed dict, or None if the line is malformed
    """
    line = line.strip()
    if not line:
        return None

    try:
        return json.loads(line)
    except json.JSONDecodeError:
        # Skip malformed lines gracefully
        return None


def parse_jsonl_stream(log_file: Path) -> Generator[dict, None, None]:
    """Stream and parse a JSONL log file line by line.

    This is memory-efficient for large files (100MB+).

    Args:
        log_file: Path to the JSONL file

    Yields:
        Parsed dict objects from each valid line
    """
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                parsed = parse_jsonl_line(line)
                if parsed:
                    yield parsed
    except Exception as e:
        print(f"Warning: Error reading JSONL file {log_file}: {e}")


# =============================================================================
# Session Activity Detection
# =============================================================================


def get_last_activity_time(log_file: Path) -> Optional[datetime]:
    """Get the timestamp of the last activity in a session log.

    Uses file modification time for efficiency.

    Args:
        log_file: Path to the JSONL file

    Returns:
        datetime of last modification, or None if unable to determine
    """
    try:
        mtime = log_file.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except Exception:
        return None


def get_idle_timeout_minutes() -> int:
    """Get the configured idle timeout in minutes.

    Returns:
        Idle timeout minutes from config, or default of 60
    """
    config = load_config()
    return config.get("idle_timeout_minutes", DEFAULT_IDLE_TIMEOUT_MINUTES)


def is_session_idle(log_file: Path) -> bool:
    """Check if a session has been idle longer than the configured timeout.

    Args:
        log_file: Path to the session's JSONL file

    Returns:
        True if the session is idle (no activity beyond timeout)
    """
    last_activity = get_last_activity_time(log_file)
    if not last_activity:
        return False

    timeout_minutes = get_idle_timeout_minutes()
    idle_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    return last_activity < idle_threshold


def is_session_process_alive(pid: int) -> bool:
    """Check if a session's process is still running.

    Args:
        pid: Process ID to check

    Returns:
        True if the process exists, False if terminated
    """
    try:
        os.kill(pid, 0)  # Signal 0 checks if process exists
        return True
    except OSError:
        return False


def detect_session_end(session: dict, project_path: str) -> bool:
    """Detect if a session has ended (idle timeout or process termination).

    Args:
        session: Session dict with uuid and pid
        project_path: Path to the project

    Returns:
        True if the session has ended
    """
    pid = session.get("pid")
    session_uuid = session.get("uuid")

    # Check process termination first (definitive end)
    if pid and not is_session_process_alive(pid):
        return True

    # Check idle timeout
    if session_uuid:
        log_file = find_session_log_file(project_path, session_uuid)
        if log_file and is_session_idle(log_file):
            return True

    return False


# =============================================================================
# Session Activity Extraction
# =============================================================================


def extract_files_modified(log_file: Path) -> list[str]:
    """Extract list of files modified during a session.

    Looks for Edit, Write, and file-related tool calls in the log.

    Args:
        log_file: Path to the session's JSONL file

    Returns:
        List of unique file paths that were modified
    """
    files = set()

    for entry in parse_jsonl_stream(log_file):
        # Look for tool use blocks with file-modifying tools
        if entry.get("type") == "assistant" and "message" in entry:
            message = entry.get("message", {})
            content = message.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})

                        if tool_name in ("Edit", "Write", "NotebookEdit"):
                            file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
                            if file_path:
                                files.add(file_path)

    return sorted(files)


def extract_commands_executed(log_file: Path) -> dict:
    """Extract commands executed during a session.

    Args:
        log_file: Path to the session's JSONL file

    Returns:
        Dict with 'count' and 'commands' (list of command strings, max 10)
    """
    commands = []

    for entry in parse_jsonl_stream(log_file):
        if entry.get("type") == "assistant" and "message" in entry:
            message = entry.get("message", {})
            content = message.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})

                        if tool_name == "Bash":
                            cmd = tool_input.get("command", "")
                            if cmd:
                                # Truncate long commands
                                cmd_display = cmd[:100] + "..." if len(cmd) > 100 else cmd
                                commands.append(cmd_display)

    return {
        "count": len(commands),
        "commands": commands[:10]  # Keep only first 10 for summary
    }


def extract_errors_encountered(log_file: Path) -> dict:
    """Extract errors and failures from a session.

    Args:
        log_file: Path to the session's JSONL file

    Returns:
        Dict with 'count' and 'errors' (list of error messages, max 5)
    """
    errors = []

    for entry in parse_jsonl_stream(log_file):
        # Look for tool results with errors
        if entry.get("type") == "user" and "message" in entry:
            message = entry.get("message", {})
            content = message.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        if block.get("is_error"):
                            error_content = block.get("content", "")
                            if isinstance(error_content, str) and error_content:
                                # Truncate long errors
                                error_display = error_content[:200] + "..." if len(error_content) > 200 else error_content
                                errors.append(error_display)

    return {
        "count": len(errors),
        "errors": errors[:5]  # Keep only first 5 for summary
    }


# =============================================================================
# Summary Generation
# =============================================================================


def generate_summary_text(
    files_modified: list[str],
    commands: dict,
    errors: dict
) -> str:
    """Generate a human-readable summary paragraph.

    Args:
        files_modified: List of modified file paths
        commands: Dict with count and commands list
        errors: Dict with count and errors list

    Returns:
        Human-readable summary string
    """
    parts = []

    # Files modified
    if files_modified:
        if len(files_modified) == 1:
            parts.append(f"Modified {files_modified[0]}")
        else:
            parts.append(f"Modified {len(files_modified)} files")
            # Add a few file names for context
            sample_files = [Path(f).name for f in files_modified[:3]]
            if len(files_modified) > 3:
                sample_files.append("...")
            parts[-1] += f" ({', '.join(sample_files)})"

    # Commands executed
    if commands["count"] > 0:
        parts.append(f"ran {commands['count']} command{'s' if commands['count'] > 1 else ''}")

    # Errors encountered
    if errors["count"] > 0:
        parts.append(f"{errors['count']} error{'s' if errors['count'] > 1 else ''} encountered")

    if not parts:
        return "Session completed with no recorded activity"

    summary = ", ".join(parts)
    # Capitalize first letter
    return summary[0].upper() + summary[1:]


def summarise_session(project_path: str, session_uuid: str) -> Optional[dict]:
    """Generate a complete session summary.

    Args:
        project_path: Absolute path to the project
        session_uuid: UUID of the session to summarise

    Returns:
        Dict with summary data, or None if session log not found
    """
    log_file = find_session_log_file(project_path, session_uuid)
    if not log_file:
        return None

    # Extract data from the session log
    files_modified = extract_files_modified(log_file)
    commands = extract_commands_executed(log_file)
    errors = extract_errors_encountered(log_file)

    # Get timestamps from log file
    last_activity = get_last_activity_time(log_file)

    # Read first entry to get start time
    start_time = None
    for entry in parse_jsonl_stream(log_file):
        if "timestamp" in entry:
            try:
                start_time = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            except Exception:
                pass
        break  # Only need first entry

    # Calculate duration
    duration_minutes = 0
    if start_time and last_activity:
        duration = last_activity - start_time
        duration_minutes = int(duration.total_seconds() / 60)

    # Generate summary text
    summary_text = generate_summary_text(files_modified, commands, errors)

    return {
        "session_id": session_uuid,
        "started_at": start_time.isoformat() if start_time else None,
        "ended_at": last_activity.isoformat() if last_activity else None,
        "duration_minutes": duration_minutes,
        "summary": summary_text,
        "files_modified": files_modified,
        "commands_run": commands["count"],
        "errors": errors["count"]
    }


# =============================================================================
# Project State Updates
# =============================================================================


def update_project_state(project_name: str, session_summary: dict) -> bool:
    """Update a project's state section with the latest session outcome.

    Args:
        project_name: Name of the project
        session_summary: Summary dict from summarise_session()

    Returns:
        True if update was successful
    """
    project_data = load_project_data(project_name)
    if project_data is None:
        return False

    # Update state section
    project_data["state"] = {
        "last_session_id": session_summary["session_id"],
        "last_session_ended": session_summary["ended_at"],
        "last_session_summary": session_summary["summary"],
        "status": "idle"  # Session has ended
    }

    return save_project_data(project_name, project_data)


def add_recent_session(project_name: str, session_summary: dict) -> tuple[bool, list[dict]]:
    """Add a session to the project's recent_sessions list.

    Maintains a FIFO list of max 5 sessions. Returns any sessions that were
    removed due to the FIFO limit for compression.

    Args:
        project_name: Name of the project
        session_summary: Summary dict from summarise_session()

    Returns:
        Tuple of (success: bool, removed_sessions: list[dict])
        - success: True if update was successful
        - removed_sessions: Sessions removed due to FIFO limit (for compression)
    """
    project_data = load_project_data(project_name)
    if project_data is None:
        return False, []

    # Initialize recent_sessions if not present
    if "recent_sessions" not in project_data or not isinstance(project_data["recent_sessions"], list):
        project_data["recent_sessions"] = []

    # Check if this session is already recorded
    existing_ids = [s.get("session_id") for s in project_data["recent_sessions"]]
    if session_summary["session_id"] in existing_ids:
        return True, []  # Already recorded, skip

    # Add new session to the front
    project_data["recent_sessions"].insert(0, session_summary)

    # Enforce FIFO limit and capture removed sessions
    removed_sessions = []
    if len(project_data["recent_sessions"]) > MAX_RECENT_SESSIONS:
        removed_sessions = project_data["recent_sessions"][MAX_RECENT_SESSIONS:]
        project_data["recent_sessions"] = project_data["recent_sessions"][:MAX_RECENT_SESSIONS]

    success = save_project_data(project_name, project_data)
    return success, removed_sessions if success else []


def process_session_end(
    project_name: str,
    project_path: str,
    session_uuid: str,
    compression_queue_callback=None
) -> Optional[dict]:
    """Process a session that has ended.

    Generates summary and updates project YAML. If sessions are removed from
    the FIFO window, queues them for compression using the provided callback.

    Args:
        project_name: Name of the project
        project_path: Absolute path to the project
        session_uuid: UUID of the ended session
        compression_queue_callback: Optional callable(project_name, session_summary)
                                   to queue removed sessions for compression

    Returns:
        Session summary dict, or None if processing failed
    """
    # Generate summary
    summary = summarise_session(project_path, session_uuid)
    if not summary:
        print(f"Warning: Could not summarise session {session_uuid} for {project_name}")
        return None

    # Update state
    update_project_state(project_name, summary)

    # Add to recent sessions (may trigger FIFO removal)
    success, removed_sessions = add_recent_session(project_name, summary)

    # Queue removed sessions for compression
    if compression_queue_callback:
        for removed in removed_sessions:
            compression_queue_callback(project_name, removed)
            print(f"Info: Queued session {removed.get('session_id', 'unknown')[:8]}... for compression")

    print(f"Info: Summarised session {session_uuid[:8]}... for {project_name}")
    return summary
