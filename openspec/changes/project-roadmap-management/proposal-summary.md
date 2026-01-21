# Proposal Summary: project-roadmap-management

## Architecture Decisions

- **Single-file pattern maintained:** All changes go in `monitor.py` following existing codebase conventions
- **Additive schema extension:** Roadmap structure added to existing project YAML, backward compatible with empty `roadmap: {}`
- **REST API pattern:** Follow existing `/api/*` route conventions with Flask's `jsonify`
- **Inline UI pattern:** HTML/CSS/JS embedded in monitor.py template string

## Implementation Approach

1. **Schema first:** Define roadmap structure validation (no migration needed - existing empty `{}` is valid)
2. **API layer:** Add GET and POST endpoints for `/api/project/<name>/roadmap`
3. **UI display:** Add collapsible roadmap panel to project cards (collapsed by default)
4. **UI edit:** Implement edit mode with form inputs, save/cancel buttons, and feedback states

## Files to Modify

- **monitor.py** (primary):
  - Add `validate_roadmap_data()` helper function (~line 210)
  - Add `GET /api/project/<name>/roadmap` endpoint (~line 2420)
  - Add `POST /api/project/<name>/roadmap` endpoint (~line 2430)
  - Extend HTML template with roadmap panel structure
  - Add CSS for roadmap panel styling
  - Add JavaScript for expand/collapse, edit mode, and API calls

- **data/projects/*.yaml** (no changes needed - schema extension is backward compatible)

## Acceptance Criteria

1. Users can expand roadmap panel on any project card
2. Roadmap displays `next_up` (title, why, definition_of_done) and list sections
3. Empty roadmaps show placeholder text
4. Users can enter edit mode, modify fields, and save
5. Save persists to YAML file and survives restarts
6. API returns 404 for invalid project, 400 for malformed data
7. UI shows loading indicator during save, success/error feedback after

## Constraints and Gotchas

- **Single file:** All HTML/CSS/JS is inline in monitor.py - no external files
- **No frameworks:** Vanilla JS only, no React/Vue/etc.
- **Project name matching:** API uses slugified project name from URL, must match YAML filename
- **Data preservation:** POST must merge roadmap into existing project data, not overwrite
- **Empty state handling:** Both `roadmap: {}` and missing roadmap key should render empty state

## Git Change History

### Related Files
- **Main:** monitor.py (all changes here)
- **Tests:** test_project_data.py (may need roadmap tests)
- **Config:** config.yaml (no changes)

### OpenSpec History
- `yaml-data-foundation` - Archived Jan 21, 2026 - Created project data structure with `roadmap: {}` placeholder

### Implementation Patterns
- Flask route pattern: `@app.route("/api/project/<name>/roadmap", methods=["GET", "POST"])`
- Data access: Use `load_project_data()` and `save_project_data()` from Sprint 1
- Response pattern: `return jsonify({"status": "success", "data": roadmap})`

## Q&A History

- No clarifications needed - PRD was comprehensive and clear
- Decisions made during proposal:
  - Chose expandable panel (option b) over modal or inline card edit
  - Sections collapsed by default to reduce visual noise

## Dependencies

- **Python:** No new packages required
- **Frontend:** No external libraries (vanilla JS)
- **Sprint 1:** Uses `load_project_data()`, `save_project_data()`, `get_project_data_path()`

## Testing Strategy

### API Tests
- GET with valid project → 200 + roadmap JSON
- GET with invalid project → 404
- POST with valid data → 200 + updated roadmap
- POST with invalid project → 404
- POST with malformed JSON → 400

### Integration Tests
- Data persists after server restart
- Partial roadmap updates preserve other fields
- Empty roadmap `{}` handled correctly

### Manual Verification
- Expand/collapse panel works
- Edit mode toggle works
- Save commits to file
- Cancel discards changes
- Loading indicator displays during save
- Success/error messages display

## OpenSpec References

- proposal.md: `openspec/changes/project-roadmap-management/proposal.md`
- tasks.md: `openspec/changes/project-roadmap-management/tasks.md`
- spec.md: `openspec/changes/project-roadmap-management/specs/roadmap-management/spec.md`
