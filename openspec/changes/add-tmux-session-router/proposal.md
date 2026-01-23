# Change: Add tmux Session Router

## Why

The monitor currently has **read-only** access to Claude Code sessions via iTerm AppleScript. This limits functionality to observation and window focus. Adding tmux integration unlocks **write** capability - the ability to send commands and text directly to sessions.

This is foundational infrastructure for:
1. **Voice Bridge** - Send voice-transcribed commands to sessions (see `docs/ideas/VOICE_BRIDGE_PLAN.md`)
2. **Usage Budget Tracking** - Poll `/status` command to get real usage data (see `docs/ideas/usage-budget-tracking.md`)
3. **Session Automation** - Approve prompts, send responses, inject commands

## What Changes

- **NEW** `lib/tmux.py` - tmux session discovery, send-keys, capture-pane operations
- **MODIFIED** `bin/claude-monitor` wrapper - Launch sessions in tmux when enabled for project
- **NEW** API endpoint `/api/send/<session_id>` - Send text to a session
- **NEW** API endpoint `/api/output/<session_id>` - Capture session output
- **NEW** API endpoint `/api/projects/<name>/tmux/enable` - Enable tmux for a project
- **NEW** API endpoint `/api/projects/<name>/tmux/disable` - Disable tmux for a project
- **MODIFIED** `lib/sessions.py` - Hybrid detection (tmux sessions alongside iTerm)
- **MODIFIED** `monitor.py` - Register new endpoints, integrate tmux router
- **MODIFIED** `config.yaml` schema - Add `tmux: true|false` per project
- **MODIFIED** Dashboard UI - tmux status indicators, enable/disable buttons

## Impact

- **New capability**: `tmux-router` - tmux-based session control
- **Affected code**:
  - `lib/tmux.py` (new)
  - `lib/sessions.py` (modified)
  - `bin/claude-monitor` (modified)
  - `monitor.py` (modified)
- **User workflow change**: Sessions should be started via wrapper to run in tmux
- **Backwards compatible**: iTerm-only sessions continue to work (read-only)

## Dependencies

- tmux must be installed (`brew install tmux`)
- No new Python dependencies required (uses subprocess)

## Related Documents

- `docs/ideas/VOICE_BRIDGE_PLAN.md` - Voice bridge architecture (tmux is Phase 1)
- `docs/ideas/usage-budget-tracking.md` - Usage tracking requiring `/status` polling
