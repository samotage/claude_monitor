# Proposal Summary: session-summarisation

## Architecture Decisions

- **Single-file pattern maintained:** All changes go in `monitor.py` following existing codebase conventions
- **No AI dependency:** Summarisation uses rule-based extraction from JSONL logs
- **Streaming parser:** Process large log files line-by-line for memory efficiency
- **FIFO session window:** Maintain exactly 5 most recent sessions per project

## Implementation Approach

1. **Log Discovery first:** Implement path encoding and directory lookup
2. **JSONL Parser:** Build streaming parser with graceful error handling
3. **End Detection:** Add idle timeout and process termination checks to scan loop
4. **Extraction:** Build modular functions for files/commands/errors extraction
5. **Persistence:** Update YAML `state` and `recent_sessions` sections
6. **API:** Add manual summarisation endpoint

## Files to Modify

- **monitor.py** (primary):
  - Add `encode_project_path()` and `get_claude_logs_directory()` functions
  - Add `parse_jsonl_stream()` streaming parser
  - Add `is_session_idle()` and `is_session_process_alive()` detection
  - Add `extract_*` functions for summarisation
  - Add `summarise_session()` master function
  - Add `update_project_state()` and `add_recent_session()` persistence
  - Add `POST /api/session/<id>/summarise` endpoint
  - Modify scan loop to detect session ends

- **config.yaml**:
  - Add `idle_timeout_minutes` setting (default: 60)

- **data/projects/*.yaml** (schema extension - backward compatible):
  - `state` section populated with latest session outcome
  - `recent_sessions` list with up to 5 session records

## Acceptance Criteria

1. Session summaries auto-written to YAML within 60 seconds of session end
2. `recent_sessions` contains up to 5 sessions with required fields
3. `state` section reflects most recent session outcome
4. Summaries include files modified, commands executed, errors
5. API endpoint returns valid summary and updates YAML
6. No external AI API calls required
7. JSONL parsing handles malformed lines gracefully

## Constraints and Gotchas

- **Claude Code log format:** Depends on `~/.claude/projects/<encoded-path>/` structure
- **Path encoding:** Forward slashes become hyphens (e.g., `/Users/sam/project` → `-Users-sam-project`)
- **Memory efficiency:** Must stream large JSONL files, not load entire file
- **Non-blocking:** JSONL parsing must not block Flask main thread
- **Session UUID matching:** State file UUID must match JSONL `sessionId` field
- **Config hot-reload:** Idle timeout changes should apply without restart

## Git Change History

### Related Files
- Main: monitor.py
- Config: config.yaml
- Tests: test_session_summarisation.py (to be created)

### OpenSpec History
- `yaml-data-foundation` - Archived Jan 21, 2026 - Created project data structure with `state: {}` and `recent_sessions: []` placeholders
- `project-roadmap-management` - Archived Jan 21, 2026 - Added roadmap management (parallel track)

### Implementation Patterns
- Flask route pattern: `@app.route("/api/session/<id>/summarise", methods=["POST"])`
- Data access: Use `load_project_data()` and `save_project_data()` from Sprint 1
- Response pattern: `return jsonify({"success": True, "data": summary})`

## Q&A History

- No clarifications needed - PRD was comprehensive and clear
- Decision: Use rule-based extraction (no AI) per Sprint 3 scope

## Dependencies

- **Python:** No new packages required (json, os, pathlib in stdlib)
- **Frontend:** No UI changes (deferred to future sprint)
- **Sprint 1:** Uses `load_project_data()`, `save_project_data()`, existing YAML schema

## Testing Strategy

### Unit Tests
- Test `encode_project_path()` with various path formats
- Test JSONL parsing with valid and malformed data
- Test extraction functions with sample log content
- Test FIFO logic for 5-session limit

### Integration Tests
- Test idle timeout detection
- Test process termination detection
- Test full summarisation pipeline
- Test API endpoint success and error cases

### Manual Verification
- Trigger actual Claude Code session
- Wait for session to end
- Verify YAML updated with summary
- Test API endpoint with real session ID

## OpenSpec References

- proposal.md: openspec/changes/session-summarisation/proposal.md
- tasks.md: openspec/changes/session-summarisation/tasks.md
- spec.md: openspec/changes/session-summarisation/specs/session-summarisation/spec.md
