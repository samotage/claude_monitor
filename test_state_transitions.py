"""Tests for state transition tracking and cleanup.

These tests verify the fixes for:
- Cache hit state update bug (Finding #6)
- State tracking key alignment (Finding #2)
- Reset API completeness (Finding #9)
"""

import pytest
from unittest.mock import patch, MagicMock


class TestStateTransitionDetection:
    """Test that state transitions are correctly detected."""

    def setup_method(self):
        """Reset state before each test."""
        from lib.sessions import (
            clear_previous_activity_states,
            clear_turn_tracking,
            clear_enter_signals,
        )
        clear_previous_activity_states()
        clear_turn_tracking()
        clear_enter_signals()

    def test_processing_to_idle_triggers_refresh(self):
        """Transition from processing to idle should trigger priority refresh."""
        from lib.sessions import set_previous_activity_states
        from lib.headspace import should_refresh_priorities

        # Set previous state
        set_previous_activity_states({"session-1": "processing"})

        # Current state is idle
        sessions = [{"session_id": "session-1", "activity_state": "idle"}]

        needs_refresh, new_states = should_refresh_priorities(sessions)

        assert needs_refresh is True
        assert new_states["session-1"] == "idle"

    def test_idle_to_idle_no_refresh(self):
        """Staying idle should not trigger refresh."""
        from lib.sessions import set_previous_activity_states
        from lib.headspace import should_refresh_priorities

        set_previous_activity_states({"session-1": "idle"})

        sessions = [{"session_id": "session-1", "activity_state": "idle"}]

        needs_refresh, new_states = should_refresh_priorities(sessions)

        assert needs_refresh is False

    def test_new_session_triggers_refresh(self):
        """New session appearing should trigger refresh."""
        from lib.sessions import set_previous_activity_states
        from lib.headspace import should_refresh_priorities

        set_previous_activity_states({})  # Empty - no previous sessions

        sessions = [{"session_id": "session-1", "activity_state": "idle"}]

        needs_refresh, new_states = should_refresh_priorities(sessions)

        assert needs_refresh is True

    def test_session_disappeared_triggers_refresh(self):
        """Session disappearing should trigger refresh."""
        from lib.sessions import set_previous_activity_states
        from lib.headspace import should_refresh_priorities

        set_previous_activity_states({
            "session-1": "idle",
            "session-2": "idle"
        })

        # Only session-1 remains
        sessions = [{"session_id": "session-1", "activity_state": "idle"}]

        needs_refresh, new_states = should_refresh_priorities(sessions)

        assert needs_refresh is True

    def test_input_needed_to_processing_triggers_refresh(self):
        """User responding (input_needed -> processing) should trigger refresh."""
        from lib.sessions import set_previous_activity_states
        from lib.headspace import should_refresh_priorities

        set_previous_activity_states({"session-1": "input_needed"})

        sessions = [{"session_id": "session-1", "activity_state": "processing"}]

        needs_refresh, new_states = should_refresh_priorities(sessions)

        assert needs_refresh is True


class TestStateUpdateOnCacheHit:
    """Test that activity states are updated even on cache hits."""

    def setup_method(self):
        """Reset state before each test."""
        from lib.sessions import clear_previous_activity_states
        from lib.headspace import reset_priorities_cache
        clear_previous_activity_states()
        reset_priorities_cache()

    def test_state_update_function_works(self):
        """update_activity_states should update the tracking dict."""
        from lib.sessions import (
            set_previous_activity_states,
            get_previous_activity_states,
        )
        from lib.headspace import update_activity_states

        # Start with processing state
        set_previous_activity_states({"session-1": "processing"})

        # Simulate cache hit path calling update_activity_states with new states
        new_states = {"session-1": "idle"}
        update_activity_states(new_states)

        # Verify state was updated
        states = get_previous_activity_states()
        assert states["session-1"] == "idle"

    def test_repeated_transitions_not_detected_after_update(self):
        """After updating states, the same transition should not be detected again."""
        from lib.sessions import set_previous_activity_states
        from lib.headspace import should_refresh_priorities, update_activity_states

        # Set initial state
        set_previous_activity_states({"session-1": "processing"})

        sessions = [{"session_id": "session-1", "activity_state": "idle"}]

        # First check - should detect transition
        needs_refresh1, new_states1 = should_refresh_priorities(sessions)
        assert needs_refresh1 is True

        # Update states (simulating what cache hit path should do)
        update_activity_states(new_states1)

        # Second check - should NOT detect transition (already updated)
        needs_refresh2, new_states2 = should_refresh_priorities(sessions)
        assert needs_refresh2 is False


class TestCleanupFunctions:
    """Test that cleanup functions work correctly."""

    def test_clear_turn_tracking(self):
        """clear_turn_tracking should empty all turn dicts."""
        from lib.sessions import (
            _turn_tracking,
            _last_completed_turn,
            clear_turn_tracking,
        )

        # Add some data
        _turn_tracking["session-1"] = MagicMock()
        _last_completed_turn["session-1"] = {"command": "test"}

        clear_turn_tracking()

        assert len(_turn_tracking) == 0
        assert len(_last_completed_turn) == 0

    def test_clear_enter_signals(self):
        """clear_enter_signals should empty the signals dict."""
        from lib.sessions import _enter_signals, clear_enter_signals

        # Add some data
        _enter_signals["session-1"] = "2024-01-01T00:00:00Z"

        clear_enter_signals()

        assert len(_enter_signals) == 0

    def test_clear_previous_activity_states(self):
        """clear_previous_activity_states should empty the states dict."""
        from lib.sessions import (
            set_previous_activity_states,
            get_previous_activity_states,
            clear_previous_activity_states,
        )

        set_previous_activity_states({"session-1": "idle"})
        assert len(get_previous_activity_states()) == 1

        clear_previous_activity_states()

        assert len(get_previous_activity_states()) == 0


class TestResetWorkingState:
    """Test that reset_working_state clears all state."""

    def setup_method(self):
        """Populate state before each test."""
        from lib.sessions import (
            _turn_tracking,
            _last_completed_turn,
            _enter_signals,
            set_previous_activity_states,
        )
        from lib.headspace import update_priorities_cache

        # Populate all state dicts
        _turn_tracking["session-1"] = MagicMock()
        _last_completed_turn["session-1"] = {"command": "test"}
        _enter_signals["session-1"] = "2024-01-01T00:00:00Z"
        set_previous_activity_states({"session-1": "idle"})
        update_priorities_cache([{"session_id": "session-1"}])

    def test_reset_clears_all_state(self):
        """reset_working_state should clear all tracking state."""
        from monitor import reset_working_state
        from lib.sessions import (
            _turn_tracking,
            _last_completed_turn,
            _enter_signals,
            get_previous_activity_states,
        )
        from lib.headspace import get_priorities_cache

        result = reset_working_state()

        # Verify all state is cleared
        assert len(_turn_tracking) == 0
        assert len(_last_completed_turn) == 0
        assert len(_enter_signals) == 0
        assert len(get_previous_activity_states()) == 0
        assert get_priorities_cache()["priorities"] is None

        # Verify return value includes all cleared items
        assert result["turn_tracking"] == "cleared"
        assert result["activity_states"] == "cleared"
        assert result["enter_signals"] == "cleared"
        assert result["priorities_cache"] == "cleared"


class TestCleanupStaleSessionData:
    """Test stale session data cleanup."""

    def setup_method(self):
        """Populate state before each test."""
        from lib.sessions import (
            _turn_tracking,
            _last_completed_turn,
            _enter_signals,
            set_previous_activity_states,
            clear_turn_tracking,
            clear_enter_signals,
            clear_previous_activity_states,
        )

        # Start clean
        clear_turn_tracking()
        clear_enter_signals()
        clear_previous_activity_states()

        # Add data for multiple sessions
        _turn_tracking["active-session"] = MagicMock()
        _turn_tracking["stale-session"] = MagicMock()
        _last_completed_turn["active-session"] = {"command": "test1"}
        _last_completed_turn["stale-session"] = {"command": "test2"}
        _enter_signals["active-session"] = "2024-01-01T00:00:00Z"
        _enter_signals["stale-session"] = "2024-01-01T00:00:00Z"
        set_previous_activity_states({
            "active-session": "idle",
            "stale-session": "processing"
        })

    def test_cleanup_removes_stale_sessions(self):
        """cleanup_stale_session_data should remove only stale sessions."""
        from lib.sessions import (
            cleanup_stale_session_data,
            _turn_tracking,
            _last_completed_turn,
            _enter_signals,
            get_previous_activity_states,
        )

        # Only active-session is still active
        active_ids = {"active-session"}
        cleaned = cleanup_stale_session_data(active_ids)

        # Should have cleaned up stale-session from all dicts
        assert cleaned > 0
        assert "active-session" in _turn_tracking
        assert "stale-session" not in _turn_tracking
        assert "active-session" in _last_completed_turn
        assert "stale-session" not in _last_completed_turn
        assert "active-session" in _enter_signals
        assert "stale-session" not in _enter_signals
        states = get_previous_activity_states()
        assert "active-session" in states
        assert "stale-session" not in states
