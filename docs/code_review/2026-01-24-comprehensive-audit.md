# Comprehensive Code Audit Report

**Application:** Claude Monitor (Claude Headspace)
**Date:** 2026-01-24
**Auditor:** Code Review Agent
**Version:** Development branch (commit f73cf82)

---

## Executive Summary

This audit covers the core requirements:
- Per-turn logging (atomic unit: user command → Claude response)
- OpenRouter API call management and logging
- Configuration parameters
- History and compaction
- Documentation consistency

**Total Issues Found: 34**

| Priority | Count | Description |
|----------|-------|-------------|
| Critical | 4 | Fundamental implementation gaps |
| High | 8 | Significant deviations from spec |
| Medium | 12 | Inconsistencies and bugs |
| Low | 10 | Documentation and minor issues |

---

## Table of Contents

1. [Turn-Based Logging Audit](#1-turn-based-logging-audit)
2. [OpenRouter API Call Audit](#2-openrouter-api-call-audit)
3. [Configuration Parameter Audit](#3-configuration-parameter-audit)
4. [History and Compaction Audit](#4-history-and-compaction-audit)
5. [Documentation Audit](#5-documentation-audit)
6. [Additional Issues](#6-additional-issues)
7. [Priority Matrix](#7-priority-matrix)
8. [Recommended Remediation Order](#8-recommended-remediation-order)

---

## 1. Turn-Based Logging Audit

### 1.1 Implementation Overview

Turn tracking is implemented in `lib/sessions.py` via `track_turn_cycle()`. Each turn (user command → Claude response) is logged as a pair:

- `turn_start` (direction=out) when processing begins
- `turn_complete` (direction=in) when processing ends

Both entries share a `correlation_id` = `turn_id` for linking.

**Key Files:**
- `lib/sessions.py` - Turn cycle tracking logic
- `lib/tmux_logging.py` - JSONL log entry creation and storage
- `data/logs/tmux.jsonl` - Turn log storage

### 1.2 Issues Found

#### ISSUE #1: Turn tracking only works for tmux-first sessions
**Priority:** Critical
**Location:** `lib/sessions.py:610`

`track_turn_cycle()` is ONLY called from `scan_backend_session()` (the new tmux-first approach).

**NOT called from:**
- `scan_tmux_session()` (legacy state-file approach, lines 666-748)
- `scan_iterm_session()` (lines 751-832)

**Impact:** Legacy session types don't get turn tracking at all.

**Evidence:**
```python
# lib/sessions.py:610 - only place track_turn_cycle is called
track_turn_cycle(session_name, session_name, activity_state, content_tail)
```

---

#### ISSUE #2: Turn logging bypasses debug toggle
**Priority:** Medium
**Location:** `lib/sessions.py:309, 345`

Turn events use `debug_enabled=True` hardcoded, ignoring `tmux_logging.debug_enabled` config.

```python
# lib/sessions.py:309
entry = create_tmux_log_entry(
    ...
    debug_enabled=True,  # Always log turn data
)
```

Comment says "Always log turn data" but this is undocumented behavior.

**Impact:** Turn data floods logs even when debug mode is off.

---

#### ISSUE #3: Duplicate `_previous_activity_states` tracking
**Priority:** Medium
**Location:** `lib/sessions.py:67` and `lib/headspace.py:40`

Two separate dicts tracking the same concept:
- `sessions.py` uses session_id (tmux session name)
- `headspace.py` uses PID-based session_id

```python
# lib/sessions.py:67
_previous_activity_states: dict[str, str] = {}

# lib/headspace.py:40
_previous_activity_states: dict[str, str] = {}
```

**Impact:** Potential state divergence, confusing code.

---

#### ISSUE #4: No cleanup of stale turn tracking data
**Priority:** Low
**Location:** `lib/sessions.py:56-67`

The following dicts are never cleaned when sessions end:
- `_turn_tracking`
- `_last_completed_turn`
- `_session_activity_cache`

**Impact:** Memory leak during long-running server, stale data accumulation.

---

## 2. OpenRouter API Call Audit

### 2.1 Current Call Points

| Caller | Location | Purpose |
|--------|----------|---------|
| Compression | `lib/compression.py:386` | History summarization |
| Priorities | `monitor.py:740` | AI session ranking |

Both properly use the `caller` parameter for logging attribution.

### 2.2 Issues Found

#### ISSUE #5: Cache validation has side effects
**Priority:** Critical
**Location:** `lib/headspace.py:359-406`

`should_refresh_priorities()` modifies `_previous_activity_states` as a side effect (line 406).

**Call chain:**
```
compute_priorities()
  → get_cached_priorities(sessions)
    → is_cache_valid(sessions)
      → should_refresh_priorities(sessions)  # Mutates state!
```

```python
# lib/headspace.py:406
_previous_activity_states = current_states  # Side effect!
```

**Impact:** Calling `is_cache_valid()` twice returns different results; may cause unnecessary API calls.

---

#### ISSUE #6: No rate limiting between compression calls
**Priority:** High
**Location:** `lib/compression.py:414-455`

`process_compression_queue()` processes all pending sessions sequentially with no delay or throttle between consecutive API calls.

```python
# lib/compression.py:428-432
for session in pending:
    session_id = session.get("session_id", "unknown")
    retry_count = session.get("retry_count", 0)
    success, error = compress_session(project_name, session)  # No delay
```

**Impact:** Could hit OpenRouter rate limits if many sessions need compression simultaneously.

---

#### ISSUE #7: Compression retry doesn't implement exponential backoff
**Priority:** High
**Location:** `lib/compression.py:28, 398-411`

```python
# lib/compression.py:28
RETRY_DELAYS = [60, 300, 1800]  # Defined but never used!

# lib/compression.py:442
_increment_retry_count(project_name, session_id)  # Only increments count
```

Code only increments `retry_count` and retries on next cycle (fixed interval).

**Impact:** Violates PRD FR18 "Retry attempts use exponential backoff (e.g., 1min, 5min, 30min)".

---

## 3. Configuration Parameter Audit

### 3.1 Expected vs Actual Configuration

| Parameter | DEFAULT_CONFIG | config.yaml | PRD Spec | Status |
|-----------|----------------|-------------|----------|--------|
| `scan_interval` | 2 | 4 | - | Mismatch with CLAUDE.md (says 5) |
| `compression_interval` | 300 | 3600 | 300 | config.yaml uses 1hr not 5min |
| `tmux_logging.debug_enabled` | **MISSING** | true | - | No default if config missing |
| `priorities.polling_interval` | 60 | 60 | 60 | OK but misleading |

### 3.2 Issues Found

#### ISSUE #8: `tmux_logging.debug_enabled` has no default
**Priority:** Medium
**Location:** `config.py:14-39`

The `tmux_logging` section is not in DEFAULT_CONFIG:

```python
# config.py - DEFAULT_CONFIG does not include:
# "tmux_logging": {
#     "debug_enabled": False,
# }
```

**Impact:** If config.yaml is missing or incomplete, debug logging behavior is undefined.

---

#### ISSUE #9: `priorities.polling_interval` is misleading
**Priority:** Medium
**Location:** `config.py:29-33`

This implies backend polling, but priorities are computed on-demand via `/api/priorities`. Frontend JavaScript does the polling, not the backend.

**Impact:** Configuration documentation is confusing.

---

#### ISSUE #10: Many settings don't hot-reload
**Priority:** High
**Location:** Various

PRD FR32 claims "Configuration changes take effect without application restart".

**This is FALSE for:**
- `tmux_logging.debug_enabled` (requires API call or restart)
- `session_sync.interval` (read only at thread start)
- Project list changes

**Impact:** User expectation mismatch.

---

#### ISSUE #11: OpenRouter API key in config.yaml
**Priority:** Medium
**Location:** `config.yaml:15`

API key `sk-or-v1-...` is hardcoded in the file. While gitignored, this is a security risk if the .gitignore is modified.

**Impact:** Potential API key exposure.

---

## 4. History and Compaction Audit

### 4.1 Process Flow

```
Session ends
  → session_sync detects (_perform_sync_cycle)
    → _handle_session_end()
      → process_session_end()
        → summarise_session()
        → add_recent_session()
          → FIFO removes old (>5)
            → add_to_compression_queue()
              → background thread
                → call_openrouter()
                  → update_project_history()
```

### 4.2 Issues Found

#### ISSUE #12: `pending_compressions` field undocumented
**Priority:** Medium
**Location:** `lib/compression.py:40-71`

This field is stored in project YAML but not documented in CLAUDE.md or PRDs.

```python
# Stored in data/projects/<name>.yaml but undocumented
project_data["pending_compressions"] = []
```

**Impact:** Hidden implementation detail, confusing for maintainers.

---

#### ISSUE #13: Exponential backoff not implemented (compression)
**Priority:** High
**Location:** `lib/compression.py:398-455`

Same as Issue #7. Sessions retry on next cycle (5 min default) regardless of retry count.

**Impact:** Failed compressions hammer the API every cycle.

---

#### ISSUE #14: No compression rollback mechanism
**Priority:** High
**Location:** `lib/compression.py:144-163`

```python
# lib/compression.py:158-161
project_data["history"] = {
    "summary": summary,  # Overwrites with no backup
    "last_compressed_at": datetime.now(timezone.utc).isoformat()
}
```

**Impact:** Bad AI output permanently corrupts history.

---

#### ISSUE #15: Session tracking lost on restart
**Priority:** Critical
**Location:** `lib/session_sync.py:73`

```python
_known_sessions: Dict[str, KnownSession] = {}  # In-memory only
```

On restart, all active sessions appear as "new".

**Impact:** No session ended = no summarization for interrupted sessions.

---

#### ISSUE #16: Path encoding may not match Claude Code
**Priority:** Medium
**Location:** `lib/summarization.py:90-106`

```python
def encode_project_path(project_path: str) -> str:
    encoded = str(path).replace("/", "-").replace("_", "-")
    return encoded
```

If Claude Code uses different encoding, JSONL files won't be found.

**Impact:** Session summarization may fail silently.

---

#### ISSUE #17: Headspace history appears empty
**Priority:** Medium
**Location:** `data/headspace.yaml`

File contains only 4 lines: current_focus, constraints, updated_at. No `history` array despite `history_enabled: true` in config.

**Impact:** History feature may not be working or was cleared.

---

## 5. Documentation Audit

### 5.1 CLAUDE.md Issues

#### ISSUE #18: Incorrect default value
**Priority:** Low
**Location:** CLAUDE.md

CLAUDE.md says `scan_interval: 5` but DEFAULT_CONFIG has `scan_interval: 2`.

---

#### ISSUE #19: Missing API endpoints
**Priority:** Low
**Location:** CLAUDE.md API Endpoints table

**Undocumented endpoints:**
- `GET/POST /api/logs/tmux/debug`
- `POST /api/session/<id>/summarise`
- `GET/POST /api/project/<name>/roadmap`
- `GET /api/project/<permalink>/brain-refresh`
- `GET /api/headspace/history`
- `POST /api/reset`

---

#### ISSUE #20: Incomplete Key Functions table
**Priority:** Low
**Location:** CLAUDE.md Key Functions section

**Missing critical functions:**
- `track_turn_cycle()`
- `compute_priorities()`
- `aggregate_priority_context()`
- `call_openrouter()`

---

#### ISSUE #21: Missing data directory entries
**Priority:** Low
**Location:** CLAUDE.md Directory Structure section

**Not documented:**
- `data/logs/` (openrouter.jsonl, tmux.jsonl)
- `data/headspace.yaml`

---

#### ISSUE #22: Notifications config not documented
**Priority:** Low
**Location:** CLAUDE.md

Says "Require terminal-notifier" but doesn't mention config/API toggle.

---

### 5.2 PRD vs Implementation Discrepancies

#### ISSUE #23: Wrong config key name
**Priority:** Medium
**Location:** `tmux-session-logging-prd.md` FR1

PRD says: `debug_tmux_logging: true|false`
Actual: `tmux_logging.debug_enabled` (nested)

---

#### ISSUE #24: Soft transitions NOT implemented
**Priority:** Critical
**Location:** `e1_s7_ai-prioritisation-prd.md` FR26-27

PRD specifies delaying reordering while sessions process.

```python
# lib/headspace.py:617-626 - EXISTS but NEVER CALLED
def is_any_session_processing(sessions: list[dict]) -> bool:
    return any(s.get("activity_state") == "processing" for s in sessions)
```

**Impact:** PRD requirement not fulfilled.

---

#### ISSUE #25: Missing response field
**Priority:** Medium
**Location:** `e1_s7_ai-prioritisation-prd.md` FR28

PRD: "API response indicates if a soft transition is pending"
Actual: `/api/priorities` response has no such field.

**Impact:** Frontend cannot show pending state.

---

#### ISSUE #26: Inconsistent commands_run type
**Priority:** Medium
**Location:** `e1_s3_session-summarisation-prd.md` FR16

PRD says `commands_run (count)` but code sometimes uses int, sometimes list structure.

**Impact:** API consumers may encounter type mismatches.

---

## 6. Additional Issues

### 6.1 Dead Code

#### ISSUE #27: Unused session scanning functions
**Priority:** High
**Location:** `lib/sessions.py:666-832`

`scan_tmux_session()` and `scan_iterm_session()` exist but are never called. `scan_sessions()` only uses `scan_backend_session()`.

**Impact:** Code maintenance burden, confusion.

---

#### ISSUE #28: Missing function reference
**Priority:** High
**Location:** `lib/sessions.py:774`

`is_claude_process()` is called but not defined in sessions.py. Must be in another file (likely iterm.py), but import is missing.

**Impact:** Potential runtime error if iTerm code path is taken.

---

### 6.2 Missing Functionality

#### ISSUE #29: No manual compression trigger
**Priority:** Low
**Location:** API layer

No API endpoint to manually trigger compression. Only triggered automatically by session end.

---

#### ISSUE #30: No compression queue management API
**Priority:** Low
**Location:** API layer

Cannot view or manage pending compressions via API. Must manually edit project YAML files.

---

#### ISSUE #31: No log rotation
**Priority:** Low
**Location:** `lib/logging.py`, `lib/tmux_logging.py`

`openrouter.jsonl` and `tmux.jsonl` grow indefinitely. No cleanup mechanism exists.

**Impact:** Disk space exhaustion over time.

---

### 6.3 Test Coverage

#### ISSUE #32: Test files untracked
**Priority:** Low
**Location:** Git working directory

Git status shows test files as `??` (untracked):
- `test_project_data.py`
- `test_sessions.py`
- `test_e2e.py`

**Impact:** CI/CD may not run tests, coverage unknown.

---

### 6.4 API Consistency

#### ISSUE #33: Inconsistent session_id formats
**Priority:** High
**Location:** Various API endpoints

| Endpoint | session_id format |
|----------|-------------------|
| `/api/session/<session_id>/summarise` | UUID |
| `/api/focus/<pid>` | PID |
| `/api/priorities` response | PID |
| `/api/send/<session_id>` | UUID or uuid_short |

**Impact:** API consumer confusion.

---

#### ISSUE #34: tmux session naming collision risk
**Priority:** Medium
**Location:** `lib/tmux.py:442-461`

```python
def slugify_project_name(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    # "My Project" and "my-project" both become "my-project"
```

**Impact:** Session collision possible for similarly-named projects.

---

## 7. Priority Matrix

### Critical (Must Fix Immediately)

| Issue | Description | Location |
|-------|-------------|----------|
| #1 | Turn tracking only works for tmux-first sessions | `lib/sessions.py:610` |
| #5 | Cache validation has side effects | `lib/headspace.py:359-406` |
| #15 | Session tracking lost on restart | `lib/session_sync.py:73` |
| #24 | Soft transitions NOT implemented | `lib/headspace.py` |

### High Priority

| Issue | Description | Location |
|-------|-------------|----------|
| #6 | No rate limiting between compression calls | `lib/compression.py:414-455` |
| #7 | Compression retry doesn't implement backoff | `lib/compression.py:28` |
| #10 | Many settings don't hot-reload | Various |
| #13 | Exponential backoff not implemented | `lib/compression.py` |
| #14 | No compression rollback mechanism | `lib/compression.py:144-163` |
| #27 | Unused session scanning functions | `lib/sessions.py:666-832` |
| #28 | Missing function reference | `lib/sessions.py:774` |
| #33 | Inconsistent session_id formats | API layer |

### Medium Priority

| Issue | Description | Location |
|-------|-------------|----------|
| #2 | Turn logging bypasses debug toggle | `lib/sessions.py:309, 345` |
| #3 | Duplicate state tracking | `lib/sessions.py:67`, `lib/headspace.py:40` |
| #8 | Missing default for debug_enabled | `config.py` |
| #9 | Misleading polling_interval | `config.py:29-33` |
| #11 | API key in config.yaml | `config.yaml:15` |
| #12 | Undocumented pending_compressions | `lib/compression.py` |
| #16 | Path encoding mismatch risk | `lib/summarization.py:90-106` |
| #17 | Empty headspace history | `data/headspace.yaml` |
| #23 | Wrong config key name in PRD | PRD vs implementation |
| #25 | Missing soft_transition_pending field | API response |
| #26 | Inconsistent commands_run type | Session data |
| #34 | Session naming collision risk | `lib/tmux.py:442-461` |

### Low Priority

| Issue | Description | Location |
|-------|-------------|----------|
| #4 | No cleanup of stale tracking data | `lib/sessions.py:56-67` |
| #18 | Incorrect default in CLAUDE.md | CLAUDE.md |
| #19 | Missing API endpoints in docs | CLAUDE.md |
| #20 | Incomplete Key Functions table | CLAUDE.md |
| #21 | Missing data directory entries | CLAUDE.md |
| #22 | Notifications config not documented | CLAUDE.md |
| #29 | No manual compression trigger | API layer |
| #30 | No compression queue management API | API layer |
| #31 | No log rotation | Logging modules |
| #32 | Test files untracked | Git |

---

## 8. Recommended Remediation Order

### Phase 1: Critical Path (Must Fix)

1. **#1: Unify turn tracking across all session types**
   - Add `track_turn_cycle()` call to `scan_tmux_session()` and `scan_iterm_session()`
   - Or remove legacy functions if truly deprecated

2. **#24: Implement soft transitions per PRD**
   - Call `is_any_session_processing()` in `compute_priorities()`
   - Add `soft_transition_pending` to API response

3. **#15: Persist known sessions across restart**
   - Save `_known_sessions` to disk or use session state files
   - Restore on startup

4. **#5: Fix cache validation side effects**
   - Separate state tracking from cache validation
   - Or make `should_refresh_priorities()` idempotent

### Phase 2: High Priority

5. **#7/#13: Implement actual exponential backoff**
   - Use `RETRY_DELAYS` array
   - Track `last_retry_at` and compare against delays

6. **#27: Remove dead code**
   - Delete `scan_tmux_session()` and `scan_iterm_session()` if unused
   - Or document why they exist

7. **#33: Standardize session_id format in API**
   - Pick one format (recommend UUID)
   - Document in CLAUDE.md

8. **#28: Fix missing import**
   - Add `from lib.iterm import is_claude_process` or define locally

### Phase 3: Technical Debt

9. **#3: Consolidate duplicate state tracking**
   - Use single source of truth for `_previous_activity_states`

10. **#31: Implement log rotation**
    - Add max file size or entry count
    - Archive old logs

11. **#10: Document hot-reload limitations**
    - Update CLAUDE.md with accurate behavior
    - Consider implementing hot-reload for critical settings

### Phase 4: Documentation

12. **#18-22: Update CLAUDE.md**
    - Correct default values
    - Add missing endpoints
    - Add missing functions
    - Document data directory

13. **#23-26: Align implementation with PRD**
    - Either implement missing features
    - Or update PRD to reflect actual behavior

---

## Appendix: Files Reviewed

| File | Lines | Purpose |
|------|-------|---------|
| `monitor.py` | 1075 | Main Flask application |
| `config.py` | 70 | Configuration management |
| `lib/sessions.py` | 1110 | Session scanning, turn tracking |
| `lib/compression.py` | 521 | History compression, OpenRouter |
| `lib/headspace.py` | 687 | Headspace, priorities |
| `lib/tmux_logging.py` | 411 | Turn logging to JSONL |
| `lib/tmux.py` | 474 | tmux integration |
| `lib/summarization.py` | 603 | Session summarization |
| `lib/session_sync.py` | 523 | Background sync thread |
| `lib/logging.py` | 239 | OpenRouter logging |
| `config.yaml` | 27 | User configuration |
| `CLAUDE.md` | ~400 | Project documentation |
| PRDs | Various | Specifications |

---

*End of Audit Report*
