"""Project model with roadmap and context."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RoadmapItem(BaseModel):
    """A single item on the project roadmap."""

    title: str = Field(..., description="Brief title of the roadmap item")
    why: str | None = Field(
        default=None,
        description="Explanation of why this item is important",
    )
    definition_of_done: str | None = Field(
        default=None,
        description="Criteria for considering this item complete",
    )


class Roadmap(BaseModel):
    """Project roadmap with prioritized items and recent progress narrative."""

    next_up: RoadmapItem | None = Field(
        default=None,
        description="Current priority item",
    )
    upcoming: list[str] = Field(
        default_factory=list,
        description="Next items to work on",
    )
    later: list[str] = Field(
        default_factory=list,
        description="Future work",
    )
    not_now: list[str] = Field(
        default_factory=list,
        description="Parked ideas",
    )
    recently_completed: str | None = Field(
        default=None,
        description="LLM-generated narrative from git history",
    )
    recently_completed_at: datetime | None = Field(
        default=None,
        description="When narrative was last generated",
    )


class ProjectContext(BaseModel):
    """Additional context about a project for AI understanding."""

    tech_stack: list[str] = Field(
        default_factory=list,
        description="Technologies used in the project",
    )
    target_users: str | None = Field(
        default=None,
        description="Who the project is for",
    )
    description: str | None = Field(
        default=None,
        description="Brief project description",
    )


class ProjectStatus(str, Enum):
    """Project status values."""

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class ProjectState(BaseModel):
    """Current state of a project."""

    status: ProjectStatus = Field(
        default=ProjectStatus.ACTIVE,
        description="Current project status (active, paused, archived)",
    )
    last_activity_at: datetime | None = Field(
        default=None,
        description="Timestamp of last activity on this project",
    )


class Project(BaseModel):
    """A monitored project with its configuration and state."""

    id: str = Field(..., description="Unique project identifier")
    name: str = Field(..., description="Human-readable project name")
    path: str = Field(..., description="Absolute path to project directory")
    goal: str | None = Field(
        default=None,
        description="Project goal from CLAUDE.md or config",
    )
    context: ProjectContext = Field(
        default_factory=ProjectContext,
        description="Additional project context for AI understanding",
    )
    roadmap: Roadmap = Field(
        default_factory=Roadmap,
        description="Project roadmap with prioritized work items",
    )
    state: ProjectState = Field(
        default_factory=ProjectState,
        description="Current project state and activity tracking",
    )
    git_repo_path: str | None = Field(
        default=None,
        description="Path to git repository (if different from path)",
    )

    def get_git_path(self) -> str:
        """Get the git repository path, defaulting to project path."""
        return self.git_repo_path or self.path
