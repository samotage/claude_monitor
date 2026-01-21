# roadmap-management Specification

## Purpose
TBD - created by archiving change project-roadmap-management. Update Purpose after archive.
## Requirements
### Requirement: Roadmap Schema Structure

The project YAML roadmap section SHALL support a structured format with four sections: `next_up` (object), `upcoming` (list), `later` (list), and `not_now` (list).

#### Scenario: Valid roadmap with all sections

- **GIVEN** a project YAML file
- **WHEN** the roadmap section contains all four sections with valid data
- **THEN** the system SHALL accept and persist the data

#### Scenario: Partial roadmap

- **GIVEN** a project YAML file
- **WHEN** the roadmap section contains only some fields
- **THEN** the system SHALL accept the partial roadmap as valid

#### Scenario: Empty roadmap

- **GIVEN** a project YAML file
- **WHEN** the roadmap section is `{}`
- **THEN** the system SHALL treat it as a roadmap with all fields empty

### Requirement: GET Roadmap API Endpoint

The system SHALL provide a `GET /api/project/<name>/roadmap` endpoint that returns the project's roadmap data as JSON.

#### Scenario: Valid project name

- **GIVEN** a project exists with name "my-project"
- **WHEN** a GET request is made to `/api/project/my-project/roadmap`
- **THEN** the system SHALL return HTTP 200 with the roadmap JSON

#### Scenario: Invalid project name

- **GIVEN** no project exists with name "nonexistent"
- **WHEN** a GET request is made to `/api/project/nonexistent/roadmap`
- **THEN** the system SHALL return HTTP 404 with an error message

### Requirement: POST Roadmap API Endpoint

The system SHALL provide a `POST /api/project/<name>/roadmap` endpoint that updates the project's roadmap data from a JSON request body.

#### Scenario: Valid update

- **GIVEN** a project exists with name "my-project"
- **WHEN** a POST request with valid roadmap JSON is made to `/api/project/my-project/roadmap`
- **THEN** the system SHALL update the roadmap and return HTTP 200 with the updated data
- **AND** the system SHALL preserve all non-roadmap project data

#### Scenario: Invalid project name

- **GIVEN** no project exists with name "nonexistent"
- **WHEN** a POST request is made to `/api/project/nonexistent/roadmap`
- **THEN** the system SHALL return HTTP 404 with an error message

#### Scenario: Malformed request body

- **GIVEN** a project exists with name "my-project"
- **WHEN** a POST request with invalid JSON structure is made
- **THEN** the system SHALL return HTTP 400 with a validation error message

### Requirement: Roadmap Panel Display

The dashboard SHALL include an expandable roadmap panel on each project card that is collapsed by default.

#### Scenario: Expand roadmap panel

- **GIVEN** a project card is displayed
- **WHEN** the user clicks the expand control
- **THEN** the roadmap panel SHALL expand to show all four sections

#### Scenario: Display populated roadmap

- **GIVEN** a project has roadmap data
- **WHEN** the roadmap panel is expanded
- **THEN** the panel SHALL display `next_up` with title, why, and definition_of_done
- **AND** the panel SHALL display `upcoming`, `later`, `not_now` as lists

#### Scenario: Display empty roadmap

- **GIVEN** a project has an empty roadmap
- **WHEN** the roadmap panel is expanded
- **THEN** the panel SHALL display placeholder text indicating no roadmap is defined

### Requirement: Roadmap Edit Mode

The roadmap panel SHALL support an edit mode for modifying roadmap fields.

#### Scenario: Enter edit mode

- **GIVEN** the roadmap panel is expanded
- **WHEN** the user clicks the Edit button
- **THEN** all roadmap fields SHALL become editable form inputs

#### Scenario: Save changes

- **GIVEN** the user is in edit mode with modified data
- **WHEN** the user clicks Save
- **THEN** the system SHALL POST the updated roadmap to the API
- **AND** display a loading indicator during the operation
- **AND** display a success message on completion
- **AND** exit edit mode

#### Scenario: Cancel changes

- **GIVEN** the user is in edit mode with modified data
- **WHEN** the user clicks Cancel
- **THEN** the system SHALL discard all changes
- **AND** exit edit mode without saving

#### Scenario: Save failure

- **GIVEN** the user is in edit mode
- **WHEN** the user clicks Save and the API returns an error
- **THEN** the system SHALL display an error message
- **AND** keep the user in edit mode to retry or cancel

