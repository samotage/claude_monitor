"""Tests for InferenceService."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.models.inference import InferenceConfig, InferencePurpose
from src.services.inference_service import CacheEntry, InferenceService


@pytest.fixture
def inference_service():
    """Create an InferenceService instance."""
    return InferenceService(api_key="test-api-key")


@pytest.fixture
def mock_response():
    """Create a mock successful API response."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"choices": [{"message": {"content": '{"state": "processing"}'}}]}
    return mock


class TestInferenceServiceInit:
    """Tests for InferenceService initialization."""

    def test_default_config(self):
        """Default InferenceConfig is used if not provided."""
        service = InferenceService()
        assert service.config is not None
        assert "haiku" in service.config.detect_state

    def test_custom_config(self):
        """Custom InferenceConfig is used when provided."""
        config = InferenceConfig(detect_state="custom/model")
        service = InferenceService(config=config)
        assert service.config.detect_state == "custom/model"

    def test_api_key_from_env(self):
        """API key is read from environment if not provided."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
            service = InferenceService()
            assert service.api_key == "env-key"


class TestModelRouting:
    """Tests for model routing based on purpose."""

    def test_fast_tier_uses_haiku(self, inference_service):
        """Fast tier purposes use Haiku by default."""
        config = inference_service.config
        assert "haiku" in config.get_model(InferencePurpose.DETECT_STATE)
        assert "haiku" in config.get_model(InferencePurpose.SUMMARIZE_COMMAND)
        assert "haiku" in config.get_model(InferencePurpose.CLASSIFY_RESPONSE)
        assert "haiku" in config.get_model(InferencePurpose.QUICK_PRIORITY)

    def test_deep_tier_uses_sonnet(self, inference_service):
        """Deep tier purposes use Sonnet by default."""
        config = inference_service.config
        assert "sonnet" in config.get_model(InferencePurpose.FULL_PRIORITY)
        assert "sonnet" in config.get_model(InferencePurpose.BRAIN_REBOOT)
        assert "sonnet" in config.get_model(InferencePurpose.GENERATE_PROGRESS_NARRATIVE)
        assert "sonnet" in config.get_model(InferencePurpose.ROADMAP_ANALYSIS)


class TestHashComputation:
    """Tests for input hash computation."""

    def test_same_input_same_hash(self, inference_service):
        """Same input produces same hash."""
        data = {"key": "value"}
        hash1 = inference_service._compute_hash(InferencePurpose.DETECT_STATE, data)
        hash2 = inference_service._compute_hash(InferencePurpose.DETECT_STATE, data)
        assert hash1 == hash2

    def test_different_input_different_hash(self, inference_service):
        """Different input produces different hash."""
        hash1 = inference_service._compute_hash(InferencePurpose.DETECT_STATE, {"a": 1})
        hash2 = inference_service._compute_hash(InferencePurpose.DETECT_STATE, {"a": 2})
        assert hash1 != hash2

    def test_different_purpose_different_hash(self, inference_service):
        """Different purpose produces different hash."""
        data = {"key": "value"}
        hash1 = inference_service._compute_hash(InferencePurpose.DETECT_STATE, data)
        hash2 = inference_service._compute_hash(InferencePurpose.SUMMARIZE_COMMAND, data)
        assert hash1 != hash2


class TestCaching:
    """Tests for caching functionality."""

    def test_get_cached_returns_none_when_empty(self, inference_service):
        """get_cached returns None when cache is empty."""
        result = inference_service.get_cached(
            InferencePurpose.DETECT_STATE,
            "abc123",
        )
        assert result is None

    @patch("src.services.inference_service.requests.post")
    def test_result_is_cached(self, mock_post, inference_service, mock_response):
        """Results are cached after a call."""
        mock_post.return_value = mock_response

        # First call
        result1 = inference_service.call(
            InferencePurpose.DETECT_STATE,
            {"content": "test"},
        )
        assert result1.cached is False

        # Second call should use cache
        result2 = inference_service.call(
            InferencePurpose.DETECT_STATE,
            {"content": "test"},
        )
        assert result2.cached is True

        # Only one API call should have been made
        assert mock_post.call_count == 1

    @patch("src.services.inference_service.requests.post")
    def test_cache_bypassed_when_disabled(self, mock_post, inference_service, mock_response):
        """Cache can be bypassed with use_cache=False."""
        mock_post.return_value = mock_response

        # First call
        inference_service.call(
            InferencePurpose.DETECT_STATE,
            {"content": "test"},
        )

        # Second call with cache disabled
        result = inference_service.call(
            InferencePurpose.DETECT_STATE,
            {"content": "test"},
            use_cache=False,
        )
        assert result.cached is False
        assert mock_post.call_count == 2

    def test_cache_expiration(self, inference_service):
        """Expired cache entries are not returned."""
        # Manually add an expired entry
        inference_service._cache["test:hash"] = CacheEntry(
            result={"test": "data"},
            expires_at=datetime.now() - timedelta(hours=1),
            inference_call=MagicMock(),
        )

        result = inference_service.get_cached(
            InferencePurpose.DETECT_STATE,
            "hash",
        )
        assert result is None

    def test_cleanup_expired(self, inference_service):
        """cleanup_expired removes expired entries."""
        # Add expired entry
        inference_service._cache["expired:hash"] = CacheEntry(
            result={},
            expires_at=datetime.now() - timedelta(hours=1),
            inference_call=MagicMock(),
        )
        # Add valid entry
        inference_service._cache["valid:hash"] = CacheEntry(
            result={},
            expires_at=datetime.now() + timedelta(hours=1),
            inference_call=MagicMock(),
        )

        removed = inference_service.cleanup_expired()
        assert removed == 1
        assert "expired:hash" not in inference_service._cache
        assert "valid:hash" in inference_service._cache

    def test_invalidate_cache_by_purpose(self, inference_service):
        """invalidate_cache can filter by purpose."""
        inference_service._cache["detect_state:h1"] = CacheEntry(
            result={}, expires_at=datetime.max, inference_call=MagicMock()
        )
        inference_service._cache["summarize_command:h2"] = CacheEntry(
            result={}, expires_at=datetime.max, inference_call=MagicMock()
        )

        removed = inference_service.invalidate_cache(purpose=InferencePurpose.DETECT_STATE)
        assert removed == 1
        assert "detect_state:h1" not in inference_service._cache
        assert "summarize_command:h2" in inference_service._cache

    def test_invalidate_cache_by_project(self, inference_service):
        """invalidate_cache can filter by project."""
        inference_service._cache["detect_state:h1:proj-1"] = CacheEntry(
            result={}, expires_at=datetime.max, inference_call=MagicMock()
        )
        inference_service._cache["detect_state:h2:proj-2"] = CacheEntry(
            result={}, expires_at=datetime.max, inference_call=MagicMock()
        )

        removed = inference_service.invalidate_cache(project_id="proj-1")
        assert removed == 1
        assert "detect_state:h1:proj-1" not in inference_service._cache
        assert "detect_state:h2:proj-2" in inference_service._cache

    def test_clear_cache(self, inference_service):
        """clear_cache removes all entries."""
        inference_service._cache["a:b"] = CacheEntry(
            result={}, expires_at=datetime.max, inference_call=MagicMock()
        )
        inference_service._cache["c:d"] = CacheEntry(
            result={}, expires_at=datetime.max, inference_call=MagicMock()
        )

        inference_service.clear_cache()
        assert inference_service.cache_size == 0


class TestAPICall:
    """Tests for API call functionality."""

    @patch("src.services.inference_service.requests.post")
    def test_successful_call(self, mock_post, inference_service, mock_response):
        """Successful API call returns parsed result."""
        mock_post.return_value = mock_response

        result = inference_service.call(
            InferencePurpose.DETECT_STATE,
            {"content": "test content"},
            system_prompt="You are a helpful assistant.",
            user_prompt="What is the state?",
        )

        assert result.purpose == InferencePurpose.DETECT_STATE
        assert result.result.get("state") == "processing"
        assert result.latency_ms > 0

    @patch("src.services.inference_service.requests.post")
    def test_call_with_project_and_turn_id(self, mock_post, inference_service, mock_response):
        """Project and turn IDs are included in InferenceCall."""
        mock_post.return_value = mock_response

        result = inference_service.call(
            InferencePurpose.SUMMARIZE_COMMAND,
            {"content": "test"},
            project_id="proj-1",
            turn_id="turn-1",
        )

        assert result.project_id == "proj-1"
        assert result.turn_id == "turn-1"

    @patch("src.services.inference_service.requests.post")
    def test_api_error_handling(self, mock_post, inference_service):
        """API errors are captured in result."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = inference_service.call(
            InferencePurpose.DETECT_STATE,
            {"content": "test"},
        )

        assert "error" in result.result
        assert "500" in result.result["error"]

    @patch("src.services.inference_service.requests.post")
    def test_request_exception_handling(self, mock_post, inference_service):
        """Request exceptions are captured in result."""
        mock_post.side_effect = Exception("Connection error")

        result = inference_service.call(
            InferencePurpose.DETECT_STATE,
            {"content": "test"},
        )

        assert "error" in result.result
        assert "Connection error" in result.result["error"]

    def test_no_api_key_error(self):
        """Missing API key returns error."""
        service = InferenceService(api_key="")

        result = service.call(
            InferencePurpose.DETECT_STATE,
            {"content": "test"},
        )

        assert "error" in result.result
        assert "No API key" in result.result["error"]

    @patch("src.services.inference_service.requests.post")
    def test_json_response_parsed(self, mock_post, inference_service):
        """JSON responses are automatically parsed."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"key": "value", "number": 42}'}}]
        }
        mock_post.return_value = mock_response

        result = inference_service.call(
            InferencePurpose.DETECT_STATE,
            {"test": "data"},
        )

        assert result.result.get("key") == "value"
        assert result.result.get("number") == 42

    @patch("src.services.inference_service.requests.post")
    def test_non_json_response_wrapped(self, mock_post, inference_service):
        """Non-JSON responses are wrapped in content field."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Just plain text response"}}]
        }
        mock_post.return_value = mock_response

        result = inference_service.call(
            InferencePurpose.DETECT_STATE,
            {"test": "data"},
        )

        assert result.result.get("content") == "Just plain text response"


class TestCacheTTLs:
    """Tests for cache TTL configuration."""

    def test_detect_state_ttl(self, inference_service):
        """DETECT_STATE has 30 second TTL."""
        ttl = inference_service.CACHE_TTLS[InferencePurpose.DETECT_STATE]
        assert ttl == timedelta(seconds=30)

    def test_summarize_command_forever(self, inference_service):
        """SUMMARIZE_COMMAND caches forever."""
        ttl = inference_service.CACHE_TTLS[InferencePurpose.SUMMARIZE_COMMAND]
        assert ttl is None  # Forever

    def test_classify_response_forever(self, inference_service):
        """CLASSIFY_RESPONSE caches forever."""
        ttl = inference_service.CACHE_TTLS[InferencePurpose.CLASSIFY_RESPONSE]
        assert ttl is None  # Forever

    def test_brain_reboot_1_hour(self, inference_service):
        """BRAIN_REBOOT has 1 hour TTL."""
        ttl = inference_service.CACHE_TTLS[InferencePurpose.BRAIN_REBOOT]
        assert ttl == timedelta(hours=1)

    def test_generate_narrative_24_hours(self, inference_service):
        """GENERATE_PROGRESS_NARRATIVE has 24 hour TTL."""
        ttl = inference_service.CACHE_TTLS[InferencePurpose.GENERATE_PROGRESS_NARRATIVE]
        assert ttl == timedelta(hours=24)


class TestCacheSize:
    """Tests for cache_size property."""

    def test_cache_size_empty(self, inference_service):
        """cache_size returns 0 for empty cache."""
        assert inference_service.cache_size == 0

    def test_cache_size_with_entries(self, inference_service):
        """cache_size returns correct count."""
        inference_service._cache["a:b"] = CacheEntry(
            result={}, expires_at=datetime.max, inference_call=MagicMock()
        )
        inference_service._cache["c:d"] = CacheEntry(
            result={}, expires_at=datetime.max, inference_call=MagicMock()
        )

        assert inference_service.cache_size == 2
