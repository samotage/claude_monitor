"""tmux session integration for Claude Headspace.

DEPRECATED: This module now forwards to lib.backends.tmux.
Please import from lib.backends.tmux directly for new code.

This module provides functions for:
- Discovering tmux sessions
- Sending input to sessions (send-keys)
- Capturing output from sessions (capture-pane)
- Creating and managing sessions

tmux enables bidirectional communication with Claude Code sessions,
unlocking features like voice bridge and remote control that aren't
possible with iTerm AppleScript alone.
"""

# Forward all exports from the new location for backwards compatibility
from lib.backends.tmux import (
    _run_tmux,
    capture_pane,
    create_session,
    get_claude_sessions,
    get_debug_logging,
    get_session_info,
    get_session_name_for_project,
    is_tmux_available,
    kill_session,
    list_sessions,
    send_keys,
    session_exists,
    set_debug_logging,
    slugify_project_name,
)

__all__ = [
    "is_tmux_available",
    "list_sessions",
    "session_exists",
    "create_session",
    "kill_session",
    "send_keys",
    "capture_pane",
    "get_session_info",
    "get_claude_sessions",
    "slugify_project_name",
    "get_session_name_for_project",
    "set_debug_logging",
    "get_debug_logging",
]
