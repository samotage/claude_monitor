## Why

Claude Monitor displays multiple concurrent Claude Code sessions but provides no guidance on which one deserves attention. Users must manually scan session cards and mentally cross-reference their current priorities. This sprint combines headspace, project roadmaps, session states, and real-time activity into an AI-powered prioritisation system that answers: "Which session should you work on next?"

## What Changes

### Context Aggregation
- Gather current headspace (current_focus, constraints) from headspace data store
- Gather roadmap data (next_up, upcoming) for all registered projects
- Gather current state summary for all projects with active sessions
- Gather real-time activity state (processing, idle, input_needed) for all active sessions
- Handle missing data gracefully (project without roadmap, missing headspace)

### Prompt Construction
- Construct token-efficient prompt combining headspace, project contexts, and activity states
- Instruct AI to return ranked list with scores (0-100) and rationale
- Emphasise headspace relevance as primary ranking factor
- Consider activity state as secondary factor (input_needed gets attention boost)
- Handle case where headspace is not set (rank by roadmap urgency and activity)

### API Endpoint
- `GET /api/priorities` returns JSON response with ranked sessions
- Each session includes: project_name, session_id, priority_score, rationale, activity_state
- Sessions ordered by priority_score descending
- Response includes metadata: timestamp, headspace_summary, cache_hit, soft_transition_pending
- Appropriate error responses when prioritisation fails

### OpenRouter Integration
- Reuse existing `call_openrouter()` function from Sprint 4
- Configurable model (default: claude-3-haiku for speed/cost)
- Parse AI response to extract structured priority data
- Handle malformed AI responses gracefully (fallback to default ordering)

### Caching & Polling
- Automatically re-prioritise on configurable interval (default: 60 seconds)
- Cache most recent priorities and serve cached responses within interval
- Manual refresh via `GET /api/priorities?refresh=true` to bypass cache

### Soft Transitions
- Track when priorities were last updated
- Delay priority reordering if any session is actively processing
- Apply pending updates when all sessions reach natural pause (idle or input_needed)
- API response indicates if soft transition is pending

### Configuration
- Enable/disable prioritisation in config.yaml
- Configurable polling interval (default: 60 seconds)
- Configurable AI model for prioritisation

## Impact

- Affected specs: priorities
- Affected code:
  - `monitor.py` - New prioritisation functions, API endpoint, cache management
  - `test_project_data.py` - Unit tests for prioritisation
  - `config.yaml` - New priorities configuration section

## Definition of Done

- [ ] `GET /api/priorities` returns ranked list of all active sessions
- [ ] Each session includes priority_score (0-100) and human-readable rationale
- [ ] Sessions most relevant to current headspace rank highest
- [ ] Sessions with `input_needed` activity state receive priority boost
- [ ] Priorities cache within polling interval
- [ ] Soft transitions prevent reordering while sessions actively processing
- [ ] Graceful degradation when headspace not set or OpenRouter unavailable
- [ ] All unit tests pass
- [ ] Integration tests verify end-to-end flow with mocked OpenRouter
