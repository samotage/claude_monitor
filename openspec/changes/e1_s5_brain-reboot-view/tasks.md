# Tasks: Brain Reboot View

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Backend - Staleness Detection

- [ ] 2.1 Add `stale_threshold_hours` config loading (default: 4)
- [ ] 2.2 Create `calculate_staleness(project_name)` function
  - Returns `{ is_stale: bool, last_activity: datetime, staleness_hours: float }`
  - Uses `project_data.state.last_session_ended` or recent_sessions timestamps

### Backend - Reboot API Endpoint

- [ ] 2.3 Create `generate_reboot_briefing(project_name)` function
  - Aggregates roadmap, state, recent, history sections
  - Handles missing data gracefully (returns null for empty sections)
- [ ] 2.4 Add `GET /api/project/<name>/reboot` endpoint
  - Returns 404 if project not found
  - Returns 200 with partial data if some sections empty
  - Response format: `{ briefing: {...}, meta: { is_stale, last_activity, staleness_hours } }`

### Frontend - CSS Styles

- [ ] 2.5 Add stale card CSS styles
  - `.card.stale` class with faded/dimmed appearance (opacity: 0.7)
  - Stale icon and label styling
- [ ] 2.6 Add side panel CSS styles
  - Fixed position on right side of screen
  - Close button styling
  - Section headers and content formatting
  - Slide-in animation

### Frontend - Side Panel JavaScript

- [ ] 2.7 Add `openRebootPanel(projectName)` function
  - Fetches `/api/project/<name>/reboot`
  - Populates panel with briefing data
  - Handles empty states with helpful messages
- [ ] 2.8 Add `closeRebootPanel()` function
- [ ] 2.9 Add click-outside-to-close behavior
- [ ] 2.10 Add only-one-panel-at-a-time logic

### Frontend - Card Modifications

- [ ] 2.11 Add Reboot button to project card rendering
  - Emphasized styling on stale cards
- [ ] 2.12 Add stale indicator to card rendering
  - Clock icon + "Stale - X hours" text
  - Apply `.stale` class based on staleness
- [ ] 2.13 Calculate staleness client-side from session data

### Frontend - Side Panel HTML

- [ ] 2.14 Add side panel HTML structure
  - Header with project name and close button
  - Four sections: Roadmap, State, Recent, History
  - Empty state messages for each section

## 3. Testing (Phase 3)

- [ ] 3.1 Test `calculate_staleness()` function
  - Test with fresh project (not stale)
  - Test with stale project (past threshold)
  - Test with missing state data
- [ ] 3.2 Test `generate_reboot_briefing()` function
  - Test with complete data
  - Test with partial data (some sections empty)
  - Test with no data (all sections empty)
- [ ] 3.3 Test `/api/project/<name>/reboot` endpoint
  - Test 200 response with complete data
  - Test 200 response with partial data
  - Test 404 response for unknown project
- [ ] 3.4 Test stale threshold configuration
  - Test default value (4 hours)
  - Test custom value from config.yaml

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
  - Dashboard loads correctly
  - Stale projects show visual indicator
  - Reboot button opens side panel
  - Side panel displays correct data
  - Side panel closes correctly
