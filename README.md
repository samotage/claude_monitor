# Claude Monitor

A Kanban-style dashboard for tracking Claude Code sessions across multiple projects.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![macOS](https://img.shields.io/badge/platform-macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

Claude Monitor provides a unified view of all your active Claude Code sessions. When running multiple Claude Code instances across different projects, this dashboard lets you:

- See all active sessions at a glance
- Track which project each session is working on
- View task summaries from iTerm window titles
- Click to focus any session's iTerm window
- Monitor session duration and status

## Requirements

- macOS (uses AppleScript for iTerm integration)
- iTerm2 terminal
- Python 3.10+
- Claude Code CLI

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd claude_monitor
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up the wrapper script:**
   ```bash
   # Copy to a directory in your PATH
   cp /Users/samotage/bin/dev-monitor ~/bin/
   chmod +x ~/bin/dev-monitor

   # Ensure ~/bin is in your PATH
   export PATH="$HOME/bin:$PATH"
   ```

4. **Configure your projects** in `config.yaml`:
   ```yaml
   projects:
     - name: "my-project"
       path: "/path/to/my-project"
     - name: "another-project"
       path: "/path/to/another-project"

   scan_interval: 2  # seconds
   ```

## Usage

### Start the Dashboard

```bash
python monitor.py
```

Then open http://localhost:5050 in your browser.

### Launch a Monitored Claude Code Session

Instead of running `claude` directly, use the wrapper:

```bash
cd /path/to/your/project
dev-monitor start
```

This will:
1. Generate a unique session UUID
2. Create a state file (`.claude-monitor-<uuid>.json`)
3. Launch Claude Code with the UUID in the environment
4. Clean up the state file when the session ends

### Dashboard Features

- **Project Columns:** Sessions are grouped by project
- **Session Cards:** Each card shows:
  - Short UUID (last 8 characters)
  - Task summary (from iTerm window title)
  - Elapsed time
  - Status (active/completed)
- **Click to Focus:** Click any card to bring that iTerm window to the foreground
- **Auto-refresh:** Dashboard updates every 2 seconds

## How It Works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  dev-monitor    │────▶│  State File      │◀────│  Monitor App    │
│  start          │     │  (.claude-       │     │  (Flask)        │
│                 │     │   monitor-*.json)│     │                 │
└────────┬────────┘     └──────────────────┘     └────────┬────────┘
         │                                                │
         ▼                                                ▼
┌─────────────────┐                              ┌─────────────────┐
│  Claude Code    │                              │  iTerm Windows  │
│  (with UUID)    │─────────────────────────────▶│  (AppleScript)  │
└─────────────────┘      updates title           └─────────────────┘
```

1. **Wrapper Script:** Creates a state file with session metadata and launches Claude Code
2. **State Files:** JSON files in project directories track session info (UUID, start time, PID)
3. **iTerm Titles:** Claude Code updates the window title as it works
4. **Monitor App:** Scans state files and matches UUIDs to iTerm windows
5. **Dashboard:** Displays sessions in a Kanban view with real-time updates

## Configuration

### config.yaml

```yaml
projects:
  - name: "display-name"
    path: "/absolute/path/to/project"

scan_interval: 2          # How often to refresh (seconds)
iterm_focus_delay: 0.1    # Delay before focusing window (seconds)
```

### Adding New Projects

Edit `config.yaml` and add your project:

```yaml
projects:
  - name: "new-project"
    path: "/Users/you/dev/new-project"
```

The monitor will pick up changes on the next scan.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/api/sessions` | GET | JSON list of all sessions |
| `/api/focus/<uuid>` | POST | Focus iTerm window by UUID |

### Example API Response

```json
{
  "sessions": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "uuid_short": "55440000",
      "project_name": "my-project",
      "status": "active",
      "task_summary": "Implementing user auth",
      "elapsed": "15m",
      "started_at": "2026-01-19T10:30:00Z"
    }
  ],
  "projects": [...]
}
```

## Troubleshooting

### "No sessions showing"

- Ensure you're using `dev-monitor start` instead of `claude` directly
- Check that the project directory is listed in `config.yaml`
- Verify the state file exists: `ls -la .claude-monitor-*.json`

### "Click to focus not working"

macOS requires automation permissions:
1. Open System Preferences → Privacy & Security → Automation
2. Ensure your terminal/IDE has permission to control iTerm

Test AppleScript access:
```bash
osascript -e 'tell application "iTerm" to get name of windows'
```

### "Port 5050 already in use"

Find and kill the existing process:
```bash
lsof -i :5050
kill <PID>
```

## Development

### Project Structure

```
claude_monitor/
├── monitor.py          # Main Flask application
├── config.yaml         # Project configuration
├── requirements.txt    # Python dependencies
├── CLAUDE.md           # AI assistant guide
└── .claude/            # Claude Code settings
    ├── settings.json
    └── rules/
        └── ai-guardrails.md
```

### Running Tests

```bash
pytest
pytest --cov=.  # With coverage
```

## License

MIT
