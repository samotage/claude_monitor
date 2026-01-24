#!/usr/bin/env python3
"""State Change Logger - Logs every state detection for debugging intermittent issues.

Run this alongside the dashboard to capture exactly what happens when detection fails.

Usage:
    python state_logger.py

Output goes to: data/logs/state_debug.log
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("data/logs/state_debug.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

PROCESSING_PATTERN = "(esc to interrupt"
INPUT_PATTERNS = [
    "yes, and don't ask again",
    "allow once",
    "allow for this session",
    "❯ yes",
    "❯ no",
    "❯ 1.",
    "❯ 2.",
    "enter to select",
]

# Track previous states
_previous_states = {}


def capture_pane(session_name: str) -> str:
    """Capture tmux pane content."""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-200"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout if result.returncode == 0 else ""
    except:
        return ""


def detect_state(content: str) -> tuple[str, str]:
    """Detect state from content. Returns (state, reason)."""
    if not content:
        return "unknown", "no content"

    tail_800 = content[-800:]
    tail_1500_lower = content[-1500:].lower()

    # Check processing first
    if PROCESSING_PATTERN in tail_800:
        return "processing", f"found '{PROCESSING_PATTERN}' in tail_800"

    # Check input_needed
    for pattern in INPUT_PATTERNS:
        if pattern.lower() in tail_1500_lower:
            return "input_needed", f"found '{pattern}'"

    # Check completion/idle
    completion_verbs = ["Baked", "Brewed", "Clauded", "Thought", "Worked"]
    for verb in completion_verbs:
        if f"✻ {verb} for" in tail_800:
            return "idle", f"found completion marker '✻ {verb} for'"

    # Check for prompt at end - need 25 lines because Claude Code UI has ~10 lines of chrome below prompt
    last_lines = content.strip().split('\n')[-25:]
    for line in reversed(last_lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("⏵"):
            continue
        if stripped == "❯" or stripped.startswith("❯ "):
            return "idle", f"found prompt: '{stripped[:30]}'"
        break

    return "unknown", "no clear indicators"


def log_entry(session: str, state: str, reason: str, content_sample: str):
    """Write a log entry."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "session": session,
        "state": state,
        "reason": reason,
        "content_tail_200": content_sample[-200:] if content_sample else "",
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    print(f"State Logger started. Writing to: {LOG_FILE}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # Get claude sessions
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode != 0:
                time.sleep(2)
                continue

            sessions = [s for s in result.stdout.strip().split('\n')
                       if s.startswith("claude-")]

            for sess in sessions:
                content = capture_pane(sess)
                state, reason = detect_state(content)

                prev_state = _previous_states.get(sess)

                # Always log, but highlight state changes
                if state != prev_state:
                    marker = ">>> STATE CHANGE <<<"
                    print(f"{datetime.now().strftime('%H:%M:%S')} {marker}")
                    print(f"  Session: {sess}")
                    print(f"  {prev_state or 'unknown'} -> {state}")
                    print(f"  Reason: {reason}")
                    print()

                    log_entry(sess, state, f"CHANGED from {prev_state}: {reason}", content)
                    _previous_states[sess] = state
                else:
                    # Log every 30 seconds even without change (for debugging)
                    log_entry(sess, state, reason, content)

            time.sleep(2)  # Check every 2 seconds

    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
