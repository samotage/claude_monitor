"""GitAnalyzer for deriving progress narratives from git history.

Provides git-based context for Claude sessions without storing
sensitive session summaries.
"""

import contextlib
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.models.inference import InferencePurpose
from src.models.project import Project
from src.services.inference_service import InferenceService

logger = logging.getLogger(__name__)


@dataclass
class Commit:
    """A git commit."""

    hash: str
    message: str
    author: str
    timestamp: datetime


@dataclass
class GitActivity:
    """Summary of git activity for a repository."""

    commits: list[Commit]
    files_changed: list[str]
    first_activity: datetime | None
    last_activity: datetime | None
    head_ref: str


class GitAnalyzer:
    """Analyzes git repositories to generate progress narratives.

    Replaces stored session summaries with git-derived content,
    ensuring privacy and accuracy.
    """

    # Cache for generated narratives (project_id:head -> narrative)
    _narrative_cache: dict[str, tuple[str, datetime]]

    def __init__(self, inference_service: InferenceService | None = None):
        """Initialize the GitAnalyzer.

        Args:
            inference_service: Service for LLM calls. Creates one if not provided.
        """
        self._inference = inference_service or InferenceService()
        self._narrative_cache = {}

    def get_head_ref(self, repo_path: str) -> str | None:
        """Get the current HEAD ref for a repository.

        Args:
            repo_path: Path to the git repository.

        Returns:
            HEAD commit hash, or None if not a git repo.
        """
        result = self._run_git(repo_path, ["rev-parse", "HEAD"])
        if result is None:
            return None
        return result.strip()

    def get_recent_commits(self, repo_path: str, count: int = 20) -> list[Commit]:
        """Get recent commits from a repository.

        Args:
            repo_path: Path to the git repository.
            count: Maximum number of commits to retrieve.

        Returns:
            List of Commit objects, most recent first.
        """
        # Format: hash|message|author|timestamp
        format_str = "%H|%s|%an|%aI"
        result = self._run_git(
            repo_path,
            ["log", f"--format={format_str}", f"-n{count}"],
        )

        if result is None:
            return []

        commits = []
        for line in result.strip().split("\n"):
            if not line:
                continue

            parts = line.split("|", 3)
            if len(parts) < 4:
                continue

            hash_val, message, author, timestamp_str = parts
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.now()

            commits.append(
                Commit(
                    hash=hash_val,
                    message=message,
                    author=author,
                    timestamp=timestamp,
                )
            )

        return commits

    def get_files_changed(self, repo_path: str, since: str = "7 days ago") -> list[str]:
        """Get files changed since a given time.

        Args:
            repo_path: Path to the git repository.
            since: Git time specification (e.g., "7 days ago", "HEAD~10").

        Returns:
            List of file paths that were changed.
        """
        result = self._run_git(
            repo_path,
            ["log", f"--since={since}", "--name-only", "--format="],
        )

        if result is None:
            return []

        # Deduplicate and filter empty lines
        files = set()
        for line in result.strip().split("\n"):
            if line.strip():
                files.add(line.strip())

        return sorted(files)

    def get_activity_timeframe(
        self, repo_path: str, since: str = "7 days ago"
    ) -> tuple[datetime | None, datetime | None]:
        """Get the first and last activity timestamps.

        Args:
            repo_path: Path to the git repository.
            since: Git time specification for lookback window.

        Returns:
            Tuple of (first_activity, last_activity) datetimes.
        """
        # Get oldest commit in timeframe
        oldest = self._run_git(
            repo_path,
            ["log", f"--since={since}", "--format=%aI", "--reverse"],
        )

        # Get newest commit
        newest = self._run_git(
            repo_path,
            ["log", "-1", "--format=%aI"],
        )

        first_activity = None
        last_activity = None

        if oldest:
            lines = oldest.strip().split("\n")
            if lines and lines[0]:
                with contextlib.suppress(ValueError):
                    first_activity = datetime.fromisoformat(lines[0].strip().replace("Z", "+00:00"))

        if newest:
            with contextlib.suppress(ValueError):
                last_activity = datetime.fromisoformat(newest.strip().replace("Z", "+00:00"))

        return first_activity, last_activity

    def get_activity(self, repo_path: str, since: str = "7 days ago") -> GitActivity:
        """Get comprehensive git activity for a repository.

        Args:
            repo_path: Path to the git repository.
            since: Git time specification for lookback window.

        Returns:
            GitActivity summary.
        """
        head_ref = self.get_head_ref(repo_path) or ""
        commits = self.get_recent_commits(repo_path, count=20)
        files = self.get_files_changed(repo_path, since)
        first, last = self.get_activity_timeframe(repo_path, since)

        return GitActivity(
            commits=commits,
            files_changed=files,
            first_activity=first,
            last_activity=last,
            head_ref=head_ref,
        )

    def generate_progress_narrative(
        self,
        project: Project,
        use_cache: bool = True,
    ) -> str:
        """Generate a human-readable progress narrative for a project.

        Uses LLM to transform git activity into a readable summary.

        Args:
            project: The project to generate narrative for.
            use_cache: Whether to use cached narratives.

        Returns:
            Human-readable progress narrative.
        """
        if not project.path:
            return "No project path configured."

        # Get git activity
        activity = self.get_activity(project.path)
        if not activity.commits:
            return "No recent git activity found."

        # Check cache
        cache_key = f"{project.id}:{activity.head_ref}"
        if use_cache and cache_key in self._narrative_cache:
            cached_narrative, cached_time = self._narrative_cache[cache_key]
            # Cache valid for 24 hours
            if (datetime.now() - cached_time).total_seconds() < 86400:
                return cached_narrative

        # Build context for LLM
        commit_summaries = [
            f"- {c.message} ({c.author}, {c.timestamp.strftime('%Y-%m-%d')})"
            for c in activity.commits[:10]
        ]

        file_summary = (
            f"Changed files: {', '.join(activity.files_changed[:20])}"
            if activity.files_changed
            else "No file changes recorded."
        )

        timeframe = ""
        if activity.first_activity and activity.last_activity:
            timeframe = (
                f"Activity from {activity.first_activity.strftime('%Y-%m-%d')} "
                f"to {activity.last_activity.strftime('%Y-%m-%d')}"
            )

        # Call LLM for narrative generation
        result = self._inference.call(
            purpose=InferencePurpose.GENERATE_PROGRESS_NARRATIVE,
            input_data={
                "project_name": project.name,
                "commits": commit_summaries,
                "files_changed": file_summary,
                "timeframe": timeframe,
            },
            user_prompt=(
                f"Summarize recent work on '{project.name}' based on this git activity. "
                f"Write 2-3 sentences describing what was accomplished.\n\n"
                f"Recent commits:\n{chr(10).join(commit_summaries)}\n\n"
                f"{file_summary}\n\n"
                f"{timeframe}"
            ),
            project_id=project.id,
            use_cache=use_cache,
        )

        # Extract narrative from result
        if "error" in result.result:
            narrative = f"Recent work on {project.name}: {len(activity.commits)} commits."
        else:
            narrative = result.result.get(
                "content", result.result.get("narrative", str(result.result))
            )

        # Cache the result
        self._narrative_cache[cache_key] = (narrative, datetime.now())

        return narrative

    def invalidate_cache(self, project_id: str | None = None) -> int:
        """Invalidate cached narratives.

        Args:
            project_id: If provided, only invalidate for this project.

        Returns:
            Number of entries invalidated.
        """
        if project_id is None:
            count = len(self._narrative_cache)
            self._narrative_cache.clear()
            return count

        to_remove = [key for key in self._narrative_cache if key.startswith(f"{project_id}:")]
        for key in to_remove:
            del self._narrative_cache[key]

        return len(to_remove)

    def _run_git(self, repo_path: str, args: list[str]) -> str | None:
        """Run a git command in the specified directory.

        Args:
            repo_path: Path to run git in.
            args: Git command arguments.

        Returns:
            Command output, or None on error.
        """
        path = Path(repo_path)
        if not path.exists():
            return None

        try:
            result = subprocess.run(
                ["git", "-C", str(path), *args],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return None
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.debug(f"Git command failed: {e}")
            return None
