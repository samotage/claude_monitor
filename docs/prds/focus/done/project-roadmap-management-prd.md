---
validation:
  status: valid
  validated_at: '2026-01-21T19:15:45+11:00'
---

## Product Requirements Document (PRD) — Project Roadmap Management

**Project:** Claude Monitor
**Scope:** Epic 1 Sprint 2 - Users can define and edit where each project is heading
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD enables users to capture and maintain project direction within Claude Monitor. By adding structured roadmap data to each project's YAML file and providing API endpoints plus dashboard UI for viewing and editing, users can document where each project is heading without leaving the monitor.

Roadmap data serves as the "where you're going" component of the brain reboot briefing (Sprint 5) and provides input for AI prioritisation (Sprint 7). The roadmap structure includes four sections: `next_up` (immediate focus with title, rationale, and definition of done), `upcoming` (near-term items), `later` (backlog), and `not_now` (explicitly deferred items).

Upon completion, users can view and edit project roadmaps via an expandable panel in the dashboard, with changes persisting to the project's YAML data file.

---

## 1. Context & Purpose

### 1.1 Context

Claude Monitor currently displays live session status but provides no visibility into project goals or direction. Sprint 1 established the YAML data foundation with an empty `roadmap: {}` placeholder. This sprint populates that structure and provides user-facing tools to manage it. When context-switching between projects, users lose track of where each project is heading - roadmap data addresses this gap.

### 1.2 Target User

Developers using Claude Monitor to track multiple Claude Code sessions across projects. They need to quickly recall each project's immediate focus and upcoming work without opening external documents or project management tools.

### 1.3 Success Moment

A developer clicks on a project card, expands the roadmap panel, and immediately sees what they were working toward (`next_up`), what's coming after (`upcoming`), and what they've consciously deferred (`not_now`). They update the `next_up` item after completing a milestone, and the change persists when they return the next day.

---

## 2. Scope

### 2.1 In Scope

- Roadmap schema structure in project YAML with four sections: `next_up`, `upcoming`, `later`, `not_now`
- `next_up` structure containing: `title`, `why`, `definition_of_done`
- `upcoming`, `later`, `not_now` as lists of string items
- API endpoint `GET /api/project/<name>/roadmap` to retrieve roadmap data
- API endpoint `POST /api/project/<name>/roadmap` to update roadmap data
- Dashboard UI: Expandable roadmap panel below project cards
- Dashboard UI: Collapsed by default, expand to view roadmap sections
- Dashboard UI: Edit mode for modifying roadmap fields
- Dashboard UI: Save/cancel actions with success/error feedback
- Dashboard UI: Empty state display when roadmap has no content
- Validation of roadmap data structure on save
- Graceful handling of projects with legacy empty `roadmap: {}` data

### 2.2 Out of Scope

- AI-generated roadmap suggestions
- Prioritisation logic (ranking projects by roadmap content)
- Roadmap history or versioning
- Roadmap templates or presets
- Import/export of roadmaps
- Multi-user collaboration on roadmaps
- Roadmap notifications or reminders
- Drag-and-drop reordering of items
- Rich text or markdown in roadmap fields

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Users can view a project's roadmap by expanding the roadmap panel on a project card
2. Users can edit all roadmap fields (`next_up`, `upcoming`, `later`, `not_now`) via the dashboard
3. Roadmap changes persist in the project's YAML file and survive dashboard restarts
4. The `GET /api/project/<name>/roadmap` endpoint returns the current roadmap data as JSON
5. The `POST /api/project/<name>/roadmap` endpoint updates roadmap data and returns success confirmation
6. API returns appropriate HTTP error codes for invalid project names (404) or malformed data (400)
7. Empty roadmaps display helpful placeholder text indicating no roadmap has been set

### 3.2 Non-Functional Success Criteria

1. Roadmap panel expand/collapse responds within 100ms (no perceptible delay)
2. API save operation completes within 500ms under normal conditions
3. UI provides clear visual feedback during save operations (loading state)

---

## 4. Functional Requirements (FRs)

### Schema

**FR1:** The project YAML roadmap section shall support the following structure:

```yaml
roadmap:
  next_up:
    title: "string"
    why: "string"
    definition_of_done: "string"
  upcoming:
    - "item 1"
    - "item 2"
  later:
    - "item 1"
  not_now:
    - "item 1"
```

**FR2:** All roadmap fields shall be optional - partial roadmaps are valid.

**FR3:** The system shall treat an empty `roadmap: {}` as equivalent to a roadmap with all fields empty.

### API

**FR4:** The system shall provide a `GET /api/project/<name>/roadmap` endpoint that returns the project's roadmap data as JSON.

**FR5:** The GET endpoint shall return HTTP 404 with an error message if the project name does not exist.

**FR6:** The system shall provide a `POST /api/project/<name>/roadmap` endpoint that updates the project's roadmap data from a JSON request body.

**FR7:** The POST endpoint shall validate the request body structure and return HTTP 400 for malformed data.

**FR8:** The POST endpoint shall return HTTP 404 if the project name does not exist.

**FR9:** The POST endpoint shall return HTTP 200 with the updated roadmap data on success.

**FR10:** The POST endpoint shall update only the `roadmap` section of the project YAML, preserving all other data.

### Dashboard UI - Display

**FR11:** Each project card in the dashboard shall include a roadmap panel that is collapsed by default.

**FR12:** Users shall be able to expand the roadmap panel by clicking an expand control on the project card.

**FR13:** The expanded roadmap panel shall display all four roadmap sections: `next_up`, `upcoming`, `later`, `not_now`.

**FR14:** The `next_up` section shall display its three fields: title, why, and definition of done.

**FR15:** The `upcoming`, `later`, and `not_now` sections shall display their items as lists.

**FR16:** When a roadmap section is empty, the panel shall display placeholder text (e.g., "No items defined").

**FR17:** When the entire roadmap is empty, the panel shall display a message indicating the roadmap has not been set up.

### Dashboard UI - Edit

**FR18:** The roadmap panel shall include an "Edit" button to enter edit mode.

**FR19:** In edit mode, all roadmap fields shall become editable form inputs.

**FR20:** The `next_up` fields (title, why, definition_of_done) shall be editable as text inputs or textareas.

**FR21:** The list fields (`upcoming`, `later`, `not_now`) shall be editable as multi-line text inputs (one item per line).

**FR22:** Edit mode shall include "Save" and "Cancel" buttons.

**FR23:** Clicking "Save" shall POST the updated roadmap to the API and exit edit mode on success.

**FR24:** Clicking "Cancel" shall discard changes and exit edit mode without saving.

**FR25:** The UI shall display a loading indicator while the save operation is in progress.

**FR26:** The UI shall display a success message when save completes successfully.

**FR27:** The UI shall display an error message if save fails, keeping the user in edit mode to retry or cancel.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** API endpoints shall follow existing codebase patterns (Flask routes, jsonify responses).

**NFR2:** UI components shall follow existing dashboard patterns (inline HTML/CSS/JS in monitor.py).

**NFR3:** The roadmap panel shall be responsive and usable on screen widths from 800px to 1920px.

---

## 6. UI Overview

### Project Card with Roadmap Panel

```
+------------------------------------------+
| Project Name                    [Status] |
| /path/to/project                         |
|------------------------------------------|
| [v] Roadmap                     [Edit]   |
|------------------------------------------|
| NEXT UP                                  |
| Title: Implement user authentication     |
| Why: Required for beta launch            |
| Done when: Users can log in via OAuth    |
|                                          |
| UPCOMING                                 |
| - Add password reset flow                |
| - Implement session timeout              |
|                                          |
| LATER                                    |
| - Multi-factor authentication            |
|                                          |
| NOT NOW                                  |
| - Social login integration               |
+------------------------------------------+
```

### Edit Mode

```
+------------------------------------------+
| [v] Roadmap                              |
|------------------------------------------|
| NEXT UP                                  |
| Title: [____________________________]    |
| Why:   [____________________________]    |
| Done:  [____________________________]    |
|                                          |
| UPCOMING (one per line)                  |
| [____________________________]           |
| [____________________________]           |
|                                          |
| LATER (one per line)                     |
| [____________________________]           |
|                                          |
| NOT NOW (one per line)                   |
| [____________________________]           |
|                                          |
|              [Cancel]  [Save]            |
+------------------------------------------+
```

### Empty State

```
+------------------------------------------+
| [>] Roadmap                     [Edit]   |
|------------------------------------------|
| No roadmap defined yet.                  |
| Click Edit to set project direction.     |
+------------------------------------------+
```

---

## 7. Dependencies

- **Depends on:** Sprint 1 (YAML Data Foundation) - provides `load_project_data()`, `save_project_data()`, project YAML structure
- **Enables:** Sprint 5 (Brain Reboot View) - roadmap provides "where you're going" context
- **Enables:** Sprint 7 (AI Prioritisation) - roadmap data informs priority ranking
