---
title: Configuration Guide
keywords: config, yaml, openrouter, api key, projects, setup, settings, install, configuration
order: 3
---

# Configuration Guide

Claude Headspace is configured through `config.yaml` in the project root. Copy `config.yaml.example` to get started.

## Projects

Add your projects to be monitored:

```yaml
projects:
  - name: "my-app"
    path: "/Users/you/dev/my-app"
    # tmux is enabled by default

  - name: "api-service"
    path: "/Users/you/dev/api-service"
    tmux: false             # Disable tmux to use iTerm mode

  - name: "frontend"
    path: "/Users/you/dev/frontend"
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name shown in the dashboard |
| `path` | Yes | Absolute path to the project directory |
| `tmux` | No | Set to `false` to disable tmux and use iTerm mode (default: true) |

## Dashboard Settings

```yaml
# How often to refresh the dashboard (in seconds)
scan_interval: 5
```

| Setting | Default | Description |
|---------|---------|-------------|
| `scan_interval` | 5 | Dashboard refresh rate. Lower = more responsive but more CPU |

## Session Settings

```yaml
# Minutes of inactivity before a session is considered "ended"
idle_timeout_minutes: 60
```

| Setting | Default | Description |
|---------|---------|-------------|
| `idle_timeout_minutes` | 60 | Triggers automatic session summarisation |

## Brain Reboot

```yaml
# Hours since last activity before a project is flagged as "stale"
stale_threshold_hours: 4
```

Stale projects show a visual indicator and the "Headspace" button becomes more prominent.

## OpenRouter (AI Features)

To enable AI-powered features (history compression, prioritisation), you need an OpenRouter API key.

### Getting an API Key

1. Go to https://openrouter.ai/keys
2. Create an account or sign in
3. Generate a new API key
4. Copy the key (starts with `sk-or-v1-...`)

### Configuration

```yaml
openrouter:
  # Required: Your OpenRouter API key
  api_key: "sk-or-v1-your-key-here"

  # Optional: Model to use (default: anthropic/claude-3-haiku)
  model: "anthropic/claude-3-haiku"

  # Optional: How often to check for pending compressions (seconds)
  compression_interval: 300
```

| Setting | Default | Description |
|---------|---------|-------------|
| `api_key` | (none) | Your OpenRouter API key. Required for AI features |
| `model` | `anthropic/claude-3-haiku` | Model for compression and prioritisation |
| `compression_interval` | 300 | How often to process the compression queue (5 min) |

**Security Note**: Never commit your API key to version control. The `config.yaml` file is gitignored by default.

## Headspace

```yaml
headspace:
  # Enable/disable the headspace panel in the dashboard
  enabled: true

  # Enable/disable headspace history tracking
  history_enabled: true
```

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | true | Show/hide the headspace panel |
| `history_enabled` | true | Track headspace changes in `data/headspace.yaml` |

## AI Prioritisation

```yaml
priorities:
  # Enable/disable AI-powered session prioritisation
  enabled: true

  # How often to refresh priorities (seconds)
  polling_interval: 60

  # Model to use (can differ from compression model)
  # model: "anthropic/claude-3-haiku"
```

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | true | Enable AI prioritisation (requires OpenRouter) |
| `polling_interval` | 60 | Cache refresh interval |
| `model` | (uses openrouter.model) | Can use a different model for prioritisation |

## Terminal Backend

Choose which terminal multiplexer to use for Claude Code sessions.

### Prerequisites

```bash
# tmux (default)
brew install tmux

# WezTerm (alternative)
brew install --cask wezterm
```

### Configuration

```yaml
# Choose the default terminal backend
terminal_backend: "tmux"    # Options: "tmux" (default), "wezterm"

# WezTerm-specific settings (only used when terminal_backend: "wezterm")
wezterm:
  workspace: "claude-monitor"   # Workspace name for grouping sessions
  full_scrollback: true         # Enable full scrollback capture
```

| Setting | Default | Description |
|---------|---------|-------------|
| `terminal_backend` | `tmux` | Which backend to use: `tmux` or `wezterm` |
| `wezterm.workspace` | `claude-monitor` | WezTerm workspace for grouping Claude sessions |
| `wezterm.full_scrollback` | `true` | Capture entire scrollback history |

### Per-Project Override

Override the backend for specific projects:

```yaml
projects:
  - name: "my-app"
    path: "/Users/you/dev/my-app"
    terminal_backend: "wezterm"   # Use WezTerm for this project only
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/send/<session_id>` | POST | Send text to session |
| `/api/output/<session_id>` | GET | Capture session output |
| `/api/projects/<name>/tmux` | GET | Check backend status for project |
| `/api/projects/<name>/tmux/enable` | POST | Enable tmux for project |
| `/api/projects/<name>/tmux/disable` | POST | Disable tmux for project |

### Backend Comparison

| Feature | tmux | WezTerm |
|---------|------|---------|
| Read output | Yes | Yes |
| Send commands | Yes | Yes |
| Platform | macOS, Linux | macOS, Linux, Windows |
| Scrollback | Configurable (default 2000) | Full scrollback |
| Window focus | AppleScript (macOS) | Native CLI |

### Command Line Flags

```bash
claude-monitor start             # Use configured backend
claude-monitor start --tmux      # Force tmux
claude-monitor start --wezterm   # Force WezTerm
```

## Complete Example

```yaml
# Projects to monitor
projects:
  - name: "billing-api"
    path: "/Users/me/dev/billing-api"
    # Uses default backend
  - name: "frontend"
    path: "/Users/me/dev/frontend"
    terminal_backend: "wezterm"   # Override: use WezTerm for this project
  - name: "docs"
    path: "/Users/me/dev/docs"

# Dashboard
scan_interval: 5

# Sessions
idle_timeout_minutes: 60

# Brain Reboot
stale_threshold_hours: 4

# OpenRouter (AI features)
openrouter:
  api_key: "sk-or-v1-your-key-here"
  model: "anthropic/claude-3-haiku"
  compression_interval: 300

# Headspace
headspace:
  enabled: true
  history_enabled: true

# AI Prioritisation
priorities:
  enabled: true
  polling_interval: 60

# Terminal Backend
terminal_backend: "tmux"    # Default: "tmux" or "wezterm"

# WezTerm settings (when using WezTerm backend)
wezterm:
  workspace: "claude-monitor"
  full_scrollback: true
```

## Environment Variables

Currently, all configuration is done through `config.yaml`. Environment variable support may be added in a future version.

## Reloading Configuration

Most settings are read on each request, so changes take effect immediately. However, for the following you should restart the server:

- Adding/removing projects
- Changing OpenRouter API key
- Changing compression interval

Use the restart script:
```bash
./restart_server.sh
```
