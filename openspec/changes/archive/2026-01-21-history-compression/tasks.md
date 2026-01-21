# Tasks: History Compression

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Rolling Window & Queue (Phase 2)

- [x] 2.1 Modify `add_recent_session()` to detect and return removed sessions
- [x] 2.2 Implement `add_to_compression_queue()` to store pending sessions in project YAML
- [x] 2.3 Implement `get_pending_compressions()` to retrieve queued sessions
- [x] 2.4 Implement `remove_from_compression_queue()` after successful compression

## 3. History Schema (Phase 2)

- [x] 3.1 Define history schema (`summary`, `last_compressed_at`) in code documentation
- [x] 3.2 Implement `get_project_history()` to retrieve current history
- [x] 3.3 Implement `update_project_history()` to store compressed summary

## 4. OpenRouter Integration (Phase 2)

- [x] 4.1 Add `requests` to requirements.txt
- [x] 4.2 Implement `get_openrouter_config()` to read API key and settings
- [x] 4.3 Implement `call_openrouter()` HTTP client with authentication headers
- [x] 4.4 Add response parsing to extract generated summary text
- [x] 4.5 Add error handling for rate limiting (429) with backoff
- [x] 4.6 Add error handling for authentication errors (401) with logging
- [x] 4.7 Add timeout handling (30 second default)

## 5. AI Summarisation (Phase 2)

- [x] 5.1 Design compression prompt for narrative summary generation
- [x] 5.2 Implement `build_compression_prompt()` with session data and existing history
- [x] 5.3 Implement `compress_session()` master function that coordinates API call
- [x] 5.4 Implement history merging logic for unified narrative

## 6. Background Processing (Phase 2)

- [x] 6.1 Implement `process_compression_queue()` to handle pending sessions
- [x] 6.2 Add exponential backoff retry logic (1min, 5min, 30min)
- [x] 6.3 Implement background thread or periodic task for compression checks
- [x] 6.4 Add `compression_interval` configuration option (default: 5 minutes)
- [x] 6.5 Ensure background processing doesn't block Flask requests

## 7. Configuration (Phase 2)

- [x] 7.1 Add `openrouter` section to config.yaml schema
- [x] 7.2 Implement API key retrieval with security (never log key)
- [x] 7.3 Add model selection config with default `anthropic/claude-3-haiku`
- [x] 7.4 Ensure config changes apply without restart

## 8. Testing (Phase 3)

- [x] 8.1 Test queue operations (add, get, remove)
- [x] 8.2 Test history operations (get, update)
- [x] 8.3 Test OpenRouter client with mocked responses
- [x] 8.4 Test error handling (429, 401, timeout)
- [x] 8.5 Test retry logic with exponential backoff
- [x] 8.6 Test end-to-end compression flow with mocked API

## 9. Final Verification

- [x] 9.1 All tests passing
- [ ] 9.2 No linter errors
- [ ] 9.3 Manual verification of full workflow
- [x] 9.4 Verify API key security (not logged, not exposed)
