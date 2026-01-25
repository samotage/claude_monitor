# Change: tmux Session Message Logging

## Why

The tmux integration layer provides bidirectional communication with Claude Code sessions, but there is no visibility into what messages are sent or received. This makes it impossible to debug discrepancies between actual session behavior and dashboard display. Adding structured logging with a debug toggle enables systematic debugging while keeping production logs minimal.

## What Changes

### Backend - Logging Infrastructure

- **NEW** `lib/tmux_logging.py` - Structured logging for tmux session messages
  - `TmuxLogEntry` dataclass (id, timestamp, session_id, tmux_session_name, direction, event_type, payload, correlation_id)
  - `write_tmux_log_entry()` - Write entries to JSONL file
  - `read_tmux_logs()` - Read and filter log entries
  - `search_tmux_logs()` - Search logs by query
  - Payload truncation for entries exceeding 10KB

- **MODIFIED** `lib/tmux.py` - Instrument existing functions with logging
  - `send_keys()` - Log outgoing messages with correlation_id
  - `capture_pane()` - Log incoming output with correlation_id
  - High-level events (session_started, session_stopped) when debug off

- **MODIFIED** `config.yaml` schema - Add `debug_tmux_logging: true|false` toggle

### Backend - API Endpoints

- **NEW** `/api/logs/tmux` (GET) - Return tmux log entries as JSON
  - Query params: `since`, `search`, `session_id`
- **NEW** `/api/logs/tmux/stats` (GET) - Return aggregate log statistics

### Frontend - UI Integration

- **MODIFIED** Logging panel - Add "tmux" tab alongside "openrouter"
- **NEW** tmux log entry cards - Collapsed/expanded view with direction indicators
- **NEW** Human-readable payload display - Preserved newlines, whitespace
- **NEW** Truncation notice - Display when payload was truncated
- **MODIFIED** Pop-out capability - Support tmux tab in standalone mode

## Impact

- **New capability**: `tmux-logging` - Debug logging for tmux session messages
- **Extends capability**: `logging-ui` - Adds tmux tab to existing logging panel
- **Affected specs**:
  - `tmux-router` (instrumentation added)
  - `logging-ui` (new tab added)
- **Affected code**:
  - `lib/tmux.py` (modified - add logging calls)
  - `lib/tmux_logging.py` (new)
  - `monitor.py` (modified - new API endpoints, UI updates)
  - `config.yaml.example` (modified - new config option)
- **Data changes**: New log file `data/logs/tmux.jsonl`
- **Backwards compatible**: Yes - logging is additive, debug mode defaults to off

## Dependencies

- Existing `lib/logging.py` pattern for JSONL storage
- Existing Logging UI panel for tab integration
- tmux-router capability (recently completed)

## Related Documents

- PRD: `docs/prds/logging/tmux-session-logging-prd.md`
- tmux-router spec: `openspec/specs/tmux-router/spec.md`
- logging-ui spec: `openspec/specs/logging-ui/spec.md`
