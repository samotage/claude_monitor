## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [ ] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Directory Structure
- [x] 2.1 Create `data/projects/` directory structure
- [x] 2.2 Add `.gitkeep` to ensure directory is tracked

### YAML Schema & Utilities
- [x] 2.3 Create `slugify_name()` function (lowercase, spaces to hyphens)
- [x] 2.4 Create `get_project_data_path(name)` function
- [x] 2.5 Create `load_project_data(name_or_path)` function
- [x] 2.6 Create `save_project_data(name, data)` function
- [x] 2.7 Create `list_project_data()` function

### CLAUDE.md Parsing
- [x] 2.8 Create `parse_claude_md(project_path)` function
- [x] 2.9 Extract "Project Overview" section for goal
- [x] 2.10 Extract "Tech Stack" section for tech_stack
- [x] 2.11 Handle missing/malformed CLAUDE.md (return empty strings)

### Project Registration
- [x] 2.12 Create `register_project(name, path)` function
- [x] 2.13 Implement idempotent logic (skip if file exists with data)
- [x] 2.14 Seed new projects with goal, tech_stack from CLAUDE.md
- [x] 2.15 Set `refreshed_at` timestamp on creation
- [x] 2.16 Initialize placeholder sections (roadmap: {}, state: {}, etc.)

### Integration
- [x] 2.17 Create `register_all_projects()` function
- [x] 2.18 Call `register_all_projects()` on monitor startup
- [x] 2.19 Add logging for registration events (info/warning level)

## 3. Testing (Phase 3)

### Unit Tests
- [x] 3.1 Test `slugify_name()` with various inputs
- [x] 3.2 Test `load_project_data()` with existing file
- [x] 3.3 Test `load_project_data()` with missing file
- [x] 3.4 Test `save_project_data()` creates valid YAML
- [x] 3.5 Test `save_project_data()` updates `refreshed_at`
- [x] 3.6 Test `list_project_data()` returns all projects

### CLAUDE.md Parsing Tests
- [x] 3.7 Test parsing with valid CLAUDE.md
- [x] 3.8 Test parsing with missing CLAUDE.md
- [x] 3.9 Test parsing with CLAUDE.md missing expected sections
- [x] 3.10 Test parsing with malformed CLAUDE.md

### Registration Tests
- [x] 3.11 Test new project registration creates file
- [x] 3.12 Test re-registration does not overwrite existing data
- [x] 3.13 Test registration with missing CLAUDE.md succeeds
- [x] 3.14 Test `register_all_projects()` processes all config projects

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification: add project to config.yaml, restart, verify YAML created
- [ ] 4.4 Manual verification: re-register doesn't overwrite
