"""Tests for GitAnalyzer."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.models.project import Project
from src.services.git_analyzer import Commit, GitActivity, GitAnalyzer


@pytest.fixture
def mock_inference():
    """Create a mock InferenceService."""
    service = MagicMock()
    service.call.return_value = MagicMock(
        result={"content": "Recent work includes bug fixes and feature additions."}
    )
    return service


@pytest.fixture
def analyzer(mock_inference):
    """Create a GitAnalyzer with mocked inference."""
    return GitAnalyzer(inference_service=mock_inference)


@pytest.fixture
def sample_project():
    """Create a sample project."""
    return Project(
        id="proj-1",
        name="Test Project",
        path="/path/to/project",
    )


class TestGetHeadRef:
    """Tests for get_head_ref method."""

    @patch.object(GitAnalyzer, "_run_git")
    def test_returns_head_hash(self, mock_run, analyzer):
        """get_head_ref returns the HEAD commit hash."""
        mock_run.return_value = "abc123def456\n"

        result = analyzer.get_head_ref("/path/to/repo")

        assert result == "abc123def456"
        mock_run.assert_called_once_with("/path/to/repo", ["rev-parse", "HEAD"])

    @patch.object(GitAnalyzer, "_run_git")
    def test_returns_none_on_error(self, mock_run, analyzer):
        """get_head_ref returns None on error."""
        mock_run.return_value = None

        result = analyzer.get_head_ref("/path/to/repo")

        assert result is None


class TestGetRecentCommits:
    """Tests for get_recent_commits method."""

    @patch.object(GitAnalyzer, "_run_git")
    def test_parses_commits(self, mock_run, analyzer):
        """get_recent_commits parses git log output."""
        mock_run.return_value = (
            "abc123|Fix bug in login|John Doe|2024-01-15T10:30:00+00:00\n"
            "def456|Add new feature|Jane Smith|2024-01-14T15:45:00+00:00\n"
        )

        commits = analyzer.get_recent_commits("/path/to/repo", count=10)

        assert len(commits) == 2
        assert commits[0].hash == "abc123"
        assert commits[0].message == "Fix bug in login"
        assert commits[0].author == "John Doe"
        assert commits[1].hash == "def456"
        assert commits[1].message == "Add new feature"

    @patch.object(GitAnalyzer, "_run_git")
    def test_empty_on_error(self, mock_run, analyzer):
        """get_recent_commits returns empty list on error."""
        mock_run.return_value = None

        commits = analyzer.get_recent_commits("/path/to/repo")

        assert commits == []

    @patch.object(GitAnalyzer, "_run_git")
    def test_handles_empty_output(self, mock_run, analyzer):
        """get_recent_commits handles empty git output."""
        mock_run.return_value = ""

        commits = analyzer.get_recent_commits("/path/to/repo")

        assert commits == []


class TestGetFilesChanged:
    """Tests for get_files_changed method."""

    @patch.object(GitAnalyzer, "_run_git")
    def test_returns_file_list(self, mock_run, analyzer):
        """get_files_changed returns list of changed files."""
        mock_run.return_value = (
            "src/main.py\n"
            "tests/test_main.py\n"
            "src/main.py\n"  # Duplicate
            "README.md\n"
        )

        files = analyzer.get_files_changed("/path/to/repo", since="7 days ago")

        assert len(files) == 3  # Duplicates removed
        assert "src/main.py" in files
        assert "tests/test_main.py" in files
        assert "README.md" in files

    @patch.object(GitAnalyzer, "_run_git")
    def test_empty_on_error(self, mock_run, analyzer):
        """get_files_changed returns empty list on error."""
        mock_run.return_value = None

        files = analyzer.get_files_changed("/path/to/repo")

        assert files == []


class TestGetActivityTimeframe:
    """Tests for get_activity_timeframe method."""

    @patch.object(GitAnalyzer, "_run_git")
    def test_returns_timeframe(self, mock_run, analyzer):
        """get_activity_timeframe returns first and last activity."""
        mock_run.side_effect = [
            "2024-01-10T10:00:00+00:00\n2024-01-11T10:00:00+00:00\n",  # oldest
            "2024-01-15T15:30:00+00:00\n",  # newest
        ]

        first, last = analyzer.get_activity_timeframe("/path/to/repo")

        assert first is not None
        assert last is not None
        assert first < last

    @patch.object(GitAnalyzer, "_run_git")
    def test_none_on_error(self, mock_run, analyzer):
        """get_activity_timeframe returns None on error."""
        mock_run.return_value = None

        first, last = analyzer.get_activity_timeframe("/path/to/repo")

        assert first is None
        assert last is None


class TestGetActivity:
    """Tests for get_activity method."""

    @patch.object(GitAnalyzer, "_run_git")
    def test_returns_complete_activity(self, mock_run, analyzer):
        """get_activity returns comprehensive GitActivity."""
        mock_run.side_effect = [
            "abc123\n",  # HEAD
            "abc123|Fix bug|John|2024-01-15T10:00:00+00:00\n",  # commits
            "src/main.py\n",  # files
            "2024-01-10T10:00:00+00:00\n",  # first activity
            "2024-01-15T10:00:00+00:00\n",  # last activity
        ]

        activity = analyzer.get_activity("/path/to/repo")

        assert activity.head_ref == "abc123"
        assert len(activity.commits) == 1
        assert len(activity.files_changed) == 1


class TestGenerateProgressNarrative:
    """Tests for generate_progress_narrative method."""

    @patch.object(GitAnalyzer, "get_activity")
    def test_generates_narrative(self, mock_activity, analyzer, sample_project, mock_inference):
        """generate_progress_narrative generates human-readable summary."""
        mock_activity.return_value = GitActivity(
            commits=[
                Commit(
                    hash="abc123",
                    message="Add login feature",
                    author="John Doe",
                    timestamp=datetime.now(),
                )
            ],
            files_changed=["src/login.py"],
            first_activity=datetime.now() - timedelta(days=7),
            last_activity=datetime.now(),
            head_ref="abc123",
        )

        narrative = analyzer.generate_progress_narrative(sample_project)

        # Verify inference was called
        mock_inference.call.assert_called_once()
        assert "Recent work" in narrative or "bug fixes" in narrative

    @patch.object(GitAnalyzer, "get_activity")
    def test_returns_fallback_on_no_commits(self, mock_activity, analyzer, sample_project):
        """generate_progress_narrative returns fallback when no commits."""
        mock_activity.return_value = GitActivity(
            commits=[],
            files_changed=[],
            first_activity=None,
            last_activity=None,
            head_ref="",
        )

        narrative = analyzer.generate_progress_narrative(sample_project)

        assert "No recent git activity" in narrative

    def test_returns_error_on_no_path(self, analyzer):
        """generate_progress_narrative returns error when no project path."""
        project = Project(id="proj-1", name="Test", path="")  # Empty path

        narrative = analyzer.generate_progress_narrative(project)

        assert "No project path" in narrative

    @patch.object(GitAnalyzer, "get_activity")
    def test_uses_cache(self, mock_activity, analyzer, sample_project, mock_inference):
        """generate_progress_narrative uses cached narratives."""
        mock_activity.return_value = GitActivity(
            commits=[
                Commit(
                    hash="abc123",
                    message="Fix",
                    author="John",
                    timestamp=datetime.now(),
                )
            ],
            files_changed=[],
            first_activity=None,
            last_activity=None,
            head_ref="abc123",
        )

        # First call
        analyzer.generate_progress_narrative(sample_project)
        # Second call
        analyzer.generate_progress_narrative(sample_project)

        # Inference should only be called once (second call uses cache)
        assert mock_inference.call.call_count == 1

    @patch.object(GitAnalyzer, "get_activity")
    def test_bypasses_cache_when_disabled(
        self, mock_activity, analyzer, sample_project, mock_inference
    ):
        """generate_progress_narrative bypasses cache when use_cache=False."""
        mock_activity.return_value = GitActivity(
            commits=[
                Commit(
                    hash="abc123",
                    message="Fix",
                    author="John",
                    timestamp=datetime.now(),
                )
            ],
            files_changed=[],
            first_activity=None,
            last_activity=None,
            head_ref="abc123",
        )

        # First call
        analyzer.generate_progress_narrative(sample_project)
        # Second call with cache disabled
        analyzer.generate_progress_narrative(sample_project, use_cache=False)

        # Inference should be called twice
        assert mock_inference.call.call_count == 2


class TestInvalidateCache:
    """Tests for invalidate_cache method."""

    @patch.object(GitAnalyzer, "get_activity")
    def test_invalidate_all(self, mock_activity, analyzer, sample_project):
        """invalidate_cache clears all cached narratives."""
        mock_activity.return_value = GitActivity(
            commits=[Commit(hash="abc", message="Fix", author="J", timestamp=datetime.now())],
            files_changed=[],
            first_activity=None,
            last_activity=None,
            head_ref="abc",
        )

        # Generate a narrative to populate cache
        analyzer.generate_progress_narrative(sample_project)
        assert len(analyzer._narrative_cache) == 1

        # Invalidate
        count = analyzer.invalidate_cache()

        assert count == 1
        assert len(analyzer._narrative_cache) == 0

    @patch.object(GitAnalyzer, "get_activity")
    def test_invalidate_by_project(self, mock_activity, analyzer):
        """invalidate_cache can filter by project."""
        mock_activity.return_value = GitActivity(
            commits=[Commit(hash="abc", message="Fix", author="J", timestamp=datetime.now())],
            files_changed=[],
            first_activity=None,
            last_activity=None,
            head_ref="abc",
        )

        proj1 = Project(id="proj-1", name="Project 1", path="/path/1")
        proj2 = Project(id="proj-2", name="Project 2", path="/path/2")

        # Generate narratives for both
        analyzer.generate_progress_narrative(proj1)
        analyzer.generate_progress_narrative(proj2)
        assert len(analyzer._narrative_cache) == 2

        # Invalidate only proj-1
        count = analyzer.invalidate_cache(project_id="proj-1")

        assert count == 1
        assert len(analyzer._narrative_cache) == 1


class TestRunGit:
    """Tests for _run_git method."""

    def test_returns_none_for_nonexistent_path(self, analyzer):
        """_run_git returns None for nonexistent path."""
        result = analyzer._run_git("/nonexistent/path", ["status"])

        assert result is None

    @patch("src.services.git_analyzer.subprocess.run")
    def test_returns_output(self, mock_subprocess, analyzer):
        """_run_git returns command output."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="output here",
        )

        with patch("src.services.git_analyzer.Path.exists", return_value=True):
            result = analyzer._run_git("/path/to/repo", ["log"])

        assert result == "output here"

    @patch("src.services.git_analyzer.subprocess.run")
    def test_returns_none_on_error(self, mock_subprocess, analyzer):
        """_run_git returns None on git error."""
        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stdout="",
        )

        with patch("src.services.git_analyzer.Path.exists", return_value=True):
            result = analyzer._run_git("/path/to/repo", ["status"])

        assert result is None

    @patch("src.services.git_analyzer.subprocess.run")
    def test_handles_timeout(self, mock_subprocess, analyzer):
        """_run_git handles subprocess timeout."""
        import subprocess

        mock_subprocess.side_effect = subprocess.TimeoutExpired("git", 30)

        with patch("src.services.git_analyzer.Path.exists", return_value=True):
            result = analyzer._run_git("/path/to/repo", ["log"])

        assert result is None


class TestCommit:
    """Tests for Commit dataclass."""

    def test_create_commit(self):
        """Commit can be created with required fields."""
        commit = Commit(
            hash="abc123",
            message="Fix bug",
            author="John Doe",
            timestamp=datetime.now(),
        )

        assert commit.hash == "abc123"
        assert commit.message == "Fix bug"


class TestGitActivity:
    """Tests for GitActivity dataclass."""

    def test_create_activity(self):
        """GitActivity can be created with required fields."""
        activity = GitActivity(
            commits=[],
            files_changed=[],
            first_activity=None,
            last_activity=None,
            head_ref="abc123",
        )

        assert activity.head_ref == "abc123"
        assert len(activity.commits) == 0
