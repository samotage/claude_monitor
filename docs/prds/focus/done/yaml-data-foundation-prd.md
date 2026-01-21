---
validation:
  status: valid
  validated_at: '2026-01-21T18:27:27+11:00'
---

## Product Requirements Document (PRD) — YAML Data Foundation

**Project:** Claude Monitor
**Scope:** Epic 1 Sprint 1 - Persistent data layer for project state storage
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

This PRD establishes the persistent data layer that transforms Claude Monitor from a stateless session viewer into a context-aware focus management tool. By creating structured YAML files for each monitored project, we enable all downstream Epic 1 features including roadmap management, session summarisation, brain reboot, and AI prioritisation.

The foundation sprint delivers the `data/projects/` directory structure, YAML schema definition, Python read/write utilities, and automatic project registration with seeding from each project's CLAUDE.md file. This is a backend-only change with no UI modifications.

Upon completion, each project in `config.yaml` will have a corresponding YAML data file containing the project's goal, tech stack, and placeholder sections for future sprint features.

---

## 1. Context & Purpose

### 1.1 Context

Claude Monitor currently displays live session status by reading transient state from iTerm and `.claude-monitor-*.json` state files at request time. It has no persistent memory of project context, goals, or history. The Epic 1 vision requires storing structured project data that survives across dashboard restarts and enables features like "brain reboot" context reload.

### 1.2 Target User

Developers using Claude Monitor to track multiple Claude Code sessions across projects. They need persistent project context to quickly recall where each project is heading and what happened recently.

### 1.3 Success Moment

When a developer adds a new project to `config.yaml` and restarts the monitor, a corresponding project YAML file is automatically created in `data/projects/` with the project's goal and tech stack extracted from its CLAUDE.md file.

---

## 2. Scope

### 2.1 In Scope

- `data/` directory structure with `projects/` subdirectory
- YAML schema definition for project data files
- Python utilities for reading and writing project YAML files
- Project registration mechanism linking `config.yaml` entries to data files
- Automatic seeding of project YAML from project's CLAUDE.md (goal, tech stack)
- Idempotent registration (re-registering preserves existing data)
- Graceful handling of missing or malformed CLAUDE.md files

### 2.2 Out of Scope

- Roadmap section content (empty placeholder only)
- State section content (empty placeholder only)
- Sessions section content (empty placeholder only)
- History section content (empty placeholder only)
- Any AI/LLM integration
- Any dashboard UI changes
- New API endpoints
- Parsing Claude Code JSONL logs

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Each project listed in `config.yaml` has a corresponding `data/projects/<slug>.yaml` file
2. Project YAML files contain: name, path, goal, and context section (tech_stack, target_users, refreshed_at)
3. Project YAML files contain placeholder sections for: roadmap, state, recent_sessions, history
4. Project data can be created, read, and updated via Python utilities
5. Re-registering a project does not overwrite existing data (idempotent)
6. Missing or malformed CLAUDE.md results in empty goal/tech_stack (no errors)

### 3.2 Non-Functional Success Criteria

1. YAML operations follow existing codebase patterns (`yaml.safe_load`, `yaml.dump`)
2. File operations handle common edge cases (permissions, disk space) gracefully

---

## 4. Functional Requirements (FRs)

### Directory Structure

**FR1:** The system shall create a `data/projects/` directory structure for storing project YAML files.

**FR2:** Project data files shall be named using a slugified version of the project name from `config.yaml` (lowercase, spaces converted to hyphens).

### YAML Schema

**FR3:** Project YAML files shall conform to the following schema:

```yaml
name: "Display Name"
path: "/absolute/path/to/project"
goal: "One-line purpose statement"

context:
  tech_stack: "Frameworks, languages, databases"
  target_users: "Target user description"
  refreshed_at: <ISO8601 timestamp>

roadmap: {}
state: {}
recent_sessions: []
history: {}
```

**FR4:** The `refreshed_at` field shall be updated whenever the project data is modified.

### Data Utilities

**FR5:** The system shall provide a function to load a project's YAML data given its name or path.

**FR6:** The system shall provide a function to save/update a project's YAML data.

**FR7:** The system shall provide a function to list all registered projects with their data.

### Project Registration

**FR8:** When a project from `config.yaml` does not have a corresponding data file, the system shall create one automatically.

**FR9:** Project registration shall extract the project goal from the "Project Overview" section of the project's CLAUDE.md file.

**FR10:** Project registration shall extract the tech stack from the "Tech Stack" section of the project's CLAUDE.md file.

**FR11:** If CLAUDE.md is missing or does not contain the expected sections, registration shall proceed with empty strings for goal and tech_stack.

**FR12:** Registration shall be idempotent: re-registering an existing project shall not overwrite user-modified data.

### Integration

**FR13:** The system shall check for and register missing project data files on monitor startup.

**FR14:** The system shall use existing PyYAML patterns from the codebase (`yaml.safe_load`, `yaml.dump` with `default_flow_style=False`).

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** YAML file operations shall complete within 100ms for typical project files.

**NFR2:** The system shall log warnings (not errors) when CLAUDE.md parsing fails, allowing the monitor to continue operating.

---

## 6. Technical Context

### 6.1 YAML Schema Reference

📌 **Full schema example** (from workshop):

```yaml
# data/projects/raglue.yaml

name: RAGlue
path: /Users/sam/dev/raglue
goal: "Document-centric RAG platform with citation fidelity as core differentiator"

context:
  tech_stack: "Rails 8.1.1, Ruby 3.4.x, Postgres, Hotwire"
  target_users: "Technical-adjacent professionals"
  refreshed_at: 2026-01-21T06:00:00+11:00

# === Placeholder sections for future sprints ===
roadmap: {}
state: {}
recent_sessions: []
history: {}
```

### 6.2 Directory Structure

```
claude_monitor/
├── data/
│   ├── strategy.yaml          # Sprint 6: Focus strategy (not this sprint)
│   └── projects/
│       ├── raglue.yaml
│       ├── claude-monitor.yaml
│       └── <project-slug>.yaml
├── monitor.py
├── config.yaml
└── ...
```

### 6.3 CLAUDE.md Parsing

Extract content from these sections by header name:
- "Project Overview" or "## Project Overview" → `goal`
- "Tech Stack" or "## Tech Stack" → `tech_stack`

Fallback: If headers not found, return empty strings.

---

## 7. Dependencies

- **Depends on:** None (foundation sprint)
- **Enables:** Sprint 2 (Roadmap Management), Sprint 3 (Session Summarisation), Sprint 6 (Focus Strategy)
