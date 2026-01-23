---
validation:
  status: valid
  validated_at: '2026-01-24T15:30:00+11:00'
---

## Product Requirements Document (PRD) — tmux Session Message Logging

**Project:** Claude Headspace
**Scope:** Debug logging for tmux session messages with UI integration
**Author:** Workshop Generated
**Status:** Draft

---

## Executive Summary

Claude Headspace uses tmux for bidirectional communication with Claude Code sessions, but currently provides no visibility into what messages are sent to or received from these sessions. This lack of observability makes it difficult to debug discrepancies between actual session behavior and what the dashboard displays.

This PRD specifies structured logging for tmux session messages (both outgoing commands and incoming output), with a configurable debug toggle to control payload capture. Logs integrate into the existing Logging UI as a new "tmux" tab, following the same patterns and features as the OpenRouter tab. Correlation IDs link related send/capture pairs, enabling developers to reconstruct conversations and diagnose issues.

This capability provides the foundation for a reliable, debuggable tmux integration layer.

---

## 1. Context & Purpose

### 1.1 Context

The tmux integration layer handles sending commands to Claude Code sessions and capturing their output. When the dashboard shows incorrect or unexpected session states, there is currently no way to see what actually happened at the tmux communication level. This makes debugging erratic behavior extremely difficult.

### 1.2 Target User

Developers and operators of Claude Headspace who need to debug tmux session communication issues, understand message flow, and diagnose discrepancies between session state and dashboard display.

### 1.3 Success Moment

The developer notices the dashboard showing an incorrect session state. They open the Logging panel, switch to the tmux tab, filter by session ID, and immediately see the sequence of messages sent and received. They identify that a capture returned stale data, explaining the discrepancy.

---

## 2. Scope

### 2.1 In Scope

- New "tmux" tab in the existing Logging panel UI
- Structured logging of tmux session messages:
  - Outgoing messages sent via send operations
  - Incoming output captured from sessions
- Metadata per log entry:
  - Timestamp (ISO 8601)
  - Session ID
  - tmux session name
  - Direction (in/out)
  - Payload content
  - Correlation ID linking related send/capture pairs
- Config toggle: `debug_tmux_logging: true|false`
  - Off: High-level events only (session_started, session_stopped, send_attempted, capture_attempted) without payload content
  - On: Full payload logging with truncation for large payloads
- Payload truncation: Payloads exceeding 10KB are truncated with indicator
- Human-readable display: Preserved newlines, formatted for readability
- Feature parity with OpenRouter tab: refresh, pop-out, search, auto-refresh
- Persistent log storage

### 2.2 Out of Scope

- Log retention policies and automatic cleanup
- Log export functionality
- Modifications to existing OpenRouter logging code
- Analytics or aggregations over tmux logs
- Real-time streaming display (polling/refresh is sufficient)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. With debug toggle off: No payload content is recorded; only high-level event types are logged
2. With debug toggle on: Full message payloads are captured (subject to truncation limits)
3. A developer can filter logs by session ID and reconstruct the full conversation for that session
4. Correlation IDs correctly link outgoing sends with their corresponding incoming captures
5. tmux tab appears in the Logging panel alongside the OpenRouter tab
6. Log entries display with preserved newlines and human-readable formatting
7. Refresh button updates the log list without page reload
8. Pop-out opens tmux logs in a new browser tab

### 3.2 Non-Functional Success Criteria

1. tmux tab styling matches the existing OpenRouter tab (dark theme, consistent spacing)
2. Search filtering responds without noticeable delay
3. Auto-refresh updates smoothly without disrupting user's current view
4. Logging operations do not noticeably impact tmux command performance

---

## 4. Functional Requirements (FRs)

### Configuration

**FR1:** A configuration option `debug_tmux_logging` controls logging verbosity with values `true` or `false`.

**FR2:** When `debug_tmux_logging` is `false`, the system logs only high-level events: session_started, session_stopped, send_attempted, capture_attempted. No payload content is recorded.

**FR3:** When `debug_tmux_logging` is `true`, the system logs full payload content for all tmux operations.

**FR4:** Payloads exceeding 10KB in size are truncated, with an indicator showing the content was truncated and the original size.

### Log Entry Structure

**FR5:** Each log entry contains: unique ID, timestamp, session_id, tmux_session_name, direction (in/out), event_type, payload (when debug enabled), and correlation_id.

**FR6:** Correlation IDs are generated by the caller before a send operation and passed through to the corresponding capture operation, linking related entries.

**FR7:** Log entries for outgoing messages record the text sent to the session.

**FR8:** Log entries for incoming captures record the output received from the session.

### UI - Tab Integration

**FR9:** The Logging panel displays a "tmux" tab alongside the existing "openrouter" tab.

**FR10:** Clicking the tmux tab displays the list of tmux log entries.

**FR11:** The tmux tab is not the default tab; OpenRouter remains the default.

### UI - Log Entry Display

**FR12:** Each log entry displays in a collapsed card format showing: timestamp, session name, direction indicator (in/out), event type.

**FR13:** Clicking a collapsed log entry expands it to reveal the full payload content (when available).

**FR14:** Expanded payload content displays with preserved newlines and whitespace for human readability.

**FR15:** Truncated payloads display a notice indicating truncation and original size.

**FR16:** Log entries are ordered with newest entries at the top.

### UI - Features

**FR17:** A search input field filters log entries by any visible field content.

**FR18:** A refresh button manually refreshes the log list.

**FR19:** New log entries appear automatically via auto-refresh without requiring manual action.

**FR20:** A pop-out button opens the tmux log view in a new browser tab.

**FR21:** The pop-out view functions independently with its own refresh and search.

### States

**FR22:** When no tmux log entries exist, an empty state message is displayed.

**FR23:** When log data cannot be loaded, an error state is displayed with a retry option.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The tmux tab uses the same visual design as the OpenRouter tab (dark theme, monospace fonts, consistent spacing).

**NFR2:** Logging operations complete without adding perceptible latency to tmux commands.

**NFR3:** Auto-refresh polling occurs at a reasonable interval matching the OpenRouter tab behavior.

**NFR4:** Search filtering completes within 100ms for typical log volumes.

**NFR5:** The log display correctly renders multi-line content without escaping newlines.

---

## 6. UI Overview

### Tab Navigation

The existing Logging panel sub-navigation gains a "tmux" tab:

```
+--------------------------------------------------+
| [openrouter] [tmux]                    [↗ pop-out] |
+--------------------------------------------------+
```

### Log Entry - Collapsed

```
┌──────────────────────────────────────────────────┐
│ 2026-01-24 14:32:15                              │
│ claude-monitor  → OUT  send_keys                 │
└──────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────┐
│ 2026-01-24 14:32:16                              │
│ claude-monitor  ← IN   capture_pane              │
└──────────────────────────────────────────────────┘
```

### Log Entry - Expanded

```
┌──────────────────────────────────────────────────┐
│ 2026-01-24 14:32:15                              │
│ claude-monitor  → OUT  send_keys                 │
│ ─────────────────────────────────────────────────│
│ Correlation ID: abc-123                          │
│                                                  │
│ Payload:                                         │
│ /review the changes in lib/tmux.py               │
│                                                  │
└──────────────────────────────────────────────────┘
```

### Log Entry - With Multiline Payload

```
┌──────────────────────────────────────────────────┐
│ 2026-01-24 14:32:16                              │
│ claude-monitor  ← IN   capture_pane              │
│ ─────────────────────────────────────────────────│
│ Correlation ID: abc-123                          │
│                                                  │
│ Payload:                                         │
│ I'll review the changes in lib/tmux.py.          │
│                                                  │
│ The file contains several functions:             │
│ - send_keys(): Sends text to a session          │
│ - capture_pane(): Captures session output       │
│                                                  │
│ Let me analyze each function...                  │
└──────────────────────────────────────────────────┘
```

### Empty State

Centered message: "No tmux logs yet. Logs will appear here when tmux session operations occur."

### Debug Off Display

When `debug_tmux_logging` is false, log entries show event type only:

```
┌──────────────────────────────────────────────────┐
│ 2026-01-24 14:32:15                              │
│ claude-monitor  → OUT  send_attempted            │
│ (payload logging disabled)                       │
└──────────────────────────────────────────────────┘
```

---

## 7. Technical Considerations

These are implementation hints for the development phase, not requirements:

- **Storage format:** Follow the existing JSONL pattern in `lib/logging.py`
- **Log file location:** `data/logs/tmux.jsonl` alongside `openrouter.jsonl`
- **Hook points:** Instrument `send_keys()` and `capture_pane()` in `lib/tmux.py`
- **Data structure:** Create a `TmuxLogEntry` dataclass following the `LogEntry` pattern
- **Correlation ID flow:** Caller generates UUID before send, passes to both send and capture calls
- **Config location:** Add `debug_tmux_logging` to `config.yaml` schema
