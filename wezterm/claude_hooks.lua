-- Claude Headspace WezTerm Hooks
-- Event-driven detection for Claude Code sessions
--
-- Installation:
-- 1. Copy this file to your WezTerm config directory
-- 2. Add this line to your wezterm.lua:
--    local claude_hooks = require("claude_hooks")
--    claude_hooks.setup(config)
--
-- Configuration (optional):
--   claude_hooks.setup(config, {
--     headspace_url = "http://localhost:5050",  -- Claude Headspace server URL
--     poll_interval_ms = 2000,                  -- Polling interval for content changes
--     debug = false,                            -- Enable debug logging
--   })

local wezterm = require("wezterm")
local M = {}

-- Default configuration
local default_config = {
  headspace_url = "http://localhost:5050",
  poll_interval_ms = 2000,
  debug = false,
}

-- Merge user config with defaults
local function merge_config(user_config)
  local config = {}
  for k, v in pairs(default_config) do
    config[k] = v
  end
  if user_config then
    for k, v in pairs(user_config) do
      config[k] = v
    end
  end
  return config
end

-- Debug logging
local function log(config, msg)
  if config.debug then
    wezterm.log_info("[claude_hooks] " .. msg)
  end
end

-- Send event to Claude Headspace server
local function send_event(config, event_type, data)
  -- Note: WezTerm Lua doesn't have built-in HTTP support
  -- We use wezterm.run_child_process to call curl
  local json_data = wezterm.json_encode({
    event_type = event_type,
    data = data,
    timestamp = os.time(),
  })

  local success, stdout, stderr = wezterm.run_child_process({
    "curl",
    "-s",
    "-X", "POST",
    "-H", "Content-Type: application/json",
    "-d", json_data,
    config.headspace_url .. "/api/events/hook",
    "--connect-timeout", "1",
  })

  if not success then
    log(config, "Failed to send event: " .. (stderr or "unknown error"))
  end

  return success
end

-- Check if a pane is a Claude session
local function is_claude_session(pane)
  local title = pane:get_title()
  local tab_title = pane:tab():get_title()

  -- Check both pane title and tab title
  return title:match("^claude%-") or
         tab_title:match("^claude%-") or
         title:match("Claude Code") or
         title:match("claude ")
end

-- Get Claude session identifier from pane
local function get_session_id(pane)
  local title = pane:get_title()
  local tab_title = pane:tab():get_title()

  -- Prefer tab title if it looks like a Claude session
  if tab_title:match("^claude%-") then
    return tab_title
  end

  -- Fall back to pane title
  if title:match("^claude%-") then
    return title
  end

  -- Use pane ID as fallback
  return "pane-" .. tostring(pane:pane_id())
end

-- Detect activity state from pane content
local function detect_state(pane)
  -- Get the last 50 lines of content
  local dims = pane:get_dimensions()
  local text = pane:get_lines_as_text(dims.scrollback_rows - 50, dims.scrollback_rows)

  if not text then
    return "unknown"
  end

  -- Check for common Claude Code patterns
  -- Input needed patterns (awaiting_input)
  if text:match("Do you want to proceed%?") or
     text:match("Press Enter to continue") or
     text:match("Would you like") or
     text:match("%[y/n%]") or
     text:match("Enter to confirm") then
    return "awaiting_input"
  end

  -- Processing patterns
  if text:match("Thinking%.%.%.") or
     text:match("Working%.%.%.") or
     text:match("Processing") or
     text:match("[%u][%l]+ing%.%.%.") then  -- Matches "Reading...", "Writing...", etc.
    return "processing"
  end

  -- Idle patterns (at prompt)
  if text:match("%$%s*$") or text:match(">%s*$") then
    return "idle"
  end

  return "unknown"
end

-- Track pane states for change detection
local pane_states = {}

-- Poll pane for state changes
local function poll_pane(config, pane)
  if not is_claude_session(pane) then
    return
  end

  local pane_id = pane:pane_id()
  local session_id = get_session_id(pane)
  local current_state = detect_state(pane)
  local previous_state = pane_states[pane_id]

  -- Only send event if state changed
  if current_state ~= previous_state and current_state ~= "unknown" then
    log(config, "State change for " .. session_id .. ": " .. (previous_state or "nil") .. " -> " .. current_state)

    send_event(config, "state_changed", {
      pane_id = pane_id,
      session_id = session_id,
      previous_state = previous_state,
      current_state = current_state,
    })

    pane_states[pane_id] = current_state
  end
end

-- Setup function to be called from wezterm.lua
function M.setup(wezterm_config, user_config)
  local config = merge_config(user_config)

  -- Hook into update-status event for periodic polling
  wezterm.on("update-status", function(window, pane)
    -- Poll all panes in the current window
    for _, tab in ipairs(window:mux_window():tabs()) do
      for _, p in ipairs(tab:panes()) do
        poll_pane(config, p)
      end
    end
  end)

  -- Hook into pane focus events
  wezterm.on("pane-focus-changed", function(window, pane)
    if is_claude_session(pane) then
      local session_id = get_session_id(pane)
      log(config, "Pane focused: " .. session_id)

      send_event(config, "pane_focused", {
        pane_id = pane:pane_id(),
        session_id = session_id,
      })
    end
  end)

  -- Hook into user variable changes (Claude Code may set these)
  wezterm.on("user-var-changed", function(window, pane, name, value)
    if is_claude_session(pane) then
      local session_id = get_session_id(pane)
      log(config, "User var changed: " .. name .. " = " .. value)

      -- Claude Code might set variables like "claude_state" or "claude_task"
      if name:match("^claude_") then
        send_event(config, "user_var_changed", {
          pane_id = pane:pane_id(),
          session_id = session_id,
          var_name = name,
          var_value = value,
        })
      end
    end
  end)

  -- Hook into bell events (Claude Code might ring bell on completion)
  wezterm.on("bell", function(window, pane)
    if is_claude_session(pane) then
      local session_id = get_session_id(pane)
      log(config, "Bell in Claude session: " .. session_id)

      send_event(config, "bell", {
        pane_id = pane:pane_id(),
        session_id = session_id,
      })
    end
  end)

  log(config, "Claude Headspace hooks initialized")

  return wezterm_config
end

-- Key bindings for manual event triggers
function M.key_bindings(config)
  local bindings = {
    -- Ctrl+Shift+H: Send "user_input" event (for testing)
    {
      key = "H",
      mods = "CTRL|SHIFT",
      action = wezterm.action_callback(function(window, pane)
        if is_claude_session(pane) then
          send_event(config, "user_input", {
            pane_id = pane:pane_id(),
            session_id = get_session_id(pane),
            source = "keybinding",
          })
        end
      end),
    },
  }

  return bindings
end

return M
