# Implementation Plan: Model currency refresh II

**Branch**: `054-model-currency-refresh-ii` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/054-model-currency-refresh-ii/spec.md`

## Summary

Replace stale default models, fallback-chain entries and price-table rows for
Claude, Gemini and Grok with the current ones, verified against each provider's
official documentation on 2026-10-04 and confirmed with one short real call per
distinct default model. Policy (from clarification): newest **stable, same-tier**
model; provider order in every chain unchanged; preview-only successors are not
adopted. This is an edit of existing constant tables plus a constitution
amendment — no new runtime code, modules or dependencies. Research and the live checks (2026-10-04) found what makes the refresh
necessary: `claude-sonnet-5` is priced wrong (3/15 vs the official 2/10); the new
Claude defaults have no price entry (cost would report $0); `gemini-2.5-flash-lite`
already returns 404 for our key (Gemini 2.5 is limited to prior users); and the
image chain's `-preview` names are documented as shut down on 2026-06-25 (they
still respond today, so they are replaced to avoid a sudden outage).

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `anthropic`, `google-genai`, `openai` (xAI endpoint) — unchanged; only model-name strings and price tables in `llm/`, `core/`, `agents/` change
**Storage**: none (constants and `providers.yaml`)
**Testing**: pytest with mocks (no real API calls per Constitution §9); the live check is a manual one-off, not a test
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — configuration/data refresh, no behavioural code
**Performance Goals**: none; expected to remove one wasted failing image call per run
**Constraints**: ruff `line-length=88`; model-name changes in §1/§6 require the constitution amendment procedure and the project lead's explicit approval (FR-007)
**Scale/Scope**: ~10 source files, 3 price tables, 1 yaml, constitution §1/§6, 3 docs, affected tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ⚠️ | Same SDKs (no new provider), but §1 hardcodes model names that this stage changes → amendment v1.3, see Complexity Tracking |
| 2 | Image Output Rule | ✅ | Image extraction/atomic write untouched; only the model-name chain shrinks |
| 3 | XML and Output Contract | ✅ | Untouched |
| 4 | Character Rules | ✅ | Untouched |
| 5 | Visual Style Rules | ✅ | Untouched |
| 6 | Verdict JSON Schema and Iteration Rules | ⚠️ | §6 names `grok-4.3` / `grok-build-0.1`; unchanged if D-X2 keeps both. Panelist ≠ aggregator invariant is tested |
| 7 | Language Rule | ✅ | Untouched |
| 8 | Project Structure | ✅ | No new directories or packages |
| 9 | Testing Rules | ✅ | Tests updated first (TDD); zero real calls in the suite; live check is outside it |
| 10 | Secrets and Security | ✅ | Keys from env via `source set_gata.sh`; none written to files |
| 11 | Development Stages | ✅ | Branch `054-model-currency-refresh-ii`; 053 merged; PR to main |
| 12 | Code Quality | ✅ | `ruff check .` / `ruff format` gate in tasks |
| 13 | Logging | ✅ | No new logging; no bare `print()` added |

**Constitution Check result (pre-research)**: 11 pass, 2 flagged (§1, §6) — both
resolved by the single amendment below; no unjustified violation.
**Post-design re-check**: unchanged — Phase 1 design adds no new modules,
interfaces or logging, so no new gate is touched.

## Project Structure

### Documentation (this feature)

```text
specs/054-model-currency-refresh-ii/
├── plan.md
├── spec.md
├── research.md        (Phase 0 — verified models, prices, decisions D-*)
├── data-model.md      (Phase 1)
├── quickstart.md      (Phase 1 — offline + live validation)
├── contracts/
│   └── model-matrix.md  (before → after defaults and price tables)
├── checklists/
│   └── requirements.md
└── tasks.md           (Phase 2 output, via /speckit-tasks)
```

### Source Code Changes

```text
providers.yaml                          MODIFY  built-in defaults + timeout comments (FR-006)
llm/claude.py                           MODIFY  price table: add 5-5/opus-5-5/fable; fix sonnet-5 to 2/10
llm/gemini.py                           MODIFY  price table: add 3.8-flash, 3.5-flash(-lite); drop 3 retired image names
llm/grok.py                             MODIFY  price table: add 4.6/4.7; grok-3 aliases per live check
core/runner.py                          MODIFY  _CLAUDE_CHAIN, _GEMINI_PRO_CHAIN (=eval chain), _PARALLEL_PANELISTS
core/image_generation.py                MODIFY  _MODELS: drop retired previews and 2.5-flash-image
core/bundle_writer.py                   MODIFY  fallback default providers
core/newsletter_merge.py                MODIFY  _GEMINI_TEXT_MODELS, _CLAUDE_MODELS, default panelists
agents/agent_cultural_strategist.py     MODIFY  _INFERENCE_MODELS
agents/trend_scout.py                   MODIFY  _GEMINI_MODEL
.specify/memory/constitution.md         MODIFY  §1 (+§6 if D-X2 changes) → v1.3 — ONLY after lead approval
tests/ (cost-table, chain, provider)    MODIFY  update cited names/prices; ADD invariant tests
README.md, docs/architecture.md         MODIFY  model names, price notes, status table (RULE 17)
CHANGELOG.md, pyproject.toml, core/__version__.py   MODIFY  new version entry (RULE 15/17)
TODO.md                                 MODIFY  remove this item (RULE 19)
```

**Structure Decision**: edit constants in place, where each already lives. Rejected:
a single shared "models" module (would be new structure and a larger refactor
touching every importer — out of scope; no new packages without a plan entry
per §8, and none is needed). The duplication across files is pre-existing and
is covered by the invariant tests instead of removed here.

## Version and docs gates

- **Version (RULE 15)**: bump `1.29.2` → `1.30.0` (default behaviour and cost
  change) — approved by the lead.
- **RULE 17**: CHANGELOG entry, README (models table, spec status row 054),
  architecture doc updated before merge.
- **RULE 19**: remove "Model currency refresh II" from `TODO.md` in the same PR.

## Decisions (project lead, 2026-10-04)

1. **Constitution amendment v1.3** — **APPROVED as described (2026-10-04).**
   §1 lines: Claude `claude-sonnet-5-5`; Gemini image `gemini-3.1-flash-image`
   (primary) with `gemini-3-pro-image` fallback; Gemini text primary
   `gemini-3.8-flash` only if the live check shows 2.5 no longer works
   (otherwise unchanged); `gemini-2.5-pro` and Grok unchanged; §6 untouched.
   Also corrects §1's stale pointer to the image fallback chain
   (`agents/agent_image_generator.py` → `core/image_generation.py`). Spec 054's
   plan and PR serve as the proposal (as in v1.1/v1.2).
2. **Gemini Flash move** (`gemini-2.5-flash` → `gemini-3.8-flash`) — **approved
   conditionally: "yes, if 2.5 is no longer working". LIVE RESULT 2026-10-04:
   `gemini-2.5-flash` still works → NO MOVE; `gemini-2.5-flash-lite` returns 404 →
   moves to `gemini-3.5-flash-lite`.** The live check
   (`quickstart.md` §2) decided: if `gemini-2.5-flash` fails for our key, make
   the move; if it still works, do NOT move and report back to the lead for a
   decision. The same condition applies to `gemini-2.5-flash-lite` →
   `gemini-3.5-flash-lite`.
3. **Haiku 4.5** — **approved: keep.** Re-check the docs after 2026-10-15.
4. **Grok aggregator** — **approved: keep `grok-4.3`.** §6 and the Grok rows in
   the matrix therefore do not change.
5. **Version bump** — **approved: 1.29.2 → 1.30.0.**
6. **Plan artifacts** — **approved** (RULE 4), including the completed Claude
   table.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| §1 SDK and Model Rules — model names change | Retired and superseded models must leave the defaults; §1 lists them by name | Leaving §1 as is would make every later plan's Constitution Check wrong; amendment is the procedure the constitution itself prescribes |
| §6 — only if the lead changes the Grok aggregator or panelist | Keep §6 naming consistent with code | Not triggered: the lead kept `grok-4.3` and `grok-build-0.1` |

## Amendment A (2026-10-04) — Claude 5 thinking blocks

**Cause (measured, research.md §9)**: `llm/claude.py` assumed the first content block is
text; Claude 5 models may start with a thinking block. **Change**: read text blocks only;
clear error when there is none; warn on `max_tokens`; optional `effort` on `ClaudeProvider`
sent only for models that support it, applied to panelists through a `panelist` flag on the
provider factories in `core/runner.py` and `core/newsletter_merge.py` and the defaults in
`core/bundle_writer.py`. **Constitution Check**: unchanged — no new provider, SDK, module or
principle touched (§1 rules (a)-(d) still hold; rule (a)'s "one real call" is now interpreted
as a realistic call, see FR-014). **Version**: patch `1.31.0` → `1.31.1`.
