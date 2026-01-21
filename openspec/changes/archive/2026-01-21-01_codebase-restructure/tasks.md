# Tasks: 01_codebase-restructure

## Phase 1: Setup

- [x] Create `templates/` directory
- [x] Create `lib/` directory with `__init__.py`
- [x] Create `config.py` at project root

## Phase 2: Implementation

### 2.1 Template Extraction

- [x] Extract `HTML_TEMPLATE` string from `monitor.py` to `templates/index.html`
- [x] Remove the `HTML_TEMPLATE = """..."""` assignment from `monitor.py`
- [x] Update Flask app initialization to use `template_folder='templates'`
- [x] Verify template rendering with Flask's `render_template()`

### 2.2 Configuration Module

- [x] Create `config.py` with `load_config()` function
- [x] Move `save_config()` to `config.py`
- [x] Move configuration validation logic
- [x] Move default configuration constants
- [x] Update `monitor.py` to import from `config.py`

### 2.3 Notifications Module

- [x] Create `lib/notifications.py`
- [x] Move `send_macos_notification()` function
- [x] Move `check_state_changes_and_notify()` function
- [x] Move notification state variables (`_previous_states`, `_notifications_enabled`)
- [x] Move notification enable/disable functions
- [x] Update `monitor.py` to import from `lib.notifications`

### 2.4 iTerm Integration Module

- [x] Create `lib/iterm.py`
- [x] Move `get_iterm_windows()` function
- [x] Move `get_pid_tty()` function
- [x] Move `focus_iterm_window_by_pid()` function
- [x] Move `focus_window_by_tty()` helper function
- [x] Move any AppleScript helper functions
- [x] Update `monitor.py` to import from `lib.iterm`

### 2.5 Sessions Module

- [x] Create `lib/sessions.py`
- [x] Move `scan_sessions()` function
- [x] Move `parse_activity_state()` function
- [x] Move session state file parsing logic
- [x] Move session data structures and constants
- [x] Update `monitor.py` to import from `lib.sessions`

### 2.6 Projects Module

- [x] Create `lib/projects.py`
- [x] Move `load_project_data()` function
- [x] Move `save_project_data()` function
- [x] Move `parse_claude_md()` function
- [x] Move `register_project()` function
- [x] Move roadmap management functions
- [x] Move state management functions
- [x] Update `monitor.py` to import from `lib.projects`

### 2.7 Summarization Module

- [x] Create `lib/summarization.py`
- [x] Move JSONL parsing functions
- [x] Move `extract_session_activity()` function
- [x] Move `generate_summary()` function
- [x] Move session end detection logic
- [x] Move summary queue management
- [x] Update `monitor.py` to import from `lib.summarization`

### 2.8 Compression Module

- [x] Create `lib/compression.py`
- [x] Move compression queue management
- [x] Move `compress_session_history()` function
- [x] Move OpenRouter API integration
- [x] Move background worker thread logic
- [x] Move compression state management
- [x] Update `monitor.py` to import from `lib.compression`

### 2.9 Headspace Module

- [x] Create `lib/headspace.py`
- [x] Move `load_headspace()` function
- [x] Move priorities cache (`_priorities_cache`)
- [x] Move any headspace-related helper functions
- [x] Update `monitor.py` to import from `lib.headspace`

### 2.10 Monitor.py Cleanup

- [x] Remove all extracted function definitions
- [x] Organize imports from new modules
- [x] Ensure Flask routes delegate to module functions
- [x] Keep only Flask app initialization, routes, and main()
- [x] Add module docstring explaining the structure

## Phase 3: Testing

- [x] Update `test_project_data.py` imports
- [x] Update any other test files with imports from monitor.py
- [x] Run `pytest` - verify all tests pass
- [ ] Run `pytest --cov` - verify coverage maintained

## Phase 4: Verification

- [ ] Start server with `./restart_server.sh`
- [ ] Verify dashboard renders at http://localhost:5050
- [ ] Verify session cards display correctly
- [ ] Verify click-to-focus opens context panel
- [ ] Verify priority badges display
- [ ] Verify Recommended Next panel works
- [ ] Verify notifications toggle works
- [ ] Test sending a test notification
- [ ] Verify API endpoints return expected data:
  - [ ] `GET /api/sessions`
  - [ ] `GET /api/config`
  - [ ] `GET /api/notifications`
  - [ ] `GET /api/priorities`
  - [ ] `GET /api/headspace`
- [ ] Verify no circular import errors on startup
- [ ] Verify no console errors in browser

## Phase 5: Documentation

- [x] Add module docstrings to all new files
- [ ] Update CLAUDE.md if directory structure section needs changes
