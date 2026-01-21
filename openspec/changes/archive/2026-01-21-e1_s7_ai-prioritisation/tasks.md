## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Data Layer - Context Aggregation

- [x] 2.1 Create `get_all_project_roadmaps()` function to gather roadmap data for all projects
- [x] 2.2 Create `get_all_project_states()` function to gather current state for all projects
- [x] 2.3 Create `get_sessions_with_activity()` function to get active sessions with activity states
- [x] 2.4 Create `aggregate_priority_context()` function to combine headspace, roadmaps, states, sessions

### Prompt Construction

- [x] 2.5 Create `build_prioritisation_prompt()` function with token-efficient format
- [x] 2.6 Handle headspace-present case (primary: headspace relevance, secondary: activity)
- [x] 2.7 Handle headspace-absent case (primary: roadmap urgency, secondary: activity)
- [x] 2.8 Create `parse_priority_response()` function to extract structured data from AI response

### API Endpoint

- [x] 2.9 Create `GET /api/priorities` endpoint returning ranked sessions
- [x] 2.10 Add priority_score (0-100), rationale, activity_state to each session
- [x] 2.11 Add metadata: timestamp, headspace_summary, cache_hit, soft_transition_pending
- [x] 2.12 Add error handling for prioritisation failures

### Caching & Polling

- [x] 2.13 Create priority cache storage (in-memory with timestamp)
- [x] 2.14 Implement `is_cache_valid()` function based on polling interval
- [x] 2.15 Add `?refresh=true` query parameter to bypass cache
- [x] 2.16 Create background prioritisation refresh mechanism

### Soft Transitions

- [x] 2.17 Create `is_any_session_processing()` function to detect active processing
- [x] 2.18 Implement soft transition delay logic
- [x] 2.19 Track pending priority updates
- [x] 2.20 Apply pending updates when all sessions paused

### Configuration

- [x] 2.21 Add `priorities` section to config.yaml with enabled, polling_interval, model
- [x] 2.22 Create `is_priorities_enabled()` helper function
- [x] 2.23 Create `get_priorities_config()` helper function

### Graceful Degradation

- [x] 2.24 Handle missing headspace (fallback to roadmap-based ranking)
- [x] 2.25 Handle OpenRouter unavailable (return default ordering with error indication)
- [x] 2.26 Handle malformed AI response (fallback to default ordering)

## 3. Testing (Phase 3)

### Unit Tests

- [x] 3.1 Test `aggregate_priority_context()` with various data combinations
- [x] 3.2 Test `build_prioritisation_prompt()` prompt construction
- [x] 3.3 Test `parse_priority_response()` with valid and malformed responses
- [x] 3.4 Test cache validity logic
- [x] 3.5 Test soft transition detection

### API Tests

- [x] 3.6 Test `GET /api/priorities` success response format
- [x] 3.7 Test cache hit behavior
- [x] 3.8 Test `?refresh=true` cache bypass
- [x] 3.9 Test error responses when prioritisation disabled
- [x] 3.10 Test graceful degradation scenarios

### Integration Tests

- [x] 3.11 End-to-end prioritisation flow with mocked OpenRouter
- [x] 3.12 Verify soft transition behavior

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete
- [x] 4.4 API response time under 3 seconds
