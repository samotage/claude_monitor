# tmux-router Specification

## Purpose
TBD - created by archiving change add-tmux-session-router. Update Purpose after archive.
## Requirements
### Requirement: tmux Session Discovery

The system SHALL discover Claude Code sessions running in tmux and include them in session listings.

#### Scenario: List tmux sessions

- **WHEN** tmux sessions exist with names matching pattern `claude-*`
- **THEN** those sessions appear in `/api/sessions` response
- **AND** each session includes `session_type: "tmux"`

#### Scenario: No tmux installed

- **WHEN** tmux is not installed on the system
- **THEN** the system logs a warning at startup
- **AND** continues operating with iTerm-only session detection

#### Scenario: Mixed session types

- **WHEN** both tmux and iTerm sessions exist for different projects
- **THEN** all sessions appear in the listing
- **AND** each session is correctly typed as `tmux` or `iterm`

---

### Requirement: Send Input to tmux Session

The system SHALL provide an API endpoint to send text input to tmux-based Claude Code sessions.

#### Scenario: Send text successfully

- **WHEN** POST request to `/api/send/<session_id>` with body `{"text": "run tests"}`
- **AND** session exists and is a tmux session
- **THEN** the text is injected into the session via `tmux send-keys`
- **AND** response is `{"success": true}`

#### Scenario: Send to non-existent session

- **WHEN** POST request to `/api/send/<session_id>` for unknown session
- **THEN** response is `{"success": false, "error": "Session not found"}`
- **AND** HTTP status is 404

#### Scenario: Send to iTerm-only session

- **WHEN** POST request to `/api/send/<session_id>` for an iTerm (non-tmux) session
- **THEN** response is `{"success": false, "error": "Session does not support input (not tmux)"}`
- **AND** HTTP status is 400

---

### Requirement: Capture tmux Session Output

The system SHALL provide an API endpoint to capture terminal output from tmux-based sessions.

#### Scenario: Capture output successfully

- **WHEN** GET request to `/api/output/<session_id>`
- **AND** session exists and is a tmux session
- **THEN** response includes recent terminal output from `tmux capture-pane`
- **AND** response format is `{"success": true, "output": "<terminal content>", "lines": <count>}`

#### Scenario: Capture with line limit

- **WHEN** GET request to `/api/output/<session_id>?lines=100`
- **THEN** response includes at most 100 lines of scrollback

#### Scenario: Capture from non-tmux session

- **WHEN** GET request to `/api/output/<session_id>` for iTerm session
- **THEN** response falls back to existing content_tail from AppleScript
- **AND** response includes `{"success": true, "output": "<content>", "source": "iterm"}`

---

### Requirement: Wrapper tmux Integration

The `claude-monitor start` wrapper SHALL launch Claude Code sessions inside named tmux sessions.

#### Scenario: Start new session

- **WHEN** user runs `claude-monitor start` in a project directory
- **AND** no tmux session exists for that project
- **THEN** a new tmux session is created with name `claude-<project-slug>`
- **AND** Claude Code is launched inside that session
- **AND** the state file includes `tmux_session` field

#### Scenario: Session already exists

- **WHEN** user runs `claude-monitor start`
- **AND** a tmux session `claude-<project-slug>` already exists
- **THEN** the wrapper attaches to the existing session
- **OR** prompts user to kill/reuse the existing session

#### Scenario: tmux not available

- **WHEN** user runs `claude-monitor start`
- **AND** tmux is not installed
- **THEN** the wrapper falls back to current behavior (direct Claude launch)
- **AND** displays message: "tmux not found - running without session routing"

---

### Requirement: Session State File Enhancement

The session state file SHALL include tmux session information when applicable.

#### Scenario: State file with tmux info

- **WHEN** a session is started via wrapper with tmux
- **THEN** the `.claude-monitor-<uuid>.json` file includes:
  ```json
  {
    "tmux_session": "claude-myproject",
    "session_type": "tmux"
  }
  ```

#### Scenario: Backwards compatibility

- **WHEN** a state file lacks `tmux_session` field
- **THEN** the session is treated as iTerm-only
- **AND** existing functionality continues to work

---

### Requirement: Project tmux Readiness Check

The system SHALL check each configured project's tmux readiness status and report it via API and dashboard.

#### Scenario: Check tmux availability

- **WHEN** the system starts or `/api/projects` is called
- **THEN** the system checks if tmux is installed on the host
- **AND** includes `tmux_available: true|false` in the response

#### Scenario: Project not configured for tmux

- **WHEN** a project exists in config.yaml without `tmux: true`
- **THEN** the project's status includes `tmux_enabled: false`
- **AND** the project's status includes `tmux_ready: false`

#### Scenario: Project configured for tmux

- **WHEN** a project has `tmux: true` in config.yaml
- **AND** tmux is installed on the system
- **THEN** the project's status includes `tmux_enabled: true`
- **AND** the project's status includes `tmux_ready: true`

#### Scenario: Project configured but tmux unavailable

- **WHEN** a project has `tmux: true` in config.yaml
- **AND** tmux is NOT installed on the system
- **THEN** the project's status includes `tmux_enabled: true`
- **AND** the project's status includes `tmux_ready: false`
- **AND** the project's status includes `tmux_error: "tmux not installed"`

---

### Requirement: Dashboard tmux Status Indicator

The dashboard SHALL display tmux integration status for each configured project and provide setup actions.

#### Scenario: Display tmux status per project

- **WHEN** viewing the dashboard project list or settings
- **THEN** each project shows its tmux status:
  - "tmux: ready" (green) - configured and available
  - "tmux: not enabled" (grey) - not configured, setup available
  - "tmux: unavailable" (orange) - configured but tmux not installed

#### Scenario: Show setup prompt for unconfigured project

- **WHEN** a project has `tmux_enabled: false`
- **AND** tmux is available on the system
- **THEN** the dashboard displays an "Enable tmux" button for that project

#### Scenario: Show install prompt when tmux missing

- **WHEN** tmux is not installed on the system
- **THEN** the dashboard displays a notice: "tmux not installed - run `brew install tmux`"
- **AND** the "Enable tmux" buttons are disabled with tooltip explaining why

---

### Requirement: Enable tmux for Project via API

The system SHALL provide an API endpoint to enable tmux integration for a configured project.

#### Scenario: Enable tmux successfully

- **WHEN** POST request to `/api/projects/<project_name>/tmux/enable`
- **AND** project exists in config.yaml
- **AND** tmux is available
- **THEN** the project's config is updated to include `tmux: true`
- **AND** response is `{"success": true, "message": "tmux enabled for project"}`

#### Scenario: Enable tmux for unknown project

- **WHEN** POST request to `/api/projects/<project_name>/tmux/enable`
- **AND** project does not exist in config.yaml
- **THEN** response is `{"success": false, "error": "Project not found"}`
- **AND** HTTP status is 404

#### Scenario: Enable tmux when already enabled

- **WHEN** POST request to `/api/projects/<project_name>/tmux/enable`
- **AND** project already has `tmux: true`
- **THEN** response is `{"success": true, "message": "tmux already enabled"}`

#### Scenario: Disable tmux for project

- **WHEN** POST request to `/api/projects/<project_name>/tmux/disable`
- **AND** project exists with `tmux: true`
- **THEN** the project's config is updated to remove or set `tmux: false`
- **AND** response is `{"success": true, "message": "tmux disabled for project"}`
