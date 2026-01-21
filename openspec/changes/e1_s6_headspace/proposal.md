# Proposal: e1_s6_headspace

## Why

Claude Monitor currently shows session status but has no concept of user intent. Users see what's happening across their projects but lack a way to declare what should be happening. This creates reactive behaviour: users respond to notifications rather than working toward explicit goals.

Sprint 6 adds the user-level context layer: "What am I trying to accomplish right now?" This headspace becomes the lens through which AI Prioritisation (Sprint 7) will rank sessions.

## What Changes

This proposal adds the Headspace feature, enabling users to:
- Declare and persist their current focus goal at the top of the dashboard
- Edit their headspace inline without modal or page navigation
- See a visible reminder of their intent throughout the day
- Track optional history of previous headspace values

## Impact

### Files to Modify

**Backend (monitor.py):**
- Add headspace data model functions (load/save YAML)
- Add `GET /api/headspace` endpoint
- Add `POST /api/headspace` endpoint
- Add `GET /api/headspace/history` endpoint (optional)
- Add configuration helpers for headspace feature toggle

**Data Storage:**
- Create `data/headspace.yaml` for persistent storage

**Frontend (embedded in monitor.py):**
- Add CSS styles for headspace panel (view mode, edit mode, empty state)
- Add JavaScript functions for headspace CRUD operations
- Add headspace panel HTML at top of dashboard
- Add inline editing functionality

### Dependencies

- Sprint 1 (YAML Data Foundation) - Provides data directory structure and YAML utilities

### Existing Patterns to Follow

- YAML file storage pattern from project roadmaps (`data/projects/<name>.yaml`)
- API response format: `{"success": true, "data": {...}}`
- CSS variables: `var(--bg-card)`, `var(--cyan)`, `var(--text-muted)`
- Vanilla JS with fetch() for API calls
- Inline editing pattern from settings panel

## Definition of Done

- [ ] User can view their current headspace at the top of the dashboard without scrolling
- [ ] User can edit their headspace inline and save changes in under 10 seconds
- [ ] Headspace persists after browser refresh
- [ ] Headspace persists after server restart
- [ ] Empty headspace state displays a helpful prompt encouraging the user to set one
- [ ] Headspace shows "last updated" timestamp in human-friendly format
- [ ] Headspace panel renders within 100ms of dashboard load
- [ ] Saving headspace does not interrupt session polling or cause visible UI flicker
- [ ] Headspace data is stored in human-readable YAML format
- [ ] All new functionality has unit test coverage
