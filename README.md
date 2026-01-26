# Claude Headspace

A Kanban-style dashboard for tracking Claude Code sessions across multiple projects, with native macOS notifications.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![macOS](https://img.shields.io/badge/platform-macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Multi-project dashboard** - See all active Claude Code sessions at a glance
- **Activity states** - Know when Claude is working, idle, or needs your input
- **Claude Code hooks** - Instant, event-driven state detection (recommended)
- **Native notifications** - Get macOS alerts when input is needed or tasks complete
- **Click-to-focus** - Jump to any session from the dashboard or notification
- **Real-time updates** - Dashboard refreshes automatically via SSE
- **Terminal backend support** - tmux (default) or WezTerm with send/capture APIs

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
- **Terminal backend** (one of):
  - **tmux** (default) - `brew install tmux`
  - **WezTerm** (alternative) - `brew install --cask wezterm`
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
    # Uses default backend

  - name: "api-service"
    path: "/Users/you/dev/api-service"
    terminal_backend: "wezterm"   # Override: use WezTerm for this project

scan_interval: 5              # Dashboard refresh rate (seconds)
terminal_backend: "tmux"      # Default backend: "tmux" or "wezterm"
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
claude-monitor start             # Uses configured backend (default: tmux)
claude-monitor start --tmux      # Force tmux backend
claude-monitor start --wezterm   # Use WezTerm backend
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

### Claude Code Hooks (Recommended)

For instant, accurate state detection, install Claude Code hooks. Instead of polling terminal output, hooks provide event-driven updates directly from Claude Code.

**Benefits:**
- Instant state updates (<100ms vs 2-second polling)
- 100% confidence (event-based vs inference)
- Reduced resource usage

**Setup:**

Ask Claude Code to install the hooks for you:

> "Install the Claude Monitor hooks. Copy `bin/notify-monitor.sh` to `~/.claude/hooks/` and merge the hook configuration from `docs/claude-code-hooks-settings.json` into my `~/.claude/settings.json`. Use absolute paths (not ~ or $HOME)."

**Important:** Hook commands must use absolute paths (e.g., `/Users/yourname/.claude/hooks/...`), not `~` or `$HOME`, as these may not expand correctly.

Alternatively, if you have `jq` installed, run the install script:
```bash
./bin/install-hooks.sh
```

After installation, the dashboard shows "hooks" badges on session cards when hooks are active.

See `docs/architecture/claude-code-hooks.md` for detailed documentation.

### Terminal Backend Integration

Terminal backends enable bidirectional control of Claude Code sessions. You can send text to sessions and capture full output programmatically.

**Available Backends:**

| Backend | Capabilities | Install |
|---------|-------------|---------|
| tmux | Full read/write (default) | `brew install tmux` |
| WezTerm | Full read/write, cross-platform, full scrollback | `brew install --cask wezterm` |

**Configuration:**

Set the default backend in `config.yaml`:
```yaml
terminal_backend: "tmux"    # or "wezterm"
```

**Session Control APIs:**

```bash
# Send text to a session
curl -X POST http://localhost:5050/api/send/<session_id> \
  -H "Content-Type: application/json" \
  -d '{"text": "yes", "enter": true}'

# Capture session output
curl http://localhost:5050/api/output/<session_id>?lines=100
```

Sessions show their backend type as a badge in the dashboard.

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
| `/hook/status` | GET | Hook receiver status |
| `/hook/session-start` | POST | Claude Code session started |
| `/hook/stop` | POST | Claude finished turn |
| `/hook/user-prompt-submit` | POST | User submitted prompt |

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
├── run.py               # Main entry point (recommended)
├── monitor.py           # Legacy Flask application
├── install.sh           # Installation script
├── config.yaml.example  # Configuration template
├── requirements.txt     # Python dependencies
├── restart_server.sh    # Server restart helper
├── bin/
│   ├── claude-monitor   # Session wrapper script
│   └── notify-monitor.sh # Hook notification script (copy to ~/.claude/hooks/)
├── src/                 # Application source code
│   ├── routes/hooks.py  # Hook API endpoints
│   └── services/hook_receiver.py  # Hook event processing
├── docs/
│   └── architecture/claude-code-hooks.md  # Hook documentation
├── .claude/             # Claude Code project settings
└── README.md
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built for use with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) by Anthropic.
