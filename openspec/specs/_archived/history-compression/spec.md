# history-compression Specification

## Purpose
Provides AI-powered compression of session summaries into narrative project history using OpenRouter API. Manages a compression queue with retry logic, runs a background thread for periodic processing, and maintains compressed history in project YAML for context continuity.
## Requirements
### Requirement: Compression Queue Management

The system SHALL detect sessions removed from `recent_sessions` and queue them for compression.

#### Scenario: Session removed from rolling window

- **GIVEN** a project with 5 sessions in `recent_sessions`
- **WHEN** a 6th session is added (triggering FIFO removal)
- **THEN** the system SHALL add the removed session to the pending compression queue

#### Scenario: Queue persistence

- **GIVEN** sessions in the pending compression queue
- **WHEN** the application restarts
- **THEN** the pending queue SHALL persist and sessions SHALL remain queued

#### Scenario: Successful compression

- **GIVEN** a session in the pending compression queue
- **WHEN** compression completes successfully
- **THEN** the system SHALL remove the session from the pending queue

### Requirement: History Schema

The system SHALL maintain a `history` section in project YAML with compressed summaries.

#### Scenario: First compression

- **GIVEN** a project with empty history
- **WHEN** the first session is compressed
- **THEN** the system SHALL initialize `history.summary` with the compressed narrative

#### Scenario: Subsequent compression

- **GIVEN** a project with existing history
- **WHEN** a new session is compressed
- **THEN** the system SHALL merge the new summary with existing history to create a unified narrative

#### Scenario: History structure

- **GIVEN** a compression operation
- **WHEN** history is updated
- **THEN** it SHALL contain `summary` (string) and `last_compressed_at` (ISO timestamp)

### Requirement: OpenRouter Integration

The system SHALL integrate with OpenRouter's chat completion API for AI summarisation.

#### Scenario: Successful API call

- **GIVEN** a valid OpenRouter API key
- **WHEN** a compression request is made
- **THEN** the system SHALL authenticate with Bearer token and receive a summary

#### Scenario: Rate limiting

- **GIVEN** an OpenRouter API call
- **WHEN** the response is HTTP 429 (rate limited)
- **THEN** the system SHALL retry with exponential backoff

#### Scenario: Authentication failure

- **GIVEN** an invalid or missing API key
- **WHEN** a compression request is made
- **THEN** the system SHALL log the error (without exposing the key) and keep the session queued

#### Scenario: Timeout handling

- **GIVEN** an OpenRouter API call
- **WHEN** no response is received within 30 seconds
- **THEN** the system SHALL timeout and retry later

### Requirement: AI Summarisation

The system SHALL generate meaningful narrative summaries from session data.

#### Scenario: Summary content

- **GIVEN** session data with files modified, commands run, and errors
- **WHEN** compression is requested
- **THEN** the summary SHALL preserve: what was worked on, key decisions, blockers encountered, current status

#### Scenario: History continuity

- **GIVEN** existing history and a new session to compress
- **WHEN** the compression prompt is built
- **THEN** it SHALL include existing history context to maintain narrative continuity

#### Scenario: Token efficiency

- **GIVEN** a compression request
- **WHEN** the prompt is constructed
- **THEN** it SHALL use minimal tokens (concise system prompt, structured input)

### Requirement: Graceful Failure Handling

The system SHALL handle API failures without losing session data.

#### Scenario: Retry logic

- **GIVEN** a failed API call
- **WHEN** retrying compression
- **THEN** the system SHALL use exponential backoff (1min, 5min, 30min)

#### Scenario: Max retries in cycle

- **GIVEN** maximum retry attempts reached in a cycle
- **WHEN** the session still cannot be compressed
- **THEN** the session SHALL remain queued for the next compression cycle

#### Scenario: No data loss

- **GIVEN** any API failure scenario
- **WHEN** compression fails
- **THEN** the original session data SHALL remain intact in the pending queue

### Requirement: Background Processing

The system SHALL process compressions asynchronously without blocking the main application.

#### Scenario: Non-blocking

- **GIVEN** a background compression process running
- **WHEN** Flask receives HTTP requests
- **THEN** request handling SHALL NOT be blocked by compression

#### Scenario: Periodic check

- **GIVEN** the compression interval configured (default: 5 minutes)
- **WHEN** the interval elapses
- **THEN** the system SHALL check for pending compressions and process them

### Requirement: Configuration

The system SHALL support configurable OpenRouter settings.

#### Scenario: API key configuration

- **GIVEN** a config.yaml file
- **WHEN** the `openrouter.api_key` is set
- **THEN** the system SHALL use this key for API authentication

#### Scenario: Model selection

- **GIVEN** a config.yaml file
- **WHEN** `openrouter.model` is not set
- **THEN** the system SHALL default to `anthropic/claude-3-haiku`

#### Scenario: API key security

- **GIVEN** any logging or error output
- **WHEN** the API key could potentially appear
- **THEN** the system SHALL NEVER log or expose the API key value
