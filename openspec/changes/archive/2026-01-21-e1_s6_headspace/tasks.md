# Tasks: e1_s6_headspace

## Phase 1: Research & Planning
- [x] Review PRD requirements
- [x] Analyze existing patterns in monitor.py
- [x] Create OpenSpec proposal

## Phase 2: Implementation

### Data Layer
- [x] Create `load_headspace()` function to read from `data/headspace.yaml`
- [x] Create `save_headspace()` function to write headspace data
- [x] Create `append_headspace_history()` function for optional history tracking
- [x] Create `get_headspace_history()` function to retrieve history
- [x] Add headspace configuration helpers (feature enabled, history enabled)

### API Endpoints
- [x] Implement `GET /api/headspace` endpoint returning current headspace
- [x] Implement `POST /api/headspace` endpoint to update headspace
- [x] Implement `GET /api/headspace/history` endpoint for history retrieval
- [x] Add proper error handling and validation for all endpoints

### Frontend CSS
- [x] Add headspace panel container styles (full-width, top of dashboard)
- [x] Add view mode styles (focus text prominent, constraints muted, timestamp subtle)
- [x] Add edit mode styles (input fields, buttons matching settings panel)
- [x] Add empty state styles (helpful prompt, encouraging CTA)

### Frontend JavaScript
- [x] Create `loadHeadspace()` function to fetch and display current headspace
- [x] Create `saveHeadspace()` function to POST updates
- [x] Create `enterHeadspaceEditMode()` function to switch to edit UI
- [x] Create `exitHeadspaceEditMode()` function (save or cancel)
- [x] Create `formatHeadspaceTimestamp()` function for human-friendly "X ago" display
- [x] Wire up event handlers for edit button, save, cancel

### Frontend HTML
- [x] Add headspace panel structure at top of dashboard (above session columns)
- [x] Add view mode template (focus, constraints, timestamp, edit button)
- [x] Add edit mode template (input fields, save/cancel buttons)
- [x] Add empty state template (prompt text, set button)

## Phase 3: Testing
- [x] Write unit tests for `load_headspace()` and `save_headspace()`
- [x] Write unit tests for `GET /api/headspace` endpoint
- [x] Write unit tests for `POST /api/headspace` endpoint
- [x] Write unit tests for history functions
- [x] Write integration tests for headspace feature toggle
- [x] Verify all existing tests still pass

## Phase 4: Final Verification
- [x] Verify headspace persists across browser refresh
- [x] Verify headspace persists across server restart
- [x] Verify inline editing completes in under 10 seconds
- [x] Verify no UI flicker during save operations
- [x] Verify empty state displays correctly
- [x] Verify timestamp updates in human-friendly format
