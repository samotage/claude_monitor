# Plan: Add Project Permalinks and Refactor Reboot API

## Overview

Add a `permalink` field to projects that provides a URL-safe, stable identifier derived from the project name. This permalink will be used in API routes instead of URL-encoded project names (e.g., `claude-monitor` instead of `CLaude%20Monitor`).

Additionally, rename the `/api/project/<name>/reboot` endpoint to `/api/project/<permalink>/brain-refresh` for clearer semantics.

## Current State

- Projects are identified by display `name` (e.g., "CLaude Monitor")
- URLs use URL-encoded names: `/api/project/CLaude%20Monitor/reboot`
- Slugs are computed dynamically via `slugify_name()` but not stored
- Project data files already use slugified names: `data/projects/claude-monitor.yaml`

## Implementation Steps

### 1. Add `permalink` field to project data (lib/projects.py)

**File:** `lib/projects.py`

- Add `generate_permalink(name: str) -> str` function (same as `slugify_name` for now, but semantically separate)
- Modify `register_project()` to add `permalink` field when creating/updating project data
- Add `update_project_permalink()` function to update permalink when project name changes
- Add `load_project_by_permalink(permalink: str)` function for efficient lookup
- Ensure permalink is included in project data returned by API

### 2. Add `/api/project/<permalink>/brain-refresh` endpoint (monitor.py)

**File:** `monitor.py`

- Add new route: `@app.route("/api/project/<permalink>/brain-refresh")`
- Keep old route temporarily for backwards compatibility (deprecation period optional)
- Route handler should:
  1. Look up project by permalink using new lookup function
  2. Call existing `generate_reboot_briefing()` logic
  3. Return same response format

### 3. Update frontend API calls (static/js/api.js)

**File:** `static/js/api.js`

- Rename `fetchRebootBriefingAPI()` to `fetchBrainRefreshAPI()`
- Change URL from `/api/project/${encodeURIComponent(projectName)}/reboot` to `/api/project/${permalink}/brain-refresh`
- Sessions returned by API should include `permalink` field

### 4. Update frontend panel functions (static/js/panels.js)

**File:** `static/js/panels.js`

- Update `openContextPanel()` to receive permalink instead of projectName
- Update `openRebootPanel()` to receive permalink instead of projectName
- Update any onclick handlers that pass project names

### 5. Update session card rendering (static/js/kanban.js)

**File:** `static/js/kanban.js`

- Session cards should pass permalink to panel functions
- Ensure session data from API includes permalink

### 6. Update session scanning (lib/sessions.py)

**File:** `lib/sessions.py`

- Add `permalink` field to session data returned by `scan_sessions()`
- Derive from project name using consistent slugification

### 7. Migrate existing project data files

**One-time migration:**
- Read each project YAML file in `data/projects/`
- Add `permalink` field if missing
- Filename already matches what permalink should be

## API Changes Summary

| Old Route | New Route | Notes |
|-----------|-----------|-------|
| `GET /api/project/<name>/reboot` | `GET /api/project/<permalink>/brain-refresh` | Name encoded → permalink |
| `GET /api/project/<name>/roadmap` | (unchanged for now) | Already uses slug-like names |
| `POST /api/project/<name>/roadmap` | (unchanged for now) | Already uses slug-like names |

## Files to Modify

1. `lib/projects.py` - Add permalink generation and lookup
2. `monitor.py` - Add new API route
3. `static/js/api.js` - Update API call URL
4. `static/js/panels.js` - Update to use permalink
5. `static/js/kanban.js` - Include permalink in card rendering
6. `lib/sessions.py` - Add permalink to session data
7. `data/projects/*.yaml` - Add permalink field (migration)

## Testing Plan

1. Verify existing projects get permalink field added on startup
2. Test `/api/project/claude-monitor/brain-refresh` returns correct data
3. Test clicking Headspace button on session card opens panel
4. Test context panel loads correctly with new API
5. Verify all API endpoints still work

## Rollback Plan

If issues arise:
- Old route still accepts URL-encoded names (Flask auto-decodes)
- Permalink is just slug of name, so lookup still works
- No data loss - permalink is additive field
