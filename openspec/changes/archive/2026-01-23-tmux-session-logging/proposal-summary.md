# Proposal Summary: tmux-session-logging

## Architecture Decisions

- **Follow existing logging pattern**: Use JSONL storage matching `lib/logging.py` pattern
- **Extend existing UI**: Add tmux tab to existing Logging panel rather than creating new panel
- **Instrument at function level**: Hook into `send_keys()` and `capture_pane()` in `lib/tmux.py`
- **Config-driven verbosity**: Debug toggle controls payload logging vs event-only logging
- **Correlation ID pattern**: Caller-generated UUIDs passed through both send and capture

## Implementation Approach

- Create new `lib/tmux_logging.py` module following `lib/logging.py` structure
- Modify `lib/tmux.py` to add optional `correlation_id` parameter and logging calls
- Add new API endpoints `/api/logs/tmux` and `/api/logs/tmux/stats`
- Extend Logging panel HTML/JS to support tmux tab with same features as OpenRouter
- Store logs in `data/logs/tmux.jsonl`

**Why this approach:**
- Follows established patterns for minimal learning curve
- Extends rather than duplicates existing infrastructure
- Config toggle allows production use without log bloat

## Files to Modify

### New Files
- `lib/tmux_logging.py` - TmuxLogEntry dataclass, read/write functions, search

### Modified Files
- `lib/tmux.py` - Add correlation_id param, logging calls to send_keys/capture_pane
- `monitor.py` - New API endpoints, UI updates for tmux tab
- `config.yaml.example` - Add debug_tmux_logging option

### Data Files
- `data/logs/tmux.jsonl` - New log storage file

## Acceptance Criteria

1. With `debug_tmux_logging: false`: Only event types logged, no payloads
2. With `debug_tmux_logging: true`: Full payloads logged with 10KB truncation
3. Correlation IDs link send/capture pairs when provided
4. tmux tab in Logging panel with same features as OpenRouter tab
5. Human-readable display with preserved newlines
6. Search, refresh, auto-refresh, pop-out all functional

## Constraints and Gotchas

- **Performance**: Logging must not add perceptible latency to tmux operations
- **Payload size**: Truncate at 10KB to prevent log bloat
- **Default off**: debug_tmux_logging should default to false
- **Preserve backwards compatibility**: send_keys/capture_pane signatures must remain backwards compatible (correlation_id is optional)
- **No OpenRouter modifications**: Do not modify existing OpenRouter logging code

## Git Change History

### Related Files
- **Modules**: `lib/tmux.py`
- **Tests**: `test_tmux.py`

### OpenSpec History
- `add-tmux-session-router` - Archived 2026-01-23 - Created lib/tmux.py with send_keys/capture_pane

### Implementation Patterns
- Detected structure: main_module → modules → tests
- Follow lib/logging.py pattern for dataclass and JSONL storage
- Follow monitor.py pattern for API endpoints

## Q&A History

No clarifications needed - PRD was comprehensive and workshop-validated.

## Dependencies

- **Python stdlib**: dataclasses, json, datetime, uuid (already used)
- **Existing modules**: lib/logging.py (pattern reference), lib/tmux.py (modification target)
- **No new pip packages required**

## Testing Strategy

### Unit Tests (lib/tmux_logging.py)
- TmuxLogEntry dataclass creation
- write_tmux_log_entry() writes valid JSONL
- read_tmux_logs() returns entries in correct order
- Payload truncation at 10KB boundary
- search_tmux_logs() filters correctly

### Integration Tests
- send_keys() creates log entry with correct metadata
- capture_pane() creates log entry with correct metadata
- Correlation IDs propagate correctly
- Debug toggle controls payload logging

### API Tests
- /api/logs/tmux returns JSON array
- Query params (since, search, session_id) filter correctly
- /api/logs/tmux/stats returns aggregates

### Manual Verification
- UI tab switching works
- Payloads display with preserved newlines
- Pop-out functionality works for tmux tab

## OpenSpec References

- proposal.md: `openspec/changes/tmux-session-logging/proposal.md`
- tasks.md: `openspec/changes/tmux-session-logging/tasks.md`
- spec.md: `openspec/changes/tmux-session-logging/specs/tmux-session-logging/spec.md`
