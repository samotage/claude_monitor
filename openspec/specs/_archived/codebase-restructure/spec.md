# codebase-restructure Specification

## Purpose
Restructures the codebase from a single monolithic monitor.py into a maintainable architecture with separate modules (lib/), extracted templates (templates/), and a root-level config module. Reduces monitor.py to under 900 lines while maintaining all functionality.
## Requirements
### Requirement: Template Extraction

The HTML/CSS/JS template SHALL be extracted from monitor.py to a separate file.

#### Scenario: Template loads from file

- **GIVEN** the server starts
- **WHEN** Flask initializes
- **THEN** templates are loaded from `templates/` directory
- **AND** `index.html` contains the complete dashboard UI

#### Scenario: Template unchanged in browser

- **GIVEN** the template was extracted correctly
- **WHEN** user loads the dashboard
- **THEN** the UI renders identically to before extraction

---

### Requirement: Module Structure

Each functional area SHALL have its own Python module under `lib/`.

#### Scenario: Notifications module exists

- **GIVEN** the restructure is complete
- **WHEN** importing `lib.notifications`
- **THEN** `send_macos_notification` function is available
- **AND** `check_state_changes_and_notify` function is available

#### Scenario: iTerm module exists

- **GIVEN** the restructure is complete
- **WHEN** importing `lib.iterm`
- **THEN** `get_iterm_windows` function is available
- **AND** `focus_iterm_window_by_pid` function is available

#### Scenario: Sessions module exists

- **GIVEN** the restructure is complete
- **WHEN** importing `lib.sessions`
- **THEN** `scan_sessions` function is available
- **AND** `parse_activity_state` function is available

#### Scenario: Projects module exists

- **GIVEN** the restructure is complete
- **WHEN** importing `lib.projects`
- **THEN** project data loading and saving functions are available
- **AND** roadmap management functions are available

#### Scenario: Summarization module exists

- **GIVEN** the restructure is complete
- **WHEN** importing `lib.summarization`
- **THEN** JSONL parsing functions are available
- **AND** summary generation functions are available

#### Scenario: Compression module exists

- **GIVEN** the restructure is complete
- **WHEN** importing `lib.compression`
- **THEN** compression queue management is available
- **AND** OpenRouter API integration is available

#### Scenario: Headspace module exists

- **GIVEN** the restructure is complete
- **WHEN** importing `lib.headspace`
- **THEN** `load_headspace` function is available
- **AND** priorities cache management is available

---

### Requirement: Configuration Module

Configuration loading SHALL be in a separate module at the project root.

#### Scenario: Config module at root

- **GIVEN** the restructure is complete
- **WHEN** importing `config`
- **THEN** `load_config` function is available
- **AND** `save_config` function is available

---

### Requirement: Monitor.py Core

The monitor.py file SHALL contain only Flask application essentials.

#### Scenario: Monitor.py is minimal

- **GIVEN** the restructure is complete
- **WHEN** examining monitor.py
- **THEN** it contains Flask app initialization
- **AND** it contains route definitions
- **AND** it contains the main() entry point
- **AND** it is under 900 lines

#### Scenario: Routes delegate to modules

- **GIVEN** a route is called
- **WHEN** the route handler executes
- **THEN** it delegates to the appropriate module function
- **AND** does not contain business logic inline

---

### Requirement: No Circular Imports

Module dependencies SHALL be acyclic.

#### Scenario: Server starts without import errors

- **GIVEN** all modules are created
- **WHEN** running `python monitor.py`
- **THEN** the server starts without ImportError
- **AND** no circular import warnings appear

---

### Requirement: Test Compatibility

All existing tests SHALL pass after restructuring.

#### Scenario: Test imports updated

- **GIVEN** tests import from monitor.py
- **WHEN** the restructure is complete
- **THEN** test imports are updated to new module paths
- **AND** all tests pass

#### Scenario: Coverage maintained

- **GIVEN** tests had X% coverage before restructure
- **WHEN** running pytest --cov after restructure
- **THEN** coverage is at least X%

---

### Requirement: Functional Equivalence

The application SHALL behave identically after restructuring.

#### Scenario: API responses unchanged

- **GIVEN** the restructure is complete
- **WHEN** calling any API endpoint
- **THEN** the response format is identical to before

#### Scenario: Notifications unchanged

- **GIVEN** the restructure is complete
- **WHEN** a session state changes
- **THEN** notifications are sent as before

#### Scenario: iTerm focus unchanged

- **GIVEN** the restructure is complete
- **WHEN** user clicks to focus a session
- **THEN** the correct iTerm window is focused
