"""Session state synchronization service for Claude Headspace.

This module handles:
- Background thread for periodic session state sync
- Live session context extraction from JSONL logs
- Session end detection and summarization triggering
- Session state persistence across server restarts

Note: In the new architecture, much of this functionality is handled by
GoverningAgent (polling) and HookReceiver (lifecycle events). This service
provides supplementary JSONL-based context extraction.
"""

import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from src.services.summarization_service import (
    find_most_recent_log_file,
    parse_jsonl_line,
)

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_SYNC_INTERVAL = 60  # seconds
DEFAULT_JSONL_TAIL_ENTRIES = 20

# Path to persist session state across restarts
SESSION_STATE_FILE = Path("data") / "session_state.yaml"


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class LiveContext:
    """Context extracted from recent JSONL entries for display."""

    recent_files: list[str] = field(default_factory=list)
    recent_commands: list[str] = field(default_factory=list)
    current_task: str = ""
    tool_in_progress: Optional[str] = None
    last_activity: Optional[datetime] = None


@dataclass
class KnownSession:
    """Tracked session state for detecting lifecycle events."""

    uuid: str
    project_name: str
    project_path: str
    pid: int
    first_seen: datetime
    last_seen: datetime
    last_jsonl_position: int = 0
    last_jsonl_mtime: float = 0.0
    activity_snapshot: Optional[LiveContext] = None


# =============================================================================
# Session Sync Service
# =============================================================================

_session_sync_service: Optional["SessionSyncService"] = None


class SessionSyncService:
    """Service for synchronizing session state with JSONL logs.

    Provides live context extraction from Claude Code session logs
    and session lifecycle detection.
    """

    def __init__(
        self,
        data_dir: str = "data",
        sync_interval: int = DEFAULT_SYNC_INTERVAL,
        jsonl_tail_entries: int = DEFAULT_JSONL_TAIL_ENTRIES,
    ):
        """Initialize the session sync service.

        Args:
            data_dir: Directory for storing state data
            sync_interval: Seconds between sync cycles
            jsonl_tail_entries: Number of JSONL entries to read per sync
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.sync_interval = sync_interval
        self.jsonl_tail_entries = jsonl_tail_entries

        self._known_sessions: dict[str, KnownSession] = {}
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Callbacks
        self.on_session_end: Optional[Callable[[KnownSession], None]] = None
        self.on_new_session: Optional[Callable[[KnownSession], None]] = None

        # Load persisted state
        self._load_known_sessions()

    # =========================================================================
    # Session State Persistence
    # =========================================================================

    def _is_process_alive(self, pid: int) -> bool:
        """Check if a process with given PID is still running."""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # Process exists but we can't signal it

    def _save_known_sessions(self) -> None:
        """Persist known sessions to disk."""
        with self._lock:
            if not self._known_sessions:
                state_file = self.data_dir / "session_state.yaml"
                if state_file.exists():
                    try:
                        state_file.unlink()
                    except Exception:
                        pass
                return

            state_file = self.data_dir / "session_state.yaml"
            state_file.parent.mkdir(parents=True, exist_ok=True)

            data = {}
            for uuid, ks in self._known_sessions.items():
                data[uuid] = {
                    "uuid": ks.uuid,
                    "project_name": ks.project_name,
                    "project_path": ks.project_path,
                    "pid": ks.pid,
                    "first_seen": ks.first_seen.isoformat(),
                    "last_seen": ks.last_seen.isoformat(),
                }

            try:
                state_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
            except Exception as e:
                logger.warning(f"Failed to save session state: {e}")

    def _load_known_sessions(self) -> None:
        """Load known sessions from disk on startup."""
        state_file = self.data_dir / "session_state.yaml"
        if not state_file.exists():
            return

        try:
            data = yaml.safe_load(state_file.read_text())
            if not data:
                return

            loaded_count = 0
            cleaned_count = 0

            with self._lock:
                for uuid, session_data in data.items():
                    pid = session_data.get("pid", 0)

                    # Skip sessions with dead PIDs
                    if not self._is_process_alive(pid):
                        cleaned_count += 1
                        continue

                    try:
                        first_seen = datetime.fromisoformat(session_data["first_seen"])
                        last_seen = datetime.fromisoformat(session_data["last_seen"])

                        self._known_sessions[uuid] = KnownSession(
                            uuid=session_data["uuid"],
                            project_name=session_data["project_name"],
                            project_path=session_data["project_path"],
                            pid=pid,
                            first_seen=first_seen,
                            last_seen=last_seen,
                        )
                        loaded_count += 1
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Invalid session state entry {uuid}: {e}")
                        continue

            if loaded_count > 0:
                logger.info(f"Restored {loaded_count} sessions from previous run")
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} stale sessions")

        except Exception as e:
            logger.warning(f"Failed to load session state: {e}")

    # =========================================================================
    # JSONL Reading
    # =========================================================================

    def read_jsonl_tail(
        self, log_file: Path, last_position: int = 0, max_entries: int = 20
    ) -> tuple[list[dict], int]:
        """Read recent entries from JSONL file without loading entire file.

        Args:
            log_file: Path to JSONL file
            last_position: Last read position in file
            max_entries: Maximum entries to return

        Returns:
            Tuple of (list of parsed entries, new file position)
        """
        try:
            file_size = log_file.stat().st_size

            if file_size <= last_position:
                return [], last_position

            with open(log_file, encoding="utf-8") as f:
                f.seek(last_position)
                entries = []
                for line in f:
                    parsed = parse_jsonl_line(line)
                    if parsed:
                        entries.append(parsed)
                new_position = f.tell()

            return entries[-max_entries:], new_position

        except Exception as e:
            logger.warning(f"Error reading JSONL tail: {e}")
            return [], last_position

    # =========================================================================
    # Live Context Extraction
    # =========================================================================

    def extract_live_context(
        self, entries: list[dict], max_files: int = 5, max_activity: int = 3
    ) -> LiveContext:
        """Extract displayable context from recent JSONL entries.

        Args:
            entries: Recent JSONL entries (newest last)
            max_files: Max files to track
            max_activity: Max activity summaries to track

        Returns:
            LiveContext with recent activity
        """
        files = set()
        recent_activity = []
        current_task = ""
        last_activity = None

        for entry in entries:
            # Track timestamp
            if "timestamp" in entry:
                try:
                    last_activity = datetime.fromisoformat(
                        entry["timestamp"].replace("Z", "+00:00")
                    )
                except Exception:
                    pass

            # Extract from assistant messages
            if entry.get("type") == "assistant" and "message" in entry:
                message = entry.get("message", {})
                content = message.get("content", [])

                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_name = block.get("name", "")
                            tool_input = block.get("input", {})

                            # Track files
                            if tool_name in ("Edit", "Write", "Read"):
                                file_path = tool_input.get("file_path")
                                if file_path:
                                    files.add(Path(file_path).name)

                        # Extract text content as activity summary
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text and len(text) > 20:
                                first_line = text.split("\n")[0].strip()
                                if 15 < len(first_line) < 150:
                                    if first_line not in recent_activity:
                                        recent_activity.append(first_line)

            # Extract user messages for task context
            if entry.get("type") == "user" and "message" in entry:
                msg = entry.get("message", {})
                msg_content = msg.get("content")
                if isinstance(msg_content, str) and msg_content:
                    if not msg_content.startswith("{") and len(msg_content) > 10:
                        current_task = msg_content[:100]

        return LiveContext(
            recent_files=list(files)[:max_files],
            recent_commands=recent_activity[-max_activity:],
            current_task=current_task,
            tool_in_progress=None,
            last_activity=last_activity,
        )

    # =========================================================================
    # Session Lifecycle
    # =========================================================================

    def register_session(
        self,
        uuid: str,
        project_name: str,
        project_path: str,
        pid: int,
    ) -> KnownSession:
        """Register a new known session.

        Args:
            uuid: Session UUID
            project_name: Project name
            project_path: Project directory path
            pid: Process ID

        Returns:
            The created KnownSession
        """
        now = datetime.now(timezone.utc)
        session = KnownSession(
            uuid=uuid,
            project_name=project_name,
            project_path=project_path,
            pid=pid,
            first_seen=now,
            last_seen=now,
        )

        with self._lock:
            self._known_sessions[uuid] = session
            self._save_known_sessions()

        if self.on_new_session:
            self.on_new_session(session)

        logger.info(f"New session detected: {uuid[:8]}... for {project_name}")
        return session

    def update_session_context(self, uuid: str) -> Optional[LiveContext]:
        """Update a session's live context from its JSONL log.

        Args:
            uuid: Session UUID

        Returns:
            Updated LiveContext or None if session not found
        """
        with self._lock:
            session = self._known_sessions.get(uuid)
            if not session:
                return None

            # Find the most recent JSONL log file
            log_file = find_most_recent_log_file(session.project_path)
            if not log_file:
                return None

            # Check if file has changed
            try:
                mtime = log_file.stat().st_mtime
                if mtime == session.last_jsonl_mtime:
                    return session.activity_snapshot
                session.last_jsonl_mtime = mtime
            except Exception:
                return None

            # Read recent entries
            entries, new_position = self.read_jsonl_tail(
                log_file, session.last_jsonl_position, self.jsonl_tail_entries
            )
            session.last_jsonl_position = new_position

            if entries:
                session.activity_snapshot = self.extract_live_context(entries)
                session.last_seen = datetime.now(timezone.utc)

            return session.activity_snapshot

    def mark_session_ended(self, uuid: str) -> Optional[KnownSession]:
        """Mark a session as ended and remove from tracking.

        Args:
            uuid: Session UUID

        Returns:
            The removed KnownSession or None if not found
        """
        with self._lock:
            session = self._known_sessions.pop(uuid, None)
            if session:
                self._save_known_sessions()
                if self.on_session_end:
                    self.on_session_end(session)
                logger.info(f"Session {uuid[:8]}... ended for {session.project_name}")
            return session

    def get_known_sessions(self) -> dict[str, KnownSession]:
        """Get a copy of all known sessions."""
        with self._lock:
            return self._known_sessions.copy()

    def get_session_context(self, uuid: str) -> Optional[LiveContext]:
        """Get the current live context for a session.

        Args:
            uuid: Session UUID

        Returns:
            LiveContext or None if session not found
        """
        with self._lock:
            session = self._known_sessions.get(uuid)
            return session.activity_snapshot if session else None

    # =========================================================================
    # Background Thread
    # =========================================================================

    def _perform_sync_cycle(self, get_active_sessions_fn: Callable[[], list[dict]]) -> None:
        """Perform one sync cycle.

        Args:
            get_active_sessions_fn: Function that returns list of active sessions
        """
        try:
            # Get current active sessions
            current_sessions = get_active_sessions_fn()
            current_uuids = {s.get("uuid", s.get("id", "")) for s in current_sessions}

            with self._lock:
                # Detect ended sessions
                ended_uuids = set(self._known_sessions.keys()) - current_uuids
                for uuid in ended_uuids:
                    self.mark_session_ended(uuid)

                # Update context for active sessions
                for session in current_sessions:
                    uuid = session.get("uuid", session.get("id", ""))
                    if uuid and uuid in self._known_sessions:
                        self.update_session_context(uuid)

        except Exception as e:
            logger.warning(f"Session sync error: {e}")

    def _worker(self, get_active_sessions_fn: Callable[[], list[dict]]) -> None:
        """Background worker that syncs session state periodically.

        Args:
            get_active_sessions_fn: Function that returns list of active sessions
        """
        while not self._stop_event.is_set():
            self._perform_sync_cycle(get_active_sessions_fn)

            # Wait for next cycle (check stop event every second)
            for _ in range(self.sync_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def start_background_thread(self, get_active_sessions_fn: Callable[[], list[dict]]) -> bool:
        """Start the background session sync thread.

        Args:
            get_active_sessions_fn: Function that returns list of active sessions

        Returns:
            True if thread was started, False if already running
        """
        if self._thread is not None and self._thread.is_alive():
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker, args=(get_active_sessions_fn,), daemon=True
        )
        self._thread.start()
        logger.info("Session sync thread started")
        return True

    def stop_background_thread(self) -> bool:
        """Stop the background session sync thread.

        Returns:
            True if thread was stopped, False if not running
        """
        if self._thread is None or not self._thread.is_alive():
            return False

        self._stop_event.set()
        self._thread.join(timeout=5)
        self._thread = None
        logger.info("Session sync thread stopped")
        return True

    def is_running(self) -> bool:
        """Check if the background thread is running."""
        return self._thread is not None and self._thread.is_alive()


def get_session_sync_service(
    data_dir: str = "data",
    sync_interval: int = DEFAULT_SYNC_INTERVAL,
    jsonl_tail_entries: int = DEFAULT_JSONL_TAIL_ENTRIES,
) -> SessionSyncService:
    """Get or create the session sync service singleton.

    Args:
        data_dir: Directory for storing state data
        sync_interval: Seconds between sync cycles
        jsonl_tail_entries: Number of JSONL entries to read per sync

    Returns:
        The SessionSyncService instance
    """
    global _session_sync_service
    if _session_sync_service is None:
        _session_sync_service = SessionSyncService(data_dir, sync_interval, jsonl_tail_entries)
    return _session_sync_service


def reset_session_sync_service() -> None:
    """Reset the session sync service singleton (for testing)."""
    global _session_sync_service
    if _session_sync_service is not None:
        _session_sync_service.stop_background_thread()
    _session_sync_service = None
