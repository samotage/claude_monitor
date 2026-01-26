# Claude Headspace - Project Specification

## Authoritative Architecture Reference

For the complete architectural specification, see:
**[docs/application/conceptual-design.md](../docs/application/conceptual-design.md)**

This document contains:
- Core domain models (Agent, Task, Turn, Project, HeadspaceFocus)
- Service architecture (AgentStore, GoverningAgent, InferenceService, etc.)
- API routes and contracts
- Terminal backend abstraction (WezTerm-first with tmux fallback)
- State machine specifications

The conceptual design document is the authoritative source for architectural decisions.

---

## Overview

Claude Headspace is a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects. It monitors terminal windows and displays real-time session status with click-to-focus functionality and native macOS notifications.

### Key Features
- Track active Claude Code sessions across projects
- Display session status (processing/input needed/idle/complete) in a visual dashboard
- Click-to-focus: bring terminal windows to foreground from the dashboard
- Native macOS notifications when input is needed or tasks complete
- AI-powered priority ranking across sessions
- Brain reboot briefings for project context recovery
- Headspace focus management for cross-project coordination

## Tech Stack

| Component | Technology | Version/Notes |
|-----------|------------|---------------|
| Language | Python | 3.10+ |
| Web Framework | Flask | REST API + dashboard |
| Models | Pydantic v2 | Type-safe domain models |
| Configuration | PyYAML | config.yaml format |
| Terminal Backends | WezTerm / tmux | Pluggable backend abstraction |
| macOS Integration | AppleScript | Via osascript subprocess |
| Notifications | terminal-notifier | Installed via Homebrew |
| LLM Inference | OpenRouter | Priority scoring, brain reboot |
| Frontend | Vanilla JS/CSS | No external dependencies |

## Architecture

### Service Layer Pattern
```
Flask Routes (src/routes/)
         ↓
   Services Layer (src/services/)
         ↓
   Domain Models (src/models/)
         ↓
   Terminal Backends (src/backends/)
```

### Key Services

| Service | Purpose |
|---------|---------|
| `AgentStore` | CRUD for agents, tasks, turns, projects |
| `GoverningAgent` | Orchestrates state transitions, polling |
| `InferenceService` | LLM calls (priority, brain reboot) |
| `NotificationService` | macOS notifications |
| `GitAnalyzer` | Progress narrative from git history |
| `TerminalBackend` | Abstract interface for WezTerm/tmux |

### State Machine

Tasks follow a 5-state machine:
```
IDLE → COMMANDED → PROCESSING → AWAITING_INPUT → COMPLETE
                       ↓
                   COMPLETE
```

## Directory Structure

```
claude_monitor/
├── src/                     # Core application code
│   ├── models/              # Pydantic domain models
│   │   ├── agent.py         # Agent model
│   │   ├── task.py          # Task, Turn, TaskState
│   │   ├── project.py       # Project, Roadmap
│   │   ├── headspace.py     # HeadspaceFocus
│   │   └── inference.py     # InferenceCall, InferencePurpose
│   ├── services/            # Business logic
│   │   ├── agent_store.py   # CRUD + event bus
│   │   ├── governing_agent.py # Orchestration
│   │   ├── inference_service.py # LLM calls
│   │   ├── notification_service.py # Notifications
│   │   ├── priority_service.py # Priority scoring
│   │   └── git_analyzer.py  # Git narrative
│   ├── routes/              # Flask blueprints
│   │   ├── __init__.py      # Blueprint registration
│   │   ├── agents.py        # Agent CRUD endpoints
│   │   ├── headspace.py     # Headspace endpoints
│   │   └── projects.py      # Project endpoints
│   └── backends/            # Terminal integrations
│       ├── base.py          # Abstract interface
│       ├── tmux.py          # tmux backend
│       └── wezterm.py       # WezTerm backend
├── monitor.py               # Flask app entry point
├── lib/                     # Legacy modules (deprecated)
├── tests/                   # Test suite
├── docs/
│   ├── application/
│   │   └── conceptual-design.md  # AUTHORITATIVE ARCHITECTURE
│   └── prds/                # Product requirements
├── openspec/                # Feature specifications
│   ├── AGENTS.md            # OpenSpec agent instructions
│   ├── project.md           # This file
│   └── specs/               # Individual feature specs
├── config.yaml              # User configuration (gitignored)
├── config.yaml.example      # Configuration template
├── requirements.txt         # Python dependencies
└── bin/
    └── claude-monitor       # Session wrapper script
```

## API Endpoints

See [conceptual-design.md](../docs/application/conceptual-design.md) for complete API specification.

### Core Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Main Kanban dashboard |
| `/api/agents` | GET | List all agents |
| `/api/agents/<id>` | GET | Get agent details |
| `/api/agents/<id>/task` | GET | Get current task |
| `/api/headspace` | GET/POST | Get/set headspace focus |
| `/api/headspace/history` | GET | Headspace change history |
| `/api/projects` | GET | List all projects |
| `/api/projects/<id>` | GET | Get project details |
| `/api/projects/<id>/roadmap` | GET/POST | Get/update roadmap |
| `/api/projects/<id>/brain-reboot` | GET | Get context briefing |

### Notification Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/notifications` | GET/POST | Get/set notification settings |
| `/api/notifications/test` | POST | Send test notification |

## Platform Requirements

- **macOS** (AppleScript/terminal integration)
- WezTerm (recommended) or tmux
- terminal-notifier (via Homebrew)
- System Preferences permissions for Automation
- OpenRouter API key (for LLM features)

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

# Start a monitored Claude session
claude-monitor start           # Use configured backend
claude-monitor start --wezterm # Force WezTerm
claude-monitor start --tmux    # Force tmux

# Run tests
pytest
pytest --cov=.
```

## Specification Index

### Active Specs (openspec/specs/)

| Spec | Status | Description |
|------|--------|-------------|
| brain-reboot | Active | Context briefing generation |
| dashboard-ui | Active | Dashboard layout and interactions |
| headspace | Active | Headspace focus management |
| logging-ui | Active | Terminal log viewer |
| priorities | Active | AI priority scoring |
| project-data | Active | Project configuration |
| roadmap-management | Active | Project roadmap tracking |
| session-summarisation | Active | Session history compression |
| terminal-logging-rename | Active | Backend-agnostic logging |

### Archived Specs (openspec/specs/_archived/)

| Spec | Reason |
|------|--------|
| codebase-restructure | Completed - describes first refactor to lib/ |
| tmux-router | Superseded by unified backend abstraction |
| tmux-session-logging | Superseded by terminal-logging-rename |

## Conventions

### Code Style
- Service layer pattern with Pydantic models
- Flask blueprints for route organization
- Backend abstraction for terminal integration

### Testing
- pytest with coverage
- Mocked services for unit tests
- Integration tests for service interactions

### Configuration
- User config in `config.yaml` (gitignored)
- Template provided as `config.yaml.example`
- Environment variables in `.env` (gitignored)
