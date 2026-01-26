"""History compression service for Claude Headspace.

This module handles:
- Compression queue management
- Background compression worker thread
- Session-to-history compression via LLM
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_COMPRESSION_INTERVAL = 300  # 5 minutes

# Retry configuration
RETRY_DELAYS = [60, 300, 1800]  # 1min, 5min, 30min

# Rate limiting
API_CALL_DELAY_SECONDS = 2  # Minimum delay between consecutive API calls


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class CompressionQueueEntry:
    """An entry in the compression queue."""

    session_id: str
    project_name: str
    session_data: dict
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    last_retry_at: Optional[datetime] = None


# =============================================================================
# Compression Service
# =============================================================================

_compression_service: Optional["CompressionService"] = None


class CompressionService:
    """Service for compressing session history via LLM.

    Manages a queue of sessions awaiting compression and processes
    them in the background using the InferenceService.
    """

    def __init__(
        self,
        data_dir: str = "data",
        compression_interval: int = DEFAULT_COMPRESSION_INTERVAL,
    ):
        """Initialize the compression service.

        Args:
            data_dir: Directory for storing compression data
            compression_interval: Seconds between compression cycles
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.compression_interval = compression_interval

        self._queue: dict[str, CompressionQueueEntry] = {}
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Optional callback for when compression completes
        self.on_compression_complete: Optional[Callable[[str, str, dict], None]] = None

    def _get_queue_file(self, project_name: str) -> Path:
        """Get the queue file path for a project."""
        return self.data_dir / "projects" / project_name / "pending_compressions.yaml"

    def _load_queue(self, project_name: str) -> list[dict]:
        """Load the compression queue for a project from disk."""
        queue_file = self._get_queue_file(project_name)
        if not queue_file.exists():
            return []
        try:
            data = yaml.safe_load(queue_file.read_text())
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Failed to load compression queue for {project_name}: {e}")
            return []

    def _save_queue(self, project_name: str, queue: list[dict]) -> bool:
        """Save the compression queue for a project to disk."""
        queue_file = self._get_queue_file(project_name)
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            queue_file.write_text(yaml.dump(queue, default_flow_style=False))
            return True
        except Exception as e:
            logger.warning(f"Failed to save compression queue for {project_name}: {e}")
            return False

    def add_to_queue(self, project_name: str, session_summary: dict) -> bool:
        """Add a session to the compression queue.

        Args:
            project_name: Name of the project
            session_summary: Session summary dict to queue for compression

        Returns:
            True if session was added to queue
        """
        with self._lock:
            queue = self._load_queue(project_name)
            session_id = session_summary.get("session_id")
            if not session_id:
                return False

            # Check if already queued
            if any(s.get("session_id") == session_id for s in queue):
                return True  # Already queued

            # Add to queue with metadata
            queue_entry = {
                **session_summary,
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "retry_count": 0,
            }
            queue.append(queue_entry)

            return self._save_queue(project_name, queue)

    def get_pending(self, project_name: str) -> list[dict]:
        """Get all sessions pending compression for a project.

        Args:
            project_name: Name of the project

        Returns:
            List of session summaries pending compression
        """
        with self._lock:
            return self._load_queue(project_name)

    def remove_from_queue(self, project_name: str, session_id: str) -> bool:
        """Remove a session from the compression queue.

        Args:
            project_name: Name of the project
            session_id: ID of the session to remove

        Returns:
            True if session was removed
        """
        with self._lock:
            queue = self._load_queue(project_name)
            original_count = len(queue)
            queue = [s for s in queue if s.get("session_id") != session_id]

            if len(queue) < original_count:
                return self._save_queue(project_name, queue)
            return True  # Session wasn't in queue

    def _increment_retry_count(self, project_name: str, session_id: str) -> None:
        """Increment the retry count for a queued session."""
        with self._lock:
            queue = self._load_queue(project_name)
            for session in queue:
                if session.get("session_id") == session_id:
                    session["retry_count"] = session.get("retry_count", 0) + 1
                    session["last_retry_at"] = datetime.now(timezone.utc).isoformat()
                    break
            self._save_queue(project_name, queue)

    def _should_retry_now(self, session: dict) -> bool:
        """Check if enough time has passed for retry based on exponential backoff.

        Uses RETRY_DELAYS = [60, 300, 1800] (1min, 5min, 30min) schedule.
        """
        retry_count = session.get("retry_count", 0)
        last_retry_at = session.get("last_retry_at")

        if retry_count == 0 or not last_retry_at:
            return True  # Never retried, try now

        # Get delay for this retry attempt (cap at last entry)
        delay_index = min(retry_count - 1, len(RETRY_DELAYS) - 1)
        required_delay = RETRY_DELAYS[delay_index]

        try:
            last_retry = datetime.fromisoformat(last_retry_at.replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - last_retry).total_seconds()
            return elapsed >= required_delay
        except (ValueError, AttributeError):
            return True  # If we can't parse, try anyway

    def build_compression_prompt(
        self, session_data: dict, existing_history: str = ""
    ) -> list[dict]:
        """Build the prompt for compressing a session into history.

        Args:
            session_data: Session summary dict
            existing_history: Existing history summary to merge with

        Returns:
            List of message dicts for LLM API
        """
        system_prompt = """You are a concise technical writer. Compress session activity into a narrative summary.
Focus on: what was worked on, key decisions, blockers encountered, current status.
Keep it brief but meaningful. Use past tense. No bullet points - write prose."""

        session_info = []
        if session_data.get("started_at"):
            session_info.append(f"Started: {session_data['started_at']}")
        if session_data.get("ended_at"):
            session_info.append(f"Ended: {session_data['ended_at']}")
        if session_data.get("files_modified"):
            files = session_data["files_modified"][:10]  # Limit to 10 files
            session_info.append(f"Files modified: {', '.join(files)}")
        if session_data.get("commands_run"):
            cmds = session_data["commands_run"]
            if isinstance(cmds, int) and cmds > 0:
                session_info.append(f"Commands run: {cmds}")
            elif isinstance(cmds, list):
                session_info.append(f"Commands: {', '.join(cmds[:5])}")
        if session_data.get("errors"):
            errors = session_data["errors"]
            if isinstance(errors, int) and errors > 0:
                session_info.append(f"Errors encountered: {errors}")
            elif isinstance(errors, list):
                session_info.append(f"Errors: {'; '.join(errors[:3])}")
        if session_data.get("summary"):
            session_info.append(f"Session summary: {session_data['summary']}")

        user_content = "Compress this session into the project history:\n\n"
        user_content += "\n".join(session_info)

        if existing_history:
            user_content += f"\n\nExisting history to merge with:\n{existing_history}"
            user_content += (
                "\n\nMerge the new session into the existing history, maintaining narrative flow."
            )
        else:
            user_content += "\n\nThis is the first session - create the initial history narrative."

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    def compress_session(
        self,
        project_name: str,
        session_data: dict,
        inference_service: Optional["InferenceService"] = None,
    ) -> tuple[bool, Optional[str]]:
        """Compress a session and update project history.

        Args:
            project_name: Name of the project
            session_data: Session summary dict to compress
            inference_service: Optional InferenceService for LLM calls

        Returns:
            Tuple of (success, error_message)
        """
        # Get existing history
        history = self._get_project_history(project_name)
        existing_summary = history.get("summary", "")

        # Build prompt
        messages = self.build_compression_prompt(session_data, existing_summary)

        # Call LLM (use InferenceService if provided, otherwise return error)
        if inference_service is None:
            return False, "InferenceService not provided"

        try:
            # Use a simple chat completion
            response = inference_service.call(
                messages=messages,
                model=inference_service.config.compression_model
                if hasattr(inference_service.config, "compression_model")
                else "anthropic/claude-3-haiku-20240307",
            )
            if response is None:
                return False, "Empty response from LLM"

            # Update history with new compressed summary
            if self._update_project_history(project_name, response):
                return True, None
            else:
                return False, "Failed to save history"

        except Exception as e:
            return False, str(e)

    def _get_project_history(self, project_name: str) -> dict:
        """Get the compressed history for a project."""
        history_file = self.data_dir / "projects" / project_name / "history.yaml"
        if not history_file.exists():
            return {"summary": "", "last_compressed_at": None}

        try:
            data = yaml.safe_load(history_file.read_text())
            return {
                "summary": data.get("summary", ""),
                "last_compressed_at": data.get("last_compressed_at"),
            }
        except Exception:
            return {"summary": "", "last_compressed_at": None}

    def _update_project_history(self, project_name: str, summary: str) -> bool:
        """Update the project's compressed history."""
        history_file = self.data_dir / "projects" / project_name / "history.yaml"
        history_file.parent.mkdir(parents=True, exist_ok=True)

        existing = self._get_project_history(project_name)

        history_data = {
            "summary": summary,
            "last_compressed_at": datetime.now(timezone.utc).isoformat(),
            "previous_summary": existing.get("summary"),
            "previous_compressed_at": existing.get("last_compressed_at"),
        }

        try:
            history_file.write_text(yaml.dump(history_data, default_flow_style=False))
            return True
        except Exception as e:
            logger.warning(f"Failed to update project history: {e}")
            return False

    def process_queue(
        self,
        project_name: str,
        inference_service: Optional["InferenceService"] = None,
    ) -> dict:
        """Process all pending compressions for a project.

        Args:
            project_name: Name of the project
            inference_service: InferenceService for LLM calls

        Returns:
            Dict with 'processed', 'failed', 'remaining', 'skipped' counts
        """
        pending = self.get_pending(project_name)
        results = {"processed": 0, "failed": 0, "remaining": 0, "skipped": 0}
        api_call_made = False

        for session in pending:
            session_id = session.get("session_id", "unknown")

            # Check exponential backoff
            if not self._should_retry_now(session):
                results["skipped"] += 1
                continue

            # Rate limit between consecutive API calls
            if api_call_made:
                time.sleep(API_CALL_DELAY_SECONDS)

            success, error = self.compress_session(project_name, session, inference_service)
            api_call_made = True

            if success:
                self.remove_from_queue(project_name, session_id)
                results["processed"] += 1
                logger.info(f"Compressed session {session_id[:8]}... for {project_name}")

                if self.on_compression_complete:
                    self.on_compression_complete(project_name, session_id, session)
            else:
                # Handle retry logic
                if error in ["rate_limited", "timeout"]:
                    self._increment_retry_count(project_name, session_id)
                    results["remaining"] += 1
                    logger.warning(f"Compression retry needed for {session_id[:8]}... ({error})")
                elif error == "authentication_failed":
                    results["failed"] += 1
                    logger.error("OpenRouter authentication failed (check API key)")
                else:
                    self._increment_retry_count(project_name, session_id)
                    results["remaining"] += 1
                    logger.warning(f"Compression failed for {session_id[:8]}... ({error})")

        return results

    # =========================================================================
    # Background Thread Management
    # =========================================================================

    def _worker(self, get_projects_fn: Callable[[], list[str]]) -> None:
        """Background worker that processes compression queues periodically.

        Args:
            get_projects_fn: Function that returns list of project names
        """
        while not self._stop_event.is_set():
            try:
                # Process all projects
                projects = get_projects_fn()
                for project_name in projects:
                    if self._stop_event.is_set():
                        break
                    pending = self.get_pending(project_name)
                    if pending:
                        self.process_queue(project_name)

            except Exception as e:
                logger.warning(f"Compression worker error: {e}")

            # Wait for next cycle (check stop event periodically)
            for _ in range(self.compression_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def start_background_thread(self, get_projects_fn: Callable[[], list[str]]) -> bool:
        """Start the background compression thread.

        Args:
            get_projects_fn: Function that returns list of project names to process

        Returns:
            True if thread was started, False if already running
        """
        if self._thread is not None and self._thread.is_alive():
            return False  # Already running

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, args=(get_projects_fn,), daemon=True)
        self._thread.start()
        logger.info("Background compression thread started")
        return True

    def stop_background_thread(self) -> bool:
        """Stop the background compression thread.

        Returns:
            True if thread was stopped, False if not running
        """
        if self._thread is None or not self._thread.is_alive():
            return False

        self._stop_event.set()
        self._thread.join(timeout=5)
        self._thread = None
        logger.info("Background compression thread stopped")
        return True

    def is_running(self) -> bool:
        """Check if the background thread is running."""
        return self._thread is not None and self._thread.is_alive()


def get_compression_service(
    data_dir: str = "data",
    compression_interval: int = DEFAULT_COMPRESSION_INTERVAL,
) -> CompressionService:
    """Get or create the compression service singleton.

    Args:
        data_dir: Directory for storing compression data
        compression_interval: Seconds between compression cycles

    Returns:
        The CompressionService instance
    """
    global _compression_service
    if _compression_service is None:
        _compression_service = CompressionService(data_dir, compression_interval)
    return _compression_service


def reset_compression_service() -> None:
    """Reset the compression service singleton (for testing)."""
    global _compression_service
    if _compression_service is not None:
        _compression_service.stop_background_thread()
    _compression_service = None
