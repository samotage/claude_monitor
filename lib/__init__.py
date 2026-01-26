"""Claude Headspace library modules.

DEPRECATED: This package is deprecated in favor of the new src/ architecture.
All new development should use src/services/, src/models/, and src/backends/.

Migration guide:
- lib/sessions.py -> src/services/agent_store.py, src/services/state_interpreter.py
- lib/headspace.py -> src/models/headspace.py, src/services/priority_service.py
- lib/notifications.py -> src/services/notification_service.py
- lib/compression.py -> src/services/inference_service.py
- lib/backends/ -> src/backends/
- lib/sse.py -> src/services/event_bus.py
- config.py -> src/services/config_service.py

To use the new architecture, run:
    python -m src.app

Or import the app factory:
    from src.app import create_app
    app = create_app()

Legacy modules in this package:
- iterm: iTerm AppleScript integration and window focus
- sessions: Session scanning and activity state parsing
- headspace: Headspace management and priorities cache
- notifications: macOS notifications and state change detection
- projects: Project data, roadmap, and CLAUDE.md parsing
- summarization: JSONL log parsing and session summarization
- compression: History compression with OpenRouter API
- session_sync: Background session state synchronization
- help: Help documentation loading and search
"""

import warnings

warnings.warn(
    "The lib/ package is deprecated. Use src/ instead. " "See lib/__init__.py for migration guide.",
    DeprecationWarning,
    stacklevel=2,
)
