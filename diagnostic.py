#!/usr/bin/env python3
"""Claude Headspace Diagnostic Framework

DEPRECATED: This script uses the legacy tmux backend. For the new WezTerm-based
architecture, use `python -m src.app` with the dashboard at http://localhost:5050.

This script tests the fundamental assumptions of session monitoring.
Run it to see exactly what's happening at each layer.

Usage:
    python diagnostic.py              # Run all diagnostics
    python diagnostic.py --live       # Continuous monitoring mode
    python diagnostic.py --session X  # Test specific tmux session
"""

import subprocess
import time
import warnings
from datetime import datetime

warnings.warn(
    "diagnostic.py uses the legacy tmux backend. Consider using the new WezTerm-based "
    "architecture with run.py or python -m src.app instead.",
    DeprecationWarning,
    stacklevel=2,
)

# =============================================================================
# LAYER 1: Can we even talk to tmux?
# =============================================================================


def test_tmux_available() -> dict:
    """Test if tmux is installed and accessible."""
    result = {"test": "tmux_available", "passed": False, "details": {}}

    try:
        proc = subprocess.run(["tmux", "-V"], capture_output=True, text=True, timeout=5)
        result["details"]["version"] = proc.stdout.strip()
        result["details"]["returncode"] = proc.returncode
        result["passed"] = proc.returncode == 0
    except FileNotFoundError:
        result["details"]["error"] = "tmux not found in PATH"
    except Exception as e:
        result["details"]["error"] = str(e)

    return result


def test_tmux_sessions() -> dict:
    """Test listing tmux sessions."""
    result = {"test": "tmux_sessions", "passed": False, "details": {}}

    try:
        proc = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if proc.returncode == 0:
            sessions = [s for s in proc.stdout.strip().split("\n") if s]
            claude_sessions = [s for s in sessions if s.startswith("claude-")]

            result["details"]["all_sessions"] = sessions
            result["details"]["claude_sessions"] = claude_sessions
            result["details"]["count"] = len(claude_sessions)
            result["passed"] = True
        else:
            result["details"]["error"] = proc.stderr.strip() or "No sessions"
            result["details"]["returncode"] = proc.returncode
            # No sessions is not a failure of tmux itself
            result["passed"] = "no server" not in proc.stderr.lower()

    except Exception as e:
        result["details"]["error"] = str(e)

    return result


# =============================================================================
# LAYER 2: Can we capture pane content?
# =============================================================================


def test_capture_pane(session_name: str) -> dict:
    """Test capturing content from a specific tmux pane."""
    result = {"test": "capture_pane", "session": session_name, "passed": False, "details": {}}

    try:
        # Capture last 200 lines
        proc = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-200"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if proc.returncode == 0:
            content = proc.stdout
            result["details"]["content_length"] = len(content)
            result["details"]["line_count"] = content.count("\n")
            result["details"]["last_500_chars"] = content[-500:] if content else "(empty)"
            result["passed"] = True
        else:
            result["details"]["error"] = proc.stderr.strip()
            result["details"]["returncode"] = proc.returncode

    except Exception as e:
        result["details"]["error"] = str(e)

    return result


# =============================================================================
# LAYER 3: What patterns do we find in the content?
# =============================================================================

# The ACTUAL patterns we look for
PROCESSING_INDICATORS = [
    "(esc to interrupt",  # Primary indicator - Claude is working (no closing paren - text continues with time)
]

COMPLETION_VERBS = [
    "Baked",
    "Brewed",
    "Clauded",
    "Thought",
    "Worked",
    "Wizarded",
    "Computed",
    "Crafted",
    "Processed",  # Sample of common ones
]

INPUT_NEEDED_PATTERNS = [
    "Yes, and don't ask again",
    "Allow once",
    "Allow for this session",
    "❯ Yes",
    "❯ No",
    "❯ 1.",
    "❯ 2.",
    "Enter to select",
]

IDLE_INDICATORS = [
    "❯",  # Prompt character at end of content
]


def analyze_content(content: str) -> dict:
    """Analyze terminal content for state indicators."""
    result = {
        "test": "content_analysis",
        "passed": True,  # Analysis itself always "passes"
        "details": {},
    }

    if not content:
        result["details"]["error"] = "No content to analyze"
        return result

    # Check what we actually find
    tail_800 = content[-800:] if len(content) > 800 else content
    tail_1500 = content[-1500:] if len(content) > 1500 else content
    last_lines = content.strip().split("\n")[-20:]

    # Processing indicators
    processing_found = []
    for indicator in PROCESSING_INDICATORS:
        if indicator in tail_800:
            processing_found.append(indicator)

    # Completion markers
    completion_found = []
    for verb in COMPLETION_VERBS:
        pattern = f"✻ {verb} for"
        if pattern in tail_800:
            completion_found.append(pattern)

    # Input needed patterns
    input_needed_found = []
    for pattern in INPUT_NEEDED_PATTERNS:
        if pattern.lower() in tail_1500.lower():
            input_needed_found.append(pattern)

    # Idle indicators (prompt at end)
    idle_found = []
    for line in reversed(last_lines):
        stripped = line.strip()
        if stripped == "❯" or stripped.startswith("❯ "):
            idle_found.append(f"Prompt found: '{stripped[:50]}'")
            break
        if stripped and not stripped.startswith("⏵"):  # Skip status bar
            break

    result["details"] = {
        "content_length": len(content),
        "tail_800_sample": tail_800[-200:],  # Show end of the check window
        "processing_found": processing_found,
        "completion_found": completion_found,
        "input_needed_found": input_needed_found,
        "idle_found": idle_found,
        "last_5_lines": last_lines[-5:],
    }

    # Determine what state we WOULD detect
    if processing_found and not completion_found:
        result["details"]["detected_state"] = "PROCESSING"
        result["details"]["reason"] = f"Found: {processing_found}"
    elif input_needed_found:
        result["details"]["detected_state"] = "INPUT_NEEDED"
        result["details"]["reason"] = f"Found: {input_needed_found}"
    elif completion_found or idle_found:
        result["details"]["detected_state"] = "IDLE"
        result["details"]["reason"] = f"Completion: {completion_found}, Idle: {idle_found}"
    else:
        result["details"]["detected_state"] = "UNKNOWN"
        result["details"]["reason"] = "No clear indicators found"

    return result


# =============================================================================
# LAYER 4: Compare detected state vs what the app reports
# =============================================================================


def test_app_detection(session_name: str) -> dict:
    """Test what the actual app code detects for this session."""
    result = {"test": "app_detection", "session": session_name, "passed": False, "details": {}}

    try:
        # Try new architecture first (src/), fall back to legacy (lib/)
        try:
            from src.backends.tmux import get_tmux_backend

            backend = get_tmux_backend()
            content = backend.get_content(session_name, lines=200) or ""
            # New architecture uses StateInterpreter, but for diagnostic we just report content
            result["details"]["app_detected_state"] = "see_content_analysis"
            result["details"]["app_summary"] = "(use dashboard for full state detection)"
            result["details"]["architecture"] = "src (new)"
        except ImportError:
            # Fall back to legacy lib/
            from lib.sessions import capture_pane, parse_activity_state

            content = capture_pane(session_name, lines=200) or ""
            state, summary = parse_activity_state("", content)  # Empty title for tmux
            result["details"]["app_detected_state"] = state
            result["details"]["app_summary"] = summary
            result["details"]["architecture"] = "lib (legacy)"

        result["details"]["content_length"] = len(content)
        result["passed"] = True

    except ImportError as e:
        result["details"]["error"] = f"Could not import app code: {e}"
    except Exception as e:
        result["details"]["error"] = str(e)

    return result


# =============================================================================
# DIAGNOSTIC RUNNER
# =============================================================================


def print_result(result: dict, verbose: bool = True):
    """Pretty print a test result."""
    status = "✓" if result["passed"] else "✗"
    color = "\033[92m" if result["passed"] else "\033[91m"
    reset = "\033[0m"

    print(f"\n{color}{status} {result['test']}{reset}")

    if "session" in result:
        print(f"  Session: {result['session']}")

    if verbose and result.get("details"):
        for key, value in result["details"].items():
            if isinstance(value, list):
                if value:
                    print(f"  {key}:")
                    for item in value[:10]:  # Limit list output
                        print(f"    - {item}")
                else:
                    print(f"  {key}: (none)")
            elif isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}...")
            else:
                print(f"  {key}: {value}")


def run_full_diagnostic(session_name: str = None, verbose: bool = True):
    """Run complete diagnostic suite."""
    print("=" * 60)
    print("CLAUDE HEADSPACE DIAGNOSTIC")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    # Layer 1: tmux basics
    print("\n--- LAYER 1: tmux Availability ---")
    print_result(test_tmux_available(), verbose)

    sessions_result = test_tmux_sessions()
    print_result(sessions_result, verbose)

    claude_sessions = sessions_result.get("details", {}).get("claude_sessions", [])

    if not claude_sessions:
        print("\n⚠️  No claude-* sessions found. Nothing to diagnose.")
        return

    # If no specific session requested, test all claude sessions
    sessions_to_test = [session_name] if session_name else claude_sessions

    for sess in sessions_to_test:
        if sess not in claude_sessions:
            print(f"\n⚠️  Session '{sess}' not found")
            continue

        print(f"\n--- LAYER 2: Pane Capture ({sess}) ---")
        capture_result = test_capture_pane(sess)
        print_result(capture_result, verbose)

        if capture_result["passed"]:
            print(f"\n--- LAYER 3: Content Analysis ({sess}) ---")
            content = capture_result["details"].get("last_500_chars", "")
            # Get full content for analysis
            proc = subprocess.run(
                ["tmux", "capture-pane", "-t", sess, "-p", "-S", "-200"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                analysis = analyze_content(proc.stdout)
                print_result(analysis, verbose)

                print(f"\n--- LAYER 4: App Detection ({sess}) ---")
                app_result = test_app_detection(sess)
                print_result(app_result, verbose)

                # Compare
                if app_result["passed"]:
                    detected = analysis["details"].get("detected_state", "UNKNOWN")
                    app_detected = app_result["details"].get("app_detected_state", "unknown")

                    print("\n--- COMPARISON ---")
                    print(f"  Raw analysis detected: {detected}")
                    print(f"  App code detected:     {app_detected}")

                    if detected.lower() != app_detected.lower():
                        print("  ⚠️  MISMATCH - This indicates a bug!")


def run_live_monitor(interval: int = 2):
    """Continuously monitor and report state."""
    print("Live monitoring mode. Press Ctrl+C to stop.\n")

    try:
        while True:
            # Get sessions
            proc = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if proc.returncode != 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No tmux sessions")
                time.sleep(interval)
                continue

            sessions = [s for s in proc.stdout.strip().split("\n") if s.startswith("claude-")]

            for sess in sessions:
                # Quick capture and analysis
                cap = subprocess.run(
                    ["tmux", "capture-pane", "-t", sess, "-p", "-S", "-200"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if cap.returncode == 0:
                    content = cap.stdout
                    tail = content[-800:]

                    # Quick state detection
                    if "(esc to interrupt)" in tail:
                        state = "PROCESSING"
                    elif any(p.lower() in content[-1500:].lower() for p in INPUT_NEEDED_PATTERNS):
                        state = "INPUT_NEEDED"
                    elif any(f"✻ {v} for" in tail for v in COMPLETION_VERBS):
                        state = "IDLE (completed)"
                    elif "❯" in content.strip().split("\n")[-1]:
                        state = "IDLE (prompt)"
                    else:
                        state = "UNKNOWN"

                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {sess}: {state}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Claude Headspace Diagnostic")
    parser.add_argument("--live", action="store_true", help="Continuous monitoring mode")
    parser.add_argument("--session", "-s", help="Test specific session")
    parser.add_argument("--quiet", "-q", action="store_true", help="Less verbose output")

    args = parser.parse_args()

    if args.live:
        run_live_monitor()
    else:
        run_full_diagnostic(session_name=args.session, verbose=not args.quiet)
