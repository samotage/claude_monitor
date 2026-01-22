# Proposal Summary: logging-ui

## Architecture Decisions

- **Tab-based UI pattern**: Follow existing tab navigation pattern used by dashboard, focus, config, help tabs
- **Sub-tab navigation**: Logging panel has its own internal tabs for future extensibility (OpenRouter first, more later)
- **JSONL log format**: Use line-delimited JSON for log storage - easy to append, easy to parse
- **Client-side search**: Filter logs in browser for responsive UX, backend provides all data
- **Polling for auto-refresh**: Use interval-based polling with `since` parameter rather than WebSockets for simplicity

## Implementation Approach

- Create new `lib/logging.py` module for log file reading and format specification
- Add API endpoint `/api/logs/openrouter` to serve log data as JSON
- Create new frontend files: `static/js/logging.js` and `static/css/logging.css`
- Update `templates/index.html` to add logging tab and panel structure
- Update `static/js/tabs.js` for lazy initialization of logging tab
- Standalone `/logging` route for pop-out capability

## Files to Modify

### New Files
- `lib/logging.py` - Log data management and format specification
- `static/js/logging.js` - Logging panel frontend logic
- `static/css/logging.css` - Logging panel styles

### Modified Files
- `templates/index.html` - Add logging tab button and panel HTML
- `static/js/tabs.js` - Add logging tab initialization
- `monitor.py` - Add API endpoint and route

## Acceptance Criteria

1. Logging tab visible in main navigation
2. Clicking tab shows logging panel with sub-tabs
3. OpenRouter sub-tab displays log entries
4. Collapsed entries show: timestamp, model, status, cost, tokens
5. Expanded entries show: full request, response, token breakdown, error
6. Search filters entries by any field
7. Newest entries appear first
8. Auto-refresh adds new entries without disruption
9. Pop-out opens in new browser tab
10. Empty state shown when no logs

## Constraints and Gotchas

- **Log file must exist**: The UI reads from a log file that doesn't exist yet. Initial state will be empty.
- **Out of scope**: This PRD does NOT modify existing API calling code to write logs. That's a separate task.
- **Cost calculation**: Requires knowing model pricing. May need to be estimated or pulled from OpenRouter.
- **Large logs**: If log file grows very large, performance may degrade. Consider adding pagination in future.
- **Token counting**: OpenRouter API response includes usage data - make sure log writing captures it.

## Git Change History

### Related Files
This is a new capability - no existing files specifically for logging.

### OpenSpec History
- `e1_s8_headspace-aware-dashboard` (2026-01-21) - Recent dashboard UI work, similar patterns

### Implementation Patterns
Existing tab pattern:
1. Add tab button in `templates/index.html` nav
2. Add tab content div in `templates/index.html` body
3. Add JS file for tab-specific logic
4. Add CSS file for tab-specific styles
5. Update `tabs.js` to initialize on first visit

## Q&A History

- No clarification questions needed - PRD was complete and unambiguous

## Dependencies

- No new Python packages required
- No external services beyond existing OpenRouter integration
- No database - uses file-based log storage

## Testing Strategy

### Backend Tests
- Test log file reading with sample data
- Test API endpoint response format
- Test `since` parameter filtering
- Test `search` parameter filtering
- Test empty log file handling

### Frontend Manual Testing
- Tab navigation works
- Log entries display correctly (collapsed and expanded)
- Expand/collapse animations smooth
- Search filters in real-time
- Auto-refresh adds new entries
- Pop-out opens in new tab
- Empty state displays
- Error state displays with retry

## OpenSpec References

- proposal.md: openspec/changes/logging-ui/proposal.md
- tasks.md: openspec/changes/logging-ui/tasks.md
- spec.md: openspec/changes/logging-ui/specs/logging-ui/spec.md
