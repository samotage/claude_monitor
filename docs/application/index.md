---
title: Claude Headspace
keywords: overview, introduction, quick start, dashboard, sessions, getting started
order: 1
---

# Claude Headspace

A Kanban-style dashboard for tracking Claude Code sessions across multiple projects, with native macOS notifications and AI-powered prioritisation.

## What It Does

Claude Headspace helps you manage multiple Claude Code sessions by:

- **Tracking sessions** across all your projects in one dashboard
- **Showing activity states** so you know when Claude is working, idle, or needs input
- **Prioritising work** using AI to recommend which session to focus on next
- **Providing context** so you can quickly reload your mental state on any project

## Quick Start

```bash
# 1. Start the monitor dashboard
cd /path/to/claude-monitor
source venv/bin/activate
python monitor.py

# 2. In another terminal, start a monitored Claude session
cd /path/to/your/project
claude-monitor start
```

Open http://localhost:5050 in your browser.

## Dashboard Overview

The dashboard has three main areas:

### Sessions Tab
The main Kanban board showing all active Claude Code sessions grouped by project. Each card shows:
- Session activity state (processing, input needed, idle)
- Current task summary
- Session duration
- Click to focus the iTerm window

### Headspace Panel
At the top of the dashboard, set your current focus to help the AI prioritise which session you should work on next.

### Priority Recommendations
When you have multiple sessions running, the AI analyses your headspace, project roadmaps, and session activity to recommend which one deserves your attention.

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-project tracking** | See all sessions at a glance |
| **Activity detection** | Know when Claude needs your input |
| **Click-to-focus** | Jump to any session instantly |
| **Native notifications** | macOS alerts when input is needed |
| **AI prioritisation** | Get recommendations on what to work on |
| **Brain reboot** | Quickly reload context on stale projects |
| **Project roadmaps** | Track where each project is heading |

## Requirements

- **macOS** (uses AppleScript for iTerm integration)
- **iTerm2** terminal
- **Python 3.10+**
- **Claude Code CLI**
- **Homebrew** (optional, for notifications)

## Next Steps

- [Configuration Guide](configuration.md) - Set up your projects and API keys
- [Usage Guide](usage.md) - Learn dashboard features in detail
- [Architecture](architecture.md) - Understand how the data flows
