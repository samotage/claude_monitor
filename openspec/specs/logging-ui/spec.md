# logging-ui Specification

## Purpose
Provides a web UI for viewing OpenRouter API call logs and terminal session logs. Routes are implemented in `src/routes/logging.py` with business logic delegated to `lib/logging.py` and `lib/terminal_logging.py`. The UI displays logs with search, filtering, and auto-refresh capabilities.
## Requirements
### Requirement: Logging Tab Navigation

The application SHALL provide a "Logging" tab in the main navigation bar.

#### Scenario: User accesses logging panel

- **WHEN** user clicks the "Logging" tab button
- **THEN** the logging panel is displayed with sub-tab navigation

#### Scenario: Logging tab position

- **WHEN** the main navigation is rendered
- **THEN** the "Logging" tab appears after existing tabs (dashboard, focus, config, help)

---

### Requirement: OpenRouter Log Display

The logging panel SHALL display OpenRouter API call logs in a list format.

#### Scenario: Log entry collapsed view

- **WHEN** a log entry is displayed in collapsed state
- **THEN** it shows: timestamp, model identifier, status indicator, cost, and token count summary

#### Scenario: Log entry expanded view

- **WHEN** user clicks a collapsed log entry
- **THEN** it expands to show: full request payload, full response content, detailed token breakdown, and error message (if applicable)

#### Scenario: Log entry collapse

- **WHEN** user clicks an expanded log entry
- **THEN** it collapses back to summary view

#### Scenario: Log ordering

- **WHEN** log entries are displayed
- **THEN** they appear in reverse chronological order (newest first)

---

### Requirement: Search Functionality

The logging panel SHALL provide search capability to filter log entries.

#### Scenario: Search filters entries

- **WHEN** user enters text in the search field
- **THEN** only log entries containing the search text in any visible field are displayed

#### Scenario: Clear search

- **WHEN** user clears the search field
- **THEN** all log entries are displayed again

---

### Requirement: Auto-Refresh

The logging panel SHALL automatically refresh to show new log entries.

#### Scenario: New entries appear

- **WHEN** new log entries are available
- **THEN** they appear in the list without requiring page refresh

#### Scenario: Preserve user state

- **WHEN** auto-refresh occurs
- **THEN** scroll position is preserved and expanded entries remain expanded

---

### Requirement: Pop-out Capability

The logging panel SHALL support opening in a new browser tab.

#### Scenario: Open in new tab

- **WHEN** user clicks the pop-out action
- **THEN** the logging panel opens in a new browser tab

#### Scenario: Pop-out independence

- **WHEN** logging panel is in pop-out mode
- **THEN** it functions independently with auto-refresh enabled

---

### Requirement: Empty State

The logging panel SHALL handle the case when no logs exist.

#### Scenario: No log entries

- **WHEN** no log entries exist
- **THEN** an empty state message is displayed: "No API logs yet. Logs will appear here when OpenRouter API calls are made."

---

### Requirement: Error State

The logging panel SHALL handle errors gracefully.

#### Scenario: Log data load failure

- **WHEN** log data cannot be loaded from the backend
- **THEN** an error state is displayed with a retry option

---

### Requirement: Log Data Specification

The logging system SHALL capture specific data for each OpenRouter API call.

#### Scenario: Required log fields

- **WHEN** an OpenRouter API call is logged
- **THEN** the following data is captured:
  - Timestamp (ISO 8601 format)
  - Request payload (messages array)
  - Response content (text returned)
  - Input token count
  - Output token count
  - Cost (calculated from tokens and model pricing)
  - Model identifier
  - Success/failure boolean
  - Error message (if failure)

---
