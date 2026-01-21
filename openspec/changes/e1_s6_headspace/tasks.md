# Tasks: e1_s6_headspace

## Phase 1: Research & Planning
- [x] Review PRD requirements
- [x] Analyze existing patterns in monitor.py
- [x] Create OpenSpec proposal

## Phase 2: Implementation

### Data Layer
- [ ] Create `load_headspace()` function to read from `data/headspace.yaml`
- [ ] Create `save_headspace()` function to write headspace data
- [ ] Create `append_headspace_history()` function for optional history tracking
- [ ] Create `get_headspace_history()` function to retrieve history
- [ ] Add headspace configuration helpers (feature enabled, history enabled)

### API Endpoints
- [ ] Implement `GET /api/headspace` endpoint returning current headspace
- [ ] Implement `POST /api/headspace` endpoint to update headspace
- [ ] Implement `GET /api/headspace/history` endpoint for history retrieval
- [ ] Add proper error handling and validation for all endpoints

### Frontend CSS
- [ ] Add headspace panel container styles (full-width, top of dashboard)
- [ ] Add view mode styles (focus text prominent, constraints muted, timestamp subtle)
- [ ] Add edit mode styles (input fields, buttons matching settings panel)
- [ ] Add empty state styles (helpful prompt, encouraging CTA)

### Frontend JavaScript
- [ ] Create `loadHeadspace()` function to fetch and display current headspace
- [ ] Create `saveHeadspace()` function to POST updates
- [ ] Create `enterEditMode()` function to switch to edit UI
- [ ] Create `exitEditMode()` function (save or cancel)
- [ ] Create `formatTimestamp()` function for human-friendly "X ago" display
- [ ] Wire up event handlers for edit button, save, cancel

### Frontend HTML
- [ ] Add headspace panel structure at top of dashboard (above session columns)
- [ ] Add view mode template (focus, constraints, timestamp, edit button)
- [ ] Add edit mode template (input fields, save/cancel buttons)
- [ ] Add empty state template (prompt text, set button)

## Phase 3: Testing
- [ ] Write unit tests for `load_headspace()` and `save_headspace()`
- [ ] Write unit tests for `GET /api/headspace` endpoint
- [ ] Write unit tests for `POST /api/headspace` endpoint
- [ ] Write unit tests for history functions
- [ ] Write integration tests for headspace feature toggle
- [ ] Verify all existing tests still pass

## Phase 4: Final Verification
- [ ] Verify headspace persists across browser refresh
- [ ] Verify headspace persists across server restart
- [ ] Verify inline editing completes in under 10 seconds
- [ ] Verify no UI flicker during save operations
- [ ] Verify empty state displays correctly
- [ ] Verify timestamp updates in human-friendly format
