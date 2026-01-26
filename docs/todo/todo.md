# Todo

## Pending

- [ ] Review API calling to OpenRouter - verify state transition logic is working correctly and reducing unnecessary API calls
- [ ] Maintain OpenRouter log files - implement trimming of old log entries to prevent unbounded growth
- [ ] Add GitRepo link in Config.yaml - populate git_repo_path field for all projects
- [ ] Fix agents not being created with project IDs in state.yaml - ensure project_id is properly set when agents are created
- [ ] Ensure started_at is included alongside completed_at in tasks in state.yaml - verify all tasks have both timestamp fields
- [ ] Refactor diagnostic.py to use WezTerm instead of tmux

## Completed
