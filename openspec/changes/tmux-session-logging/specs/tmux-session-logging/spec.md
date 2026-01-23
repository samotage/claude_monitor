# Specification: tmux-session-logging

## ADDED Requirements

### Requirement: Debug Logging Toggle

The system SHALL provide a configuration option `debug_tmux_logging` that controls logging verbosity.

#### Scenario: Debug mode disabled (default)

- **GIVEN** `debug_tmux_logging` is `false` in config.yaml
- **WHEN** a tmux operation occurs (send_keys, capture_pane)
- **THEN** only high-level event types are logged (send_attempted, capture_attempted)
- **AND** no payload content is recorded

#### Scenario: Debug mode enabled

- **GIVEN** `debug_tmux_logging` is `true` in config.yaml
- **WHEN** a tmux operation occurs
- **THEN** full payload content is logged
- **AND** payloads exceeding 10KB are truncated with size indicator

---

### Requirement: Structured Log Entry Format

Each tmux log entry SHALL contain structured metadata for debugging.

#### Scenario: Log entry creation

- **WHEN** a tmux operation is logged
- **THEN** the entry contains:
  - `id`: Unique identifier (UUID)
  - `timestamp`: ISO 8601 format
  - `session_id`: Session identifier
  - `tmux_session_name`: tmux session name
  - `direction`: "in" or "out"
  - `event_type`: Operation type (send_keys, capture_pane, session_started, etc.)
  - `payload`: Content (when debug enabled, subject to truncation)
  - `correlation_id`: Links related send/capture pairs

---

### Requirement: Correlation ID Linking

The system SHALL support correlation IDs to link related operations.

#### Scenario: Send and capture correlation

- **GIVEN** a caller generates a correlation_id before sending
- **WHEN** the caller passes the same correlation_id to send_keys() and capture_pane()
- **THEN** both log entries contain the same correlation_id
- **AND** the entries can be filtered together by correlation_id

#### Scenario: No correlation ID provided

- **WHEN** send_keys() or capture_pane() is called without correlation_id
- **THEN** the log entry's correlation_id field is null
- **AND** the operation proceeds normally

---

### Requirement: Payload Truncation

Large payloads SHALL be truncated to prevent excessive log file growth.

#### Scenario: Payload exceeds size limit

- **GIVEN** a payload exceeds 10KB in size
- **WHEN** the log entry is created
- **THEN** the payload is truncated to 10KB
- **AND** a `truncated` flag is set to true
- **AND** the `original_size` field contains the original byte count

#### Scenario: Payload within size limit

- **GIVEN** a payload is 10KB or smaller
- **WHEN** the log entry is created
- **THEN** the full payload is stored
- **AND** the `truncated` flag is false or absent

---

### Requirement: UI Tab Integration

The Logging panel SHALL display a "tmux" tab for viewing tmux logs.

#### Scenario: Tab navigation

- **WHEN** user opens the Logging panel
- **THEN** a "tmux" tab appears alongside the "openrouter" tab
- **AND** the "openrouter" tab remains the default/active tab

#### Scenario: Tab switching

- **WHEN** user clicks the "tmux" tab
- **THEN** the panel displays tmux log entries
- **AND** the tab is visually marked as active

---

### Requirement: Human-Readable Display

Log payloads SHALL be displayed in human-readable format.

#### Scenario: Multiline payload display

- **GIVEN** a log entry has a payload with newline characters
- **WHEN** the entry is expanded in the UI
- **THEN** newlines are rendered as actual line breaks
- **AND** whitespace is preserved

#### Scenario: Truncated payload display

- **GIVEN** a log entry has a truncated payload
- **WHEN** the entry is expanded in the UI
- **THEN** a notice indicates the content was truncated
- **AND** the original size is displayed

---

### Requirement: Feature Parity with OpenRouter Tab

The tmux tab SHALL have the same features as the OpenRouter tab.

#### Scenario: Search functionality

- **WHEN** user enters text in the search field
- **THEN** log entries are filtered to show only matches
- **AND** filtering completes within 100ms

#### Scenario: Refresh functionality

- **WHEN** user clicks the refresh button
- **THEN** the log list is updated with latest entries
- **AND** the current scroll position is preserved

#### Scenario: Auto-refresh

- **GIVEN** auto-refresh is active
- **WHEN** new log entries are created
- **THEN** they appear in the list without manual action
- **AND** expanded entries remain expanded

#### Scenario: Pop-out functionality

- **WHEN** user clicks the pop-out button while on tmux tab
- **THEN** a new browser tab opens with tmux logs in standalone mode
- **AND** the pop-out view has its own search and refresh

---

### Requirement: Empty and Error States

The UI SHALL handle empty and error states gracefully.

#### Scenario: No logs exist

- **GIVEN** no tmux logs have been recorded
- **WHEN** user views the tmux tab
- **THEN** an empty state message is displayed: "No tmux logs yet. Logs will appear here when tmux session operations occur."

#### Scenario: Load error

- **GIVEN** log data cannot be loaded (file error, API error)
- **WHEN** user views the tmux tab
- **THEN** an error message is displayed
- **AND** a retry button is available

---

## MODIFIED Requirements

### Requirement: tmux send_keys() Function

The existing `send_keys()` function in `lib/tmux.py` SHALL be modified to support logging.

#### Scenario: send_keys with logging

- **GIVEN** the send_keys() function is called
- **WHEN** the operation completes (success or failure)
- **THEN** a log entry is written with direction="out"
- **AND** event_type="send_keys"
- **AND** payload contains the text sent (if debug enabled)

#### Scenario: send_keys with correlation_id

- **GIVEN** send_keys() is called with a correlation_id parameter
- **WHEN** the log entry is created
- **THEN** the correlation_id is included in the entry

---

### Requirement: tmux capture_pane() Function

The existing `capture_pane()` function in `lib/tmux.py` SHALL be modified to support logging.

#### Scenario: capture_pane with logging

- **GIVEN** the capture_pane() function is called
- **WHEN** the operation completes
- **THEN** a log entry is written with direction="in"
- **AND** event_type="capture_pane"
- **AND** payload contains the captured output (if debug enabled)

#### Scenario: capture_pane with correlation_id

- **GIVEN** capture_pane() is called with a correlation_id parameter
- **WHEN** the log entry is created
- **THEN** the correlation_id is included in the entry
