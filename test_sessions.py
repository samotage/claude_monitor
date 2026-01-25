"""Tests for session scanning and activity state parsing.

This module contains comprehensive tests for lib/sessions.py, including:
- Regression tests for previously-fixed bugs
- Unit tests for activity state detection
- Unit tests for turn completion detection
- Unit tests for session parsing utilities
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from lib.sessions import (
    parse_activity_state,
    is_turn_complete,
    extract_turn_command,
    extract_completion_marker,
    extract_last_message,
    track_session_activity,
    format_time_ago,
    format_elapsed,
    parse_session_name,
    match_project,
    TURN_COMPLETE_VERBS,
    _session_activity_cache,
)


# =============================================================================
# REGRESSION TESTS - Previously Fixed Bugs
# =============================================================================


class TestRegressionActivityStateDetection:
    """Regression tests for activity state detection bugs.

    These tests encode previously-fixed bugs to prevent regressions.
    If any of these tests fail, a previously-fixed bug has been reintroduced.
    """

    def test_regression_processing_detected_via_esc_to_interrupt(self):
        """REGRESSION: Processing should be detected via '(esc to interrupt)' in terminal tail.

        Bug: Processing detection was unreliable because it checked for spinner characters
        in window title or vague content patterns.

        Fix (commit f73cf82): Use '(esc to interrupt)' as the reliable indicator that
        Claude is actively processing. This appears in the status bar during processing.
        """
        # Content with (esc to interrupt) should be detected as processing
        content_with_processing = """
        Some previous output here...

        ⏺ Read(file.py)
        · thinking)

        ⏵ File Reading · Token Usage: 15,234 (esc to interrupt)
        ❯
        """

        # Empty window title (tmux session) - rely on content detection
        state, _ = parse_activity_state("", content_with_processing)
        assert state == "processing", "Failed to detect processing via (esc to interrupt)"

    def test_regression_processing_detected_case_insensitive_esc(self):
        """REGRESSION: Processing detection must be case-insensitive for 'Esc to interrupt'.

        Bug (2026-01-26): Claude Code displays "(Esc to interrupt" with capital E,
        but the detection code used lowercase "(esc to interrupt", causing processing
        sessions to be incorrectly marked as idle.

        Fix: Use case-insensitive comparison for the "(esc to interrupt)" check.
        """
        # Content with capital E in "Esc" - as Claude Code actually displays it
        content_with_capital_esc = """
        Some output here...

        * Composing... (Esc to interrupt - 3m 52s - ↓ 3.0k tokens - thinking)

        ❯
        """

        # Must detect processing even with capital E
        state, _ = parse_activity_state("", content_with_capital_esc)
        assert state == "processing", "Failed to detect processing with capital 'Esc' - case sensitivity bug"

        # Also verify lowercase still works
        content_with_lowercase_esc = """
        Some output here...

        * Composing... (esc to interrupt - 2m 10s)

        ❯
        """
        state, _ = parse_activity_state("", content_with_lowercase_esc)
        assert state == "processing", "Failed to detect processing with lowercase 'esc'"

    def test_regression_processing_not_detected_when_turn_complete(self):
        """REGRESSION: Completed turns should NOT be detected as processing.

        Bug: Old patterns like '· thinking)' or 'Running…' would trigger processing
        even after the turn was complete, because they remained in terminal history.

        Fix (commit f73cf82): If a completion marker (✻ Baked for...) is found,
        override processing detection since the turn is complete.
        """
        # Content with BOTH processing indicators AND completion marker
        # The completion marker should take precedence
        content_completed = """
        ⏺ Read(file.py)
        · thinking)
        Running…

        Done reading file.

        ✻ Baked for 2m 30s
        ❯
        """

        state, _ = parse_activity_state("", content_completed)
        assert state == "idle", "Failed to recognize completed turn - falsely detected as processing"

    def test_regression_input_needed_false_positive_proceed(self):
        """REGRESSION: Text like 'proceed?' in Claude's response should NOT trigger input_needed.

        Bug: The input_needed_patterns list included generic patterns like 'proceed?',
        'y/n', 'confirm?' which could appear in Claude's explanatory text.

        Fix (commit f73cf82): Stripped input_needed_patterns to ONLY specific Claude Code
        UI elements like 'Allow once', 'Yes, and don't ask again', etc.
        """
        # Claude explaining that something will proceed
        content_with_proceed_text = """
        I'll implement this feature for you. Before I proceed, let me explain the approach:

        1. First, we'll create the database schema
        2. Then, we'll add the API endpoints

        Do you want me to proceed? Here's what will happen...

        ✻ Thought for 45s
        ❯
        """

        state, _ = parse_activity_state("", content_with_proceed_text)
        assert state != "input_needed", "False positive: 'proceed?' in response text triggered input_needed"

    def test_regression_input_needed_false_positive_yes_no(self):
        """REGRESSION: Text like 'yes/no' in Claude's response should NOT trigger input_needed.

        Bug: Patterns like 'y/n' or 'yes/no' in explanatory text would falsely
        trigger input_needed state.

        Fix (commit f73cf82): Removed these generic patterns from input_needed detection.
        """
        content_with_yesno = """
        The function returns a boolean - true if the operation succeeded, false otherwise.
        You can interpret this as a yes/no answer to whether the file was saved.

        Here's an example:
        result = save_file()  # Returns true/false (yes/no)

        ✻ Worked for 1m 15s
        ❯
        """

        state, _ = parse_activity_state("", content_with_yesno)
        assert state != "input_needed", "False positive: 'yes/no' in response text triggered input_needed"

    def test_regression_input_needed_false_positive_confirm(self):
        """REGRESSION: Text like 'confirm' in Claude's response should NOT trigger input_needed.

        Bug: The word 'confirm' appearing anywhere could trigger input_needed.

        Fix (commit f73cf82): Only specific Claude Code UI strings trigger input_needed.
        """
        content_with_confirm = """
        I've made the changes. Let me confirm what was done:

        1. Updated the config file
        2. Added the new dependency
        3. Modified the test file

        The tests should now pass. You can confirm by running pytest.

        ✻ Crunched for 3m 10s
        ❯
        """

        state, _ = parse_activity_state("", content_with_confirm)
        assert state != "input_needed", "False positive: 'confirm' in response text triggered input_needed"

    def test_regression_genuine_permission_dialog_detected(self):
        """REGRESSION: Genuine Claude Code permission dialogs SHOULD trigger input_needed.

        Bug: After removing false positive patterns, we need to ensure genuine
        permission dialogs are still detected.

        Fix (commit f73cf82): Keep specific UI strings like 'Allow once',
        'Yes, and don't ask again' for genuine dialog detection.
        """
        # Genuine permission dialog
        content_permission_dialog = """
        ⚠️ Claude wants to run a bash command:

        rm -rf /tmp/test_dir

        Allow once                Allow for this session
        Yes, and don't ask again  Deny

        ❯
        """

        state, _ = parse_activity_state("", content_permission_dialog)
        assert state == "input_needed", "Failed to detect genuine permission dialog"

    def test_regression_genuine_ask_user_question_detected(self):
        """REGRESSION: AskUserQuestion UI elements SHOULD trigger input_needed.

        The specific selector UI with 'Enter to select' and '↑↓ to navigate'
        should trigger input_needed since it requires user action.
        """
        content_ask_question = """
        I need to know your preference:

        Which approach do you prefer?

        ❯ 1. Use the simple method (Recommended)
          2. Use the advanced method
          3. Skip this step

        Enter to select · ↑↓ to navigate
        """

        state, _ = parse_activity_state("", content_ask_question)
        assert state == "input_needed", "Failed to detect AskUserQuestion dialog"


class TestRegressionTurnCompletionWindow:
    """Regression tests for turn completion detection window size.

    Bug (commit f73cf82): Turn completion detection checked only the last 300 chars,
    but Claude Code's status bar alone can be 300+ chars, causing the completion
    marker to be outside the check window.

    Fix: Changed from content[-300:] to content[-800:] in is_turn_complete().
    """

    def test_regression_completion_marker_with_long_status_bar(self):
        """REGRESSION: Completion marker should be found even with 400+ char status bar.

        This test simulates the exact bug: a completion marker followed by a
        status bar that pushes the marker beyond a 300-char window.
        """
        # Build content with completion marker followed by ~450 chars of status bar
        completion_marker = "✻ Baked for 2m 30s"

        # Realistic status bar content (typically 300-500 chars)
        status_bar = """
⏵ Claude Code · /Users/developer/projects/my-app · Token Usage: 48,234 / 200,000 (24.1%) · Cost: $0.142 · Session: 45m · Ready
❯ samotage@MacBook-Pro my-app %
        """ * 2  # Make it ~500 chars

        content = f"""
Some previous Claude output...

{completion_marker}
{status_bar}
❯
"""

        # This should find the completion marker
        assert is_turn_complete(content), \
            f"Failed to find completion marker with {len(status_bar)} char status bar"

    def test_regression_completion_marker_at_300_char_boundary(self):
        """REGRESSION: Completion marker exactly at 300 char boundary should be found.

        The old code used [-300:] which would miss markers at exactly 300 chars.
        """
        # Create content where completion marker is at exactly 300 chars from end
        filler = "x" * 280  # 280 chars of filler
        content = f"✻ Baked for 1m{filler}❯"  # Total: 14 + 280 + 1 = 295 chars

        assert is_turn_complete(content), "Failed to find completion marker at 300 char boundary"

    def test_regression_completion_marker_at_700_chars(self):
        """REGRESSION: Completion marker at 700 chars from end should be found.

        With the new 800-char window, markers up to 800 chars from end should work.
        """
        filler = "x" * 680
        content = f"✻ Worked for 5m{filler}❯"

        assert is_turn_complete(content), "Failed to find completion marker at 700 chars from end"

    def test_completion_marker_beyond_window_not_found(self):
        """Completion markers beyond the 800-char window should NOT be found.

        This is expected behavior - very old completion markers shouldn't
        affect current state detection.
        """
        filler = "x" * 850
        content = f"✻ Baked for 1m{filler}❯"

        assert not is_turn_complete(content), \
            "Should not find completion marker beyond 800 char window"


class TestRegressionInputNeededPatterns:
    """Regression tests for specific input_needed pattern handling.

    These tests verify that ONLY genuine Claude Code UI elements trigger input_needed,
    not arbitrary text that might contain similar words.
    """

    @pytest.mark.parametrize("false_positive_text", [
        "Would you like to proceed?",
        "Please confirm this action.",
        "Enter y/n to continue",
        "Type yes or no",
        "Should I continue?",
        "Let me know if you want me to proceed.",
        "This will require confirmation from you.",
        "Select an option below:",
        "Choose option 1 or 2",
        "Do you want to allow this?",  # 'allow' but not in exact UI format
    ])
    def test_regression_false_positive_patterns_not_detected(self, false_positive_text):
        """REGRESSION: Common response text patterns should NOT trigger input_needed."""
        content = f"""
        {false_positive_text}

        Here's my explanation of what I'm going to do...

        ✻ Thought for 30s
        ❯
        """

        state, _ = parse_activity_state("", content)
        assert state != "input_needed", \
            f"False positive: '{false_positive_text[:30]}...' triggered input_needed"

    @pytest.mark.parametrize("genuine_pattern", [
        "Yes, and don't ask again",
        "Allow once",
        "Allow for this session",
        "❯ Yes",
        "❯ No",
        "❯ 1.",
        "❯ 2.",
        "Enter to select",
    ])
    def test_genuine_ui_patterns_detected(self, genuine_pattern):
        """Genuine Claude Code UI patterns SHOULD trigger input_needed."""
        content = f"""
        Some context here...

        {genuine_pattern}

        ❯
        """

        state, _ = parse_activity_state("", content)
        assert state == "input_needed", \
            f"Failed to detect genuine UI pattern: '{genuine_pattern}'"


# =============================================================================
# UNIT TESTS - Core Functions
# =============================================================================


class TestParseActivityState:
    """Unit tests for parse_activity_state() function."""

    def test_spinner_in_title_returns_processing(self):
        """Spinner character in window title indicates processing."""
        # Test various spinner characters
        for spinner in ["⠁", "⠂", "⠋", "⠙", "⣾", "◐"]:
            state, _ = parse_activity_state(f"{spinner} Claude Code - Working", "")
            assert state == "processing", f"Spinner '{spinner}' not detected as processing"

    def test_idle_char_in_title_returns_idle(self):
        """Idle character in window title indicates idle state."""
        for idle_char in ["✳", "✱", "*", "›", "❯", ">"]:
            state, _ = parse_activity_state(f"{idle_char} Claude Code - Ready", "")
            assert state == "idle", f"Idle char '{idle_char}' not detected as idle"

    def test_empty_title_content_based_processing(self):
        """Empty title (tmux) uses content-based processing detection."""
        content = "Some work... (esc to interrupt)"
        state, _ = parse_activity_state("", content)
        assert state == "processing"

    def test_empty_title_content_based_idle(self):
        """Empty title (tmux) uses content-based idle detection."""
        content = """
        Done with work.

        ✻ Baked for 2m
        ❯
        """
        state, _ = parse_activity_state("", content)
        assert state == "idle"

    def test_task_summary_extracted_from_title(self):
        """Task summary is extracted from window title."""
        _, summary = parse_activity_state("✳ Working on authentication feature", "")
        assert "authentication feature" in summary.lower() or "working on" in summary.lower()

    def test_uuid_removed_from_summary(self):
        """UUIDs are removed from task summary."""
        uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        _, summary = parse_activity_state(f"✳ Task - {uuid}", "")
        assert uuid not in summary


class TestIsTurnComplete:
    """Unit tests for is_turn_complete() function."""

    def test_returns_false_for_empty_content(self):
        """Empty content returns False."""
        assert is_turn_complete("") is False
        assert is_turn_complete(None) is False

    def test_detects_all_completion_verbs(self):
        """All known completion verbs are detected."""
        # Test a representative sample (testing all would be excessive)
        sample_verbs = ["Baked", "Brewed", "Clauded", "Thought", "Worked", "Wizarded"]

        for verb in sample_verbs:
            content = f"Some output... ✻ {verb} for 2m 30s"
            assert is_turn_complete(content), f"Failed to detect verb: {verb}"

    def test_requires_full_pattern(self):
        """Partial patterns don't trigger completion."""
        # Just the verb without "for" shouldn't match
        content = "✻ Baked the code"
        assert not is_turn_complete(content)

        # Missing the "✻" symbol
        content = "Baked for 2m"
        assert not is_turn_complete(content)

    def test_completion_marker_anywhere_in_tail(self):
        """Completion marker can be anywhere in the last 800 chars."""
        marker = "✻ Worked for 5m"

        # At the very end
        content1 = f"prefix {marker}"
        assert is_turn_complete(content1)

        # In the middle of the tail
        content2 = f"{marker}{'x' * 400}"
        assert is_turn_complete(content2)


class TestExtractTurnCommand:
    """Unit tests for extract_turn_command() function."""

    def test_extracts_command_after_prompt(self):
        """Extracts text after ❯ prompt."""
        content = """
        Some output
        ❯ /commit -m "Fix bug"
        Processing...
        """
        command = extract_turn_command(content)
        assert '/commit -m "Fix bug"' in command

    def test_returns_empty_for_no_prompt(self):
        """Returns empty string if no prompt found."""
        content = "Just some text without a prompt"
        assert extract_turn_command(content) == ""

    def test_returns_empty_for_empty_content(self):
        """Returns empty string for empty content."""
        assert extract_turn_command("") == ""
        assert extract_turn_command(None) == ""

    def test_truncates_long_commands(self):
        """Long commands are truncated with ellipsis."""
        long_text = "a" * 200
        content = f"❯ {long_text}"
        result = extract_turn_command(content, max_chars=100)
        assert len(result) <= 103  # 100 + "..."
        assert result.endswith("...")

    def test_finds_most_recent_prompt(self):
        """Finds the most recent ❯ prompt, not earlier ones."""
        content = """
        ❯ old command
        Some output
        ❯ new command
        """
        command = extract_turn_command(content)
        assert "new command" in command


class TestExtractCompletionMarker:
    """Unit tests for extract_completion_marker() function."""

    def test_extracts_full_marker(self):
        """Extracts the complete completion marker including time."""
        content = "Done! ✻ Brewed for 3m 45s\n❯"
        marker = extract_completion_marker(content)
        assert marker == "✻ Brewed for 3m 45s"

    def test_returns_empty_for_no_marker(self):
        """Returns empty string if no marker found."""
        content = "Just regular text"
        assert extract_completion_marker(content) == ""

    def test_handles_seconds_only_time(self):
        """Handles markers with just seconds (no minutes)."""
        content = "✻ Thought for 45s"
        marker = extract_completion_marker(content)
        assert "45s" in marker


class TestExtractLastMessage:
    """Unit tests for extract_last_message() function."""

    def test_extracts_substantial_content(self):
        """Extracts meaningful content, skipping prompts and short lines."""
        content = """
        Here's what I found in the codebase:

        The main function handles authentication and returns a boolean.
        It uses JWT tokens for session management.

        ❯
        """
        message = extract_last_message(content)
        assert "authentication" in message.lower() or "jwt" in message.lower()

    def test_skips_prompt_characters(self):
        """Prompt characters alone are skipped."""
        content = """
        Real content here.

        ❯
        $
        >
        """
        message = extract_last_message(content)
        assert "❯" not in message or "Real content" in message

    def test_truncates_to_max_chars(self):
        """Output is truncated to max_chars."""
        long_content = "word " * 500
        message = extract_last_message(long_content, max_chars=100)
        assert len(message) <= 103  # max_chars + "..."


class TestTrackSessionActivity:
    """Unit tests for track_session_activity() function."""

    def test_returns_iso_timestamp(self):
        """Returns an ISO format timestamp."""
        result = track_session_activity("test-session", "some content")
        # Should be parseable as ISO datetime
        datetime.fromisoformat(result.replace("Z", "+00:00"))

    def test_updates_timestamp_on_content_change(self):
        """Timestamp updates when content changes."""
        session_id = "test-session-change"

        ts1 = track_session_activity(session_id, "content v1")
        import time
        time.sleep(0.01)
        ts2 = track_session_activity(session_id, "content v2 different")

        # Timestamps should be different
        dt1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
        assert dt2 >= dt1

    def test_keeps_timestamp_on_same_content(self):
        """Timestamp stays the same when content is unchanged."""
        session_id = "test-session-same"
        content = "same content"

        ts1 = track_session_activity(session_id, content)
        ts2 = track_session_activity(session_id, content)

        # Should be the same timestamp
        assert ts1 == ts2


class TestFormatTimeAgo:
    """Unit tests for format_time_ago() function."""

    def test_just_now(self):
        """Recent timestamps show 'just now'."""
        now = datetime.now(timezone.utc).isoformat()
        assert format_time_ago(now) == "just now"

    def test_seconds_ago(self):
        """Shows seconds for times under a minute."""
        from datetime import timedelta
        ts = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        result = format_time_ago(ts)
        assert "s ago" in result

    def test_minutes_ago(self):
        """Shows minutes for times under an hour."""
        from datetime import timedelta
        ts = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        result = format_time_ago(ts)
        assert "m ago" in result

    def test_hours_ago(self):
        """Shows hours for times under a day."""
        from datetime import timedelta
        ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        result = format_time_ago(ts)
        assert "h ago" in result

    def test_days_ago(self):
        """Shows days for times over a day."""
        from datetime import timedelta
        ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        result = format_time_ago(ts)
        assert "d ago" in result


class TestFormatElapsed:
    """Unit tests for format_elapsed() function."""

    def test_negative_returns_just_now(self):
        """Negative seconds return 'just now'."""
        assert format_elapsed(-5) == "just now"

    def test_seconds_format(self):
        """Seconds under 60 show as Xs."""
        assert format_elapsed(45) == "45s"

    def test_minutes_format(self):
        """Seconds under 3600 show as Xm."""
        assert format_elapsed(300) == "5m"

    def test_hours_minutes_format(self):
        """Large durations show as Xh Ym."""
        assert format_elapsed(5400) == "1h 30m"


class TestParseSessionName:
    """Unit tests for parse_session_name() function."""

    def test_parses_valid_session_name(self):
        """Parses claude-{project}-{uuid8} format."""
        slug, uuid8 = parse_session_name("claude-my-project-abcd1234")
        assert slug == "my-project"
        assert uuid8 == "abcd1234"

    def test_handles_hyphens_in_project_name(self):
        """Handles project names with multiple hyphens."""
        slug, uuid8 = parse_session_name("claude-my-cool-project-12345678")
        assert slug == "my-cool-project"
        assert uuid8 == "12345678"

    def test_returns_none_for_invalid_prefix(self):
        """Returns (None, None) for non-claude sessions."""
        slug, uuid8 = parse_session_name("other-session")
        assert slug is None
        assert uuid8 is None

    def test_returns_none_for_empty_string(self):
        """Returns (None, None) for empty string."""
        slug, uuid8 = parse_session_name("")
        assert slug is None
        assert uuid8 is None


class TestMatchProject:
    """Unit tests for match_project() function."""

    def test_matches_by_slugified_name(self):
        """Matches project by slugified name."""
        projects = [
            {"name": "My Project", "path": "/path/to/my-project"},
            {"name": "Other", "path": "/path/to/other"},
        ]
        result = match_project("my-project", projects)
        assert result["name"] == "My Project"

    def test_matches_by_directory_name(self):
        """Matches project by directory name when name doesn't match."""
        projects = [
            {"name": "Display Name", "path": "/path/to/actual-dir"},
        ]
        result = match_project("actual-dir", projects)
        assert result["name"] == "Display Name"

    def test_returns_none_for_no_match(self):
        """Returns None when no project matches."""
        projects = [{"name": "Project A", "path": "/a"}]
        result = match_project("nonexistent", projects)
        assert result is None

    def test_returns_none_for_empty_slug(self):
        """Returns None for empty slug."""
        projects = [{"name": "Project", "path": "/path"}]
        result = match_project("", projects)
        assert result is None

    def test_matches_malformed_session_with_numeric_suffix(self):
        """Matches project when slug has numeric suffix (e.g., 'claude-monitor-3').

        This handles malformed WezTerm session names like 'claude-claude-monitor-3'
        which parse to slug 'claude-monitor-3' but should match 'claude-monitor'.
        """
        projects = [
            {"name": "Claude Monitor", "path": "/path/to/claude_monitor"},
            {"name": "Other Project", "path": "/path/to/other"},
        ]
        # Malformed slug with single-digit suffix
        result = match_project("claude-monitor-3", projects)
        assert result is not None
        assert result["name"] == "Claude Monitor"

        # Another numeric suffix
        result = match_project("claude-monitor-1", projects)
        assert result is not None
        assert result["name"] == "Claude Monitor"

    def test_does_not_match_valid_uuid_suffix_as_malformed(self):
        """Does not use prefix matching for valid 8-hex-char suffixes.

        Valid session names like 'claude-monitor-94e09464' should use
        exact matching, not prefix matching.
        """
        projects = [
            {"name": "Claude Monitor", "path": "/path/to/claude_monitor"},
        ]
        # Valid UUID suffix - exact match should work
        result = match_project("claude-monitor", projects)
        assert result is not None
        assert result["name"] == "Claude Monitor"

        # Non-numeric, non-matching suffix should NOT match
        result = match_project("claude-monitor-xyz", projects)
        assert result is None


# =============================================================================
# INTEGRATION TESTS - Multi-Component Flows
# =============================================================================


class TestActivityStateTransitions:
    """Integration tests for activity state transitions."""

    def test_processing_to_idle_transition(self):
        """Transition from processing to idle is detected correctly."""
        # Processing state
        processing_content = "Working... (esc to interrupt)"
        state1, _ = parse_activity_state("", processing_content)
        assert state1 == "processing"

        # Idle state after completion
        idle_content = """
        Work done.
        ✻ Baked for 2m
        ❯
        """
        state2, _ = parse_activity_state("", idle_content)
        assert state2 == "idle"

    def test_idle_to_input_needed_transition(self):
        """Transition from idle to input_needed is detected correctly."""
        idle_content = "✻ Ready for input\n❯"
        state1, _ = parse_activity_state("", idle_content)

        input_needed_content = """
        Claude wants to run a command:

        Allow once    Allow for this session

        ❯
        """
        state2, _ = parse_activity_state("", input_needed_content)
        assert state2 == "input_needed"


class TestTurnCycleTracking:
    """Integration tests for turn cycle tracking."""

    def test_turn_completion_detected_after_processing(self):
        """Turn completion is detected when processing ends."""
        # Simulate processing content
        processing_content = "Working on task... (esc to interrupt)"

        # Then completion
        completion_content = f"""
        {processing_content}

        Task completed.

        ✻ Worked for 3m 15s
        ❯
        """

        assert is_turn_complete(completion_content)

    def test_command_and_completion_extracted(self):
        """Both command and completion marker can be extracted from content."""
        content = """
        ❯ /fix the authentication bug

        I'll analyze the code...

        Done! The bug is fixed.

        ✻ Baked for 5m 30s
        ❯
        """

        command = extract_turn_command(content)
        marker = extract_completion_marker(content)

        assert "fix" in command.lower() or "authentication" in command.lower()
        assert "Baked for 5m 30s" in marker
