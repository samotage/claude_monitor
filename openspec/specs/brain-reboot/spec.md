# brain-reboot Specification

## Purpose
Enables quick context reload for projects via a "Brain Reboot" feature. Uses LLM-powered briefing generation combining roadmap focus, git-based progress narratives, and active agent context. Provides a REST API endpoint for the dashboard side panel.

## Requirements
### Requirement: Reboot API Endpoint

The system SHALL provide a `GET /api/projects/<project_id>/brain-reboot` endpoint that returns an LLM-generated briefing for quick context reload.

#### Scenario: Successful reboot with complete data

- **WHEN** a GET request is made to `/api/projects/<project_id>/brain-reboot` for a project with complete data
- **THEN** the response status SHALL be 200
- **AND** the response SHALL include:
  - `briefing`: LLM-generated context summary string
  - `headspace`: current user headspace (if set)
  - `roadmap`: project roadmap data
  - `recently_completed`: git-based progress narrative
  - `active_agents`: list of active agents for this project

#### Scenario: Reboot with partial data

- **WHEN** a GET request is made to `/api/projects/<project_id>/brain-reboot` for a project with some missing data
- **THEN** the response status SHALL be 200
- **AND** missing sections SHALL be returned as null or empty structures
- **AND** present sections SHALL be returned normally

#### Scenario: Project not found

- **WHEN** a GET request is made to `/api/projects/<project_id>/brain-reboot` for a non-existent project
- **THEN** the response status SHALL be 404
- **AND** the response SHALL include an error message

### Requirement: Brain Refresh Endpoint

The system SHALL also provide a `GET /api/projects/<project_id>/brain-refresh` endpoint for quick refresh without LLM.

#### Scenario: Refresh returns cached data

- **WHEN** a GET request is made to `/api/projects/<project_id>/brain-refresh`
- **THEN** the response SHALL return roadmap and progress data without calling the LLM
- **AND** this endpoint is faster but provides less context than brain-reboot

### Requirement: Reboot Button

Each project card SHALL display a Reboot button that opens the briefing panel.

#### Scenario: Click reboot button

- **WHEN** user clicks the Reboot button on a project card
- **THEN** the side panel SHALL open
- **AND** the panel SHALL display the LLM-generated briefing for that project

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

The system SHALL handle missing data gracefully.

#### Scenario: Empty roadmap

- **WHEN** the project has no roadmap data
- **THEN** the roadmap section SHALL display an appropriate empty state message

#### Scenario: No recent git activity

- **WHEN** the project has no recent commits
- **THEN** the recently_completed section SHALL be empty or null

#### Scenario: No active agents

- **WHEN** the project has no active agents
- **THEN** the active_agents list SHALL be empty

#### Scenario: Partial data display

- **WHEN** some sections have data and others are empty
- **THEN** populated sections SHALL display their data normally
- **AND** empty sections SHALL be returned as null or empty structures
- **AND** empty sections SHALL NOT prevent the briefing from being generated
