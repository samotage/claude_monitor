# Tasks: tmux Session Message Logging

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Configuration (Phase 2)

- [x] 2.1 Add `debug_tmux_logging` option to config.yaml schema
- [x] 2.2 Update `config.yaml.example` with new option and documentation
- [x] 2.3 Add config loading for the new option in monitor.py

## 3. Logging Infrastructure (Phase 2)

- [x] 3.1 Create `lib/tmux_logging.py` module
- [x] 3.2 Define `TmuxLogEntry` dataclass with all required fields
- [x] 3.3 Implement `ensure_log_directory()` function
- [x] 3.4 Implement `write_tmux_log_entry()` with JSONL storage
- [x] 3.5 Implement payload truncation logic (10KB limit)
- [x] 3.6 Implement `read_tmux_logs()` function
- [x] 3.7 Implement `get_tmux_logs_since()` for incremental fetching
- [x] 3.8 Implement `search_tmux_logs()` for filtering
- [x] 3.9 Implement `get_tmux_log_stats()` for aggregates

## 4. tmux Integration (Phase 2)

- [x] 4.1 Modify `send_keys()` to accept optional correlation_id parameter
- [x] 4.2 Add logging call to `send_keys()` for outgoing messages
- [x] 4.3 Modify `capture_pane()` to accept optional correlation_id parameter
- [x] 4.4 Add logging call to `capture_pane()` for incoming output
- [x] 4.5 Implement debug toggle check before logging payloads
- [x] 4.6 Log high-level events when debug is off

## 5. API Endpoints (Phase 2)

- [x] 5.1 Add `/api/logs/tmux` GET endpoint in monitor.py
- [x] 5.2 Implement query parameter handling (since, search, session_id)
- [x] 5.3 Add `/api/logs/tmux/stats` GET endpoint
- [x] 5.4 Test API endpoints return correct JSON format

## 6. Frontend - Tab Integration (Phase 2)

- [x] 6.1 Add "tmux" tab button to logging panel sub-navigation
- [x] 6.2 Implement tab switching logic for tmux logs
- [x] 6.3 Update pop-out functionality to support tmux tab
- [x] 6.4 Ensure OpenRouter remains the default tab

## 7. Frontend - Log Display (Phase 2)

- [x] 7.1 Create tmux log entry card template (collapsed view)
- [x] 7.2 Add direction indicator (→ OUT / ← IN)
- [x] 7.3 Implement expand/collapse functionality
- [x] 7.4 Display correlation ID in expanded view
- [x] 7.5 Implement human-readable payload display with preserved newlines
- [x] 7.6 Add truncation notice when payload was truncated
- [x] 7.7 Style log entries to match OpenRouter tab (dark theme)

## 8. Frontend - Features (Phase 2)

- [x] 8.1 Implement search filtering for tmux logs
- [x] 8.2 Add refresh button functionality
- [x] 8.3 Implement auto-refresh polling
- [x] 8.4 Add empty state message
- [x] 8.5 Add error state with retry option

## 9. Testing (Phase 3)

- [x] 9.1 Unit tests for TmuxLogEntry dataclass
- [x] 9.2 Unit tests for write_tmux_log_entry()
- [x] 9.3 Unit tests for read_tmux_logs() and filtering
- [x] 9.4 Unit tests for payload truncation
- [x] 9.5 Unit tests for search functionality
- [x] 9.6 Integration tests for send_keys() logging
- [x] 9.7 Integration tests for capture_pane() logging
- [x] 9.8 Integration tests for API endpoints
- [x] 9.9 Test debug toggle behavior (on vs off)
- [x] 9.10 Test correlation ID linking

## 10. Final Verification (Phase 4)

- [ ] 10.1 All tests passing
- [ ] 10.2 No linter errors
- [ ] 10.3 Manual verification: debug off logs only events
- [ ] 10.4 Manual verification: debug on logs full payloads
- [ ] 10.5 Manual verification: correlation IDs link correctly
- [ ] 10.6 Manual verification: UI displays human-readable content
- [ ] 10.7 Manual verification: pop-out works for tmux tab
