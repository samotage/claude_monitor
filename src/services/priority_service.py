"""PriorityService for cross-project prioritization.

Computes and manages priority scores for agents/tasks based on
headspace alignment, using LLM inference.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.models.headspace import HeadspaceFocus
from src.models.inference import InferencePurpose
from src.models.task import TaskState
from src.services.inference_service import InferenceService

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Context for an agent used in priority computation."""

    agent_id: str
    session_name: str
    project_id: str | None
    project_name: str | None
    state: TaskState
    task_summary: str | None = None


@dataclass
class PriorityResult:
    """Result of a priority computation."""

    agent_id: str
    score: int  # 0-100
    rationale: str | None = None
    computed_at: datetime = field(default_factory=datetime.now)


class PriorityService:
    """Computes cross-project priorities based on headspace alignment.

    Responsibilities:
    1. FULL_PRIORITY: Rank all agents/tasks vs headspace (Deep Tier)
    2. QUICK_PRIORITY: Update single agent priority (Fast Tier)
    3. Manage priority caching with proper invalidation
    """

    # Cache TTL in seconds
    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self, inference_service: InferenceService | None = None):
        """Initialize the PriorityService.

        Args:
            inference_service: Service for LLM calls. Creates one if not provided.
        """
        self._inference = inference_service or InferenceService()
        self._cache: dict[str, tuple[dict[str, PriorityResult], datetime]] = {}
        self._last_headspace_hash: str | None = None

    def compute_full_priorities(
        self,
        agents: list[AgentContext],
        headspace: HeadspaceFocus | None,
        force_refresh: bool = False,
    ) -> dict[str, PriorityResult]:
        """Compute priorities for all agents based on headspace.

        Deep Tier operation - uses FULL_PRIORITY inference.

        Args:
            agents: List of agent contexts to prioritize.
            headspace: Current headspace focus. None for default priority.
            force_refresh: If True, bypass cache.

        Returns:
            Dict mapping agent_id to PriorityResult.
        """
        if not agents:
            return {}

        # Build cache key
        cache_key = self._compute_cache_key(agents, headspace)

        # Check cache
        if not force_refresh and cache_key in self._cache:
            cached_results, cached_time = self._cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.CACHE_TTL_SECONDS:
                logger.debug("Returning cached priorities")
                return cached_results

        # Build context for LLM
        headspace_focus = headspace.current_focus if headspace else "No specific focus"
        headspace_constraints = headspace.constraints if headspace else None

        agent_data = [
            {
                "agent_id": a.agent_id,
                "session_name": a.session_name,
                "project_name": a.project_name or "Unknown",
                "state": a.state.value if a.state else "unknown",
                "task_summary": a.task_summary or "No summary",
            }
            for a in agents
        ]

        # Build the prompt
        constraints_text = (
            f"\nConstraints: {headspace_constraints}" if headspace_constraints else ""
        )
        prompt = (
            f"Rank these agents by priority (0-100) based on alignment with the focus.\n\n"
            f"Focus: {headspace_focus}{constraints_text}\n\n"
            f"Agents:\n"
        )
        for a in agent_data:
            prompt += (
                f"- {a['agent_id']}: {a['session_name']} ({a['project_name']}) - {a['state']}\n"
            )

        prompt += '\nRespond with JSON: {"priorities": {"agent_id": {"score": 0-100, "rationale": "..."}, ...}}'

        # Call LLM
        result = self._inference.call(
            purpose=InferencePurpose.FULL_PRIORITY,
            input_data={
                "agents": agent_data,
                "headspace_focus": headspace_focus,
                "headspace_constraints": headspace_constraints,
            },
            user_prompt=prompt,
        )

        # Parse results
        priorities: dict[str, PriorityResult] = {}
        now = datetime.now()

        if "error" not in result.result:
            priorities_data = result.result.get("priorities", {})

            for agent_id, data in priorities_data.items():
                if isinstance(data, dict):
                    score = data.get("score", 50)
                    rationale = data.get("rationale")
                elif isinstance(data, int | float):
                    score = int(data)
                    rationale = None
                else:
                    continue

                priorities[agent_id] = PriorityResult(
                    agent_id=agent_id,
                    score=max(0, min(100, score)),
                    rationale=rationale,
                    computed_at=now,
                )

        # Ensure all agents have a priority
        for agent in agents:
            if agent.agent_id not in priorities:
                # Default priority based on state
                default_score = self._default_priority_for_state(agent.state)
                priorities[agent.agent_id] = PriorityResult(
                    agent_id=agent.agent_id,
                    score=default_score,
                    rationale="Default priority (no LLM result)",
                    computed_at=now,
                )

        # Cache results
        self._cache[cache_key] = (priorities, now)
        self._last_headspace_hash = self._hash_headspace(headspace)

        return priorities

    def compute_quick_priority(
        self,
        agent: AgentContext,
        headspace: HeadspaceFocus | None,
        task_outcome: str | None = None,
    ) -> PriorityResult:
        """Compute quick priority update for a single agent.

        Fast Tier operation - uses QUICK_PRIORITY inference.

        Args:
            agent: The agent context.
            headspace: Current headspace focus.
            task_outcome: Description of what just completed (if any).

        Returns:
            PriorityResult for the agent.
        """
        headspace_focus = headspace.current_focus if headspace else "No specific focus"

        outcome_text = f"\nTask just completed: {task_outcome}" if task_outcome else ""

        result = self._inference.call(
            purpose=InferencePurpose.QUICK_PRIORITY,
            input_data={
                "agent_id": agent.agent_id,
                "session_name": agent.session_name,
                "project_name": agent.project_name,
                "state": agent.state.value,
                "headspace_focus": headspace_focus,
                "task_outcome": task_outcome,
            },
            user_prompt=(
                f"Rate priority 0-100 for this agent after completing work.\n\n"
                f"Focus: {headspace_focus}\n"
                f"Agent: {agent.session_name} ({agent.project_name or 'Unknown'})\n"
                f"State: {agent.state.value}"
                f"{outcome_text}\n\n"
                f"Respond with JSON: {{\"score\": 0-100, \"rationale\": \"...\"}}"
            ),
        )

        if "error" not in result.result:
            score = result.result.get("score", 50)
            rationale = result.result.get("rationale")
        else:
            score = self._default_priority_for_state(agent.state)
            rationale = "Default priority (inference error)"

        return PriorityResult(
            agent_id=agent.agent_id,
            score=max(0, min(100, score)),
            rationale=rationale,
        )

    def invalidate_cache(self, headspace: HeadspaceFocus | None = None) -> int:
        """Invalidate priority cache.

        Called when headspace changes or when agents change significantly.

        Args:
            headspace: New headspace. If different from last, all cache invalidated.

        Returns:
            Number of cache entries invalidated.
        """
        new_hash = self._hash_headspace(headspace)

        # If headspace changed, clear all cache
        if new_hash != self._last_headspace_hash:
            count = len(self._cache)
            self._cache.clear()
            self._last_headspace_hash = new_hash
            logger.debug(f"Invalidated all {count} cache entries (headspace changed)")
            return count

        # Otherwise, clear stale entries
        now = datetime.now()
        stale_keys = [
            key
            for key, (_, cached_time) in self._cache.items()
            if (now - cached_time).total_seconds() >= self.CACHE_TTL_SECONDS
        ]
        for key in stale_keys:
            del self._cache[key]

        if stale_keys:
            logger.debug(f"Invalidated {len(stale_keys)} stale cache entries")

        return len(stale_keys)

    def _compute_cache_key(
        self, agents: list[AgentContext], headspace: HeadspaceFocus | None
    ) -> str:
        """Compute a cache key for a priority computation.

        Args:
            agents: The agents being prioritized.
            headspace: The headspace context.

        Returns:
            A hash string for caching.
        """
        # Sort agents by ID for consistent hashing
        agent_ids = sorted(a.agent_id for a in agents)
        agent_states = "|".join(
            f"{a.agent_id}:{a.state.value if a.state else 'none'}"
            for a in sorted(agents, key=lambda x: x.agent_id)
        )

        headspace_hash = self._hash_headspace(headspace)

        combined = f"{','.join(agent_ids)}|{agent_states}|{headspace_hash}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _hash_headspace(self, headspace: HeadspaceFocus | None) -> str:
        """Compute a hash for headspace.

        Args:
            headspace: The headspace to hash.

        Returns:
            Hash string.
        """
        if headspace is None:
            return "no_headspace"

        content = f"{headspace.current_focus}|{headspace.constraints or ''}"
        return hashlib.md5(content.encode()).hexdigest()

    def _default_priority_for_state(self, state: TaskState) -> int:
        """Get default priority based on task state.

        Args:
            state: The task state.

        Returns:
            Default priority score.
        """
        # AWAITING_INPUT is highest priority (needs attention)
        # COMPLETE is low (task is done)
        # Others are medium
        priorities = {
            TaskState.AWAITING_INPUT: 90,
            TaskState.COMMANDED: 70,
            TaskState.PROCESSING: 60,
            TaskState.IDLE: 50,
            TaskState.COMPLETE: 30,
        }
        return priorities.get(state, 50)

    @property
    def cache_size(self) -> int:
        """Get the number of cached priority computations."""
        return len(self._cache)
