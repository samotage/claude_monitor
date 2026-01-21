---
validation:
  status: valid
  validated_at: '2026-01-21T19:46:29+11:00'
---

## Product Requirements Document (PRD) — Brain Reboot View

**Project:** Claude Monitor
**Scope:** Epic 1, Sprint 5 - One-click context reload for stale projects
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD defines the requirements for the Brain Reboot feature, which enables users to quickly reload mental context on projects they haven't touched in a while. The feature synthesizes data from project roadmaps (Sprint 2), session state (Sprint 3), and compressed history (Sprint 4) into a structured briefing designed to be read in under 30 seconds.

The key deliverables are: a reboot API endpoint that aggregates project context, a side panel UI for displaying the briefing, visual indicators for stale projects, and graceful handling of incomplete data. This sprint delivers the core user-facing value of Epic 1: "reboot your brain on any project in under 30 seconds."

Success is measured by the user's ability to click one button, read a structured briefing, and understand where a project is heading, where it currently stands, and what happened recently—all without digging through logs or notes.

---

## 1. Context & Purpose

### 1.1 Context

Developers working across multiple Claude Code projects lose mental context when switching between them. Returning to a project after hours or days typically requires re-reading code, scrolling through terminal history, and piecing together notes to remember "where was I?" This context-switching tax can consume 15-25 minutes per project.

Sprints 1-4 established the data foundation: project roadmaps (where you're going), session capture (what happened), and history compression (the arc of work). Sprint 5 synthesizes this data into a consumable briefing that reduces context reload time to 30 seconds.

### 1.2 Target User

Developers managing multiple Claude Code projects who need to:
- Quickly remember what they were working on after stepping away
- Understand project trajectory without reading raw session logs
- Identify which projects need attention (stale indicators)
- Context-switch efficiently between concurrent projects

### 1.3 Success Moment

A developer opens Claude Monitor after lunch and sees two project cards are faded (stale). They click the Reboot button on one project. A side panel slides open showing: "Focus: Implementing user auth. Last session: Added JWT validation, tests passing. Recent: 3 sessions over 2 days covering auth flow. History: Started 2 weeks ago with database schema, completed user model last week." The developer knows exactly where to pick up—in 30 seconds.

---

## 2. Scope

### 2.1 In Scope

- **Reboot API Endpoint**: `GET /api/project/<name>/reboot` returning structured briefing
- **Briefing Generation**: Aggregate and format data from roadmap, state, recent_sessions, and history
- **Stale Project Detection**: Calculate staleness from last activity, configurable threshold (default: 4 hours)
- **Stale Visual Indicator**: Faded/dimmed card appearance with icon and text label
- **Reboot Button**: Added to project cards, triggers side panel
- **Side Panel UI**: Contextual panel displaying structured briefing alongside dashboard
- **Empty State Handling**: Graceful degradation with helpful prompts when data is missing
- **Configuration**: Stale threshold configurable in config.yaml

### 2.2 Out of Scope

- AI-enhanced reboot suggestions (future sprint)
- Session prioritisation (Sprint 7)
- Editing project data from reboot panel
- Reboot notifications or reminders
- Project comparison views
- Mobile-optimized layout
- Keyboard shortcuts for reboot

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. **SC1**: User can click a Reboot button on any project card to open the briefing panel
2. **SC2**: Briefing displays structured content: roadmap → state → recent sessions → history
3. **SC3**: Briefing can be read and understood in under 30 seconds (concise formatting)
4. **SC4**: Projects not touched for 4+ hours display stale visual indicator (faded + icon + label)
5. **SC5**: API returns complete briefing data in a single request
6. **SC6**: Missing data sections show helpful prompts rather than errors

### 3.2 Non-Functional Success Criteria

1. **SC7**: Side panel opens within 500ms of button click
2. **SC8**: Stale threshold is configurable without code changes
3. **SC9**: Panel is dismissible and doesn't block dashboard interaction

---

## 4. Functional Requirements (FRs)

### Reboot API Endpoint

**FR1**: The system provides a `GET /api/project/<name>/reboot` endpoint that returns a structured briefing

**FR2**: The API response includes a `briefing` object with sections: `roadmap`, `state`, `recent`, `history`

**FR3**: The API response includes a `meta` object with: `is_stale`, `last_activity`, `staleness_hours`

**FR4**: The endpoint returns 404 with appropriate message if project not found

**FR5**: The endpoint returns 200 with partial data if some sections are empty (graceful degradation)

### Briefing Generation

**FR6**: The `briefing.roadmap` section includes: current focus (next_up.title), why it matters (next_up.why), and immediate next steps (upcoming items)

**FR7**: The `briefing.state` section includes: current status, last action taken, and time since last session

**FR8**: The `briefing.recent` section includes condensed summaries of recent sessions (from recent_sessions)

**FR9**: The `briefing.history` section includes the compressed narrative summary and period covered (from history)

**FR10**: Each briefing section is formatted for quick scanning (concise, structured)

### Stale Detection

**FR11**: The system calculates project staleness based on time since last session ended

**FR12**: Projects are considered stale when inactive for longer than the configured threshold

**FR13**: The stale threshold is configurable in config.yaml with a default of 4 hours (240 minutes)

**FR14**: Staleness information is included in both the API response and dashboard rendering

### Dashboard UI - Stale Indicator

**FR15**: Stale project cards display with faded/dimmed visual appearance

**FR16**: Stale project cards show a stale icon (e.g., clock or pause icon)

**FR17**: Stale project cards show a text label indicating staleness (e.g., "Stale - 6 hours")

**FR18**: Non-stale projects display with normal appearance (no indicator)

### Dashboard UI - Reboot Button

**FR19**: Each project card displays a Reboot button

**FR20**: The Reboot button is visually emphasized on stale project cards

**FR21**: Clicking the Reboot button opens the side panel for that project

### Side Panel

**FR22**: The side panel displays alongside the dashboard (not as a modal overlay)

**FR23**: The side panel shows the project name and a close button

**FR24**: The side panel displays briefing sections in order: Roadmap → State → Recent → History

**FR25**: Each section has a clear header and formatted content

**FR26**: The side panel can be closed by clicking the close button or clicking outside

**FR27**: Only one side panel can be open at a time (opening another closes the current)

### Empty State Handling

**FR28**: When roadmap is empty, display: "No roadmap defined yet. Would you like to define one?" with link to roadmap editor

**FR29**: When state is empty, display: "No session activity recorded yet"

**FR30**: When recent_sessions is empty, display: "No recent sessions"

**FR31**: When history is empty, display: "No compressed history yet" (acceptable for newer projects)

**FR32**: Empty sections do not prevent other sections from displaying

---

## 5. Non-Functional Requirements (NFRs)

**NFR1**: Side panel must open within 500ms of button click (perceived responsiveness)

**NFR2**: API endpoint must respond within 200ms for typical project data sizes

**NFR3**: Side panel must not block interaction with the rest of the dashboard

**NFR4**: Stale indicator styling must meet accessibility contrast requirements

**NFR5**: All new functionality must have unit test coverage

---

## 6. UI Overview

### Project Card (with stale state)

```
┌─────────────────────────────────────┐
│  ◐ Project Name          [Reboot]  │  ← Faded appearance
│  ⏸ Stale - 6 hours                 │  ← Icon + text indicator
│  Status: idle                       │
│  Last: Implementing auth flow       │
└─────────────────────────────────────┘
```

### Side Panel (Brain Reboot)

```
┌──────────────────────────────────────┐
│  ✕  Brain Reboot: Project Name       │
├──────────────────────────────────────┤
│                                      │
│  📍 WHERE YOU'RE GOING               │
│  ─────────────────────               │
│  Focus: Implementing user auth       │
│  Why: Core feature for MVP launch    │
│  Next: Add password reset flow       │
│                                      │
│  📌 WHERE YOU ARE                    │
│  ─────────────────────               │
│  Last session: 6 hours ago           │
│  Status: Tests passing               │
│  Last action: Added JWT validation   │
│                                      │
│  🕐 RECENT SESSIONS                  │
│  ─────────────────────               │
│  • Today: JWT validation, 3 files    │
│  • Yesterday: Auth middleware setup  │
│  • 2 days ago: Database schema       │
│                                      │
│  📚 PROJECT HISTORY                  │
│  ─────────────────────               │
│  Over the past 2 weeks: Started      │
│  with database schema design,        │
│  completed user model, now working   │
│  on authentication flow.             │
│                                      │
└──────────────────────────────────────┘
```

### Empty State Example

```
│  📍 WHERE YOU'RE GOING               │
│  ─────────────────────               │
│  No roadmap defined yet.             │
│  → Define a roadmap                  │  ← Clickable link
│                                      │
```

---

## 7. Technical Context

This section provides context for implementation without prescribing solutions.

### Data Sources (from Dependencies)

| Section | Source | Sprint |
|---------|--------|--------|
| Roadmap | `project_data.roadmap` | Sprint 2 |
| State | `project_data.state` | Sprint 3 |
| Recent | `project_data.recent_sessions` | Sprint 3 |
| History | `project_data.history` | Sprint 4 |

### API Response Structure

```json
{
  "briefing": {
    "roadmap": {
      "focus": "string or null",
      "why": "string or null",
      "next_steps": ["string"]
    },
    "state": {
      "status": "string or null",
      "last_action": "string or null",
      "last_session_time": "ISO timestamp or null"
    },
    "recent": [
      {
        "date": "string",
        "summary": "string",
        "files_count": "number"
      }
    ],
    "history": {
      "narrative": "string or null",
      "period": "string or null"
    }
  },
  "meta": {
    "is_stale": "boolean",
    "last_activity": "ISO timestamp or null",
    "staleness_hours": "number or null"
  }
}
```

### Configuration

```yaml
# Addition to config.yaml
stale_threshold_hours: 4  # Projects inactive longer than this show stale indicator
```

### Dependencies

- Sprint 2 (Roadmap Management) - Provides roadmap data
- Sprint 3 (Session Summarisation) - Provides state and recent_sessions
- Sprint 4 (History Compression) - Provides compressed history narrative
