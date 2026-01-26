# Migration Plan: lib/ to src/ Architecture

**Status:** In Progress (Phase 1 Complete)
**Created:** 2026-01-26
**Task:** #27 - Complete migration from lib/ to src/ architecture

---

## Executive Summary

The Claude Headspace codebase has two parallel architectures:
- **lib/** (legacy): ~6,310 lines across 18 files - deprecated but still used
- **src/** (new): ~5,063 lines across 34 files - recommended, ~80% complete

This plan details the systematic migration of remaining lib/ functionality to src/ to achieve a single, maintainable architecture.

**Critical Blocker:** `src/routes/logging.py` still imports from lib/ modules.

**Estimated Effort:** 13-18 days across 6 phases

---

## Current State Analysis

### lib/ Files and Status

| File | Lines | Purpose | Migration Status |
|------|-------|---------|------------------|
| `lib/sessions.py` | 1,332 | Session scanning, activity state, turn tracking | **CRITICAL** - partially migrated |
| `lib/headspace.py` | 780 | Focus management, priorities caching | **CRITICAL** - mostly migrated |
| `lib/logging.py` | 282 | OpenRouter API call logging | **ACTIVE** - not migrated |
| `lib/terminal_logging.py` | 547 | Terminal session message logging | **ACTIVE** - not migrated |
| `lib/projects.py` | 643 | Project YAML, roadmap, CLAUDE.md parsing | **ACTIVE** - partially migrated |
| `lib/compression.py` | 584 | History compression, queue management | **ACTIVE** - not migrated |
| `lib/session_sync.py` | 661 | Background sync, context extraction | **ACTIVE** - not migrated |
| `lib/summarization.py` | 614 | JSONL parsing, content preparation | **ACTIVE** - not migrated |
| `lib/notifications.py` | 243 | macOS notifications | MIGRATED to `src/services/notification_service.py` |
| `lib/sse.py` | 91 | SSE broadcasting | MIGRATED to `src/services/event_bus.py` |
| `lib/backends/*.py` | ~1,668 | Terminal backends | MIGRATED to `src/backends/` |
| `lib/iterm.py` | 165 | iTerm window focusing | DEPRECATED |
| `lib/tmux.py` | 49 | Forwarding shim | DEPRECATED |
| `lib/help.py` | 279 | Help documentation | LEGACY - can deprecate |

### src/ Architecture Already Complete

- **Models:** Pydantic v2 models with validation (agent, task, turn, headspace, project, config, inference)
- **Services:** agent_store, state_interpreter, task_state_machine, governing_agent, inference_service, config_service, hook_receiver, notification_service, priority_service, event_bus, git_analyzer
- **Backends:** tmux, wezterm (simplified from lib/)
- **Routes:** agents, tasks, events, hooks, headspace, notifications, projects, priorities, logging*

*logging route still imports from lib/

---

## Dependency Graph

### Critical src/ → lib/ Dependencies

```
src/routes/logging.py
  ├── lib/logging.py (OpenRouter log reading)
  ├── lib/terminal_logging.py (turn log reading)
  └── lib/tmux.py (debug logging flags)
```

### lib/ → lib/ Internal Dependencies

```
sessions.py
  ├── headspace.py (priorities invalidation)
  ├── terminal_logging.py (turn logging)
  ├── iterm.py (window focus)
  ├── summarization.py (content prep)
  └── backends/wezterm.py (capture)

compression.py
  ├── projects.py (load/save)
  └── logging.py (API log writing)

session_sync.py
  ├── projects.py (state updates)
  ├── sessions.py (cleanup)
  ├── summarization.py (JSONL parsing)
  └── compression.py (queue)

headspace.py
  ├── projects.py (roadmaps)
  └── sessions.py (activity states)
```

---

## Migration Phases

### Phase 1: Logging Infrastructure (Blocks all other phases)

**Goal:** Remove all lib/ imports from src/routes/logging.py

**Deliverables:**
1. `src/services/logging_service.py` - OpenRouter API call logging
2. `src/services/terminal_logging_service.py` - Terminal session message logging

**Tasks:**
- [x] Create `src/services/logging_service.py`
  - [x] `read_openrouter_logs(limit, offset)` - Read JSONL log entries
  - [x] `get_logs_since(timestamp)` - Get logs after timestamp
  - [x] `search_logs(query, filters)` - Search log content
  - [x] `get_log_stats()` - Aggregate statistics
  - [x] `write_log_entry(entry)` - Write new log entry

- [x] Create `src/services/terminal_logging_service.py`
  - [x] `create_terminal_log_entry(...)` - Create structured log entry
  - [x] `write_terminal_log_entry(entry)` - Write to JSONL
  - [x] `get_turn_entries(turn_id)` - Get entries by correlation_id
  - [x] `get_session_entries(session_id, limit)` - Get session history
  - [x] `rotate_log_file()` - Handle log rotation

- [x] Create `src/models/log_entry.py` (Pydantic models)
  - [x] `OpenRouterLogEntry` model
  - [x] `TerminalLogEntry` model
  - [x] `LogStats` model

- [x] Update `src/routes/logging.py`
  - [x] Replace `from lib.logging import ...`
  - [x] Replace `from lib.terminal_logging import ...`
  - [x] Replace `from lib.tmux import get_debug_logging, set_debug_logging`

- [x] Add debug logging flags to `src/services/config_service.py`

**Tests:**
- [x] Unit tests for logging_service.py (22 tests)
- [x] Unit tests for terminal_logging_service.py (30 tests)
- [x] Integration tests for logging routes (existing tests pass)

**Effort:** 3-4 days

---

### Phase 2: Turn Cycle & Activity Tracking

**Goal:** Move turn cycle and activity state logic from lib/sessions.py to src/

**Deliverables:**
1. Enhanced `src/services/state_interpreter.py`
2. Turn tracking in `src/services/agent_store.py` or new service

**Tasks:**
- [ ] Migrate turn cycle tracking from `lib/sessions.py`
  - [ ] `TurnState` dataclass → Pydantic model
  - [ ] `track_turn_cycle()` → service method
  - [ ] `_turn_tracking` dict → agent_store integration
  - [ ] `_last_completed_turn` dict → task history

- [ ] Migrate activity state tracking
  - [ ] `_previous_activity_states` → agent_store or state_interpreter
  - [ ] `get_previous_activity_state()` → service method
  - [ ] `cleanup_stale_session_data()` → agent_store method

- [ ] Migrate Enter signal handling
  - [ ] `record_enter_signal()` → hook_receiver integration
  - [ ] `consume_enter_signal()` → state_interpreter

- [ ] Update `src/services/hook_receiver.py`
  - [ ] Use new turn tracking service
  - [ ] Remove any lib/ dependencies

**Tests:**
- [ ] Turn cycle transition tests
- [ ] Activity state detection tests
- [ ] Enter signal handling tests

**Effort:** 2-3 days

---

### Phase 3: Background Processing Services

**Goal:** Port compression and session sync background workers to src/

**Deliverables:**
1. `src/services/compression_service.py`
2. `src/services/session_sync_service.py`
3. `src/services/summarization_service.py`

**Tasks:**
- [ ] Create `src/services/summarization_service.py` (needed by others)
  - [ ] `parse_jsonl_session(path)` - Parse session JSONL logs
  - [ ] `extract_activities(logs)` - Extract files, commands, errors
  - [ ] `prepare_content_for_summary(content)` - Clean for AI
  - [ ] `extract_last_message(content)` - Get last Claude message

- [ ] Create `src/services/compression_service.py`
  - [ ] `CompressionQueue` class with thread-safe queue
  - [ ] `compress_session_history(session_id)` - OpenRouter API call
  - [ ] `_worker_thread()` - Background processing
  - [ ] `start()`/`stop()` - Worker lifecycle
  - [ ] Integration with inference_service for API calls

- [ ] Create `src/services/session_sync_service.py`
  - [ ] `SessionSyncService` class
  - [ ] `_sync_loop()` - Periodic sync background thread
  - [ ] `extract_live_context(session_id)` - From JSONL logs
  - [ ] `detect_session_end(session_id)` - Completion detection
  - [ ] `update_project_state(project_id, context)` - State updates
  - [ ] Integration with agent_store, compression_service

- [ ] Update `src/app.py`
  - [ ] Initialize compression_service
  - [ ] Initialize session_sync_service
  - [ ] Add to `start_background_tasks()`

- [ ] Create Pydantic models
  - [ ] `CompressionJob` model
  - [ ] `SessionContext` model
  - [ ] `ActivitySummary` model

**Tests:**
- [ ] Summarization function tests
- [ ] Compression queue tests
- [ ] Session sync worker tests
- [ ] Integration tests with mock API

**Effort:** 4-5 days

---

### Phase 4: Supporting Features

**Goal:** Migrate remaining lib/ functionality

**Deliverables:**
1. Complete project management in src/
2. Validated notification/SSE migrations

**Tasks:**
- [ ] Audit `lib/projects.py` vs `src/models/project.py`
  - [ ] Roadmap validation/normalization
  - [ ] CLAUDE.md parsing
  - [ ] Brain reboot briefing generation
  - [ ] Project YAML CRUD (if not in agent_store)

- [ ] Migrate missing project functions to `src/services/`
  - [ ] Consider `src/services/project_service.py` if needed
  - [ ] Or extend agent_store with project operations

- [ ] Validate notification migration
  - [ ] Compare `lib/notifications.py` vs `src/services/notification_service.py`
  - [ ] Ensure all features ported
  - [ ] Remove any lib/ dependencies

- [ ] Validate SSE migration
  - [ ] Compare `lib/sse.py` vs `src/services/event_bus.py`
  - [ ] Ensure all event types supported
  - [ ] Remove any lib/ dependencies

- [ ] Audit `lib/headspace.py` vs `src/models/headspace.py` + `priority_service.py`
  - [ ] Priorities caching
  - [ ] History tracking
  - [ ] Focus updates

**Tests:**
- [ ] Project management tests
- [ ] Notification comparison tests
- [ ] SSE event tests

**Effort:** 2-3 days

---

### Phase 5: Terminal Backend Audit

**Goal:** Ensure src/backends/ has full feature parity with lib/backends/

**Tasks:**
- [ ] Compare `lib/backends/base.py` vs `src/backends/base.py`
  - [ ] SessionInfo fields
  - [ ] TerminalBackend interface methods

- [ ] Compare `lib/backends/tmux.py` vs `src/backends/tmux.py`
  - [ ] list_sessions()
  - [ ] get_session_info()
  - [ ] capture_pane()
  - [ ] send_text()
  - [ ] create_session()
  - [ ] ANSI/escape handling

- [ ] Compare `lib/backends/wezterm.py` vs `src/backends/wezterm.py`
  - [ ] All operations
  - [ ] HTTP protocol handling
  - [ ] Session lookup by name

- [ ] Remove `lib/iterm.py` dependency
  - [ ] If focus needed: add to backend interface
  - [ ] WezTerm has native focus via CLI
  - [ ] tmux focus via attach or send-keys

- [ ] Update any backend callers to use src/ only

**Tests:**
- [ ] Backend operation tests
- [ ] Session lifecycle tests
- [ ] Cross-backend consistency tests

**Effort:** 1-2 days

---

### Phase 6: Cleanup & Deprecation

**Goal:** Remove lib/ from production code path

**Tasks:**
- [ ] Audit all src/ files for lib/ imports
  ```bash
  grep -r "from lib" src/ --include="*.py"
  grep -r "import lib" src/ --include="*.py"
  ```

- [ ] Update entry points
  - [ ] `run.py` - ensure only src/ services
  - [ ] `monitor.py` - add deprecation warning or remove

- [ ] Add deprecation warnings to lib/
  - [ ] Update `lib/__init__.py` warnings
  - [ ] Add warnings to actively-used modules

- [ ] Update documentation
  - [ ] CLAUDE.md - mark lib/ as deprecated
  - [ ] README.md - update architecture section

- [ ] Run full test suite
  - [ ] Ensure 450+ tests pass
  - [ ] Verify 70%+ coverage
  - [ ] No lib/ imports in src/

- [ ] Optional: Archive lib/
  - [ ] Move to `archive/lib/` for reference
  - [ ] Or keep with clear deprecation markers

**Effort:** 1 day

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Background worker bugs | Medium | High | Extensive testing, gradual rollout |
| JSONL parsing edge cases | Medium | Medium | Port existing tests, add fuzzing |
| State tracking race conditions | Medium | High | Thread-safe design, lock auditing |
| API compatibility breaks | Low | High | Version routes if needed |
| Test coverage gaps | Medium | Medium | Coverage enforcement, CI checks |

---

## Success Criteria

1. **Zero lib/ imports in src/**
   ```bash
   grep -r "from lib" src/ --include="*.py" | wc -l
   # Expected: 0
   ```

2. **All tests passing**
   ```bash
   pytest
   # Expected: 450+ tests, 0 failures
   ```

3. **Coverage maintained**
   ```bash
   pytest --cov=src
   # Expected: 70%+ coverage
   ```

4. **Application functional**
   - Dashboard loads
   - Sessions discovered
   - State transitions work
   - Notifications fire
   - SSE events broadcast

5. **No production regressions**
   - Same behavior as before migration
   - No new bugs introduced

---

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Phase 1 | logging_service.py, terminal_logging_service.py |
| 1-2 | Phase 2 | Turn tracking migrated |
| 2-3 | Phase 3 | compression_service.py, session_sync_service.py, summarization_service.py |
| 3 | Phase 4 | Project/notification/SSE audited |
| 3 | Phase 5 | Backend audit complete |
| 3-4 | Phase 6 | Cleanup, all tests passing |

**Total:** ~3-4 weeks (13-18 working days)

---

## Appendix: File-by-File Migration Map

| lib/ File | → src/ Destination | Notes |
|-----------|-------------------|-------|
| `lib/logging.py` | `src/services/logging_service.py` | New service |
| `lib/terminal_logging.py` | `src/services/terminal_logging_service.py` | New service |
| `lib/sessions.py` | `src/services/agent_store.py`, `state_interpreter.py` | Merge into existing |
| `lib/headspace.py` | `src/models/headspace.py`, `priority_service.py` | Verify complete |
| `lib/compression.py` | `src/services/compression_service.py` | New service |
| `lib/session_sync.py` | `src/services/session_sync_service.py` | New service |
| `lib/summarization.py` | `src/services/summarization_service.py` | New service |
| `lib/projects.py` | `src/models/project.py`, `agent_store.py` | Merge/extend |
| `lib/notifications.py` | `src/services/notification_service.py` | Already migrated |
| `lib/sse.py` | `src/services/event_bus.py` | Already migrated |
| `lib/backends/*.py` | `src/backends/*.py` | Already migrated |
| `lib/iterm.py` | Deprecate | Not needed with WezTerm |
| `lib/tmux.py` | Deprecate | Just a shim |
| `lib/help.py` | Deprecate or static docs | Not actively used |
