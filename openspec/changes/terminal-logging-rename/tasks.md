## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Module and Dataclass Rename
- [ ] 2.1.1 Rename `lib/tmux_logging.py` to `lib/terminal_logging.py`
- [ ] 2.1.2 Rename `TmuxLogEntry` dataclass to `TerminalLogEntry`
- [ ] 2.1.3 Add `backend` field to `TerminalLogEntry` with default "tmux"

### 2.2 Log File Migration
- [ ] 2.2.1 Update log file path to `data/logs/terminal.jsonl`
- [ ] 2.2.2 Implement fallback: read from `tmux.jsonl` if `terminal.jsonl` doesn't exist
- [ ] 2.2.3 Apply default `backend: "tmux"` when reading entries without backend field

### 2.3 Configuration Migration
- [ ] 2.3.1 Update config key to `terminal_logging.debug_enabled`
- [ ] 2.3.2 Implement fallback: use `tmux_logging.debug_enabled` if new key not present

### 2.4 API Endpoint Updates
- [ ] 2.4.1 Rename `/api/logs/tmux` to `/api/logs/terminal`
- [ ] 2.4.2 Rename `/api/logs/tmux/stats` to `/api/logs/terminal/stats`
- [ ] 2.4.3 Rename `/api/logs/tmux/debug` to `/api/logs/terminal/debug`
- [ ] 2.4.4 Add `backend` query parameter filter to `/api/logs/terminal`
- [ ] 2.4.5 Add DELETE endpoint `/api/logs/terminal` to clear all logs

### 2.5 Backend Integration
- [ ] 2.5.1 Update `lib/backends/tmux.py` to pass `backend="tmux"` to log calls
- [ ] 2.5.2 Update `lib/backends/wezterm.py` to pass `backend="wezterm"` to log calls
- [ ] 2.5.3 Update all import statements in monitor.py and other files

### 2.6 UI Updates
- [ ] 2.6.1 Update tab label from "tmux" to "terminal" in templates/logging.html
- [ ] 2.6.2 Add backend indicator to collapsed log entry view
- [ ] 2.6.3 Add backend indicator to expanded log entry view
- [ ] 2.6.4 Add backend filter buttons (All / tmux / wezterm) in toolbar
- [ ] 2.6.5 Implement filter state persistence during session
- [ ] 2.6.6 Add Clear Logs button with destructive styling
- [ ] 2.6.7 Implement confirmation dialog for Clear Logs
- [ ] 2.6.8 Update CSS for backend indicators (minimal badge styling)

## 3. Testing (Phase 3)

- [ ] 3.1 Rename `test_tmux_logging.py` to `test_terminal_logging.py`
- [ ] 3.2 Update all test imports and references
- [ ] 3.3 Add tests for `backend` field in new log entries
- [ ] 3.4 Add tests for default `backend: "tmux"` on old entries
- [ ] 3.5 Add tests for backend filter query parameter
- [ ] 3.6 Add tests for clear logs endpoint
- [ ] 3.7 Add tests for backward-compatible config reading
- [ ] 3.8 Add tests for backward-compatible log file reading
- [ ] 3.9 Run full test suite to ensure no regressions

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification: terminal tab displays correctly
- [ ] 4.4 Manual verification: backend indicators visible
- [ ] 4.5 Manual verification: backend filter works
- [ ] 4.6 Manual verification: clear logs with confirmation works
