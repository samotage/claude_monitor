<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# CLAUDE.md - Claude Headspace Project Guide

## Project Overview

Claude Headspace is a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects. It monitors iTerm windows and displays real-time session status with click-to-focus functionality and native macOS notifications.

**Purpose:**
- Track active Claude Code sessions across projects
- Display session status (processing/input needed/idle) in a visual dashboard
- Click-to-focus: bring iTerm windows to foreground from the dashboard
- Native macOS notifications when input is needed or tasks complete
- Auto-refresh to keep status current

## Tech Stack

- **Python:** 3.10+
- **Framework:** Flask
- **Config:** PyYAML
- **macOS Integration:** AppleScript via osascript subprocess
- **Notifications:** terminal-notifier

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the monitor
python monitor.py
# Dashboard available at http://localhost:5050

# Restart the server
./restart_server.sh

# Run tests
pytest
pytest --cov=.  # With coverage

# Start a monitored Claude session (in your project directory)
claude-monitor start
```

## Directory Structure

```
claude_monitor/
├── monitor.py           # Main application (all-in-one Flask app)
├── install.sh           # Installation script
├── restart_server.sh    # Script to restart the Flask server
├── config.yaml.example  # Configuration template
├── config.yaml          # User configuration (gitignored)
├── requirements.txt     # Python dependencies
├── bin/
│   └── claude-monitor   # Session wrapper script
├── venv/                # Python virtual environment
├── orch/                # PRD orchestration Ruby scripts
│   ├── orchestrator.rb  # Main dispatcher
│   ├── commands/        # Command implementations
│   ├── working/         # State files (gitignored)
│   └── log/             # Log files (gitignored)
├── docs/
│   └── prds/            # PRD documents by subsystem
├── .claude/
│   ├── settings.json    # Permissions for bash commands
│   └── commands/
│       ├── openspec/    # OpenSpec commands
│       └── otl/         # PRD orchestration commands
├── CLAUDE.md            # This file
├── README.md            # User documentation
└── LICENSE              # MIT license
```

## Configuration

Edit `config.yaml` to configure monitored projects:

```yaml
projects:
  - name: "project_name"
    path: "/absolute/path/to/project"

scan_interval: 5          # Refresh interval in seconds
iterm_focus_delay: 0.1    # Delay before focusing window
```

## How It Works

1. **State Files:** The `claude-monitor start` wrapper creates `.claude-monitor-*.json` files in project directories
2. **PID/TTY Matching:** The monitor reads the PID from state files, finds its TTY, and matches to iTerm sessions
3. **Activity Detection:** Terminal content is analyzed to detect if Claude is processing, idle, or waiting for input
4. **Status Detection:** Sessions with matching iTerm windows are "active"; others are hidden
5. **Notifications:** State changes trigger macOS notifications via terminal-notifier
6. **Focus Feature:** Clicking a card or notification runs AppleScript to bring that iTerm window to foreground

## Key Functions

| Function | Purpose |
|----------|---------|
| `scan_sessions()` | Scan all project directories for session state files |
| `get_iterm_windows()` | Get iTerm sessions mapped by TTY via AppleScript |
| `get_pid_tty()` | Get the TTY for a given process ID |
| `parse_activity_state()` | Determine if session is processing/input_needed/idle |
| `focus_iterm_window_by_pid()` | Bring iTerm window to foreground by matching PID to TTY |
| `send_macos_notification()` | Send notification via terminal-notifier |
| `check_state_changes_and_notify()` | Track state changes and trigger notifications |

## API Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Main Kanban dashboard |
| `/api/sessions` | GET | JSON list of all sessions |
| `/api/focus/<pid>` | POST | Focus iTerm window by process ID |
| `/api/config` | GET/POST | Read/write configuration |
| `/api/notifications` | GET/POST | Notification enable/disable |
| `/api/notifications/test` | POST | Send test notification |

## Notes for AI Assistants

- **Single-file application:** All code is in `monitor.py` including HTML/CSS/JS template
- **macOS-only:** AppleScript integration requires macOS with iTerm2
- **State files:** Created by `claude-monitor start` wrapper, not this application
- **No database:** All state is read from filesystem and iTerm at request time
- **Notifications:** Require terminal-notifier to be installed via Homebrew

### Development Tips

- The Flask app runs on port 5050 (not the default 5000)
- Debug mode is disabled by default for cleaner output
- AppleScript calls have timeouts to prevent hangs
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

The script handles everything: kills old process, activates venv, starts new one, verifies it's running.

## PRD Orchestration System

This project includes a PRD-driven development orchestration system for managing feature development through a structured pipeline.

### Orchestration Overview

The system uses Ruby scripts (`orch/`) with Claude Code commands (`.claude/commands/otl/`) to automate:

1. **PRD Workshop** - Create and validate PRDs
2. **Queue Management** - Batch processing of multiple PRDs
3. **Proposal Generation** - Create OpenSpec change proposals from PRDs
4. **Build Phase** - Implement changes with AI assistance
5. **Test Phase** - Run pytest with auto-retry (Ralph loop)
6. **Validation** - Verify implementation matches spec
7. **Finalize** - Commit, create PR, and merge

### Git Workflow

```
development (base) → feature/change-name → PR → development
```

- Feature branches are created FROM `development`
- PRs target `development` branch
- `main` is the stable/release branch

### Key Commands

```bash
# PRD Management
/10: prd-workshop      # Create/remediate PRDs
/20: prd-list          # List pending PRDs
/30: prd-validate      # Quality gate validation

# Orchestration (from development branch)
/10: queue-add         # Add PRDs to queue
/20: prd-orchestrate   # Start queue processing

# Ruby CLI (direct access)
ruby orch/orchestrator.rb status      # Show current state
ruby orch/orchestrator.rb queue list  # List queue items
ruby orch/prd_validator.rb list-all   # List PRDs with validation status
```

### Orchestration Directories

```
orch/
├── orchestrator.rb      # Main orchestration dispatcher
├── state_manager.rb     # State persistence
├── queue_manager.rb     # Queue operations
├── prd_validator.rb     # PRD validation
├── config.yaml          # Orchestration config
├── commands/            # Ruby command implementations
├── working/             # State/queue files (gitignored)
└── log/                 # Log files (gitignored)

.claude/commands/otl/
├── prds/                # PRD management commands
└── orch/                # Orchestration commands
```

### PRD Location

PRDs are stored in `docs/prds/{subsystem}/`:

```
docs/prds/
├── dashboard/
│   ├── voice-bridge-prd.md
│   └── done/            # Completed PRDs
└── notifications/
    └── slack-integration-prd.md
```

### Running the Orchestration

1. Create a PRD in `docs/prds/{subsystem}/`
2. Run `/10: prd-workshop` to validate
3. Switch to `development` branch
4. Run `/10: queue-add` to add to queue
5. Run `/20: prd-orchestrate` to start processing

See `.claude/commands/otl/README.md` for detailed documentation.
