---
validation:
  status: valid
  validated_at: '2026-01-22T14:14:16+11:00'
---

## Product Requirements Document (PRD) — Logging UI Panel

**Project:** Claude Headspace
**Scope:** Dashboard logging panel with tabbed interface for API call visibility
**Author:** Workshop Generated
**Status:** Draft

---

## Executive Summary

Claude Headspace currently provides no visibility into OpenRouter API calls made by the application. This creates challenges for cost management, quality monitoring, and debugging during development.

This PRD specifies a new Logging UI panel accessible from the main navigation. The panel uses a tabbed interface to support multiple log types, with the OpenRouter API log as the first implementation. Users can view API call details including request/response data, token counts, costs, and status. The panel supports opening in a new browser tab for side-by-side monitoring and includes search functionality for filtering log entries.

This capability enables developers to understand API usage patterns, debug issues quickly, and make informed decisions about model selection and optimization.

---

## 1. Context & Purpose

### 1.1 Context

The application makes OpenRouter API calls for features like history compression and AI prioritization. Currently there is no way to see what calls are being made, what they cost, or whether they succeed or fail. This lack of visibility makes it difficult to:
- Track API usage costs
- Debug failed API calls
- Understand model performance
- Optimize prompt engineering

### 1.2 Target User

Developers and operators of Claude Headspace who need visibility into API activity for cost management, debugging, and continuous improvement.

### 1.3 Success Moment

The user clicks on the Logging tab, sees a list of recent OpenRouter API calls, expands one to view the full request and response, and immediately understands what happened and how much it cost.

---

## 2. Scope

### 2.1 In Scope

- New "Logging" item in main tab navigation
- Logging panel with tabbed sub-navigation for different log types
- OpenRouter API log tab displaying:
  - Timestamp of each call
  - Request payload (messages sent)
  - Response content received
  - Input token count
  - Output token count
  - Cost of the call
  - Model identifier used
  - Success or failure status
  - Error message when applicable
- Expandable log entries (collapsed by default, expand on click)
- Reverse chronological ordering (newest entries first)
- Search functionality to filter log entries
- Pop-out capability to open logging panel in new browser tab
- Auto-refresh to show new log entries without manual reload
- Backend API to serve log data to the frontend
- Log data persistence specification (what data the API calling code must capture)
- Empty state when no logs exist

### 2.2 Out of Scope

- Modifying existing API calling code to write logs (separate implementation task)
- Additional log type tabs beyond OpenRouter (future PRDs)
- Log retention policies and automatic cleanup
- Log export to file or external systems
- Historical analytics, charts, or aggregations
- Log entry editing or deletion from the UI

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Logging tab is visible in main navigation alongside existing tabs
2. Clicking Logging tab displays the logging panel with sub-tab navigation
3. OpenRouter sub-tab shows list of API call log entries
4. Each log entry displays timestamp, model, status, and cost in collapsed view
5. Clicking a log entry expands it to show full request and response details
6. Search input filters log entries by any visible field content
7. Log entries appear in reverse chronological order (newest first)
8. New log entries appear automatically without page refresh
9. "Open in new tab" action opens logging panel in separate browser tab
10. Empty state message displays when no log entries exist

### 3.2 Non-Functional Success Criteria

1. Log panel styling matches existing dark theme and design patterns
2. Auto-refresh updates smoothly without visual disruption
3. Expandable entries animate smoothly
4. Search filtering responds without noticeable delay

---

## 4. Functional Requirements (FRs)

### Navigation & Structure

**FR1:** The main tab navigation includes a "Logging" tab button after existing tabs.

**FR2:** The logging panel contains sub-tab navigation for different log types.

**FR3:** The OpenRouter sub-tab is the default/first tab shown when accessing Logging.

**FR4:** The logging panel can be opened in a new browser tab via a pop-out action.

### Log Entry Display

**FR5:** Each log entry displays in a collapsed card format showing:
- Timestamp (human-readable format)
- Model identifier
- Success/failure status indicator
- Cost of the call
- Token count summary (input + output)

**FR6:** Clicking a collapsed log entry expands it to reveal:
- Full request payload (messages sent to API)
- Full response content received
- Detailed token breakdown (input count, output count)
- Error message if the call failed

**FR7:** Clicking an expanded log entry collapses it back to summary view.

**FR8:** Log entries are ordered with newest entries at the top.

### Search & Filtering

**FR9:** A search input field is displayed above the log entry list.

**FR10:** Entering text in the search field filters log entries to show only those containing the search text in any displayed field.

**FR11:** Clearing the search field shows all log entries again.

### Auto-Refresh

**FR12:** New log entries appear in the list automatically without requiring page refresh.

**FR13:** Auto-refresh does not disrupt the user's current view (no scroll jumping, no collapse of expanded entries).

### Empty & Error States

**FR14:** When no log entries exist, an empty state message is displayed indicating no logs are available.

**FR15:** When log data cannot be loaded, an error state is displayed with a retry option.

### Log Data Specification

**FR16:** The logging system captures and persists the following data for each OpenRouter API call:
- Timestamp (ISO 8601 format)
- Request payload (messages array sent to API)
- Response content (text returned from API)
- Input token count
- Output token count
- Cost (calculated from tokens and model pricing)
- Model identifier
- Success/failure boolean
- Error message (if failure)

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The logging panel uses the same visual design language as existing tabs (dark theme, monospace fonts, consistent spacing).

**NFR2:** Auto-refresh polling occurs at a reasonable interval that balances responsiveness with resource usage.

**NFR3:** Search filtering completes within 100ms for typical log volumes.

**NFR4:** Expand/collapse animations complete within 200ms.

**NFR5:** The pop-out logging tab functions independently and continues auto-refreshing.

---

## 6. UI Overview

### Main Navigation
The existing tab navigation bar gains a new "logging" tab button. Visual treatment matches existing tab buttons (dashboard, focus, config, help).

### Logging Panel Layout
```
+--------------------------------------------------+
| [openrouter] [future-tab] [future-tab]    [↗ pop-out] |
+--------------------------------------------------+
| [🔍 Search logs...]                              |
+--------------------------------------------------+
| ┌──────────────────────────────────────────────┐ |
| │ 2026-01-22 14:32:15                          │ |
| │ claude-3-haiku  ✓ Success  $0.0012  450 tok  │ |
| └──────────────────────────────────────────────┘ |
| ┌──────────────────────────────────────────────┐ |
| │ 2026-01-22 14:30:02                          │ |
| │ claude-3-haiku  ✗ Failed   --       0 tok    │ |
| │ ─────────────────────────────────────────────│ |
| │ Request:                                      │ |
| │ [{ "role": "system", "content": "..." },     │ |
| │  { "role": "user", "content": "..." }]       │ |
| │                                               │ |
| │ Response:                                     │ |
| │ (none - request failed)                       │ |
| │                                               │ |
| │ Error: timeout                                │ |
| │                                               │ |
| │ Tokens: 0 in / 0 out                          │ |
| └──────────────────────────────────────────────┘ |
| ┌──────────────────────────────────────────────┐ |
| │ 2026-01-22 14:28:44                          │ |
| │ claude-3-haiku  ✓ Success  $0.0008  312 tok  │ |
| └──────────────────────────────────────────────┘ |
+--------------------------------------------------+
```

### Collapsed Entry
Shows one-line summary: timestamp, model, status icon, cost, total tokens.

### Expanded Entry
Shows full details below the summary line:
- Request section with formatted JSON/text
- Response section with formatted text
- Error message (if applicable)
- Token breakdown (input / output)

### Empty State
Centered message: "No API logs yet. Logs will appear here when OpenRouter API calls are made."

### Pop-out Behavior
The pop-out button opens `/logging` (or similar route) in a new browser tab, showing the logging panel in standalone mode without the main dashboard chrome.
