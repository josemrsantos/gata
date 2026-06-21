# Feature Specification: Grok Integration — xAI Grok as Third LLM Provider

**Spec**: `025-grok-integration`
**Created**: 2026-06-21
**Status**: Draft

## Problem

The pipeline currently uses two LLM providers (Claude, Gemini). The Co-Satirist
role is filled entirely by Gemini, which means creative critique comes from a
single model family. Adding Grok as Co-Satirist primary brings a distinct voice
(irreverent, culture-aware) to the review loop and adds provider redundancy.

## Goal

Add xAI's Grok as a third LLM provider via a new `llm/grok.py` file and wire
it into `core/runner.py` as the Co-Satirist primary, with Gemini Flash / Pro as
fallback. No agent code changes required.

## Implementation

### `llm/grok.py` — GrokProvider

xAI's API is OpenAI-compatible. `GrokProvider` uses the `openai` Python SDK
with `base_url="https://api.x.ai/v1"` and `api_key` from the `XAI_API_KEY`
environment variable.

```python
class GrokProvider(LLMProvider):
    def __init__(self, model: str) -> None: ...

    @property
    def model_id(self) -> str: ...

    def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> tuple[str, TokenUsage]: ...
```

Cost table (rates per million tokens, input/output):

| Model | Input | Output |
|---|---|---|
| `grok-3` | $3.00 | $15.00 |
| `grok-3-mini` | $0.30 | $0.50 |
| `grok-3-fast` | $5.00 | $25.00 |
| `grok-3-mini-fast` | $0.60 | $4.00 |

Client is lazily initialised on first `generate()` call (same pattern as
`ClaudeProvider`). Module-level singleton so repeated calls share one connection.

### `pyproject.toml`

Add `openai` to `dependencies`.

### `llm/__init__.py`

Export `GrokProvider`.

### `core/runner.py`

Replace `_GEMINI_FLASH_CHAIN` (used for Co-Satirist) with a new
`_GROK_CO_SATIRIST_CHAIN`:

```python
_GROK_CO_SATIRIST_CHAIN = [
    GrokProvider("grok-3"),
    GeminiProvider("gemini-2.5-flash"),
    GeminiProvider("gemini-2.0-flash"),
]
```

Wire it into `agent_satirist.run(co_satirist_providers=_GROK_CO_SATIRIST_CHAIN)`.

`_GEMINI_FLASH_CHAIN` is no longer referenced once Co-Satirist is switched —
remove it to avoid dead code.

## Tests

New file `tests/test_grok_provider.py`:
- Happy path: `generate()` returns `(str, TokenUsage)` with correct cost
- Empty content guard: raises `RuntimeError` if API returns no choices
- Token usage: input/output tokens correctly extracted from response
- Cost calculation: correct for known model rates
- Unknown model: cost defaults to 0.0
- Model fallback via DualPersonaLoop: GrokProvider failure falls through to next provider
- `model_id` property returns the model string

`tests/test_pipeline.py`: update `_GEMINI_FLASH_CHAIN` references to
`_GROK_CO_SATIRIST_CHAIN` where the Co-Satirist mock target changes.

## Scope

- Does **not** change any agent logic or system prompts.
- Does **not** change the public CLI interface.
- Does **not** add Grok to any role other than Co-Satirist.
- Image generation remains Gemini-only (out of scope per spec 024).

## Verification

- All existing tests pass.
- `gata "some topic"` runs end-to-end; telemetry shows a Grok call for the
  Co-Satirist turn.
- `python pipeline.py` also runs end-to-end successfully.
