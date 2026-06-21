from __future__ import annotations

from google import genai
from google.genai import types as genai_types

from core.types import TokenUsage
from llm.base import LLMProvider

_COST_PER_M: dict[str, tuple[float, float]] = {
    "gemini-2.5-pro":       (1.25,  10.00),
    "gemini-2.5-flash":     (0.30,   2.50),
    "gemini-2.0-flash":     (0.10,   0.40),
    "gemini-3.1-flash-lite":(0.10,   0.40),
    "gemini-3.1-pro-preview":(1.25, 10.00),
    # Image model rates (per-million token equivalent; see spec 014)
    "gemini-3.1-flash-image-preview": (0.50,  60.00),
    "gemini-3.1-flash-image":         (0.50,  60.00),
    "gemini-3-pro-image-preview":     (2.00, 120.00),
    "gemini-3-pro-image":             (2.00, 120.00),
    "gemini-2.5-flash-image":         (0.30,  30.23),
}

_client: genai.Client | None = None


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated USD cost for one Gemini call; unknown models cost 0.0."""
    rates = _COST_PER_M.get(model, (0.0, 0.0))
    return (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


def get_gemini_client() -> genai.Client:
    """Return the shared Gemini client, initialising it on first call."""
    return _get_client()


class GeminiProvider(LLMProvider):
    def __init__(self, model: str) -> None:
        self._model = model

    @property
    def model_id(self) -> str:
        return self._model

    def compute_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return estimated USD cost for this model; unknown models cost 0.0."""
        return compute_cost(self._model, input_tokens, output_tokens)

    @property
    def client(self) -> genai.Client:
        # Exposes the underlying client for agents that need special Gemini config
        # (e.g. search grounding, image evaluation) not expressible via generate().
        return _get_client()

    def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> tuple[str, TokenUsage]:
        client = _get_client()
        prompt = "\n\n".join(
            f"{'Assistant' if m['role'] == 'assistant' else 'User'}: {m['content']}"
            for m in messages
        )
        response = client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
                temperature=0.2,
            ),
        )
        meta = getattr(response, "usage_metadata", None)
        in_tok = getattr(meta, "prompt_token_count", 0) or 0
        out_tok = getattr(meta, "candidates_token_count", 0) or 0
        cost = self.compute_cost(in_tok, out_tok)
        return response.text, TokenUsage(
            model=self._model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
        )
