# session-summarisation Proposal

## Why

Claude Monitor currently provides real-time visibility into active Claude Code sessions but loses all context when sessions end. Users cannot see what happened in previous sessions or understand the current state of their projects. This sprint enables automatic session summarisation by parsing Claude Code JSONL logs and persisting summaries to project YAML files.

## What Changes

- **Log Discovery**: Add functions to locate Claude Code JSONL logs at `~/.claude/projects/<encoded-path>/`
- **JSONL Parsing**: Implement streaming parser for session logs with graceful error handling
- **Session End Detection**: Monitor for idle timeout (configurable, default 60 min) and process termination
- **Summarisation Engine**: Extract files modified, commands executed, and errors encountered without AI
- **State Persistence**: Update project YAML `state` section with latest session outcome
- **Recent Sessions**: Maintain rolling window of 5 most recent sessions per project
- **API Endpoint**: Add `POST /api/session/<id>/summarise` for manual summarisation trigger

## Impact

- Affected specs: None (new capability)
- Affected code: `monitor.py` (new functions and API endpoint)
- Affected config: `config.yaml` (new `idle_timeout_minutes` setting)

## Risk Assessment

- **Risk Level**: Medium
- **Breaking Changes**: None
- **Dependencies**: Relies on Claude Code's JSONL log format (stable public format)
- **Backward Compatibility**: Fully backward compatible - adds new sections to existing YAML structure
