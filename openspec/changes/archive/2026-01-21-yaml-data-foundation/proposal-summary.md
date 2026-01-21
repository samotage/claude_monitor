# Proposal Summary: yaml-data-foundation

## Architecture Decisions
- All project data stored in YAML files (consistent with existing config.yaml pattern)
- Single-file-per-project structure in `data/projects/`
- Slugified filenames (lowercase, hyphens) for cross-platform compatibility
- Idempotent registration to preserve user modifications

## Implementation Approach
- Add new functions to `monitor.py` (single-file application pattern)
- Follow existing PyYAML patterns (`yaml.safe_load`, `yaml.dump`)
- Parse CLAUDE.md by section headers (## Project Overview, ## Tech Stack)
- Call `register_all_projects()` during Flask app initialization
- Use logging for registration events (info for success, warning for missing CLAUDE.md)

## Files to Modify
- `monitor.py` - Add project data utilities and startup hook
- `data/projects/` - New directory (create with .gitkeep)
- `data/projects/*.yaml` - Generated files per registered project

## Acceptance Criteria
1. Each project in config.yaml has corresponding `data/projects/<slug>.yaml`
2. YAML files contain: name, path, goal, context (tech_stack, target_users, refreshed_at)
3. YAML files have placeholder sections: roadmap, state, recent_sessions, history
4. Re-registering doesn't overwrite existing data
5. Missing CLAUDE.md handled gracefully (empty strings)

## Constraints and Gotchas
- CLAUDE.md parsing is best-effort - missing sections return empty strings
- Section extraction looks for "## Project Overview" and "## Tech Stack" headers
- `refreshed_at` updates on every save, not just on changes
- Directory must exist before saving files
- No API endpoints in this sprint (foundation only)

## Git Change History

### Related Files
- **Config**: config.yaml (existing), config.yaml.example (existing)
- **Main**: monitor.py (existing - will be modified)
- **New**: data/projects/*.yaml

### OpenSpec History
- No previous changes to this subsystem (greenfield)

### Implementation Patterns
- Single-file application (all code in monitor.py)
- PyYAML for config: `yaml.safe_load()` / `yaml.dump(default_flow_style=False)`
- Path handling: `Path(__file__).parent / "path"`
- Function pattern: `load_config()` / `save_config()` as reference

## Q&A History
- No clarifications needed - PRD was sufficiently detailed
- YAML schema provided by user during workshop phase

## Dependencies
- PyYAML (already installed)
- No new dependencies required

## Testing Strategy
- Unit tests for each utility function (slugify, load, save, list)
- CLAUDE.md parsing tests (valid, missing, malformed)
- Registration tests (new project, re-registration, missing CLAUDE.md)
- Integration test: add project to config.yaml, restart, verify YAML created

## OpenSpec References
- proposal.md: openspec/changes/yaml-data-foundation/proposal.md
- tasks.md: openspec/changes/yaml-data-foundation/tasks.md
- spec.md: openspec/changes/yaml-data-foundation/specs/project-data/spec.md
