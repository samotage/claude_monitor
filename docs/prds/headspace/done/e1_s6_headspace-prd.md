---
validation:
  status: valid
  validated_at: '2026-01-21T19:53:04+11:00'
---

## Product Requirements Document (PRD) — Headspace

**Project:** Claude Monitor
**Scope:** Epic 1, Sprint 6 - User-defined focus goal visible at top of dashboard
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD defines the requirements for the Headspace feature, which allows users to declare and persist their current focus goal at the top of the Claude Monitor dashboard. By making intent explicit and visible, users shift from reactive notification-driven work to intentional priority-driven work.

The key deliverables are: a persistent headspace data store, API endpoints for reading and updating headspace, and an inline-editable panel at the top of the dashboard. Users can set their current focus in under 10 seconds and see it immediately upon loading the dashboard.

This sprint establishes the foundation for Sprint 7 (AI Prioritisation), which will use the headspace to rank sessions by relevance to the user's stated goals. Success is measured by the user's ability to quickly set, view, and update their focus goal without disrupting session monitoring.

---

## 1. Context & Purpose

### 1.1 Context

Claude Monitor currently shows session status but has no concept of user intent. Users see what's happening across their projects but lack a way to declare what should be happening. This creates reactive behaviour: users respond to notifications rather than working toward explicit goals.

Sprints 1-5 established project-level context (roadmaps, sessions, history, brain reboot). Sprint 6 adds the user-level context layer: "What am I trying to accomplish right now?" This headspace becomes the lens through which AI Prioritisation (Sprint 7) will rank sessions.

### 1.2 Target User

Developers managing multiple Claude Code sessions who need to:
- Declare their current priority across all projects
- Maintain focus despite multiple sessions competing for attention
- Quickly adjust priorities as circumstances change
- Have a visible reminder of their intent at the top of their workflow

### 1.3 Success Moment

A developer starts their morning and opens Claude Monitor. At the top of the dashboard, they see yesterday's headspace: "Ship auth feature for demo Friday." They update it to "Fix CI pipeline blocking auth PR" and continue. Throughout the day, the visible headspace reminds them to stay focused despite notifications from other projects. When Sprint 7 is complete, sessions relevant to CI and auth will automatically surface to the top.

---

## 2. Scope

### 2.1 In Scope

- **Headspace Display**: Visible panel at the top of the dashboard showing current focus goal
- **Inline Editing**: Users can edit headspace directly in the dashboard without modal or page navigation
- **Headspace Fields**: Current focus statement (required), constraints (optional), last updated timestamp
- **Persistence**: Headspace persists across browser refreshes and server restarts
- **API Endpoints**: GET and POST endpoints for reading and updating headspace
- **Edit History**: Optional tracking of previous headspace values for reference
- **Configuration**: Headspace feature can be enabled/disabled in config

### 2.2 Out of Scope

- AI using headspace for session ranking (Sprint 7)
- Soft transition logic or priority smoothing (Sprint 7)
- Multiple headspace profiles or presets
- Time-based headspace scheduling (e.g., "focus on X until 3pm")
- AI-generated headspace suggestions
- Mobile-optimized layout
- Keyboard shortcuts for headspace editing

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. **SC1**: User can view their current headspace at the top of the dashboard without scrolling
2. **SC2**: User can edit their headspace inline and save changes in under 10 seconds
3. **SC3**: Headspace persists after browser refresh
4. **SC4**: Headspace persists after server restart
5. **SC5**: Empty headspace state displays a helpful prompt encouraging the user to set one
6. **SC6**: Headspace shows "last updated" timestamp so users know when they last reviewed it

### 3.2 Non-Functional Success Criteria

1. **SC7**: Headspace panel renders within 100ms of dashboard load
2. **SC8**: Saving headspace does not interrupt session polling or cause visible UI flicker
3. **SC9**: Headspace data is stored in a human-readable format for debugging

---

## 4. Functional Requirements (FRs)

### Data Model

**FR1**: The system stores headspace data with the following fields: current_focus (string, required), constraints (string, optional), updated_at (ISO timestamp)

**FR2**: The system maintains an optional history of previous headspace values with timestamps

**FR3**: Headspace data persists independently of project data (global to the user, not per-project)

### API Endpoints

**FR4**: `GET /api/headspace` returns the current headspace data including all fields

**FR5**: `GET /api/headspace` returns an appropriate empty state when no headspace has been set

**FR6**: `POST /api/headspace` accepts current_focus and optional constraints, updates the stored data, and returns the updated headspace

**FR7**: `POST /api/headspace` automatically sets updated_at to the current timestamp

**FR8**: `POST /api/headspace` appends the previous headspace to history before updating (if history is enabled)

**FR9**: `GET /api/headspace/history` returns the list of previous headspace values (optional endpoint)

### Dashboard UI

**FR10**: The headspace panel appears at the top of the dashboard, above session cards

**FR11**: The headspace panel displays the current focus statement prominently

**FR12**: The headspace panel displays constraints (if set) in a secondary style

**FR13**: The headspace panel displays the "last updated" timestamp in a human-friendly format (e.g., "2 hours ago")

**FR14**: The headspace panel includes an edit button/icon that enables inline editing mode

**FR15**: In edit mode, the current focus and constraints are editable in text fields

**FR16**: In edit mode, Save and Cancel buttons are available

**FR17**: Saving exits edit mode and displays the updated headspace

**FR18**: Cancelling exits edit mode without saving changes

**FR19**: When no headspace is set, the panel displays an empty state with prompt text (e.g., "What's your focus right now?")

### Configuration

**FR20**: The headspace feature can be enabled/disabled via configuration

**FR21**: History tracking can be enabled/disabled via configuration

**FR22**: Configuration changes take effect without application restart

---

## 5. Non-Functional Requirements (NFRs)

**NFR1**: Headspace data must be stored in a human-readable format (YAML or JSON)

**NFR2**: API responses must complete within 200ms under normal conditions

**NFR3**: UI updates must not cause layout shift or flicker in the session cards below

**NFR4**: All new functionality must have unit test coverage

**NFR5**: The headspace panel must be visually consistent with the existing dashboard design (dark theme, cyan accents)

---

## 6. UI Overview

### Headspace Panel (Top of Dashboard)

The headspace panel sits at the very top of the dashboard, spanning the full width above the session columns.

**View Mode:**
```
┌─────────────────────────────────────────────────────────────┐
│  HEADSPACE                                        [Edit]    │
│                                                             │
│  "Ship auth feature for demo Friday"                        │
│                                                             │
│  Constraints: No new features until CI is green             │
│  Updated 2 hours ago                                        │
└─────────────────────────────────────────────────────────────┘
```

**Edit Mode:**
```
┌─────────────────────────────────────────────────────────────┐
│  HEADSPACE                                                  │
│                                                             │
│  Focus: [____________________________________]              │
│                                                             │
│  Constraints (optional): [_______________________]          │
│                                                             │
│                                    [Cancel]  [Save]         │
└─────────────────────────────────────────────────────────────┘
```

**Empty State:**
```
┌─────────────────────────────────────────────────────────────┐
│  HEADSPACE                                        [Set]     │
│                                                             │
│  What's your focus right now?                               │
│  Setting a headspace helps you stay intentional.            │
└─────────────────────────────────────────────────────────────┘
```

### Visual Design Notes

- Panel uses the existing dark theme (var(--bg-card), var(--cyan) accents)
- Focus statement is prominent (larger font, high contrast)
- Constraints are secondary (smaller, muted color)
- Timestamp is subtle (smallest, most muted)
- Edit mode fields match existing settings panel styling

---

## 7. Technical Context

This section provides context for implementation without prescribing solutions.

### Data Storage

The existing pattern from Sprint 1 stores project data in `data/projects/<name>.yaml`. Headspace is global (not per-project), so it should have its own file: `data/headspace.yaml`.

### Sprint 7 Integration

Sprint 7 (AI Prioritisation) will read headspace to inform session ranking. The API should return headspace in a format suitable for inclusion in LLM prompts (plain text, not nested structures).

### Existing Dashboard Patterns

The dashboard uses vanilla JS with fetch() for API calls. Settings panel has inline editing pattern that can be referenced. CSS uses custom properties for theming.

### Dependencies

- Sprint 1 (YAML Data Foundation) - Provides data directory structure and YAML utilities
