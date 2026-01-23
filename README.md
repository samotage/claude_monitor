# Claude Headspace

A Kanban-style dashboard for tracking Claude Code sessions across multiple projects, with native macOS notifications.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![macOS](https://img.shields.io/badge/platform-macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Multi-project dashboard** - See all active Claude Code sessions at a glance
- **Activity states** - Know when Claude is working, idle, or needs your input
- **Native notifications** - Get macOS alerts when input is needed or tasks complete
- **Click-to-focus** - Jump to any session from the dashboard or notification
- **Real-time updates** - Dashboard refreshes automatically
- **tmux integration** - Bidirectional session control with send/capture APIs

## Quick Start

```bash
# Clone and install
git clone https://github.com/otagelabs/claude-monitor.git
cd claude-monitor
./install.sh

# Add your projects to config.yaml, then:
source venv/bin/activate
python monitor.py

# In another terminal, start a monitored Claude session:
cd /path/to/your/project
claude-monitor start
```

Open http://localhost:5050 in your browser.

> **Tip:** You can ask Claude Code to help you set this up! Just share this README and ask for assistance.

## Requirements

- **macOS** (uses AppleScript for iTerm integration)
- **iTerm2** terminal
- **Python 3.10+**
- **Claude Code CLI**
- **tmux** (default session mode, install with `brew install tmux`)
- **Homebrew** (optional, for notifications)

## Installation

### Automated Setup

Run the install script:

```bash
./install.sh
```

This will:
1. Check all requirements
2. Install `terminal-notifier` (for notifications)
3. Create a Python virtual environment
4. Install dependencies
5. Set up the `claude-monitor` command
6. Create your config file

### Manual Setup

If you prefer manual installation:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install terminal-notifier for notifications
brew install terminal-notifier

# Copy config template
cp config.yaml.example config.yaml

# Add claude-monitor to your PATH
ln -s "$(pwd)/bin/claude-monitor" ~/bin/claude-monitor
```

## Configuration

Edit `config.yaml` to add your projects:

```yaml
projects:
  - name: "my-app"
    path: "/Users/you/dev/my-app"
    # tmux is enabled by default

  - name: "api-service"
    path: "/Users/you/dev/api-service"
    tmux: false          # Disable tmux to use iTerm mode

scan_interval: 5        # Dashboard refresh rate (seconds)
iterm_focus_delay: 0.1  # Delay before focusing window
```

## Usage

### Start the Dashboard

```bash
cd /path/to/claude-monitor
source venv/bin/activate
python monitor.py
```

The dashboard will be available at http://localhost:5050

### Launch a Monitored Session

Instead of running `claude` directly, use the wrapper:

```bash
cd /path/to/your/project
claude-monitor start           # Default: runs in tmux
claude-monitor start --iterm   # Force iTerm mode (read-only)
```

This creates a state file that the dashboard uses to track the session.

### Dashboard Features

| Feature | Description |
|---------|-------------|
| **Project columns** | Sessions grouped by project |
| **Activity states** | Processing, Input Needed, Idle |
| **Click to focus** | Click any card to switch to that terminal |
| **Notifications** | Toggle in Settings tab |
| **Auto-hide** | Empty projects are hidden automatically |

### Activity States

| State | Indicator | Meaning |
|-------|-----------|---------|
| **Processing** | Green spinner | Claude is working |
| **Input Needed** | Amber highlight | Waiting for your response |
| **Idle** | Blue | Ready for a new task |

### Notifications

When enabled, you'll receive macOS notifications:

- **Input Needed** - When Claude asks a question or needs permission
- **Task Complete** - When processing finishes

Click the notification to jump directly to that iTerm session.

Enable/disable notifications in the Settings tab of the dashboard.

### tmux Integration

tmux is the **default session mode**, enabling bidirectional control of Claude Code sessions. You can send text to sessions and capture full output programmatically. This is the foundation for features like voice bridge and remote control.

**Setup:**
1. Install tmux: `brew install tmux`
2. Run `claude-monitor start` (tmux is used by default)
3. Sessions run inside named tmux sessions (`claude-<project-name>`)

**Session Control APIs:**

```bash
# Send text to a session (tmux only)
curl -X POST http://localhost:5050/api/send/<session_id> \
  -H "Content-Type: application/json" \
  -d '{"text": "yes", "enter": true}'

# Capture session output (tmux or iTerm)
curl http://localhost:5050/api/output/<session_id>?lines=100

# Enable/disable tmux for a project
curl -X POST http://localhost:5050/api/projects/my-app/tmux/enable
curl -X POST http://localhost:5050/api/projects/my-app/tmux/disable
```

**Session Types:**

| Type | Capabilities | Use Case |
|------|-------------|----------|
| tmux | Full read/write | Default, voice bridge, remote control |
| iTerm | Read-only + focus | Simple observation (use `--iterm` flag) |

Sessions show a "tmux" badge in the dashboard when running in tmux mode.

## How It Works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  claude-monitor │────▶│  State File      │◀────│  Monitor App    │
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

1. **Wrapper script** creates a state file with session metadata
2. **Claude Code** runs and updates the iTerm window title as it works
3. **Monitor app** scans state files and reads iTerm window info via AppleScript
4. **Dashboard** displays sessions with real-time status updates
5. **Notifications** fire when activity state changes

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/api/sessions` | GET | JSON list of all sessions |
| `/api/focus/<pid>` | POST | Focus iTerm window by process ID |
| `/api/config` | GET/POST | Read/write configuration |
| `/api/notifications` | GET/POST | Notification settings |
| `/api/notifications/test` | POST | Send test notification |
| `/api/send/<session_id>` | POST | Send text to tmux session |
| `/api/output/<session_id>` | GET | Capture session output |
| `/api/projects/<name>/tmux` | GET | Get project tmux status |
| `/api/projects/<name>/tmux/enable` | POST | Enable tmux for project |
| `/api/projects/<name>/tmux/disable` | POST | Disable tmux for project |

### Example: Get Sessions

```bash
curl http://localhost:5050/api/sessions
```

```json
{
  "sessions": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "uuid_short": "55440000",
      "project_name": "my-app",
      "activity_state": "processing",
      "task_summary": "Implementing user auth",
      "elapsed": "15m",
      "pid": 12345
    }
  ],
  "projects": [...]
}
```

## Troubleshooting

### Sessions not showing

1. Ensure you're using `claude-monitor start` (not `claude` directly)
2. Check the project is listed in `config.yaml`
3. Verify the state file exists: `ls -la .claude-monitor-*.json`

### Click-to-focus not working

macOS requires automation permissions:

1. Open **System Preferences → Privacy & Security → Automation**
2. Ensure your terminal has permission to control iTerm

Test with:
```bash
osascript -e 'tell application "iTerm" to get name of windows'
```

### Notifications not appearing

1. Check `terminal-notifier` is installed: `which terminal-notifier`
2. Verify notifications are enabled in the dashboard Settings tab
3. Check macOS notification settings for terminal-notifier

### Port 5050 already in use

```bash
lsof -i :5050
kill <PID>
```

Or use the restart script:
```bash
./restart_server.sh
```

## Project Structure

```
claude-monitor/
├── monitor.py           # Main Flask application
├── install.sh           # Installation script
├── config.yaml.example  # Configuration template
├── requirements.txt     # Python dependencies
├── restart_server.sh    # Server restart helper
├── bin/
│   └── claude-monitor   # Session wrapper script
├── .claude/             # Claude Code project settings
└── README.md
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built for use with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) by Anthropic.
