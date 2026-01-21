# Tasks: Session Summarisation

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Log Discovery & Parsing (Phase 2)

- [x] 2.1 Implement `encode_project_path()` function to convert paths to Claude Code format
- [x] 2.2 Implement `get_claude_logs_directory()` to locate `~/.claude/projects/<encoded-path>/`
- [x] 2.3 Implement `find_session_log_file()` to find JSONL file matching session UUID
- [x] 2.4 Implement streaming JSONL parser with `parse_jsonl_line()` helper
- [x] 2.5 Add graceful error handling for malformed JSONL lines (skip and log warning)

## 3. Session End Detection (Phase 2)

- [x] 3.1 Add `idle_timeout_minutes` config option with default of 60
- [x] 3.2 Implement `get_last_activity_time()` to check JSONL file modification time
- [x] 3.3 Implement `is_session_idle()` to compare last activity against timeout
- [x] 3.4 Implement `is_session_process_alive()` to check if PID still exists
- [x] 3.5 Add session end detection to scan loop with `detect_session_end()`

## 4. Summarisation Engine (Phase 2)

- [x] 4.1 Implement `extract_files_modified()` from JSONL log content
- [x] 4.2 Implement `extract_commands_executed()` for bash commands and tool invocations
- [x] 4.3 Implement `extract_errors_encountered()` for failures and errors
- [x] 4.4 Implement `generate_summary_text()` to create human-readable summary paragraph
- [x] 4.5 Implement `summarise_session()` master function that coordinates extraction

## 5. State Persistence (Phase 2)

- [x] 5.1 Define session record schema (session_id, started_at, ended_at, duration_minutes, summary, files_modified, commands_run, errors)
- [x] 5.2 Implement `update_project_state()` to update YAML `state` section
- [x] 5.3 Implement `add_recent_session()` to add session to `recent_sessions` list
- [x] 5.4 Implement FIFO logic to maintain max 5 sessions (remove oldest when adding 6th)
- [x] 5.5 Integrate summarisation with session end detection (auto-trigger)

## 6. API Endpoint (Phase 2)

- [x] 6.1 Implement `POST /api/session/<id>/summarise` endpoint
- [x] 6.2 Add request validation for session ID
- [x] 6.3 Add error responses for invalid session ID (404) and missing log files (404)
- [x] 6.4 Return generated summary and confirm YAML update

## 7. Testing (Phase 3)

- [ ] 7.1 Test encode_project_path() with various path formats
- [ ] 7.2 Test JSONL parsing with valid and malformed data
- [ ] 7.3 Test session end detection (idle timeout and process termination)
- [ ] 7.4 Test summarisation extraction functions
- [ ] 7.5 Test state persistence and FIFO logic
- [ ] 7.6 Test API endpoint success and error cases

## 8. Final Verification

- [ ] 8.1 All tests passing
- [ ] 8.2 No linter errors
- [ ] 8.3 Manual verification of full workflow
- [ ] 8.4 Verify memory-efficient JSONL parsing with large files
