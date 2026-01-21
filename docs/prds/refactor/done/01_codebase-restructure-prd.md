---
validation:
  status: valid
  validated_at: '2026-01-21T21:08:38+11:00'
---

## Product Requirements Document (PRD) — Codebase Restructure

**Project:** Claude Monitor
**Scope:** Refactor monolithic monitor.py into modular architecture
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD defines the requirements for restructuring the Claude Monitor codebase from a single 4,125-line `monitor.py` file into a modular architecture with clear separation of concerns.

The current monolithic structure emerged organically through four feature sprints (YAML Data Foundation, Project Roadmap Management, Session Summarisation, History Compression). While functional, the single-file architecture creates maintenance challenges: difficult navigation, high cognitive load, and no clear ownership boundaries.

The restructuring extracts the embedded HTML/CSS/JS template (~2,100 lines) to a proper templates directory, organizes Python code into logical modules under `lib/`, and reduces `monitor.py` to its core responsibility as the Flask application entry point.

**Key Outcome:** Improved developer experience with faster navigation, easier testing, and clearer code organization—without any functional changes.

---

## 1. Context & Purpose

### 1.1 Context

The Claude Monitor application has grown through multiple feature additions:
- Sprint 1: YAML data layer (~300 lines)
- Sprint 2: Project/roadmap management (~300 lines)
- Sprint 3: Session summarisation (~400 lines)
- Sprint 4: History compression (~350 lines)
- Core functionality: iTerm integration, session scanning, notifications (~700 lines)
- Embedded HTML template (~2,100 lines)

All code resides in `monitor.py`, making it difficult to:
- Find specific functionality quickly
- Understand module boundaries
- Test components in isolation
- Onboard new contributors

### 1.2 Target User

Developers maintaining and extending the Claude Monitor codebase.

### 1.3 Success Moment

A developer needs to modify the history compression logic. They navigate directly to `lib/compression.py`, make their change, and run targeted tests—without scrolling through 4,000 lines of unrelated code.

---

## 2. Scope

### 2.1 In Scope

- Extract HTML/CSS/JS template to `templates/index.html`
- Create `lib/` directory with focused Python modules
- Create `config.py` for configuration loading/saving
- Update `monitor.py` to import from new modules
- Update test file imports to reference new module paths
- Maintain backwards compatibility with `restart_server.sh`
- Maintain all existing API endpoints and functionality

### 2.2 Out of Scope

- New features or functionality
- Performance optimizations
- Database or persistence layer changes
- API endpoint additions or modifications
- UI/UX changes
- Changes to the orchestration system (`orch/`)
- Changes to Claude commands (`.claude/commands/`)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. All existing pytest tests pass with updated imports
2. `restart_server.sh` works without modification
3. All API endpoints return identical responses before and after refactoring
4. Dashboard renders identically in browser
5. macOS notifications continue to function
6. iTerm window focus feature continues to work

### 3.2 Non-Functional Success Criteria

1. `monitor.py` reduced to under 600 lines (Flask app, routes, main)
2. Each module in `lib/` is under 400 lines
3. Each module has a single, clear responsibility
4. No circular import dependencies between modules
5. All modules have docstrings explaining their purpose

---

## 4. Functional Requirements (FRs)

### FR1: Template Extraction

The system shall extract the embedded HTML_TEMPLATE string from `monitor.py` to a separate file at `templates/index.html`, and Flask shall be configured to load templates from this directory.

### FR2: Notifications Module

The system shall have a `lib/notifications.py` module containing:
- macOS notification sending via terminal-notifier
- State change detection and notification triggering
- Notification enable/disable state management

### FR3: Configuration Module

The system shall have a `config.py` module containing:
- `config.yaml` loading and saving
- Configuration validation
- Default configuration values

### FR4: iTerm Integration Module

The system shall have a `lib/iterm.py` module containing:
- AppleScript-based iTerm window enumeration
- PID-to-TTY mapping
- Window focus functionality

### FR5: Sessions Module

The system shall have a `lib/sessions.py` module containing:
- Session state file scanning
- Activity state parsing (processing/input_needed/idle)
- Session data aggregation

### FR6: Projects Module

The system shall have a `lib/projects.py` module containing:
- Project YAML data loading and saving
- CLAUDE.md parsing
- Project registration
- Roadmap data management

### FR7: Summarization Module

The system shall have a `lib/summarization.py` module containing:
- JSONL log file parsing
- Session activity extraction (files, commands, errors)
- Summary text generation
- Session end detection and processing

### FR8: Compression Module

The system shall have a `lib/compression.py` module containing:
- Compression queue management
- OpenRouter API integration
- History compression logic
- Background compression worker thread

### FR9: Flask Application Core

The `monitor.py` file shall contain only:
- Flask application initialization
- Route definitions (delegating to module functions)
- Application entry point (`main()`)

### FR10: Test Import Updates

All test files shall be updated to import from the new module structure while maintaining test coverage and functionality.

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: No Functional Regression

The refactoring shall not change any observable behavior of the application. All inputs shall produce identical outputs.

### NFR2: Import Organization

Modules shall use absolute imports from the project root. Circular dependencies shall be avoided through careful dependency ordering.

### NFR3: Documentation

Each new module shall include a module-level docstring explaining its purpose and primary exports.

---

## 6. Target Directory Structure

```
claude_monitor/
├── monitor.py           # Flask app, routes, main() (~500 lines)
├── config.py            # Configuration management (~100 lines)
├── templates/
│   └── index.html       # HTML/CSS/JS dashboard (~2,100 lines)
├── lib/
│   ├── __init__.py      # Package marker
│   ├── notifications.py # macOS notifications (~120 lines)
│   ├── iterm.py         # iTerm AppleScript integration (~350 lines)
│   ├── sessions.py      # Session scanning, state parsing (~250 lines)
│   ├── projects.py      # Project data, roadmap, CLAUDE.md (~400 lines)
│   ├── summarization.py # Log parsing, summary generation (~400 lines)
│   └── compression.py   # History compression, OpenRouter (~400 lines)
├── test_project_data.py # Updated imports
└── ...
```

---

## 7. Dependencies

### 7.1 Prerequisites

- Completion of Epic 1 Headspace sprints (S5-S8) recommended
- All current tests passing

### 7.2 Sequencing

This PRD should be implemented after the Headspace epic to avoid merge conflicts and disruption to active feature development.
