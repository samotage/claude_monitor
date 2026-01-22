## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Backend Implementation (Phase 2)

- [ ] 2.1 Create `lib/logging.py` with log data format specification
  - Define LogEntry dataclass with all required fields
  - Define log file path constant (e.g., `data/logs/openrouter.jsonl`)
  - Implement `read_openrouter_logs()` function to parse log file
  - Implement `get_logs_since(timestamp)` for incremental fetching

- [ ] 2.2 Add API endpoint in `monitor.py`
  - Add `/api/logs/openrouter` GET endpoint
  - Support `since` query parameter for polling
  - Support `search` query parameter for filtering
  - Return JSON array of log entries

- [ ] 2.3 Create standalone logging route
  - Add `/logging` route for pop-out capability
  - Render logging panel in standalone mode

## 3. Frontend Structure (Phase 2)

- [ ] 3.1 Update `templates/index.html`
  - Add "logging" tab button to navigation
  - Add `logging-tab` content div with sub-tab structure
  - Add OpenRouter sub-tab container
  - Add search input field
  - Add pop-out button
  - Add empty state element
  - Add error state element

- [ ] 3.2 Create `static/css/logging.css`
  - Style logging sub-tab navigation
  - Style log entry cards (collapsed state)
  - Style log entry expanded state
  - Style search input
  - Style pop-out button
  - Style empty and error states
  - Add expand/collapse animation (200ms)

- [ ] 3.3 Update CSS imports in `templates/index.html`
  - Add logging.css link

## 4. Frontend Logic (Phase 2)

- [ ] 4.1 Create `static/js/logging.js`
  - Implement `initLogging()` function
  - Implement `loadOpenRouterLogs()` for initial fetch
  - Implement `renderLogEntry(entry)` for card rendering
  - Implement `toggleLogEntry(entryId)` for expand/collapse
  - Implement `searchLogs(query)` for filtering
  - Implement `startLogPolling()` for auto-refresh
  - Implement `openLoggingPopout()` for new tab
  - Handle empty state display
  - Handle error state with retry

- [ ] 4.2 Update `static/js/tabs.js`
  - Add logging tab initialization in `initTabNavigation()`
  - Call `initLogging()` on first tab visit (lazy load pattern)

- [ ] 4.3 Update JS imports in `templates/index.html`
  - Add logging.js script tag

## 5. Log Entry Display (Phase 2)

- [ ] 5.1 Implement collapsed card view
  - Display timestamp in human-readable format
  - Display model identifier
  - Display success/failure status icon
  - Display cost formatted as currency
  - Display total token count

- [ ] 5.2 Implement expanded card view
  - Show full request payload with JSON formatting
  - Show full response content
  - Show detailed token breakdown (input/output)
  - Show error message if failed
  - Smooth animation on expand/collapse

## 6. Search and Filtering (Phase 2)

- [ ] 6.1 Implement client-side search
  - Filter log entries as user types
  - Match against all visible fields
  - Update display without scroll jumping
  - Show "no results" state if nothing matches

## 7. Auto-Refresh (Phase 2)

- [ ] 7.1 Implement polling mechanism
  - Poll backend at reasonable interval (5-10 seconds)
  - Use `since` parameter to fetch only new entries
  - Prepend new entries to list (newest first)
  - Preserve expanded state of existing entries
  - Preserve scroll position

## 8. Testing (Phase 3)

- [ ] 8.1 Create test log file with sample data
  - Include success and failure entries
  - Include various models
  - Include range of token counts and costs

- [ ] 8.2 Write backend tests
  - Test log file reading
  - Test API endpoint responses
  - Test search parameter filtering
  - Test since parameter filtering

- [ ] 8.3 Manual UI verification
  - Verify tab navigation works
  - Verify log entries display correctly
  - Verify expand/collapse animation
  - Verify search filtering
  - Verify auto-refresh
  - Verify pop-out functionality
  - Verify empty state
  - Verify error state with retry

## 9. Final Verification (Phase 4)

- [ ] 9.1 All tests passing
- [ ] 9.2 No linter errors
- [ ] 9.3 Manual verification complete
- [ ] 9.4 Code review complete
