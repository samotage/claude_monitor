# Proposal Summary: e1_s6_headspace

## Architecture Decisions
- Headspace is global (not per-project), stored in `data/headspace.yaml`
- Single YAML file for both current headspace and optional history
- Feature toggle via config.yaml for enabling/disabling entire feature
- Separate toggle for history tracking (disabled by default)
- Follow existing patterns from Brain Reboot and settings panel

## Implementation Approach
- Add backend functions for YAML load/save in monitor.py
- Add three API endpoints: GET/POST headspace, GET history
- Add CSS following existing dark theme with cyan accents
- Add vanilla JS for fetch() API calls and DOM manipulation
- Add inline editing following settings panel pattern

## Files to Modify
- **monitor.py** - Backend functions, API endpoints, CSS, JavaScript, HTML template
- **data/headspace.yaml** - New file for headspace persistence (created on first save)

## Acceptance Criteria
- User can view headspace at top of dashboard without scrolling
- User can edit headspace inline and save in under 10 seconds
- Headspace persists after browser refresh and server restart
- Empty state shows helpful prompt encouraging user to set focus
- "Last updated" timestamp shows in human-friendly format (e.g., "2 hours ago")
- Panel renders within 100ms of dashboard load
- Saving does not interrupt session polling or cause UI flicker

## Constraints and Gotchas
- Headspace panel must appear ABOVE session columns (CSS flexbox order)
- Must not break existing dashboard layout or session polling
- History is optional and disabled by default
- Empty `current_focus` should be rejected with 400 error
- Use `datetime.utcnow().isoformat() + 'Z'` for timestamps
- Panel width should span full dashboard width

## Git Change History

### Related Files
- monitor.py - Main application (all routes, functions, templates)
- data/ directory - Existing YAML storage for projects

### OpenSpec History
- e1_s5_brain-reboot-view (2026-01-21) - Added side panel pattern, staleness detection
- Project roadmap features - Established YAML data patterns

### Implementation Patterns
- API response format: `{"success": true, "data": {...}}`
- CSS variables: `var(--bg-card)`, `var(--cyan)`, `var(--text-muted)`
- YAML helpers: `yaml.safe_load()` for reading, `yaml.dump()` for writing
- Human-friendly time: Calculate difference from now, format as "X hours ago"

## Q&A History
- No clarifications needed - PRD was sufficiently clear and consistent

## Dependencies
- None - Uses existing Flask and PyYAML dependencies

## Testing Strategy
- Unit tests for `load_headspace()` and `save_headspace()` functions
- Unit tests for GET /api/headspace endpoint (with data, without data)
- Unit tests for POST /api/headspace endpoint (valid data, missing field)
- Unit tests for GET /api/headspace/history endpoint
- Integration tests for feature toggle configuration
- All existing 44 tests must continue to pass

## OpenSpec References
- proposal.md: openspec/changes/e1_s6_headspace/proposal.md
- tasks.md: openspec/changes/e1_s6_headspace/tasks.md
- spec.md: openspec/changes/e1_s6_headspace/specs/headspace/spec.md
