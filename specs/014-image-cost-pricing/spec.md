# Feature Specification: Image Generation Cost Pricing Fix

**Feature Branch**: `015-image-cost-pricing`
**Created**: 2026-06-16
**Status**: Draft

## Summary

`agent_image_generator.generate()` hardcodes `output_tokens=0` for every image call, and
`_COST_PER_M` prices all five image models at `(0.0, 0.0)`. Together these mean the Image
Generator's line in `summary.txt` / `telemetry.json` always reports `$0.0000`, even though
image generation is the single largest real cost in a run. This stage records the actual
output token count Gemini bills for the generated image and prices the five image models
against verified official rates, so the run summary reflects real spend.

## Why now

The user is preparing an announcement post for this project and wants the price/time summary
(shipped in `012-run-summary`) to be accurate. Image generation cost being silently $0.00 in
every reported total defeats the purpose of that feature.

## Source of pricing data

Verified directly against `https://ai.google.dev/gemini-api/docs/pricing` (fetched 2026-06-16):

| Model | Input $/1M tokens | Output $/1M tokens | Notes |
|---|---|---|---|
| `gemini-3.1-flash-image` | 0.50 | 60.00 | 1120 tokens/image at 1K resolution → ~$0.067/image |
| `gemini-3-pro-image` | 2.00 | 120.00 | 1120 tokens/image at 1K resolution → ~$0.134/image |
| `gemini-2.5-flash-image` | 0.30 | — | Billed flat at $0.039/image (legacy, not token-rate) |

The `-preview` aliases (`gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`) used as
the first two entries in `_MODELS` are **not listed** on the official pricing page at all.
Since they are preview aliases of the listed GA models and the user's independently-sourced
Gemini pricing answer quotes identical per-image figures for the preview names ($0.067 / $0.134
at 1K, matching the GA math above), this stage prices the preview aliases identically to their
GA counterparts. This is a reasonable approximation, not a guarantee — flagged in a code
comment so it's easy to revisit if Google's preview pricing ever diverges.

`gemini-2.5-flash-image` is a legacy model billed as a flat per-image fee rather than a
token rate (scheduled shutdown 2026-10-02, per Google's docs). To fit it into the existing
`compute_cost(model, input_tokens, output_tokens)` token-rate architecture without adding a
second pricing code path, this stage derives an equivalent output rate from the documented
1290-token image size: `0.039 / 1290 * 1_000_000 ≈ $30.23/1M`. This reproduces the documented
$0.039/image as long as the model continues to bill at 1290 tokens/image.

## User Scenarios & Testing

### User Story 1 — Image Generator cost is non-zero (Priority: P1)

Running the pipeline produces a `summary.txt` / `telemetry.json` where the Image Generator's
`cost_usd` reflects real spend instead of `$0.0000`.

**Acceptance Scenarios**:

1. **Given** a successful image generation call, **When** the response's `usage_metadata`
   includes a `candidates_token_count`, **Then** `TokenUsage.output_tokens` for that call is
   set from it (not hardcoded to 0).
2. **Given** the same call, **When** cost is computed, **Then** `compute_cost()` uses the
   model's real per-token rate from `_COST_PER_M`, producing a `cost_usd > 0`.
3. **Given** `usage_metadata` is absent or missing `candidates_token_count` (defensive case,
   mirrors existing `dual_loop.py` guard), **Then** `output_tokens` defaults to `0` rather than
   raising.

### Edge Cases

- A model not in `_COST_PER_M` (e.g. a future fallback model) still defaults to `(0.0, 0.0)`
  via the existing `compute_cost()` unknown-model fallback — unchanged behavior.

## Technical Design

### `agents/types.py`

Replace the five `(0.0, 0.0)` image-model entries in `_COST_PER_M` with:

```python
"gemini-3.1-flash-image-preview": (0.50,  60.00),
"gemini-3.1-flash-image":         (0.50,  60.00),
"gemini-3-pro-image-preview":     (2.00, 120.00),
"gemini-3-pro-image":             (2.00, 120.00),
"gemini-2.5-flash-image":         (0.30,  30.23),
```

### `agents/agent_image_generator.py`

Mirror the existing `dual_loop.py` pattern for reading output tokens:

```python
meta = getattr(response, "usage_metadata", None)
in_tok = getattr(meta, "prompt_token_count", 0) or 0
out_tok = getattr(meta, "candidates_token_count", 0) or 0
token_calls.append(TokenUsage(
    model=model,
    input_tokens=in_tok,
    output_tokens=out_tok,
    cost_usd=compute_cost(model, in_tok, out_tok),
))
```

### Modified files

| File | Change |
|------|--------|
| `agents/types.py` | Real per-token rates for the 5 image models in `_COST_PER_M` |
| `agents/agent_image_generator.py` | Read `candidates_token_count` instead of hardcoding 0 |
| `pyproject.toml` | Bump version to `1.5.1` |
| `agents/__version__.py` | Bump to `1.5.1` |
| `tests/test_agent_image_generator.py` | Cover non-zero cost computation |
