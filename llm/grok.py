from __future__ import annotations

import os

import openai

from core.types import TokenUsage
from llm.base import LLMProvider

_COST_PER_M: dict[str, tuple[float, float]] = {
    "grok-3": (3.00, 15.00),
    "grok-3-mini": (0.30, 0.50),
    "grok-3-fast": (5.00, 25.00),
    "grok-3-mini-fast": (0.60, 4.00),
}

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI(
            api_key=os.environ["XAI_API_KEY"],
            base_url="https://api.x.ai/v1",
        )
    return _client


class GrokProvider(LLMProvider):
    def __init__(self, model: str, timeout: float | None = None) -> None:
        self._model = model
        self._timeout = timeout

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def timeout(self) -> float | None:
        return self._timeout

    def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> tuple[str, TokenUsage]:
        client = _get_client()
        full_messages = [{"role": "system", "content": system_prompt}, *messages]
        response = client.chat.completions.create(
            model=self._model,
            messages=full_messages,
            max_tokens=max_tokens,
        )
        if not response.choices:
            raise RuntimeError(
                f"Grok returned empty choices list for model {self._model}"
            )
        text = response.choices[0].message.content
        if not text:
            # None content (tool_use only response) must raise so the fallback
            # chain tries the next provider instead of passing "" downstream.
            raise RuntimeError(
                f"GrokProvider: empty response content for model {self._model}"
            )
        usage = response.usage
        in_tok = getattr(usage, "prompt_tokens", 0) or 0
        out_tok = getattr(usage, "completion_tokens", 0) or 0
        rates = _COST_PER_M.get(self._model, (0.0, 0.0))
        cost = (in_tok * rates[0] + out_tok * rates[1]) / 1_000_000
        return text, TokenUsage(
            model=self._model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
        )
