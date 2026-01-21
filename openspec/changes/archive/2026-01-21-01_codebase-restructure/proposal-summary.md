# Proposal Summary: 01_codebase-restructure

## Architecture Decisions

- Extract HTML/CSS/JS template to `templates/index.html` (Flask standard location)
- Create `lib/` package for Python modules with clear responsibilities
- Keep `config.py` at project root (not in lib/) for easier imports
- Use absolute imports from project root to avoid circular dependencies
- Flask routes delegate to module functions - no business logic in routes

## Implementation Approach

- **Sequential extraction**: Extract one module at a time, run tests after each
- **Template first**: Extract HTML_TEMPLATE before Python modules (largest chunk)
- **Dependency-aware ordering**: Create modules in dependency order to avoid import issues
- **Preserve functionality**: No changes to behavior, only code organization

## Files to Modify

### New Files (Create)

| File | Purpose |
|------|---------|
| `templates/index.html` | Dashboard HTML/CSS/JS (~2,500 lines) |
| `config.py` | Configuration management (~150 lines) |
| `lib/__init__.py` | Package marker |
| `lib/notifications.py` | macOS notifications (~150 lines) |
| `lib/iterm.py` | iTerm AppleScript integration (~400 lines) |
| `lib/sessions.py` | Session scanning (~300 lines) |
| `lib/projects.py` | Project data management (~500 lines) |
| `lib/summarization.py` | Log parsing, summaries (~450 lines) |
| `lib/compression.py` | History compression (~450 lines) |
| `lib/headspace.py` | Headspace/priorities (~200 lines) |

### Modified Files

| File | Changes |
|------|---------|
| `monitor.py` | Remove ~6,000 lines, keep Flask app + routes (~800 lines) |
| `test_project_data.py` | Update imports |
| `test_*.py` | Update any imports from monitor.py |

## Acceptance Criteria

- [ ] All 90+ pytest tests pass
- [ ] `monitor.py` under 900 lines
- [ ] Each `lib/` module under 500 lines
- [ ] Dashboard renders identically
- [ ] Notifications work
- [ ] iTerm focus works
- [ ] No circular import errors
- [ ] `restart_server.sh` works unchanged

## Constraints and Gotchas

1. **Circular Imports**: Careful with cross-module imports. Order: config → iterm → sessions → headspace → notifications → projects → summarization → compression
2. **Global State**: Some modules have module-level state (e.g., `_previous_states`, `_notifications_enabled`, `_priorities_cache`). Move these carefully.
3. **Template Path**: Must update Flask app initialization to use `template_folder='templates'`
4. **Test Imports**: Tests currently import from `monitor`. Need to update to import from specific modules.
5. **AppleScript Functions**: Keep all iTerm/AppleScript code together in `lib/iterm.py`

## Git Change History

### Related Files

- **Main Application**: `monitor.py` (6,892 lines - to be restructured)
- **Tests**: `test_project_data.py`, `test_compression.py`, etc.
- **Scripts**: `restart_server.sh` (unchanged)

### OpenSpec History

- Previous changes: YAML Data Foundation (S1), Project Roadmap (S2), Session Summarisation (S3), History Compression (S4), Brain Reboot View (S5), Headspace (S6), AI Prioritisation (S7), Headspace-Aware Dashboard (S8)
- All previous sprints added code to monitor.py, contributing to 6,892 lines

### Implementation Patterns

- Flask app with embedded HTML template (current)
- YAML-based configuration (`config.yaml`)
- AppleScript subprocess calls for macOS integration
- Background threads for async operations (compression)
- Module-level caches for state management

## Q&A History

- No clarifications needed - PRD is comprehensive

## Dependencies

- No new dependencies needed
- Existing: Flask, PyYAML, terminal-notifier, openrouter API

## Testing Strategy

- Run `pytest` after each module extraction
- Verify all 90+ tests pass
- Manual verification of:
  - Dashboard rendering
  - Click-to-focus functionality
  - Notifications
  - Priority badges and Recommended Next panel

## OpenSpec References

- proposal.md: openspec/changes/01_codebase-restructure/proposal.md
- tasks.md: openspec/changes/01_codebase-restructure/tasks.md
- spec.md: openspec/changes/01_codebase-restructure/specs/codebase-restructure/spec.md
