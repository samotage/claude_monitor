## Why

Claude Headspace currently provides no visibility into OpenRouter API calls, making it difficult to track costs, debug failures, and optimize API usage. Developers need real-time insight into what API calls are being made and their outcomes.

## What Changes

- Add new "Logging" tab to main navigation
- Create logging panel with tabbed sub-navigation for log types
- Implement OpenRouter API log tab with:
  - Expandable log entries showing timestamp, model, status, cost, tokens
  - Full request/response details on expansion
  - Search functionality for filtering
  - Auto-refresh for new entries
  - Pop-out capability for side-by-side monitoring
- Add backend API endpoint to serve log data
- Define log data persistence format specification
- Handle empty and error states gracefully

## Impact

- Affected specs: dashboard-ui (new logging panel capability)
- Affected code:
  - `templates/index.html` - Add logging tab and panel HTML
  - `static/js/logging.js` - New file for logging panel logic
  - `static/css/logging.css` - New file for logging panel styles
  - `static/js/tabs.js` - Update tab initialization for logging tab
  - `monitor.py` - Add `/api/logs/openrouter` endpoint and log reading logic
  - `lib/logging.py` - New file for log data management (reading, format spec)

## Dependencies

- Requires log files to exist (written by API calling code - out of scope for this change)
- Uses existing tab navigation pattern
- Uses existing dark theme CSS variables

## Risks

- Log file format must be defined clearly for future API calling code to write
- Large log volumes may impact performance (mitigated by search/filter)
