# Proposal Summary: terminal-logging-rename

## Architecture Decisions
- Single logging module approach maintained (no per-backend separation)
- Backend identification via field in log entries rather than separate files
- Backward compatibility through fallback reading of old files/config

## Implementation Approach
- Rename-first: change module, file, and API names before adding features
- Add backend field to dataclass with automatic population from backend classes
- UI filter is client-side JavaScript filtering (no new API complexity)
- Clear logs via simple file truncation

## Files to Modify

### Rename Operations
- `lib/tmux_logging.py` → `lib/terminal_logging.py`
- `test_tmux_logging.py` → `test_terminal_logging.py`

### Modify Operations
- `lib/terminal_logging.py` - Add backend field, update dataclass name
- `lib/backends/tmux.py` - Pass backend="tmux" to log calls
- `lib/backends/wezterm.py` - Pass backend="wezterm" to log calls
- `monitor.py` - Update API endpoints, imports
- `templates/logging.html` - Tab label change
- `static/js/logging.js` - Filter logic, clear logs, backend display
- `static/css/logging.css` - Backend indicator styling, clear button

## Acceptance Criteria
1. Tab displays "terminal" not "tmux"
2. Each log entry has backend field
3. Backend indicator visible in UI
4. Filter by backend works (UI and API)
5. Clear logs button with confirmation
6. Backward compatibility: old logs/config still work
7. All tests pass

## Constraints and Gotchas
- Log file migration: only read from old file if new doesn't exist (one-time)
- Config fallback: check for old key only if new key is absent
- Backend field default: entries without backend are assumed "tmux" (legacy)
- Filter state: persist during session via JavaScript variable (not localStorage)
- Clear logs confirmation: use browser confirm() for simplicity

## Git Change History

### Related Files
- **Modules:** `lib/logging.py`, `lib/tmux_logging.py`
- **Tests:** `test_tmux_logging.py`
- **Templates:** `templates/logging.html`
- **Static:** `static/css/logging.css`, `static/js/logging.js`

### OpenSpec History
- `logging-ui` (archived 2026-01-22) - Initial logging UI implementation
- `tmux-session-logging` (archived 2026-01-23) - tmux session message logging

### Implementation Patterns
- Typical structure: main_module → modules → tests → templates → static
- Follows existing backend abstraction pattern in `lib/backends/`

## Q&A History
- No clarifications needed - PRD is comprehensive and unambiguous
- All requirements clearly specified with no conflicts detected

## Dependencies
- No new packages required
- Uses existing terminal-notifier for any notifications
- No database migrations needed

## Testing Strategy
- Rename test file to match module rename
- Test backend field presence in new entries
- Test default backend for legacy entries
- Test API filter query parameter
- Test clear logs endpoint (success, empty file)
- Test backward-compatible config reading
- Test backward-compatible log file reading
- Manual verification of UI components

## OpenSpec References
- proposal.md: openspec/changes/terminal-logging-rename/proposal.md
- tasks.md: openspec/changes/terminal-logging-rename/tasks.md
- spec.md: openspec/changes/terminal-logging-rename/specs/terminal-logging-rename/spec.md
