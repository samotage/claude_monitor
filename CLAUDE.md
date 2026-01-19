# CLAUDE.md - Claude Monitor Project Guide

## Project Overview

Claude Monitor is a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects. It monitors iTerm windows and displays real-time session status with click-to-focus functionality.

**Purpose:**
- Track active Claude Code sessions across projects
- Display session status (active/completed) in a visual dashboard
- Click-to-focus: bring iTerm windows to foreground from the dashboard
- Auto-refresh to keep status current

## Tech Stack

- **Python:** 3.14+
- **Framework:** Flask
- **Config:** PyYAML
- **macOS Integration:** AppleScript via osascript subprocess

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the monitor
python monitor.py
# Dashboard available at http://localhost:5050

# Restart the server (use this!)
./restart_server.sh

# Run tests (when added)
pytest
pytest --cov=.  # With coverage
```

## Directory Structure

```
claude_monitor/
├── monitor.py          # Main application (all-in-one Flask app)
├── restart_server.sh   # Script to restart the Flask server
├── config.yaml         # Project paths and settings
├── requirements.txt    # Python dependencies
├── venv/               # Python 3.14 virtual environment
├── .claude/            # Claude Code configuration
│   ├── settings.json       # Permissions for bash commands
│   ├── settings.local.json # Local-only permissions (git)
│   └── rules/
│       └── ai-guardrails.md # AI behavior rules
└── CLAUDE.md           # This file
```

## Configuration

Edit `config.yaml` to configure monitored projects:

```yaml
projects:
  - name: "project_name"
    path: "/absolute/path/to/project"

scan_interval: 2          # Refresh interval in seconds
iterm_focus_delay: 0.1    # Delay before focusing window
```

## How It Works

1. **State Files:** Claude Code sessions write `.claude-monitor-*.json` files in project directories
2. **PID/TTY Matching:** The monitor reads the PID from state files, finds its TTY, and matches to iTerm sessions
3. **Status Detection:** Sessions with matching iTerm windows are "active"; others are "completed"
4. **Focus Feature:** Clicking a card runs AppleScript to bring that iTerm window to foreground

## Key Functions

| Function | Purpose |
|----------|---------|
| `scan_sessions()` | Scan all project directories for session state files |
| `get_iterm_windows()` | Get iTerm sessions mapped by TTY via AppleScript |
| `get_pid_tty()` | Get the TTY for a given process ID |
| `focus_iterm_window_by_pid()` | Bring iTerm window to foreground by matching PID to TTY |
| `extract_task_summary()` | Parse task info from window title |

## API Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Main Kanban dashboard |
| `/api/sessions` | GET | JSON list of all sessions |
| `/api/focus/<pid>` | POST | Focus iTerm window by process ID |

## Notes for AI Assistants

- **Single-file application:** All code is in `monitor.py` including HTML/CSS/JS template
- **macOS-only:** AppleScript integration requires macOS with iTerm2
- **State files:** Created by Claude Code hooks, not this application
- **No database:** All state is read from filesystem and iTerm at request time

### Development Tips

- The Flask app runs on port 5050 (not the default 5000)
- Debug mode is disabled by default for cleaner output
- AppleScript calls have 5-second timeouts to prevent hangs
- The HTML template uses vanilla JS with no external dependencies

### Testing AppleScript

Test AppleScript commands manually before modifying:
```bash
osascript -e 'tell application "iTerm" to get name of windows'
```

If permissions errors occur, check System Preferences → Privacy & Security → Automation.

### Auto-Restart Server

When making changes that require a server restart, **use the restart script**:
```bash
./restart_server.sh
```

**DO NOT** create your own restart commands. The script handles everything: kills old process, activates venv, starts new one, verifies it's running.
