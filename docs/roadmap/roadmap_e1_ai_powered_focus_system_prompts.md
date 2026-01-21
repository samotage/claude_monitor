# Epic 1: AI-Powered Focus System - PRD Workshop Prompts

These prompts are designed to be used sequentially with the `/10: prd-workshop` command to create PRDs for each sprint in the AI-Powered Focus System epic.

**Usage:** Copy each sprint prompt and run `/10: prd-workshop` to start the interactive PRD creation process.

**Roadmap Reference:** `@docs/roadmap/roadmap_e1_ai_powered_focus.md`

---

## Sprint 1: YAML Data Foundation

```
I need to create a PRD for Epic 1 Sprint 1: YAML Data Foundation.

**Context Documents:**
- Roadmap: @docs/roadmap/roadmap_e1_ai_powered_focus.md (see "Sprint 1" section)

**Sprint Goal:**
Establish the persistent data layer for project state storage.

**Deliverables:**
1. `data/` directory structure for storing project YAML files
2. YAML schema definition for project files
3. Python YAML read/write utilities
4. Project registration linking config.yaml projects to data files
5. Initial project YAML seeding from CLAUDE.md (goal, tech stack)

**What This Sprint Does NOT Include:**
- Roadmap, state, sessions, history sections (just scaffolding placeholders)
- Any AI/LLM integration
- Any UI changes

**Dependencies:** None (foundation sprint)

**PRD Output Location:** docs/prds/focus/
```

---

## Sprint 2: Project Roadmap Management

```
I need to create a PRD for Epic 1 Sprint 2: Project Roadmap Management.

**Context Documents:**
- Roadmap: @docs/roadmap/roadmap_e1_ai_powered_focus.md (see "Sprint 2" section)

**Sprint Goal:**
Users can define and edit where each project is heading.

**Deliverables:**
1. Roadmap section added to project YAML schema
2. API endpoints: `GET/POST /api/project/<name>/roadmap`
3. Dashboard UI: View/edit roadmap for a project
4. Roadmap fields: next_up (with title, why, DoD), upcoming, later, not_now

**What This Sprint Does NOT Include:**
- AI-generated roadmap suggestions
- Prioritisation logic

**Dependencies:** Sprint 1 (YAML Data Foundation)

**PRD Output Location:** docs/prds/focus/
```

---

## Sprint 3: Session Summarisation & State Tracking

```
I need to create a PRD for Epic 1 Sprint 3: Session Summarisation & State Tracking.

**Context Documents:**
- Roadmap: @docs/roadmap/roadmap_e1_ai_powered_focus.md (see "Sprint 3" section)

**Sprint Goal:**
Capture what happened in each Claude Code session and maintain current state.

**Deliverables:**
1. Parse Claude Code JSONL logs for session context
2. Session end detection (idle for N minutes or explicit end)
3. State and recent_sessions sections in project YAML
4. Auto-update state summary after each session
5. Store last 5 sessions with detail
6. API endpoint: `POST /api/session/<id>/summarise`

**What This Sprint Does NOT Include:**
- AI summarisation (use simple extraction first)
- History compression
- UI for viewing session history

**Technical Notes:**
- Claude Code logs are stored in JSONL format
- Session detection uses existing PID/TTY matching from monitor.py

**Dependencies:** Sprint 1 (YAML Data Foundation)

**PRD Output Location:** docs/prds/focus/
```

---

## Sprint 4: History Compression

```
I need to create a PRD for Epic 1 Sprint 4: History Compression.

**Context Documents:**
- Roadmap: @docs/roadmap/roadmap_e1_ai_powered_focus.md 

**Sprint Goal:**
Automatically compress old sessions into a summary to keep context manageable.

**Deliverables:**
1. Rolling window logic (triggers when recent_sessions > 5)
2. History section added to project YAML schema
3. OpenRouter integration for AI-powered summarisation
4. Configuration: OpenRouter API key, model selection
5. Compress oldest sessions into history.summary

**What This Sprint Does NOT Include:**
- Live prioritisation
- Brain reboot UI

**Technical Constraints:**
- OpenRouter API integration required
- Need to handle API failures gracefully
- Token-efficient prompt design for summarisation

**Dependencies:** Sprint 3 (Session Summarisation)

**PRD Output Location:** docs/prds/focus/
```

---

## Sprint 5: Brain Reboot View

```
I need to create a PRD for Epic 1 Sprint 5: Brain Reboot View.

**Context Documents:**
- Roadmap: @docs/roadmap/roadmap_e1_ai_powered_focus.md 

**Sprint Goal:**
Users can quickly reload context on a project they haven't touched in a while.

**Deliverables:**
1. API endpoint: `GET /api/project/<name>/reboot`
2. Generate reboot briefing from YAML (roadmap → state → recent → history)
3. Dashboard UI: Reboot button on project cards
4. Stale indicator (project not touched in N hours)
5. Reboot modal/panel with structured briefing

**Success Criteria:**
- Context reload in <30 seconds reading time
- One-click brain reboot for any project

**What This Sprint Does NOT Include:**
- AI-enhanced reboot suggestions
- Session prioritisation

**Dependencies:**
- Sprint 2 (Roadmap Management)
- Sprint 4 (History Compression) - for compressed history in briefing

**PRD Output Location:** docs/prds/focus/
```

---

## Sprint 6: Focus Strategy

```
I need to create a PRD for Epic 1 Sprint 6: Focus Strategy.

**Context Documents:**
- Roadmap: @docs/roadmap/roadmap_e1_ai_powered_focus.md 

**Sprint Goal:**
Users can set and adjust their current focus goal, visible at top of dashboard.

**Deliverables:**
1. Create `data/strategy.yaml` schema
2. API endpoints: `GET/POST /api/strategy`
3. Dashboard UI: Strategy panel at top (view/edit inline)
4. Strategy fields: current_focus, constraints, updated_at
5. Persistence across dashboard restarts
6. Optional: strategy history

**What This Sprint Does NOT Include:**
- AI using strategy for ranking
- Soft transition logic

**Dependencies:** Sprint 1 (YAML Data Foundation)

**PRD Output Location:** docs/prds/focus/
```

---

## Sprint 7: AI Prioritisation

```
I need to create a PRD for Epic 1 Sprint 7: AI Prioritisation.

**Context Documents:**
- Roadmap: @docs/roadmap/roadmap_e1_ai_powered_focus.md 

**Sprint Goal:**
AI ranks sessions based on focus strategy, roadmaps, and activity state.

**Deliverables:**
1. API endpoint: `GET /api/priorities`
2. LLM prompt construction: strategy + all project contexts + activity states
3. OpenRouter API call to rank sessions
4. Ranked list with rationale returned
5. Polling interval config (re-prioritise every N seconds)
6. Soft transition: wait for natural pause before reordering

**What This Sprint Does NOT Include:**
- UI changes (API only)

**Technical Constraints:**
- Reuse OpenRouter integration from Sprint 4
- Prompt must be token-efficient (include all projects)
- Handle stale/offline sessions appropriately

**Dependencies:**
- Sprint 4 (History Compression) - for OpenRouter integration
- Sprint 6 (Focus Strategy) - for strategy input to ranking

**PRD Output Location:** docs/prds/focus/
```

---

## Sprint 8: Focus-Aware Dashboard UI

```
I need to create a PRD for Epic 1 Sprint 8: Focus-Aware Dashboard UI.

**Context Documents:**
- Roadmap: @docs/roadmap/roadmap_e1_ai_powered_focus.md 

**Sprint Goal:**
Surface AI prioritisation in the dashboard.

**Deliverables:**
1. Recommended next panel (highlight top session with reasoning)
2. Priority indicators on session cards
3. Optional sort-by-priority toggle
4. Context panel on session select (expanded project state)
5. Integration with existing notification system (priority-aware notifications)

**Success Criteria:**
- Users know at a glance which session needs attention
- Complete focus-aware dashboard
- End-to-end epic goal achieved

**What This Sprint Does NOT Include:**
- Calendar integration
- Mobile support

**Technical Notes:**
- All HTML/CSS/JS is inline in monitor.py (single-file application)
- Uses vanilla JS with no external dependencies
- Existing notification system uses terminal-notifier

**Dependencies:** Sprint 7 (AI Prioritisation)

**PRD Output Location:** docs/prds/focus/
```

---

## Sprint Execution Order

Based on the dependency graph in the roadmap, execute sprints in this order:

| Order | Sprint | Dependencies |
|-------|--------|--------------|
| 1 | Sprint 1: YAML Foundation | None |
| 2 | Sprint 2: Roadmap Management | Sprint 1 |
| 3 | Sprint 3: Session Summarisation | Sprint 1 |
| 4 | Sprint 6: Focus Strategy | Sprint 1 |
| 5 | Sprint 4: History Compression | Sprint 3 |
| 6 | Sprint 5: Brain Reboot View | Sprints 2, 4 |
| 7 | Sprint 7: AI Prioritisation | Sprints 4, 6 |
| 8 | Sprint 8: Focus-Aware Dashboard UI | Sprint 7 |

---

## Notes

- Each prompt references the roadmap explicitly for context
- PRDs should be saved to `docs/prds/focus/` subsystem directory
- Sprint numbers in the prompt match the roadmap, but execution order follows dependencies
- The PRD workshop process will guide through requirements elicitation, scope definition, and validation
