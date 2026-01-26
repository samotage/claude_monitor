# terminal-logging-rename Specification

## Purpose
Defines the terminal logging system with backend-agnostic naming and filtering. Renames tmux-specific logging to generic "terminal" logging to support multiple backends (tmux, WezTerm). Provides API endpoints for log retrieval with backend filtering, log clearing, and statistics.
## Requirements
### Requirement: Backend Identification

Each terminal log entry SHALL include a `backend` field identifying the source terminal backend.

#### Scenario: New log entry from tmux backend

- **WHEN** the tmux backend creates a log entry
- **THEN** the entry SHALL have `backend: "tmux"`

#### Scenario: New log entry from WezTerm backend

- **WHEN** the WezTerm backend creates a log entry
- **THEN** the entry SHALL have `backend: "wezterm"`

#### Scenario: Legacy log entry without backend field

- **WHEN** a log entry is read that lacks a `backend` field
- **THEN** the system SHALL default the value to `"tmux"`

---

### Requirement: Backend Filter API

The terminal log API SHALL support filtering by backend.

#### Scenario: Filter by tmux backend

- **WHEN** a GET request is made to `/api/logs/terminal?backend=tmux`
- **THEN** only entries with `backend: "tmux"` SHALL be returned

#### Scenario: Filter by wezterm backend

- **WHEN** a GET request is made to `/api/logs/terminal?backend=wezterm`
- **THEN** only entries with `backend: "wezterm"` SHALL be returned

#### Scenario: No filter specified

- **WHEN** a GET request is made to `/api/logs/terminal` without backend parameter
- **THEN** all entries SHALL be returned regardless of backend

---

### Requirement: Clear Logs Endpoint

The system SHALL provide an endpoint to delete all terminal logs.

#### Scenario: Clear logs successfully

- **WHEN** a DELETE request is made to `/api/logs/terminal`
- **THEN** all entries in `data/logs/terminal.jsonl` SHALL be deleted
- **AND** the response SHALL indicate success

#### Scenario: Clear logs with empty file

- **WHEN** a DELETE request is made and the log file is already empty
- **THEN** the response SHALL indicate success (no error)

---

### Requirement: Backward Compatible Configuration

The system SHALL support migration from old configuration keys.

#### Scenario: Only new config key present

- **WHEN** `terminal_logging.debug_enabled` is set in config
- **THEN** that value SHALL be used

#### Scenario: Only old config key present

- **WHEN** `tmux_logging.debug_enabled` is set but `terminal_logging.debug_enabled` is not
- **THEN** the old value SHALL be used as fallback

#### Scenario: Both config keys present

- **WHEN** both old and new config keys are set
- **THEN** the new `terminal_logging.debug_enabled` value SHALL take precedence

---

### Requirement: Backward Compatible Log File

The system SHALL support migration from old log file location.

#### Scenario: New log file exists

- **WHEN** `data/logs/terminal.jsonl` exists
- **THEN** it SHALL be used as the log source

#### Scenario: Only old log file exists

- **WHEN** `data/logs/tmux.jsonl` exists but `data/logs/terminal.jsonl` does not
- **THEN** `data/logs/tmux.jsonl` SHALL be read as the log source

#### Scenario: Neither file exists

- **WHEN** neither log file exists
- **THEN** a new `data/logs/terminal.jsonl` SHALL be created on first write

---

### Requirement: Terminal Logging API Endpoints

All logging API endpoints SHALL use the `/api/logs/terminal` prefix.

#### Endpoints

- `GET /api/logs/terminal` - Retrieve log entries (with optional `backend` filter)
- `DELETE /api/logs/terminal` - Clear all log entries
- `GET /api/logs/terminal/stats` - Retrieve log statistics
- `GET /api/logs/terminal/debug` - Get debug logging state
- `POST /api/logs/terminal/debug` - Set debug logging state

---

### Requirement: Terminal Logging UI

The Logging panel SHALL display a "terminal" tab instead of "tmux".

#### Scenario: Tab display

- **WHEN** the user opens the Logging panel
- **THEN** the tab label SHALL read "terminal"

#### Scenario: Backend indicator in collapsed view

- **WHEN** a log entry is displayed in collapsed view
- **THEN** it SHALL show a backend indicator badge (e.g., `[tmux]` or `[wezterm]`)

#### Scenario: Backend indicator in expanded view

- **WHEN** a log entry is expanded
- **THEN** it SHALL display the backend in the detail section

#### Scenario: Backend filter controls

- **WHEN** the user views the terminal log tab
- **THEN** filter buttons (All / tmux / wezterm) SHALL be visible
- **AND** clicking a filter SHALL show only matching entries

#### Scenario: Clear logs button

- **WHEN** the user clicks the "Clear Logs" button
- **THEN** a confirmation dialog SHALL appear
- **AND** upon confirmation, all logs SHALL be deleted
