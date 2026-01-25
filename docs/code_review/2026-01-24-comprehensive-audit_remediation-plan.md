# Remediation Plan: Claude Monitor Comprehensive Audit

**Date:** 2026-01-24
**Based on:** `2026-01-24-comprehensive-audit.md`
**Status:** Approved for implementation

---

## Executive Summary

This plan addresses findings from the comprehensive code audit. It incorporates specific direction from the project owner and follows audit recommendations for remaining issues.

**Key Clarifications Applied:**
- Turn tracking being tmux-only is **intended design** (Issue #1 removed from scope)
- iTerm support is **required** and must be retained
- Soft transitions feature is **deprecated** (not to be implemented)
- Polling mechanism to be replaced with **event-driven** approach

**Total Work Items:** 24 tasks across 4 phases

---

## Table of Contents

1. [Phase 1: Critical Fixes](#phase-1-critical-fixes)
2. [Phase 2: Architecture Improvements](#phase-2-architecture-improvements)
3. [Phase 3: Code Cleanup](#phase-3-code-cleanup)
4. [Phase 4: Documentation](#phase-4-documentation)
5. [Implementation Notes](#implementation-notes)
6. [Testing Requirements](#testing-requirements)

---

## Phase 1: Critical Fixes

**Priority:** Must complete first
**Estimated scope:** 5 tasks

### Task 1.1: Fix Cache Validation Side Effects
**Audit Issue:** #5
**Priority:** Critical
**Files:**
- `lib/headspace.py:359-406`

**Problem:**
`should_refresh_priorities()` modifies `_previous_activity_states` as a side effect, causing `is_cache_valid()` to return different results on consecutive calls.

**Solution:**
1. Separate state comparison from state mutation
2. Make `should_refresh_priorities()` a pure function that returns both the decision AND the new state
3. Only update `_previous_activity_states` after cache is actually refreshed

**Implementation:**
```python
# Before (problematic)
def should_refresh_priorities(sessions: list[dict]) -> bool:
    global _previous_activity_states
    # ... comparison logic ...
    _previous_activity_states = current_states  # Side effect!
    return needs_refresh

# After (pure function)
def should_refresh_priorities(sessions: list[dict]) -> tuple[bool, dict]:
    """Returns (needs_refresh, new_state) without mutation."""
    current_states = {s["session_id"]: s["activity_state"] for s in sessions}
    needs_refresh = current_states != _previous_activity_states
    return needs_refresh, current_states

def update_activity_states(new_states: dict) -> None:
    """Explicitly update state after cache refresh."""
    global _previous_activity_states
    _previous_activity_states = new_states
```

**Acceptance Criteria:**
- [ ] `is_cache_valid()` is idempotent (same result on repeated calls)
- [ ] State only updates after successful cache refresh
- [ ] Unit test verifies no side effects

---

### Task 1.2: Persist Session Tracking Across Restart
**Audit Issue:** #15
**Priority:** Critical
**Files:**
- `lib/session_sync.py:73`
- New: `data/session_state.yaml`

**Problem:**
`_known_sessions` is in-memory only. On restart, all active sessions appear as "new" and no summarization occurs for sessions that were active before restart.

**Solution:**
1. Persist `_known_sessions` to `data/session_state.yaml`
2. Load on startup
3. Save on each sync cycle (debounced)
4. Clean up stale entries on load

**Implementation:**
```python
SESSION_STATE_FILE = Path(__file__).parent.parent / "data" / "session_state.yaml"

def _save_known_sessions() -> None:
    """Persist known sessions to disk."""
    data = {
        uuid: {
            "uuid": ks.uuid,
            "project_name": ks.project_name,
            "project_path": ks.project_path,
            "pid": ks.pid,
            "first_seen": ks.first_seen.isoformat(),
            "last_seen": ks.last_seen.isoformat(),
        }
        for uuid, ks in _known_sessions.items()
    }
    SESSION_STATE_FILE.write_text(yaml.dump(data, default_flow_style=False))

def _load_known_sessions() -> None:
    """Load known sessions from disk on startup."""
    global _known_sessions
    if not SESSION_STATE_FILE.exists():
        return
    # Load and validate entries (check if PIDs still exist, etc.)
```

**Acceptance Criteria:**
- [ ] Sessions survive server restart
- [ ] Stale sessions (dead PIDs) cleaned up on load
- [ ] Session end detection works for pre-restart sessions

---

### Task 1.3: Add Missing Config Default for tmux_logging
**Audit Issue:** #8
**User Direction:** Default to `false`
**Priority:** Critical
**Files:**
- `config.py:14-39`

**Problem:**
`tmux_logging.debug_enabled` has no default in `DEFAULT_CONFIG`.

**Solution:**
Add to DEFAULT_CONFIG with value `false`:

```python
DEFAULT_CONFIG = {
    # ... existing ...
    "tmux_logging": {
        "debug_enabled": False,
    },
}
```

**Acceptance Criteria:**
- [ ] App starts correctly with missing/empty config.yaml
- [ ] Default is `false` (events only, no payloads)

---

### Task 1.4: Move OpenRouter API Key to .env
**Audit Issue:** #11
**User Direction:** Never in git commits
**Priority:** Critical
**Files:**
- `config.yaml` (remove key)
- `.env.example` (new)
- `.env` (gitignored)
- `lib/compression.py` (read from env)
- `.gitignore` (ensure .env listed)

**Problem:**
API key hardcoded in config.yaml risks exposure.

**Solution:**
1. Create `.env.example` with placeholder
2. Read key from environment variable `OPENROUTER_API_KEY`
3. Fall back to config.yaml for backwards compatibility (with warning)
4. Remove actual key from config.yaml in repo

**Implementation:**
```python
# lib/compression.py
import os

def get_openrouter_config() -> dict:
    config = load_config()
    openrouter = config.get("openrouter", {})

    # Prefer environment variable
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        api_key = openrouter.get("api_key", "")
        if api_key:
            print("Warning: OpenRouter API key in config.yaml is deprecated. Use OPENROUTER_API_KEY env var.")

    return {
        "api_key": api_key,
        "model": openrouter.get("model", DEFAULT_MODEL),
        "compression_interval": openrouter.get("compression_interval", DEFAULT_COMPRESSION_INTERVAL),
    }
```

**.env.example:**
```
# OpenRouter API Configuration
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

**Acceptance Criteria:**
- [ ] App works with key in .env only
- [ ] Warning printed if key found in config.yaml
- [ ] .env is gitignored
- [ ] .env.example committed with placeholder

---

### Task 1.5: Add Rate Limiting Between API Calls
**Audit Issue:** #6
**Priority:** Critical
**Files:**
- `lib/compression.py:414-455`

**Problem:**
`process_compression_queue()` processes all pending sessions with no delay, risking rate limits.

**Solution:**
Add configurable delay between consecutive API calls:

```python
API_CALL_DELAY_SECONDS = 2  # Minimum delay between calls

def process_compression_queue(project_name: str) -> int:
    """Process pending compressions with rate limiting."""
    pending = get_pending_compressions(project_name)
    processed = 0

    for i, session in enumerate(pending):
        if i > 0:
            time.sleep(API_CALL_DELAY_SECONDS)  # Rate limit

        success, error = compress_session(project_name, session)
        if success:
            processed += 1

    return processed
```

**Acceptance Criteria:**
- [ ] Minimum 2 second delay between API calls
- [ ] Delay configurable via constant (future: config.yaml)

---

## Phase 2: Architecture Improvements

**Priority:** High
**Estimated scope:** 6 tasks

### Task 2.1: Implement Event-Driven Priorities Refresh
**Audit Issue:** #9
**User Direction:** Replace polling with events
**Priority:** High
**Files:**
- `lib/headspace.py`
- `lib/sessions.py`
- `monitor.py`
- `templates/index.html` (frontend)

**Problem:**
`priorities.polling_interval` implies backend polling, but it's actually frontend polling. This is confusing and inefficient.

**Solution:**
Implement event-driven refresh triggered by:
1. **Turn completion** - When session transitions to idle/input_needed
2. **User action** - Explicit refresh button/API call
3. **Headspace update** - When user changes current focus

**Implementation:**

**Backend - Event emission:**
```python
# lib/sessions.py - Add to track_turn_cycle()
def track_turn_cycle(...):
    # ... existing logic ...
    if new_state in ("idle", "input_needed") and old_state == "processing":
        # Turn completed - emit event
        _emit_priorities_refresh_needed()

# lib/headspace.py
_priorities_refresh_callbacks: list[callable] = []

def on_priorities_refresh_needed(callback: callable) -> None:
    """Register callback for priorities refresh events."""
    _priorities_refresh_callbacks.append(callback)

def _emit_priorities_refresh_needed() -> None:
    """Notify all listeners that priorities should refresh."""
    for callback in _priorities_refresh_callbacks:
        try:
            callback()
        except Exception as e:
            print(f"Warning: Priorities refresh callback failed: {e}")
```

**Backend - Headspace update trigger:**
```python
# lib/headspace.py - Modify save_headspace()
def save_headspace(current_focus: str, constraints: Optional[str] = None) -> dict:
    # ... existing save logic ...
    _emit_priorities_refresh_needed()  # Trigger refresh
    return result
```

**Frontend - SSE or WebSocket (future) or invalidation flag:**
```python
# Simple approach: Add invalidation timestamp to API
@app.route("/api/priorities")
def api_priorities():
    # ... existing ...
    return jsonify({
        # ... existing fields ...
        "last_invalidated": _get_last_invalidation_time()
    })
```

**Config cleanup:**
```python
# config.py - Remove or mark deprecated
"priorities": {
    "enabled": True,
    # "polling_interval": 60,  # DEPRECATED - now event-driven
    "model": "",
},
```

**Acceptance Criteria:**
- [ ] Priorities refresh on turn completion
- [ ] Priorities refresh on headspace update
- [ ] Manual refresh still works via API
- [ ] `polling_interval` config removed or deprecated
- [ ] Frontend updated to use events (or polling with invalidation check)

---

### Task 2.2: Implement Exponential Backoff for Compression Retries
**Audit Issue:** #7
**Priority:** High
**Files:**
- `lib/compression.py:28, 398-455`

**Problem:**
`RETRY_DELAYS = [60, 300, 1800]` is defined but never used. Retries happen on fixed interval.

**Solution:**
Track `last_retry_at` and use `RETRY_DELAYS` for actual backoff:

```python
def _should_retry_now(session: dict) -> bool:
    """Check if enough time has passed for retry based on backoff schedule."""
    retry_count = session.get("retry_count", 0)
    last_retry_at = session.get("last_retry_at")

    if not last_retry_at:
        return True  # Never retried, try now

    # Get delay for this retry attempt
    delay_index = min(retry_count, len(RETRY_DELAYS) - 1)
    required_delay = RETRY_DELAYS[delay_index]

    last_retry = datetime.fromisoformat(last_retry_at)
    elapsed = (datetime.now(timezone.utc) - last_retry).total_seconds()

    return elapsed >= required_delay

def process_compression_queue(project_name: str) -> int:
    pending = get_pending_compressions(project_name)
    processed = 0

    for session in pending:
        if not _should_retry_now(session):
            continue  # Skip, not time yet

        success, error = compress_session(project_name, session)
        if success:
            remove_from_compression_queue(project_name, session["session_id"])
            processed += 1
        else:
            _update_retry_metadata(project_name, session["session_id"])

    return processed
```

**Acceptance Criteria:**
- [ ] First retry after 60 seconds
- [ ] Second retry after 5 minutes
- [ ] Third+ retry after 30 minutes
- [ ] `last_retry_at` tracked in queue entry

---

### Task 2.3: Standardize session_id Format in API
**Audit Issue:** #33
**Priority:** High
**Files:**
- `monitor.py` (all session-related endpoints)
- `lib/sessions.py`
- `templates/index.html`

**Problem:**
Inconsistent session_id formats across API:
- Some use UUID
- Some use PID
- Some use uuid_short

**Solution:**
Standardize on UUID as the canonical session_id. Provide PID as separate field where needed.

```python
# Standard session response format
{
    "session_id": "abc-123-def-456",      # Always full UUID
    "session_id_short": "abc-123",         # Convenience field
    "pid": 12345,                          # Process ID (separate field)
    "project_name": "my-project",
    # ... other fields
}
```

**Endpoints to update:**
- `GET /api/sessions` - Ensure consistent format
- `GET /api/priorities` - Use UUID not PID
- `POST /api/focus/<identifier>` - Accept both UUID and PID, document preference

**Acceptance Criteria:**
- [ ] All endpoints use UUID as primary session_id
- [ ] PID available as separate field
- [ ] API documentation updated

---

### Task 2.4: Add Compression Rollback Mechanism
**Audit Issue:** #14
**Priority:** High
**Files:**
- `lib/compression.py:144-163`

**Problem:**
`update_project_history()` overwrites history with no backup. Bad AI output permanently corrupts history.

**Solution:**
Keep previous history as backup:

```python
def update_project_history(project_name: str, summary: str) -> bool:
    project_data = load_project_data(project_name)
    if not project_data:
        return False

    existing_history = project_data.get("history", {})

    # Backup previous summary
    project_data["history"] = {
        "summary": summary,
        "last_compressed_at": datetime.now(timezone.utc).isoformat(),
        "previous_summary": existing_history.get("summary"),  # Backup
        "previous_compressed_at": existing_history.get("last_compressed_at"),
    }

    return save_project_data(project_name, project_data)
```

**Acceptance Criteria:**
- [ ] Previous summary preserved in `previous_summary` field
- [ ] Manual rollback possible by swapping fields
- [ ] Consider: API endpoint for rollback (future)

---

### Task 2.5: Consolidate Duplicate State Tracking
**Audit Issue:** #3
**Priority:** Medium
**Files:**
- `lib/sessions.py:67`
- `lib/headspace.py:40`

**Problem:**
Two separate `_previous_activity_states` dicts tracking similar concepts.

**Solution:**
Create single source of truth in a shared location:

```python
# lib/state.py (new file)
"""Shared state management for Claude Headspace."""

_activity_states: dict[str, str] = {}

def get_activity_state(session_id: str) -> Optional[str]:
    return _activity_states.get(session_id)

def set_activity_state(session_id: str, state: str) -> None:
    _activity_states[session_id] = state

def get_all_activity_states() -> dict[str, str]:
    return _activity_states.copy()

def clear_activity_state(session_id: str) -> None:
    _activity_states.pop(session_id, None)
```

Update both `sessions.py` and `headspace.py` to use this shared module.

**Acceptance Criteria:**
- [ ] Single `_activity_states` dict
- [ ] Both modules import from `lib/state.py`
- [ ] No duplicate tracking

---

### Task 2.6: Cleanup Stale Turn Tracking Data
**Audit Issue:** #4
**Priority:** Medium
**Files:**
- `lib/sessions.py:56-67`

**Problem:**
`_turn_tracking`, `_last_completed_turn`, `_session_activity_cache` never cleaned.

**Solution:**
Add cleanup when sessions end:

```python
def cleanup_session_state(session_id: str) -> None:
    """Clean up all tracking state for an ended session."""
    _turn_tracking.pop(session_id, None)
    _last_completed_turn.pop(session_id, None)
    _session_activity_cache.pop(session_id, None)
    clear_activity_state(session_id)  # From lib/state.py
```

Call from `session_sync.py` when session ends:

```python
def _handle_session_end(known_session: KnownSession) -> None:
    # ... existing summarization logic ...
    cleanup_session_state(known_session.uuid)
```

**Acceptance Criteria:**
- [ ] State cleaned up when session ends
- [ ] No memory leak over long server runtime

---

## Phase 3: Code Cleanup

**Priority:** Medium
**Estimated scope:** 7 tasks

### Task 3.1: Remove Legacy State-File Scanning Code
**Audit Issue:** #27
**User Direction:** Remove old state-file approach
**Priority:** Medium
**Files:**
- `lib/sessions.py:666-748` (`scan_tmux_session()`)

**Problem:**
`scan_tmux_session()` handles legacy `.claude-monitor-*.json` state files but is never called. `scan_sessions()` only uses `scan_backend_session()`.

**Solution:**
1. Verify `scan_tmux_session()` is truly unused
2. Remove the function
3. Remove any state-file related helpers
4. Update docstrings

**Note:** Keep `scan_iterm_session()` - iTerm support is required.

**Acceptance Criteria:**
- [ ] `scan_tmux_session()` removed
- [ ] State-file helpers removed if unused elsewhere
- [ ] No regression in tmux session detection
- [ ] iTerm session detection still works

---

### Task 3.2: Mark Soft Transitions as Deprecated in PRDs
**Audit Issue:** #24
**User Direction:** Deprecate, don't implement
**Priority:** Medium
**Files:**
- `docs/prds/headspace/done/e1_s7_ai-prioritisation-prd.md`

**Problem:**
PRD FR26-27 specify soft transitions that are not implemented and now deprecated.

**Solution:**
Add deprecation notice to PRD:

```markdown
### Deprecated Features

> **Note:** The following features from the original specification have been
> deprecated and will not be implemented:
>
> - **FR26-27: Soft Transitions** - Priority reordering delay during processing
> - **FR28: Soft Transition Pending Indicator** - API response field
>
> These were deemed unnecessary complexity. Priorities refresh immediately
> on state change via event-driven architecture.
```

**Acceptance Criteria:**
- [ ] PRD updated with deprecation notice
- [ ] FR26-28 marked as deprecated

---

### Task 3.3: Remove Soft Transition Code References
**Audit Issue:** #25
**User Direction:** Clean up all references
**Priority:** Medium
**Files:**
- `lib/headspace.py:617-626`

**Problem:**
`is_any_session_processing()` exists but is never called.

**Solution:**
Remove the unused function:

```python
# DELETE this function from lib/headspace.py
def is_any_session_processing(sessions: list[dict]) -> bool:
    return any(s.get("activity_state") == "processing" for s in sessions)
```

**Acceptance Criteria:**
- [ ] Function removed
- [ ] No references to soft transitions in code
- [ ] No `soft_transition_pending` field expected in API

---

### Task 3.4: Fix tmux Session Naming Collision Risk
**Audit Issue:** #34
**Priority:** Medium
**Files:**
- `lib/tmux.py:442-461`

**Problem:**
`slugify_project_name()` could produce identical slugs for different projects (e.g., "My Project" and "my-project" both become "my-project").

**Solution:**
Add collision detection and suffix:

```python
def get_unique_session_name(project_name: str, existing_sessions: list[str]) -> str:
    """Get unique tmux session name, adding suffix if needed."""
    base_name = f"claude-{slugify_project_name(project_name)}"

    if base_name not in existing_sessions:
        return base_name

    # Add numeric suffix for collision
    for i in range(2, 100):
        candidate = f"{base_name}-{i}"
        if candidate not in existing_sessions:
            return candidate

    raise ValueError(f"Too many sessions with name {base_name}")
```

**Acceptance Criteria:**
- [ ] Collision detected before creating session
- [ ] Suffix added if collision detected
- [ ] Warning logged when collision handling triggered

---

### Task 3.5: Implement Log Rotation
**Audit Issue:** #31
**Priority:** Medium
**Files:**
- `lib/logging.py`
- `lib/tmux_logging.py`

**Problem:**
`openrouter.jsonl` and `tmux.jsonl` grow indefinitely.

**Solution:**
Add rotation based on file size:

```python
import os
from datetime import datetime

MAX_LOG_SIZE_MB = 10
MAX_LOG_FILES = 5

def _rotate_log_if_needed(log_file: str) -> None:
    """Rotate log file if it exceeds max size."""
    if not os.path.exists(log_file):
        return

    size_mb = os.path.getsize(log_file) / (1024 * 1024)
    if size_mb < MAX_LOG_SIZE_MB:
        return

    # Rotate: file.jsonl -> file.jsonl.1, file.jsonl.1 -> file.jsonl.2, etc.
    for i in range(MAX_LOG_FILES - 1, 0, -1):
        old_name = f"{log_file}.{i}"
        new_name = f"{log_file}.{i + 1}"
        if os.path.exists(old_name):
            if i + 1 >= MAX_LOG_FILES:
                os.remove(old_name)  # Delete oldest
            else:
                os.rename(old_name, new_name)

    os.rename(log_file, f"{log_file}.1")
```

Call before each write operation.

**Acceptance Criteria:**
- [ ] Logs rotate at 10MB
- [ ] Keep last 5 rotated files
- [ ] Oldest files deleted automatically

---

### Task 3.6: Fix Path Encoding Verification
**Audit Issue:** #16
**Priority:** Medium
**Files:**
- `lib/summarization.py:90-106`

**Problem:**
Path encoding may not match Claude Code's actual encoding.

**Solution:**
Add verification and fallback:

```python
def get_claude_logs_directory(project_path: str) -> Optional[Path]:
    """Get Claude Code logs directory, trying multiple encoding strategies."""
    encodings = [
        encode_project_path(project_path),  # Current approach
        str(Path(project_path).resolve()).replace("/", "-"),  # Without underscore replacement
    ]

    for encoded in encodings:
        logs_dir = CLAUDE_PROJECTS_DIR / encoded
        if logs_dir.exists() and logs_dir.is_dir():
            return logs_dir

    # Log warning if not found
    print(f"Warning: Could not find Claude logs for {project_path}")
    return None
```

**Acceptance Criteria:**
- [ ] Multiple encoding strategies tried
- [ ] Warning logged if no match found
- [ ] Document actual Claude Code encoding if discovered

---

### Task 3.7: Track Test Files in Git
**Audit Issue:** #32
**Priority:** Medium
**Files:**
- `test_project_data.py`
- `test_sessions.py`
- `test_e2e.py`
- `test_tmux.py`
- `test_tmux_logging.py`

**Problem:**
Test files shown as untracked in git status.

**Solution:**
```bash
git add test_*.py
git commit -m "chore: track test files in git"
```

**Acceptance Criteria:**
- [ ] All test files tracked
- [ ] Tests pass in CI

---

## Phase 4: Documentation

**Priority:** Low
**Estimated scope:** 6 tasks

### Task 4.1: Fix Incorrect Default Value in CLAUDE.md
**Audit Issue:** #18
**Files:** `CLAUDE.md`

**Change:**
```markdown
# Before
scan_interval: 5          # Refresh interval in seconds

# After
scan_interval: 2          # Refresh interval in seconds (default)
```

---

### Task 4.2: Add Missing API Endpoints to CLAUDE.md
**Audit Issue:** #19
**Files:** `CLAUDE.md`

**Add to API Endpoints table:**

| Route | Method | Description |
|-------|--------|-------------|
| `/api/logs/tmux/debug` | GET | Get tmux debug logging state |
| `/api/logs/tmux/debug` | POST | Set tmux debug logging state |
| `/api/session/<id>/summarise` | POST | Manually trigger session summarization |
| `/api/project/<name>/roadmap` | GET | Get project roadmap |
| `/api/project/<name>/roadmap` | POST | Update project roadmap |
| `/api/project/<permalink>/brain-refresh` | GET | Get brain reboot briefing |
| `/api/headspace/history` | GET | Get headspace history |
| `/api/reset` | POST | Reset all working state |

---

### Task 4.3: Update Key Functions Table in CLAUDE.md
**Audit Issue:** #20
**Files:** `CLAUDE.md`

**Add to Key Functions table:**

| Function | Purpose |
|----------|---------|
| `track_turn_cycle()` | Track user command → Claude response cycle (tmux only) |
| `compute_priorities()` | Calculate AI-ranked session priorities |
| `aggregate_priority_context()` | Gather context for prioritization prompt |
| `call_openrouter()` | Make API call to OpenRouter |

---

### Task 4.4: Document Data Directory Structure in CLAUDE.md
**Audit Issue:** #21
**Files:** `CLAUDE.md`

**Update Directory Structure section:**

```markdown
├── data/
│   ├── projects/           # Project YAML data files
│   │   └── <project>.yaml
│   ├── logs/               # Application logs
│   │   ├── openrouter.jsonl  # OpenRouter API call logs
│   │   └── tmux.jsonl        # tmux session message logs
│   ├── headspace.yaml      # Current focus and constraints
│   └── session_state.yaml  # Persisted session tracking (new)
```

---

### Task 4.5: Document Notification Configuration in CLAUDE.md
**Audit Issue:** #22
**Files:** `CLAUDE.md`

**Add to Notes section:**

```markdown
### Notifications

Notifications require `terminal-notifier` installed via Homebrew:
```bash
brew install terminal-notifier
```

Notifications can be enabled/disabled via:
- **API:** `POST /api/notifications` with `{"enabled": true/false}`
- **Dashboard:** Toggle in settings panel
```

---

### Task 4.6: Fix Config Key Name in PRD
**Audit Issue:** #23
**Files:** `docs/prds/tmux/done/tmux-session-logging-prd.md`

**Change:**
```markdown
# Before
FR1: Configuration option `debug_tmux_logging: true|false`

# After
FR1: Configuration option `tmux_logging.debug_enabled: true|false`
```

---

## Implementation Notes

### Recommended Implementation Order

```
Phase 1 (Critical) - Do first, in order:
├── Task 1.3: Config default (quick win)
├── Task 1.4: API key to .env (security)
├── Task 1.5: Rate limiting (stability)
├── Task 1.1: Cache side effects (correctness)
└── Task 1.2: Session persistence (reliability)

Phase 2 (Architecture) - After Phase 1:
├── Task 2.1: Event-driven priorities (biggest change)
├── Task 2.2: Exponential backoff
├── Task 2.5: Consolidate state tracking
├── Task 2.6: Cleanup stale data
├── Task 2.3: Standardize session_id
└── Task 2.4: Compression rollback

Phase 3 (Cleanup) - After Phase 2:
├── Task 3.1: Remove legacy code
├── Task 3.2: PRD deprecation
├── Task 3.3: Remove soft transitions
├── Task 3.4: Naming collision
├── Task 3.5: Log rotation
├── Task 3.6: Path encoding
└── Task 3.7: Track test files

Phase 4 (Documentation) - Can run in parallel:
└── Tasks 4.1-4.6: Documentation updates
```

### Dependencies

```
Task 2.5 (consolidate state) should precede Task 2.6 (cleanup state)
Task 1.1 (cache fix) should precede Task 2.1 (event-driven)
Task 3.1 (remove legacy) should precede Task 3.3 (remove soft transitions)
```

### Breaking Changes

| Task | Breaking Change | Migration |
|------|-----------------|-----------|
| 1.4 | API key location | Add .env file with key |
| 2.1 | Remove polling_interval | Remove from config.yaml |
| 2.3 | session_id format | Update any external integrations |

---

## Testing Requirements

### Unit Tests Required

| Task | Test Coverage |
|------|---------------|
| 1.1 | `test_cache_validation_idempotent()` |
| 1.2 | `test_session_persistence_across_restart()` |
| 1.5 | `test_rate_limiting_between_calls()` |
| 2.2 | `test_exponential_backoff_delays()` |
| 2.4 | `test_compression_rollback()` |
| 3.4 | `test_session_name_collision()` |
| 3.5 | `test_log_rotation()` |

### Integration Tests Required

| Task | Test Coverage |
|------|---------------|
| 2.1 | `test_priorities_refresh_on_turn_complete()` |
| 2.1 | `test_priorities_refresh_on_headspace_update()` |

### Manual Testing Checklist

- [ ] Server starts with empty config.yaml
- [ ] Server starts with .env API key only
- [ ] Sessions survive server restart
- [ ] Priorities refresh when turn completes
- [ ] Priorities refresh when headspace updated
- [ ] Logs rotate at 10MB
- [ ] tmux and iTerm sessions both work

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Author | Code Review Agent | 2026-01-24 | ✓ |
| Reviewer | | | |
| Approver | | | |

---

*End of Remediation Plan*
