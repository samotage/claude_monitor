"""iTerm integration module for Claude Headspace.

This module handles all AppleScript-based iTerm window operations:
- Enumerating iTerm windows and sessions
- Mapping PIDs to TTYs
- Focusing specific iTerm windows
"""

import subprocess
from typing import Optional


def get_iterm_windows() -> dict[str, dict]:
    """Get all iTerm window info mapped by TTY.

    Returns:
        Dict mapping TTY (e.g., "ttys012") to window info:
        {tty: {"title": str, "content_tail": str}}
    """
    script = '''
    tell application "iTerm"
        set output to {}
        repeat with w in windows
            set wName to name of w
            repeat with t in tabs of w
                repeat with s in sessions of t
                    try
                        set sTty to tty of s
                        set sText to text of s
                        -- Get last 5000 chars to check for input prompts
                        -- Claude Code has UI chrome at the bottom (dividers, status bar, prompt)
                        -- so we need enough chars to capture the output ABOVE that chrome
                        if length of sText > 5000 then
                            set sText to text -5000 thru -1 of sText
                        end if
                        set end of output to sTty & "|||" & wName & "|||" & sText
                    end try
                end repeat
            end repeat
        end repeat
        return output
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {}

        # Parse the AppleScript output
        # Format: "/dev/ttys000|||Window Title|||content_tail, /dev/ttys001|||..."
        output = result.stdout.strip()
        windows = {}

        if output:
            # Split carefully - entries are separated by ", /dev/"
            # First split by ", /dev/" then add back "/dev/" prefix
            raw_entries = output.split(", /dev/")
            entries = [raw_entries[0]]  # First entry already has /dev/
            entries.extend(["/dev/" + e for e in raw_entries[1:]])

            for entry in entries:
                parts = entry.split("|||", 2)
                if len(parts) >= 2:
                    tty = parts[0].strip()
                    title = parts[1].strip()
                    content_tail = parts[2] if len(parts) > 2 else ""
                    # Store just the tty number (e.g., "ttys012")
                    if tty.startswith("/dev/"):
                        tty = tty[5:]
                    windows[tty] = {
                        "title": title,
                        "content_tail": content_tail,
                    }

        return windows
    except Exception:
        return {}


def is_claude_process(pid: int) -> bool:
    """Check if a PID is a Claude Code process.

    This prevents PID reuse issues where a dead session's PID
    gets recycled by the OS for an unrelated process.

    Args:
        pid: Process ID to check

    Returns:
        True if the process appears to be Claude Code
    """
    try:
        # Get the full command line for the process
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False

        command = result.stdout.strip().lower()
        # Claude Code runs as node with claude in the path, or as 'claude' directly
        return "claude" in command
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
