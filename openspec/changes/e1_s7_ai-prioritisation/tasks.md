## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Data Layer - Context Aggregation

- [ ] 2.1 Create `get_all_project_roadmaps()` function to gather roadmap data for all projects
- [ ] 2.2 Create `get_all_project_states()` function to gather current state for all projects
- [ ] 2.3 Create `get_sessions_with_activity()` function to get active sessions with activity states
- [ ] 2.4 Create `aggregate_priority_context()` function to combine headspace, roadmaps, states, sessions

### Prompt Construction

- [ ] 2.5 Create `build_prioritisation_prompt()` function with token-efficient format
- [ ] 2.6 Handle headspace-present case (primary: headspace relevance, secondary: activity)
- [ ] 2.7 Handle headspace-absent case (primary: roadmap urgency, secondary: activity)
- [ ] 2.8 Create `parse_priority_response()` function to extract structured data from AI response

### API Endpoint

- [ ] 2.9 Create `GET /api/priorities` endpoint returning ranked sessions
- [ ] 2.10 Add priority_score (0-100), rationale, activity_state to each session
- [ ] 2.11 Add metadata: timestamp, headspace_summary, cache_hit, soft_transition_pending
- [ ] 2.12 Add error handling for prioritisation failures

### Caching & Polling

- [ ] 2.13 Create priority cache storage (in-memory with timestamp)
- [ ] 2.14 Implement `is_cache_valid()` function based on polling interval
- [ ] 2.15 Add `?refresh=true` query parameter to bypass cache
- [ ] 2.16 Create background prioritisation refresh mechanism

### Soft Transitions

- [ ] 2.17 Create `is_any_session_processing()` function to detect active processing
- [ ] 2.18 Implement soft transition delay logic
- [ ] 2.19 Track pending priority updates
- [ ] 2.20 Apply pending updates when all sessions paused

### Configuration

- [ ] 2.21 Add `priorities` section to config.yaml with enabled, polling_interval, model
- [ ] 2.22 Create `is_priorities_enabled()` helper function
- [ ] 2.23 Create `get_priorities_config()` helper function

### Graceful Degradation

- [ ] 2.24 Handle missing headspace (fallback to roadmap-based ranking)
- [ ] 2.25 Handle OpenRouter unavailable (return default ordering with error indication)
- [ ] 2.26 Handle malformed AI response (fallback to default ordering)

## 3. Testing (Phase 3)

### Unit Tests

- [ ] 3.1 Test `aggregate_priority_context()` with various data combinations
- [ ] 3.2 Test `build_prioritisation_prompt()` prompt construction
- [ ] 3.3 Test `parse_priority_response()` with valid and malformed responses
- [ ] 3.4 Test cache validity logic
- [ ] 3.5 Test soft transition detection

### API Tests

- [ ] 3.6 Test `GET /api/priorities` success response format
- [ ] 3.7 Test cache hit behavior
- [ ] 3.8 Test `?refresh=true` cache bypass
- [ ] 3.9 Test error responses when prioritisation disabled
- [ ] 3.10 Test graceful degradation scenarios

### Integration Tests

- [ ] 3.11 End-to-end prioritisation flow with mocked OpenRouter
- [ ] 3.12 Verify soft transition behavior

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
- [ ] 4.4 API response time under 3 seconds
