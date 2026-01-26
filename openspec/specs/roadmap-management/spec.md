# roadmap-management Specification

## Purpose
Defines the roadmap management system that allows users to track project direction through a structured schema (next_up, upcoming, later, not_now, recently_completed). Provides REST API endpoints for reading and updating roadmaps, with Pydantic validation to ensure data consistency. Roadmaps are stored in the centralized state.yaml via AgentStore.

## Requirements
### Requirement: Roadmap Schema Structure

The Roadmap model SHALL support a structured format with five sections: `next_up` (RoadmapItem), `upcoming` (list), `later` (list), `not_now` (list), and `recently_completed` (string, git-based).

#### Scenario: Valid roadmap with all sections

- **GIVEN** a project in AgentStore
- **WHEN** the roadmap section contains all sections with valid data
- **THEN** the system SHALL accept and persist the data via Pydantic validation

#### Scenario: Partial roadmap

- **GIVEN** a project in AgentStore
- **WHEN** the roadmap section contains only some fields
- **THEN** the system SHALL accept the partial roadmap as valid (optional fields)

#### Scenario: Empty roadmap

- **GIVEN** a project in AgentStore
- **WHEN** the roadmap is None or empty
- **THEN** the system SHALL treat it as a roadmap with all fields at defaults

### Requirement: GET Roadmap API Endpoint

The system SHALL provide a `GET /api/projects/<project_id>/roadmap` endpoint that returns the project's roadmap data as JSON.

#### Scenario: Valid project ID

- **GIVEN** a project exists with ID "my-project"
- **WHEN** a GET request is made to `/api/projects/my-project/roadmap`
- **THEN** the system SHALL return HTTP 200 with the roadmap JSON

#### Scenario: Invalid project ID

- **GIVEN** no project exists with ID "nonexistent"
- **WHEN** a GET request is made to `/api/projects/nonexistent/roadmap`
- **THEN** the system SHALL return HTTP 404 with an error message

### Requirement: POST Roadmap API Endpoint

The system SHALL provide a `POST /api/projects/<project_id>/roadmap` endpoint that updates the project's roadmap data from a JSON request body.

#### Scenario: Valid update

- **GIVEN** a project exists with ID "my-project"
- **WHEN** a POST request with valid roadmap JSON is made to `/api/projects/my-project/roadmap`
- **THEN** the system SHALL update the roadmap via AgentStore and return HTTP 200 with the updated data

#### Scenario: Invalid project ID

- **GIVEN** no project exists with ID "nonexistent"
- **WHEN** a POST request is made to `/api/projects/nonexistent/roadmap`
- **THEN** the system SHALL return HTTP 404 with an error message

#### Scenario: Malformed request body

- **GIVEN** a project exists with ID "my-project"
- **WHEN** a POST request with invalid JSON structure is made
- **THEN** the system SHALL return HTTP 400 with a Pydantic validation error message

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
