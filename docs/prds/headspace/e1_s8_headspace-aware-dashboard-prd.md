---
validation:
  status: valid
  validated_at: '2026-01-21T20:15:35+11:00'
---

## Product Requirements Document (PRD) — Headspace-Aware Dashboard UI

**Project:** Claude Monitor
**Scope:** Epic 1, Sprint 8 - Surface AI prioritisation in the dashboard
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD defines the requirements for the Headspace-Aware Dashboard UI, the capstone sprint of Epic 1. This sprint surfaces AI prioritisation (from Sprint 7) in the dashboard, enabling users to see at a glance which session needs attention and why.

The key deliverables are: a Recommended Next panel that highlights the top-priority session with AI-generated rationale, priority indicators on all session cards, a sort-by-priority toggle, an expandable context panel for selected sessions, and priority-aware notifications. Together, these components deliver the epic's core promise: "glance at the dashboard to know which session needs attention."

Success is measured by the user's ability to identify the recommended session within 2 seconds, understand why it's recommended, and take action without cognitive overhead. The dashboard gracefully degrades when prioritisation is unavailable, maintaining core functionality.

---

## 1. Context & Purpose

### 1.1 Context

Sprint 7 built the AI prioritisation backend (`GET /api/priorities`) that ranks sessions based on headspace, project roadmaps, and activity states. However, this intelligence is hidden behind an API endpoint. Users cannot see the recommendations without building their own interface or manually querying the API.

Sprints 1-7 established the complete data and intelligence stack: project data (Sprint 1), roadmaps (Sprint 2), session state (Sprint 3), history compression (Sprint 4), brain reboot (Sprint 5), headspace (Sprint 6), and AI prioritisation (Sprint 7). Sprint 8 is the final piece that brings this intelligence to the user interface.

### 1.2 Target User

Developers managing multiple Claude Code sessions who need to:
- See at a glance which session deserves attention right now
- Understand the reasoning behind AI recommendations
- Quickly access project context for any session
- Receive intelligent notifications that respect their headspace
- Toggle between AI-prioritised and default session ordering

### 1.3 Success Moment

A developer opens Claude Monitor with five sessions running. At the top of the dashboard, a prominent "Recommended Next" panel shows: "billing-api - Directly aligned with your headspace: 'Ship billing feature by Thursday.' Session is idle and ready for input." Each session card shows a priority badge (95, 70, 40, 30, 20). The developer clicks billing-api, and a context panel slides out showing the project's roadmap, current state, and recent session history. They click to focus the iTerm window and immediately know what to work on. When frontend-ui later needs input, a notification appears: "⚡ High Priority: frontend-ui needs your input - Related to billing UI."

---

## 2. Scope

### 2.1 In Scope

- **Recommended Next Panel**: Prominent panel at top highlighting the #1 priority session with rationale
- **Priority Indicators**: Visual badges on session cards showing priority score (0-100)
- **Sort-by-Priority Toggle**: Switch between AI-prioritised order and default project grouping
- **Context Panel**: Expandable side panel showing project state when a session is selected
- **Priority-Aware Notifications**: Notifications that include priority level and headspace relevance
- **Soft Transition Indicator**: Visual cue when priority update is pending (waiting for natural pause)
- **Graceful Degradation**: Dashboard functions normally when prioritisation is disabled or API unavailable
- **Configuration**: Settings to enable/disable priority features
- **Visual Consistency**: All new components match existing dashboard design (dark theme, cyan accents)

### 2.2 Out of Scope

- Calendar integration
- Mobile-responsive layout
- Priority history or trend visualization
- Manual priority overrides (pinning/boosting sessions)
- Audio/sound for notifications
- Keyboard shortcuts for priority navigation
- Auto-focus on recommended session (user must click)
- Drag-and-drop session reordering
- Priority thresholds or alerts configuration

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. **SC1**: User can identify the recommended session within 2 seconds of viewing the dashboard
2. **SC2**: Recommended Next panel displays the top session's name, priority score, and AI rationale
3. **SC3**: All session cards display a visible priority indicator (badge with score)
4. **SC4**: User can toggle between priority-sorted and default-grouped session views
5. **SC5**: Clicking a session opens a context panel with project roadmap, state, and recent history
6. **SC6**: Context panel can be closed without losing dashboard state
7. **SC7**: Notifications for high-priority sessions include priority context in the message
8. **SC8**: Dashboard displays gracefully when `/api/priorities` is unavailable (no priority features, no errors)
9. **SC9**: Soft transition indicator appears when priorities are pending update

### 3.2 Non-Functional Success Criteria

1. **SC10**: Dashboard renders within 500ms including priority data
2. **SC11**: Priority indicators update smoothly without jarring visual changes
3. **SC12**: Context panel opens within 200ms of click
4. **SC13**: All new UI components are accessible (proper contrast, focus states)
5. **SC14**: No external dependencies added (vanilla JS only)

---

## 4. Functional Requirements (FRs)

### Recommended Next Panel

**FR1**: The dashboard displays a "Recommended Next" panel prominently at the top (below headspace, above session columns)

**FR2**: The panel shows the highest-priority session's project name and short identifier

**FR3**: The panel displays the priority score (0-100) in a visually distinct badge

**FR4**: The panel displays the AI-generated rationale explaining why this session is recommended

**FR5**: The panel displays the session's current activity state (processing/idle/input_needed)

**FR6**: Clicking the Recommended Next panel focuses the corresponding iTerm window

**FR7**: The panel updates when priorities change (respecting soft transitions)

**FR8**: When no sessions are active, the panel displays an appropriate empty state

**FR9**: When prioritisation is disabled or unavailable, the panel is hidden

### Priority Indicators on Cards

**FR10**: Each session card displays a priority badge showing the score (0-100)

**FR11**: Priority badges use visual styling to indicate priority level (high/medium/low color coding)

**FR12**: Priority badges are positioned consistently on all cards (e.g., top-right corner)

**FR13**: Cards without priority data (API unavailable) display without badges gracefully

**FR14**: Priority badges update when priorities refresh

### Sort-by-Priority Toggle

**FR15**: The dashboard includes a toggle to switch between priority-sorted and default-grouped views

**FR16**: In priority-sorted view, sessions are ordered by priority score (highest first) across all projects

**FR17**: In default-grouped view, sessions are grouped by project (existing behavior)

**FR18**: The toggle state persists across page refreshes (stored in browser)

**FR19**: The toggle is disabled and hidden when prioritisation is unavailable

### Context Panel

**FR20**: Clicking a session card opens a context panel (side panel or modal)

**FR21**: The context panel displays the project's roadmap (next_up, upcoming)

**FR22**: The context panel displays the project's current state summary

**FR23**: The context panel displays recent session history (last 3-5 sessions)

**FR24**: The context panel displays the session's priority score and rationale

**FR25**: The context panel includes a button to focus the iTerm window

**FR26**: The context panel includes a close button/action

**FR27**: Only one context panel can be open at a time

**FR28**: The context panel displays gracefully when project data is incomplete

### Priority-Aware Notifications

**FR29**: Notifications for sessions with priority score ≥70 include a "High Priority" indicator

**FR30**: Notification messages include headspace relevance when available (e.g., "Related to: [headspace summary]")

**FR31**: Notification priority indicator is visual (emoji or prefix) to stand out

**FR32**: Notifications continue to work normally when prioritisation is unavailable

### Soft Transition Indicator

**FR33**: When priorities are pending update (soft transition), a subtle indicator appears

**FR34**: The indicator shows that new priorities will apply when sessions pause

**FR35**: The indicator disappears when priorities are applied

### Graceful Degradation

**FR36**: When `/api/priorities` returns an error, the dashboard displays sessions without priority features

**FR37**: When prioritisation is disabled in config, priority UI elements are hidden

**FR38**: Error states are logged but not shown to users (silent degradation)

**FR39**: The dashboard polls for priorities and recovers automatically when API becomes available

### Configuration

**FR40**: Priority UI features can be enabled/disabled via configuration

**FR41**: Configuration changes take effect without application restart

---

## 5. Non-Functional Requirements (NFRs)

**NFR1**: All new UI components must match the existing dashboard visual design (dark theme, cyan accents, monospace fonts)

**NFR2**: Priority data must be fetched asynchronously without blocking initial dashboard render

**NFR3**: Context panel must not cause layout shift in the main dashboard area

**NFR4**: All interactive elements must have visible focus states for keyboard navigation

**NFR5**: Color-coded priority indicators must have sufficient contrast (WCAG AA)

**NFR6**: All new functionality must have unit test coverage

**NFR7**: No external JavaScript libraries or CSS frameworks may be added

**NFR8**: Dashboard must remain functional if JavaScript priority features fail to load

---

## 6. UI Overview

### Dashboard Layout (Updated)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HEADSPACE (Sprint 6)                                            [Edit]     │
│  "Ship billing feature for client demo Thursday"                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  ⭐ RECOMMENDED NEXT                                              [95]      │
│  billing-api • idle                                                         │
│  "Directly aligned with your headspace goal. Ready for input."              │
│                                                        [Click to focus]     │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Sort: ○ By Project  ● By Priority]              [Priorities updating...]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ [95] billing-api│  │ [70] frontend-ui│  │ [40] auth-svc   │             │
│  │ ○ idle          │  │ ⚡ input_needed │  │ ◐ processing    │             │
│  │ Working on...   │  │ Waiting for...  │  │ Running tests...│             │
│  │ 23m             │  │ 5m              │  │ 12m             │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Priority Badge Styling

```
High Priority (70-100):   [95] - Cyan/bright background
Medium Priority (40-69):  [55] - Muted/gray background
Low Priority (0-39):      [25] - Dim/subtle background
```

### Context Panel (Side Panel)

```
┌──────────────────────────────────────┐
│  billing-api                    [×]  │
│  Priority: 95 - High                 │
├──────────────────────────────────────┤
│  WHY RECOMMENDED                     │
│  Directly aligned with headspace:    │
│  "Ship billing feature by Thursday"  │
├──────────────────────────────────────┤
│  ROADMAP                             │
│  Next: Payment processing API        │
│  Then: Invoice generation            │
├──────────────────────────────────────┤
│  CURRENT STATE                       │
│  Implemented Stripe integration,     │
│  working on webhook handling.        │
├──────────────────────────────────────┤
│  RECENT SESSIONS                     │
│  • 2h ago: Added webhook endpoints   │
│  • Yesterday: Stripe SDK setup       │
│  • 2d ago: Schema design             │
├──────────────────────────────────────┤
│  [Focus iTerm Window]                │
└──────────────────────────────────────┘
```

### Notification Format (Priority-Aware)

```
Standard notification:
  "frontend-ui needs input"

High-priority notification:
  "⚡ High Priority: frontend-ui needs input
   Related to: Ship billing feature"
```

### Empty/Error States

```
No sessions:
┌─────────────────────────────────────┐
│  RECOMMENDED NEXT                   │
│  No active sessions                 │
└─────────────────────────────────────┘

API unavailable (silent - just hide panel):
[Recommended Next panel not shown]
[Priority badges not shown]
[Sort toggle disabled]
```

---

## 7. Technical Context

This section provides context for implementation without prescribing solutions.

### Single-File Architecture

Claude Monitor is a single-file Flask application (`monitor.py`) with all HTML, CSS, and JavaScript inline. New UI components must follow this pattern - no external files.

### Data Source

Sprint 7 provides the `/api/priorities` endpoint:
```json
{
  "priorities": [
    {
      "project_name": "billing-api",
      "session_id": "abc123",
      "priority_score": 95,
      "rationale": "Directly aligned with your headspace goal...",
      "activity_state": "idle"
    }
  ],
  "metadata": {
    "timestamp": "2024-01-15T10:30:00Z",
    "headspace_summary": "Ship billing feature for client demo Thursday",
    "cache_hit": false,
    "soft_transition_pending": false
  }
}
```

### Existing Notification System

The notification system uses `terminal-notifier` via subprocess. The `check_state_changes_and_notify()` function tracks state changes and sends notifications. Priority-aware notifications should extend this existing system.

### Project Data Sources

Context panel data comes from Sprint 1-5 endpoints:
- Roadmap: `GET /api/project/<name>/roadmap`
- State: Project YAML state section
- Recent sessions: Project YAML recent_sessions section
- Reboot briefing: `GET /api/project/<name>/reboot` (Sprint 5)

### Dependencies

- Sprint 7 (AI Prioritisation) - `/api/priorities` endpoint
- Sprint 6 (Headspace) - Headspace panel placement
- Sprint 5 (Brain Reboot) - Reboot data for context panel
- Sprints 1-4 - Project data structure
