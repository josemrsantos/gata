from __future__ import annotations

import anthropic

from core.types import TokenUsage
from llm.base import LLMProvider

_COST_PER_M: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6":         (3.00,  15.00),
    "claude-opus-4-8":           (15.00, 75.00),
    "claude-opus-4-7":           (15.00, 75.00),
    "claude-sonnet-4-5":         (3.00,  15.00),
    "claude-haiku-4-5-20251001": (0.80,   4.00),
}

_client: anthropic.Anthropic | None = None


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str) -> None:
        self._model = model

    @property
    def model_id(self) -> str:
        return self._model

    def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> tuple[str, TokenUsage]:
        global _client
        if _client is None:
            _client = anthropic.Anthropic()
        response = _client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        if not response.content:
            raise RuntimeError(
                f"Claude returned empty content list for model {self._model}"
            )
        text = response.content[0].text
        in_tok = getattr(response.usage, "input_tokens", 0) or 0
        out_tok = getattr(response.usage, "output_tokens", 0) or 0
        rates = _COST_PER_M.get(self._model, (0.0, 0.0))
        cost = (in_tok * rates[0] + out_tok * rates[1]) / 1_000_000
        return text, TokenUsage(
            model=self._model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
        )
