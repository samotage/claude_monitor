---
validation:
  status: valid
  validated_at: '2026-01-21T19:26:47+11:00'
---

## Product Requirements Document (PRD) — Session Summarisation & State Tracking

**Project:** Claude Monitor
**Scope:** Epic 1, Sprint 3 - Capture Claude Code session activity and maintain project state
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD defines the requirements for capturing Claude Code session activity and maintaining persistent project state within Claude Monitor. Currently, the dashboard shows live session status but loses all context when sessions end. This sprint enables the system to parse Claude Code JSONL logs, detect session completion, and automatically summarise session activity into the project's YAML data file.

The key deliverable is automatic session summarisation without AI dependency. When a Claude Code session ends (via idle timeout or process termination), the system extracts key information from the session logs and persists it to the project's YAML file. This creates the foundation for the Brain Reboot feature (Sprint 5) and History Compression (Sprint 4).

Success is measured by the system's ability to automatically capture session summaries with meaningful content (files modified, commands run, errors encountered) and maintain a rolling window of the 5 most recent sessions per project.

---

## 1. Context & Purpose

### 1.1 Context

Claude Monitor currently provides real-time visibility into active Claude Code sessions across multiple projects. However, all session context is lost when sessions end—users cannot see what happened in previous sessions or understand the current state of their projects.

The YAML Data Foundation (Sprint 1) established persistent storage for project data with placeholder sections for `state` and `recent_sessions`. This sprint populates those sections by parsing Claude Code's native JSONL session logs stored at `~/.claude/projects/`.

### 1.2 Target User

Developers using Claude Code across multiple projects who need to:
- Understand what happened in a session they stepped away from
- Track progress across multiple concurrent projects
- Quickly reload context when returning to a stale project

### 1.3 Success Moment

The user returns to Claude Monitor after being away for several hours. They see that their session on Project X ended 2 hours ago. They click to view recent sessions and see a summary: "Modified 3 files in auth module, ran tests (2 failures), last working on password reset flow." They now have context to resume work.

---

## 2. Scope

### 2.1 In Scope

- **Claude Code Log Discovery**: Locate and read JSONL session logs from `~/.claude/projects/<encoded-path>/`
- **JSONL Parsing**: Extract session messages, timestamps, and metadata from log files
- **Session-to-Project Mapping**: Associate Claude Code sessions with monitored projects using path matching
- **Session End Detection**: Detect session completion via configurable idle timeout or process termination
- **State Section Updates**: Maintain current project state summary in YAML
- **Recent Sessions Storage**: Store last 5 sessions with timestamps, duration, and summaries
- **Simple Summarisation**: Extract key actions (files modified, commands run, errors) without AI
- **API Endpoint**: Manual summarisation trigger via `POST /api/session/<id>/summarise`
- **Configuration**: Idle timeout value configurable in `config.yaml`

### 2.2 Out of Scope

- AI-powered summarisation (deferred to Sprint 4 - History Compression)
- History compression and rolling window beyond 5 sessions (Sprint 4)
- UI for viewing session history (future sprint)
- Dashboard visual changes
- Notification system changes
- Project roadmap integration (Sprint 2, separate track)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. **SC1**: When a Claude Code session ends (idle timeout or termination), a summary is automatically written to the project's YAML file within 60 seconds
2. **SC2**: Project YAML `recent_sessions` contains up to 5 session records, each with: session ID, start time, end time, duration, and human-readable summary
3. **SC3**: Project YAML `state` section reflects the outcome of the most recent session (last action, current status)
4. **SC4**: Session summaries include: files modified (count and names), commands executed, errors encountered (if any)
5. **SC5**: API endpoint `POST /api/session/<id>/summarise` returns a valid summary and updates the project YAML

### 3.2 Non-Functional Success Criteria

1. **SC6**: All summarisation works without external API calls (no AI dependency)
2. **SC7**: JSONL parsing handles malformed lines gracefully (skip and continue)
3. **SC8**: Idle timeout is configurable via `config.yaml` with a sensible default (60 minutes)

---

## 4. Functional Requirements (FRs)

### Log Discovery & Parsing

**FR1**: The system can locate Claude Code JSONL log files by encoding the project path (replacing `/` with `-`) and looking in `~/.claude/projects/<encoded-path>/`

**FR2**: The system can parse JSONL log files, extracting message type, content, timestamp, session ID, and working directory from each line

**FR3**: The system can identify which JSONL files belong to a specific session using the session UUID (matching the `.claude-monitor-*.json` state file UUID)

**FR4**: The system handles JSONL parsing errors gracefully, skipping malformed lines and logging warnings

### Session End Detection

**FR5**: The system detects when a monitored session becomes idle (no new log entries) for longer than the configured timeout period

**FR6**: The system detects when a monitored session's process terminates (PID no longer exists)

**FR7**: When session end is detected, the system triggers automatic summarisation

**FR8**: The idle timeout period is configurable via `config.yaml` with a default of 60 minutes

### Summarisation

**FR9**: The system extracts a list of files modified during the session from JSONL log content

**FR10**: The system extracts commands executed during the session (bash commands, tool invocations)

**FR11**: The system extracts errors and failures encountered during the session

**FR12**: The system generates a human-readable summary paragraph from extracted information (without AI)

### State Persistence

**FR13**: The system updates the project YAML `state` section with the latest session outcome after each session ends

**FR14**: The system maintains a `recent_sessions` list in the project YAML containing the last 5 sessions

**FR15**: When a 6th session is added, the oldest session is removed from `recent_sessions` (FIFO)

**FR16**: Each session record in `recent_sessions` includes: session_id, started_at, ended_at, duration_minutes, summary, files_modified (list), commands_run (count), errors (count)

### API

**FR17**: The system provides a `POST /api/session/<id>/summarise` endpoint that triggers summarisation for a specific session

**FR18**: The API endpoint returns the generated summary and updates the project YAML

**FR19**: The API endpoint returns appropriate error responses for invalid session IDs or missing log files

---

## 5. Non-Functional Requirements (NFRs)

**NFR1**: JSONL parsing must not block the main Flask application (use appropriate async patterns or background processing)

**NFR2**: Session log files may be large (100MB+); parsing must be memory-efficient (streaming, not loading entire file)

**NFR3**: All new functionality must have unit test coverage

**NFR4**: Configuration changes (idle timeout) must not require application restart

---

## 6. Technical Context

This section provides context for implementation without prescribing solutions.

### Claude Code Log Structure

- **Location**: `~/.claude/projects/<encoded-project-path>/`
- **Path Encoding**: `/Users/foo/project` becomes `-Users-foo-project`
- **File Format**: JSONL (one JSON object per line)
- **Session Files**: Named `<session-uuid>.jsonl`
- **Key Fields**: `type`, `sessionId`, `uuid`, `timestamp`, `message`, `cwd`, `gitBranch`

### Existing Integration Points

- `scan_sessions()` in `monitor.py` already discovers active sessions via `.claude-monitor-*.json` state files
- Project YAML files exist at `data/projects/<name>.yaml` with `state` and `recent_sessions` placeholders
- Session state files contain `uuid` that matches JSONL `sessionId`

### Dependencies

- Sprint 1 (YAML Data Foundation) - Complete
- Python standard library for JSONL parsing
- No external AI APIs required
