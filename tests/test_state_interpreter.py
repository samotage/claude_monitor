"""Tests for StateInterpreter."""

from unittest.mock import MagicMock, patch

import pytest

from src.models.inference import InferencePurpose
from src.models.task import TaskState
from src.services.state_interpreter import (
    InterpretationMethod,
    StateInterpreter,
)


@pytest.fixture
def mock_inference_service():
    """Create a mock InferenceService."""
    return MagicMock()


@pytest.fixture
def interpreter(mock_inference_service):
    """Create a StateInterpreter with mocked inference service."""
    return StateInterpreter(inference_service=mock_inference_service)


class TestRegexFastPathProcessing:
    """Tests for regex fast-path PROCESSING detection."""

    def test_spinner_detected(self, interpreter):
        """Spinner character triggers PROCESSING state."""
        content = "⠋ Running tests..."
        result = interpreter.interpret(content)

        assert result.state == TaskState.PROCESSING
        assert result.confidence >= 0.9
        assert result.method == InterpretationMethod.REGEX

    def test_multiple_spinner_chars(self, interpreter):
        """Various spinner characters all detected."""
        for spinner in ["⠁", "⠙", "⠿"]:
            content = f"{spinner} Working..."
            result = interpreter.interpret(content)
            assert result.state == TaskState.PROCESSING

    def test_esc_to_interrupt(self, interpreter):
        """'(esc to interrupt)' triggers PROCESSING state."""
        content = "Reading file... (esc to interrupt)"
        result = interpreter.interpret(content)

        assert result.state == TaskState.PROCESSING
        assert result.method == InterpretationMethod.REGEX

    def test_running_indicator(self, interpreter):
        """'Running: command' triggers PROCESSING state."""
        content = "Running: pytest tests/"
        result = interpreter.interpret(content)

        assert result.state == TaskState.PROCESSING

    def test_executing_indicator(self, interpreter):
        """'Executing:' triggers PROCESSING state."""
        content = "Executing: npm install"
        result = interpreter.interpret(content)

        assert result.state == TaskState.PROCESSING


class TestRegexFastPathComplete:
    """Tests for regex fast-path COMPLETE detection."""

    def test_checkmark_completion(self, interpreter):
        """Checkmark with duration triggers COMPLETE state."""
        content = "✻ Wrote file for 2m 30s"
        result = interpreter.interpret(content)

        assert result.state == TaskState.COMPLETE
        assert result.confidence >= 0.9
        assert result.method == InterpretationMethod.REGEX

    def test_completed_in_indicator(self, interpreter):
        """'Completed in X' triggers COMPLETE state."""
        content = "All tests passed. Completed in 45 seconds."
        result = interpreter.interpret(content)

        assert result.state == TaskState.COMPLETE

    def test_success_checkmark(self, interpreter):
        """Success checkmark variant triggers COMPLETE."""
        content = "✓ Build finished for 1m 5s"
        result = interpreter.interpret(content)

        assert result.state == TaskState.COMPLETE


class TestRegexFastPathAwaitingInput:
    """Tests for regex fast-path AWAITING_INPUT detection."""

    def test_question_mark_at_end(self, interpreter):
        """Question ending in '?' triggers AWAITING_INPUT."""
        content = "Would you like me to proceed?"
        result = interpreter.interpret(content)

        assert result.state == TaskState.AWAITING_INPUT
        assert result.method == InterpretationMethod.REGEX

    def test_do_you_want_prompt(self, interpreter):
        """'Do you want to' prompt triggers AWAITING_INPUT."""
        content = "Do you want to run these tests?"
        result = interpreter.interpret(content)

        assert result.state == TaskState.AWAITING_INPUT

    def test_should_i_prompt(self, interpreter):
        """'Should I' prompt triggers AWAITING_INPUT."""
        content = "Should I continue with the refactoring?"
        result = interpreter.interpret(content)

        assert result.state == TaskState.AWAITING_INPUT

    def test_y_n_prompt(self, interpreter):
        """'[y/n]' prompt triggers AWAITING_INPUT."""
        content = "Create new file? [y/n]"
        result = interpreter.interpret(content)

        assert result.state == TaskState.AWAITING_INPUT

    def test_yes_no_prompt(self, interpreter):
        """'(yes/no)' prompt triggers AWAITING_INPUT."""
        content = "Overwrite existing file? (yes/no)"
        result = interpreter.interpret(content)

        assert result.state == TaskState.AWAITING_INPUT


class TestRegexFastPathPriority:
    """Tests for pattern priority when multiple patterns match."""

    def test_processing_takes_priority_over_question(self, interpreter):
        """PROCESSING patterns take priority over AWAITING_INPUT."""
        # Content has both a spinner and a question
        content = "⠋ Should I continue?"
        result = interpreter.interpret(content)

        # Processing should win because it indicates active work
        assert result.state == TaskState.PROCESSING

    def test_processing_in_middle_of_content(self, interpreter):
        """Processing detected even if not at end of content."""
        content = """
        Some initial text
        ⠙ Running tests...
        Some more text
        """
        result = interpreter.interpret(content)

        assert result.state == TaskState.PROCESSING


class TestEmptyAndMinimalContent:
    """Tests for empty and minimal content handling."""

    def test_empty_content(self, interpreter):
        """Empty content returns IDLE with low confidence."""
        result = interpreter.interpret("")

        assert result.state == TaskState.IDLE
        assert result.confidence == 0.5
        assert result.method == InterpretationMethod.REGEX

    def test_whitespace_only(self, interpreter):
        """Whitespace-only content returns IDLE."""
        result = interpreter.interpret("   \n\n\t  ")

        assert result.state == TaskState.IDLE

    def test_none_content(self, interpreter):
        """None content (via empty string check) returns IDLE."""
        # The method expects a string, but empty is the edge case
        result = interpreter.interpret("")
        assert result.state == TaskState.IDLE


class TestLLMFallback:
    """Tests for LLM fallback when regex doesn't match."""

    def test_llm_called_for_ambiguous_content(self, interpreter, mock_inference_service):
        """LLM is called when regex patterns don't match."""
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "IDLE", "confidence": 0.7, "reasoning": "Just a prompt"}
        )

        # Content that doesn't match any regex pattern
        content = "$ claude-code\nWelcome to Claude Code!"
        result = interpreter.interpret(content)

        # LLM should have been called
        mock_inference_service.call.assert_called_once()
        assert result.method == InterpretationMethod.LLM

    def test_llm_returns_processing(self, interpreter, mock_inference_service):
        """LLM can return PROCESSING state."""
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "PROCESSING", "confidence": 0.85, "reasoning": "Thinking"}
        )

        content = "Let me think about this..."
        result = interpreter.interpret(content)

        assert result.state == TaskState.PROCESSING
        assert result.confidence == 0.85
        assert result.method == InterpretationMethod.LLM

    def test_llm_returns_awaiting_input(self, interpreter, mock_inference_service):
        """LLM can return AWAITING_INPUT state."""
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "AWAITING_INPUT", "confidence": 0.9, "reasoning": "Waiting"}
        )

        content = "I need some clarification from you."
        result = interpreter.interpret(content)

        assert result.state == TaskState.AWAITING_INPUT
        assert result.method == InterpretationMethod.LLM

    def test_llm_returns_complete(self, interpreter, mock_inference_service):
        """LLM can return COMPLETE state."""
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "COMPLETE", "confidence": 0.95, "reasoning": "Done"}
        )

        content = "I've finished the task you asked for."
        result = interpreter.interpret(content)

        assert result.state == TaskState.COMPLETE

    def test_llm_returns_commanded(self, interpreter, mock_inference_service):
        """LLM can return COMMANDED state."""
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "COMMANDED", "confidence": 0.8, "reasoning": "Just started"}
        )

        content = "Understood, I'll work on that now."
        result = interpreter.interpret(content)

        assert result.state == TaskState.COMMANDED


class TestLLMErrorHandling:
    """Tests for LLM error handling."""

    def test_llm_error_returns_idle(self, interpreter, mock_inference_service):
        """LLM error returns IDLE with low confidence."""
        mock_inference_service.call.return_value = MagicMock(result={"error": "API error: 500"})

        content = "Some ambiguous content"
        result = interpreter.interpret(content)

        assert result.state == TaskState.IDLE
        assert result.confidence == 0.3
        assert result.method == InterpretationMethod.LLM

    def test_llm_invalid_state_returns_idle(self, interpreter, mock_inference_service):
        """Invalid state from LLM maps to IDLE."""
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "INVALID_STATE", "confidence": 0.5}
        )

        content = "Some content"
        result = interpreter.interpret(content)

        assert result.state == TaskState.IDLE


class TestLLMCallParameters:
    """Tests for LLM call parameters."""

    def test_correct_purpose_used(self, interpreter, mock_inference_service):
        """DETECT_STATE purpose is used for LLM calls."""
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "IDLE", "confidence": 0.5}
        )

        content = "Some ambiguous content"
        interpreter.interpret(content)

        call_args = mock_inference_service.call.call_args
        assert call_args[1]["purpose"] == InferencePurpose.DETECT_STATE

    def test_content_included_in_input_data(self, interpreter, mock_inference_service):
        """Terminal content is included in input_data."""
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "IDLE", "confidence": 0.5}
        )

        content = "Test content for LLM"
        interpreter.interpret(content)

        call_args = mock_inference_service.call.call_args
        input_data = call_args[1]["input_data"]
        assert "terminal_content" in input_data

    def test_long_content_truncated(self, interpreter, mock_inference_service):
        """Long content is truncated before sending to LLM."""
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "IDLE", "confidence": 0.5}
        )

        # Content longer than 2000 chars
        content = "x" * 5000
        interpreter.interpret(content)

        call_args = mock_inference_service.call.call_args
        input_data = call_args[1]["input_data"]
        # Should be truncated to 2000 (most recent)
        assert len(input_data["terminal_content"]) == 2000


class TestInterpretationResult:
    """Tests for InterpretationResult dataclass."""

    def test_result_has_all_fields(self, interpreter):
        """InterpretationResult has all expected fields."""
        content = "⠋ Working..."
        result = interpreter.interpret(content)

        assert hasattr(result, "state")
        assert hasattr(result, "confidence")
        assert hasattr(result, "method")
        assert hasattr(result, "raw_content_snippet")

    def test_snippet_preserved(self, interpreter):
        """Raw content snippet is preserved for debugging."""
        content = "⠋ Working on something important..."
        result = interpreter.interpret(content)

        assert result.raw_content_snippet is not None
        assert "Working" in result.raw_content_snippet

    def test_long_content_snippet_truncated(self, interpreter):
        """Long content snippet is truncated."""
        content = "x" * 1000 + "⠋ Working..."
        result = interpreter.interpret(content)

        # Snippet should be truncated (last 500 chars)
        assert len(result.raw_content_snippet) <= 500


class TestDefaultInferenceService:
    """Tests for default InferenceService creation."""

    @patch("src.services.state_interpreter.InferenceService")
    def test_creates_default_service(self, mock_service_class):
        """Creates InferenceService if none provided."""
        StateInterpreter()

        mock_service_class.assert_called_once()

    def test_uses_provided_service(self, mock_inference_service):
        """Uses provided InferenceService instance."""
        interpreter = StateInterpreter(inference_service=mock_inference_service)

        # Trigger an LLM call
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "IDLE", "confidence": 0.5}
        )
        interpreter.interpret("ambiguous content")

        # The provided mock should be called
        mock_inference_service.call.assert_called_once()


class TestEdgeCases:
    """Tests for edge cases and corner conditions."""

    def test_unicode_content(self, interpreter):
        """Unicode content is handled correctly."""
        content = "日本語のテスト ⠋ 処理中..."
        result = interpreter.interpret(content)

        assert result.state == TaskState.PROCESSING

    def test_ansi_escape_codes(self, interpreter):
        """ANSI escape codes don't break parsing."""
        content = "\x1b[32m⠋\x1b[0m Running..."
        result = interpreter.interpret(content)

        assert result.state == TaskState.PROCESSING

    def test_mixed_line_endings(self, interpreter):
        """Mixed line endings are handled."""
        content = "Line 1\r\nLine 2\nLine 3\r⠋ Working"
        result = interpreter.interpret(content)

        assert result.state == TaskState.PROCESSING

    def test_very_long_content(self, interpreter, mock_inference_service):
        """Very long content doesn't cause issues."""
        mock_inference_service.call.return_value = MagicMock(
            result={"state": "IDLE", "confidence": 0.5}
        )

        content = "x" * 100000  # 100KB
        result = interpreter.interpret(content)

        # Should complete without error
        assert result is not None
