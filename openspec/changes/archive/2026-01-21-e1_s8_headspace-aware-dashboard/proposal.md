## Why

Claude Monitor has an AI prioritisation backend (Sprint 7) that ranks sessions based on headspace, roadmaps, and activity states. However, this intelligence is hidden behind an API endpoint with no user-facing interface.

## What Changes

### Dashboard UI Enhancements
- Add "Recommended Next" panel at top highlighting the #1 priority session with rationale
- Add priority badges (0-100 score) on all session cards with color-coded styling
- Add sort-by-priority toggle to switch between priority-sorted and default-grouped views
- Add expandable context panel showing project roadmap, state, and recent sessions
- Enhance notifications with priority level and headspace relevance

### Graceful Degradation
- Dashboard functions normally when prioritisation is disabled or API unavailable
- Silent error handling (logged but not shown to users)
- Auto-recovery when API becomes available

### JavaScript Additions (Inline)
- Priority data fetching and polling
- Context panel open/close logic
- Sort toggle with localStorage persistence
- Soft transition indicator management

## Impact

- Affected specs: `dashboard-ui` (new capability)
- Affected code:
  - `monitor.py` - HTML template with new panels, CSS styles, JavaScript logic
  - `test_project_data.py` - Tests for any new Python functions

## Definition of Done

- [ ] Recommended Next panel displays top-priority session with name, score, rationale, and activity state
- [ ] Clicking Recommended Next panel focuses the iTerm window
- [ ] All session cards display priority badges with color coding (high/medium/low)
- [ ] Sort-by-priority toggle switches between priority-sorted and default-grouped views
- [ ] Toggle state persists across page refreshes (localStorage)
- [ ] Context panel opens when clicking a session card
- [ ] Context panel shows roadmap, state, recent sessions, priority rationale
- [ ] Context panel has close button and focus iTerm button
- [ ] High-priority notifications (score ≥70) include priority indicator and headspace relevance
- [ ] Soft transition indicator appears when priorities are pending update
- [ ] Dashboard gracefully degrades when API unavailable (hides priority features)
- [ ] All new UI matches existing dark theme with cyan accents
- [ ] No external JS/CSS dependencies added
- [ ] All tests passing
