# Proposal: 01_codebase-restructure

## Summary

Restructure the monolithic 6,892-line `monitor.py` into a modular architecture with clear separation of concerns. Extract the embedded HTML/CSS/JS template (~2,500 lines) to `templates/index.html`, create focused Python modules under `lib/`, and reduce `monitor.py` to Flask routes and entry point only.

## Motivation

The current single-file architecture creates maintenance challenges:
- Difficult navigation through 6,800+ lines
- High cognitive load when modifying specific functionality
- No clear module boundaries
- Harder to test components in isolation

## Impact

### Files Created

| File | Purpose | Est. Lines |
|------|---------|------------|
| `templates/index.html` | HTML/CSS/JS dashboard template | ~2,500 |
| `lib/__init__.py` | Package marker | ~5 |
| `lib/notifications.py` | macOS notifications, state change detection | ~150 |
| `lib/iterm.py` | iTerm AppleScript integration, window focus | ~400 |
| `lib/sessions.py` | Session scanning, activity state parsing | ~300 |
| `lib/projects.py` | Project data, roadmap, CLAUDE.md parsing | ~500 |
| `lib/summarization.py` | Log parsing, summary generation | ~450 |
| `lib/compression.py` | History compression, OpenRouter API | ~450 |
| `lib/headspace.py` | Headspace loading, priorities cache | ~200 |
| `config.py` | Configuration loading/saving | ~150 |

### Files Modified

| File | Changes |
|------|---------|
| `monitor.py` | Extract all modules, retain Flask app + routes (~800 lines) |
| `test_project_data.py` | Update imports to new module paths |
| `test_*.py` | Update any imports referencing monitor.py functions |

### Files Unchanged

- `orch/` - Orchestration system unchanged
- `.claude/commands/` - Claude commands unchanged
- `restart_server.sh` - Should work without modification
- `config.yaml` - Configuration file unchanged

## Approach

1. **Template Extraction**: Extract `HTML_TEMPLATE` string to `templates/index.html`, configure Flask template directory
2. **Module Creation**: Create each `lib/` module by extracting related functions from `monitor.py`
3. **Config Module**: Create `config.py` at root level for configuration management
4. **Import Updates**: Update `monitor.py` to import from new modules, update tests
5. **Validation**: Run all tests, verify API endpoints, check dashboard rendering

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Circular imports | Careful dependency ordering, avoid cross-module state sharing |
| Missing imports in tests | Run full test suite after each module extraction |
| Broken AppleScript | Test iTerm focus feature manually |
| Template path issues | Use Flask's standard template_folder configuration |

## Definition of Done

- [ ] `monitor.py` under 900 lines
- [ ] Each `lib/` module under 500 lines
- [ ] All 90+ pytest tests pass
- [ ] Dashboard renders correctly
- [ ] Notifications work
- [ ] iTerm focus works
- [ ] No circular import errors
- [ ] `restart_server.sh` works unchanged
