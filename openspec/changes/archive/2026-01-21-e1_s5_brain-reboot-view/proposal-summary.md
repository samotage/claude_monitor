# Proposal Summary: e1_s5_brain-reboot-view

## Architecture Decisions

- **Single-file architecture**: All code changes go in `monitor.py`, including embedded HTML/CSS/JS
- **API pattern**: Follow existing `{ success: true, data: {...} }` response format
- **Side panel approach**: Slide-in panel from right side, not modal overlay (maintains dashboard interaction)
- **Client-side staleness**: Calculate staleness in JavaScript from session data to avoid extra API calls

## Implementation Approach

Build the feature in layers:
1. Backend first: staleness calculation and reboot API endpoint
2. CSS styles: stale card appearance and side panel
3. JavaScript: panel management and data fetching
4. Card modifications: integrate button and stale indicators

This order allows incremental testing and ensures backend is solid before UI integration.

## Files to Modify

- **monitor.py** (single-file Flask app)
  - New functions: `calculate_staleness()`, `generate_reboot_briefing()`
  - New endpoint: `GET /api/project/<name>/reboot`
  - HTML_TEMPLATE updates: CSS, JavaScript, card rendering
- **config.yaml** - Add `stale_threshold_hours` setting (optional, default 4)

## Acceptance Criteria

1. Reboot button on every project card
2. Stale projects (4+ hours inactive) show faded appearance with clock icon and label
3. Clicking Reboot opens side panel with structured briefing
4. Panel displays 4 sections: Roadmap, State, Recent, History
5. Missing sections show helpful empty state messages
6. Panel can be closed via button or click outside
7. Only one panel open at a time
8. Panel opens within 500ms

## Constraints and Gotchas

- **Data dependencies**: Relies on data from Sprints 2-4:
  - `project_data.roadmap` (Sprint 2)
  - `project_data.state` and `project_data.recent_sessions` (Sprint 3)
  - `project_data.history` (Sprint 4)
- **Project data location**: Data files are in `data/projects/<slug>.yaml`
- **Staleness source**: Use `state.last_session_ended` or most recent session timestamp
- **Existing card onclick**: Cards already have `onclick="focusWindow(pid)"` - Reboot button needs `event.stopPropagation()`
- **CSS variables**: Use existing `--cyan`, `--text-muted`, etc. from :root
- **No external JS**: Vanilla JavaScript only, no libraries

## Git Change History

### Related Files
- `monitor.py` - Main application with all Flask routes and HTML template

### OpenSpec History
- Sprint 1 (yaml-data-foundation): Established project data YAML structure
- Sprint 2 (project-roadmap-management): Added roadmap data format
- Sprint 3 (session-summarisation): Added state and recent_sessions
- Sprint 4 (history-compression): Added history with narrative

### Implementation Patterns
- API endpoints follow: `@app.route("/api/project/<name>/...")` pattern
- Project data loaded via: `load_project_data(name)` returns full YAML
- CSS uses terminal-inspired design with glow effects
- JavaScript functions follow: `function verbNoun()` naming

## Q&A History

No clarifications needed - PRD was sufficiently detailed.

## Dependencies

- No new packages required
- Uses existing: Flask, PyYAML, datetime, timedelta

## Testing Strategy

### Unit Tests
- `test_calculate_staleness()` - fresh/stale/missing data cases
- `test_generate_reboot_briefing()` - complete/partial/empty data cases
- `test_api_project_reboot()` - 200/404 responses

### Test Scenarios
1. Fresh project (< 4 hours) - not stale
2. Stale project (> 4 hours) - is stale
3. Missing state data - handle gracefully
4. Custom threshold from config
5. All sections populated
6. Some sections empty
7. Project not found

## OpenSpec References

- proposal.md: openspec/changes/e1_s5_brain-reboot-view/proposal.md
- tasks.md: openspec/changes/e1_s5_brain-reboot-view/tasks.md
- spec.md: openspec/changes/e1_s5_brain-reboot-view/specs/brain-reboot/spec.md
