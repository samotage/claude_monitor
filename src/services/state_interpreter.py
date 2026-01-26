"""StateInterpreter for detecting Claude Code session state.

Uses LLM-based interpretation with regex fast-path optimization.
"""

import re
from dataclasses import dataclass
from enum import Enum

from src.models.inference import InferencePurpose
from src.models.task import TaskState
from src.services.inference_service import InferenceService


class InterpretationMethod(str, Enum):
    """How the state was determined."""

    REGEX = "regex"
    LLM = "llm"


@dataclass
class InterpretationResult:
    """Result of state interpretation."""

    state: TaskState
    confidence: float  # 0.0 to 1.0
    method: InterpretationMethod
    raw_content_snippet: str | None = None  # Truncated content for debugging


class StateInterpreter:
    """Interprets terminal content to determine Claude Code session state.

    Uses a two-tier approach:
    1. Regex fast-path for obvious states (high confidence, no LLM call)
    2. LLM-based interpretation for ambiguous content (via InferenceService)

    The InferenceService handles caching with 30s TTL for DETECT_STATE purpose.
    """

    # Spinner patterns indicating PROCESSING state
    SPINNER_CHARS = "⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿"

    # Regex patterns for fast-path detection
    PROCESSING_PATTERNS = [
        # Spinner in content
        re.compile(rf"[{re.escape(SPINNER_CHARS)}]"),
        # "esc to interrupt" prompt
        re.compile(r"\(esc to interrupt\)", re.IGNORECASE),
        # Active tool execution indicators
        re.compile(r"Running:?\s+\w+", re.IGNORECASE),
        re.compile(r"Executing:?\s+", re.IGNORECASE),
    ]

    COMPLETE_PATTERNS = [
        # Completion marker with duration
        re.compile(r"[✻✓]\s*\w+.*for\s+\d+[ms]\s*\d*[sm]?", re.IGNORECASE),
        # Success indicator
        re.compile(r"Completed\s+in\s+\d+", re.IGNORECASE),
    ]

    AWAITING_INPUT_PATTERNS = [
        # Direct question prompts
        re.compile(r"\?\s*$"),
        # Permission requests
        re.compile(r"Do you want to\s+", re.IGNORECASE),
        re.compile(r"Should I\s+", re.IGNORECASE),
        # Y/N prompts
        re.compile(r"\[y/n\]", re.IGNORECASE),
        re.compile(r"\(yes/no\)", re.IGNORECASE),
    ]

    # State detection prompt for LLM
    STATE_DETECTION_PROMPT = """You are analyzing terminal output from a Claude Code session.
Determine which state the session is in based on the content.

STATES:
- IDLE: No active task, waiting for user to start something. Clean prompt, no activity.
- COMMANDED: User has just sent a command, Claude is about to process it.
- PROCESSING: Claude is actively working - you see spinners, tool execution, or thinking indicators.
- AWAITING_INPUT: Claude is asking a question or needs user confirmation to continue.
- COMPLETE: Claude has finished a task - look for completion markers like checkmarks or "Completed in X".

TERMINAL CONTENT:
```
{content}
```

Respond with JSON:
{{"state": "IDLE|COMMANDED|PROCESSING|AWAITING_INPUT|COMPLETE", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""

    def __init__(self, inference_service: InferenceService | None = None):
        """Initialize the StateInterpreter.

        Args:
            inference_service: Service for LLM calls. If not provided, creates one.
        """
        self._inference_service = inference_service or InferenceService()

    def interpret(self, terminal_content: str) -> InterpretationResult:
        """Interpret terminal content to determine session state.

        Args:
            terminal_content: The terminal output to analyze.

        Returns:
            InterpretationResult with state, confidence, and method.
        """
        if not terminal_content or not terminal_content.strip():
            return InterpretationResult(
                state=TaskState.IDLE,
                confidence=0.5,
                method=InterpretationMethod.REGEX,
                raw_content_snippet=None,
            )

        # Try regex fast-path first
        result = self._try_regex_fast_path(terminal_content)
        if result:
            return result

        # Fall back to LLM interpretation
        return self._interpret_with_llm(terminal_content)

    def _try_regex_fast_path(self, content: str) -> InterpretationResult | None:
        """Try to determine state using regex patterns.

        Args:
            content: Terminal content to analyze.

        Returns:
            InterpretationResult if high-confidence match found, None otherwise.
        """
        snippet = content[-500:] if len(content) > 500 else content

        # Check PROCESSING patterns (highest priority - active work)
        for pattern in self.PROCESSING_PATTERNS:
            if pattern.search(content):
                return InterpretationResult(
                    state=TaskState.PROCESSING,
                    confidence=0.9,
                    method=InterpretationMethod.REGEX,
                    raw_content_snippet=snippet,
                )

        # Check AWAITING_INPUT patterns
        # Only check the last portion of content (recent output matters most)
        recent_content = content[-200:] if len(content) > 200 else content
        for pattern in self.AWAITING_INPUT_PATTERNS:
            if pattern.search(recent_content):
                return InterpretationResult(
                    state=TaskState.AWAITING_INPUT,
                    confidence=0.85,
                    method=InterpretationMethod.REGEX,
                    raw_content_snippet=snippet,
                )

        # Check COMPLETE patterns
        for pattern in self.COMPLETE_PATTERNS:
            if pattern.search(recent_content):
                return InterpretationResult(
                    state=TaskState.COMPLETE,
                    confidence=0.9,
                    method=InterpretationMethod.REGEX,
                    raw_content_snippet=snippet,
                )

        # No high-confidence match
        return None

    def _interpret_with_llm(self, content: str) -> InterpretationResult:
        """Use LLM to interpret terminal content.

        Args:
            content: Terminal content to analyze.

        Returns:
            InterpretationResult based on LLM analysis.
        """
        # Truncate content for LLM (keep most recent)
        max_content_length = 2000
        truncated = content[-max_content_length:] if len(content) > max_content_length else content
        snippet = truncated[-500:]

        prompt = self.STATE_DETECTION_PROMPT.format(content=truncated)

        inference_call = self._inference_service.call(
            purpose=InferencePurpose.DETECT_STATE,
            input_data={"terminal_content": truncated},
            user_prompt=prompt,
        )

        # Parse the LLM response
        result = inference_call.result
        if "error" in result:
            # LLM call failed, return conservative default
            return InterpretationResult(
                state=TaskState.IDLE,
                confidence=0.3,
                method=InterpretationMethod.LLM,
                raw_content_snippet=snippet,
            )

        # Parse the state from LLM response
        state_str = result.get("state", "IDLE").upper()
        confidence = float(result.get("confidence", 0.5))

        # Map string to TaskState
        state_mapping = {
            "IDLE": TaskState.IDLE,
            "COMMANDED": TaskState.COMMANDED,
            "PROCESSING": TaskState.PROCESSING,
            "AWAITING_INPUT": TaskState.AWAITING_INPUT,
            "COMPLETE": TaskState.COMPLETE,
        }
        state = state_mapping.get(state_str, TaskState.IDLE)

        return InterpretationResult(
            state=state,
            confidence=confidence,
            method=InterpretationMethod.LLM,
            raw_content_snippet=snippet,
        )
