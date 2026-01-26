# Archived Specifications

This folder contains specifications that have been superseded or are no longer applicable to the current architecture.

## Archived Specs

### session-summarisation (archived 2026-01-26)
**Reason:** Superseded by git-based progress narratives in the major refactor.

The original spec described JSONL log parsing, session-end detection, and YAML-based session history storage. The refactored architecture replaces this with:
- `GitAnalyzer` service that extracts progress from commit history
- On-demand narrative generation instead of session-end triggered summarization
- `recently_completed` field in Roadmap model populated from git commits

See `src/services/git_analyzer.py` for the current implementation.

### history-compression (archived 2026-01-26)
**Reason:** Superseded by git-based progress narratives in the major refactor.

The original spec described background compression queues with OpenRouter integration for AI-powered session compression. The refactored architecture replaces this with:
- On-demand git-based narrative generation
- No background compression threads or queues
- LLM calls only when brain-reboot is requested

See `src/routes/projects.py` (brain-reboot endpoint) for the current approach.

### project-data (archived 2026-01-26)
**Reason:** Architecture changed to centralized state storage.

The original spec described per-project YAML files in `data/projects/` with individual load/save functions. The refactored architecture uses:
- Centralized `data/state.yaml` containing all agents, tasks, projects, and headspace
- `AgentStore` service as single source of truth
- Pydantic models for validation (`src/models/project.py`)

See `src/services/agent_store.py` for the current implementation.

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
