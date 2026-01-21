# project-data Specification

## Purpose
TBD - created by archiving change yaml-data-foundation. Update Purpose after archive.
## Requirements
### Requirement: Project Data Directory Structure

The system SHALL store project data files in a dedicated `data/projects/` directory.

#### Scenario: Directory Creation

- **WHEN** the monitor starts
- **THEN** the `data/projects/` directory SHALL exist (created if missing)

### Requirement: Project Data File Naming

Project data files SHALL be named using a slugified version of the project name.

#### Scenario: Name Slugification

- **WHEN** a project named "My Project" is registered
- **THEN** the file SHALL be named `my-project.yaml`

#### Scenario: Simple Name

- **WHEN** a project named "raglue" is registered
- **THEN** the file SHALL be named `raglue.yaml`

### Requirement: Project YAML Schema

Project YAML files SHALL conform to the defined schema with required and placeholder fields.

#### Scenario: New Project File Structure

- **WHEN** a new project file is created
- **THEN** it SHALL contain:
  - `name`: Display name from config.yaml
  - `path`: Absolute path from config.yaml
  - `goal`: Extracted from CLAUDE.md or empty string
  - `context.tech_stack`: Extracted from CLAUDE.md or empty string
  - `context.target_users`: Empty string (future use)
  - `context.refreshed_at`: ISO8601 timestamp of creation
  - `roadmap`: Empty object `{}`
  - `state`: Empty object `{}`
  - `recent_sessions`: Empty array `[]`
  - `history`: Empty object `{}`

### Requirement: Project Data Load Function

The system SHALL provide a function to load project data by name or path.

#### Scenario: Load Existing Project

- **WHEN** `load_project_data("my-project")` is called
- **AND** `data/projects/my-project.yaml` exists
- **THEN** the function SHALL return the parsed YAML data as a dictionary

#### Scenario: Load Non-Existent Project

- **WHEN** `load_project_data("unknown")` is called
- **AND** no matching file exists
- **THEN** the function SHALL return `None`

### Requirement: Project Data Save Function

The system SHALL provide a function to save/update project data.

#### Scenario: Save Project Data

- **WHEN** `save_project_data("my-project", data)` is called
- **THEN** the data SHALL be written to `data/projects/my-project.yaml`
- **AND** `context.refreshed_at` SHALL be updated to current timestamp

### Requirement: List All Projects Function

The system SHALL provide a function to list all registered projects with their data.

#### Scenario: List Projects

- **WHEN** `list_project_data()` is called
- **THEN** it SHALL return a list of all project data dictionaries from `data/projects/`

### Requirement: CLAUDE.md Goal Extraction

Project registration SHALL extract the project goal from the CLAUDE.md file.

#### Scenario: Extract Goal from Project Overview

- **WHEN** registering a project with CLAUDE.md containing "## Project Overview"
- **THEN** the content under that header SHALL be extracted as the `goal`

#### Scenario: Missing Project Overview Section

- **WHEN** registering a project with CLAUDE.md lacking "Project Overview"
- **THEN** `goal` SHALL be set to empty string

### Requirement: CLAUDE.md Tech Stack Extraction

Project registration SHALL extract the tech stack from the CLAUDE.md file.

#### Scenario: Extract Tech Stack

- **WHEN** registering a project with CLAUDE.md containing "## Tech Stack"
- **THEN** the content under that header SHALL be extracted as `context.tech_stack`

#### Scenario: Missing Tech Stack Section

- **WHEN** registering a project with CLAUDE.md lacking "Tech Stack"
- **THEN** `context.tech_stack` SHALL be set to empty string

### Requirement: Missing CLAUDE.md Handling

The system SHALL gracefully handle missing CLAUDE.md files.

#### Scenario: No CLAUDE.md File

- **WHEN** registering a project without a CLAUDE.md file
- **THEN** registration SHALL succeed
- **AND** `goal` SHALL be empty string
- **AND** `context.tech_stack` SHALL be empty string
- **AND** a warning SHALL be logged

### Requirement: Idempotent Registration

Re-registering an existing project SHALL NOT overwrite user-modified data.

#### Scenario: Re-register Existing Project

- **WHEN** `register_project("my-project", "/path")` is called
- **AND** `data/projects/my-project.yaml` already exists
- **THEN** the existing file SHALL NOT be modified
- **AND** the function SHALL return success

### Requirement: Startup Registration

The system SHALL register all missing project data files on startup.

#### Scenario: New Project in Config

- **WHEN** the monitor starts
- **AND** config.yaml contains a project without a data file
- **THEN** the project SHALL be automatically registered
- **AND** the data file SHALL be created

#### Scenario: Existing Project in Config

- **WHEN** the monitor starts
- **AND** config.yaml contains a project with existing data file
- **THEN** the existing data file SHALL NOT be modified

### Requirement: PyYAML Pattern Compliance

YAML operations SHALL use existing codebase patterns.

#### Scenario: YAML Reading

- **WHEN** reading YAML files
- **THEN** `yaml.safe_load()` SHALL be used

#### Scenario: YAML Writing

- **WHEN** writing YAML files
- **THEN** `yaml.dump()` SHALL be used with `default_flow_style=False`

