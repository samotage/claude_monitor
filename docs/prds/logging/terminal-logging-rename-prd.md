---
validation:
  status: valid
  validated_at: '2026-01-25T11:16:08+11:00'
---

## Product Requirements Document (PRD) — Terminal Logging Generalization

**Project:** Claude Headspace
**Scope:** Rename tmux-specific logging to backend-agnostic terminal logging with backend identification
**Author:** Workshop Generated
**Status:** Draft

---

## Executive Summary

Claude Headspace now supports multiple terminal backends (tmux and WezTerm), but the shared logging infrastructure still carries tmux-specific naming throughout: the UI tab, API endpoints, config keys, log file, and Python module are all labeled "tmux" despite being used by both backends. This creates confusion, particularly for users running WezTerm as their primary backend.

This PRD specifies renaming the logging system from "tmux" to "terminal" across the UI, API, configuration, and codebase. It also adds a backend identifier field to each log entry so users can distinguish which backend produced a given event. A backward compatibility strategy ensures existing logs without a backend field are treated as tmux-origin entries.

The result is a logging system whose naming accurately reflects its multi-backend nature, with clear per-entry attribution.

---

## 1. Context & Purpose

### 1.1 Context

The logging infrastructure was originally built for tmux session message debugging. When the WezTerm backend was added, it was wired into the same logging module and log file. However, all user-facing names — the UI tab, API routes, config keys — still say "tmux." Users running WezTerm see "tmux" labels throughout the logging interface, which is misleading and confusing.

### 1.2 Target User

Developers and operators of Claude Headspace who use either tmux or WezTerm (or both) as their terminal backend and need to debug session communication.

### 1.3 Success Moment

A developer using WezTerm opens the Logging panel, sees a "terminal" tab (not "tmux"), views log entries each clearly tagged with "wezterm" or "tmux," and filters to show only WezTerm events to debug a session issue.

---

## 2. Scope

### 2.1 In Scope

- Add a `backend` field ("tmux" or "wezterm") to each log entry
- Rename the Logging panel UI tab from "tmux" to "terminal"
- Display the backend identifier visually in each log entry in the list
- Rename API endpoints from `/api/logs/tmux/*` to `/api/logs/terminal/*`
- Rename configuration key from `tmux_logging.debug_enabled` to `terminal_logging.debug_enabled`
- Rename the log file from `data/logs/tmux.jsonl` to `data/logs/terminal.jsonl`
- Rename the Python module from `lib/tmux_logging.py` to `lib/terminal_logging.py`
- Rename the `TmuxLogEntry` dataclass to `TerminalLogEntry`
- Add backend filter capability to the UI and API
- Backward compatibility: existing log entries without a `backend` field default to "tmux"
- Update all imports and references across the codebase
- Update tests to reflect new naming

### 2.2 Out of Scope

- Separate log files per backend
- Separate UI tabs per backend
- Changes to backend send/capture logic
- New logging events or event types
- Log retention policies or automatic cleanup
- Log export functionality

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. The Logging panel tab displays "terminal" instead of "tmux"
2. Each log entry includes a `backend` field indicating "tmux" or "wezterm"
3. The backend identifier is visually displayed on each log entry in the list
4. Users can filter log entries by backend in the UI
5. The API supports filtering logs by backend via query parameter
6. API endpoints at `/api/logs/terminal/*` function correctly
7. Configuration uses `terminal_logging.debug_enabled` key
8. Logs are written to `data/logs/terminal.jsonl`
9. Existing log entries in the old `tmux.jsonl` file without a `backend` field are read with a default of "tmux"
10. All existing logging features (search, refresh, pop-out, auto-refresh, expand/collapse) continue to work

### 3.2 Non-Functional Success Criteria

1. Rename does not introduce any perceptible performance change
2. Visual styling of the terminal tab matches the existing design (dark theme, consistent spacing)
3. The backend indicator is visually distinct but not distracting in the log entry list

---

## 4. Functional Requirements (FRs)

### Log Entry Structure

**FR1:** Each log entry includes a `backend` field with value "tmux" or "wezterm", indicating which terminal backend produced the event.

**FR2:** The backend field is set automatically based on which backend instance creates the log entry.

**FR3:** When reading log entries that lack a `backend` field, the system defaults the value to "tmux".

### Naming — Module and Dataclass

**FR4:** The logging module is named `terminal_logging` (file: `lib/terminal_logging.py`).

**FR5:** The log entry dataclass is named `TerminalLogEntry`.

**FR6:** All codebase imports reference the new module and class names.

### Naming — Log File

**FR7:** New log entries are written to `data/logs/terminal.jsonl`.

**FR8:** On startup, if `data/logs/tmux.jsonl` exists and `data/logs/terminal.jsonl` does not, the old file is read as the log source (backward compatibility).

### Naming — Configuration

**FR9:** The debug toggle configuration key is `terminal_logging.debug_enabled`.

**FR10:** On startup, if the old `tmux_logging.debug_enabled` key is present in config and the new key is not, the old value is used.

### Naming — API Endpoints

**FR11:** Log retrieval endpoint is `/api/logs/terminal`.

**FR12:** Log statistics endpoint is `/api/logs/terminal/stats`.

**FR13:** Debug toggle endpoints are `/api/logs/terminal/debug` (GET and POST).

**FR14:** The API log retrieval endpoint accepts an optional `backend` query parameter to filter results by backend ("tmux" or "wezterm").

### UI — Tab

**FR15:** The Logging panel displays a "terminal" tab in place of the former "tmux" tab.

**FR16:** The terminal tab retains all existing features: search, refresh, pop-out, auto-refresh, expand/collapse.

### UI — Backend Indicator

**FR17:** Each log entry in the list displays a visual indicator of its backend (e.g., a label showing "tmux" or "wezterm").

**FR18:** The backend indicator is visible in both collapsed and expanded log entry views.

### UI — Backend Filter

**FR19:** The terminal log view includes a filter control to show all entries, only tmux entries, or only wezterm entries.

**FR20:** The filter state persists during the session (not reset by auto-refresh).

### Tests

**FR21:** All existing logging tests pass under the new naming.

**FR22:** Tests cover the `backend` field: presence in new entries, default for old entries, filtering by backend.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The terminal tab uses the same visual design as the existing tab implementation (dark theme, monospace fonts, consistent spacing).

**NFR2:** The backend indicator styling is minimal — a small label or badge that does not dominate the log entry layout.

**NFR3:** Backward-compatible config and file reading adds no startup delay beyond file existence checks.

---

## 6. UI Overview

### Tab Navigation (Updated)

```
+----------------------------------------------------+
| [openrouter] [terminal]                  [^ pop-out] |
+----------------------------------------------------+
```

### Backend Filter

```
+----------------------------------------------------+
| Filter: [All] [tmux] [wezterm]          [Q Search]  |
+----------------------------------------------------+
```

### Log Entry — Collapsed (with backend indicator)

```
+------------------------------------------------------+
| 2026-01-25 14:32:15                                  |
| claude-monitor  -> OUT  send_keys         [wezterm]  |
+------------------------------------------------------+
+------------------------------------------------------+
| 2026-01-25 14:32:16                                  |
| claude-monitor  <- IN   capture_pane      [tmux]     |
+------------------------------------------------------+
```

### Log Entry — Expanded (with backend indicator)

```
+------------------------------------------------------+
| 2026-01-25 14:32:15                                  |
| claude-monitor  -> OUT  send_keys         [wezterm]  |
| ---------------------------------------------------- |
| Correlation ID: abc-123                              |
| Backend: wezterm                                     |
|                                                      |
| Payload:                                             |
| /review the changes in lib/tmux.py                   |
|                                                      |
+------------------------------------------------------+
```
