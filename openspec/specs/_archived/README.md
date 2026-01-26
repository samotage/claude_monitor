# Archived Specifications

This folder contains specifications that have been superseded or are no longer applicable to the current architecture.

## Archived Specs

### tmux-router (archived 2026-01-26)
**Reason:** Superseded by WezTerm-first backend strategy.

The project has moved to a unified `TerminalBackend` abstraction layer (see `src/backends/`) that supports multiple backends:
- WezTerm (primary/recommended)
- tmux (supported as fallback)

The tmux-router spec was written before this abstraction existed and described tmux-specific implementation details. The functionality described is now implemented generically in:
- `src/backends/base.py` - Abstract TerminalBackend interface
- `src/backends/tmux.py` - tmux implementation
- `src/backends/wezterm.py` - WezTerm implementation

### tmux-session-logging (archived 2026-01-26)
**Reason:** Superseded by terminal-logging-rename spec and unified backend approach.

Terminal logging is now implemented as a backend-agnostic feature. See:
- `openspec/specs/terminal-logging-rename/` for the current spec
- `src/services/log_service.py` for the implementation

### codebase-restructure (archived 2026-01-26)
**Reason:** Completed - describes the first restructure (monolithic → lib/).

This spec documented the first restructuring effort to move from a monolithic `monitor.py` to separate modules in `lib/`. A subsequent major refactor has since restructured the codebase again to `src/` with:
- Pydantic v2 models in `src/models/`
- Service layer in `src/services/`
- Flask blueprints in `src/routes/`
- Backend abstraction in `src/backends/`

The current architecture is documented in `docs/application/conceptual-design.md`.

## Reference

For current architecture documentation, see:
- `docs/application/conceptual-design.md` - Authoritative architecture reference
- `openspec/project.md` - Project overview and spec index
