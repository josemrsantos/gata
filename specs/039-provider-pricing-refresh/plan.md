# Implementation Plan: Provider Pricing & Model Currency Refresh

**Branch**: `039-provider-pricing-refresh` | **Date**: 2026-07-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/039-provider-pricing-refresh/spec.md`

## Summary

Correct the three `_COST_PER_M` pricing tables (`llm/claude.py`, `llm/gemini.py`,
`llm/grok.py`) against each provider's live official pricing, and replace three
confirmed-dead/retired default model IDs (`grok-3`, `grok-3-mini`,
`gemini-2.0-flash`) with their live equivalents (`grok-4.3`, `grok-build-0.1`,
`gemini-2.5-flash-lite`) across `providers.yaml`, `core/runner.py`, and
`core/bundle_writer.py`. A live API smoke test (2026-07-27, see `research.md`)
confirmed `grok-3` and `grok-3-mini` both now silently redirect to and bill as
`grok-4.3` — the same model — which had quietly collapsed the aggregator-vs-panelist
distinction from Spec 029. The key architectural decision is to keep the retired
Grok slugs in `_COST_PER_M` as priced aliases (at the rate they now actually bill)
rather than delete them, so a leftover custom `providers.yaml` still gets a correct
cost instead of a silent `$0.00`.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `anthropic`, `openai` (Grok), `google-genai` — unchanged, no new dependencies
**Storage**: None — no new files on disk (spec artifacts only)
**Testing**: pytest with mocks (no real API calls in the test suite per Constitution §9; the live verification calls in `research.md` were a one-off manual planning step, not a test)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — configuration/pricing correction; no new agents, protocols, or files
**Performance Goals**: No regression expected; `grok-build-0.1` is xAI's code-oriented cheap tier and may have different latency than the old `grok-3-mini`, but Spec 036 per-provider timeouts already absorb per-model latency variance
**Constraints**: `ruff check .` must exit 0; `ruff format .` on all modified files; RULE 17 doc-sync gate (CHANGELOG/README/architecture.md) before merge; RULE 15 version bump before push
**Scale/Scope**: Medium — 3 provider modules, `providers.yaml`, 3 default-chain call sites, 1 constitution amendment, README/architecture/CHANGELOG sync, and every test asserting a now-changed model ID or price

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ⚠️ | §1 names `grok-3` as Grok's "primary model" — **amendment required** (see Complexity Tracking). Gemini/Claude lines in §1 are untouched: `gemini-2.5-flash`/`gemini-2.5-pro` stay primary, `gemini-3.1-flash-image-preview` stays the image model, `claude-sonnet-4-6` stays Claude's primary model |
| 2 | Image Output Rule | ✅ | Image generation untouched |
| 3 | XML and Output Contract | ✅ | `<verdict>` tags untouched |
| 4 | Character Rules | ✅ | Gata description untouched |
| 5 | Visual Style Rules | ✅ | Image prompts untouched |
| 6 | Verdict JSON Schema and Iteration Rules | ⚠️ | §6 names `grok-3` as aggregator and `grok-3-mini` as panelist by string — **amendment required** (see Complexity Tracking) |
| 7 | Language Rule | ✅ | Unaffected |
| 8 | Project Structure | ✅ | No new directories or packages; all changes are edits to existing files |
| 9 | Testing Rules | ✅ | Existing tests updated to match new model IDs/prices; TDD order followed in tasks.md (failing assertions fixed before/alongside the production edit they cover); zero real API calls inside the pytest suite |
| 10 | Secrets and Security | ✅ | No new secrets. The one live API call made during planning (`research.md`) used existing `XAI_API_KEY` via `source set_gata.sh`, was read-only, and is not part of the committed test suite |
| 11 | Development Stages | ✅ | Branch `039-provider-pricing-refresh`, off `main` |
| 12 | Code Quality | ✅ | `ruff check .` / `ruff format .` on all modified files before commit |
| 13 | Logging | ✅ | No new log call sites needed; existing cost/model logging already carries model name and cost |

**Constitution Check result**: 2 violations — §1 and §6 require amendment (approved below).

## Project Structure

### Documentation (this feature)

```text
specs/039-provider-pricing-refresh/
├── plan.md      (this file)
├── spec.md
├── research.md
└── tasks.md     (Phase 2 output)
```

### Source Code Changes

```text
llm/claude.py                        MODIFY — fix claude-opus-4-7/4-8 (5,25 not 15,75) and claude-haiku-4-5 (1,5 not 0.8,4) rates; add claude-sonnet-5 and claude-opus-5 entries
llm/gemini.py                        MODIFY — fix gemini-3.1-flash-lite (0.25,1.50) and gemini-3.1-pro-preview (2,12 tiered) rates; remove gemini-2.0-flash entry (dead, no longer referenced anywhere after this change)
llm/grok.py                          MODIFY — add grok-4.5/grok-4.3/grok-build-0.1 at real rates; reprice grok-3/grok-3-mini/grok-3-fast/grok-3-mini-fast to the grok-4.3 rate (confirmed live redirect target) instead of their old individual rates
providers.yaml                       MODIFY — default aggregator grok-3 → grok-4.3; default panelist grok-3-mini → grok-build-0.1 (both panelist slots that use it); timeout comment block's example model names updated to match (no gemini-2.0-flash reference exists in this file — only core/runner.py and agent_cultural_strategist.py have that one)
core/runner.py                       MODIFY — _PARALLEL_PANELISTS (grok-3-mini → grok-build-0.1), _GEMINI_PRO_CHAIN (last entry gemini-2.0-flash → gemini-2.5-flash-lite; also feeds _GEMINI_EVAL_CHAIN alias), _GROK_AGGREGATOR (grok-3 → grok-4.3) — three swaps for the built-in-default code path
core/bundle_writer.py                MODIFY — its hardcoded HTML-fallback defaults only reference Grok (no gemini-2.0-flash here): grok-3-mini → grok-build-0.1, grok-3 → grok-4.3
agents/agent_cultural_strategist.py  MODIFY — _INFERENCE_MODELS: gemini-2.0-flash → gemini-2.5-flash-lite
.specify/memory/constitution.md      MODIFY — §1 amendment (Grok primary model grok-3 → grok-4.3); §6 amendment (aggregator grok-3 → grok-4.3, panelist grok-3-mini → grok-build-0.1); version bump + amendment record per Amendment Procedure step 4
README.md                            MODIFY — providers.yaml example block, agent table if it names specific models (RULE 17 gate)
docs/architecture.md                 MODIFY — diagrams/examples naming grok-3, grok-3-mini, gemini-2.0-flash (RULE 17 gate)
CHANGELOG.md                         MODIFY — new version entry describing the pricing fix + model swap (RULE 17 gate)
pyproject.toml, core/__version__.py  MODIFY — version bump per RULE 15 (exact bump decided in tasks.md; existing pyproject.toml/core/__version__.py mismatch — 1.19.0 vs 1.20.0 — is pre-existing and out of scope for this spec, flagged separately)
tests/test_grok_provider.py          MODIFY — cost-table expectations for all grok-* entries
tests/test_providers_config.py       MODIFY — any fixture/assertion tied to the production default chain (grok-3/grok-3-mini as *defaults*, not as arbitrary YAML-parsing example strings)
tests/test_agent_satirist.py         MODIFY — assertions that _PARALLEL_PANELISTS contains grok-3-mini and _GROK_AGGREGATOR contains grok-3
tests/*                              MODIFY (audit) — any other test asserting a specific stale price or a now-dead model ID as a production default; found via `grep -rn "grok-3\b\|gemini-2.0-flash" tests/`
```

**Structure Decision**: All changes are edits to existing files; no new modules. This
is a correction/currency pass, not a feature addition, so it stays entirely within
the existing `llm/`, `core/`, `agents/` structure per Constitution §8.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| §1 — "[Grok] primary model `grok-3`" must change to `grok-4.3` | `grok-3` is confirmed retired (live API check, `research.md`): it silently redirects to `grok-4.3` today. Leaving the constitution text as `grok-3` would document a model that no longer independently exists, and the spec's whole point is to stop relying on that redirect | Leaving §1 unamended and only fixing the code would make the constitution actively wrong about the SDK/model rule it's supposed to be the source of truth for |
| §6 — "Grok (`grok-3`) is the aggregator... Grok-3-mini participates as panelist" must change to `grok-4.3` (aggregator) / `grok-build-0.1` (panelist) | Same retirement fact, plus a second reason: the live check showed `grok-3` and `grok-3-mini` now redirect to the *same* model (`grok-4.3`), which silently defeats §6's own stated design intent that the panelist and aggregator not be the same model ("not both judge and sole proposer"). Restoring that distinction requires the panelist to name a genuinely different live model | Keeping `grok-3-mini` as the panelist string would look unchanged in the diff but silently run as `grok-4.3` under the hood — the same model as the aggregator — reintroducing the exact problem Spec 029 was written to avoid, just invisibly |

**Amendment** (pending explicit approval below, per Amendment Procedure step 3).
§6 currently names the old models in three places; all three change together:

- §1: `Grok SDK: ... primary model \`grok-3\`` → `primary model \`grok-4.3\``.
- §6, bullet "Grok (`grok-3`) is the aggregator/decider...": `Grok (\`grok-3\`) is
  the aggregator/decider across all \`ParallelPanel\` agents. Grok-3-mini
  participates as panelist alongside Claude and Gemini.` → `Grok (\`grok-4.3\`) is
  the aggregator/decider across all \`ParallelPanel\` agents. Grok's
  \`grok-build-0.1\` participates as panelist alongside Claude and Gemini, kept
  deliberately distinct from the aggregator model.` (rest of that bullet, on the
  Final Say Protocol, is unchanged).
- §6, closing bullet on ParallelPanel topology: `(Claude + Grok-mini + Gemini as
  independent panelists; Grok-3 as aggregator)` → `(Claude + grok-build-0.1 +
  Gemini as independent panelists; grok-4.3 as aggregator)`.

Version/record: bump constitution to v1.1, dated 2026-07-27, with an amendment-log
line noting "Spec 039 — Grok default models updated from grok-3/grok-3-mini
(confirmed retired, redirecting to grok-4.3) to grok-4.3/grok-build-0.1."
