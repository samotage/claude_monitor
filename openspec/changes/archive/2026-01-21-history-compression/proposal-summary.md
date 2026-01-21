# Proposal Summary: history-compression

## Architecture Decisions
- Use OpenRouter API for AI-powered summarisation (establishes pattern for Sprint 7)
- Background thread for non-blocking compression processing
- Queue-based architecture: sessions enter pending queue, processed asynchronously
- Merge-based history: new compressions merge with existing narrative

## Implementation Approach
- Hook into Sprint 3's `add_recent_session()` to detect removed sessions
- Store pending compressions in project YAML (`pending_compressions` list)
- Background thread checks queue at configurable interval (default: 5 minutes)
- OpenRouter HTTP client with authentication, timeout, retry logic
- Prompt engineering for token-efficient narrative generation
- History section stores compressed narrative with timestamp

## Files to Modify
- **monitor.py**: Add history compression functions
  - Queue management (add_to_compression_queue, get_pending_compressions, remove_from_compression_queue)
  - History operations (get_project_history, update_project_history)
  - OpenRouter client (get_openrouter_config, call_openrouter)
  - AI summarisation (build_compression_prompt, compress_session)
  - Background processing (process_compression_queue, start_compression_thread)
- **config.yaml**: Add `openrouter` section (api_key, model, compression_interval)
- **requirements.txt**: Confirm `requests` is available (already present)

## Acceptance Criteria
- SC1: Session removed from recent_sessions is queued for compression
- SC2: Background process compresses pending sessions
- SC3: History contains coherent narrative merging new and existing
- SC4: OpenRouter API calls authenticate and return summaries
- SC5: Sessions remain queued on API failure for retry

## Constraints and Gotchas
- API key must NEVER appear in logs or responses (security critical)
- Background thread must not block Flask requests
- OpenRouter rate limits: implement exponential backoff (1min, 5min, 30min)
- 30-second timeout on HTTP requests
- Must handle missing/invalid API key gracefully (log error, keep queued)
- Config changes should apply without restart

## Git Change History

### Related Files
- Models: None (YAML-based storage)
- Controllers: monitor.py (main Flask app)
- Services: monitor.py (session summarisation functions added in Sprint 3)
- Config: config.yaml

### OpenSpec History
- session-summarisation (Sprint 3) - Added session capture, FIFO window, summarise_session()
- project-roadmap-management (Sprint 2) - Added project YAML management

### Implementation Patterns
- All functions in single monitor.py file
- YAML storage for project data
- Config read via config.yaml with get_config()
- Background tasks via threading module

## Q&A History
- No clarifications needed - PRD is comprehensive and clear

## Dependencies
- Python `requests` library (already in requirements.txt)
- OpenRouter API account with valid API key
- Sprint 3 session-summarisation must be complete (provides FIFO trigger)

## Testing Strategy
- Unit tests for queue operations (add, get, remove)
- Unit tests for history operations (get, update)
- Unit tests for OpenRouter client with mocked responses
- Unit tests for error handling (429, 401, timeout)
- Unit tests for retry logic with exponential backoff
- Integration test for end-to-end compression flow (mocked API)

## OpenSpec References
- proposal.md: openspec/changes/history-compression/proposal.md
- tasks.md: openspec/changes/history-compression/tasks.md
- spec.md: openspec/changes/history-compression/specs/history-compression/spec.md
