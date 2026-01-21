## Why

Claude Monitor currently has no persistent memory of project context, goals, or history. Each dashboard load reads transient state from iTerm and state files. This foundation sprint establishes the persistent data layer that enables all Epic 1 features (roadmap management, session summarisation, brain reboot, AI prioritisation).

## What Changes

- Add `data/projects/` directory structure for project YAML files
- Create Python utilities for reading/writing project YAML data
- Implement project registration mechanism that links `config.yaml` projects to data files
- Add CLAUDE.md parsing to seed project goal and tech stack
- Ensure idempotent registration (re-registering preserves existing data)
- Handle missing/malformed CLAUDE.md gracefully (empty strings, no errors)

## Impact

- **Affected specs**: None (new capability)
- **Affected code**:
  - `monitor.py` - Add project data utilities and startup registration
  - `data/projects/*.yaml` - New files created per project
- **Dependencies**: None (foundation sprint)
- **Breaking changes**: None
