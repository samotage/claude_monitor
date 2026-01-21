# Proposal: Project Roadmap Management

## Why

Claude Monitor currently displays live session status but provides no visibility into project goals or direction. Users managing multiple Claude Code sessions lose track of where each project is heading when context-switching. This feature enables users to capture and maintain project direction within the monitor, supporting the "brain reboot" capability planned for Sprint 5.

## What Changes

### Schema Extension
- Add structured `roadmap` section to project YAML schema
- Support `next_up` object with `title`, `why`, `definition_of_done` fields
- Support `upcoming`, `later`, `not_now` as lists of string items
- All fields optional - partial roadmaps are valid

### API Endpoints
- Add `GET /api/project/<name>/roadmap` endpoint
- Add `POST /api/project/<name>/roadmap` endpoint
- Return appropriate HTTP error codes (404, 400, 200)
- Preserve non-roadmap data on update

### Dashboard UI
- Add collapsible roadmap panel to project cards (collapsed by default)
- Display all four roadmap sections when expanded
- Implement edit mode with form inputs
- Handle empty state with placeholder messaging
- Provide save/cancel with loading and feedback states

## Impact

- **Affected specs:** Project data schema, API routing, dashboard rendering
- **Affected code:**
  - `monitor.py` - API endpoints, HTML template, JavaScript handlers
  - `data/projects/*.yaml` - Schema extension (backward compatible)
- **Dependencies:** Sprint 1 (YAML Data Foundation) - already complete
- **Enables:** Sprint 5 (Brain Reboot View), Sprint 7 (AI Prioritisation)

## Risk Assessment

- **Low risk:** Additive changes only, no breaking modifications
- **Backward compatible:** Empty `roadmap: {}` treated as valid
- **Isolated:** Changes contained to monitor.py and project YAML files
