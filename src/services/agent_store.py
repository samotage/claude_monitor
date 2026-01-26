"""AgentStore - Single source of truth for all agent and task state.

Replaces the 7+ scattered state locations in the legacy codebase:
- _previous_activity_states (in-memory dict)
- _turn_tracking (in-memory dict)
- _last_completed_turn (in-memory dict)
- _session_activity_cache (in-memory dict)
- _scan_sessions_cache (200ms TTL cache)
- data/session_state.yaml (on-disk)
- .claude-monitor-*.json files (per-project)
"""

import contextlib
import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

from src.models.agent import Agent
from src.models.headspace import HeadspaceFocus
from src.models.inference import InferenceCall
from src.models.project import Project
from src.models.task import Task, TaskState
from src.models.turn import Turn


class AgentStore:
    """Central store for all agent, task, and turn state.

    This is the single source of truth for:
    - All Agent instances
    - All Task instances
    - All Turn instances
    - All InferenceCall instances
    - HeadspaceFocus singleton
    - Project registry

    State is persisted to disk on changes (debounced).
    Events are emitted for SSE integration.
    """

    def __init__(self, data_dir: str | Path = "data"):
        """Initialize the store.

        Args:
            data_dir: Directory for persisting state.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # In-memory storage
        self._agents: dict[str, Agent] = {}
        self._tasks: dict[str, Task] = {}
        self._turns: dict[str, Turn] = {}
        self._inference_calls: dict[str, InferenceCall] = {}
        self._projects: dict[str, Project] = {}
        self._headspace: HeadspaceFocus | None = None

        # Claude Code session correlation (session_id -> agent_id)
        # This maps Claude Code's $CLAUDE_SESSION_ID to our agent IDs
        self._claude_session_map: dict[str, str] = {}

        # Event listeners
        self._listeners: dict[str, list[Callable]] = {}

        # Load persisted state
        self._load_state()

    # =========================================================================
    # HeadspaceFocus (Singleton)
    # =========================================================================

    def get_headspace(self) -> HeadspaceFocus | None:
        """Get the current headspace focus."""
        return self._headspace

    def update_headspace(self, focus: str, constraints: str | None = None) -> HeadspaceFocus:
        """Update the headspace focus.

        Args:
            focus: The new focus objective.
            constraints: Optional constraints.

        Returns:
            The updated HeadspaceFocus.
        """
        if self._headspace is None:
            self._headspace = HeadspaceFocus(current_focus=focus, constraints=constraints)
        else:
            self._headspace.update_focus(focus, constraints)

        self._emit("headspace_changed", {"headspace": self._headspace.model_dump()})
        self._save_state()
        return self._headspace

    # =========================================================================
    # Project CRUD
    # =========================================================================

    def add_project(self, project: Project) -> Project:
        """Add a project to the store."""
        self._projects[project.id] = project
        self._emit("project_added", {"project_id": project.id})
        self._save_state()
        return project

    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        return self._projects.get(project_id)

    def get_project_by_name(self, name: str) -> Project | None:
        """Get a project by name."""
        for project in self._projects.values():
            if project.name == name:
                return project
        return None

    def list_projects(self) -> list[Project]:
        """List all projects."""
        return list(self._projects.values())

    def update_project(self, project: Project) -> Project:
        """Update a project."""
        self._projects[project.id] = project
        self._emit("project_updated", {"project_id": project.id})
        self._save_state()
        return project

    def remove_project(self, project_id: str) -> bool:
        """Remove a project."""
        if project_id in self._projects:
            del self._projects[project_id]
            self._emit("project_removed", {"project_id": project_id})
            self._save_state()
            return True
        return False

    # =========================================================================
    # Agent CRUD
    # =========================================================================

    def create_agent(
        self,
        terminal_session_id: str,
        session_name: str,
        project_id: str | None = None,
    ) -> Agent:
        """Create a new agent.

        Args:
            terminal_session_id: The WezTerm pane ID.
            session_name: The terminal session name.
            project_id: The project this agent belongs to (optional).

        Returns:
            The created Agent.
        """
        agent = Agent(
            id=str(uuid.uuid4()),
            project_id=project_id,
            terminal_session_id=terminal_session_id,
            session_name=session_name,
        )
        self._agents[agent.id] = agent
        self._emit("agent_created", {"agent_id": agent.id, "project_id": project_id})
        self._save_state()
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def get_agent_by_terminal_session_id(self, session_id: str) -> Agent | None:
        """Get an agent by its terminal session ID."""
        for agent in self._agents.values():
            if agent.terminal_session_id == session_id:
                return agent
        return None

    def get_agents_by_project(self, project_id: str) -> list[Agent]:
        """Get all agents for a project."""
        return [a for a in self._agents.values() if a.project_id == project_id]

    def list_agents(self) -> list[Agent]:
        """List all agents."""
        return list(self._agents.values())

    def update_agent(self, agent: Agent) -> Agent:
        """Update an agent."""
        self._agents[agent.id] = agent
        self._emit("agent_updated", {"agent_id": agent.id})
        self._save_state()
        return agent

    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent and its tasks/turns."""
        if agent_id not in self._agents:
            return False

        # Remove associated tasks and turns
        task_ids = [t.id for t in self._tasks.values() if t.agent_id == agent_id]
        for task_id in task_ids:
            self._remove_task_cascade(task_id)

        # Remove any Claude session mappings
        sessions_to_remove = [
            sid for sid, aid in self._claude_session_map.items() if aid == agent_id
        ]
        for session_id in sessions_to_remove:
            del self._claude_session_map[session_id]

        del self._agents[agent_id]
        self._emit("agent_removed", {"agent_id": agent_id})
        self._save_state()
        return True

    # =========================================================================
    # Claude Code Session Correlation
    # =========================================================================

    def register_claude_session(self, claude_session_id: str, cwd: str) -> Agent:
        """Register a Claude Code session and correlate to an agent.

        This is called when we receive a session_start hook from Claude Code.
        We try to match to an existing agent by working directory, or create
        a new agent if no match is found.

        Args:
            claude_session_id: The Claude Code $CLAUDE_SESSION_ID.
            cwd: The working directory of the session.

        Returns:
            The correlated or newly created Agent.
        """
        # Check if we already have this session mapped
        if claude_session_id in self._claude_session_map:
            agent_id = self._claude_session_map[claude_session_id]
            agent = self._agents.get(agent_id)
            if agent:
                return agent

        # Normalize cwd
        cwd = cwd.rstrip("/") if cwd else ""

        # Try to find existing agent by project path match
        for agent in self._agents.values():
            if agent.project_id:
                project = self._projects.get(agent.project_id)
                if project and project.path:
                    project_path = project.path.rstrip("/")
                    if project_path == cwd:
                        self._claude_session_map[claude_session_id] = agent.id
                        self._emit(
                            "claude_session_registered",
                            {
                                "claude_session_id": claude_session_id,
                                "agent_id": agent.id,
                                "correlation_method": "project_path",
                            },
                        )
                        return agent

        # No match - create a new agent
        session_name = cwd.split("/")[-1] if cwd else "claude-session"
        agent = self.create_agent(
            terminal_session_id=f"hook-{claude_session_id[:8]}",
            session_name=session_name,
        )

        self._claude_session_map[claude_session_id] = agent.id
        self._emit(
            "claude_session_registered",
            {
                "claude_session_id": claude_session_id,
                "agent_id": agent.id,
                "correlation_method": "new_agent",
            },
        )

        return agent

    def get_agent_by_claude_session(self, claude_session_id: str) -> Agent | None:
        """Get an agent by its Claude Code session ID.

        Args:
            claude_session_id: The Claude Code $CLAUDE_SESSION_ID.

        Returns:
            The Agent if found, None otherwise.
        """
        agent_id = self._claude_session_map.get(claude_session_id)
        if agent_id:
            return self._agents.get(agent_id)
        return None

    def unregister_claude_session(self, claude_session_id: str) -> bool:
        """Unregister a Claude Code session.

        Called when a session ends.

        Args:
            claude_session_id: The Claude Code $CLAUDE_SESSION_ID.

        Returns:
            True if the session was registered and removed, False otherwise.
        """
        if claude_session_id in self._claude_session_map:
            agent_id = self._claude_session_map.pop(claude_session_id)
            self._emit(
                "claude_session_unregistered",
                {
                    "claude_session_id": claude_session_id,
                    "agent_id": agent_id,
                },
            )
            return True
        return False

    def get_claude_session_mapping(self) -> dict[str, str]:
        """Get the current Claude session to agent mapping.

        Returns:
            Dict mapping claude_session_id -> agent_id.
        """
        return self._claude_session_map.copy()

    # =========================================================================
    # Task CRUD
    # =========================================================================

    def create_task(self, agent_id: str) -> Task:
        """Create a new task for an agent.

        Args:
            agent_id: The agent this task belongs to.

        Returns:
            The created Task.
        """
        task = Task(id=str(uuid.uuid4()), agent_id=agent_id)
        self._tasks[task.id] = task

        # Link task to agent
        agent = self._agents.get(agent_id)
        if agent:
            agent.current_task_id = task.id
            agent.set_state(task.state)

        self._emit("task_created", {"task_id": task.id, "agent_id": agent_id})
        self._save_state()
        return task

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_current_task(self, agent_id: str) -> Task | None:
        """Get the current task for an agent."""
        agent = self._agents.get(agent_id)
        if agent and agent.current_task_id:
            return self._tasks.get(agent.current_task_id)
        return None

    def get_active_tasks(self) -> list[Task]:
        """Get all tasks that are not COMPLETE or IDLE."""
        return [
            t for t in self._tasks.values() if t.state not in (TaskState.COMPLETE, TaskState.IDLE)
        ]

    def list_tasks(self) -> list[Task]:
        """List all tasks."""
        return list(self._tasks.values())

    def update_task(self, task: Task) -> Task:
        """Update a task and sync agent state."""
        self._tasks[task.id] = task

        # Sync agent state
        agent = self._agents.get(task.agent_id)
        if agent and agent.current_task_id == task.id:
            agent.set_state(task.state)

        self._emit(
            "task_state_changed",
            {"task_id": task.id, "state": task.state.value},
        )
        self._save_state()
        return task

    def remove_task(self, task_id: str) -> bool:
        """Remove a task and its turns."""
        return self._remove_task_cascade(task_id)

    def _remove_task_cascade(self, task_id: str) -> bool:
        """Remove a task and all associated turns/inference calls."""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]

        # Remove turns
        for turn_id in task.turn_ids:
            self._remove_turn_cascade(turn_id)

        # Clear agent reference
        agent = self._agents.get(task.agent_id)
        if agent and agent.current_task_id == task_id:
            agent.current_task_id = None
            agent.set_state(TaskState.IDLE)

        del self._tasks[task_id]
        return True

    # =========================================================================
    # Turn CRUD
    # =========================================================================

    def create_turn(self, task_id: str, turn: Turn) -> Turn:
        """Add a turn to a task.

        Args:
            task_id: The task this turn belongs to.
            turn: The Turn to add (should have task_id set).

        Returns:
            The created Turn.
        """
        turn.task_id = task_id
        if not turn.id:
            turn.id = str(uuid.uuid4())

        self._turns[turn.id] = turn

        # Link to task
        task = self._tasks.get(task_id)
        if task:
            task.turn_ids.append(turn.id)

        self._emit("turn_created", {"turn_id": turn.id, "task_id": task_id})
        self._save_state()
        return turn

    def get_turn(self, turn_id: str) -> Turn | None:
        """Get a turn by ID."""
        return self._turns.get(turn_id)

    def get_turns_for_task(self, task_id: str) -> list[Turn]:
        """Get all turns for a task."""
        task = self._tasks.get(task_id)
        if not task:
            return []
        return [self._turns[tid] for tid in task.turn_ids if tid in self._turns]

    def update_turn(self, turn: Turn) -> Turn:
        """Update a turn."""
        self._turns[turn.id] = turn
        self._save_state()
        return turn

    def _remove_turn_cascade(self, turn_id: str) -> bool:
        """Remove a turn and associated inference calls."""
        if turn_id not in self._turns:
            return False

        turn = self._turns[turn_id]
        for call_id in turn.inference_call_ids:
            if call_id in self._inference_calls:
                del self._inference_calls[call_id]

        del self._turns[turn_id]
        return True

    # =========================================================================
    # InferenceCall CRUD
    # =========================================================================

    def add_inference_call(self, call: InferenceCall) -> InferenceCall:
        """Add an inference call."""
        self._inference_calls[call.id] = call

        # Link to turn if applicable
        if call.turn_id and call.turn_id in self._turns:
            self._turns[call.turn_id].inference_call_ids.append(call.id)

        self._save_state()
        return call

    def get_inference_call(self, call_id: str) -> InferenceCall | None:
        """Get an inference call by ID."""
        return self._inference_calls.get(call_id)

    def list_inference_calls(self) -> list[InferenceCall]:
        """List all inference calls."""
        return list(self._inference_calls.values())

    # =========================================================================
    # Event System
    # =========================================================================

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to an event type.

        Args:
            event_type: The event type to subscribe to.
            callback: Function to call when event occurs.
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from an event type."""
        if event_type in self._listeners:
            self._listeners[event_type] = [
                cb for cb in self._listeners[event_type] if cb != callback
            ]

    def _emit(self, event_type: str, data: dict) -> None:
        """Emit an event to all subscribers."""
        data["event_type"] = event_type
        data["timestamp"] = datetime.now().isoformat()

        for callback in self._listeners.get(event_type, []):
            with contextlib.suppress(Exception):
                callback(data)

        # Also emit to wildcard listeners
        for callback in self._listeners.get("*", []):
            with contextlib.suppress(Exception):
                callback(data)

    # =========================================================================
    # Persistence
    # =========================================================================

    def _get_state_file(self) -> Path:
        """Get the state file path."""
        return self.data_dir / "state.yaml"

    def _save_state(self) -> None:
        """Save state to disk."""
        state = {
            "headspace": self._headspace.model_dump(mode="json") if self._headspace else None,
            "projects": {pid: p.model_dump(mode="json") for pid, p in self._projects.items()},
            "agents": {aid: self._serialize_agent(a) for aid, a in self._agents.items()},
            "tasks": {tid: t.model_dump(mode="json") for tid, t in self._tasks.items()},
            "turns": {tid: t.model_dump(mode="json") for tid, t in self._turns.items()},
            "inference_calls": {
                cid: c.model_dump(mode="json") for cid, c in self._inference_calls.items()
            },
        }

        state_file = self._get_state_file()
        try:
            with open(state_file, "w") as f:
                yaml.dump(state, f, default_flow_style=False)
            logger.info(f"Saved state: {len(self._agents)} agents, {len(self._tasks)} tasks")
        except OSError as e:
            logger.error(f"Failed to save state to {state_file}: {e}")

    def _serialize_agent(self, agent: Agent) -> dict:
        """Serialize an agent to dict."""
        return {
            "id": agent.id,
            "project_id": agent.project_id,
            "terminal_session_id": agent.terminal_session_id,
            "session_name": agent.session_name,
            "current_task_id": agent.current_task_id,
            "created_at": agent.created_at.isoformat(),
            "state": agent.get_state().value,
        }

    def _load_state(self) -> None:
        """Load state from disk."""
        state_file = self._get_state_file()
        if not state_file.exists():
            return

        try:
            with open(state_file) as f:
                state = yaml.safe_load(f)

            if not state:
                return

            # Load headspace
            if state.get("headspace"):
                hdata = state["headspace"]
                # Convert datetime fields
                if "updated_at" in hdata and isinstance(hdata["updated_at"], str):
                    hdata["updated_at"] = datetime.fromisoformat(hdata["updated_at"])
                # Handle history entries
                for entry in hdata.get("history", []):
                    for field in ["started_at", "ended_at"]:
                        if field in entry and isinstance(entry[field], str):
                            entry[field] = datetime.fromisoformat(entry[field])
                self._headspace = HeadspaceFocus(**hdata)

            # Load projects
            for pid, pdata in state.get("projects", {}).items():
                # Handle nested datetime fields
                if (
                    "state" in pdata
                    and "last_activity_at" in pdata["state"]
                    and isinstance(pdata["state"]["last_activity_at"], str)
                ):
                    pdata["state"]["last_activity_at"] = datetime.fromisoformat(
                        pdata["state"]["last_activity_at"]
                    )
                if (
                    "roadmap" in pdata
                    and "recently_completed_at" in pdata["roadmap"]
                    and isinstance(pdata["roadmap"]["recently_completed_at"], str)
                ):
                    pdata["roadmap"]["recently_completed_at"] = datetime.fromisoformat(
                        pdata["roadmap"]["recently_completed_at"]
                    )
                self._projects[pid] = Project(**pdata)

            # Load agents (need to handle state separately)
            for aid, adata in state.get("agents", {}).items():
                cached_state = adata.pop("state", "idle")
                if "created_at" in adata and isinstance(adata["created_at"], str):
                    adata["created_at"] = datetime.fromisoformat(adata["created_at"])
                agent = Agent(**adata)
                agent.set_state(TaskState(cached_state))
                self._agents[aid] = agent

            # Load tasks
            for tid, tdata in state.get("tasks", {}).items():
                if "started_at" in tdata and isinstance(tdata["started_at"], str):
                    tdata["started_at"] = datetime.fromisoformat(tdata["started_at"])
                if "completed_at" in tdata and isinstance(tdata["completed_at"], str):
                    tdata["completed_at"] = datetime.fromisoformat(tdata["completed_at"])
                self._tasks[tid] = Task(**tdata)

            # Load turns
            for tid, tdata in state.get("turns", {}).items():
                if "timestamp" in tdata and isinstance(tdata["timestamp"], str):
                    tdata["timestamp"] = datetime.fromisoformat(tdata["timestamp"])
                self._turns[tid] = Turn(**tdata)

            # Load inference calls
            for cid, cdata in state.get("inference_calls", {}).items():
                if "timestamp" in cdata and isinstance(cdata["timestamp"], str):
                    cdata["timestamp"] = datetime.fromisoformat(cdata["timestamp"])
                self._inference_calls[cid] = InferenceCall(**cdata)

        except Exception:
            # If state is corrupted, start fresh
            pass

    def clear(self) -> None:
        """Clear all state (for testing)."""
        self._agents.clear()
        self._tasks.clear()
        self._turns.clear()
        self._inference_calls.clear()
        self._projects.clear()
        self._headspace = None
        self._save_state()
