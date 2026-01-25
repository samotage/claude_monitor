# State Tracking Remediation Plan

## Overview

This document details the implementation plan for fixing state tracking issues identified in the turn/command processing audit. The fixes address stale data display, state desynchronization, and incomplete cleanup.

---

## Phase 1: Fix Cache Hit State Update Bug

**Priority:** HIGH
**Impact:** Eliminates redundant API calls, fixes stale state persistence
**Estimated Changes:** 3 lines

### Problem

When priorities cache is hit, `update_activity_states(new_states)` is not called, causing:
- `_previous_activity_states` to retain old values
- Same state transition detected repeatedly on subsequent polls
- Redundant `fetchPriorities()` calls from frontend

### File: `lib/headspace.py`

**Location:** Lines 755-776 (cache hit code path in `get_cached_priorities` usage within `compute_priorities`)

**Current Code (monitor.py:750-776):**
```python
cached, new_states = get_cached_priorities(sessions)
if not force_refresh and cached:
    # Get session states for filtering
    session_states = {s["session_id"]: s["activity_state"] for s in sessions}

    # Only include priorities for sessions that still exist
    valid_priorities = []
    for p in cached["priorities"]:
        if p["session_id"] in session_states:
            p["activity_state"] = session_states[p["session_id"]]
            valid_priorities.append(p)

    return {
        "success": True,
        "priorities": valid_priorities,
        "metadata": {
            "timestamp": cached["timestamp"],
            "headspace_summary": None,
            "cache_hit": True,
            "last_invalidated": get_last_invalidation_time(),
        }
    }
```

**Fixed Code:**
```python
cached, new_states = get_cached_priorities(sessions)
if not force_refresh and cached:
    # CRITICAL FIX: Update activity states even on cache hit
    # This prevents the same transition from being detected repeatedly
    update_activity_states(new_states)

    # Get session states for filtering
    session_states = {s["session_id"]: s["activity_state"] for s in sessions}

    # Only include priorities for sessions that still exist
    valid_priorities = []
    for p in cached["priorities"]:
        if p["session_id"] in session_states:
            p["activity_state"] = session_states[p["session_id"]]
            valid_priorities.append(p)

    return {
        "success": True,
        "priorities": valid_priorities,
        "metadata": {
            "timestamp": cached["timestamp"],
            "headspace_summary": None,
            "cache_hit": True,
            "last_invalidated": get_last_invalidation_time(),
        }
    }
```

### Verification

1. Start a Claude session
2. Let it complete a turn (processing → idle)
3. Check server logs - should see ONE priority refresh, not repeated ones
4. Dashboard should stabilize without flickering

---

## Phase 2: Align State Tracking Keys

**Priority:** HIGH
**Impact:** Fixes state desynchronization between frontend and backend
**Estimated Changes:** 15-20 lines

### Problem

- Backend tracks states by `session_name` (e.g., "claude-monitor-abc123")
- Frontend tracks states by `session.pid` (e.g., "12345")
- These are different identifiers, causing state mismatches
- Cleanup happens by session_name but frontend retains old PIDs

### File: `static/js/polling.js`

**Location:** Lines 96-107 (detectStateTransitions function)

**Current Code:**
```javascript
function detectStateTransitions(sessions) {
    let needsRefresh = false;

    for (const session of sessions) {
        const sessionId = String(session.pid);  // BUG: Uses PID
        const currentState = session.activity_state;
        const previousState = previousActivityStates[sessionId];
        // ...
    }
}
```

**Fixed Code:**
```javascript
function detectStateTransitions(sessions) {
    let needsRefresh = false;

    for (const session of sessions) {
        // Use stable session identifier that matches backend tracking
        // Priority: tmux_session > uuid > pid (fallback)
        const sessionId = session.tmux_session || session.uuid || String(session.pid);
        const currentState = session.activity_state;
        const previousState = previousActivityStates[sessionId];
        // ...
    }
}
```

**Also update cleanup section (lines 111-116):**
```javascript
// Clean up sessions that no longer exist
const currentSessionIds = new Set(sessions.map(s =>
    s.tmux_session || s.uuid || String(s.pid)
));
for (const sessionId of Object.keys(previousActivityStates)) {
    if (!currentSessionIds.has(sessionId)) {
        delete previousActivityStates[sessionId];
    }
}
```

### File: `static/js/config.js`

**Location:** Line 44

Add a comment for clarity:
```javascript
// Track previous activity states per session for transition detection
// Key: session identifier (tmux_session || uuid || pid)
// Value: activity state string
let previousActivityStates = {};
```

### Verification

1. Start multiple sessions
2. End one session
3. Start a new session (may reuse same PID)
4. Verify new session doesn't inherit old session's state
5. Check browser console - no state tracking errors

---

## Phase 3: Complete Reset API

**Priority:** MEDIUM
**Impact:** Allows manual recovery from broken state
**Estimated Changes:** 10 lines

### Problem

The `/api/reset` endpoint doesn't clear turn tracking state:
- `_turn_tracking` persists old TurnState objects
- `_last_completed_turn` shows stale completed turns
- `_previous_activity_states` has old state data
- `_enter_signals` may have stale signals

### File: `monitor.py`

**Location:** Lines 289-306 (reset_working_state function)

**Current Code:**
```python
def reset_working_state() -> dict:
    """Reset all in-memory working state."""
    reset_notification_state()
    reset_priorities_cache()

    return {
        "notification_state": "cleared",
        "priorities_cache": "cleared"
    }
```

**Fixed Code:**
```python
def reset_working_state() -> dict:
    """Reset all in-memory working state.

    Clears:
    - Notification tracking state (previous session states)
    - Priorities cache (AI-computed priorities)
    - Turn tracking state (active and completed turns)
    - Activity state tracking (previous states for transition detection)
    - Enter signals (pending WezTerm signals)
    """
    from lib.sessions import (
        clear_previous_activity_states,
        clear_turn_tracking,
        clear_enter_signals,
    )

    reset_notification_state()
    reset_priorities_cache()
    clear_previous_activity_states()
    clear_turn_tracking()
    clear_enter_signals()

    return {
        "notification_state": "cleared",
        "priorities_cache": "cleared",
        "turn_tracking": "cleared",
        "activity_states": "cleared",
        "enter_signals": "cleared",
    }
```

### File: `lib/sessions.py`

**Add new cleanup functions (after existing clear_previous_activity_states):**

```python
def clear_turn_tracking() -> None:
    """Clear all turn tracking state."""
    global _turn_tracking, _last_completed_turn
    _turn_tracking.clear()
    _last_completed_turn.clear()


def clear_enter_signals() -> None:
    """Clear all pending Enter signals."""
    global _enter_signals
    _enter_signals.clear()
```

### Verification

1. Start sessions, let them run
2. Call `POST /api/reset`
3. Verify response includes all cleared items
4. Check that dashboard refreshes cleanly
5. No stale data visible after reset

---

## Phase 4: Replace Stale Task Summary with Dynamic Context

**Priority:** MEDIUM
**Impact:** Session cards show relevant, current context
**Estimated Changes:** 25-30 lines

### Problem

`task_summary` comes from terminal window title which:
- Is set once when session starts
- Never updates during session
- Shows initial task, not current activity

### Solution: Prefer Last Turn Command Over Window Title

### File: `lib/sessions.py`

**Location:** Lines 798-802 (session dict construction for tmux sessions)

**Current Code:**
```python
return {
    "pid": pid,
    "project_name": project_name,
    # ...
    "task_summary": task_summary,  # From window title - STALE
    # ...
}
```

**Fixed Code:**
```python
# Compute dynamic task summary based on current/recent activity
dynamic_summary = None
if activity_state == "processing":
    # During processing, turn_command will be used by frontend
    dynamic_summary = task_summary  # Keep original for context
elif activity_state in ("idle", "input_needed"):
    # For idle/input_needed, prefer last completed turn's command
    last_turn = get_last_completed_turn(session_name)
    if last_turn and last_turn.get("command"):
        cmd = last_turn["command"]
        # Prefix to indicate this is historical context
        dynamic_summary = f"Last: {cmd[:60]}{'...' if len(cmd) > 60 else ''}"
    else:
        dynamic_summary = task_summary  # Fall back to window title

return {
    "pid": pid,
    "project_name": project_name,
    # ...
    "task_summary": dynamic_summary,
    "window_title": task_summary,  # Preserve original for debugging
    # ...
}
```

**Apply same change to iTerm session dict (lines 888-893).**

### Alternative: Frontend-Only Fix

If backend changes are too risky, fix in frontend only:

### File: `static/js/kanban.js`

**Location:** Lines 40-55 (getActivitySummary function)

**Current Code:**
```javascript
} else {
    // Idle: prefer AI summary, then turn_command context, then task_summary
    if (aiSummary) {
        summaryText = aiSummary;
    } else if (turnCommand) {
        summaryText = `Completed: ${turnCommand.length > 50 ? turnCommand.substring(0, 47) + '...' : turnCommand}`;
    } else {
        summaryText = taskSummary || 'Ready for task';
    }
}
```

**Fixed Code:**
```javascript
} else {
    // Idle: prefer AI summary, then turn_command context
    // Avoid task_summary as it's often stale (from window title at session start)
    if (aiSummary) {
        summaryText = aiSummary;
    } else if (turnCommand) {
        summaryText = `Last: ${turnCommand.length > 50 ? turnCommand.substring(0, 47) + '...' : turnCommand}`;
    } else {
        // Only use task_summary if it looks like recent context (not a generic title)
        // Generic titles often contain project names or "Claude Code"
        const looksGeneric = !taskSummary ||
            taskSummary.toLowerCase().includes('claude') ||
            taskSummary.length < 10;
        summaryText = looksGeneric ? 'Ready for task' : taskSummary;
    }
}
```

### Verification

1. Start a session with initial task "Feature X"
2. Complete that task
3. Start new task "Fix bug Y"
4. Verify card shows "Last: Fix bug Y" not "Feature X"
5. Complete "Fix bug Y", start "Write tests"
6. Verify card updates to "Last: Write tests"

---

## Phase 5: Add State Transition Tests

**Priority:** LOW
**Impact:** Prevents regression
**Estimated Changes:** 50-100 lines (new test file)

### File: `test_state_transitions.py` (new)

```python
"""Tests for state transition tracking and cleanup."""

import pytest
from lib.sessions import (
    _previous_activity_states,
    _turn_tracking,
    _last_completed_turn,
    clear_previous_activity_states,
    clear_turn_tracking,
    track_turn_cycle,
    get_previous_activity_state,
    set_previous_activity_states,
)
from lib.headspace import (
    should_refresh_priorities,
    update_activity_states,
    get_cached_priorities,
)


class TestStateTransitionDetection:
    """Test that state transitions are correctly detected."""

    def setup_method(self):
        clear_previous_activity_states()
        clear_turn_tracking()

    def test_processing_to_idle_triggers_refresh(self):
        """Transition from processing to idle should trigger priority refresh."""
        # Set previous state
        set_previous_activity_states({"session-1": "processing"})

        # Current state is idle
        sessions = [{"session_id": "session-1", "activity_state": "idle"}]

        needs_refresh, new_states = should_refresh_priorities(sessions)

        assert needs_refresh is True
        assert new_states["session-1"] == "idle"

    def test_idle_to_idle_no_refresh(self):
        """Staying idle should not trigger refresh."""
        set_previous_activity_states({"session-1": "idle"})

        sessions = [{"session_id": "session-1", "activity_state": "idle"}]

        needs_refresh, new_states = should_refresh_priorities(sessions)

        assert needs_refresh is False

    def test_new_session_triggers_refresh(self):
        """New session appearing should trigger refresh."""
        set_previous_activity_states({})  # Empty

        sessions = [{"session_id": "session-1", "activity_state": "idle"}]

        needs_refresh, new_states = should_refresh_priorities(sessions)

        assert needs_refresh is True


class TestStateUpdateOnCacheHit:
    """Test that activity states are updated even on cache hits."""

    def setup_method(self):
        clear_previous_activity_states()

    def test_cache_hit_updates_states(self):
        """Cache hit should still update activity states."""
        # This test validates the fix for Finding #6
        set_previous_activity_states({"session-1": "processing"})

        sessions = [{"session_id": "session-1", "activity_state": "idle"}]
        needs_refresh, new_states = should_refresh_priorities(sessions)

        # Simulate cache hit path calling update_activity_states
        update_activity_states(new_states)

        # Verify state was updated
        from lib.sessions import get_previous_activity_states
        states = get_previous_activity_states()
        assert states["session-1"] == "idle"


class TestCleanupFunctions:
    """Test that cleanup functions work correctly."""

    def test_clear_turn_tracking(self):
        """clear_turn_tracking should empty all turn dicts."""
        # Add some data
        _turn_tracking["session-1"] = "some_data"
        _last_completed_turn["session-1"] = {"command": "test"}

        clear_turn_tracking()

        assert len(_turn_tracking) == 0
        assert len(_last_completed_turn) == 0
```

---

## Implementation Order

| Step | Phase | Risk | Dependencies |
|------|-------|------|--------------|
| 1 | Phase 1 (Cache bug) | Low | None |
| 2 | Phase 3 (Reset API) | Low | Phase 1 (needs new functions) |
| 3 | Phase 2 (Key alignment) | Medium | None |
| 4 | Phase 4 (Task summary) | Medium | None |
| 5 | Phase 5 (Tests) | Low | All above |

---

## Rollback Plan

Each phase can be rolled back independently:

- **Phase 1:** Remove the `update_activity_states(new_states)` line
- **Phase 2:** Revert to `String(session.pid)` in polling.js
- **Phase 3:** Remove new function calls from reset_working_state
- **Phase 4:** Revert to using `task_summary` directly

---

## Success Criteria

| Phase | Verification |
|-------|--------------|
| 1 | No repeated "refreshing priorities" logs after turn completes |
| 2 | State tracking stable across session start/stop cycles |
| 3 | `/api/reset` returns all cleared items, dashboard refreshes cleanly |
| 4 | Session cards show recent activity, not initial task |
| 5 | All new tests pass, existing tests still pass |
