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
