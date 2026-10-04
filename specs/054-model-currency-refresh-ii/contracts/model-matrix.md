# Contract: default model matrix (before → after)

This is the observable contract of the feature: which models an operator gets
with no `providers.yaml` override, and which rates the cost report uses. The
`providers.yaml` schema (keys, structure, `timeout` field) is **unchanged**.
Rationale for every row is in `../research.md`. Live check 2026-10-04 settled the Gemini rows: Flash HOLD (unchanged `gemini-2.5-flash`), Flash-Lite GO (`gemini-3.5-flash-lite`).

## 1. Provider chains (order kept — FR-003)

| Location | Before | After |
|---|---|---|
| `providers.yaml` panelist 1 | claude-sonnet-4-6 → gemini-2.5-flash → grok-build-0.1 | claude-sonnet-5-5 → gemini-2.5-flash → grok-build-0.1 |
| `providers.yaml` panelist 2 | grok-build-0.1 → gemini-2.5-flash → claude-haiku-4-5-20251001 | grok-build-0.1 → gemini-2.5-flash → claude-haiku-4-5-20251001 |
| `providers.yaml` panelist 3 | gemini-2.5-flash → grok-build-0.1 → claude-haiku-4-5-20251001 | gemini-2.5-flash → grok-build-0.1 → claude-haiku-4-5-20251001 |
| `providers.yaml` aggregator | grok-4.3 → claude-sonnet-4-6 → gemini-2.5-pro | grok-4.3 (unchanged, approved) → claude-sonnet-5-5 → gemini-2.5-pro (unchanged, preview-only successor) |
| `core/runner.py` `_PARALLEL_PANELISTS` | claude-sonnet-4-6, grok-build-0.1, gemini-2.5-flash | claude-sonnet-5-5, grok-build-0.1, gemini-2.5-flash |
| `core/runner.py` `_GROK_AGGREGATOR` | grok-4.3 | grok-4.3 (unchanged, approved) |
| `core/runner.py` `_CLAUDE_CHAIN` | sonnet-4-6 → opus-4-7 → haiku-4-5-20251001 | sonnet-5-5 → opus-5-5 → haiku-4-5-20251001 |
| `core/runner.py` `_GEMINI_PRO_CHAIN` (= `_GEMINI_EVAL_CHAIN`) | 2.5-pro → 2.5-flash → 2.5-flash-lite | 2.5-pro (unchanged) → 3.8-flash → 3.5-flash-lite |
| `core/bundle_writer.py` fallback defaults | claude-sonnet-4-6 / grok-build-0.1 / gemini-2.5-flash / grok-4.3 | claude-sonnet-5-5 / grok-build-0.1 / gemini-2.5-flash / grok-4.3 |
| `core/newsletter_merge.py` panelists + aggregator | same trio as `_PARALLEL_PANELISTS` | same trio as the updated `_PARALLEL_PANELISTS` |
| `core/newsletter_merge.py` `_GEMINI_TEXT_MODELS` | 2.5-flash-lite, 3.1-flash-lite, 2.5-flash, 2.5-pro, 3.1-pro-preview | 3.5-flash-lite, 3.1-flash-lite, 3.8-flash, 2.5-pro, 3.1-pro-preview |
| `core/newsletter_merge.py` `_CLAUDE_MODELS` | haiku-4-5-20251001, sonnet-4-6, opus-4-7 | haiku-4-5-20251001, sonnet-5-5, opus-5-5 |
| `core/newsletter_merge.py` `_GROK_MODELS` | grok-build-0.1, grok-4.3, grok-4.5 | unchanged |
| `agents/agent_cultural_strategist.py` `_INFERENCE_MODELS` | 2.5-flash, 2.5-pro, 2.5-flash-lite | 3.8-flash, 2.5-pro, 3.5-flash-lite |
| `agents/trend_scout.py` `_GEMINI_MODEL` | gemini-2.5-flash | gemini-2.5-flash |
| `core/image_generation.py` `_MODELS` | 3.1-flash-image-preview → 3.1-flash-image → 3-pro-image-preview → 3-pro-image → 2.5-flash-image | 3.1-flash-image → 3-pro-image |

## 2. Cost tables ($ per million tokens, input / output)

| File | Change |
|---|---|
| `llm/claude.py` | ADD claude-sonnet-5-5 2.00/10.00; claude-opus-5-5 4.00/20.00; claude-opus-4-6 5.00/25.00; claude-opus-4-5-20251101 and claude-opus-4-5 5.00/25.00; claude-sonnet-4-5-20250929 3.00/15.00; claude-fable-5-1 and claude-fable-5 10.00/50.00. FIX claude-sonnet-5 3.00/15.00 → 2.00/10.00. KEEP claude-sonnet-4-5 (alias), claude-sonnet-4-6, claude-opus-4-7 / 4-8 / 5, claude-haiku-4-5-20251001. NOT priced: Mythos models (invitation-only). Result: every non-retired, generally available model on Anthropic's pricing page has a row. |
| `llm/gemini.py` | ADD gemini-3.8-flash 0.75/3.75 (promo to 2026-12-31, then 1.50/7.50 — note in a code comment; priced, not a default), gemini-3.5-flash-lite 0.30/2.50, gemini-3.5-flash 1.50/9.00. KEEP gemini-3.1-flash-image-preview, gemini-3-pro-image-preview, gemini-2.5-flash-image: docs say shut down but live calls still succeed, so they are still-billed names (FR-005); they leave the image chain only. KEEP 2.5-pro/-flash/-flash-lite, 3.1-flash-lite, 3.1-pro-preview, 3.1-flash-image (0.50/60.00), 3-pro-image (2.00/120.00). |
| `llm/grok.py` | ADD grok-4.6, grok-4.7 2.00/6.00. KEEP 4.5, 4.3, build-0.1. The `grok-3*` aliases follow the live check (research D-X4). |

## 3. `providers.yaml` comment block

Recommended-timeout comments are carried over unchanged to each successor
(claude-sonnet-5-5: 25.0, gemini-2.5-flash: 15.0; others unchanged). No timeout
is enabled by default (FR-006).

## 4. Invariants (tested)

- Every default model is in its provider's price table.
- No retired name appears in any default chain.
- Grok panelist ≠ Grok aggregator (constitution §6).
- Provider order inside each chain is unchanged from `main`.
