# Tasks: Add tmux Session Router

## 1. Core tmux Module

- [ ] 1.1 Create `lib/tmux.py` with session listing function
- [ ] 1.2 Add `send_keys()` function for text injection
- [ ] 1.3 Add `capture_pane()` function for output capture
- [ ] 1.4 Add `session_exists()` and `create_session()` helpers
- [ ] 1.5 Add `is_tmux_available()` check function (returns bool, caches result)

## 2. Wrapper Integration

- [ ] 2.1 Modify `bin/claude-monitor` to check if project has tmux enabled in config
- [ ] 2.2 Create named tmux session when tmux is enabled for project
- [ ] 2.3 Update state file to include `tmux_session` and `session_type` fields
- [ ] 2.4 Add session cleanup on exit (optional kill or leave running)
- [ ] 2.5 Handle case where tmux session already exists for project
- [ ] 2.6 Fall back to direct launch if tmux not available (with warning)

## 3. Session Scanner Integration

- [ ] 3.1 Add `scan_tmux_sessions()` to `lib/sessions.py`
- [ ] 3.2 Merge tmux sessions with iTerm sessions in `scan_sessions()`
- [ ] 3.3 Add `session_type` field to distinguish tmux vs iTerm sessions
- [ ] 3.4 Update activity detection to work with tmux capture output

## 4. Project tmux Configuration

- [ ] 4.1 Add `tmux: true|false` support to project config schema
- [ ] 4.2 Add `get_project_tmux_status()` function returning readiness info
- [ ] 4.3 Add `/api/projects/<name>/tmux/enable` POST endpoint
- [ ] 4.4 Add `/api/projects/<name>/tmux/disable` POST endpoint
- [ ] 4.5 Update `/api/config` or `/api/projects` to include tmux status per project

## 5. Session Control API Endpoints

- [ ] 5.1 Add `/api/send/<session_id>` POST endpoint
- [ ] 5.2 Add `/api/output/<session_id>` GET endpoint with `?lines=N` param
- [ ] 5.3 Add session type validation (only tmux sessions can receive input)
- [ ] 5.4 Add error handling for non-existent sessions

## 6. Dashboard UI

- [ ] 6.1 Add tmux status indicator to project cards/settings (ready/not enabled/unavailable)
- [ ] 6.2 Add "Enable tmux" button for unconfigured projects
- [ ] 6.3 Add tmux install notice when tmux not available on system
- [ ] 6.4 Disable enable buttons with tooltip when tmux unavailable

## 7. Testing

- [ ] 7.1 Add unit tests for `lib/tmux.py` functions
- [ ] 7.2 Add integration test for send/capture round-trip
- [ ] 7.3 Test wrapper creates tmux session correctly when enabled
- [ ] 7.4 Test wrapper falls back correctly when tmux disabled or unavailable
- [ ] 7.5 Test hybrid iTerm + tmux session listing
- [ ] 7.6 Test enable/disable API endpoints update config correctly

## 8. Documentation

- [ ] 8.1 Update CLAUDE.md with tmux workflow
- [ ] 8.2 Update README.md with tmux setup instructions
- [ ] 8.3 Document new API endpoints
- [ ] 8.4 Add tmux troubleshooting section
