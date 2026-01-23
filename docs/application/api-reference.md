---
title: API Reference
keywords: api, endpoint, rest, json, curl, sessions, headspace, priorities, focus, config, notifications
order: 6
---

# API Reference

Claude Headspace exposes a REST API for all functionality. The dashboard uses these endpoints, and you can use them for automation or integration.

Base URL: `http://localhost:5050`

## Sessions

### GET /api/sessions

List all active Claude Code sessions.

**Response:**
```json
{
  "sessions": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "uuid_short": "55440000",
      "project_name": "my-app",
      "activity_state": "processing",
      "task_summary": "Implementing user authentication",
      "elapsed": "15m",
      "pid": 12345,
      "tty": "/dev/ttys003",
      "session_type": "tmux",
      "tmux_session": "claude-my-app",
      "tmux_attached": true
    }
  ],
  "projects": [
    {
      "name": "my-app",
      "path": "/Users/me/dev/my-app",
      "tmux": true
    }
  ]
}
```

Note: `session_type` is either `"tmux"` or `"iterm"`. The `tmux_session` and `tmux_attached` fields are only present for tmux sessions.

### POST /api/focus/\<pid\>

Focus an iTerm window by process ID.

**Parameters:**
- `pid` (path) - Process ID of the session

**Response:**
```json
{
  "success": true
}
```

## tmux Session Control

These endpoints enable bidirectional control of sessions running in tmux mode.

### POST /api/send/\<session_id\>

Send text to a tmux session.

**Parameters:**
- `session_id` (path) - Session UUID or short UUID

**Request Body:**
```json
{
  "text": "yes",
  "enter": true
}
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `text` | Yes | - | Text to send to the session |
| `enter` | No | true | Whether to press Enter after sending |

**Response:**
```json
{
  "success": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "tmux_session": "claude-my-app"
}
```

**Error (not a tmux session):**
```json
{
  "success": false,
  "error": "Send is only supported for tmux sessions. This session is using iTerm (read-only)."
}
```

### GET /api/output/\<session_id\>

Capture output from a session.

**Parameters:**
- `session_id` (path) - Session UUID or short UUID

**Query Parameters:**
- `lines` (optional) - Number of lines to capture (default: 100)

**Response (tmux session):**
```json
{
  "success": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_type": "tmux",
  "output": "Claude: I'll help you implement...\n...",
  "lines": 100
}
```

**Response (iTerm session):**
```json
{
  "success": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_type": "iterm",
  "output": "...",
  "lines": 100,
  "note": "iTerm sessions have limited output capture (last ~5000 chars)"
}
```

## Project tmux Configuration

### GET /api/projects/\<name\>/tmux

Get tmux status for a project.

**Parameters:**
- `name` (path) - Project name

**Response:**
```json
{
  "success": true,
  "project": "my-app",
  "enabled": true,
  "available": true,
  "status": "ready",
  "session_name": "claude-my-app"
}
```

| Field | Description |
|-------|-------------|
| `enabled` | Whether tmux is enabled in config for this project |
| `available` | Whether tmux is installed on the system |
| `status` | One of: `ready`, `not_enabled`, `unavailable` |
| `session_name` | The tmux session name that would be used |

### POST /api/projects/\<name\>/tmux/enable

Enable tmux for a project (updates config.yaml).

**Parameters:**
- `name` (path) - Project name

**Response:**
```json
{
  "success": true,
  "project": "my-app",
  "message": "tmux enabled for project 'my-app'",
  "enabled": true,
  "available": true,
  "status": "ready",
  "session_name": "claude-my-app"
}
```

**Error (tmux not installed):**
```json
{
  "success": false,
  "error": "tmux is not installed. Install with: brew install tmux"
}
```

### POST /api/projects/\<name\>/tmux/disable

Disable tmux for a project (updates config.yaml).

**Parameters:**
- `name` (path) - Project name

**Response:**
```json
{
  "success": true,
  "project": "my-app",
  "message": "tmux disabled for project 'my-app'",
  "enabled": false,
  "available": true,
  "status": "not_enabled",
  "session_name": "claude-my-app"
}
```

## Headspace

### GET /api/headspace

Get the current headspace (user's focus).

**Response:**
```json
{
  "success": true,
  "headspace": {
    "current_focus": "Ship billing feature by Thursday",
    "constraints": "No breaking API changes",
    "updated_at": "2026-01-21T21:57:17.967259Z"
  }
}
```

### POST /api/headspace

Update the current headspace.

**Request Body:**
```json
{
  "current_focus": "Complete authentication flow",
  "constraints": "Must work with existing database"
}
```

**Response:**
```json
{
  "success": true,
  "headspace": {
    "current_focus": "Complete authentication flow",
    "constraints": "Must work with existing database",
    "updated_at": "2026-01-21T22:00:00.000000Z"
  }
}
```

### GET /api/headspace/history

Get headspace change history.

**Response:**
```json
{
  "success": true,
  "history": [
    {
      "current_focus": "Previous focus",
      "constraints": null,
      "updated_at": "2026-01-20T15:00:00Z"
    }
  ]
}
```

## Priorities

### GET /api/priorities

Get AI-ranked session priorities.

**Query Parameters:**
- `refresh` (optional) - Set to `true` to force cache refresh

**Response:**
```json
{
  "success": true,
  "priorities": [
    {
      "project_name": "billing-api",
      "session_id": "abc123",
      "priority_score": 95,
      "rationale": "Directly aligned with headspace goal",
      "activity_state": "input_needed"
    },
    {
      "project_name": "frontend",
      "session_id": "def456",
      "priority_score": 70,
      "rationale": "Related to billing UI",
      "activity_state": "idle"
    }
  ],
  "metadata": {
    "timestamp": "2026-01-21T22:00:00Z",
    "headspace_summary": "Ship billing feature",
    "cache_hit": false,
    "soft_transition_pending": false
  }
}
```

## Project Data

### GET /api/project/\<name\>/reboot

Get a brain reboot briefing for quick context reload.

**Parameters:**
- `name` (path) - Project name (URL encoded if contains spaces)

**Response:**
```json
{
  "success": true,
  "briefing": {
    "roadmap": {
      "focus": "Implement payment processing",
      "why": "Core feature for launch",
      "next_steps": ["Add Stripe integration", "Write tests"]
    },
    "state": {
      "status": "active",
      "last_action": "Added database migrations",
      "last_session_time": "2026-01-21T15:30:00Z"
    },
    "recent": [
      {
        "date": "Jan 21",
        "summary": "Set up payment models",
        "files_count": 5
      }
    ],
    "history": {
      "narrative": "Project started with user auth...",
      "period": "2026-01-15T00:00:00Z"
    }
  },
  "meta": {
    "is_stale": false,
    "last_activity": "2026-01-21T15:30:00Z",
    "staleness_hours": 2.5
  }
}
```

### GET /api/project/\<name\>/roadmap

Get a project's roadmap.

**Response:**
```json
{
  "success": true,
  "roadmap": {
    "next_up": {
      "title": "Payment integration",
      "why": "Core feature",
      "definition_of_done": "Stripe payments working"
    },
    "upcoming": ["Email notifications", "Admin dashboard"],
    "later": ["Mobile app"],
    "not_now": ["Social login"]
  }
}
```

### POST /api/project/\<name\>/roadmap

Update a project's roadmap.

**Request Body:**
```json
{
  "next_up": {
    "title": "New focus item",
    "why": "Reason",
    "definition_of_done": "Criteria"
  },
  "upcoming": ["Item 1", "Item 2"]
}
```

## Configuration

### GET /api/config

Get current configuration.

**Response:**
```json
{
  "projects": [
    {"name": "my-app", "path": "/Users/me/dev/my-app"}
  ],
  "scan_interval": 5,
  "iterm_focus_delay": 0.1
}
```

### POST /api/config

Update configuration.

**Request Body:**
```json
{
  "projects": [
    {"name": "my-app", "path": "/Users/me/dev/my-app"},
    {"name": "new-project", "path": "/Users/me/dev/new-project"}
  ],
  "scan_interval": 3
}
```

## Notifications

### GET /api/notifications

Get notification settings.

**Response:**
```json
{
  "enabled": true
}
```

### POST /api/notifications

Update notification settings.

**Request Body:**
```json
{
  "enabled": false
}
```

### POST /api/notifications/test

Send a test notification.

**Response:**
```json
{
  "success": true,
  "message": "Test notification sent"
}
```

## Documentation

### GET /api/readme

Get the README.md content as HTML.

**Response:**
```json
{
  "html": "<h1>Claude Headspace</h1>..."
}
```

### GET /api/help

List all help documentation pages.

**Response:**
```json
{
  "success": true,
  "pages": [
    {"slug": "index", "title": "Claude Headspace", "order": 1},
    {"slug": "architecture", "title": "Architecture", "order": 2}
  ]
}
```

### GET /api/help/\<slug\>

Get a specific help page as HTML.

**Response:**
```json
{
  "success": true,
  "page": {
    "slug": "architecture",
    "title": "Architecture",
    "html": "<h1>Architecture</h1>...",
    "keywords": ["architecture", "data flow", "diagram"]
  }
}
```

### GET /api/help/search

Search help documentation.

**Query Parameters:**
- `q` - Search query

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "slug": "configuration",
      "title": "Configuration Guide",
      "snippet": "...OpenRouter API key...",
      "score": 0.95
    }
  ]
}
```

## Error Responses

All endpoints return errors in a consistent format:

```json
{
  "success": false,
  "error": "Error message describing what went wrong"
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad request (invalid parameters)
- `404` - Resource not found
- `500` - Server error

## Example: cURL

```bash
# Get all sessions
curl http://localhost:5050/api/sessions

# Update headspace
curl -X POST http://localhost:5050/api/headspace \
  -H "Content-Type: application/json" \
  -d '{"current_focus": "Ship feature X"}'

# Get priorities
curl "http://localhost:5050/api/priorities?refresh=true"

# Focus a session
curl -X POST http://localhost:5050/api/focus/12345

# tmux: Send text to a session
curl -X POST http://localhost:5050/api/send/55440000 \
  -H "Content-Type: application/json" \
  -d '{"text": "yes", "enter": true}'

# tmux: Capture session output
curl "http://localhost:5050/api/output/55440000?lines=50"

# tmux: Enable tmux for a project
curl -X POST http://localhost:5050/api/projects/my-app/tmux/enable

# tmux: Check tmux status
curl http://localhost:5050/api/projects/my-app/tmux
```
