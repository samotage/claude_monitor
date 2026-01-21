## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Recommended Next Panel
- [x] 2.1 Add CSS styles for Recommended Next panel (dark theme, cyan accents)
- [x] 2.2 Add HTML structure for Recommended Next panel in template
- [x] 2.3 Add JavaScript to fetch priorities and populate Recommended Next panel
- [x] 2.4 Add click handler to focus iTerm window from panel
- [x] 2.5 Handle empty state (no active sessions)
- [x] 2.6 Handle unavailable state (hide panel when API fails)

### Priority Badges on Cards
- [x] 2.7 Add CSS styles for priority badges (high/medium/low color coding)
- [x] 2.8 Add priority badge HTML structure to session card template
- [x] 2.9 Add JavaScript to update badges when priorities refresh
- [x] 2.10 Handle graceful display when no priority data available

### Sort-by-Priority Toggle
- [x] 2.11 Add CSS styles for toggle control
- [x] 2.12 Add toggle HTML in dashboard header area
- [x] 2.13 Add JavaScript for toggle functionality
- [x] 2.14 Implement priority-sorted view (sessions ordered by score)
- [x] 2.15 Implement localStorage persistence for toggle state
- [x] 2.16 Hide toggle when prioritisation unavailable

### Context Panel
- [x] 2.17 Add CSS styles for side panel (slide-out design)
- [x] 2.18 Add context panel HTML structure
- [x] 2.19 Add JavaScript to open panel on session card click
- [x] 2.20 Fetch and display project roadmap in panel
- [x] 2.21 Fetch and display project state in panel
- [x] 2.22 Display recent session history in panel
- [x] 2.23 Display priority score and rationale in panel
- [x] 2.24 Add close button functionality
- [x] 2.25 Add focus iTerm button in panel
- [x] 2.26 Handle incomplete project data gracefully

### Priority-Aware Notifications
- [x] 2.27 Modify notification logic to include priority score
- [x] 2.28 Add high-priority indicator for scores ≥70
- [x] 2.29 Include headspace relevance in notification message
- [x] 2.30 Ensure notifications work when prioritisation unavailable

### Soft Transition Indicator
- [x] 2.31 Add CSS for soft transition indicator
- [x] 2.32 Add indicator HTML element
- [x] 2.33 Add JavaScript to show/hide based on soft_transition_pending

### Graceful Degradation
- [x] 2.34 Add error handling for /api/priorities failures
- [x] 2.35 Implement silent error logging
- [x] 2.36 Add auto-recovery polling when API becomes available

## 3. Testing (Phase 3)

- [x] 3.1 Test Recommended Next panel displays correctly
- [x] 3.2 Test priority badges render with correct colors
- [x] 3.3 Test sort toggle switches views correctly
- [x] 3.4 Test context panel opens and closes
- [x] 3.5 Test notifications include priority info
- [x] 3.6 Test graceful degradation when API unavailable
- [x] 3.7 Test soft transition indicator appears/disappears

## 4. Final Verification

- [x] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
- [ ] 4.4 Dashboard renders within 500ms
- [ ] 4.5 Context panel opens within 200ms
