# Proposal Summary: e1_s8_headspace-aware-dashboard

## Architecture Decisions
- Single-file Flask application pattern - all HTML/CSS/JS inline in monitor.py
- Vanilla JavaScript only - no external libraries
- Side panel for context (slide-out from right) rather than modal
- LocalStorage for toggle persistence
- Polling-based priority updates with soft transition support

## Implementation Approach
- Extend existing HTML template with new panels and components
- Add CSS styles following existing dark theme with cyan accents
- JavaScript fetches /api/priorities and updates UI components
- Context panel fetches project-specific data on demand
- Notifications enhanced with priority info when available

## Files to Modify
- `monitor.py`:
  - HTML template: Add Recommended Next panel, priority badges, sort toggle, context panel
  - CSS: Styles for all new components (badges, panels, toggle, indicator)
  - JavaScript: Priority fetching, sorting logic, panel management, localStorage

## Acceptance Criteria
- User can identify recommended session within 2 seconds
- Recommended Next panel shows name, score, rationale, activity state
- All session cards have color-coded priority badges
- Sort toggle switches between priority-sorted and default views
- Context panel shows roadmap, state, history, priority info
- High-priority notifications include priority indicator
- Dashboard degrades gracefully when API unavailable

## Constraints and Gotchas
- All code must be inline in monitor.py (no external files)
- Must match existing visual design (dark theme, cyan accents, monospace)
- No external JS/CSS dependencies
- Priority data must be fetched asynchronously (non-blocking)
- Context panel must not cause layout shift
- Must handle all error states silently

## Git Change History

### Related Files
- Config: `data/headspace.yaml`

### OpenSpec History
- `e1_s6_headspace` - Archived 2026-01-21 (headspace capability)
- `e1_s7_ai-prioritisation` - Archived 2026-01-21 (priorities API)

### Implementation Patterns
- Single-file architecture: all HTML/CSS/JS in monitor.py template
- Config via data/ YAML files
- API endpoints return JSON
- Notifications via terminal-notifier

## Q&A History
- No clarifications needed - PRD was comprehensive

## Dependencies
- Sprint 7: `/api/priorities` endpoint (already implemented)
- Sprint 6: Headspace panel placement (already implemented)
- Sprint 5: Reboot data for context panel (already implemented)
- Sprints 1-4: Project data structure (already implemented)

## Testing Strategy
- Test Recommended Next panel displays correctly
- Test priority badges render with correct color coding
- Test sort toggle switches views correctly
- Test context panel opens/closes properly
- Test notifications include priority info
- Test graceful degradation when API unavailable
- Test soft transition indicator appears/disappears

## OpenSpec References
- proposal.md: openspec/changes/e1_s8_headspace-aware-dashboard/proposal.md
- tasks.md: openspec/changes/e1_s8_headspace-aware-dashboard/tasks.md
- spec.md: openspec/changes/e1_s8_headspace-aware-dashboard/specs/dashboard-ui/spec.md
