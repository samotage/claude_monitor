# priorities Specification

## Purpose
TBD - created by archiving change e1_s7_ai-prioritisation. Update Purpose after archive.
## Requirements
### Requirement: Context Aggregation

The system SHALL aggregate context from multiple data sources to inform AI prioritisation.

#### Scenario: Aggregate with complete data

- **WHEN** all data sources are available (headspace, roadmaps, project states, sessions)
- **THEN** the system combines all context into a unified structure for the AI prompt

#### Scenario: Aggregate with missing headspace

- **WHEN** headspace data is not set
- **THEN** the system proceeds with roadmap and activity data only
- **AND** the AI prompt indicates headspace is not available

#### Scenario: Aggregate with missing roadmap

- **WHEN** a project has no roadmap data
- **THEN** the system includes the project with activity state only
- **AND** does not fail the entire aggregation

### Requirement: AI-Powered Prioritisation Prompt

The system SHALL construct a token-efficient prompt that instructs the AI to rank sessions.

#### Scenario: Prompt with headspace

- **WHEN** headspace is set
- **THEN** the prompt emphasises relevance to current_focus as primary ranking factor
- **AND** considers activity_state as secondary factor

#### Scenario: Prompt without headspace

- **WHEN** headspace is not set
- **THEN** the prompt ranks by roadmap urgency (next_up items) and activity state
- **AND** sessions with input_needed receive attention boost

#### Scenario: Activity state boost

- **WHEN** a session has activity_state = input_needed
- **THEN** the AI prompt instructs to boost its priority score
- **AND** the rationale reflects that the session needs attention

### Requirement: Priorities API Endpoint

The system SHALL expose `GET /api/priorities` returning ranked sessions with rationale.

#### Scenario: Successful prioritisation

- **WHEN** `GET /api/priorities` is called
- **AND** prioritisation is enabled
- **THEN** the response includes a `priorities` array ordered by priority_score descending
- **AND** each entry contains project_name, session_id, priority_score (0-100), rationale, activity_state
- **AND** metadata includes timestamp, headspace_summary, cache_hit, soft_transition_pending

#### Scenario: Prioritisation disabled

- **WHEN** `GET /api/priorities` is called
- **AND** prioritisation is disabled in config
- **THEN** the response returns HTTP 404 with error message

#### Scenario: OpenRouter unavailable

- **WHEN** `GET /api/priorities` is called
- **AND** OpenRouter API is unavailable or returns error
- **THEN** the response returns sessions in default order (alphabetical by project name)
- **AND** includes error indication in metadata

### Requirement: Response Caching

The system SHALL cache priorities within the polling interval to avoid redundant API calls.

#### Scenario: Cache hit

- **WHEN** `GET /api/priorities` is called
- **AND** cached priorities exist
- **AND** cache age is less than polling_interval
- **THEN** the cached response is returned
- **AND** metadata.cache_hit is true

#### Scenario: Cache miss

- **WHEN** `GET /api/priorities` is called
- **AND** no cached priorities exist OR cache has expired
- **THEN** fresh prioritisation is performed
- **AND** metadata.cache_hit is false

#### Scenario: Force refresh

- **WHEN** `GET /api/priorities?refresh=true` is called
- **THEN** fresh prioritisation is performed regardless of cache state
- **AND** cache is updated with new results

### Requirement: Soft Transitions

The system SHALL delay priority reordering while sessions are actively processing.

#### Scenario: Session processing

- **WHEN** priorities are refreshed
- **AND** any session has activity_state = processing
- **THEN** the new priorities are stored as pending
- **AND** the previous order is returned
- **AND** metadata.soft_transition_pending is true

#### Scenario: All sessions paused

- **WHEN** priorities are refreshed
- **AND** all sessions are idle or input_needed
- **THEN** pending priorities (if any) are applied
- **AND** the new order is returned
- **AND** metadata.soft_transition_pending is false

### Requirement: Priority Configuration

The system SHALL allow configuration of prioritisation behavior in config.yaml.

#### Scenario: Configuration structure

- **WHEN** priorities configuration is read
- **THEN** it includes enabled (boolean), polling_interval (seconds), model (string)
- **AND** defaults are: enabled=true, polling_interval=60, model=same as compression

#### Scenario: Dynamic configuration

- **WHEN** configuration is changed in config.yaml
- **THEN** changes take effect without application restart
- **AND** next prioritisation request uses new settings

