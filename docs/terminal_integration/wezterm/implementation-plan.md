# WezTerm Integration Implementation Plan

## Overview

WezTerm is an alternative terminal backend for Claude Headspace Monitor, enabling cross-platform support and improved capabilities over tmux.

**Reference Specification:** `docs/terminal_integration/turn-cycle-specification.md`

---

## Architecture

### Backend Abstraction Layer

The backend abstraction layer (`lib/backends/`) provides a common interface:

```
lib/
├── backends/
│   ├── __init__.py          # Backend factory
│   ├── base.py              # Abstract interface
│   ├── tmux.py              # Refactored tmux backend
│   └── wezterm.py           # WezTerm backend
```

### Interface Contract

Both backends implement the `TerminalBackend` abstract class:

| Method | Description |
|--------|-------------|
| `is_available()` | Check if backend is installed |
| `list_sessions()` | List all sessions |
| `session_exists(name)` | Verify session exists |
| `get_claude_sessions()` | Filter to `claude-*` pattern |
| `create_session(name, dir, cmd)` | Create detached session |
| `kill_session(name)` | Terminate session |
| `send_keys(session, text, enter)` | Send text to session |
| `capture_pane(session, lines)` | Get terminal content |
| `get_session_info(name)` | Get PID, TTY, path |
| `focus_window(session)` | Bring window to foreground |

### WezTerm CLI Mappings

| Function | WezTerm Command |
|----------|-----------------|
| `list_sessions()` | `wezterm cli list --format json` |
| `create_session()` | `wezterm cli spawn --new-window --workspace claude-monitor` |
| `send_keys()` | `wezterm cli send-text --pane-id X --no-paste` |
| `capture_pane()` | `wezterm cli get-text --pane-id X --start-line -N` |
| `focus_window()` | `wezterm cli activate-pane --pane-id X` |
| `kill_session()` | `wezterm cli kill-pane --pane-id X` |

---

## Key Implementation Details

### Session Naming

WezTerm uses numeric pane IDs, not named sessions. Session names are mapped via window titles:

1. Session name pattern: `claude-{slug}-{hash}`
2. Window title is set via escape sequence: `\033]0;{session_name}\007`
3. A pane-id to session-name mapping cache is maintained

### Workspace Grouping

All Claude sessions are grouped in a WezTerm workspace (default: `claude-monitor`), making them easy to identify and manage.

### Full Scrollback Access

Unlike tmux's default 2000-line limit, WezTerm provides full scrollback history access via `wezterm cli get-text`.

---

## Configuration

```yaml
# Choose which terminal backend to use
terminal_backend: "tmux"  # or "wezterm"

# WezTerm-specific settings
wezterm:
  workspace: "claude-monitor"  # Workspace name for grouping sessions
  full_scrollback: true        # Enable full scrollback capture
```

Per-project override:
```yaml
projects:
  - name: "my-project"
    path: "/path/to/project"
    terminal_backend: "wezterm"  # Override for this project only
```

---

## Files

| File | Purpose |
|------|---------|
| `lib/backends/__init__.py` | Backend factory with `get_backend()` |
| `lib/backends/base.py` | Abstract `TerminalBackend` class and `SessionInfo` dataclass |
| `lib/backends/tmux.py` | Tmux implementation |
| `lib/backends/wezterm.py` | WezTerm implementation |
| `lib/tmux.py` | Backwards-compatible forwarding |
| `bin/claude-monitor` | Wrapper script supporting both backends |
| `test_wezterm.py` | Unit tests for WezTerm backend |

---

## Usage

### Command Line

```bash
# Use configured backend (default: tmux)
claude-monitor start

# Explicitly use WezTerm
claude-monitor start --wezterm

# Explicitly use tmux
claude-monitor start --tmux
```

### Prerequisites

- **tmux:** `brew install tmux`
- **WezTerm:** `brew install --cask wezterm`

---

## Testing

```bash
# Run WezTerm tests
pytest test_wezterm.py -v

# Run all backend tests
pytest test_tmux.py test_wezterm.py -v
```

---

## Comparison: tmux vs WezTerm

| Feature | tmux | WezTerm |
|---------|------|---------|
| Platform | macOS, Linux | macOS, Linux, Windows |
| Installation | `brew install tmux` | `brew install --cask wezterm` |
| Session naming | Native session names | Window titles + pane IDs |
| Scrollback | Configurable (default 2000 lines) | Full scrollback access |
| Window focus | AppleScript (macOS only) | Native CLI (`activate-pane`) |
| Mouse support | Requires configuration | Native |
| Session persistence | Survives terminal close | Requires WezTerm running |

---

## Migration Path

1. **Phase 1 (Complete):** Backend abstraction layer with tmux as default
2. **Phase 2 (Complete):** WezTerm implementation as opt-in
3. **Phase 3:** Documentation and testing
4. **Future:** Consider WezTerm as default (if proven stable)
