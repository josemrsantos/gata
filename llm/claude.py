from __future__ import annotations

import logging

import anthropic

from core.types import TokenUsage
from llm.base import LLMProvider

# Published rates in USD per million input/output tokens, verified against
# Anthropic's pricing page on 2026-10-04 (Spec 054). Lookups are exact-string, so
# a model with both a dateless alias and a dated ID needs a row for each. Mythos
# models are invitation-only and deliberately not priced.
_COST_PER_M: dict[str, tuple[float, float]] = {
    "claude-fable-5-1": (10.00, 50.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-opus-4-5-20251101": (5.00, 25.00),
    "claude-opus-4-5": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
}

logger = logging.getLogger(__name__)

# Panelists request low effort (spec 054 amendment A): Claude 5 models decide per
# request whether to think, and on real panel prompts Sonnet 5.5 spent 500-900
# thinking tokens (about half its output) while Opus 5.5 always thinks. Low effort
# removed the thinking in every measured Sonnet 5.5 call and cut output to ~700 tokens.
PANELIST_CLAUDE_EFFORT = "low"

# Models that accept output_config.effort among the ones we run. Others (for example
# Haiku 4.5) reject the field, so the setting is silently not sent to them.
_EFFORT_MODELS = frozenset(
    {"claude-sonnet-5-5", "claude-opus-5-5", "claude-sonnet-5", "claude-opus-5"}
)

_client: anthropic.Anthropic | None = None


class ClaudeProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        timeout: float | None = None,
        effort: str | None = None,
    ) -> None:
        self._model = model
        self._timeout = timeout
        # Only models that support effort keep the setting; for the rest it is None.
        self._effort = effort if model in _EFFORT_MODELS else None

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def timeout(self) -> float | None:
        return self._timeout

    @property
    def effort(self) -> str | None:
        return self._effort

    @property
    def client(self) -> anthropic.Anthropic:
        # Exposes the underlying client for agents that need special Claude config
        # (e.g. web search tool use) not expressible via generate() — mirrors
        # GeminiProvider.client (Spec 042 FR-002).
        global _client
        if _client is None:
            _client = anthropic.Anthropic()
        return _client

    def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> tuple[str, TokenUsage]:
        global _client
        if _client is None:
            _client = anthropic.Anthropic()
        request = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        if self._effort:
            request["extra_body"] = {"output_config": {"effort": self._effort}}
        response = _client.messages.create(**request)
        if not response.content:
            raise RuntimeError(
                f"Claude returned empty content list for model {self._model}"
            )
        in_tok = getattr(response.usage, "input_tokens", 0) or 0
        out_tok = getattr(response.usage, "output_tokens", 0) or 0
        rates = _COST_PER_M.get(self._model, (0.0, 0.0))
        cost = (in_tok * rates[0] + out_tok * rates[1]) / 1_000_000
        # Claude 5 models may start a reply with a thinking block, so the answer is
        # the text blocks, not simply the first block.
        text = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        stop_reason = getattr(response, "stop_reason", None)
        if not text:
            raise RuntimeError(
                f"Claude returned no text block for model {self._model}"
                f" (stop_reason={stop_reason}, output_tokens={out_tok},"
                f" ~${cost:.4f} billed)"
            )
        if stop_reason == "max_tokens":
            logger.warning(
                "claude: %s reply hit max_tokens=%d (output_tokens=%d) — thinking"
                " shares this budget, so the answer may be truncated",
                self._model,
                max_tokens,
                out_tok,
            )
        return text, TokenUsage(
            model=self._model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
        )
