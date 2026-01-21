# session-summarisation Specification

## Purpose
Implements automatic session summarization by parsing Claude Code JSONL logs to extract activity metrics (files modified, commands run, errors encountered). Detects session end via idle timeout or process termination, generates human-readable summaries, and persists them to project YAML with FIFO window management.
## Requirements
### Requirement: Claude Code Log Discovery

The system SHALL locate Claude Code JSONL log files by encoding the project path (replacing `/` with `-`) and looking in `~/.claude/projects/<encoded-path>/`.

#### Scenario: Valid project path encoding

- **GIVEN** a project path `/Users/sam/projects/my-app`
- **WHEN** the system encodes the path for log lookup
- **THEN** it SHALL produce the encoded path `-Users-sam-projects-my-app`

#### Scenario: Log directory found

- **GIVEN** an encoded project path
- **WHEN** the log directory exists at `~/.claude/projects/<encoded-path>/`
- **THEN** the system SHALL return the directory path

#### Scenario: Log directory not found

- **GIVEN** an encoded project path
- **WHEN** the log directory does not exist
- **THEN** the system SHALL return None without error

### Requirement: JSONL Parsing

The system SHALL parse JSONL log files, extracting message type, content, timestamp, session ID, and working directory from each line.

#### Scenario: Valid JSONL line

- **GIVEN** a valid JSON line in the log file
- **WHEN** the parser processes the line
- **THEN** it SHALL extract all available fields into a structured object

#### Scenario: Malformed JSONL line

- **GIVEN** an invalid JSON line in the log file
- **WHEN** the parser encounters the line
- **THEN** it SHALL skip the line, log a warning, and continue processing

#### Scenario: Large log file

- **GIVEN** a log file exceeding 100MB
- **WHEN** the parser processes the file
- **THEN** it SHALL use streaming (line-by-line) to avoid loading the entire file into memory

### Requirement: Session End Detection

The system SHALL detect when a monitored session becomes idle or terminates.

#### Scenario: Idle timeout detection

- **GIVEN** a session with no new log entries
- **WHEN** the idle period exceeds the configured timeout (default 60 minutes)
- **THEN** the system SHALL mark the session as ended and trigger summarisation

#### Scenario: Process termination detection

- **GIVEN** a monitored session with a known PID
- **WHEN** the PID no longer exists in the process table
- **THEN** the system SHALL mark the session as ended and trigger summarisation

#### Scenario: Configurable timeout

- **GIVEN** `idle_timeout_minutes` is set in config.yaml
- **WHEN** the system checks for idle sessions
- **THEN** it SHALL use the configured value instead of the default

### Requirement: Session Summarisation

The system SHALL generate summaries from session logs without AI dependency.

#### Scenario: Extract files modified

- **GIVEN** a session log containing file modification events
- **WHEN** summarisation is triggered
- **THEN** the system SHALL extract a list of modified file paths

#### Scenario: Extract commands executed

- **GIVEN** a session log containing bash commands and tool invocations
- **WHEN** summarisation is triggered
- **THEN** the system SHALL extract a count and list of executed commands

#### Scenario: Extract errors encountered

- **GIVEN** a session log containing error messages or failures
- **WHEN** summarisation is triggered
- **THEN** the system SHALL extract error details

#### Scenario: Generate summary text

- **GIVEN** extracted files, commands, and errors
- **WHEN** summary generation is complete
- **THEN** the system SHALL produce a human-readable summary paragraph

### Requirement: State Persistence

The system SHALL persist session summaries to project YAML files.

#### Scenario: Update state section

- **GIVEN** a completed session with a generated summary
- **WHEN** persistence is triggered
- **THEN** the system SHALL update the project YAML `state` section with the latest session outcome

#### Scenario: Add to recent sessions

- **GIVEN** a completed session record
- **WHEN** persistence is triggered
- **THEN** the system SHALL add the session to the `recent_sessions` list

#### Scenario: FIFO limit enforcement

- **GIVEN** `recent_sessions` already contains 5 sessions
- **WHEN** a 6th session is added
- **THEN** the system SHALL remove the oldest session to maintain the 5-session limit

#### Scenario: Session record schema

- **GIVEN** a session to be persisted
- **WHEN** the record is created
- **THEN** it SHALL include: session_id, started_at, ended_at, duration_minutes, summary, files_modified (list), commands_run (count), errors (count)

### Requirement: Manual Summarisation API

The system SHALL provide a `POST /api/session/<id>/summarise` endpoint for manual summarisation.

#### Scenario: Valid session ID

- **GIVEN** a valid session ID with associated log file
- **WHEN** POST request is made to `/api/session/<id>/summarise`
- **THEN** the system SHALL return HTTP 200 with the generated summary

#### Scenario: Invalid session ID

- **GIVEN** a session ID with no associated log file
- **WHEN** POST request is made to `/api/session/<id>/summarise`
- **THEN** the system SHALL return HTTP 404 with an error message

#### Scenario: Session not found

- **GIVEN** a session ID that doesn't match any known session
- **WHEN** POST request is made to `/api/session/<id>/summarise`
- **THEN** the system SHALL return HTTP 404 with an error message

