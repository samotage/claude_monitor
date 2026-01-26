# dashboard-ui Specification

## Purpose
Defines the headspace-aware dashboard UI enhancements including priority badges on agent cards, context panels showing roadmap and agent data, and priority-aware notification formatting. The dashboard displays agents in a Kanban-style layout with 5-state support (idle, commanded, processing, awaiting_input, complete).
## Requirements
### Requirement: Priority Display

The dashboard MAY display priority information when available from the PriorityService.

#### Scenario: Priorities displayed on agent cards

- **WHEN** the dashboard loads and priorities are available
- **THEN** agent cards MAY display:
  - Priority score (0-100) in a visually distinct badge
  - AI-generated rationale explaining the recommendation
  - Current task state (idle/commanded/processing/awaiting_input/complete)

#### Scenario: User clicks to focus agent

- **WHEN** user clicks an agent card
- **THEN** the corresponding terminal window is focused (via WezTerm or tmux backend)

#### Scenario: No active agents

- **WHEN** no agents are active
- **THEN** the dashboard displays an appropriate empty state message

#### Scenario: Prioritisation unavailable

- **WHEN** `/api/priorities` returns an error or is disabled
- **THEN** priority features are hidden (graceful degradation)

---

### Requirement: Priority Badges on Agent Cards

Each agent card MAY display a priority badge showing the score (0-100) with visual styling indicating priority level.

#### Scenario: Badge displays with color coding

- **WHEN** priority data is available for an agent
- **THEN** the badge displays:
  - Score value (0-100)
  - High priority (70-100): cyan/bright background
  - Medium priority (40-69): muted/gray background
  - Low priority (0-39): dim/subtle background

#### Scenario: No priority data available

- **WHEN** priority data is unavailable for an agent
- **THEN** the card displays without a badge (graceful degradation)

---

### Requirement: Context Panel

Clicking an agent card SHALL open a context panel displaying detailed project information.

#### Scenario: Panel opens with full context

- **WHEN** user clicks an agent card
- **THEN** a side panel opens displaying:
  - Project roadmap (next_up, upcoming)
  - Current task state and details
  - Recently completed work (git-based)
  - Priority score and rationale (if available)
  - Button to focus terminal window
  - Close button

#### Scenario: Only one panel open

- **WHEN** user clicks a different agent card while panel is open
- **THEN** the panel updates to show the new agent's context

#### Scenario: Incomplete project data

- **WHEN** project data is incomplete (missing roadmap, etc.)
- **THEN** the panel displays available information gracefully

---

### Requirement: Notifications

Notifications SHALL alert the user when agents need input or complete tasks.

#### Scenario: Agent needs input notification

- **WHEN** an agent transitions to awaiting_input state
- **THEN** a macOS notification is sent via terminal-notifier

#### Scenario: Task completion notification

- **WHEN** an agent's task transitions to complete state
- **THEN** a macOS notification is sent via terminal-notifier

#### Scenario: Notification configuration

- **WHEN** notifications are disabled in config
- **THEN** no notifications are sent

---

### Requirement: Graceful Degradation

The dashboard SHALL function normally when prioritisation is disabled or unavailable.

#### Scenario: API error

- **WHEN** `/api/priorities` returns an error
- **THEN** the dashboard displays agents without priority features
- **AND** error is logged but not shown to user

#### Scenario: Prioritisation disabled

- **WHEN** prioritisation is disabled in config
- **THEN** all priority UI elements are hidden

#### Scenario: Auto-recovery

- **WHEN** API becomes available after being unavailable
- **THEN** the dashboard recovers and displays priority features
