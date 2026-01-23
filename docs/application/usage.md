---
title: Usage Guide
keywords: usage, dashboard, sessions, activity, notifications, headspace, roadmap, priority, focus, how to
order: 4
---

# Usage Guide

This guide covers how to use all the features of Claude Headspace.

## Starting the Dashboard

```bash
cd /path/to/claude-monitor
source venv/bin/activate
python monitor.py
```

The dashboard will be available at http://localhost:5050

## Starting a Monitored Session

Instead of running `claude` directly, use the wrapper script:

```bash
cd /path/to/your/project
claude-monitor start           # Default: runs in tmux (bidirectional control)
claude-monitor start --iterm   # Force iTerm mode (read-only observation)
```

This creates a state file that the dashboard uses to track the session.

### Session Types

| Type | Capabilities | Use Case |
|------|-------------|----------|
| **tmux** | Full read/write control via API | Default, voice bridge, automation, remote control |
| **iTerm** | Read-only observation + window focus | Simple monitoring (use `--iterm` flag) |

Sessions running in tmux mode show a "tmux" badge in the dashboard.

## Dashboard Layout

### Tab Navigation

| Tab | Description |
|-----|-------------|
| **sessions** | Main Kanban board with active sessions |
| **readme.md** | Project documentation |
| **config.yaml** | Settings and project management |

### Sessions Tab

The sessions tab shows:

1. **Headspace Panel** (top) - Your current focus
2. **Priority Recommendation** (when available) - What to work on next
3. **Session Cards** - Grouped by project in columns

## Activity States

Each session card shows its current activity state:

| State | Indicator | Meaning |
|-------|-----------|---------|
| **Processing** | Green spinner | Claude is actively working |
| **Input Needed** | Amber highlight | Waiting for your response |
| **Idle** | Blue | Ready for a new task |
| **Unknown** | Grey | State cannot be determined |

The dashboard title updates to show when any session needs input: `(1) INPUT NEEDED - Claude Headspace`

## Session Cards

Click any session card to focus that iTerm window.

Each card shows:
- **Activity state** indicator
- **Task summary** - What Claude is working on
- **Duration** - How long the session has been running
- **Headspace button** - View project context (brain reboot)

## Setting Your Headspace

The headspace panel at the top lets you declare your current focus:

1. Click in the headspace area
2. Type your current goal (e.g., "Ship billing feature by Thursday")
3. Optionally add constraints (e.g., "No breaking API changes")
4. Click Save

Your headspace is used by the AI to prioritise which session you should work on next.

### Example Headspace

```
Focus: Complete the authentication flow for the demo
Constraints: Must work with existing user database
```

## AI Prioritisation

When you have multiple active sessions, the AI analyses:

1. **Your headspace** - What you're trying to accomplish
2. **Project roadmaps** - What each project's immediate focus is
3. **Session activity** - Which sessions need input vs are processing
4. **Recent context** - What you've been working on

It then recommends which session deserves your attention with a score (0-100) and rationale.

### Priority Panel

When priorities are available, a recommendation panel appears showing:
- The top recommended session
- Why it's recommended (aligned with your headspace, needs input, etc.)
- Click to focus that session

## Project Roadmaps

Each project can have a roadmap showing where it's heading:

1. Click the **Headspace** button on any project card
2. The side panel shows the project's roadmap:
   - **Where You're Going** - Current focus and next steps
   - **Where You Are** - Recent activity and state
   - **Recent Sessions** - What happened in past sessions
   - **Project History** - Compressed narrative of older work

### Editing Roadmaps

Roadmaps are stored in `data/projects/<project>.yaml` and can be edited:

1. Directly in the YAML file
2. Through the dashboard (click to expand roadmap section on a project card)

## Notifications

When enabled, you receive macOS notifications for:

- **Input Needed** - When Claude asks a question or needs permission
- **Task Complete** - When processing finishes

Click a notification to jump directly to that iTerm session.

### Enabling/Disabling Notifications

1. Go to the **config.yaml** tab
2. Find the **notifications** section
3. Toggle the enabled button
4. Click "Test Notification" to verify they work

### Notification Requirements

- `terminal-notifier` must be installed (`brew install terminal-notifier`)
- macOS notification settings must allow terminal-notifier

## Brain Reboot

For projects you haven't touched in a while ("stale" projects):

1. The project card appears faded
2. Click the **Headspace** button
3. A side panel shows a structured briefing:
   - Current roadmap focus
   - Last session summary
   - Recent activity
   - Compressed history

This helps you reload context in under 30 seconds.

## Keyboard Shortcuts

Currently, all interactions are mouse-based. Keyboard shortcuts may be added in a future version.

## Managing Projects

### Adding a Project

1. Go to the **config.yaml** tab
2. Click **+ add_project**
3. Enter the project name and path
4. Click **save_config**

### Removing a Project

1. Go to the **config.yaml** tab
2. Click the **x** button next to the project
3. Click **save_config**

Note: This only removes the project from monitoring. Project data in `data/projects/` is preserved.

## tmux Integration

tmux is the **default session mode**, enabling bidirectional control of Claude Code sessions. You can send commands and capture full output programmatically. This is the foundation for features like voice bridge and remote control.

### Installing tmux

```bash
brew install tmux
```

### Using tmux (Default)

tmux is enabled by default. Just run:

```bash
claude-monitor start
```

### Disabling tmux for a Project

To use iTerm mode (read-only) instead:

**Option 1: Command line flag**

```bash
claude-monitor start --iterm
```

**Option 2: Via config.yaml**

Set `tmux: false` in your project configuration:

```yaml
projects:
  - name: "my-app"
    path: "/Users/you/dev/my-app"
    tmux: false
```

**Option 3: Via API**

```bash
curl -X POST http://localhost:5050/api/projects/my-app/tmux/disable
```

### Session Control via API

Once running in tmux mode, you can control sessions programmatically:

**Send text to a session:**
```bash
curl -X POST http://localhost:5050/api/send/<session_id> \
  -H "Content-Type: application/json" \
  -d '{"text": "yes", "enter": true}'
```

**Capture session output:**
```bash
curl http://localhost:5050/api/output/<session_id>?lines=100
```

The `session_id` can be found in the `/api/sessions` response (use `uuid` or `uuid_short`).

### tmux Session Names

Sessions run inside named tmux sessions following the pattern `claude-<project-slug>`:

- Project "my-app" → tmux session `claude-my-app`
- Project "API Service" → tmux session `claude-api-service`

You can attach to these sessions directly with:
```bash
tmux attach-session -t claude-my-app
```

### Dashboard Indicators

Sessions running in tmux mode show:
- A **tmux** badge next to the activity state
- Badge colour indicates attached (green) or detached (amber) state
- Hover over the badge to see the tmux session name

## Tips

### Multiple Monitors
Keep the dashboard open on a secondary monitor to always see session status.

### Focus Time
Set your headspace at the start of each work session to stay intentional.

### Stale Projects
Check stale projects periodically - the brain reboot feature helps you remember where you left off.

### Notifications
Enable notifications so you never miss when Claude needs input, even when the dashboard isn't visible.
