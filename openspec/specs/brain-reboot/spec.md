# brain-reboot Specification

## Purpose
TBD - created by archiving change e1_s5_brain-reboot-view. Update Purpose after archive.
## Requirements
### Requirement: Reboot API Endpoint

The system SHALL provide a `GET /api/project/<name>/reboot` endpoint that returns a structured briefing for quick context reload.

#### Scenario: Successful reboot with complete data

- **WHEN** a GET request is made to `/api/project/<name>/reboot` for a project with complete data
- **THEN** the response status SHALL be 200
- **AND** the response SHALL include a `briefing` object with:
  - `roadmap`: `{ focus, why, next_steps[] }`
  - `state`: `{ status, last_action, last_session_time }`
  - `recent`: `[{ date, summary, files_count }]`
  - `history`: `{ narrative, period }`
- **AND** the response SHALL include a `meta` object with:
  - `is_stale`: boolean
  - `last_activity`: ISO timestamp or null
  - `staleness_hours`: number or null

#### Scenario: Reboot with partial data

- **WHEN** a GET request is made to `/api/project/<name>/reboot` for a project with some missing data
- **THEN** the response status SHALL be 200
- **AND** missing sections SHALL be returned as null or empty structures
- **AND** present sections SHALL be returned normally

#### Scenario: Project not found

- **WHEN** a GET request is made to `/api/project/<name>/reboot` for a non-existent project
- **THEN** the response status SHALL be 404
- **AND** the response SHALL include `{ success: false, error: "Project '<name>' not found" }`

### Requirement: Stale Detection

The system SHALL calculate project staleness based on time since last session activity.

#### Scenario: Fresh project (not stale)

- **WHEN** a project's last activity is within the configured stale threshold
- **THEN** `meta.is_stale` SHALL be `false`
- **AND** the project card SHALL display with normal appearance

#### Scenario: Stale project

- **WHEN** a project's last activity exceeds the configured stale threshold
- **THEN** `meta.is_stale` SHALL be `true`
- **AND** `meta.staleness_hours` SHALL contain the hours since last activity
- **AND** the project card SHALL display with faded/dimmed appearance
- **AND** the project card SHALL show a clock icon and "Stale - X hours" label

#### Scenario: Configurable threshold

- **WHEN** `stale_threshold_hours` is set in config.yaml
- **THEN** that value SHALL be used as the stale threshold
- **WHEN** `stale_threshold_hours` is not set
- **THEN** the default value of 4 hours SHALL be used

### Requirement: Reboot Button

Each project card SHALL display a Reboot button that opens the briefing panel.

#### Scenario: Click reboot button

- **WHEN** user clicks the Reboot button on a project card
- **THEN** the side panel SHALL open within 500ms
- **AND** the panel SHALL display the structured briefing for that project

#### Scenario: Button emphasis on stale cards

- **WHEN** a project is stale
- **THEN** the Reboot button SHALL be visually emphasized

### Requirement: Side Panel

The briefing SHALL be displayed in a side panel alongside the dashboard.

#### Scenario: Open side panel

- **WHEN** the Reboot button is clicked
- **THEN** a side panel SHALL slide in from the right side
- **AND** the panel SHALL display the project name and a close button
- **AND** the panel SHALL NOT block interaction with the rest of the dashboard

#### Scenario: Close side panel

- **WHEN** user clicks the close button or clicks outside the panel
- **THEN** the panel SHALL close

#### Scenario: Only one panel at a time

- **WHEN** user clicks Reboot on a different project while a panel is open
- **THEN** the current panel SHALL close
- **AND** the new project's panel SHALL open

### Requirement: Empty State Handling

The system SHALL handle missing data gracefully with helpful prompts.

#### Scenario: Empty roadmap

- **WHEN** the project has no roadmap data
- **THEN** the roadmap section SHALL display: "No roadmap defined yet. Would you like to define one?"
- **AND** SHALL include a clickable link to the roadmap editor

#### Scenario: Empty state

- **WHEN** the project has no session state data
- **THEN** the state section SHALL display: "No session activity recorded yet"

#### Scenario: Empty recent sessions

- **WHEN** the project has no recent sessions
- **THEN** the recent section SHALL display: "No recent sessions"

#### Scenario: Empty history

- **WHEN** the project has no compressed history
- **THEN** the history section SHALL display: "No compressed history yet"

#### Scenario: Partial data display

- **WHEN** some sections have data and others are empty
- **THEN** populated sections SHALL display their data normally
- **AND** empty sections SHALL display their respective empty state message
- **AND** empty sections SHALL NOT prevent other sections from displaying

