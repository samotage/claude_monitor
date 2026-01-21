# Tasks: 01_codebase-restructure

## Phase 1: Setup

- [ ] Create `templates/` directory
- [ ] Create `lib/` directory with `__init__.py`
- [ ] Create `config.py` at project root

## Phase 2: Implementation

### 2.1 Template Extraction

- [ ] Extract `HTML_TEMPLATE` string from `monitor.py` to `templates/index.html`
- [ ] Remove the `HTML_TEMPLATE = """..."""` assignment from `monitor.py`
- [ ] Update Flask app initialization to use `template_folder='templates'`
- [ ] Verify template rendering with Flask's `render_template()`

### 2.2 Configuration Module

- [ ] Create `config.py` with `load_config()` function
- [ ] Move `save_config()` to `config.py`
- [ ] Move configuration validation logic
- [ ] Move default configuration constants
- [ ] Update `monitor.py` to import from `config.py`

### 2.3 Notifications Module

- [ ] Create `lib/notifications.py`
- [ ] Move `send_macos_notification()` function
- [ ] Move `check_state_changes_and_notify()` function
- [ ] Move notification state variables (`_previous_states`, `_notifications_enabled`)
- [ ] Move notification enable/disable functions
- [ ] Update `monitor.py` to import from `lib.notifications`

### 2.4 iTerm Integration Module

- [ ] Create `lib/iterm.py`
- [ ] Move `get_iterm_windows()` function
- [ ] Move `get_pid_tty()` function
- [ ] Move `focus_iterm_window_by_pid()` function
- [ ] Move `focus_window_by_tty()` helper function
- [ ] Move any AppleScript helper functions
- [ ] Update `monitor.py` to import from `lib.iterm`

### 2.5 Sessions Module

- [ ] Create `lib/sessions.py`
- [ ] Move `scan_sessions()` function
- [ ] Move `parse_activity_state()` function
- [ ] Move session state file parsing logic
- [ ] Move session data structures and constants
- [ ] Update `monitor.py` to import from `lib.sessions`

### 2.6 Projects Module

- [ ] Create `lib/projects.py`
- [ ] Move `load_project_data()` function
- [ ] Move `save_project_data()` function
- [ ] Move `parse_claude_md()` function
- [ ] Move `register_project()` function
- [ ] Move roadmap management functions
- [ ] Move state management functions
- [ ] Update `monitor.py` to import from `lib.projects`

### 2.7 Summarization Module

- [ ] Create `lib/summarization.py`
- [ ] Move JSONL parsing functions
- [ ] Move `extract_session_activity()` function
- [ ] Move `generate_summary()` function
- [ ] Move session end detection logic
- [ ] Move summary queue management
- [ ] Update `monitor.py` to import from `lib.summarization`

### 2.8 Compression Module

- [ ] Create `lib/compression.py`
- [ ] Move compression queue management
- [ ] Move `compress_session_history()` function
- [ ] Move OpenRouter API integration
- [ ] Move background worker thread logic
- [ ] Move compression state management
- [ ] Update `monitor.py` to import from `lib.compression`

### 2.9 Headspace Module

- [ ] Create `lib/headspace.py`
- [ ] Move `load_headspace()` function
- [ ] Move priorities cache (`_priorities_cache`)
- [ ] Move any headspace-related helper functions
- [ ] Update `monitor.py` to import from `lib.headspace`

### 2.10 Monitor.py Cleanup

- [ ] Remove all extracted function definitions
- [ ] Organize imports from new modules
- [ ] Ensure Flask routes delegate to module functions
- [ ] Keep only Flask app initialization, routes, and main()
- [ ] Add module docstring explaining the structure

## Phase 3: Testing

- [ ] Update `test_project_data.py` imports
- [ ] Update any other test files with imports from monitor.py
- [ ] Run `pytest` - verify all tests pass
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

- [ ] Add module docstrings to all new files
- [ ] Update CLAUDE.md if directory structure section needs changes
