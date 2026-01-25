## Why

The shared logging infrastructure carries tmux-specific naming throughout (UI tab, API endpoints, config keys, log file, Python module) despite being used by both tmux and WezTerm backends. This creates confusion for users running WezTerm as their primary backend and misrepresents the system's multi-backend nature.

## What Changes

### Naming Changes
- **BREAKING** API endpoints renamed: `/api/logs/tmux/*` → `/api/logs/terminal/*`
- **BREAKING** Configuration key renamed: `tmux_logging.debug_enabled` → `terminal_logging.debug_enabled`
- **BREAKING** Log file renamed: `data/logs/tmux.jsonl` → `data/logs/terminal.jsonl`
- Python module renamed: `lib/tmux_logging.py` → `lib/terminal_logging.py`
- Dataclass renamed: `TmuxLogEntry` → `TerminalLogEntry`
- UI tab label: "tmux" → "terminal"

### New Features
- Backend field added to each log entry ("tmux" or "wezterm")
- Backend filter in UI and API
- Clear Logs button with confirmation dialog

### Backward Compatibility
- Old log file (`tmux.jsonl`) auto-migrated on first read if new file doesn't exist
- Old config key (`tmux_logging.debug_enabled`) used as fallback if new key not present
- Log entries without `backend` field default to "tmux"

## Impact

- **Affected specs:** logging-ui, tmux-session-logging (both archived)
- **Affected code:**
  - `lib/tmux_logging.py` → `lib/terminal_logging.py` (rename + modify)
  - `lib/backends/tmux.py` (add backend identifier to log calls)
  - `lib/backends/wezterm.py` (add backend identifier to log calls)
  - `monitor.py` (update API endpoints, imports)
  - `templates/logging.html` (update tab label)
  - `static/css/logging.css` (backend indicator styling, clear button)
  - `static/js/logging.js` (filter logic, clear logs functionality)
  - `test_tmux_logging.py` → `test_terminal_logging.py` (rename + update tests)
