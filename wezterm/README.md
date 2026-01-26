# WezTerm Lua Hooks for Claude Headspace

Event-driven detection for Claude Code sessions using WezTerm's Lua API.

## Overview

These hooks enable Claude Headspace to receive real-time events from WezTerm instead of relying solely on polling. This provides faster state detection and lower latency notifications.

## Installation

1. Copy `claude_hooks.lua` to your WezTerm config directory:
   ```bash
   cp claude_hooks.lua ~/.config/wezterm/
   ```

2. Add to your `wezterm.lua`:
   ```lua
   local wezterm = require("wezterm")
   local claude_hooks = require("claude_hooks")

   local config = wezterm.config_builder()

   -- Your existing config...

   -- Setup Claude Headspace hooks
   claude_hooks.setup(config)

   return config
   ```

## Configuration

You can customize the hook behavior:

```lua
claude_hooks.setup(config, {
  headspace_url = "http://localhost:5050",  -- Claude Headspace server URL
  poll_interval_ms = 2000,                  -- Polling interval (ms)
  debug = false,                            -- Enable debug logging
})
```

## Events

The hooks detect and send these events to Claude Headspace:

| Event | Trigger | Description |
|-------|---------|-------------|
| `state_changed` | Terminal content | Detected state change (idle/processing/awaiting_input) |
| `pane_focused` | User action | User focused a Claude session pane |
| `user_var_changed` | Claude Code | Claude Code set a user variable |
| `bell` | Terminal | Terminal bell triggered (task complete) |

## How It Works

1. **Polling**: The `update-status` event triggers periodic content checks
2. **Pattern Matching**: Lua regex matches Claude Code patterns in terminal
3. **HTTP POST**: Events are sent to `/api/events/hook` endpoint
4. **State Hints**: Claude Headspace uses hints to accelerate state detection

## Debug Mode

Enable debug mode to see hook activity in WezTerm's debug console:

```lua
claude_hooks.setup(config, { debug = true })
```

View logs: WezTerm Debug Overlay (Ctrl+Shift+L on macOS)

## Requirements

- WezTerm 20230408 or later
- `curl` command available (for HTTP requests)
- Claude Headspace running on configured URL
