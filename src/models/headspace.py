"""HeadspaceFocus model - global singleton for user's current focus."""

from datetime import datetime

from pydantic import BaseModel, Field


class HeadspaceHistoryEntry(BaseModel):
    """A previous headspace focus value."""

    focus: str
    constraints: str | None = None
    started_at: datetime
    ended_at: datetime


class HeadspaceFocus(BaseModel):
    """Global singleton representing the user's current focus objective.

    The HeadspaceFocus guides all prioritization decisions across projects,
    ensuring work aligns with the user's primary objective.
    """

    current_focus: str = Field(
        ...,
        description="The user's current primary objective, e.g., 'Ship billing feature by Thursday'",
    )
    constraints: str | None = Field(
        default=None,
        description="Optional constraints on work, e.g., 'No breaking API changes'",
    )
    updated_at: datetime = Field(default_factory=datetime.now)
    history: list[HeadspaceHistoryEntry] = Field(
        default_factory=list,
        description="Previous focus values (max 50)",
    )

    def update_focus(self, new_focus: str, new_constraints: str | None = None) -> None:
        """Update the focus, archiving the current one to history."""
        if self.current_focus:
            # Archive current focus to history
            history_entry = HeadspaceHistoryEntry(
                focus=self.current_focus,
                constraints=self.constraints,
                started_at=self.updated_at,
                ended_at=datetime.now(),
            )
            self.history.insert(0, history_entry)
            # Keep only last 50 entries
            self.history = self.history[:50]

        self.current_focus = new_focus
        self.constraints = new_constraints
        self.updated_at = datetime.now()
