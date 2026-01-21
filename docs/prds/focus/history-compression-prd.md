---
validation:
  status: valid
  validated_at: '2026-01-21T19:35:04+11:00'
---

## Product Requirements Document (PRD) — History Compression

**Project:** Claude Monitor
**Scope:** Epic 1, Sprint 4 - Automatically compress old sessions into AI-summarised history
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD defines the requirements for automatically compressing old session records into a coherent narrative summary using AI. As projects accumulate sessions beyond the 5-session rolling window (established in Sprint 3), the oldest sessions need to be preserved in a token-efficient format that maintains semantic meaning for the Brain Reboot feature (Sprint 5).

The key deliverable is OpenRouter integration for AI-powered summarisation. When sessions are removed from the `recent_sessions` window, they enter a pending compression queue. A background process calls OpenRouter to generate a narrative summary, which is stored in the project's `history` section. This establishes the external API integration pattern that will be reused in Sprint 7 (AI Prioritisation).

Success is measured by the system's ability to automatically compress sessions without data loss, handle API failures gracefully with retry logic, and produce meaningful narrative summaries that preserve the arc of project work.

---

## 1. Context & Purpose

### 1.1 Context

Sprint 3 establishes session capture with a 5-session rolling window in `recent_sessions`. When a 6th session is added, the oldest is removed via FIFO. Without compression, this historical context is lost entirely.

Simple aggregation (file counts, command totals) loses semantic meaning. AI summarisation preserves the narrative: "Implemented auth flow, hit a blocker with OAuth, pivoted to JWT" - context that matters when users need to reload their mental state on a project.

This sprint introduces the first external API integration (OpenRouter), establishing patterns for authentication, error handling, and retry logic that will be reused in Sprint 7.

### 1.2 Target User

Developers managing multiple Claude Code projects over weeks or months who need to:
- Understand the full arc of project work, not just the last 5 sessions
- Reload context on projects they haven't touched in a while
- Maintain project history without manual note-taking

### 1.3 Success Moment

A developer returns to a project after three weeks. The Brain Reboot view shows: "Over the past month: Completed user authentication module, refactored database layer for performance, started work on API rate limiting but paused due to upstream dependency." The developer understands the project trajectory without reading through dozens of individual session logs.

---

## 2. Scope

### 2.1 In Scope

- **Rolling Window Trigger**: Detect sessions removed from `recent_sessions` and queue for compression
- **Pending Compression Queue**: Store sessions awaiting AI summarisation
- **Background Compression Process**: Asynchronously process pending sessions via OpenRouter
- **History Schema**: Simple structure with `summary` and `last_compressed_at` fields
- **OpenRouter Integration**: HTTP client with authentication, error handling, and retry logic
- **AI Summarisation**: Token-efficient prompt design for narrative compression
- **Configuration**: OpenRouter API key, model selection (default: claude-3-haiku)
- **Graceful Failure Handling**: Retry logic, queue persistence, logging

### 2.2 Out of Scope

- Live prioritisation (Sprint 7)
- Brain reboot UI (Sprint 5)
- Manual history editing or deletion
- Multiple AI provider support (OpenRouter only)
- Real-time streaming responses
- History search or querying
- Re-compression of history itself (future sprint)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. **SC1**: When a session is removed from `recent_sessions`, it is added to the pending compression queue
2. **SC2**: Background process compresses pending sessions and updates the project's `history.summary` field
3. **SC3**: History contains a coherent narrative summary that merges new compressions with existing history
4. **SC4**: OpenRouter API calls authenticate successfully and return valid summaries
5. **SC5**: When OpenRouter is unavailable, sessions remain in pending queue and are retried later

### 3.2 Non-Functional Success Criteria

1. **SC6**: API key is stored securely in config.yaml (gitignored) and never logged
2. **SC7**: Failed API calls are retried with exponential backoff (max 3 attempts per cycle)
3. **SC8**: Compression prompt uses minimal tokens while preserving semantic meaning
4. **SC9**: Background compression does not block the main Flask application

---

## 4. Functional Requirements (FRs)

### Rolling Window & Queue

**FR1**: The system detects when a session is removed from `recent_sessions` (triggered by Sprint 3's FIFO logic)

**FR2**: Removed sessions are added to a pending compression queue stored in the project YAML

**FR3**: The pending compression queue persists across application restarts

**FR4**: A background process periodically checks for pending compressions (configurable interval)

### History Schema

**FR5**: The project YAML `history` section contains: `summary` (string) and `last_compressed_at` (ISO timestamp)

**FR6**: When history is empty, the first compression initialises the summary

**FR7**: When history exists, new compressions are merged with the existing summary to create a unified narrative

### OpenRouter Integration

**FR8**: The system calls OpenRouter's chat completion API with proper authentication headers

**FR9**: The system supports configurable model selection with a default of `anthropic/claude-3-haiku`

**FR10**: API responses are parsed to extract the generated summary text

**FR11**: The system handles rate limiting responses (429) with appropriate backoff

**FR12**: The system handles authentication errors (401) with clear error logging

### AI Summarisation

**FR13**: The compression prompt instructs the AI to create a narrative summary of session activity

**FR14**: The prompt includes existing history context when merging (to maintain continuity)

**FR15**: The prompt is designed to be token-efficient (minimal system prompt, structured input)

**FR16**: The generated summary preserves: what was worked on, key decisions, blockers encountered, current status

### Graceful Failure Handling

**FR17**: When an API call fails, the session remains in the pending queue for retry

**FR18**: Retry attempts use exponential backoff (e.g., 1min, 5min, 30min)

**FR19**: After maximum retry attempts in a cycle, the session stays queued for the next cycle

**FR20**: All API failures are logged with sufficient detail for debugging

**FR21**: The system does not lose session data due to API failures

### Configuration

**FR22**: OpenRouter API key is configured in `config.yaml` under an `openrouter` section

**FR23**: Model selection is configurable with a sensible default (`anthropic/claude-3-haiku`)

**FR24**: Compression check interval is configurable (default: 5 minutes)

**FR25**: Configuration changes take effect without application restart

---

## 5. Non-Functional Requirements (NFRs)

**NFR1**: API key must never appear in logs, error messages, or responses

**NFR2**: Background compression must not block Flask request handling

**NFR3**: HTTP requests to OpenRouter must have reasonable timeouts (30 seconds default)

**NFR4**: All new functionality must have unit test coverage (mocked API calls)

**NFR5**: Integration tests should verify end-to-end compression flow (with mocked OpenRouter)

---

## 6. Technical Context

This section provides context for implementation without prescribing solutions.

### OpenRouter API

- **Endpoint**: `https://openrouter.ai/api/v1/chat/completions`
- **Authentication**: Bearer token in Authorization header
- **Request Format**: OpenAI-compatible chat completion format
- **Default Model**: `anthropic/claude-3-haiku` (fast, cost-effective for summarisation)

### Sprint 3 Integration Points

- Sprint 3 FR15 defines FIFO removal when 6th session added
- Sprint 3 FR16 defines session record structure (session_id, started_at, ended_at, duration_minutes, summary, files_modified, commands_run, errors)
- This sprint hooks into the removal event to queue sessions for compression

### Configuration Structure

```yaml
# Addition to config.yaml
openrouter:
  api_key: "sk-or-..."  # Required
  model: "anthropic/claude-3-haiku"  # Optional, has default
  compression_interval: 300  # Optional, seconds between checks
```

### Dependencies

- Sprint 3 (Session Summarisation) - Provides session data and FIFO trigger
- OpenRouter API account with valid API key
- Python HTTP library (requests or similar)
