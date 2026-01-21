# Proposal: Brain Reboot View

## Why

Developers lose mental context when switching between multiple Claude Code projects. Returning to a project after hours or days requires re-reading code and scrolling through logs to remember "where was I?" This context-switching tax consumes 15-25 minutes per project. This feature enables users to quickly reload mental context via a one-click briefing.

## What Changes

- **New API endpoint**: `GET /api/project/<name>/reboot` returning structured briefing with sections for roadmap, state, recent sessions, and history
- **Stale detection**: Calculate project staleness based on time since last session activity; configurable threshold (default: 4 hours)
- **Dashboard UI changes**:
  - Stale project cards show faded/dimmed appearance with clock icon and "Stale - X hours" label
  - New "Reboot" button on each project card
  - New side panel UI for displaying the structured briefing alongside the dashboard
- **Empty state handling**: Graceful degradation with helpful prompts when data sections are missing
- **Configuration**: New `stale_threshold_hours` setting in config.yaml

## Impact

### Affected Files

- `monitor.py` - Main application file (all changes in this single-file Flask app):
  - New `generate_reboot_briefing()` function to aggregate data
  - New `calculate_staleness()` helper function
  - New `/api/project/<name>/reboot` GET endpoint
  - HTML_TEMPLATE updates:
    - New side panel CSS styles
    - New stale card CSS styles
    - New JavaScript for side panel management
    - Modified card rendering to include Reboot button and stale indicators
  - Configuration loading updates for stale_threshold_hours

- `config.yaml` - Configuration file:
  - New `stale_threshold_hours` setting

### Dependencies

This sprint depends on data from previous sprints:
- Sprint 2 (Roadmap): `project_data.roadmap` with `next_up` and `upcoming` fields
- Sprint 3 (Session Summarisation): `project_data.state` and `project_data.recent_sessions`
- Sprint 4 (History Compression): `project_data.history` with `narrative` and `period`

### Patterns Followed

- Single-file architecture: All code in `monitor.py` including embedded HTML/CSS/JS
- API pattern: Returns `{ "success": true, "data": {...} }` for success, `{ "success": false, "error": "..." }` for errors
- Project data loading via `load_project_data(name)` function
- CSS follows existing terminal-inspired design with CSS variables
- JavaScript follows existing vanilla JS patterns with no external dependencies
