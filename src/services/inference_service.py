"""InferenceService for LLM calls via OpenRouter.

Implements per-purpose model routing and caching strategy from §6.
"""

import contextlib
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

from src.models.inference import InferenceCall, InferenceConfig, InferencePurpose


@dataclass
class CacheEntry:
    """A cached inference result."""

    result: dict
    expires_at: datetime
    inference_call: InferenceCall


class InferenceService:
    """Service for making LLM inference calls via OpenRouter.

    Features:
    - Per-purpose model routing via InferenceConfig
    - Caching with purpose-specific TTLs
    - Cost tracking
    - Structured output parsing
    """

    # Cache TTLs by purpose (from §6)
    CACHE_TTLS: dict[InferencePurpose, timedelta | None] = {
        InferencePurpose.DETECT_STATE: timedelta(seconds=30),
        InferencePurpose.SUMMARIZE_COMMAND: None,  # Forever
        InferencePurpose.CLASSIFY_RESPONSE: None,  # Forever
        InferencePurpose.QUICK_PRIORITY: timedelta(minutes=5),  # Until next turn
        InferencePurpose.FULL_PRIORITY: timedelta(minutes=10),  # Until invalidation
        InferencePurpose.BRAIN_REBOOT: timedelta(hours=1),
        InferencePurpose.GENERATE_PROGRESS_NARRATIVE: timedelta(hours=24),
        InferencePurpose.ROADMAP_ANALYSIS: timedelta(hours=1),
    }

    # OpenRouter API endpoint
    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        config: InferenceConfig | None = None,
        api_key: str | None = None,
    ):
        """Initialize the InferenceService.

        Args:
            config: Model configuration per purpose.
            api_key: OpenRouter API key. If not provided, reads from OPENROUTER_API_KEY.
        """
        self.config = config or InferenceConfig()
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._cache: dict[str, CacheEntry] = {}

    def _compute_hash(self, purpose: InferencePurpose, input_data: dict) -> str:
        """Compute a hash for caching purposes."""
        data = json.dumps({"purpose": purpose.value, **input_data}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _get_cache_key(
        self,
        purpose: InferencePurpose,
        input_hash: str,
        project_id: str | None = None,
        turn_id: str | None = None,
    ) -> str:
        """Get the cache key for a request."""
        parts = [purpose.value, input_hash]
        if project_id:
            parts.append(project_id)
        if turn_id:
            parts.append(turn_id)
        return ":".join(parts)

    def get_cached(
        self,
        purpose: InferencePurpose,
        input_hash: str,
        project_id: str | None = None,
        turn_id: str | None = None,
    ) -> InferenceCall | None:
        """Get a cached result if available and not expired.

        Args:
            purpose: The inference purpose.
            input_hash: Hash of the input data.
            project_id: Optional project ID for context.
            turn_id: Optional turn ID for context.

        Returns:
            Cached InferenceCall or None.
        """
        key = self._get_cache_key(purpose, input_hash, project_id, turn_id)
        entry = self._cache.get(key)

        if entry is None:
            return None

        # Check expiration
        if entry.expires_at and datetime.now() > entry.expires_at:
            del self._cache[key]
            return None

        return entry.inference_call

    def invalidate_cache(
        self,
        purpose: InferencePurpose | None = None,
        project_id: str | None = None,
    ) -> int:
        """Invalidate cached entries.

        Args:
            purpose: If provided, only invalidate for this purpose.
            project_id: If provided, only invalidate for this project.

        Returns:
            Number of entries invalidated.
        """
        to_remove = []
        for key in self._cache:
            parts = key.split(":")
            key_purpose = parts[0]
            key_project = parts[2] if len(parts) > 2 else None

            if purpose and key_purpose != purpose.value:
                continue
            if project_id and key_project != project_id:
                continue
            to_remove.append(key)

        for key in to_remove:
            del self._cache[key]

        return len(to_remove)

    def call(
        self,
        purpose: InferencePurpose,
        input_data: dict,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        project_id: str | None = None,
        turn_id: str | None = None,
        use_cache: bool = True,
    ) -> InferenceCall:
        """Make an inference call.

        Args:
            purpose: The purpose of this inference.
            input_data: Data to include in the request.
            system_prompt: Optional system prompt.
            user_prompt: Optional user prompt. If not provided, input_data is formatted.
            project_id: Optional project ID for context.
            turn_id: Optional turn ID for context.
            use_cache: Whether to use/update cache.

        Returns:
            InferenceCall with the result.
        """
        input_hash = self._compute_hash(purpose, input_data)

        # Check cache
        if use_cache:
            cached = self.get_cached(purpose, input_hash, project_id, turn_id)
            if cached:
                # Return a copy with cached=True
                return InferenceCall(
                    id=cached.id,
                    turn_id=cached.turn_id,
                    project_id=cached.project_id,
                    purpose=cached.purpose,
                    model=cached.model,
                    input_hash=cached.input_hash,
                    result=cached.result,
                    timestamp=cached.timestamp,
                    latency_ms=cached.latency_ms,
                    cost_cents=cached.cost_cents,
                    cached=True,
                )

        # Build the request
        model = self.config.get_model(purpose)
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})
        else:
            # Format input_data as prompt
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(input_data, indent=2),
                }
            )

        # Make the API call
        start_time = time.time()
        result, latency_ms = self._call_api(model, messages)
        if latency_ms == 0:
            latency_ms = int((time.time() - start_time) * 1000)
        # Ensure at least 1ms for successful calls (mocks can be instant)
        if latency_ms == 0 and "error" not in result:
            latency_ms = 1

        # Create InferenceCall
        inference_call = InferenceCall(
            id=str(uuid.uuid4()),
            turn_id=turn_id,
            project_id=project_id,
            purpose=purpose,
            model=model,
            input_hash=input_hash,
            result=result,
            latency_ms=latency_ms,
            cached=False,
        )

        # Update cache
        if use_cache:
            self._update_cache(purpose, input_hash, inference_call, project_id, turn_id)

        return inference_call

    def _call_api(self, model: str, messages: list[dict]) -> tuple[dict, int]:
        """Make the actual API call to OpenRouter.

        Args:
            model: The model to use.
            messages: The messages to send.

        Returns:
            Tuple of (result dict, latency in ms).
        """
        if not self.api_key:
            return {"error": "No API key configured", "content": ""}, 0

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/otagelabs/claude-headspace",
            "X-Title": "Claude Headspace",
        }

        payload = {
            "model": model,
            "messages": messages,
        }

        try:
            start = time.time()
            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            latency = int((time.time() - start) * 1000)

            if response.status_code != 200:
                return {
                    "error": f"API error: {response.status_code}",
                    "content": response.text,
                }, latency

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Try to parse as JSON if it looks like JSON
            result = {"content": content}
            if content.strip().startswith("{"):
                with contextlib.suppress(json.JSONDecodeError):
                    result = json.loads(content)

            return result, latency

        except Exception as e:
            return {"error": str(e), "content": ""}, 0

    def _update_cache(
        self,
        purpose: InferencePurpose,
        input_hash: str,
        inference_call: InferenceCall,
        project_id: str | None,
        turn_id: str | None,
    ) -> None:
        """Update the cache with a new result."""
        ttl = self.CACHE_TTLS.get(purpose)
        expires_at = datetime.max if ttl is None else datetime.now() + ttl

        key = self._get_cache_key(purpose, input_hash, project_id, turn_id)
        self._cache[key] = CacheEntry(
            result=inference_call.result,
            expires_at=expires_at,
            inference_call=inference_call,
        )

    def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed.
        """
        now = datetime.now()
        to_remove = [
            key for key, entry in self._cache.items() if entry.expires_at and entry.expires_at < now
        ]
        for key in to_remove:
            del self._cache[key]
        return len(to_remove)

    @property
    def cache_size(self) -> int:
        """Get the number of cached entries."""
        return len(self._cache)

    def clear_cache(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
