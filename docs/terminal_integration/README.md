# Terminal Integration Specification

**Project:** Claude Headspace
**Version:** 1.0
**Last Updated:** 2026-01-25
**Purpose:** Baseline specification for evaluating and planning terminal emulator migration (tmux → WezTerm)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Current Implementation (tmux)](#3-current-implementation-tmux)
4. [Session Lifecycle](#4-session-lifecycle)
5. [Activity State Detection](#5-activity-state-detection)
6. [Turn Cycle Tracking](#6-turn-cycle-tracking)
7. [Logging System](#7-logging-system)
8. [API Endpoints](#8-api-endpoints)
9. [Data Structures](#9-data-structures)
10. [Integration Points](#10-integration-points)
11. [Known Issues & Limitations](#11-known-issues--limitations)
12. [Requirements for Replacement](#12-requirements-for-replacement)
13. [References](#13-references)

---

## 1. Executive Summary

Claude Headspace monitors Claude Code sessions running in terminal emulators, providing a dashboard with real-time activity states, notifications, and AI-powered session prioritization.

### Current Approach: Polling-Based Screen Scraping

The system uses **tmux** as the terminal multiplexer with a **polling architecture**:

1. Dashboard polls `/api/sessions` every ~2 seconds
2. Monitor captures terminal content via `tmux capture-pane`
3. Pattern matching detects activity state from captured text
4. State transitions are logged and trigger notifications/priorities refresh

### Key Limitation

**There is no event streaming from the terminal.** The system relies entirely on periodic snapshots of terminal content, which creates inherent race conditions and detection gaps.

### Purpose of This Document

This specification serves as a complete baseline for:
- Understanding the current terminal integration architecture
- Identifying issues that a replacement must address
- Planning migration to WezTerm or another terminal emulator
- Ensuring feature parity during migration

---

## 2. Architecture Overview

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TERMINAL LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   User ──────▶ tmux Session ◀─────── Claude Code CLI                        │
│                    │                        │                                │
│                    │ (terminal content)     │ (spinner, completion marker)   │
│                    ▼                        ▼                                │
│              tmux capture-pane ◀──────── Screen Buffer                      │
│                                                                              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    │ Polling (~2s interval)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MONITOR LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   scan_sessions() ───▶ parse_activity_state() ───▶ track_turn_cycle()       │
│         │                       │                         │                  │
│         │                       │                         ▼                  │
│         │                       │              ┌─────────────────────┐       │
│         │                       │              │ tmux.jsonl logging  │       │
│         │                       │              └─────────────────────┘       │
│         │                       ▼                                            │
│         │              Activity State                                        │
│         │         (processing/idle/input_needed)                             │
│         │                       │                                            │
│         ▼                       ▼                                            │
│   Session Dict ────────▶ State Change Detection ────▶ Notifications         │
│                                 │                                            │
│                                 ▼                                            │
│                    emit_priorities_invalidation()                            │
│                                 │                                            │
└─────────────────────────────────┼────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI LAYER                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   aggregate_priority_context() ───▶ OpenRouter API ───▶ Ranked Priorities   │
│              │                            │                                  │
│              │                            ▼                                  │
│              │                  ┌─────────────────────┐                      │
│              │                  │ openrouter.jsonl    │                      │
│              │                  └─────────────────────┘                      │
│              ▼                                                               │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │ Context: headspace.yaml + project/*.yaml + session states       │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| **tmux.py** | `lib/tmux.py` | Low-level tmux operations (create, send, capture, kill) |
| **sessions.py** | `lib/sessions.py` | Session discovery, activity state parsing, turn tracking |
| **tmux_logging.py** | `lib/tmux_logging.py` | Structured logging for tmux operations |
| **notifications.py** | `lib/notifications.py` | State change detection, macOS notifications |
| **headspace.py** | `lib/headspace.py` | Priority computation, cache management |
| **iterm.py** | `lib/iterm.py` | iTerm window focus via AppleScript |
| **monitor.py** | `monitor.py` | Flask app, API endpoints, HTML dashboard |

---

## 3. Current Implementation (tmux)

### 3.1 Why tmux?

tmux was chosen for:
- **Bidirectional control**: Can send text to sessions (`send_keys`) and capture output (`capture_pane`)
- **Session persistence**: Sessions survive terminal disconnection
- **Programmatic control**: Clean CLI interface via subprocess
- **Cross-platform consistency**: Same behavior across different terminal emulators

### 3.2 tmux Module Functions (`lib/tmux.py`)

| Function | Purpose | Returns |
|----------|---------|---------|
| `is_tmux_available()` | Check if tmux is installed | `bool` (cached) |
| `list_sessions()` | List all tmux sessions | `list[dict]` |
| `session_exists(name)` | Check if session exists | `bool` |
| `create_session(name, dir, cmd)` | Create detached session | `bool` |
| `kill_session(name)` | Terminate session | `bool` |
| `send_keys(name, text, enter)` | Send text to session | `bool` |
| `capture_pane(name, lines)` | Capture terminal content | `str` or `None` |
| `get_session_info(name)` | Get session metadata | `dict` or `None` |
| `get_claude_sessions()` | Filter to `claude-*` sessions | `list[dict]` |

### 3.3 Session Naming Convention

**Format:** `claude-{project-slug}-{hash}`

**Example:** `claude-my-project-87c165e4`

Components:
- **Prefix:** `claude-` (identifies monitored sessions)
- **Slug:** Project name normalized (lowercase, hyphens)
- **Hash:** 8-char MD5 suffix (collision prevention)

**Slugification rules:**
- Lowercase conversion
- Spaces/underscores → hyphens
- Special characters removed
- Multiple hyphens collapsed
- Leading/trailing hyphens removed
- Empty → "unnamed"

### 3.4 Content Capture

```python
def capture_pane(session_name: str, lines: int = 100) -> str | None:
    """Capture last N lines from tmux pane."""
    result = run_tmux(["capture-pane", "-t", session_name, "-p", "-S", f"-{lines}"])
    return result.stdout if result else None
```

**Default capture:** 200 lines (configurable per call)

**Limitations:**
- Only captures visible scrollback
- No access to content that has scrolled beyond buffer
- Captures a snapshot, not a stream

---

## 4. Session Lifecycle

### 4.1 Session Creation (`claude-monitor start`)

The wrapper script (`bin/claude-monitor`) creates monitored sessions:

```bash
#!/bin/bash
# Simplified flow

# 1. Generate identifiers
UUID=$(python -c "import uuid; print(uuid.uuid4())")
PROJECT_NAME=$(basename $(pwd))
SESSION_NAME="claude-${PROJECT_SLUG}-${UUID:0:8}"

# 2. Create state file
cat > ".claude-monitor-${UUID}.json" << EOF
{
  "uuid": "${UUID}",
  "project_dir": "$(pwd)",
  "project_name": "${PROJECT_NAME}",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)",
  "session_type": "tmux",
  "tmux_session": "${SESSION_NAME}"
}
EOF

# 3. Create tmux session with Claude Code
tmux new-session -d -s "${SESSION_NAME}" -c "$(pwd)" \
  "env CLAUDE_MONITOR_UUID=${UUID} claude"

# 4. Configure tmux session
tmux set-option -t "${SESSION_NAME}" mouse on
tmux set-option -t "${SESSION_NAME}" set-clipboard on

# 5. Get PID and update state file
PID=$(tmux list-panes -t "${SESSION_NAME}" -F "#{pane_pid}")
# Update state file with PID

# 6. Attach (blocks until detach)
tmux attach-session -t "${SESSION_NAME}"

# 7. Cleanup on exit
rm ".claude-monitor-${UUID}.json"
```

### 4.2 Session Discovery (`scan_sessions`)

**Approach:** tmux-first (source of truth)

```python
def scan_sessions(config: dict) -> list[dict]:
    """Discover all active Claude Code sessions."""

    # 1. Query tmux directly
    tmux_sessions = get_claude_sessions()  # Filters to claude-* prefix

    sessions = []
    for tmux_info in tmux_sessions:
        # 2. Parse session name
        project_slug, uuid8 = parse_session_name(tmux_info["name"])

        # 3. Match to config project
        project = match_project(project_slug, config["projects"])

        # 4. Capture and analyze content
        content = capture_pane(tmux_info["name"], lines=200)
        activity_state, task_summary = parse_activity_state("", content)

        # 5. Track turn cycle (logs state transitions)
        track_turn_cycle(session_id, tmux_info["name"], activity_state, content)

        # 6. Build session dict
        session = {
            "session_id": uuid8,
            "project_name": project["name"] if project else project_slug,
            "activity_state": activity_state,
            "task_summary": task_summary,
            # ... other fields
        }
        sessions.append(session)

    # 7. Cleanup stale state files
    cleanup_stale_state_files(config, [s["tmux_session"] for s in tmux_sessions])

    return sessions
```

### 4.3 State File Format

**Location:** `{project_dir}/.claude-monitor-{uuid}.json`

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "project_dir": "/Users/you/dev/my-project",
  "project_name": "my-project",
  "started_at": "2026-01-25T10:30:45.123456+00:00",
  "pid": 12345,
  "session_type": "tmux",
  "tmux_session": "claude-my-project-87c165e4"
}
```

**Note:** State files are legacy. The system now uses tmux as the source of truth for session discovery.

---

## 5. Activity State Detection

### 5.1 States

| State | Meaning | User Action Required |
|-------|---------|---------------------|
| `processing` | Claude is actively working | Wait |
| `idle` | Ready for new task | Can send command |
| `input_needed` | Waiting for user decision | Must respond |
| `unknown` | Cannot determine state | Check manually |

### 5.2 Detection Algorithm

```python
def parse_activity_state(window_title: str, content_tail: str) -> tuple[str, str]:
    """
    Analyze terminal content to determine activity state.

    Returns: (activity_state, task_summary)
    """

    # Detection windows (from end of content)
    COMPLETION_WINDOW = 300    # chars to search for completion marker
    PROCESSING_WINDOW = 800    # chars to search for processing indicators
    INPUT_WINDOW = 1500        # chars to search for input patterns

    # 1. Check for completion marker (highest priority)
    #    Pattern: "✻ Verb for Xm Xs" or "✻ Verb for Xs"
    completion_pattern = r"✻\s+\w+\s+for\s+(?:\d+m\s+)?\d+s"
    if re.search(completion_pattern, content_tail[-COMPLETION_WINDOW:]):
        is_completed = True

    # 2. Check for active processing
    #    Indicator: "(esc to interrupt)" in recent content
    if "(esc to interrupt)" in content_tail[-PROCESSING_WINDOW:]:
        is_actively_processing = True

    # 3. Check for spinner in window title
    #    Braille characters: ⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿
    #    Other spinners: ◐◑◒◓◴◵◶◷⣾⣽⣻⢿⡿⣟⣯⣷
    SPINNER_CHARS = set("⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿◐◑◒◓◴◵◶◷⣾⣽⣻⢿⡿⣟⣯⣷")
    first_char = window_title[0] if window_title else ""
    has_spinner = first_char in SPINNER_CHARS

    # 4. Check for input-needed patterns
    #    Only genuine UI patterns, not conversational text
    INPUT_PATTERNS = [
        "Yes, and don't ask again",
        "Allow once",
        "Allow for this session",
        "❯ Yes",
        "❯ No",
        "❯ 1.",
        "❯ 2.",
        "Enter to select",
        "↑↓ to navigate",
    ]
    is_input_needed = any(p in content_tail[-INPUT_WINDOW:] for p in INPUT_PATTERNS)

    # 5. Check for idle prompt
    #    Look for ❯ in last 25 lines without active processing
    has_idle_prompt = "❯" in content_tail[-500:]

    # 6. Determine state (priority order)
    if is_completed and not has_spinner:
        state = "idle"
    elif has_spinner:
        state = "processing"
    elif is_input_needed:
        state = "input_needed"
    elif is_actively_processing:
        state = "processing"
    elif has_idle_prompt:
        state = "idle"
    else:
        state = "unknown"

    return (state, extract_task_summary(window_title, content_tail))
```

### 5.3 Completion Marker Verbs

Claude Code uses randomized completion verbs. The system recognizes 150+ variants:

```
Accomplished, Actioned, Actualized, Baked, Booped, Brewed,
Calculated, Cerebrated, Channelled, Churned, Clauded, Coalesced,
Cogitated, Combobulated, Computed, Concocted, Conjured, Considered,
Contemplated, Cooked, Crafted, Created, Crunched, Deciphered,
Deliberated, Determined, Discombobulated, Divined, Done, Effected,
Elucidated, Enchanted, Envisioned, Finagled, Flibbertigibbeted,
Forged, Formed, Frolicked, Generated, Germinated, Hatched, Herded,
Honked, Hustled, Ideated, Imagined, Incubated, Inferred, Jived,
Manifested, Marinated, Meandered, Moseyed, Mulled, Mustered, Mused,
Noodled, Percolated, Perused, Philosophised, Pondered, Pontificated,
Processed, Puttered, Puzzled, Reticulated, Ruminated, Sautéed,
Schemed, Schlepped, Shimmied, Shucked, Simmered, Smooshed, Spelunked,
Spun, Stewed, Sussed, Synthesized, Thought, Tinkered, Transmuted,
Unfurled, Unravelled, Vibed, Wandered, Whirred, Wibbled, Whisked,
Wizarded, Worked, Wrangled, ...
```

---

## 6. Turn Cycle Tracking

### 6.1 Turn Definition

A **turn** is one user command → Claude response cycle:

```
User: ❯ ls -la                    ← Turn Start (command detected)
Claude: ⠋ Processing...           ← Processing state
Claude: Here are the files...     ← Response
Claude: ✻ Baked for 5s            ← Turn Complete (marker detected)
User: ❯                           ← Idle, ready for next turn
```

### 6.2 Turn State Machine

```
                    ┌────────────────────────────────────┐
                    │                                    │
                    ▼                                    │
              ┌──────────┐                              │
              │  IDLE    │◀─────────────────────────────┤
              │          │                              │
              └────┬─────┘                              │
                   │                                    │
                   │ User sends command                 │
                   │ (detected: idle → processing)      │
                   │                                    │
                   ▼                                    │
              ┌──────────┐                              │
        ┌────▶│PROCESSING│                              │
        │     │          │                              │
        │     └────┬─────┘                              │
        │          │                                    │
        │          │ Claude finishes                    │
        │          │ (detected: processing → idle)      │
        │          │                   OR               │
        │          │ (detected: processing → input)     │
        │          │                                    │
        │          ├───────────────────────────────────►│
        │          │                                    │
        │          ▼                                    │
        │     ┌──────────┐                              │
        │     │  INPUT   │                              │
        │     │  NEEDED  │──────────────────────────────┘
        │     └──────────┘     User responds
        │          │
        │          │ User responds
        └──────────┘ (input → processing)
```

### 6.3 Turn Tracking Implementation

```python
@dataclass
class TurnState:
    turn_id: str              # UUID linking start/complete log entries
    command: str              # User's command that started the turn
    started_at: datetime      # When processing began
    previous_state: str       # State before processing
    logged_start: bool        # Prevent duplicate start logs
    logged_completion: bool   # Prevent duplicate completion logs

# In-memory tracking
_turn_tracking: dict[str, TurnState] = {}
_previous_activity_states: dict[str, str] = {}
_last_completed_turn: dict[str, dict] = {}

def track_turn_cycle(session_id: str, tmux_session: str,
                     current_state: str, content_tail: str) -> dict | None:
    """
    Track turn state transitions and log events.

    Returns turn data dict on completion, None otherwise.
    """
    previous_state = _previous_activity_states.get(session_id, "unknown")

    # Turn Start: idle/input_needed → processing
    if current_state == "processing" and previous_state in ("idle", "input_needed", "unknown"):
        turn_id = str(uuid.uuid4())
        command = extract_turn_command(content_tail)

        _turn_tracking[session_id] = TurnState(
            turn_id=turn_id,
            command=command,
            started_at=datetime.now(timezone.utc),
            previous_state=previous_state,
            logged_start=False,
            logged_completion=False,
        )

        _log_turn_start(session_id, tmux_session, turn_id, command)
        _turn_tracking[session_id].logged_start = True

    # Turn Complete: processing → idle/input_needed
    elif current_state in ("idle", "input_needed") and previous_state == "processing":
        turn_state = _turn_tracking.get(session_id)

        if turn_state and not turn_state.logged_completion:
            duration = (datetime.now(timezone.utc) - turn_state.started_at).total_seconds()
            completion_marker = extract_completion_marker(content_tail)
            response_summary = extract_last_message(content_tail)

            turn_data = {
                "turn_id": turn_state.turn_id,
                "command": turn_state.command,
                "result_state": current_state,
                "completion_marker": completion_marker,
                "duration_seconds": duration,
                "response_summary": response_summary,
            }

            _log_turn_completion(session_id, tmux_session, turn_data)
            _last_completed_turn[session_id] = turn_data
            turn_state.logged_completion = True

            # Signal priorities refresh
            emit_priorities_invalidation("turn_completed")

            return turn_data

    # Update previous state
    _previous_activity_states[session_id] = current_state
    return None
```

### 6.4 Command Extraction

```python
def extract_turn_command(content_tail: str) -> str:
    """Extract user's command from terminal content."""

    # Find last occurrence of prompt character
    prompt_index = content_tail.rfind("❯ ")
    if prompt_index == -1:
        return ""

    # Extract text after prompt until newline
    command_start = prompt_index + 2
    newline_index = content_tail.find("\n", command_start)

    if newline_index == -1:
        command = content_tail[command_start:]
    else:
        command = content_tail[command_start:newline_index]

    # Truncate long commands
    MAX_COMMAND_LENGTH = 200
    if len(command) > MAX_COMMAND_LENGTH:
        command = command[:MAX_COMMAND_LENGTH] + "..."

    return command.strip()
```

---

## 7. Logging System

### 7.1 tmux Log Storage

**File:** `data/logs/tmux.jsonl`
**Format:** JSON Lines (one JSON object per line)
**Rotation:** 10MB max, keeps 5 versions

### 7.2 Log Entry Structure

```python
@dataclass
class TmuxLogEntry:
    id: str                          # UUID for the log entry
    timestamp: str                   # ISO 8601 timestamp
    session_id: str                  # Project identifier (slug)
    tmux_session_name: str           # Full tmux session name
    direction: str                   # "in" (capture) or "out" (send)
    event_type: str                  # Type of operation
    payload: Optional[str]           # Content (None if debug disabled)
    correlation_id: Optional[str]    # Links related operations
    truncated: bool                  # Whether payload was truncated
    original_size: Optional[int]     # Original payload size
    success: bool                    # Whether operation succeeded
```

### 7.3 Event Types

| Event Type | Direction | Trigger | Payload |
|------------|-----------|---------|---------|
| `turn_start` | out | User command detected | `{turn_id, command, started_at}` |
| `turn_complete` | in | Claude response done | `{turn_id, result_state, duration_seconds, completion_marker, response_summary}` |
| `send_keys` | out | API sends text | Text sent |
| `capture_pane` | in | API captures output | Terminal content |
| `send_attempted` | out | Send (debug off) | None |
| `capture_attempted` | in | Capture (debug off) | None |

### 7.4 Correlation IDs

Turn start and complete events share a `correlation_id` (the `turn_id`), enabling reconstruction of complete turn cycles:

```json
{"event_type": "turn_start", "correlation_id": "abc-123", "payload": "{\"command\": \"ls\"}"}
{"event_type": "turn_complete", "correlation_id": "abc-123", "payload": "{\"duration_seconds\": 5.2}"}
```

### 7.5 Debug Toggle

**Config:** `tmux_logging.debug_enabled` in `config.yaml`

| Setting | Behavior |
|---------|----------|
| `false` (default) | Log event types only, no payload content |
| `true` | Log full payloads (truncated at 10KB) |

---

## 8. API Endpoints

### 8.1 Session Discovery

**GET /api/sessions**

Returns all active sessions with current state.

```json
{
  "sessions": [
    {
      "session_id": "87c165e4",
      "project_name": "my-project",
      "activity_state": "processing",
      "task_summary": "Adding dark mode",
      "turn_command": "claude add dark mode",
      "elapsed": "5m 30s",
      "last_activity_ago": "2s ago",
      "tmux_session": "claude-my-project-87c165e4",
      "session_type": "tmux"
    }
  ],
  "projects": [...]
}
```

### 8.2 Session Control

**POST /api/send/{session_id}**

Send text to a tmux session.

```bash
curl -X POST http://localhost:5050/api/send/87c165e4 \
  -H "Content-Type: application/json" \
  -d '{"text": "yes", "enter": true}'
```

**GET /api/output/{session_id}?lines=100**

Capture session output.

```bash
curl "http://localhost:5050/api/output/87c165e4?lines=200"
```

### 8.3 Window Focus

**POST /api/focus/{pid}** (legacy)
**POST /api/focus/tmux/{session_name}**

Focus iTerm window containing the session.

### 8.4 Logging

**GET /api/logs/tmux** - Get log entries
**GET /api/logs/tmux/stats** - Get statistics
**GET/POST /api/logs/tmux/debug** - Get/set debug toggle

---

## 9. Data Structures

### 9.1 Session Dict

Returned by `scan_sessions()` and `/api/sessions`:

```python
{
    # Identifiers
    "session_id": str,              # UUID or short hash
    "session_id_short": str,        # Last 8 chars
    "uuid": str,                    # Legacy alias

    # Project info
    "project_name": str,
    "project_dir": str,

    # Timing
    "started_at": str,              # ISO 8601
    "elapsed": str,                 # "5m", "2h 30m"
    "last_activity_at": str,        # ISO 8601
    "last_activity_ago": str,       # "2m ago"

    # Activity state
    "status": "active",
    "activity_state": str,          # processing/idle/input_needed/unknown
    "task_summary": str,            # From title or inferred
    "turn_command": str | None,     # Current/last command

    # Content
    "content_snippet": str,         # For AI summarization (1500 chars)
    "last_message": str,            # Last Claude response (500 chars)

    # tmux info
    "session_type": "tmux",
    "tmux_session": str,
    "tmux_attached": bool,

    # Process info
    "pid": int | None,
    "tty": str | None,
}
```

### 9.2 Priorities Cache

```python
{
    "priorities": [
        {
            "project_name": str,
            "session_id": str,
            "priority_score": int,      # 0-100
            "rationale": str,
            "activity_summary": str,
        },
        ...
    ],
    "timestamp": datetime,
    "content_hash": str,                # MD5 of session content
    "error": str | None,
}
```

---

## 10. Integration Points

### 10.1 Notification System

State changes trigger notifications via `check_state_changes_and_notify()`:

| Transition | Notification |
|------------|--------------|
| `processing` → `input_needed` | "Input needed!" (high priority) |
| `processing` → `idle` | "Task complete" |
| `idle` → `processing` | Optional: "Started working" |

### 10.2 Priority Computation

Turn completion triggers `emit_priorities_invalidation("turn_completed")`, which:
1. Marks priorities cache as stale
2. Next `/api/priorities` call recomputes via OpenRouter
3. Uses session states, headspace, and roadmaps for context

### 10.3 iTerm Focus

Focus mechanism:
1. Get TTY from tmux client or process PID
2. Query iTerm via AppleScript to find window with matching TTY
3. Focus window via AppleScript

```python
def focus_iterm_window_by_tmux_session(tmux_session: str) -> bool:
    tty = get_tmux_client_tty(tmux_session)
    if not tty:
        return False

    # AppleScript to find and focus window with matching TTY
    script = f'''
    tell application "iTerm"
        repeat with w in windows
            repeat with t in tabs of w
                repeat with s in sessions of t
                    if tty of s is "{tty}" then
                        select w
                        select t
                        select s
                        return true
                    end if
                end repeat
            end repeat
        end repeat
    end tell
    '''
    return run_applescript(script)
```

---

## 11. Known Issues & Limitations

### 11.1 Fundamental Architecture Issues

#### 11.1.1 Polling-Based Detection (Critical)

**Problem:** No event streaming from terminal. System relies on periodic snapshots.

**Impact:**
- **Race conditions**: Fast commands may start and complete between polls
- **Missed transitions**: State changes between polls are invisible
- **Detection lag**: Up to 2 seconds before state change is detected
- **Content scrolling**: Initial command may scroll off before first capture

**Example scenario:**
```
T+0.0s: User types "ls" and presses Enter
T+0.1s: Claude processes (spinner shown)
T+0.5s: Claude completes (completion marker shown)
T+1.0s: More output scrolls the completion marker off screen
T+2.0s: Poll happens → sees "idle" but missed the turn entirely
```

#### 11.1.2 Content Window Limits

**Problem:** Only captures last 200 lines of terminal.

**Impact:**
- Long outputs push important markers (completion, command) off screen
- Cannot reconstruct full conversation history
- Session summaries may be incomplete

#### 11.1.3 Pattern Matching Fragility

**Problem:** State detection relies on specific text patterns.

**Impact:**
- Claude Code UI changes can break detection
- Different Claude versions may use different patterns
- False positives from conversational text containing patterns
- False negatives when patterns don't match exactly

### 11.2 tmux-Specific Issues

#### 11.2.1 tmux Availability

**Problem:** Requires tmux to be installed.

**Impact:**
- Additional dependency for users
- Different tmux versions may behave differently
- tmux configuration can affect behavior

#### 11.2.2 Session Name Collisions

**Problem:** Relies on naming convention for discovery.

**Impact:**
- Non-monitored `claude-*` sessions could be picked up
- Hash collisions theoretically possible (unlikely with 8 chars)

#### 11.2.3 Detached Session State

**Problem:** tmux sessions can exist without attached clients.

**Impact:**
- Window focus doesn't work for detached sessions
- TTY matching fails without attached client

### 11.3 iTerm Integration Issues

#### 11.3.1 AppleScript Permissions

**Problem:** Requires macOS Automation permissions.

**Impact:**
- Users must manually grant permissions
- Permission prompts can be confusing
- Permissions can be revoked/break silently

#### 11.3.2 TTY Matching

**Problem:** Relies on TTY path matching between tmux and iTerm.

**Impact:**
- Can fail if TTY is reassigned
- Multiple iTerm windows with same TTY theoretically possible
- macOS sandboxing can affect TTY visibility

#### 11.3.3 macOS Only

**Problem:** AppleScript is macOS-only.

**Impact:**
- No Linux/Windows support
- No support for other terminal emulators

### 11.4 State Tracking Issues

#### 11.4.1 State Flicker

**Problem:** Rapid state transitions can cause duplicate logs.

**Mitigation:** `logged_start` and `logged_completion` flags prevent duplicates.

**Remaining issue:** Brief transitions may still be missed entirely.

#### 11.4.2 Stale State Files

**Problem:** State files can become orphaned.

**Mitigation:** `cleanup_stale_state_files()` removes orphans.

**Remaining issue:** Cleanup only runs during session scan.

### 11.5 Performance Issues

#### 11.5.1 Polling Overhead

**Problem:** Every poll executes multiple tmux commands.

**Impact:**
- CPU usage scales with number of sessions
- Network latency if tmux is remote
- Subprocess overhead per operation

#### 11.5.2 Content Hashing

**Problem:** MD5 hash computed on every poll for activity tracking.

**Impact:** Minor CPU overhead, acceptable for current scale.

### 11.6 Missing Features

| Feature | Status | Notes |
|---------|--------|-------|
| `is_claude_process(pid)` | Not implemented | Referenced but orphaned |
| Real-time streaming | Not supported | Would require different architecture |
| Full conversation history | Not stored | Only recent content captured |
| Cross-platform support | macOS only | AppleScript dependency |

---

## 12. Requirements for Replacement

Any terminal integration replacement (e.g., WezTerm) must address:

### 12.1 Must Have (Feature Parity)

| Requirement | Current Implementation | Notes |
|-------------|------------------------|-------|
| Session creation | `tmux new-session` | Create named, detached sessions |
| Send text | `tmux send-keys` | Send arbitrary text with optional Enter |
| Capture output | `tmux capture-pane` | Get terminal content (configurable lines) |
| Session listing | `tmux list-sessions` | Discover active sessions |
| Session termination | `tmux kill-session` | Clean shutdown |
| Window focus | AppleScript via TTY | Bring window to foreground |
| Named sessions | `claude-{slug}-{hash}` | Predictable, collision-resistant naming |

### 12.2 Should Have (Improvements)

| Requirement | Benefit | Notes |
|-------------|---------|-------|
| Event streaming | Eliminate polling latency | Real-time state updates |
| Full scrollback access | Complete conversation history | Not limited to N lines |
| Native window control | Remove AppleScript dependency | Direct focus API |
| Cross-platform | Linux/Windows support | Broader user base |
| Structured output | Reliable parsing | Not dependent on text patterns |

### 12.3 Nice to Have (Enhancements)

| Requirement | Benefit | Notes |
|-------------|---------|-------|
| Built-in logging | Native audit trail | Not reconstructed from captures |
| Session metadata API | Rich session info | Beyond what tmux provides |
| Scriptable hooks | Event-driven architecture | On content change, on exit, etc. |
| Split pane support | Multiple views | Side-by-side sessions |

### 12.4 Migration Considerations

1. **Backwards compatibility**: Support existing tmux sessions during transition
2. **Configuration migration**: Map tmux config to new system
3. **State file compatibility**: Maintain or migrate state file format
4. **API stability**: Keep `/api/send` and `/api/output` interfaces stable
5. **Logging continuity**: Preserve log format for historical data

---

## 13. References

### 13.1 Sequence Diagrams

- [Turn Cycle Sequence Diagram](./turn-cycle-sequence.md) - Complete end-to-end flow

### 13.2 PRDs

| PRD | Location | Relevance |
|-----|----------|-----------|
| tmux Session Logging | `docs/prds/tmux/done/tmux-session-logging-prd.md` | Logging specification |
| Session Summarisation | `docs/prds/headspace/done/e1_s3_session-summarisation-prd.md` | Content processing |
| AI Prioritisation | `docs/prds/headspace/done/e1_s7_ai-prioritisation-prd.md` | Priority computation |

### 13.3 User Documentation

- [README.md](../../README.md) - User-facing documentation
- [CLAUDE.md](../../CLAUDE.md) - Developer guide

### 13.4 Source Files

| File | Purpose |
|------|---------|
| `lib/tmux.py` | tmux operations |
| `lib/sessions.py` | Session discovery, state parsing, turn tracking |
| `lib/tmux_logging.py` | Structured logging |
| `lib/iterm.py` | iTerm focus via AppleScript |
| `lib/notifications.py` | State change notifications |
| `lib/headspace.py` | Priority computation |
| `bin/claude-monitor` | Session wrapper script |
| `monitor.py` | Flask app, API endpoints |

### 13.5 Test Files

| File | Coverage |
|------|----------|
| `test_tmux.py` | tmux module functions |
| `test_sessions.py` | Session scanning, activity detection |
| `test_tmux_logging.py` | Logging functionality |
| `test_e2e.py` | End-to-end integration |
