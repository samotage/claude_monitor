"""iTerm integration module for Claude Headspace.

This module handles AppleScript-based iTerm window operations:
- Focusing specific iTerm windows by tmux session name

Note: Session discovery is now handled via tmux, not iTerm AppleScript.
This module only provides focus functionality.
"""

import subprocess
from typing import Optional


def get_tmux_client_tty(tmux_session: str) -> Optional[str]:
    """Get the TTY of the tmux client attached to a session.

    When a tmux session is attached in an iTerm window, the tmux client
    runs on the iTerm session's TTY. This function finds that TTY.

    Args:
        tmux_session: The tmux session name

    Returns:
        TTY string (e.g., "/dev/ttys003") or None if not found
    """
    try:
        result = subprocess.run(
            ["tmux", "list-clients", "-t", tmux_session, "-F", "#{client_tty}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Return the first client's TTY
            return result.stdout.strip().split('\n')[0]
        return None
    except Exception:
        return None


def focus_iterm_window_by_tmux_session(tmux_session: str) -> bool:
    """Bring iTerm window running the given tmux session to foreground.

    Uses tmux client info to find which iTerm window has the session attached,
    then focuses that window via AppleScript.

    Args:
        tmux_session: The tmux session name (e.g., "claude-my-project-87c165e4")

    Returns:
        True if window was found and focused, False otherwise
    """
    # Get the iTerm TTY from tmux client info
    tty = get_tmux_client_tty(tmux_session)
    if not tty:
        return False

    # Focus the iTerm window with this TTY
    script = f'''
    tell application "iTerm"
        activate
        repeat with w in windows
            repeat with t in tabs of w
                repeat with s in sessions of t
                    try
                        if tty of s is "{tty}" then
                            select w
                            select t
                            select s
                            return true
                        end if
                    end try
                end repeat
            end repeat
        end repeat
        return false
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and "true" in result.stdout.lower()
    except Exception:
        return False


def get_pid_tty(pid: int) -> Optional[str]:
    """Get the TTY for a given PID.

    Args:
        pid: Process ID to look up

    Returns:
        TTY string (e.g., "ttys012") or None if not found
    """
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "tty="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            tty = result.stdout.strip()
            if tty and tty != "??":
                return tty
        return None
    except Exception:
        return None


def focus_iterm_window_by_pid(pid: int) -> bool:
    """Bring iTerm window containing the given PID to foreground.

    Note: This function uses TTY matching which doesn't work well with
    tmux sessions. For tmux sessions, use focus_iterm_window_by_tmux_session().

    Args:
        pid: Process ID of the session to focus

    Returns:
        True if window was found and focused, False otherwise
    """
    # First get the TTY for this PID
    tty = get_pid_tty(pid)
    if not tty:
        return False

    # Add /dev/ prefix if needed for AppleScript matching
    tty_path = f"/dev/{tty}" if not tty.startswith("/dev/") else tty

    script = f'''
    tell application "iTerm"
        activate
        repeat with w in windows
            repeat with t in tabs of w
                repeat with s in sessions of t
                    try
                        if tty of s is "{tty_path}" then
                            select w
                            select t
                            select s
                            return true
                        end if
                    end try
                end repeat
            end repeat
        end repeat
        return false
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and "true" in result.stdout.lower()
    except Exception:
        return False
