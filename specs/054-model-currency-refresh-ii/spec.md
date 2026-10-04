# Feature Specification: Model currency refresh II

**Spec**: `054-model-currency-refresh-ii`
**Created**: 2026-10-04
**Status**: Draft

## Problem

Providers keep releasing and retiring models, so the default models, fallback
chains and pricing tables drift out of date. A retired model can make a run fail
or silently redirect to (and bill as) a different model, and stale prices make
the run-cost report wrong. Spec 039 corrected this once; it has drifted again.

## Goal

When this feature is done, every default model, fallback chain entry and price
for Claude, Gemini and Grok reflects what each provider currently offers and
charges, no retired model is referenced by default, and the constitution's
model rules match the code.

## Clarifications

### Session 2026-10-04

- Q: Upgrade policy for defaults → A: newest model of the same tier (cost-stable)
- Q: Retired names in cost tables → A: keep as priced alias only if the provider still bills that name
- Q: How to prove refreshed defaults work (SC-004)? → A: official documentation plus one short real call per distinct default model, run once manually and recorded in the plan (not part of the test suite)
- Q: Should fallback chain order change? (FR-003) → A: no; keep each chain's provider order and swap each model in place for its same-tier successor
- Q: Re-measure recommended timeouts? (FR-006) → A: no; carry each existing recommended value over to its successor model unchanged; timeouts stay commented out (no default sets one)
- Q: Preview-only or no newer model in a tier? (FR-002, FR-008) → A: stay on the current stable model unless the successor is stable; record the reason in the plan
- Q: Gemini Flash / Flash-Lite move? → A: approved only if the live check shows gemini-2.5 no longer works for our key; otherwise stay and report to the project lead
- Q: Grok aggregator tier? → A: xAI has no tier names; keep grok-4.3 (aggregator) and grok-build-0.1 (panelist) unchanged

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Runs use current, available models (Priority: P1)

An operator runs the pipeline or the `gata` CLI with no model configuration and
every default model they get is one the provider currently serves.

**Why this priority**: A retired default breaks or mis-bills every run.

**Independent Test**: `python -m pytest tests/ -q` passes, and a default run
completes with no "model not found" or retired-model warning in `run.log`.

**Acceptance Scenarios**:

1. **Given** no `providers.yaml` override, **When** a run starts, **Then** every
   default panelist, aggregator, inference, image and newsletter model is a
   currently available model for its provider.
2. **Given** a fallback chain, **When** its first model fails, **Then** the
   next entry is also a currently available model.

---

### User Story 2 — Cost reports show correct prices (Priority: P2)

An operator reads the run cost summary and the per-model breakdown and trusts
the figures.

**Why this priority**: Cost reporting is the only spending visibility there is.

**Independent Test**: A unit test per provider asserts each default model has a
price entry equal to the provider's published price at the verification date.

**Acceptance Scenarios**:

1. **Given** a default model, **When** a call is costed, **Then** the rate used
   equals the provider's current published rate for input and output tokens.
2. **Given** a model with no price entry, **When** it is used, **Then** the
   existing unpriced-model behaviour is unchanged.

---

### User Story 3 — Governance matches the code (Priority: P3)

The project lead reads the constitution and finds the same model names the code
uses.

**Why this priority**: §1 hardcodes model names; leaving it stale breaks the
Constitution Check gate for every later plan.

**Independent Test**: Every model name in the constitution's §1 (and §6 if changed)
appears in the default configuration, and no default model is absent from §1.

**Acceptance Scenarios**:

1. **Given** the amended constitution, **When** compared with the defaults,
   **Then** they agree.

---

### Edge Cases

- The same-tier successor is only a preview → the default stays on the current
  stable model; the plan records "no change (preview only)". A successor that
  is stable replaces the default.
- A retired model name still appears in an operator's own `providers.yaml` →
  behaviour unchanged by this spec (operator config is not rewritten).
- A provider's price page and its API disagree → the official pricing page at
  the verification date wins, and the source is recorded in the plan.
- No newer model exists for a tier → the current model stays; "no change" is a
  valid verified outcome.
- A refresh would make the Grok panelist and the aggregator the same model →
  not allowed; constitution §6 keeps them deliberately distinct, so one of them
  keeps its previous distinct model or the conflict goes to the project lead.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST record, per provider, the current model list and
  published prices, each verified against the provider's official documentation
  on a stated date (not from memory), and MUST confirm each distinct default
  model with one short real call run once manually (not in the test suite);
  the result is recorded in the research record.
- **FR-002**: Every built-in default model (panelists, aggregators, inference
  chain, trend-scout, image generation chain, newsletter chains) MUST be a
  currently available model.
- **FR-003**: Fallback chains MUST keep their existing provider order, with each
  model swapped in place for its same-tier successor, and MUST NOT contain a
  retired model. Reordering a chain is out of scope for this feature.
- **FR-004**: The cost tables for all three providers MUST hold the verified
  current input/output rates for every default model.
- **FR-005**: Retired model names MUST be removed from defaults. A retired name
  is kept in the cost tables as a priced alias only where the provider still
  bills that name (as Spec 039 did for the old `grok-3` names); otherwise it is
  dropped.
- **FR-006**: The provider config file's built-in defaults MUST reflect the
  refreshed models. Its recommended-timeout comments carry each existing value
  over unchanged to the successor model; no timeout is re-measured or enabled
  by default.
- **FR-007**: The constitution MUST be amended (§1 model names, and §6 only if
  a Grok model changes; version bump, amendment log) in this feature, only after
  the project lead's explicit approval.
- **FR-008**: Each default MUST be replaced by the newest STABLE model of the
  SAME tier (cost-stable); a default is never moved up to a higher tier or to
  a preview-only successor by this feature. Exceptions approved by the project
  lead: (a) Gemini Flash and Flash-Lite move only if the live check shows the
  2.5 model no longer works; (b) Grok has no tier names, so `grok-4.3` and
  `grok-build-0.1` stay. Each swap or "no change" MUST state its tier and
  reason in the research record.
- **FR-009**: Existing tests and docs that cite replaced model names or prices
  MUST be updated so the suite passes with zero failures.
- **FR-010**: `README.md`, `docs/architecture.md` and `CHANGELOG.md` MUST be
  updated for any changed model name or price table (RULE 17), and this item
  MUST be removed from `TODO.md` in the same PR (RULE 19).

### Key Entities

- **Default model assignment**: a provider/model pair in a role (panelist,
  aggregator, inference, image, newsletter) with an ordered fallback.
- **Price entry**: a model's input and output rate per million tokens (image
  models also an image-output rate).
- **Verification record**: the date and official source for each model and
  price claim.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of built-in default models are confirmed current by the
  provider's own documentation on the verification date.
- **SC-002**: 0 retired models remain in any built-in default or fallback chain.
- **SC-003**: 100% of default models have a price entry equal to the published
  rate on the verification date.
- **SC-004**: Each distinct default model answers one short real test call
  without a model-not-found or retired-model error, and the result is recorded
  in the research record.
- **SC-005**: The test suite passes with 0 failures and `ruff check .` exits 0.
- **SC-006**: Every model name in the constitution's §1 (and §6 if changed) matches
  the defaults.

## What does NOT change

- Pipeline stages, agent roles, protocols and CLI flags.
- The order of providers inside any fallback chain.
- Prompts, character and style rules (§4, §5) and the verdict schema (§3, §6).
- Operator-supplied `providers.yaml` files are never rewritten.
- The set of providers (Claude, Gemini, Grok only; §1 forbids others).
- Spec 039's historical record is left as it is.

## Assumptions

- Today's date for verification is 2026-10-04; each claim is dated.
- "Current" means served by the provider's official API and not announced as
  retired; a preview model is kept only where it is already the default and
  no stable successor exists.
- This is a new Flow-Forward spec per RULE 18, confirmed by the project lead.
- The next stage is numbered 054, the next free number after 053.
- The constitution amendment follows its Amendment Procedure and needs the
  project lead's explicit approval before it is written.
