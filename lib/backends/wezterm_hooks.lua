-- Claude Monitor: WezTerm Enter-key notification hook
--
-- Notifies the Claude Headspace server when Enter is pressed in a Claude
-- session pane, enabling immediate turn-start detection instead of waiting
-- for the next poll cycle.
--
-- Usage: Add to your ~/.wezterm.lua:
--
--   local claude_hooks = dofile('/path/to/lib/backends/wezterm_hooks.lua')
--   claude_hooks.apply(config)
--
-- Place these lines BEFORE 'return config' in your WezTerm config.
--
-- Shift+Enter (newline) is explicitly passed through so Claude Code
-- can distinguish it from plain Enter (submit).
-- Ctrl+Enter and Alt+Enter are unaffected.
-- Only plain Enter triggers the notification, and only in panes whose
-- tab title starts with "claude-" (i.e. Claude Monitor sessions).

local wezterm = require 'wezterm'

local M = {}

--- Apply the Enter-key hook to a WezTerm config table.
-- Appends key bindings for Enter that:
-- 1. Plain Enter: checks if the pane is a claude- session, fires async
--    HTTP POST to the monitor server, then sends Enter through
-- 2. Shift+Enter: explicitly passes through with SHIFT modifier so
--    Claude Code receives it as a distinct key (newline, not submit)
--
-- @param config  The wezterm config_builder table
-- @param opts    Optional table: { port = 5050 }
function M.apply(config, opts)
  opts = opts or {}
  local port = opts.port or 5050
  local url = 'http://localhost:' .. port .. '/api/wezterm/enter-pressed'

  if not config.keys then
    config.keys = {}
  end

  -- Plain Enter (no modifiers): intercept for notification, then pass through
  table.insert(config.keys, {
    key = 'Enter',
    mods = 'NONE',
    action = wezterm.action_callback(function(window, pane)
      -- Check the tab title (not pane title) because Claude Code
      -- overwrites the pane title to "✳ Claude Code".
      -- Tab titles are set by claude-monitor and persist.
      local tab = pane:tab()
      local tab_title = tab and tab:get_title() or ''
      if tab_title:sub(1, 7) == 'claude-' then
        local pane_id = tostring(pane:pane_id())
        wezterm.background_child_process {
          'curl', '-s', '-X', 'POST',
          '-H', 'Content-Type: application/json',
          '-d', '{"pane_id":' .. pane_id .. '}',
          '--max-time', '1',
          url,
        }
      end
      -- Send the Enter key through to the terminal
      window:perform_action(wezterm.action.SendKey { key = 'Enter' }, pane)
    end),
  })

  -- Shift+Enter: send the raw kitty keyboard protocol sequence directly.
  -- SendKey { key='Enter', mods='SHIFT' } doesn't reliably encode the
  -- SHIFT modifier through WezTerm's key pipeline, so we bypass it
  -- entirely with the exact CSI u bytes Claude Code expects:
  --   ESC [ 13 ; 2 u  (keycode=13=Enter, modifier=2=Shift)
  table.insert(config.keys, {
    key = 'Enter',
    mods = 'SHIFT',
    action = wezterm.action.SendString('\x1b[13;2u'),
  })
end

return M
