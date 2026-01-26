"""macOS notification handling for Claude Headspace.

This module handles:
- Sending native macOS notifications via terminal-notifier
- Tracking session state changes
- Priority-aware notification formatting
"""

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from lib.headspace import get_priorities_cache, load_headspace

# Directory for notification AppleScript files
_SCRIPT_DIR = Path(tempfile.gettempdir()) / "claude-monitor-scripts"


def _cleanup_old_scripts(max_age_seconds: int = 3600) -> None:
    """Remove script files older than max_age_seconds (default: 1 hour)."""
    if not _SCRIPT_DIR.exists():
        return
    cutoff = time.time() - max_age_seconds
    for f in _SCRIPT_DIR.glob("*.applescript"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except Exception:
            pass


# Track session states for notifications
_previous_states: dict[str, str] = {}
_notifications_enabled: bool = True


def is_notifications_enabled() -> bool:
    """Check if notifications are currently enabled.

    Returns:
        True if enabled, False if disabled
    """
    return _notifications_enabled


def set_notifications_enabled(enabled: bool) -> None:
    """Set the notifications enabled state.

    Args:
        enabled: Whether notifications should be enabled
    """
    global _notifications_enabled
    _notifications_enabled = enabled


def reset_notification_state() -> None:
    """Reset all notification tracking state.

    Clears the previous states dictionary so sessions will be
    re-discovered fresh on the next scan.
    """
    global _previous_states
    _previous_states.clear()


def _validate_pid(pid: int) -> bool:
    """Validate that a PID is safe to use in shell commands.

    Args:
        pid: Process ID to validate.

    Returns:
        True if PID is valid, False otherwise.
    """
    # PIDs must be positive integers, typically < 99999 on most systems
    return isinstance(pid, int) and 1 <= pid <= 99999


def send_macos_notification(
    title: str, message: str, sound: bool = True, pid: Optional[int] = None
) -> bool:
    """Send a native macOS notification via terminal-notifier with click-to-focus.

    Args:
        title: Notification title
        message: Notification message body
        sound: Whether to play a sound (default: True)
        pid: Optional PID to focus iTerm window on click

    Returns:
        True if notification sent successfully, False otherwise
    """
    try:
        # Validate PID before use in shell commands (security)
        if pid is not None and not _validate_pid(pid):
            print(f"Invalid PID: {pid}")
            return False
        cmd = [
            "terminal-notifier",
            "-title",
            title,
            "-message",
            message,
            "-sender",
            "com.googlecode.iterm2",  # Shows iTerm icon
        ]

        if sound:
            cmd.extend(["-sound", "default"])

        # If PID provided, clicking notification will focus that iTerm session
        if pid:
            # Create AppleScript to focus the window by PID's TTY
            focus_script = f"""
            tell application "iTerm"
                activate
                set targetTty to do shell script "ps -p {pid} -o tty= 2>/dev/null || echo ''"
                if targetTty is not "" then
                    set targetTty to "/dev/" & targetTty
                    repeat with w in windows
                        repeat with t in tabs of w
                            repeat with s in sessions of t
                                try
                                    if tty of s is targetTty then
                                        select w
                                        select t
                                        select s
                                        return
                                    end if
                                end try
                            end repeat
                        end repeat
                    end repeat
                end if
            end tell
            """
            # Cleanup old scripts and write new one to dedicated directory
            _cleanup_old_scripts()
            _SCRIPT_DIR.mkdir(exist_ok=True)
            script_path = _SCRIPT_DIR / f"focus-{pid}.applescript"
            script_path.write_text(focus_script)
            # Use shlex.quote to safely escape the path
            import shlex

            cmd.extend(["-execute", f"osascript {shlex.quote(str(script_path))}"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            print(f"Notification error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Notification exception: {e}")
        return False


def check_state_changes_and_notify(sessions: list[dict]) -> None:
    """Check for state changes and send macOS notifications with priority info.

    Args:
        sessions: List of session dicts with uuid, activity_state, project_name, etc.
    """
    global _previous_states

    if not _notifications_enabled:
        return

    # Get priority and headspace info for enhanced notifications
    priority_map = {}
    headspace_focus = None

    # Build priority lookup map from cache
    priorities_cache = get_priorities_cache()
    if priorities_cache.get("priorities"):
        for p in priorities_cache["priorities"]:
            priority_map[str(p.get("session_id"))] = p

    # Get headspace focus
    try:
        headspace = load_headspace()
        if headspace:
            headspace_focus = headspace.get("current_focus")
    except Exception:
        pass

    for session in sessions:
        uuid = session.get("uuid", "")
        current_state = session.get("activity_state", "unknown")
        previous_state = _previous_states.get(uuid)

        # Skip if no previous state (first scan)
        if previous_state is None:
            _previous_states[uuid] = current_state
            continue

        project = session.get("project_name", "Unknown")
        task = session.get("task_summary", "")[:50]
        pid = session.get("pid")

        # Get priority info for this session
        priority_info = priority_map.get(str(pid)) if pid else None
        is_high_priority = priority_info and priority_info.get("priority_score", 0) >= 70

        # Notify: became input_needed
        if current_state == "input_needed" and previous_state != "input_needed":
            # Build notification title and message
            if is_high_priority:
                title = "⚡ High Priority: Input Needed"
                message = f"{project}: {task}"
                # Add headspace relevance if available
                if headspace_focus:
                    message += f"\nRelated to: {headspace_focus[:40]}"
            else:
                title = "Input Needed"
                message = f"{project}: {task}"

            send_macos_notification(title, message, pid=pid)

        # Notify: processing finished (became idle)
        if current_state == "idle" and previous_state == "processing":
            if is_high_priority:
                title = "⚡ High Priority: Task Complete"
                message = f"{project}: {task}"
                if headspace_focus:
                    message += f"\nRelated to: {headspace_focus[:40]}"
            else:
                title = "Task Complete"
                message = f"{project}: {task}"

            send_macos_notification(title, message, pid=pid)

        _previous_states[uuid] = current_state

    # Clean up old sessions
    current_uuids = {s.get("uuid") for s in sessions}
    for uuid in list(_previous_states.keys()):
        if uuid not in current_uuids:
            del _previous_states[uuid]
