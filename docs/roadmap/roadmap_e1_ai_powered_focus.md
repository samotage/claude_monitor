# Epic: AI-Powered Focus System for Claude Monitor

## Overview

Transform Claude Monitor from a passive session viewer into an active focus management tool that helps users prioritise work and quickly reload context when returning to projects.

**Inspired by:** John Duduk's focus model - AI as monitor/router, summariser/recaller, decomposer/scaffolder.

## Epic Goal

User can glance at the dashboard to know which session needs attention, and can reboot their brain on any project in under 30 seconds.

---

## Sprint 1: YAML Data Foundation

**Goal:** Establish the persistent data layer for project state storage.

**Scope:**
- Create `data/` directory structure
- Define YAML schema for project files
- Implement YAML read/write utilities in Python
- Add project registration (link config.yaml projects to data files)
- Seed initial project YAML from CLAUDE.md (goal, tech stack)

**Delivers:**
- `data/projects/<name>.yaml` files created for each registered project
- Basic CRUD operations for project data
- Project context pulled from CLAUDE.md on registration

**Does NOT include:**
- Roadmap, state, sessions, history sections (just scaffolding)
- Any AI integration
- Any UI changes

---

## Sprint 2: Project Roadmap Management

**Goal:** Users can define and edit where each project is heading.

**Scope:**
- Add roadmap section to project YAML schema
- API endpoints: `GET/POST /api/project/<name>/roadmap`
- Dashboard UI: View/edit roadmap for a project
- Roadmap fields: next_up (with title, why, DoD), upcoming, later, not_now

**Delivers:**
- Users can set and update project roadmaps via dashboard
- Roadmap persists in YAML
- Foundation for brain reboot "where you're going"

**Does NOT include:**
- AI-generated roadmap suggestions
- Prioritisation logic

---

## Sprint 3: Session Summarisation & State Tracking

**Goal:** Capture what happened in each Claude Code session and maintain current state.

**Scope:**
- Parse Claude Code JSONL logs for session context
- Implement session end detection (idle for N minutes or explicit end)
- Add state and recent_sessions sections to project YAML
- Auto-update state summary after each session
- Store last 5 sessions with detail
- API endpoint: `POST /api/session/<id>/summarise`

**Delivers:**
- Sessions automatically summarised and logged
- Project state updated after each session
- Recent session history available

**Does NOT include:**
- AI summarisation (use simple extraction first)
- History compression
- UI for viewing session history

---

## Sprint 4: History Compression

**Goal:** Automatically compress old sessions into a summary to keep context manageable.

**Scope:**
- Implement rolling window logic (when recent_sessions > 5)
- Add history section to project YAML
- Integrate OpenRouter for AI-powered summarisation
- Config: OpenRouter API key, model selection
- Compress oldest sessions into history.summary

**Delivers:**
- Old sessions automatically summarised into history
- OpenRouter integration working
- Token-efficient project context

**Does NOT include:**
- Live prioritisation
- Brain reboot UI

---

## Sprint 5: Brain Reboot View

**Goal:** Users can quickly reload context on a project they haven't touched in a while.

**Scope:**
- API endpoint: `GET /api/project/<name>/reboot`
- Generate reboot briefing from YAML (roadmap → state → recent → history)
- Dashboard UI: Reboot button on project cards
- Stale indicator (project not touched in N hours)
- Reboot modal/panel with structured briefing

**Delivers:**
- One-click brain reboot for any project
- Visual indicator for stale projects
- Context reload in <30 seconds reading time

**Does NOT include:**
- AI-enhanced reboot suggestions
- Session prioritisation

---

## Sprint 6: Focus Strategy

**Goal:** Users can set and adjust their current focus goal, visible at top of dashboard.

**Scope:**
- Create `data/strategy.yaml` schema
- API endpoints: `GET/POST /api/strategy`
- Dashboard UI: Strategy panel at top (view/edit inline)
- Strategy fields: current_focus, constraints, updated_at
- Persist across dashboard restarts
- Optional: strategy history

**Delivers:**
- Editable focus goal at top of dashboard
- Strategy persists in YAML
- Foundation for AI prioritisation

**Does NOT include:**
- AI using strategy for ranking
- Soft transition logic

---

## Sprint 7: AI Prioritisation

**Goal:** AI ranks sessions based on focus strategy, roadmaps, and activity state.

**Scope:**
- API endpoint: `GET /api/priorities`
- Build LLM prompt: strategy + all project contexts + activity states
- Call OpenRouter to rank sessions
- Return ranked list with rationale
- Polling interval config (re-prioritise every N seconds)
- Soft transition: wait for natural pause before reordering

**Delivers:**
- AI-ranked session list
- Rationale for recommendations
- Smooth priority transitions

**Does NOT include:**
- UI changes (just API)

---

## Sprint 8: Focus-Aware Dashboard UI

**Goal:** Surface AI prioritisation in the dashboard.

**Scope:**
- Recommended next panel (highlight top session with reasoning)
- Priority indicators on session cards
- Optional sort-by-priority toggle
- Context panel on session select (expanded project state)
- Integrate with existing notification system (priority-aware notifications)

**Delivers:**
- Complete focus-aware dashboard
- Users know at a glance which session needs attention
- End-to-end epic goal achieved

**Does NOT include:**
- Calendar integration
- Mobile support

---

## Sprint Dependency Graph
```
Sprint 1: YAML Foundation
    │
    ├── Sprint 2: Roadmap Management
    │
    ├── Sprint 3: Session Summarisation
    │       │
    │       └── Sprint 4: History Compression (requires OpenRouter)
    │               │
    │               └── Sprint 5: Brain Reboot View
    │
    └── Sprint 6: Focus Strategy
            │
            └── Sprint 7: AI Prioritisation (requires OpenRouter from Sprint 4)
                    │
                    └── Sprint 8: Focus-Aware Dashboard UI
```

---

## Suggested Sprint Sequence

| Order | Sprint | Dependency | Est. Size |
|-------|--------|------------|-----------|
| 1 | YAML Foundation | None | Small |
| 2 | Roadmap Management | Sprint 1 | Small |
| 3 | Session Summarisation | Sprint 1 | Medium |
| 4 | Focus Strategy | Sprint 1 | Small |
| 5 | History Compression | Sprint 3 | Medium |
| 6 | Brain Reboot View | Sprints 2, 5 | Medium |
| 7 | AI Prioritisation | Sprints 4, 6 | Medium |
| 8 | Focus-Aware Dashboard UI | Sprint 7 | Medium |

---

## Usage

For each sprint, create an OpenSpec change:
```
/openspec:proposal Sprint 1: YAML Data Foundation for Claude Monitor

[paste sprint scope from this document]
```

This keeps each change focused and implementable in a single development session.