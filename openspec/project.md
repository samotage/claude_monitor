# Claude Headspace - Project Specification

## Overview

Claude Headspace is a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects. It monitors iTerm windows and displays real-time session status with click-to-focus functionality and native macOS notifications.

### Key Features
- Track active Claude Code sessions across projects
- Display session status (processing/input needed/idle) in a visual dashboard
- Click-to-focus: bring iTerm windows to foreground from the dashboard
- Native macOS notifications when input is needed or tasks complete
- Auto-refresh to keep status current

## Tech Stack

| Component | Technology | Version/Notes |
|-----------|------------|---------------|
| Language | Python | 3.10+ |
| Web Framework | Flask | Lightweight, single-file app |
| Configuration | PyYAML | config.yaml format |
| macOS Integration | AppleScript | Via osascript subprocess |
| Notifications | terminal-notifier | Installed via Homebrew |
| Frontend | Vanilla JS/CSS | No external dependencies |

## Architecture

### Single-File Application
All code resides in `monitor.py`, including:
- Flask routes and API endpoints
- HTML/CSS/JS templates (embedded)
- AppleScript integration
- Session scanning logic

### Data Flow
```
State Files (.claude-monitor-*.json)
         ↓
    scan_sessions()
         ↓
    get_iterm_windows() ← AppleScript
         ↓
    parse_activity_state()
         ↓
    Dashboard / API / Notifications
```

### No Database
All state is read from:
- Filesystem (state files in project directories)
- iTerm (via AppleScript at request time)

## Directory Structure

```
claude_monitor/
├── monitor.py           # Main application (all-in-one)
├── install.sh           # Installation script
├── restart_server.sh    # Server restart script
├── config.yaml          # User configuration (gitignored)
├── config.yaml.example  # Configuration template
├── requirements.txt     # Python dependencies
├── bin/
│   └── claude-monitor   # Session wrapper script
├── venv/                # Python virtual environment
├── .claude/             # Claude Code configuration
├── openspec/            # Project specifications
├── CLAUDE.md            # AI assistant guide
├── README.md            # User documentation
└── LICENSE              # MIT license
```

## API Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Main Kanban dashboard |
| `/api/sessions` | GET | JSON list of all sessions |
| `/api/focus/<pid>` | POST | Focus iTerm window by process ID |
| `/api/config` | GET/POST | Read/write configuration |
| `/api/notifications` | GET/POST | Notification enable/disable |
| `/api/notifications/test` | POST | Send test notification |

## Key Functions

| Function | Purpose |
|----------|---------|
| `scan_sessions()` | Scan project directories for session state files |
| `get_iterm_windows()` | Map iTerm sessions by TTY via AppleScript |
| `get_pid_tty()` | Get TTY for a given process ID |
| `parse_activity_state()` | Determine session state (processing/input_needed/idle) |
| `focus_iterm_window_by_pid()` | Bring iTerm window to foreground |
| `send_macos_notification()` | Send notification via terminal-notifier |
| `check_state_changes_and_notify()` | Track changes and trigger notifications |

## Conventions

### Code Style
- Single-file architecture for simplicity
- Embedded templates (no separate template files)
- AppleScript calls wrapped with timeouts to prevent hangs

### Configuration
- User config in `config.yaml` (gitignored)
- Template provided as `config.yaml.example`
- Projects defined with name and absolute path

### Server
- Runs on port 5050 (not default 5000)
- Debug mode disabled by default
- Use `./restart_server.sh` for restarts

### Testing
```bash
pytest                # Run all tests
pytest --cov=.        # With coverage
```

## Platform Requirements

- **macOS only** (AppleScript/iTerm integration)
- iTerm2 terminal emulator
- terminal-notifier (via Homebrew)
- System Preferences permissions for Automation

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the monitor
python monitor.py
# Dashboard at http://localhost:5050

# Restart server after changes
./restart_server.sh

# Start a monitored Claude session (in project directory)
claude-monitor start
```

## State Management

### Session State Files
Created by `claude-monitor start` wrapper in project directories:
- Format: `.claude-monitor-*.json`
- Contains PID and session metadata
- Used to match running processes to iTerm windows

### Activity Detection
Terminal content analyzed to determine:
- `processing` - Claude is working
- `input_needed` - Waiting for user input
- `idle` - Session inactive
