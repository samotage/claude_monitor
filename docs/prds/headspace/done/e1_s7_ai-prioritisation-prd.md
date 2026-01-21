---
validation:
  status: valid
  validated_at: '2026-01-21T19:59:26+11:00'
---

## Product Requirements Document (PRD) — AI Prioritisation

**Project:** Claude Monitor
**Scope:** Epic 1, Sprint 7 - AI ranks sessions based on headspace, roadmaps, and activity state
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD defines the requirements for AI-powered session prioritisation in Claude Monitor. The system combines the user's declared headspace (Sprint 6), project roadmaps (Sprint 2), current project states (Sprint 3), and real-time activity states to generate an intelligent ranking of which session deserves attention next.

The key deliverable is an API endpoint that returns a prioritised list of sessions with rationale explaining why each session is ranked where it is. The AI considers relevance to the user's stated focus, project urgency, session activity state (processing/idle/input_needed), and staleness. Priorities refresh automatically on a configurable interval, with soft transitions that avoid jarring reorders while the user is actively working.

This sprint delivers the intelligence layer that transforms Claude Monitor from a passive session viewer into an active focus assistant. Success is measured by the API's ability to surface the most relevant session to the user's current headspace, provide meaningful rationale, and handle edge cases (missing headspace, offline sessions, API failures) gracefully.

---

## 1. Context & Purpose

### 1.1 Context

Claude Monitor displays multiple concurrent Claude Code sessions but provides no guidance on which one deserves attention. Users manually scan session cards, check activity states, and mentally cross-reference their current priorities. This cognitive overhead increases with the number of active projects.

Sprints 1-6 established the data foundation: project roadmaps (where projects are heading), session states (what's happening now), history (what happened before), and headspace (what the user is trying to accomplish). Sprint 7 combines these signals with AI to answer the question: "Given everything I know about your projects and your stated focus, which session should you work on next?"

### 1.2 Target User

Developers managing 3+ concurrent Claude Code sessions who need to:
- Know at a glance which session needs attention
- Understand why a session is recommended (not just that it is)
- Trust that priorities reflect their stated headspace
- Avoid cognitive overhead of manually prioritising

### 1.3 Success Moment

A developer has four Claude Code sessions running: auth-service (processing), billing-api (idle), frontend-ui (input_needed), and infra-setup (idle). Their headspace is "Ship billing feature for client demo Thursday." They call `/api/priorities` and receive:

1. **billing-api** (priority: 95) - "Directly aligned with your headspace goal. Session is idle and ready for your input."
2. **frontend-ui** (priority: 70) - "Waiting for input. May be related to billing UI components."
3. **auth-service** (priority: 40) - "Currently processing. Not directly related to billing focus."
4. **infra-setup** (priority: 20) - "Idle. No apparent connection to current headspace."

The developer immediately knows to focus on billing-api, understands why, and can proceed without deliberation.

---

## 2. Scope

### 2.1 In Scope

- **Priorities API Endpoint**: `GET /api/priorities` returns ranked session list with rationale
- **Context Aggregation**: Gather headspace, all project roadmaps, project states, and session activity states
- **LLM Prompt Construction**: Token-efficient prompt combining all context for AI ranking
- **OpenRouter Integration**: Reuse existing client (from Sprint 4) to call ranking model
- **Ranked Output**: Return ordered list with priority score (0-100) and reasoning per session
- **Polling Configuration**: Configurable interval for automatic re-prioritisation
- **Soft Transitions**: Delay reordering until sessions reach natural pause points
- **Graceful Degradation**: Handle missing headspace, offline sessions, API failures
- **Response Caching**: Cache priorities within polling interval to avoid redundant API calls
- **Configuration**: Enable/disable prioritisation, polling interval, model selection

### 2.2 Out of Scope

- Dashboard UI changes (Sprint 8)
- Notification integration with priorities (Sprint 8)
- Manual priority overrides or pinning
- Priority history or audit logging
- Multiple ranking strategies or algorithms
- Real-time streaming priority updates
- Per-project priority weighting configuration
- Priority-based auto-focus (automatically switching windows)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. **SC1**: `GET /api/priorities` returns a ranked list of all active sessions
2. **SC2**: Each session in the response includes a priority score (0-100) and human-readable rationale
3. **SC3**: Sessions most relevant to the current headspace rank highest
4. **SC4**: Sessions with `input_needed` activity state receive priority boost (they need attention)
5. **SC5**: Priorities automatically refresh on the configured interval
6. **SC6**: Soft transitions prevent reordering while any session is actively processing
7. **SC7**: When headspace is not set, prioritisation uses project roadmaps and activity states only
8. **SC8**: When OpenRouter is unavailable, the endpoint returns sessions in default order with error indication

### 3.2 Non-Functional Success Criteria

1. **SC9**: API response completes within 3 seconds under normal conditions
2. **SC10**: Cached responses return within 100ms
3. **SC11**: OpenRouter API key is never logged or included in responses
4. **SC12**: Prioritisation does not block or slow down session scanning
5. **SC13**: System handles 10+ concurrent projects without prompt token overflow

---

## 4. Functional Requirements (FRs)

### Context Aggregation

**FR1**: The system gathers the current headspace (current_focus, constraints) from the headspace data store

**FR2**: The system gathers roadmap data (next_up, upcoming) for all registered projects

**FR3**: The system gathers current state summary for all projects with active sessions

**FR4**: The system gathers real-time activity state (processing, idle, input_needed) for all active sessions

**FR5**: The system gathers recent session context (what was worked on recently) for each project

**FR6**: The system handles missing data gracefully (project without roadmap, missing headspace, etc.)

### Prompt Construction

**FR7**: The system constructs a token-efficient prompt that includes headspace, project contexts, and activity states

**FR8**: The prompt instructs the AI to return a ranked list with scores and rationale

**FR9**: The prompt emphasises relevance to headspace as the primary ranking factor

**FR10**: The prompt considers activity state as a secondary factor (input_needed gets attention boost)

**FR11**: The prompt handles the case where headspace is not set (rank by roadmap urgency and activity)

### API Endpoint

**FR12**: `GET /api/priorities` returns a JSON response with ranked sessions

**FR13**: The response includes for each session: project_name, session_id, priority_score (0-100), rationale (string), activity_state

**FR14**: Sessions are ordered by priority_score descending (highest priority first)

**FR15**: The response includes metadata: timestamp, headspace_summary, cache_hit (boolean)

**FR16**: The endpoint returns appropriate error responses when prioritisation fails

### OpenRouter Integration

**FR17**: The system reuses the existing `call_openrouter()` function from Sprint 4

**FR18**: The system uses a configurable model (default: claude-3-haiku for speed/cost)

**FR19**: The system parses the AI response to extract structured priority data

**FR20**: The system handles malformed AI responses gracefully (fallback to default ordering)

### Polling & Refresh

**FR21**: The system automatically re-prioritises on a configurable interval (default: 60 seconds)

**FR22**: The polling interval is configurable in config.yaml

**FR23**: The system caches the most recent priorities and serves cached responses within the interval

**FR24**: Manual refresh is available via `GET /api/priorities?refresh=true` to bypass cache

### Soft Transitions

**FR25**: The system tracks when priorities were last updated

**FR26**: The system delays priority reordering if any session is actively processing

**FR27**: When all sessions reach a natural pause (idle or input_needed), pending priority updates are applied

**FR28**: The API response indicates if a soft transition is pending

### Configuration

**FR29**: Prioritisation can be enabled/disabled in config.yaml

**FR30**: The polling interval is configurable (default: 60 seconds)

**FR31**: The AI model for prioritisation is configurable (default: same as compression model)

**FR32**: Configuration changes take effect without application restart

---

## 5. Non-Functional Requirements (NFRs)

**NFR1**: API response time must be under 3 seconds for fresh prioritisation

**NFR2**: Cached responses must return within 100ms

**NFR3**: The prioritisation prompt must fit within model context limits for 10+ projects

**NFR4**: OpenRouter API key must never appear in logs, errors, or responses

**NFR5**: Prioritisation must run in background without blocking session scanning

**NFR6**: Failed prioritisation attempts must be logged with sufficient detail for debugging

**NFR7**: All new functionality must have unit test coverage

**NFR8**: Integration tests must verify end-to-end prioritisation flow (with mocked OpenRouter)

---

## 6. Technical Context

This section provides context for implementation without prescribing solutions.

### Data Sources

The prioritisation system aggregates data from multiple sources established in earlier sprints:

- **Headspace** (Sprint 6): `data/headspace.yaml` - current_focus, constraints
- **Project Roadmaps** (Sprint 2): `data/projects/<name>.yaml` - roadmap.next_up, roadmap.upcoming
- **Project State** (Sprint 3): `data/projects/<name>.yaml` - state.summary
- **Recent Sessions** (Sprint 3): `data/projects/<name>.yaml` - recent_sessions
- **Activity State** (existing): Real-time from `scan_sessions()` - processing/idle/input_needed

### OpenRouter Integration

Sprint 4 established the OpenRouter integration pattern:
- `get_openrouter_config()` - reads API key and model from config
- `call_openrouter(messages, model)` - HTTP client with error handling
- Configuration in `config.yaml` under `openrouter` section

The prioritisation feature reuses this infrastructure with a new prompt builder.

### Response Format

The API should return data suitable for Sprint 8's dashboard consumption:

```
{
  "priorities": [
    {
      "project_name": "billing-api",
      "session_id": "abc123",
      "priority_score": 95,
      "rationale": "Directly aligned with your headspace goal...",
      "activity_state": "idle"
    },
    ...
  ],
  "metadata": {
    "timestamp": "2024-01-15T10:30:00Z",
    "headspace_summary": "Ship billing feature for client demo Thursday",
    "cache_hit": false,
    "soft_transition_pending": false
  }
}
```

### Dependencies

- Sprint 4 (History Compression) - OpenRouter client and configuration
- Sprint 6 (Headspace) - User intent data for ranking
- Sprints 1-3 - Project data structure (roadmaps, state, sessions)
