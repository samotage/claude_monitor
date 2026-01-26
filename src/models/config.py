"""Application configuration models with Pydantic validation."""


from pydantic import BaseModel, Field

from src.models.inference import InferenceConfig


class ProjectConfig(BaseModel):
    """Configuration for a single monitored project."""

    name: str = Field(..., description="Project name (used as identifier)")
    path: str = Field(..., description="Absolute path to project directory")
    goal: str | None = Field(
        default=None,
        description="Project goal (overrides CLAUDE.md)",
    )
    git_repo_path: str | None = Field(
        default=None,
        description="Path to git repo (if different from path)",
    )


class WezTermConfig(BaseModel):
    """WezTerm-specific configuration."""

    workspace: str = Field(
        default="claude-monitor",
        description="WezTerm workspace for grouping sessions",
    )
    full_scrollback: bool = Field(
        default=True,
        description="Enable full scrollback capture",
    )
    max_cache_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum session cache entries before LRU eviction",
    )
    max_lines: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum lines to capture from terminal scrollback",
    )


class NotificationConfig(BaseModel):
    """Notification configuration."""

    enabled: bool = Field(
        default=True,
        description="Whether notifications are enabled",
    )
    on_awaiting_input: bool = Field(
        default=True,
        description="Notify when agent needs input",
    )
    on_complete: bool = Field(
        default=True,
        description="Notify when task completes",
    )


class HookConfig(BaseModel):
    """Claude Code hooks configuration.

    Hooks provide event-driven state detection from Claude Code sessions,
    offering instant, certain state updates vs. polling-based inference.
    """

    enabled: bool = Field(
        default=True,
        description="Whether to accept Claude Code hook events",
    )
    fallback_polling: bool = Field(
        default=True,
        description="Continue polling as a fallback when hooks are enabled",
    )
    polling_interval_with_hooks: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Polling interval in seconds when hooks are active (reduced from normal)",
    )
    session_timeout: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Seconds without hook events before falling back to normal polling",
    )


class ApiLimitsConfig(BaseModel):
    """API rate limiting and bounds configuration."""

    max_history_limit: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum entries for history endpoints",
    )
    rate_limit_requests: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum requests per rate limit window",
    )
    rate_limit_window: int = Field(
        default=60,
        ge=10,
        le=600,
        description="Rate limit window in seconds",
    )


class TerminalLoggingConfig(BaseModel):
    """Terminal session logging configuration.

    Controls debug logging for terminal operations (send_keys, capture_pane).
    When debug is disabled, payloads are not recorded to conserve space.
    """

    debug_enabled: bool = Field(
        default=False,
        description="Enable debug logging with payload content",
    )
    max_payload_size: int = Field(
        default=10 * 1024,  # 10KB
        ge=1024,
        le=1024 * 1024,  # 1MB max
        description="Maximum payload size before truncation (bytes)",
    )
    max_log_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Rotate log when file exceeds this size (MB)",
    )
    max_log_files: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of rotated log files to keep",
    )


class HeadspaceConfig(BaseModel):
    """Headspace feature configuration."""

    enabled: bool = Field(
        default=True,
        description="Whether headspace features are enabled",
    )
    history_enabled: bool = Field(
        default=True,
        description="Whether to track headspace history",
    )


class SessionSyncConfig(BaseModel):
    """Session synchronization configuration.

    Controls background sync of session state with JSONL logs.
    """

    enabled: bool = Field(
        default=True,
        description="Whether session sync is enabled",
    )
    interval: int = Field(
        default=60,
        ge=10,
        le=600,
        description="Sync interval in seconds",
    )
    jsonl_tail_entries: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Number of JSONL tail entries to read for sync",
    )


class PrioritiesConfig(BaseModel):
    """AI-driven priorities configuration."""

    enabled: bool = Field(
        default=True,
        description="Whether AI priority computation is enabled",
    )


class AppConfig(BaseModel):
    """Root application configuration.

    Loaded from config.yaml and validated with Pydantic.
    """

    projects: list[ProjectConfig] = Field(
        default_factory=list,
        description="List of monitored projects",
    )
    scan_interval: int = Field(
        default=2,
        ge=1,
        le=60,
        description="Interval in seconds between state detection polls",
    )
    terminal_backend: str = Field(
        default="wezterm",
        pattern="^(wezterm|tmux)$",
        description="Terminal backend to use (wezterm recommended, tmux deprecated)",
    )
    wezterm: WezTermConfig = Field(
        default_factory=WezTermConfig,
        description="WezTerm-specific settings",
    )
    inference: InferenceConfig = Field(
        default_factory=InferenceConfig,
        description="Per-purpose model configuration",
    )
    notifications: NotificationConfig = Field(
        default_factory=NotificationConfig,
        description="Notification settings",
    )
    hooks: HookConfig = Field(
        default_factory=HookConfig,
        description="Claude Code hooks configuration for event-driven state detection",
    )
    api_limits: ApiLimitsConfig = Field(
        default_factory=ApiLimitsConfig,
        description="API rate limiting and bounds configuration",
    )
    terminal_logging: TerminalLoggingConfig = Field(
        default_factory=TerminalLoggingConfig,
        description="Terminal session logging configuration",
    )
    headspace: HeadspaceConfig = Field(
        default_factory=HeadspaceConfig,
        description="Headspace feature configuration",
    )
    session_sync: SessionSyncConfig = Field(
        default_factory=SessionSyncConfig,
        description="Session synchronization configuration",
    )
    priorities: PrioritiesConfig = Field(
        default_factory=PrioritiesConfig,
        description="AI-driven priorities configuration",
    )
    idle_timeout_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,
        description="Minutes of inactivity before marking agent idle",
    )
    stale_threshold_hours: int = Field(
        default=4,
        ge=1,
        le=168,
        description="Hours before marking project data as stale",
    )
    port: int = Field(
        default=5050,
        ge=1024,
        le=65535,
        description="Port for the Flask server",
    )
    debug: bool = Field(
        default=False,
        description="Enable Flask debug mode",
    )
