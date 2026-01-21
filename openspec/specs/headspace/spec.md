# headspace Specification

## Purpose
TBD - created by archiving change e1_s6_headspace. Update Purpose after archive.
## Requirements
### Requirement: Headspace Data Model

The system SHALL store headspace data with the following fields.

#### Scenario: Complete headspace data

- **WHEN** headspace is saved with all fields
- **THEN** the stored data SHALL include:
  - `current_focus`: string (required) - the user's focus statement
  - `constraints`: string (optional) - any constraints or limitations
  - `updated_at`: ISO timestamp - automatically set on save

#### Scenario: Headspace history tracking

- **WHEN** headspace is updated and history is enabled
- **THEN** the previous headspace value SHALL be appended to history with its timestamp
- **AND** the history SHALL be stored in reverse chronological order

### Requirement: GET /api/headspace Endpoint

The system SHALL provide a GET endpoint to retrieve the current headspace.

#### Scenario: Headspace exists

- **WHEN** a GET request is made to `/api/headspace`
- **AND** headspace data exists
- **THEN** the response status SHALL be 200
- **AND** the response SHALL include `{ success: true, data: { current_focus, constraints, updated_at } }`

#### Scenario: No headspace set

- **WHEN** a GET request is made to `/api/headspace`
- **AND** no headspace has been set
- **THEN** the response status SHALL be 200
- **AND** the response SHALL include `{ success: true, data: null }`

### Requirement: POST /api/headspace Endpoint

The system SHALL provide a POST endpoint to update the headspace.

#### Scenario: Update headspace with valid data

- **WHEN** a POST request is made to `/api/headspace`
- **AND** the request body contains `current_focus` (required)
- **THEN** the response status SHALL be 200
- **AND** `updated_at` SHALL be set to the current timestamp
- **AND** the previous headspace SHALL be added to history (if history enabled)
- **AND** the response SHALL include the updated headspace data

#### Scenario: Update headspace with missing required field

- **WHEN** a POST request is made to `/api/headspace`
- **AND** `current_focus` is missing or empty
- **THEN** the response status SHALL be 400
- **AND** the response SHALL include `{ success: false, error: "current_focus is required" }`

### Requirement: GET /api/headspace/history Endpoint

The system SHALL provide a GET endpoint to retrieve headspace history.

#### Scenario: History exists

- **WHEN** a GET request is made to `/api/headspace/history`
- **AND** history tracking is enabled
- **AND** history entries exist
- **THEN** the response status SHALL be 200
- **AND** the response SHALL include `{ success: true, data: [{ current_focus, constraints, updated_at }] }`

#### Scenario: History empty or disabled

- **WHEN** a GET request is made to `/api/headspace/history`
- **AND** history is empty or disabled
- **THEN** the response status SHALL be 200
- **AND** the response SHALL include `{ success: true, data: [] }`

### Requirement: Headspace Panel Display

The headspace panel SHALL appear at the top of the dashboard.

#### Scenario: View mode with headspace set

- **WHEN** the dashboard loads
- **AND** headspace is set
- **THEN** the panel SHALL display:
  - The current focus statement prominently (larger font, high contrast)
  - The constraints (if set) in secondary style (smaller, muted)
  - The "last updated" timestamp in human-friendly format (e.g., "2 hours ago")
  - An edit button/icon

#### Scenario: Empty state (no headspace)

- **WHEN** the dashboard loads
- **AND** no headspace is set
- **THEN** the panel SHALL display:
  - Prompt text: "What's your focus right now?"
  - Encouraging secondary text: "Setting a headspace helps you stay intentional."
  - A "Set" button to enter edit mode

### Requirement: Inline Editing

Users SHALL be able to edit headspace directly in the dashboard.

#### Scenario: Enter edit mode

- **WHEN** user clicks the edit button
- **THEN** the panel SHALL switch to edit mode
- **AND** the current focus SHALL be editable in a text field
- **AND** the constraints SHALL be editable in a text field
- **AND** Save and Cancel buttons SHALL be visible

#### Scenario: Save changes

- **WHEN** user clicks Save in edit mode
- **THEN** the headspace SHALL be saved via POST /api/headspace
- **AND** the panel SHALL exit edit mode
- **AND** the updated headspace SHALL be displayed
- **AND** no visible UI flicker SHALL occur

#### Scenario: Cancel changes

- **WHEN** user clicks Cancel in edit mode
- **THEN** the panel SHALL exit edit mode without saving
- **AND** the original headspace SHALL remain displayed

### Requirement: Configuration

The headspace feature SHALL be configurable.

#### Scenario: Feature enabled (default)

- **WHEN** `headspace.enabled` is true or not set in config
- **THEN** the headspace panel SHALL be displayed
- **AND** all headspace endpoints SHALL be functional

#### Scenario: Feature disabled

- **WHEN** `headspace.enabled` is false in config
- **THEN** the headspace panel SHALL NOT be displayed
- **AND** headspace endpoints SHALL return 404

#### Scenario: History enabled

- **WHEN** `headspace.history_enabled` is true in config
- **THEN** previous headspace values SHALL be saved to history on update

#### Scenario: History disabled (default)

- **WHEN** `headspace.history_enabled` is false or not set
- **THEN** no history SHALL be recorded
- **AND** GET /api/headspace/history SHALL return empty array

### Requirement: Data Persistence

Headspace data SHALL persist independently of project data.

#### Scenario: Browser refresh

- **WHEN** user refreshes the browser
- **THEN** the headspace SHALL remain as last saved

#### Scenario: Server restart

- **WHEN** the server is restarted
- **THEN** the headspace SHALL remain as last saved (from data/headspace.yaml)

#### Scenario: Storage format

- **WHEN** headspace is saved
- **THEN** it SHALL be stored in `data/headspace.yaml` in human-readable YAML format

