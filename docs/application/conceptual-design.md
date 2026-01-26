---
title: Conceptual Design
keywords: architecture, domain model, headspace, agent, task, turn, inference, governing agent
order: 1
---

# Claude Headspace: Conceptual Design

**Version:** 2.0
**Status:** Input artifact for major refactor
**Last Updated:** 2026-01-26

---

## 1. Fundamental Purpose and Concept

### Vision Statement

**An agentic tool for managing agentic tasks.**

Claude Headspace is a system that provides intelligent oversight and prioritization across multiple AI-assisted development sessions, guided by a user-defined focus objective.

### Core Value Proposition

A **Governing Agent** monitors multiple projects and their AI agents (Claude Code sessions), prioritizing work according to the user's current **Headspace Focus**. This enables:

- Quick context switching between projects after days or weeks away
- AI-powered prioritization of which task needs attention next
- Real-time visibility into what each agent is doing across all projects
- Intelligent summarization of recent progress via git history analysis

### Key Differentiator

The **Headspace Focus** serves as the governing principle that guides all prioritization decisions, ensuring work across multiple projects aligns with the user's current primary objective.

---

## 2. Design Decisions

The following decisions define the conceptual model:

| Decision | Resolution |
|----------|------------|
| Agent-Session relationship | **1:1** - One agent per terminal session |
| Session terminology | **DEPRECATED** - "Session" replaced by "Agent" |
| Turn definition | **Multiple turns per task** - User responding to clarification = new turn |
| "Commanded" state | **Distinct state** - Command sent, processing not yet started |
| Complete vs Idle | **Distinct states** - Complete = task finished, Idle = awaiting new task |
| Roadmap auto-updates | **Future enhancement** - Document but don't implement now |
| Backend strategy | **WezTerm-first** - Deprecate tmux |
| State detection | **LLM-primary** with regex fast-path |
| Supporting features | **All included**: Notifications, Window Focus, Brain Reboot, SSE Events |
| Dashboard grouping | **Hybrid** - Grouped by project, sorted by priority within |
| Headspace scope | **Global singleton** - One focus for all projects |
| Recent work context | **In Roadmap** - `recently_completed` section with LLM narrative |
| History source | **Git-primary** - Derive recent work from git commit history |
| Inference models | **Per-purpose config** - Fast tier (Haiku) for real-time, Deep tier (Sonnet) for batch |

### Terminology Deprecation

The legacy codebase uses "session" to mean a Claude Code session (terminal lifetime). This is **deprecated**:

| Legacy Term | New Term | Notes |
|-------------|----------|-------|
| Session | Agent | Terminal session lifetime, 1:1 with WezTerm pane |
| `recent_sessions` | `recently_completed` (in Roadmap) | Derived from git, narrative format |
| `session_state` | Agent state / Task state | Explicit state machines |
| `SessionSummary` | Git-derived narrative | No longer stored separately |

---

## 3. Core Domain Model

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
    │   └── recently_completed (LLM narrative from git)
    ├── state (status)
    │
    └── has many → Agent (1:N per project, concurrent allowed)
                   │
                   ├── 1:1 with TerminalSession (WezTerm pane)
                   ├── state derived from current task
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
                                                 ├── result_type: question | completion
                                                 │
                                                 └── triggers → InferenceCall (0:N)
                                                                ├── purpose (see §6)
                                                                ├── model, input_hash, result
                                                                └── timestamp

External Data Source:
─────────────────────
GitRepository (per project)
├── recent_commits → feeds → Roadmap.recently_completed (via LLM)
├── files_changed → enriches → Task context
└── commit_messages → informs → progress narrative
```

---

## 4. Entity Schemas

### HeadspaceFocus (Singleton)

```python
class HeadspaceFocus(BaseModel):
    current_focus: str                    # "Ship billing feature by Thursday"
    constraints: Optional[str]            # "No breaking API changes"
    updated_at: datetime
    history: list[HeadspaceHistoryEntry]  # Previous focus values (max 50)
```

### Project

```python
class Project(BaseModel):
    name: str                             # "claude-monitor"
    path: str                             # "/Users/you/dev/project"
    goal: str                             # From CLAUDE.md
    context: ProjectContext               # tech_stack, target_users
    roadmap: Roadmap                      # Includes recently_completed narrative
    state: ProjectState                   # status (no session references)
    git_repo_path: Optional[str]          # For git history analysis
```

### Roadmap

```python
class RoadmapItem(BaseModel):
    title: str
    why: Optional[str]
    definition_of_done: Optional[str]

class Roadmap(BaseModel):
    next_up: Optional[RoadmapItem]        # Current priority
    upcoming: list[str]                   # Next items
    later: list[str]                      # Future work
    not_now: list[str]                    # Parked ideas
    recently_completed: Optional[str]     # LLM-generated narrative from git
    recently_completed_at: Optional[datetime]  # When narrative was last generated
```

### Agent

```python
class Agent(BaseModel):
    id: str                               # UUID
    project_id: str                       # References Project
    terminal_session_id: str              # WezTerm pane ID
    current_task_id: Optional[str]        # Active task (if any)
    created_at: datetime
    # State is derived from current_task.state
```

### Task

```python
class TaskState(str, Enum):
    IDLE = "idle"                         # No active work, awaiting command
    COMMANDED = "commanded"               # Command sent, processing not started
    PROCESSING = "processing"             # LLM actively working
    AWAITING_INPUT = "awaiting_input"     # Waiting for user response
    COMPLETE = "complete"                 # Task finished (terminal state)

class Task(BaseModel):
    id: str                               # UUID
    agent_id: str                         # References Agent
    state: TaskState
    started_at: datetime
    completed_at: Optional[datetime]
    turn_ids: list[str]                   # Turn IDs (objects managed by AgentStore)
    summary: Optional[str]                # LLM-generated summary
    priority_score: Optional[int]         # 0-100, relative to headspace
    priority_rationale: Optional[str]
```

> **Implementation Note:** `turn_ids` stores Turn IDs rather than embedded Turn objects
> to avoid circular dependencies. The AgentStore manages the actual Turn objects and
> provides methods to retrieve them by ID.

### Turn

```python
class TurnType(str, Enum):
    USER_COMMAND = "user_command"         # User initiated
    AGENT_RESPONSE = "agent_response"     # Claude's response

class ResponseResultType(str, Enum):
    QUESTION = "question"                 # Claude asking for clarification
    COMPLETION = "completion"             # Claude finished the work

class Turn(BaseModel):
    id: str                               # UUID
    task_id: str                          # References Task
    type: TurnType
    content: str                          # Command text or response text
    result_type: Optional[ResponseResultType]  # Only for agent_response
    timestamp: datetime
    inference_call_ids: list[str]         # InferenceCall IDs (managed separately)
```

> **Implementation Note:** `inference_call_ids` stores IDs rather than embedded objects
> for the same reason as Task.turn_ids - avoids circular dependencies and allows
> the InferenceService to manage call records independently.

### InferenceCall

```python
class InferencePurpose(str, Enum):
    # Fast tier (Haiku) - high frequency, low latency
    DETECT_STATE = "detect_state"                 # LLM-based state detection
    SUMMARIZE_COMMAND = "summarize_command"       # Quick command summary
    CLASSIFY_RESPONSE = "classify_response"       # Question vs completion
    QUICK_PRIORITY = "quick_priority"             # Within-session priority update

    # Deep tier (Sonnet/Opus) - low frequency, high quality
    GENERATE_PROGRESS_NARRATIVE = "generate_progress_narrative"  # Git → narrative
    FULL_PRIORITY = "full_priority"               # Cross-project priority computation
    ROADMAP_ANALYSIS = "roadmap_analysis"         # Roadmap progress analysis
    BRAIN_REBOOT = "brain_reboot"                 # Context briefing generation

class InferenceCall(BaseModel):
    id: str
    turn_id: Optional[str]                # None for project-level calls
    project_id: Optional[str]             # For project-level calls
    purpose: InferencePurpose
    model: str                            # Resolved from InferenceConfig
    input_hash: str                       # For caching
    result: dict                          # Structured output
    timestamp: datetime
    latency_ms: int
    cost_cents: Optional[float]           # Track inference costs
```

### InferenceConfig

```python
class InferenceConfig(BaseModel):
    """Per-purpose model configuration for inference calls.

    Allows tuning model selection based on:
    - Latency requirements (fast tier for real-time, deep for batch)
    - Quality requirements (deep tier for complex reasoning)
    - Cost constraints (fast tier is cheaper)
    """

    # Fast tier - high frequency, low latency (default: claude-3-haiku)
    detect_state: str = "anthropic/claude-3-haiku"
    summarize_command: str = "anthropic/claude-3-haiku"
    classify_response: str = "anthropic/claude-3-haiku"
    quick_priority: str = "anthropic/claude-3-haiku"

    # Deep tier - low frequency, high quality (default: claude-3-sonnet)
    generate_progress_narrative: str = "anthropic/claude-3-sonnet"
    full_priority: str = "anthropic/claude-3-sonnet"
    roadmap_analysis: str = "anthropic/claude-3-sonnet"
    brain_reboot: str = "anthropic/claude-3-sonnet"

    def get_model(self, purpose: InferencePurpose) -> str:
        """Resolve model for a given purpose."""
        return getattr(self, purpose.value)
```

---

## 5. Task State Machine

```
                          ┌─────────────────────────────────────────┐
                          │                                         │
                          ▼                                         │
                    ┌──────────┐                                    │
         ┌────────▶│   IDLE   │◀───────────────────────────────────┤
         │         └────┬─────┘                                    │
         │              │                                          │
         │              │ User types command and presses Enter     │
         │              │ (WezTerm hook: enter-pressed)            │
         │              ▼                                          │
         │         ┌──────────┐                                    │
         │         │COMMANDED │  Brief transitional state          │
         │         └────┬─────┘  (command sent, processing starts) │
         │              │                                          │
         │              │ LLM begins processing                    │
         │              │ (detected via content analysis)          │
         │              ▼                                          │
         │         ┌──────────┐                                    │
         │    ┌───▶│PROCESSING│◀───┐                               │
         │    │    └────┬─────┘    │                               │
         │    │         │          │                               │
         │    │         │ LLM finishes (detected via LLM or regex) │
         │    │         │          │                               │
         │    │         ├──────────┼───────────────────────────────┘
         │    │         │          │       (result: completion)
         │    │         │          │
         │    │         ▼          │
         │    │    ┌──────────┐    │
         │    │    │ AWAITING │    │
         │    │    │  INPUT   │────┘
         │    │    └────┬─────┘
         │    │         │      User responds to question
         │    │         │      (new Turn created)
         │    └─────────┘
         │
         │         ┌──────────┐
         └─────────│ COMPLETE │  Terminal state for task
                   └──────────┘  (Agent transitions to IDLE, new Task created)
```

### State Transition Triggers

| From | To | Trigger | Detection Method |
|------|-----|---------|-----------------|
| IDLE | COMMANDED | User presses Enter | WezTerm hook |
| COMMANDED | PROCESSING | LLM starts | Content analysis |
| PROCESSING | AWAITING_INPUT | LLM asks question | LLM interpretation |
| PROCESSING | COMPLETE | LLM finishes | LLM interpretation + completion marker |
| AWAITING_INPUT | PROCESSING | User responds | WezTerm hook + content change |
| COMPLETE | IDLE | New task begins | Automatic (task lifecycle) |

---

## 6. Governing Agent

The Governing Agent is the orchestrating component that:

1. **Monitors** all project agents via WezTerm integration
2. **Detects** state transitions using LLM-based interpretation (with regex fast-path)
3. **Triggers** inference calls at appropriate moments (see Activity Matrix)
4. **Computes** priorities across all active tasks based on headspace alignment
5. **Emits** events for real-time dashboard updates (SSE)
6. **Sends** notifications on significant state changes
7. **Analyzes** git history to generate `recently_completed` narratives

**Future Enhancement (documented, not implemented):**
- Periodically update project roadmaps with significant events and milestones

### Activity Matrix

The Governing Agent performs inference calls at specific moments. Each uses a model tier appropriate to its latency and quality requirements.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     GOVERNING AGENT ACTIVITY MATRIX                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TRIGGER                    INFERENCE PURPOSE           MODEL TIER          │
│  ──────────────────────────────────────────────────────────────────────     │
│                                                                              │
│  ┌─ TASK LIFECYCLE (Real-time, per-turn) ─────────────────────────────┐    │
│  │                                                                     │    │
│  │  IDLE → COMMANDED        SUMMARIZE_COMMAND           Fast (Haiku)  │    │
│  │  (User presses Enter)    "What is user asking?"                    │    │
│  │                                                                     │    │
│  │  Poll cycle              DETECT_STATE                Fast (Haiku)  │    │
│  │  (Every 2s)              "Is Claude processing/idle/waiting?"      │    │
│  │                                                                     │    │
│  │  PROCESSING → AWAITING   CLASSIFY_RESPONSE           Fast (Haiku)  │    │
│  │  (Claude asks question)  "What type of question?"                  │    │
│  │                                                                     │    │
│  │  PROCESSING → COMPLETE   QUICK_PRIORITY              Fast (Haiku)  │    │
│  │  (Turn finished)         "Did priority change?"                    │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─ PROJECT LIFECYCLE (Batch, periodic/on-demand) ────────────────────┐    │
│  │                                                                     │    │
│  │  Dashboard load /        FULL_PRIORITY               Deep (Sonnet) │    │
│  │  Priority invalidation   "Rank all tasks vs headspace"             │    │
│  │                                                                     │    │
│  │  Brain Reboot request    BRAIN_REBOOT                Deep (Sonnet) │    │
│  │                          "Generate context briefing"               │    │
│  │                                                                     │    │
│  │  Git HEAD changed /      GENERATE_PROGRESS_NARRATIVE Deep (Sonnet) │    │
│  │  Stale narrative         "Summarize recent git activity"           │    │
│  │                                                                     │    │
│  │  Roadmap viewed          ROADMAP_ANALYSIS            Deep (Sonnet) │    │
│  │  (if stale)              "Assess progress vs roadmap"              │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Inference Frequency and Cost Expectations

| Tier | Purpose | Frequency | Latency Target | Approx Cost |
|------|---------|-----------|----------------|-------------|
| **Fast** | DETECT_STATE | Every 2s per agent | <200ms | ~$0.0001/call |
| **Fast** | SUMMARIZE_COMMAND | Per command | <200ms | ~$0.0001/call |
| **Fast** | CLASSIFY_RESPONSE | Per response | <200ms | ~$0.0001/call |
| **Fast** | QUICK_PRIORITY | Per turn completion | <200ms | ~$0.0001/call |
| **Deep** | FULL_PRIORITY | On invalidation (minutes) | <2s | ~$0.005/call |
| **Deep** | BRAIN_REBOOT | On demand | <3s | ~$0.01/call |
| **Deep** | GENERATE_PROGRESS_NARRATIVE | On git change / daily | <3s | ~$0.01/call |
| **Deep** | ROADMAP_ANALYSIS | On roadmap view (cached) | <3s | ~$0.01/call |

### Caching Strategy

| Purpose | Cache Key | TTL | Invalidation |
|---------|-----------|-----|--------------|
| DETECT_STATE | content_hash | 30s | Content change |
| SUMMARIZE_COMMAND | command_hash | Forever | Never (immutable) |
| CLASSIFY_RESPONSE | response_hash | Forever | Never (immutable) |
| QUICK_PRIORITY | agent_id + turn_id | Until next turn | Turn completion |
| FULL_PRIORITY | all_agents_hash | Until invalidation | State transition, headspace change |
| BRAIN_REBOOT | project_id + git_head | 1 hour | Git change |
| GENERATE_PROGRESS_NARRATIVE | project_id + git_head | 24 hours | Git change |
| ROADMAP_ANALYSIS | project_id + roadmap_hash | 1 hour | Roadmap change |

---

## 7. Git Integration

The system uses git as the primary source of truth for understanding recent work on a project. This enables quick spin-up when returning after days or weeks.

### Data Flow

```
GitRepository
    │
    ├── git log --oneline -n 20
    │   └── Recent commit messages
    │
    ├── git diff --stat HEAD~10
    │   └── Files changed recently
    │
    └── git log --since="7 days ago"
        └── Activity timeframe
            │
            ▼
    LLM Inference (purpose: GENERATE_PROGRESS_NARRATIVE)
            │
            ▼
    Roadmap.recently_completed (narrative string)
```

### Narrative Generation

- **Triggered on:** Dashboard load, Brain Reboot request, or periodic refresh
- **Input:** Recent git commits, files changed, commit messages
- **Output:** LLM-generated narrative summarizing recent progress
- **Caching:** Stored in `Roadmap.recently_completed`, refreshed when git HEAD changes

### Example Output

```
"Over the past week, focus was on the notification system:
- Added macOS notification support with terminal-notifier
- Implemented state change detection for idle→processing transitions
- Fixed duplicate notification bug in rapid state changes
Last commit: 2 days ago (refactor: extract notification logic)"
```

---

## 8. Supporting Features

### Notifications

- macOS notifications via `terminal-notifier`
- Triggered on: PROCESSING → AWAITING_INPUT, PROCESSING → COMPLETE
- Configurable enable/disable

### Window Focus

- Click-to-focus from dashboard
- WezTerm native `activate-pane` API
- Brings terminal to foreground

### Brain Reboot

Context refresh for returning to a project after days/weeks. Aggregates:

- Headspace focus (what you're trying to accomplish)
- Roadmap (next_up, upcoming items)
- **Recently completed narrative** (git-derived, LLM-generated)
- Current agent/task state (if any active)

Provides briefing for quick spin-up on context switch. Triggers refresh of `Roadmap.recently_completed` if stale.

### SSE Events

- Real-time dashboard updates without polling
- Events: `agent_updated`, `priorities_changed`, `task_state_changed`

---

## 9. Dashboard Representation

### Layout

- Headspace Focus displayed prominently at top
- Projects grouped as columns (Kanban-style)
- Within each project: Agent cards showing current task state
- Cards sorted by priority within project

### Visual Indicators

- State badges: color-coded by task state
- Priority indicators: score (0-100) and alignment rationale
- Time tracking: elapsed time, last activity

### Interactions

- Click card → Focus terminal window
- Click notification → Focus relevant terminal
- Edit headspace → Triggers priority recalculation

---

## 10. Architecture Decisions

### WezTerm-First Backend Strategy

- **Primary:** WezTerm with Lua hooks for event-driven detection
- **Deprecated:** tmux (polling-only, no event hooks)
- **Migration:** Document path from tmux to WezTerm

### LLM-Based State Detection

- **Primary:** LLM interpretation via OpenRouter (Claude Haiku)
- **Fast-path:** Regex for obvious states (spinner in title)
- **Caching:** By content hash to avoid redundant calls

---

## 11. Changes from Current Implementation

| # | Change | Current State | Target State |
|---|--------|--------------|--------------|
| 1 | Agent entity | Implicit (session ≈ agent) | Explicit `Agent` model |
| 2 | **Session terminology** | "Session" used throughout | **DEPRECATED** → "Agent" |
| 3 | Task entity | Conflated with "turn" | First-class `Task` with lifecycle |
| 4 | Turn definition | One turn = full command-to-completion | Multiple turns per task (clarifications) |
| 5 | Commanded state | Not tracked | Distinct state via WezTerm hook |
| 6 | Complete state | Same as idle | Distinct terminal state |
| 7 | State detection | Regex/heuristics | LLM-primary with regex fast-path |
| 8 | Backend | tmux + WezTerm + iTerm | WezTerm-first (tmux deprecated) |
| 9 | Inference tracking | Mixed purposes | Categorized by `InferencePurpose` |
| 10 | **Recent work history** | `recent_sessions[]` in Project | **Git-derived** narrative in Roadmap |
| 11 | **Spin-up context** | Session summaries (stored) | Git commits → LLM narrative (computed) |
