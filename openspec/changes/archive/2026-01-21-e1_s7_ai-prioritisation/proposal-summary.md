# Proposal Summary: e1_s7_ai-prioritisation

## Architecture Decisions
- Reuse existing `call_openrouter()` function from Sprint 4 for AI integration
- In-memory caching with timestamp for priority responses (no additional file storage)
- Soft transitions delay reordering when any session is processing to avoid jarring UX
- Token-efficient prompt construction to handle 10+ projects within context limits

## Implementation Approach
- Add prioritisation functions to `monitor.py` following existing patterns
- Create context aggregation layer that pulls from headspace, roadmaps, states, and sessions
- Build prompt that emphasises headspace relevance as primary factor, activity state as secondary
- Cache responses for configurable polling interval, with manual refresh option
- Graceful degradation: missing headspace falls back to roadmap-based ranking; OpenRouter failure returns default order

## Files to Modify
- `monitor.py` - Context aggregation, prompt construction, API endpoint, caching, soft transitions
- `test_project_data.py` - Unit tests for prioritisation functions
- `config.yaml.example` - Document priorities configuration options

## Acceptance Criteria
- `GET /api/priorities` returns ranked list with scores (0-100) and rationale
- Sessions most relevant to headspace rank highest
- `input_needed` sessions get priority boost
- Cache serves responses within polling interval
- Soft transitions prevent reordering during active processing
- Graceful degradation for missing data or API failures

## Constraints and Gotchas
- Must reuse existing `call_openrouter()` - do not duplicate OpenRouter integration
- Prompt must fit within model context limits for 10+ projects
- API response time under 3 seconds for fresh prioritisation
- API key must never be logged or exposed in responses
- Do not block session scanning - prioritisation runs in background conceptually
- Sprint 8 will consume this API for dashboard UI - ensure stable response format

## Git Change History

### Related Files
Sprint 4 established OpenRouter integration patterns:
- `monitor.py` contains `call_openrouter()`, `get_openrouter_config()`
Sprint 6 established headspace data patterns:
- `monitor.py` contains `load_headspace()`, `HEADSPACE_DATA_PATH`

### OpenSpec History
- e1_s6_headspace (2026-01-21) - Added headspace data layer and API

### Implementation Patterns
- Follow existing API endpoint patterns (Flask routes with JSON responses)
- Follow existing config helper patterns (`is_*_enabled()`, `get_*_config()`)
- Follow existing test patterns using pytest fixtures and monkeypatch

## Q&A History
- No clarifications needed - PRD was well-structured with clear requirements
- Dependencies on Sprints 1-6 are all in place

## Dependencies
- Sprint 4 (History Compression) - OpenRouter client (`call_openrouter()`)
- Sprint 6 (Headspace) - User intent data (`load_headspace()`)
- Sprints 1-3 - Project data structure (roadmaps, state, sessions)
- No new packages required - reusing existing dependencies

## Testing Strategy
- Unit tests for context aggregation with various data combinations
- Unit tests for prompt construction (with/without headspace)
- Unit tests for response parsing (valid and malformed responses)
- Unit tests for cache validity logic
- Unit tests for soft transition detection
- API tests for endpoint responses, cache behavior, error handling
- Integration tests with mocked OpenRouter for end-to-end flow

## OpenSpec References
- proposal.md: openspec/changes/e1_s7_ai-prioritisation/proposal.md
- tasks.md: openspec/changes/e1_s7_ai-prioritisation/tasks.md
- spec.md: openspec/changes/e1_s7_ai-prioritisation/specs/priorities/spec.md
