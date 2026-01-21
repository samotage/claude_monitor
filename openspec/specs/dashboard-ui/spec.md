# dashboard-ui Specification

## Purpose
TBD - created by archiving change e1_s8_headspace-aware-dashboard. Update Purpose after archive.
## Requirements
### Requirement: Recommended Next Panel

The dashboard SHALL display a prominent "Recommended Next" panel at the top (below headspace, above session columns) that highlights the highest-priority session.

#### Scenario: Panel displays top-priority session

- **WHEN** the dashboard loads and priorities are available
- **THEN** the Recommended Next panel displays:
  - Project name and session identifier
  - Priority score (0-100) in a visually distinct badge
  - AI-generated rationale explaining the recommendation
  - Current activity state (processing/idle/input_needed)

#### Scenario: User clicks to focus session

- **WHEN** user clicks the Recommended Next panel
- **THEN** the corresponding iTerm window is focused

#### Scenario: No active sessions

- **WHEN** no sessions are active
- **THEN** the panel displays an appropriate empty state message

#### Scenario: Prioritisation unavailable

- **WHEN** `/api/priorities` returns an error or is disabled
- **THEN** the Recommended Next panel is hidden (not shown)

---

### Requirement: Priority Badges on Session Cards

Each session card SHALL display a priority badge showing the score (0-100) with visual styling indicating priority level.

#### Scenario: Badge displays with color coding

- **WHEN** priority data is available for a session
- **THEN** the badge displays:
  - Score value (0-100)
  - High priority (70-100): cyan/bright background
  - Medium priority (40-69): muted/gray background
  - Low priority (0-39): dim/subtle background

#### Scenario: No priority data available

- **WHEN** priority data is unavailable for a session
- **THEN** the card displays without a badge (graceful degradation)

---

### Requirement: Sort-by-Priority Toggle

The dashboard SHALL include a toggle to switch between priority-sorted and default-grouped session views.

#### Scenario: Toggle to priority-sorted view

- **WHEN** user enables priority sort
- **THEN** sessions are ordered by priority score (highest first) across all projects

#### Scenario: Toggle to default-grouped view

- **WHEN** user disables priority sort
- **THEN** sessions are grouped by project (existing behavior)

#### Scenario: Toggle state persists

- **WHEN** user changes toggle state and refreshes the page
- **THEN** the previous toggle state is restored from localStorage

#### Scenario: Toggle hidden when unavailable

- **WHEN** prioritisation is unavailable
- **THEN** the toggle is disabled and hidden

---

### Requirement: Context Panel

Clicking a session card SHALL open a context panel displaying detailed project information.

#### Scenario: Panel opens with full context

- **WHEN** user clicks a session card
- **THEN** a side panel opens displaying:
  - Project roadmap (next_up, upcoming)
  - Current state summary
  - Recent session history (last 3-5 sessions)
  - Priority score and rationale
  - Button to focus iTerm window
  - Close button

#### Scenario: Only one panel open

- **WHEN** user clicks a different session card while panel is open
- **THEN** the panel updates to show the new session's context

#### Scenario: Incomplete project data

- **WHEN** project data is incomplete (missing roadmap, state, etc.)
- **THEN** the panel displays available information gracefully

---

### Requirement: Priority-Aware Notifications

Notifications for high-priority sessions SHALL include priority context.

#### Scenario: High-priority notification

- **WHEN** a session with priority score ≥70 needs input
- **THEN** the notification includes:
  - "High Priority" indicator (emoji prefix)
  - Headspace relevance when available

#### Scenario: Standard notification

- **WHEN** a session with priority score <70 needs input
- **THEN** the notification displays normally without priority indicator

#### Scenario: Prioritisation unavailable

- **WHEN** prioritisation is unavailable
- **THEN** notifications continue to work with standard format

---

### Requirement: Soft Transition Indicator

The dashboard SHALL display a subtle indicator when priorities are pending update.

#### Scenario: Indicator appears

- **WHEN** `soft_transition_pending` is true in priority response
- **THEN** a subtle indicator appears showing "Priorities updating..."

#### Scenario: Indicator disappears

- **WHEN** priorities are applied (soft transition complete)
- **THEN** the indicator disappears

---

### Requirement: Graceful Degradation

The dashboard SHALL function normally when prioritisation is disabled or unavailable.

#### Scenario: API error

- **WHEN** `/api/priorities` returns an error
- **THEN** the dashboard displays sessions without priority features
- **AND** error is logged but not shown to user

#### Scenario: Prioritisation disabled

- **WHEN** prioritisation is disabled in config
- **THEN** all priority UI elements are hidden

#### Scenario: Auto-recovery

- **WHEN** API becomes available after being unavailable
- **THEN** the dashboard recovers and displays priority features

