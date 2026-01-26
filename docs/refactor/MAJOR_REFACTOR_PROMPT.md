# Major Refactor System Prompt

**Purpose:** System prompt for Claude Code to rebuild Claude Headspace from the ground up.

---

## Mission

Rebuild the Claude Headspace application to implement the conceptual design documented in `docs/application/conceptual-design.md`. Use the [clawdbot](https://github.com/clawdbot/clawdbot) repository as an architectural reference for patterns and code organization.

This clawdbot project also performs a similar operation as this project, that is automating and orchestrating interactions with agentic processes.

---

## Context

### What is Claude Headspace?

An agentic tool for managing agentic tasks. A **Governing Agent** monitors multiple projects and their AI agents (Claude Code sessions), prioritizing work according to the user's current **Headspace Focus**.

### Why the Rebuild?

The current implementation is fundamentally broken:

- Sessions detected unreliably
- Status detection (processing/idle/input_needed) is wrong
- Notifications don't fire correctly
- Dashboard shows stale/wrong data

---

## Critical Issues Identified

### 1. State Fragmentation (7+ locations)

State is scattered with no single source of truth:

- `_previous_activity_states` (in-memory dict)
- `_turn_tracking` (in-memory dict)
- `_last_completed_turn` (in-memory dict)
- `_session_activity_cache` (in-memory dict)
- `_scan_sessions_cache` (200ms TTL cache)
- `data/session_state.yaml` (on-disk)
- `.claude-monitor-*.json` files (per-project)
- Project YAML "state" sections

**Solution:** Single `AgentStore` class owns all state.

### 2. Fragile Activity Detection

Current detection relies on brittle regex/heuristics:

- Spinner characters in window title (⠁⠂⠃...)
- "(esc to interrupt)" pattern in content
- Completion markers ("✻ Verb for Xm Ys")
- Permission dialog string matching

These constantly break with Claude Code UI changes.

**Solution:** LLM-based state interpretation with regex fast-path for obvious states.

### 3. tmux Cannot Support Event-Driven Detection

tmux has no hook system for API callbacks. This means:

- Turn START detection requires polling (2s+ delay)
- Turn COMPLETION detection requires polling
- No real-time responsiveness possible

WezTerm has Lua hooks that can call HTTP APIs on events.

**Solution:** WezTerm-first. Deprecate tmux.

### 4. God-Object Files

- `lib/sessions.py` = 49KB (1300+ lines)
- `monitor.py` = 1273 lines
- `lib/headspace.py` = 26KB

**Solution:** Module boundaries < 500 LOC per file.

### 5. No Proper Domain Model

Current code conflates:

- Session ≈ Agent (no explicit model)
- Turn ≈ Task (no distinction)
- No Turn entity for clarifications

**Solution:** Implement full domain model from conceptual design.

### 6. No Validation or Type Safety

- Config loaded with `yaml.safe_load()` directly
- No Pydantic schemas
- No runtime type checking

**Solution:** Pydantic models for all entities and config.

### 7. Insufficient Testing

- No coverage thresholds enforced
- No pre-commit hooks
- Tests exist but gaps are common

**Solution:** 70% coverage threshold, pre-commit hooks with ruff.

---

## Architecture Reference: Clawdbot

Study the [clawdbot repository](https://github.com/clawdbot/clawdbot) for:

### Code Organization

```
src/
├── agents/          # Agent management
├── config/          # 100+ files for config with Zod schemas
├── gateway/         # WebSocket gateway (single source of truth)
├── logging/         # Structured logging with levels, redaction
├── sessions/        # Session management
└── terminal/        # Terminal utilities
```

### Key Patterns to Adopt

1. **Zod schemas** (use Pydantic in Python) for all config and data
2. **Colocated tests** (`*.test.ts` next to source)
3. **Pre-commit hooks** enforced
4. **Coverage thresholds** (70% enforced)
5. **Clear module boundaries** (~500-700 LOC guideline)
6. **Multi-agent safety rules** in AGENTS.md
7. **Structured logging** with levels and redaction

### Patterns NOT to Copy

- Clawdbot uses RPC mode to communicate with agents (direct API)
- Claude Headspace monitors external Claude Code CLI sessions (terminal observation)
- Different fundamental architecture - adopt patterns, not code

---

## Canonical Requirements: Conceptual Design

**Read and implement exactly:** `docs/application/conceptual-design.md`

### Core Domain Model (§3)

```
HeadspaceFocus (global singleton)
│
├── guides prioritization of →
│
└── Project (1:N)
    ├── name, path, goal
    ├── context (tech_stack, target_users)
    ├── roadmap
    │   ├── next_up, upcoming, later, not_now
    │   └── recently_completed (LLM narrative from git)  ← NEW
    ├── state (status)
    │
    └── has many → Agent (1:N per project, concurrent allowed)
                   │
                   ├── 1:1 with TerminalSession (WezTerm pane)
                   ├── state derived from current task
                   ├── replaces legacy "Session" concept  ← TERMINOLOGY CHANGE
                   │
                   └── has many → Task (1:N per agent, sequential)
                                  │
                                  ├── state: idle → commanded → processing
                                  │          ↓                    ↓
                                  │       (user types)    (LLM working)
                                  │                              ↓
                                  │          ←←← awaiting_input ←←←
                                  │          ↓         ↑
                                  │       (user responds)
                                  │                              ↓
                                  │                          complete
                                  │                              ↓
                                  │                            idle
                                  │
                                  └── has many → Turn (1:N per task)
                                                 │
                                                 ├── type: user_command | agent_response
                                                 ├── content: command text or response text
                                                 ├── result_type: question | completion (agent turns only)
                                                 │
                                                 └── triggers → InferenceCall (0:N)
                                                                ├── purpose: summarize | classify | prioritize | detect_state
                                                                ├── model, input_hash, result
                                                                └── timestamp

External Data Source:
─────────────────────
GitRepository (per project)
├── recent_commits → feeds → Roadmap.recently_completed (via LLM)
├── files_changed → enriches → Task context
└── commit_messages → informs → progress narrative
```

### Entity Schemas (§4)

Implement EXACTLY as specified in conceptual design:

- `HeadspaceFocus` - global singleton with history
- `Project` - with goal, context, roadmap, git_repo_path
- `Roadmap` - with recently_completed narrative
- `Agent` - 1:1 with WezTerm pane, state derived from task
- `Task` - with TaskState enum (5 states), turns, priority
- `Turn` - with TurnType, ResponseResultType
- `InferenceCall` - with InferencePurpose, model, caching
- `InferenceConfig` - per-purpose model configuration

### Task State Machine (§5)

```
IDLE → COMMANDED → PROCESSING → AWAITING_INPUT → PROCESSING (loop)
                             → COMPLETE → IDLE (new task)
```

| From           | To             | Trigger            | Detection          |
| -------------- | -------------- | ------------------ | ------------------ |
| IDLE           | COMMANDED      | User presses Enter | WezTerm hook       |
| COMMANDED      | PROCESSING     | LLM starts         | Content analysis   |
| PROCESSING     | AWAITING_INPUT | LLM asks question  | LLM interpretation |
| PROCESSING     | COMPLETE       | LLM finishes       | LLM interpretation |
| AWAITING_INPUT | PROCESSING     | User responds      | WezTerm hook       |
| COMPLETE       | IDLE           | New task           | Automatic          |

### Governing Agent (§6)

Implement the Activity Matrix:

**Fast Tier (Haiku) - Real-time:**

- DETECT_STATE (every 2s)
- SUMMARIZE_COMMAND (on Enter)
- CLASSIFY_RESPONSE (on response)
- QUICK_PRIORITY (on turn complete)

**Deep Tier (Sonnet) - Batch:**

- FULL_PRIORITY (on invalidation)
- BRAIN_REBOOT (on demand)
- GENERATE_PROGRESS_NARRATIVE (on git change)
- ROADMAP_ANALYSIS (on roadmap view)

### Git Integration (§7)

- `recently_completed` derived from git history, not stored session summaries
- LLM generates narrative from commits
- Cached by project_id + git_head (24 hour TTL)

### Supporting Features (§8)

- Notifications (macOS via terminal-notifier)
- Window Focus (WezTerm activate-pane)
- Brain Reboot (context briefing)
- SSE Events (agent_updated, priorities_changed, task_state_changed)

---

## Target Architecture

```
claude_monitor/
├── monitor.py                    # Flask app entry (~300 LOC)
├── config.py                     # Pydantic config validation
│
├── models/                       # Domain Models (§4)
│   ├── __init__.py
│   ├── headspace.py             # HeadspaceFocus, HeadspaceHistoryEntry
│   ├── project.py               # Project, ProjectContext, Roadmap, RoadmapItem
│   ├── agent.py                 # Agent
│   ├── task.py                  # Task, TaskState
│   ├── turn.py                  # Turn, TurnType, ResponseResultType
│   ├── inference.py             # InferenceCall, InferencePurpose, InferenceConfig
│   └── config.py                # AppConfig
│
├── services/                    # Governing Agent Components (§6)
│   ├── __init__.py
│   ├── governing_agent.py       # Main orchestrator
│   ├── agent_store.py           # Single source of truth
│   ├── task_state_machine.py    # State transitions (§5)
│   ├── state_interpreter.py     # LLM-based state detection
│   ├── inference_service.py     # InferenceCall management + caching
│   ├── git_analyzer.py          # Git → recently_completed (§7)
│   ├── priority_service.py      # Cross-project priorities
│   ├── notification_service.py  # macOS notifications
│   └── event_bus.py             # SSE broadcasting
│
├── backends/
│   ├── base.py                  # TerminalBackend interface (keep)
│   ├── wezterm.py               # PRIMARY backend (keep)
│   ├── wezterm_hooks.lua        # Lua hooks (expand)
│   └── tmux.py                  # DEPRECATED (warning on use)
│
├── routes/                      # Flask blueprints
│   ├── __init__.py
│   ├── agents.py                # /api/agents/* (was sessions)
│   ├── projects.py              # /api/projects/*
│   ├── headspace.py             # /api/headspace/*
│   ├── priorities.py            # /api/priorities
│   ├── wezterm_hooks.py         # /api/wezterm/*
│   └── events.py                # /api/events (SSE)
│
└── tests/
    ├── test_task_state_machine.py  # 100% coverage required
    ├── test_state_interpreter.py
    ├── test_agent_store.py
    ├── test_inference_service.py
    └── test_git_analyzer.py
```

---

## Files to Delete

| File                      | Reason                                   |
| ------------------------- | ---------------------------------------- |
| `lib/sessions.py` (49KB)  | Replaced by models/ and services/        |
| `lib/headspace.py` (26KB) | Replaced by services/priority_service.py |
| `lib/session_sync.py`     | No longer needed                         |
| `lib/compression.py`      | No session summaries to compress         |
| `lib/summarization.py`    | Replaced by git-derived narratives       |

---

## Terminology Migration

| Legacy            | New                   | Notes                                    |
| ----------------- | --------------------- | ---------------------------------------- |
| Session           | Agent                 | Terminal lifetime, 1:1 with WezTerm pane |
| `recent_sessions` | `recently_completed`  | Git-derived narrative in Roadmap         |
| `session_state`   | Agent/Task state      | Explicit state machines                  |
| `SessionSummary`  | Git-derived narrative | Computed, not stored                     |

All code, comments, API endpoints, and documentation must use new terminology.

---

## Implementation Order

### Phase 1: Models

Create `models/` with ALL Pydantic schemas from §4 of conceptual design.
Write validation tests for each model.

### Phase 2: State Machine

Implement `TaskStateMachine` with all 6 transitions from §5.
100% test coverage required.

### Phase 3: Inference Service

Implement `InferenceService` with:

- All 8 InferencePurpose values
- Per-purpose model routing via InferenceConfig
- Caching strategy from §6

### Phase 4: Governing Agent

Wire together:

- AgentStore (single source of truth)
- TaskStateMachine (transitions)
- InferenceService (LLM calls)
- EventBus (SSE)

### Phase 5: Git Integration

Implement `GitAnalyzer` for `recently_completed` narratives.

### Phase 6: Routes & Dashboard

Flask blueprints with new terminology (agents, not sessions).
SSE event streaming.

### Phase 7: Integration

Wire everything in `monitor.py`.
Delete legacy code.
Enforce 70% coverage.

---

## Success Criteria

- [ ] Domain model matches Conceptual Design §3-4 exactly
- [ ] Task state machine matches §5 (all 6 transitions)
- [ ] Governing Agent implements Activity Matrix (§6)
- [ ] Git-derived `recently_completed` narratives (§7)
- [ ] "Session" terminology completely removed
- [ ] WezTerm-first (tmux deprecated with warning)
- [ ] LLM-based state detection with fast-path
- [ ] 70% test coverage enforced
- [ ] No file > 500 LOC
- [ ] Pre-commit hooks configured (ruff)

---

## Commands

```bash
# Run tests with coverage
pytest --cov=. --cov-fail-under=70

# Start dev server
python monitor.py

# Start monitored session (WezTerm)
claude-monitor start --wezterm
```

---

## Reference Documents

1. **Conceptual Design (canonical):** `docs/application/conceptual-design.md`
2. **Architecture Reference:** https://github.com/clawdbot/clawdbot
3. **Current CLAUDE.md:** `CLAUDE.md` (update after refactor)
