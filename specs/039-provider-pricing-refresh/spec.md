# Feature Specification: Provider Pricing & Model Currency Refresh

**Spec**: `039-provider-pricing-refresh`
**Created**: 2026-07-27
**Status**: Draft

## Problem

The per-model `_COST_PER_M` tables in `llm/claude.py`, `llm/gemini.py`, and
`llm/grok.py`, and the default model IDs in `providers.yaml`, `core/runner.py`, and
`core/bundle_writer.py`, were last set at the time each provider was integrated and
have not been refreshed since. A web check against each provider's current official
pricing (2026-07-27, see `research.md`) found two distinct problems:

1. **Stale prices on live models.** Claude Opus 4.7/4.8 and Haiku 4.5, and Gemini
   3.1-flash-lite and 3.1-pro-preview, are still active models but priced wrong in
   the cost tables — cost telemetry and run-summary totals (Spec 009/033) have been
   silently incorrect for any run touching those models.
2. **Dead/retired default models.** `gemini-2.0-flash` — used as the last-resort
   fallback in `core/runner.py` and `agents/agent_cultural_strategist.py` — was shut
   down by Google on 2026-06-01; any run that falls through to it now hard-fails
   instead of degrading gracefully. `grok-3` — the default aggregator model in
   `providers.yaml`, `core/runner.py`, and `core/bundle_writer.py` — was retired by
   xAI on 2026-05-15; it still resolves via redirect but bills at `grok-4.3` rates,
   so the `_COST_PER_M` table (which still charges the old `grok-3` rate) has been
   overstating aggregator cost by roughly 2.4x for over two months.

## Goal

Every price in `llm/claude.py`, `llm/gemini.py`, and `llm/grok.py` matches each
provider's current official published rate, and every default model ID in
`providers.yaml`, `core/runner.py`, and `core/bundle_writer.py` refers to a model
that is currently active (not retired or shut down) on that provider's API.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Accurate cost telemetry (Priority: P1)

A developer runs the pipeline and checks the run summary / bundle cost breakdown
(Spec 009, 033). The dollar amount shown for each agent call must reflect what the
provider actually billed, not a stale rate baked in at integration time.

**Why this priority**: Cost reporting existing to be *trusted* is the entire point of
Spec 009/014/033; a silently wrong rate defeats it without anyone noticing.

**Independent Test**:
```
python -c "from llm.grok import _COST_PER_M; print(_COST_PER_M)"
python -c "from llm.claude import _COST_PER_M; print(_COST_PER_M)"
python -c "from llm.gemini import _COST_PER_M; print(_COST_PER_M)"
```
Every rate printed must match the table in `research.md`.

**Acceptance Scenarios**:

1. **Given** a Claude Opus 4.7 call with known input/output token counts, **When**
   `ClaudeProvider.generate()` computes `cost_usd`, **Then** the result matches
   $5/$25 per MTok, not $15/$75.
2. **Given** a Grok aggregator call, **When** the default `providers.yaml` aggregator
   entry is used, **Then** the provider/model is not a retired slug (`grok-3`) and its
   cost is computed at that model's real current rate.

---

### User Story 2 — No dead models in the default fallback chains (Priority: P1)

A developer runs the pipeline with no `providers.yaml` override (built-in defaults)
and every provider in a fallback chain happens to fail except the last one.

**Why this priority**: A fallback chain whose last resort is a dead model isn't a
fallback chain — it's a chain that silently loses its safety net. This is a
functional bug, not just a cosmetic pricing issue.

**Independent Test**:
```
grep -rn "gemini-2.0-flash\|grok-3\b" core/runner.py core/bundle_writer.py providers.yaml
```
Must return no matches once this spec is implemented.

**Acceptance Scenarios**:

1. **Given** `core/runner.py`'s `_FALLBACK` Gemini chain, **When** all models before
   the last are unavailable, **Then** the last-resort model is one that is currently
   active on Google's API (not `gemini-2.0-flash`).
2. **Given** `providers.yaml`'s default aggregator entry, **When** no override file is
   present, **Then** the aggregator model is not a retired xAI slug.

---

### Edge Cases

- A model still appears in a `_COST_PER_M` table but is now retired everywhere except
  Bedrock/Google Cloud (e.g. Claude Opus 4.1, Opus 4, Haiku 3.5) → keep the entry (a
  user's custom `providers.yaml` may legitimately target Bedrock) but do not use it as
  a *default*.
- A provider's own redirect silently reprices a call (e.g. `grok-3` → `grok-4.3`) →
  the cost table must charge the rate the provider actually bills, not the rate of the
  slug that was requested.
- `gemini-2.5-flash` / `gemini-2.5-pro` (current primary Gemini models) are not dead
  yet but are scheduled to shut down 2026-10-16 → out of scope for this spec (see
  "What does NOT change"); flagged as a follow-up TODO item.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `llm/claude.py` `_COST_PER_M` MUST have correct current rates for
  `claude-sonnet-4-6`, `claude-sonnet-4-5`, `claude-haiku-4-5-20251001`,
  `claude-opus-4-7`, and `claude-opus-4-8` per `research.md`.
- **FR-002**: `llm/gemini.py` `_COST_PER_M` MUST have correct current rates for every
  model still referenced anywhere in the codebase after this spec, and MUST NOT list
  `gemini-2.0-flash` as a default fallback target anywhere in `core/runner.py` or
  `agents/agent_cultural_strategist.py`.
- **FR-003**: `llm/grok.py` `_COST_PER_M` MUST add entries for the models confirmed
  live on xAI's API today (`grok-4.5`, `grok-4.3`, `grok-build-0.1`), priced per
  `research.md`. `grok-3`, `grok-3-mini`, `grok-3-fast`, and `grok-3-mini-fast` — all
  confirmed by a live API call to silently redirect to and bill as `grok-4.3` — MUST
  be repriced to the `grok-4.3` rate rather than deleted, so any leftover custom
  `providers.yaml` entry still gets a correct cost instead of a silent $0.00.
- **FR-004**: `providers.yaml`'s built-in-default comment block and
  `core/bundle_writer.py`'s hardcoded default provider chains MUST NOT reference a
  retired or dead model ID as a default.
- **FR-005**: `core/runner.py`'s `_PARALLEL_PANELISTS`, `_FALLBACK`, and
  `_GROK_AGGREGATOR` chains MUST NOT reference a retired or dead model ID.
- **FR-006**: `.specify/memory/constitution.md` §1 and §6, which hardcode `grok-3` as
  the named aggregator model, MUST be amended (per the constitution's own Amendment
  Procedure — requires explicit project-lead approval) to match whatever model this
  spec's plan selects as the new default aggregator.
- **FR-007**: Every test that asserts a specific model ID or a specific cost value
  tied to `_COST_PER_M` (`tests/test_grok_provider.py`,
  `tests/test_providers_config.py`, `tests/test_agent_satirist.py`, and others found
  during implementation) MUST be updated to match the new defaults and prices.
- **FR-008**: Per RULE 17, CHANGELOG.md, README.md, and docs/architecture.md MUST be
  updated to reflect the new default model IDs before this spec's PR merges.

### Key Entities

- **`_COST_PER_M`**: Per-provider dict mapping model ID → `(input_$_per_MTok,
  output_$_per_MTok)`, read by each provider's `generate()` to compute `cost_usd` on
  every call.
- **Default fallback chain**: The ordered list of `(provider, model)` pairs a
  panelist/aggregator slot tries in sequence, defined in `providers.yaml` (or the
  built-in defaults in `core/runner.py` / `core/bundle_writer.py` when no override
  file is present).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every rate in all three `_COST_PER_M` tables matches the corresponding
  official provider pricing page as of this spec's research date (2026-07-27), per
  `research.md`.
- **SC-002**: `grep -rn "gemini-2.0-flash\|grok-3\b" core/ providers.yaml agents/`
  (excluding `specs/` and test fixtures that intentionally exercise legacy model
  strings) returns no matches.
- **SC-003**: The full test suite passes with the updated model IDs and prices.
- **SC-004**: README.md, docs/architecture.md, and CHANGELOG.md contain no reference
  to a retired/dead default model (RULE 17 gate).

## What does NOT change

- The *set* of providers used (Claude, Gemini, Grok) — no new provider, no provider
  removed.
- Which provider plays which *role* (panelist vs. aggregator, primary creative model
  vs. evaluator) — this spec swaps model *versions* within existing roles, it does not
  redesign the panel.
- Migrating off `gemini-2.5-flash` / `gemini-2.5-pro` before their 2026-10-16
  shutdown — those models are still active today; forcing that migration now is a
  separate, larger decision (new pricing tier, possible quality/latency change) and is
  left as a follow-up TODO item rather than folded into this pricing fix.
- Adopting Claude Sonnet 5 or Grok 4.5 as new *primary* creative/aggregator models —
  both are new, more expensive options; this spec only replaces dead/retired defaults
  and corrects prices on models already in use, not a general "upgrade to the newest
  model" pass.
- Image generation model IDs (`gemini-3.1-flash-image-preview` family) — verified
  still active and already correctly priced; no change needed.

## Assumptions

- Pricing and deprecation data was fetched directly from each provider's official
  docs (`platform.claude.com`, `ai.google.dev`, `docs.x.ai`) on 2026-07-27; third-party
  aggregator/SEO pricing sites were cross-checked but not trusted where they
  disagreed with official docs (see `research.md`).
- `grok-3-mini`'s exact current behavior was confirmed with a live, low-cost API call
  during planning (2026-07-27): it silently redirects to and bills as `grok-4.3`,
  the same model the aggregator now resolves to. Its replacement in default configs
  is `grok-build-0.1` — the cheapest genuinely-live Grok model — chosen specifically
  to restore the aggregator-vs-panelist distinction the redirect had collapsed.
- This spec's numbers will already be stale again in a few months (Claude Sonnet 5
  intro pricing ends 2026-08-31; Gemini 2.5-flash/pro retire 2026-10-16) — this is
  expected to become a recurring maintenance spec, not a one-time fix.
