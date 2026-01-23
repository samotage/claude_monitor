# Design: tmux Session Router

## Context

The Claude Monitor currently uses AppleScript to interact with iTerm2 terminals running Claude Code sessions. This provides:
- Session enumeration (windows, tabs, sessions by TTY)
- Content capture (last 5000 chars via `text of session`)
- Window focus (`select` commands)

However, AppleScript cannot reliably **send input** to sessions. Keystroke injection is fragile, timing-dependent, and requires Accessibility permissions.

tmux provides a robust alternative for bidirectional communication with terminal sessions.

## Goals

- Enable sending text/commands to Claude Code sessions
- Capture full terminal output (beyond 5000 char limit)
- Maintain backwards compatibility with iTerm-only workflows
- Establish foundation for voice bridge and usage tracking features

## Non-Goals

- Replace iTerm integration entirely (still needed for GUI focus)
- Support non-macOS platforms (macOS-only for now)
- Automatic migration of existing sessions to tmux

## Decisions

### Decision 1: Hybrid Architecture (tmux + iTerm)

**Choice**: Support both tmux and iTerm sessions concurrently.

**Rationale**:
- Users may have existing iTerm workflows they don't want to change
- iTerm is still needed for GUI operations (focus, bring to front)
- Gradual adoption path - users can opt into tmux when ready

**Implementation**:
```
Session Router
├── tmux sessions → full control (read + write)
└── iTerm sessions → read-only (observe + focus)
```

### Decision 2: Named tmux Sessions

**Choice**: Use predictable session names: `claude-<project-slug>`

**Rationale**:
- Direct addressing without PID→TTY lookup chain
- Survives process restarts (tmux session persists)
- Easy to list and manage (`tmux ls`)

**Format**: `claude-{project_name}` where project_name is slugified (lowercase, hyphens)

### Decision 3: Wrapper Creates tmux Session

**Choice**: `claude-monitor start` creates tmux session, then runs claude inside it.

**Rationale**:
- Single entry point for monitored sessions
- Consistent naming convention
- State file can record tmux session name

**Alternative considered**: Detect existing tmux sessions automatically.
**Rejected**: Harder to ensure consistent naming, may conflict with user's tmux setup.

### Decision 4: API Endpoints for Remote Control

**Choice**: New REST endpoints for send/capture operations.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/send/<session_id>` | POST | Send text to session |
| `/api/output/<session_id>` | GET | Capture recent output |

**Rationale**:
- Enables voice bridge (HTTP-based control)
- Enables dashboard UI buttons (approve, send message)
- Consistent with existing API patterns

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Claude Monitor                        │
├─────────────────────────────────────────────────────────┤
│  Session Scanner (lib/sessions.py)                       │
│  ├── scan_tmux_sessions() ──────────┐                   │
│  └── scan_iterm_sessions() ─────────┼─→ merged list     │
├─────────────────────────────────────────────────────────┤
│  tmux Router (lib/tmux.py) - NEW                        │
│  ├── list_sessions()                                    │
│  ├── send_keys(session, text)                           │
│  ├── capture_pane(session, lines)                       │
│  └── session_exists(session)                            │
├─────────────────────────────────────────────────────────┤
│  iTerm Integration (lib/iterm.py) - UNCHANGED           │
│  ├── get_iterm_windows()                                │
│  ├── focus_iterm_window_by_pid()                        │
│  └── get_pid_tty()                                      │
├─────────────────────────────────────────────────────────┤
│  API Endpoints (monitor.py)                             │
│  ├── /api/sessions (existing)                           │
│  ├── /api/focus/<pid> (existing)                        │
│  ├── /api/send/<session_id> (NEW)                       │
│  └── /api/output/<session_id> (NEW)                     │
└─────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
    ┌─────────────┐                ┌─────────────┐
    │    tmux     │                │   iTerm2    │
    │  sessions   │                │  (GUI only) │
    └─────────────┘                └─────────────┘
```

## tmux Commands Used

| Operation | Command | Notes |
|-----------|---------|-------|
| List sessions | `tmux list-sessions -F "#{session_name}"` | Get session names |
| Check exists | `tmux has-session -t <name>` | Returns 0 if exists |
| Send text | `tmux send-keys -t <name> "<text>" Enter` | Inject input |
| Capture output | `tmux capture-pane -t <name> -p -S -<lines>` | Get scrollback |
| Create session | `tmux new-session -d -s <name> -c <path>` | Detached, named |
| Kill session | `tmux kill-session -t <name>` | Cleanup |

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| User must run Claude in tmux | Clear documentation, wrapper handles it |
| tmux not installed | Check on startup, provide install instructions |
| Session name collisions | Use project-slug naming, check before create |
| Send-keys timing issues | Add small delay option if needed |

## Migration Plan

1. **Phase 1**: Add tmux module and API endpoints (this change)
2. **Phase 2**: Update wrapper to create tmux sessions by default
3. **Phase 3**: Update dashboard UI to show send/control buttons for tmux sessions
4. **Future**: Voice bridge integration

No breaking changes to existing iTerm workflows.

## Open Questions

1. Should we support running Claude Code in existing user-created tmux sessions? (Defer - start with wrapper-created sessions)
2. Should capture-pane output be cached? (Defer - implement if performance issues arise)
