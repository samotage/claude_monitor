#!/usr/bin/env python3
"""
Claude Code Monitor - Kanban-style dashboard for tracking Claude Code sessions.

Usage:
    python monitor.py
    # Then open http://localhost:5050 in your browser
"""

import json
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
import markdown
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    """Load configuration from config.yaml."""
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text())
    return {"projects": [], "scan_interval": 2, "iterm_focus_delay": 0.1}


def save_config(config: dict) -> bool:
    """Save configuration to config.yaml."""
    try:
        CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
        return True
    except Exception:
        return False


def get_readme_content() -> str:
    """Get README.md content."""
    readme_path = Path(__file__).parent / "README.md"
    if readme_path.exists():
        return readme_path.read_text()
    return "# README\n\nNo README.md found."


def get_iterm_windows() -> dict[str, dict]:
    """
    Get all iTerm window info mapped by TTY.
    Returns dict: {tty: {"title": str, "content_tail": str}}
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
                        -- Get last 400 chars to check for input prompts
                        if length of sText > 400 then
                            set sText to text -400 thru -1 of sText
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


def get_pid_tty(pid: int) -> Optional[str]:
    """Get the TTY for a given PID."""
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


def scan_sessions(config: dict) -> list[dict]:
    """
    Scan all registered project directories for active sessions.
    Returns list of session dicts with status info.
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
                })
            except Exception:
                continue

    return sessions


def parse_activity_state(window_title: str, content_tail: str = "") -> tuple[str, str]:
    """
    Parse Claude Code window title and terminal content to extract activity state.

    Returns: (activity_state, task_summary)

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
    ]

    # Get the first character to determine base state
    first_char = window_title[0] if window_title else ""

    if first_char in spinner_chars:
        activity_state = "processing"
    elif first_char in idle_chars:
        # Check terminal content to distinguish input_needed vs idle
        content_lower = content_tail.lower()
        is_input_needed = any(pattern.lower() in content_lower for pattern in input_needed_patterns)
        activity_state = "input_needed" if is_input_needed else "idle"
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
    """Extract meaningful task summary from iTerm window title."""
    _, summary = parse_activity_state(window_title, "")
    return summary


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as human-readable string."""
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


def focus_iterm_window_by_pid(pid: int) -> bool:
    """Bring iTerm window containing the given PID to foreground."""
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


# HTML Template with embedded CSS and JavaScript
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Monitor</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%23111114'/%3E%3Crect x='5' y='10' width='9' height='14' rx='2' fill='%2356d4dd'/%3E%3Crect x='18' y='6' width='9' height='18' rx='2' fill='%2373e0a0'/%3E%3C/svg%3E">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            /* Terminal-inspired color palette */
            --bg-void: #08080a;
            --bg-deep: #0c0c0e;
            --bg-surface: #111114;
            --bg-elevated: #18181c;
            --bg-hover: #1e1e24;

            /* Syntax highlighting colors */
            --cyan: #56d4dd;
            --cyan-dim: #56d4dd80;
            --cyan-glow: #56d4dd40;
            --green: #73e0a0;
            --green-dim: #73e0a080;
            --amber: #e0b073;
            --amber-dim: #e0b07380;
            --magenta: #d073e0;
            --magenta-dim: #d073e080;
            --red: #e07373;
            --red-dim: #e0737380;
            --blue: #7399e0;
            --blue-dim: #7399e080;

            /* Text colors */
            --text-primary: #e8e8ed;
            --text-secondary: #8b8b96;
            --text-muted: #4a4a54;
            --text-ghost: #2a2a32;

            /* Borders */
            --border: #252530;
            --border-bright: #363644;

            /* Fonts */
            --font-mono: 'JetBrains Mono', 'IBM Plex Mono', 'SF Mono', 'Consolas', monospace;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        html {
            font-size: 17px;
        }

        body {
            font-family: var(--font-mono);
            background: var(--bg-void);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
            position: relative;
            overflow-x: hidden;
        }

        /* Scanline overlay effect */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: repeating-linear-gradient(
                0deg,
                transparent,
                transparent 2px,
                rgba(0, 0, 0, 0.03) 2px,
                rgba(0, 0, 0, 0.03) 4px
            );
            pointer-events: none;
            z-index: 9999;
        }

        /* Subtle noise texture */
        body::after {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
            opacity: 0.02;
            pointer-events: none;
            z-index: 9998;
        }

        /* Tab Navigation - styled like terminal tabs */
        .tab-nav {
            display: flex;
            background: var(--bg-deep);
            border-bottom: 1px solid var(--border);
            padding: 0;
            position: relative;
        }

        .tab-nav::before {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--cyan-dim), transparent);
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 16px 28px;
            font-family: var(--font-mono);
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            border-right: 1px solid var(--border);
            transition: all 0.15s ease;
            position: relative;
            letter-spacing: 0.02em;
        }

        .tab-btn::before {
            content: '>';
            margin-right: 8px;
            opacity: 0;
            color: var(--cyan);
            transition: opacity 0.15s ease;
        }

        .tab-btn:hover {
            background: var(--bg-surface);
            color: var(--text-secondary);
        }

        .tab-btn:hover::before {
            opacity: 0.5;
        }

        .tab-btn.active {
            background: var(--bg-surface);
            color: var(--cyan);
        }

        .tab-btn.active::before {
            opacity: 1;
        }

        .tab-btn.active::after {
            content: '';
            position: absolute;
            bottom: -1px;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--cyan);
            box-shadow: 0 0 12px var(--cyan-glow);
        }

        .tab-content {
            display: none;
            padding: 24px;
            min-height: calc(100vh - 52px);
            animation: fadeIn 0.2s ease;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Header - ASCII art style */
        header {
            text-align: center;
            margin-bottom: 32px;
            padding: 20px 0;
        }

        .ascii-title {
            font-size: 0.65rem;
            color: var(--cyan);
            white-space: pre;
            line-height: 1.1;
            text-shadow: 0 0 20px var(--cyan-glow);
            animation: glowPulse 4s ease-in-out infinite;
            letter-spacing: -0.02em;
        }

        @keyframes glowPulse {
            0%, 100% { text-shadow: 0 0 20px var(--cyan-glow); }
            50% { text-shadow: 0 0 30px var(--cyan-dim), 0 0 60px var(--cyan-glow); }
        }

        .subtitle {
            color: var(--text-muted);
            font-size: 0.8rem;
            margin-top: 16px;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }

        .subtitle::before {
            content: '// ';
            color: var(--text-ghost);
        }

        /* Stats bar */
        .stats-bar {
            display: flex;
            justify-content: center;
            gap: 32px;
            margin-top: 20px;
            padding: 12px 24px;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 4px;
            display: inline-flex;
        }

        .stat-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .stat-label {
            color: var(--text-muted);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .stat-value {
            font-weight: 600;
            font-size: 1rem;
        }

        .stat-value.active { color: var(--green); }
        .stat-value.input-needed {
            color: #ffb464;
            font-weight: 600;
        }
        .stat-value.idle { color: #64b4ff; }
        .stat-value.completed { color: var(--text-muted); }
        .stat-value.total { color: var(--cyan); }

        /* Kanban styles - terminal windows */
        .kanban {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            padding-bottom: 20px;
        }

        .kanban::-webkit-scrollbar {
            height: 8px;
        }

        .kanban::-webkit-scrollbar-track {
            background: var(--bg-deep);
        }

        .kanban::-webkit-scrollbar-thumb {
            background: var(--border-bright);
            border-radius: 4px;
        }

        .column {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            flex: 1;
            min-width: 300px;
            overflow: hidden;
        }

        /* Terminal-style window header */
        .column-header {
            padding: 10px 14px;
            background: var(--bg-elevated);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .column-title {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .window-dots {
            display: flex;
            gap: 6px;
        }

        .window-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--text-ghost);
        }

        .window-dot.red { background: var(--red-dim); }
        .window-dot.yellow { background: var(--amber-dim); }
        .window-dot.green { background: var(--green-dim); }

        .column-name {
            font-weight: 600;
            color: var(--text-primary);
            font-size: 0.9rem;
        }

        .column-count {
            background: var(--bg-void);
            color: var(--green);
            padding: 2px 10px;
            border-radius: 3px;
            font-size: 0.75rem;
            font-weight: 500;
            border: 1px solid var(--border);
        }

        .column-count.zero {
            color: var(--text-muted);
        }

        .column-body {
            padding: 12px;
            min-height: 120px;
            background: linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-deep) 100%);
        }

        /* Cards - styled like log entries */
        .card {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 0;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.15s ease;
            overflow: hidden;
            position: relative;
        }

        .card::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            background: var(--cyan);
            opacity: 0;
            transition: opacity 0.15s ease;
        }

        .card.active-session::before {
            background: var(--green);
            opacity: 1;
        }

        .card.completed-session::before {
            background: var(--text-muted);
            opacity: 0.5;
        }

        .card:hover {
            border-color: var(--cyan);
            transform: translateX(4px);
            box-shadow:
                0 0 0 1px var(--cyan-dim),
                0 4px 20px rgba(0, 0, 0, 0.4),
                -4px 0 20px var(--cyan-glow);
        }

        .card:hover::before {
            opacity: 1;
            background: var(--cyan);
        }

        .card:active {
            transform: translateX(2px);
        }

        .card-line-numbers {
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 32px;
            background: var(--bg-void);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            padding: 10px 0;
            font-size: 0.65rem;
            color: var(--text-ghost);
            text-align: right;
            padding-right: 8px;
            line-height: 1.8;
        }

        .card-content {
            margin-left: 32px;
            padding: 10px 12px;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .uuid {
            font-size: 0.75rem;
            color: var(--magenta);
            font-weight: 500;
        }

        .uuid::before {
            content: '#';
            color: var(--text-muted);
        }

        .status {
            font-size: 0.7rem;
            padding: 2px 8px;
            border-radius: 2px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .status.active {
            background: var(--green-dim);
            color: var(--green);
            border: 1px solid var(--green-dim);
        }

        .status.active::before {
            content: '';
            display: inline-block;
            width: 6px;
            height: 6px;
            background: var(--green);
            border-radius: 50%;
            margin-right: 6px;
            animation: blink 1s ease-in-out infinite;
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        .status.completed {
            background: transparent;
            color: var(--text-muted);
            border: 1px solid var(--border);
        }

        .status.completed::before {
            content: '';
            display: inline-block;
            width: 6px;
            height: 6px;
            background: var(--text-muted);
            margin-right: 6px;
        }

        /* Activity state indicator */
        .activity-state {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 4px;
            margin-bottom: 10px;
            font-size: 0.8rem;
            font-weight: 500;
        }

        .activity-state.processing {
            background: rgba(0, 212, 170, 0.15);
            border: 1px solid rgba(0, 212, 170, 0.3);
            color: var(--green);
        }

        .activity-state.processing .activity-icon {
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        /* INPUT NEEDED - Claude is blocked waiting for response */
        .activity-state.input_needed {
            background: rgba(255, 180, 100, 0.2);
            border: 1px solid rgba(255, 180, 100, 0.5);
            color: #ffb464;
            font-weight: 600;
        }

        /* Card highlight when input is needed */
        .card.input-needed-card {
            border-color: #ffb464 !important;
        }

        .card.input-needed-card::before {
            background: #ffb464 !important;
            opacity: 1 !important;
        }

        /* IDLE - Session ready for new task */
        .activity-state.idle {
            background: rgba(100, 180, 255, 0.12);
            border: 1px solid rgba(100, 180, 255, 0.25);
            color: #64b4ff;
        }

        .activity-state.permission_needed {
            background: rgba(255, 87, 34, 0.15);
            border: 1px solid rgba(255, 87, 34, 0.3);
            color: #ff5722;
            animation: pulse 1.5s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }

        .activity-state.completed, .activity-state.unknown {
            background: rgba(128, 128, 128, 0.1);
            border: 1px solid rgba(128, 128, 128, 0.2);
            color: var(--text-muted);
        }

        .activity-icon {
            font-size: 1rem;
        }

        .activity-label {
            flex: 1;
        }

        .task-summary {
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 10px;
            line-height: 1.5;
            word-break: break-word;
        }

        /* Syntax highlighting for task summary */
        .task-keyword { color: var(--cyan); }
        .task-string { color: var(--green); }
        .task-number { color: var(--amber); }

        .card-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.7rem;
            color: var(--text-muted);
            padding-top: 8px;
            border-top: 1px solid var(--border);
        }

        .elapsed {
            color: var(--amber);
            font-weight: 500;
        }

        .elapsed::before {
            content: 'uptime:';
            color: var(--text-muted);
            margin-right: 6px;
            font-weight: 400;
        }

        .pid-info {
            color: var(--text-ghost);
        }

        .pid-info::before {
            content: 'pid:';
            margin-right: 4px;
        }

        .no-sessions {
            text-align: center;
            color: var(--text-muted);
            padding: 60px 20px;
            font-style: italic;
        }

        .no-sessions::before {
            content: '$ ';
            color: var(--cyan);
        }

        .empty-column {
            color: var(--text-ghost);
            text-align: center;
            padding: 30px 20px;
            font-size: 0.8rem;
        }

        .empty-column::before {
            content: '// ';
        }

        /* Refresh indicator - terminal style */
        .refresh-indicator {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--bg-elevated);
            padding: 8px 14px;
            border-radius: 4px;
            font-size: 0.75rem;
            color: var(--text-muted);
            border: 1px solid var(--border);
            font-family: var(--font-mono);
        }

        .refresh-indicator::before {
            content: '~ ';
            color: var(--text-ghost);
        }

        .refresh-indicator.active {
            color: var(--cyan);
            border-color: var(--cyan-dim);
        }

        .refresh-indicator.active::before {
            color: var(--cyan);
        }

        /* Health/README styles - code documentation style */
        .readme-container {
            max-width: 900px;
            margin: 0 auto;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            overflow: hidden;
        }

        .readme-header {
            background: var(--bg-elevated);
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .readme-header .window-dots {
            display: flex;
            gap: 6px;
        }

        .readme-filename {
            color: var(--text-secondary);
            font-size: 0.85rem;
        }

        .readme-content {
            padding: 24px 32px;
            line-height: 1.8;
        }

        .readme-content h1 {
            color: var(--cyan);
            font-size: 1.6rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 12px;
            margin-bottom: 24px;
            font-weight: 600;
        }

        .readme-content h1::before {
            content: '# ';
            color: var(--text-muted);
        }

        .readme-content h2 {
            color: var(--green);
            margin-top: 32px;
            margin-bottom: 16px;
            font-size: 1.2rem;
            font-weight: 600;
        }

        .readme-content h2::before {
            content: '## ';
            color: var(--text-muted);
        }

        .readme-content h3 {
            color: var(--amber);
            margin-top: 24px;
            margin-bottom: 12px;
            font-size: 1rem;
            font-weight: 600;
        }

        .readme-content h3::before {
            content: '### ';
            color: var(--text-muted);
        }

        .readme-content p {
            margin-bottom: 16px;
            color: var(--text-secondary);
        }

        .readme-content ul, .readme-content ol {
            margin-bottom: 16px;
            padding-left: 24px;
            color: var(--text-secondary);
        }

        .readme-content li {
            margin-bottom: 8px;
        }

        .readme-content li::marker {
            color: var(--cyan);
        }

        .readme-content code {
            background: var(--bg-void);
            padding: 2px 8px;
            border-radius: 3px;
            font-family: var(--font-mono);
            color: var(--magenta);
            font-size: 0.9em;
            border: 1px solid var(--border);
        }

        .readme-content pre {
            background: var(--bg-void);
            padding: 16px 20px;
            border-radius: 4px;
            overflow-x: auto;
            margin-bottom: 16px;
            border: 1px solid var(--border);
            position: relative;
        }

        .readme-content pre::before {
            content: 'bash';
            position: absolute;
            top: 8px;
            right: 12px;
            font-size: 0.65rem;
            color: var(--text-ghost);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .readme-content pre code {
            padding: 0;
            background: none;
            border: none;
            color: var(--text-primary);
        }

        .readme-content table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 16px;
            font-size: 0.9rem;
        }

        .readme-content th, .readme-content td {
            border: 1px solid var(--border);
            padding: 10px 14px;
            text-align: left;
        }

        .readme-content th {
            background: var(--bg-elevated);
            color: var(--cyan);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }

        .readme-content td {
            color: var(--text-secondary);
        }

        .readme-content a {
            color: var(--cyan);
            text-decoration: none;
            border-bottom: 1px dashed var(--cyan-dim);
            transition: border-color 0.15s ease;
        }

        .readme-content a:hover {
            border-bottom-style: solid;
        }

        .readme-content img {
            display: none;
        }

        /* Settings styles - config editor style */
        .settings-container {
            max-width: 800px;
            margin: 0 auto;
        }

        .settings-section {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            margin-bottom: 20px;
            overflow: hidden;
        }

        .settings-section-header {
            background: var(--bg-elevated);
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .settings-section h2 {
            color: var(--text-primary);
            font-size: 0.9rem;
            font-weight: 600;
        }

        .settings-section h2::before {
            content: '> ';
            color: var(--cyan);
        }

        .settings-section-body {
            padding: 20px;
        }

        .settings-description {
            color: var(--text-muted);
            font-size: 0.8rem;
            margin-bottom: 20px;
        }

        .settings-description::before {
            content: '// ';
            color: var(--text-ghost);
        }

        .project-list {
            margin-bottom: 20px;
        }

        .project-item {
            display: flex;
            gap: 10px;
            align-items: center;
            margin-bottom: 10px;
            padding: 12px 14px;
            background: var(--bg-elevated);
            border-radius: 4px;
            border: 1px solid var(--border);
        }

        .project-item input {
            flex: 1;
            background: var(--bg-void);
            border: 1px solid var(--border);
            border-radius: 3px;
            padding: 10px 12px;
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-size: 0.85rem;
            transition: border-color 0.15s ease;
        }

        .project-item input:focus {
            outline: none;
            border-color: var(--cyan);
            box-shadow: 0 0 0 3px var(--cyan-glow);
        }

        .project-item input::placeholder {
            color: var(--text-ghost);
        }

        .project-name {
            width: 100px;
            flex-shrink: 0;
        }

        .project-path {
            flex: 3;
            min-width: 0;  /* Allow text to shrink/scroll */
        }

        .btn {
            background: var(--cyan);
            color: var(--bg-void);
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-family: var(--font-mono);
            font-weight: 600;
            font-size: 0.85rem;
            transition: all 0.15s ease;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }

        .btn:hover {
            background: var(--text-primary);
            box-shadow: 0 0 20px var(--cyan-glow);
        }

        .btn-secondary {
            background: transparent;
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: var(--bg-elevated);
            color: var(--text-primary);
            border-color: var(--text-muted);
            box-shadow: none;
        }

        .btn-danger {
            background: transparent;
            color: var(--red);
            border: 1px solid var(--red-dim);
            padding: 8px 12px;
        }

        .btn-danger:hover {
            background: var(--red);
            color: var(--bg-void);
            box-shadow: 0 0 20px var(--red-dim);
        }

        .settings-actions {
            display: flex;
            gap: 12px;
            margin-top: 24px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
        }

        .settings-status {
            margin-top: 16px;
            padding: 12px 16px;
            border-radius: 4px;
            display: none;
            font-size: 0.85rem;
        }

        .settings-status::before {
            content: '> ';
        }

        .settings-status.success {
            display: block;
            background: var(--green-dim);
            color: var(--green);
            border: 1px solid var(--green-dim);
        }

        .settings-status.error {
            display: block;
            background: var(--red-dim);
            color: var(--red);
            border: 1px solid var(--red-dim);
        }

        .setting-row {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 16px;
            padding: 12px 14px;
            background: var(--bg-elevated);
            border-radius: 4px;
            border: 1px solid var(--border);
        }

        .setting-row label {
            width: 140px;
            color: var(--cyan);
            font-size: 0.85rem;
            font-weight: 500;
        }

        .setting-row input {
            background: var(--bg-void);
            border: 1px solid var(--border);
            border-radius: 3px;
            padding: 10px 12px;
            color: var(--text-primary);
            width: 100px;
            font-family: var(--font-mono);
            font-size: 0.85rem;
        }

        .setting-row input:focus {
            outline: none;
            border-color: var(--cyan);
            box-shadow: 0 0 0 3px var(--cyan-glow);
        }

        .setting-hint {
            color: var(--text-muted);
            font-size: 0.75rem;
        }

        /* Custom scrollbar for webkit */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-deep);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border-bright);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }
    </style>
</head>
<body>
    <!-- Tab Navigation -->
    <nav class="tab-nav">
        <button class="tab-btn active" data-tab="kanban">sessions</button>
        <button class="tab-btn" data-tab="health">readme.md</button>
        <button class="tab-btn" data-tab="settings">config.yaml</button>
    </nav>

    <!-- Kanban Tab -->
    <div id="kanban-tab" class="tab-content active">
        <header>
            <pre class="ascii-title"> ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗
██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝
██║     ██║     ███████║██║   ██║██║  ██║█████╗
██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝
╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗
 ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝
            M O N I T O R</pre>
            <p class="subtitle">tracking claude code sessions across projects</p>
            <div class="stats-bar" id="stats-bar">
                <div class="stat-item">
                    <span class="stat-label">input needed</span>
                    <span class="stat-value input-needed" id="input-needed-count">0</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">working</span>
                    <span class="stat-value active" id="working-count">0</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">idle</span>
                    <span class="stat-value idle" id="idle-count">0</span>
                </div>
            </div>
        </header>
        <div id="kanban" class="kanban">
            <div class="no-sessions">initializing...</div>
        </div>
    </div>

    <!-- Health Tab -->
    <div id="health-tab" class="tab-content">
        <div class="readme-container">
            <div class="readme-header">
                <div class="window-dots">
                    <span class="window-dot red"></span>
                    <span class="window-dot yellow"></span>
                    <span class="window-dot green"></span>
                </div>
                <span class="readme-filename">README.md</span>
            </div>
            <div id="readme-content" class="readme-content">
                <p>loading documentation...</p>
            </div>
        </div>
    </div>

    <!-- Settings Tab -->
    <div id="settings-tab" class="tab-content">
        <div class="settings-container">
            <div class="settings-section">
                <div class="settings-section-header">
                    <h2>monitored_projects</h2>
                </div>
                <div class="settings-section-body">
                    <p class="settings-description">Configure the projects that Claude Monitor will track.</p>

                    <div id="project-list" class="project-list">
                        <!-- Projects will be rendered here -->
                    </div>

                    <button class="btn btn-secondary" onclick="addProject()">+ add_project</button>

                    <div class="settings-actions">
                        <button class="btn" onclick="saveSettings()">save_config</button>
                    </div>

                    <div id="settings-status" class="settings-status"></div>
                </div>
            </div>

            <div class="settings-section">
                <div class="settings-section-header">
                    <h2>options</h2>
                </div>
                <div class="settings-section-body">
                    <div class="setting-row">
                        <label>scan_interval</label>
                        <input type="number" id="scan-interval" min="1" max="60" value="2">
                        <span class="setting-hint">seconds</span>
                    </div>
                    <div class="setting-row">
                        <label>focus_delay</label>
                        <input type="number" id="focus-delay" min="0" max="1" step="0.1" value="0.1">
                        <span class="setting-hint">seconds</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="refresh-indicator" class="refresh-indicator">
        last_sync: --
    </div>

    <script>
        const REFRESH_INTERVAL = {{ scan_interval * 1000 }};
        let currentProjects = [];

        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                // Update buttons
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Update content
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                document.getElementById(btn.dataset.tab + '-tab').classList.add('active');

                // Load tab-specific content
                if (btn.dataset.tab === 'health') {
                    loadReadme();
                } else if (btn.dataset.tab === 'settings') {
                    loadSettings();
                }
            });
        });

        // Kanban functions
        async function fetchSessions() {
            try {
                const response = await fetch('/api/sessions');
                const data = await response.json();
                renderKanban(data.sessions, data.projects);
                updateStats(data.sessions);
                updateRefreshIndicator();
            } catch (error) {
                console.error('Failed to fetch sessions:', error);
            }
        }

        function updateStats(sessions) {
            const inputNeeded = sessions.filter(s => s.activity_state === 'input_needed').length;
            const working = sessions.filter(s => s.activity_state === 'processing').length;
            const idle = sessions.filter(s => s.activity_state === 'idle').length;
            document.getElementById('input-needed-count').textContent = inputNeeded;
            document.getElementById('working-count').textContent = working;
            document.getElementById('idle-count').textContent = idle;

            // Update document title with input needed count for tab visibility
            if (inputNeeded > 0) {
                document.title = `(${inputNeeded}) INPUT NEEDED - Claude Monitor`;
            } else {
                document.title = 'Claude Monitor';
            }
        }

        function renderKanban(sessions, projects) {
            const kanban = document.getElementById('kanban');

            const byProject = {};
            projects.forEach(p => {
                byProject[p.name] = [];
            });

            sessions.forEach(session => {
                const projectName = session.project_name;
                if (!byProject[projectName]) {
                    byProject[projectName] = [];
                }
                byProject[projectName].push(session);
            });

            let html = '';
            for (const [projectName, projectSessions] of Object.entries(byProject)) {
                const activeSessions = projectSessions.filter(s => s.status === 'active');
                const count = activeSessions.length;
                const countClass = count === 0 ? 'zero' : '';

                html += `
                    <div class="column">
                        <div class="column-header">
                            <div class="column-title">
                                <div class="window-dots">
                                    <span class="window-dot red"></span>
                                    <span class="window-dot yellow"></span>
                                    <span class="window-dot green"></span>
                                </div>
                                <span class="column-name">${escapeHtml(projectName)}</span>
                            </div>
                            <span class="column-count ${countClass}">${count} active</span>
                        </div>
                        <div class="column-body">
                `;

                if (projectSessions.length === 0) {
                    html += '<div class="empty-column">no active sessions</div>';
                } else {
                    projectSessions.forEach((session, idx) => {
                        const statusClass = session.status === 'active' ? 'active-session' : 'completed-session';
                        const inputNeededClass = session.activity_state === 'input_needed' ? 'input-needed-card' : '';
                        const lineNums = ['01', '02', '03', '04'].join('<br>');

                        const activityInfo = getActivityInfo(session.activity_state);

                        html += `
                            <div class="card ${statusClass} ${inputNeededClass}" onclick="focusWindow(${session.pid || 0})" title="Click to focus iTerm window">
                                <div class="card-line-numbers">${lineNums}</div>
                                <div class="card-content">
                                    <div class="card-header">
                                        <span class="uuid">${session.uuid_short}</span>
                                        <span class="status ${session.status}">${session.status}</span>
                                    </div>
                                    <div class="activity-state ${session.activity_state}">
                                        <span class="activity-icon">${activityInfo.icon}</span>
                                        <span class="activity-label">${activityInfo.label}</span>
                                    </div>
                                    <div class="task-summary">${escapeHtml(session.task_summary)}</div>
                                    <div class="card-footer">
                                        <span class="elapsed">${session.elapsed}</span>
                                        ${session.pid ? `<span class="pid-info">${session.pid}</span>` : ''}
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                }

                html += '</div></div>';
            }

            kanban.innerHTML = html || '<div class="no-sessions">no projects configured</div>';
        }

        function getActivityInfo(state) {
            const states = {
                'processing': {
                    icon: '⚙',
                    label: "Claude's turn - working..."
                },
                'input_needed': {
                    icon: '🔔',
                    label: 'INPUT NEEDED!'
                },
                'idle': {
                    icon: '💤',
                    label: 'Idle - ready for task'
                },
                'completed': {
                    icon: '✓',
                    label: 'Session ended'
                },
                'unknown': {
                    icon: '?',
                    label: 'Unknown state'
                }
            };
            return states[state] || states['unknown'];
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function focusWindow(pid) {
            if (!pid) {
                console.warn('No PID available for this session');
                return;
            }
            try {
                const response = await fetch(`/api/focus/${pid}`, { method: 'POST' });
                const data = await response.json();
                if (!data.success) {
                    console.warn('Could not focus window');
                }
            } catch (error) {
                console.error('Failed to focus window:', error);
            }
        }

        function updateRefreshIndicator() {
            const indicator = document.getElementById('refresh-indicator');
            const now = new Date().toLocaleTimeString('en-US', { hour12: false });
            indicator.textContent = `last_sync: ${now}`;
            indicator.classList.add('active');
            setTimeout(() => indicator.classList.remove('active'), 500);
        }

        // Health/README functions
        async function loadReadme() {
            try {
                const response = await fetch('/api/readme');
                const data = await response.json();
                document.getElementById('readme-content').innerHTML = data.html;
            } catch (error) {
                console.error('Failed to load README:', error);
                document.getElementById('readme-content').innerHTML = '<p>// failed to load documentation</p>';
            }
        }

        // Settings functions
        async function loadSettings() {
            try {
                const response = await fetch('/api/config');
                const config = await response.json();
                currentProjects = config.projects || [];
                renderProjectList();
                document.getElementById('scan-interval').value = config.scan_interval || 2;
                document.getElementById('focus-delay').value = config.iterm_focus_delay || 0.1;
            } catch (error) {
                console.error('Failed to load settings:', error);
            }
        }

        function renderProjectList() {
            const container = document.getElementById('project-list');
            if (currentProjects.length === 0) {
                container.innerHTML = '<p class="settings-description" style="margin-bottom: 0;">no projects configured. add one below.</p>';
                return;
            }

            container.innerHTML = currentProjects.map((project, index) => `
                <div class="project-item">
                    <input type="text" class="project-name" placeholder="project_name"
                           value="${escapeHtml(project.name)}" onchange="updateProject(${index}, 'name', this.value)">
                    <input type="text" class="project-path" placeholder="/path/to/project"
                           value="${escapeHtml(project.path)}" onchange="updateProject(${index}, 'path', this.value)">
                    <button class="btn btn-danger" onclick="removeProject(${index})">rm</button>
                </div>
            `).join('');
        }

        function addProject() {
            currentProjects.push({ name: '', path: '' });
            renderProjectList();
        }

        function updateProject(index, field, value) {
            currentProjects[index][field] = value;
        }

        function removeProject(index) {
            currentProjects.splice(index, 1);
            renderProjectList();
        }

        async function saveSettings() {
            const statusEl = document.getElementById('settings-status');

            // Filter out empty projects
            const validProjects = currentProjects.filter(p => p.name && p.path);

            const config = {
                projects: validProjects,
                scan_interval: parseInt(document.getElementById('scan-interval').value) || 2,
                iterm_focus_delay: parseFloat(document.getElementById('focus-delay').value) || 0.1
            };

            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                const result = await response.json();

                if (result.success) {
                    statusEl.className = 'settings-status success';
                    statusEl.textContent = 'config written successfully';
                    currentProjects = validProjects;
                    renderProjectList();
                } else {
                    statusEl.className = 'settings-status error';
                    statusEl.textContent = 'error: ' + (result.error || 'unknown error');
                }
            } catch (error) {
                statusEl.className = 'settings-status error';
                statusEl.textContent = 'error: ' + error.message;
            }

            setTimeout(() => {
                statusEl.className = 'settings-status';
            }, 3000);
        }

        // Initial load
        fetchSessions();
        setInterval(fetchSessions, REFRESH_INTERVAL);
    </script>
</body>
</html>
'''


@app.route("/")
def index():
    """Serve the main kanban dashboard."""
    config = load_config()
    return render_template_string(
        HTML_TEMPLATE,
        scan_interval=config.get("scan_interval", 2),
    )


@app.route("/api/sessions")
def api_sessions():
    """API endpoint to get all sessions."""
    config = load_config()
    sessions = scan_sessions(config)
    return jsonify({
        "sessions": sessions,
        "projects": config.get("projects", []),
    })


@app.route("/api/focus/<int:pid>", methods=["POST"])
def api_focus(pid: int):
    """API endpoint to focus an iTerm window by PID."""
    success = focus_iterm_window_by_pid(pid)
    return jsonify({"success": success})


@app.route("/api/readme")
def api_readme():
    """API endpoint to get README as HTML."""
    content = get_readme_content()
    html = markdown.markdown(
        content,
        extensions=["tables", "fenced_code", "codehilite"]
    )
    return jsonify({"html": html})


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


def main():
    """Run the monitor web server."""
    config = load_config()
    print(f"Claude Monitor starting...")
    print(f"Monitoring {len(config.get('projects', []))} projects")
    print(f"Refresh interval: {config.get('scan_interval', 2)}s")
    print(f"\nOpen http://localhost:5050 in your browser")
    print("Press Ctrl+C to stop\n")

    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
