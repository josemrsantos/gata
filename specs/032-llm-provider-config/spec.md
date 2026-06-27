# Feature Specification: LLM Provider Configurability + Cross-Provider Fallback

**Spec**: `032-llm-provider-config`
**Created**: 2026-06-27
**Status**: Draft

## Problem

Provider and model assignments for every agent role (panelists, aggregator) are
hardcoded as module-level constants in `core/runner.py` and `core/bundle_writer.py`.
Changing which LLM handles which role requires editing source code. If all models
of one LLM provider fail, the pipeline crashes rather than trying a different
provider.

## Goal

An optional `providers.yaml` config file declares which LLM/model handles each
agent role, with an ordered fallback chain that spans provider boundaries. If all
models of the primary provider fail, the next provider in the chain is tried
automatically. If no `providers.yaml` is present the pipeline behaves exactly as
before (no regression).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Config-driven provider selection (Priority: P1)

A developer creates `providers.yaml` specifying Grok as the primary panelist and
Claude as the aggregator. Running the pipeline uses those providers without any code
change.

**Why this priority**: Core deliverable — without this, the spec has no effect.

**Independent Test**: `python pipeline.py --topic "test" --providers providers.yaml`

**Acceptance Scenarios**:

1. **Given** a valid `providers.yaml`, **When** `--providers providers.yaml` is
   passed, **Then** each agent role uses the configured providers.
2. **Given** no `--providers` flag, **When** the pipeline runs, **Then** it uses
   the current hardcoded defaults unchanged.

---

### User Story 2 — Cross-provider fallback (Priority: P1)

All models of the primary provider raise an exception. The pipeline automatically
retries with the next configured provider and completes successfully.

**Why this priority**: The second half of the spec's core promise.

**Independent Test**: Mock the primary provider to raise; assert the pipeline
completes and the fallback provider's model appears in telemetry.

**Acceptance Scenarios**:

1. **Given** a panelist slot configured as `[claude-sonnet-4-6, gemini-2.5-flash]`,
   **When** the Claude call raises `RuntimeError`, **Then** Gemini is used and the
   panelist output is non-empty.
2. **Given** all providers in a slot fail, **When** the panel runs, **Then** a
   `RuntimeError` is raised and logged.

---

### Edge Cases

- Unknown provider name in YAML → `ValueError` raised at load time, before any API call
- Empty panelists list in YAML → `ValueError` raised at load time
- `providers.yaml` absent with `--providers` flag → `ValueError` raised with clear message
- Single-model slot (no fallback configured) → behaves identically to current code

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST load `providers.yaml` when `--providers PATH` is supplied.
- **FR-002**: The system MUST reject unknown provider names (`ValueError`) at load time.
- **FR-003**: When a provider call fails, the system MUST try the next provider in the
  slot's ordered list before declaring the panelist failed.
- **FR-004**: When no `providers.yaml` is supplied, the system MUST use hardcoded
  defaults, preserving current behaviour exactly.
- **FR-005**: `providers.yaml` at the project root MUST ship as a sample config that
  mirrors current hardcoded defaults.

### Key Entities

- **ModelSpec**: A `(provider, model)` pair identifying one LLM call target.
- **ProvidersConfig**: The parsed providers.yaml — a list of panelist slots (each slot
  is an ordered list of `ModelSpec`) and an aggregator chain (ordered list of `ModelSpec`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `python -m pytest tests/` exits 0 with no new failures.
- **SC-002**: A providers.yaml with three panelist slots and one aggregator loads
  without error and produces the correct `ProvidersConfig` structure.
- **SC-003**: A test that mocks the primary provider to raise confirms the fallback
  provider is called and the run succeeds.
- **SC-004**: `python pipeline.py --providers providers.yaml --topic "test" ...` runs
  without error (smoke test; does not require a live API call).

## What does NOT change

- `llm/parallel_panel.py` — no change; existing `_call_persona` fallback loop is sufficient.
- `llm/dual_loop.py` — no change.
- `llm/base.py`, `claude.py`, `gemini.py`, `grok.py` — no change.
- `communities.yaml`, `humor.yaml` — no change; providers are a separate concern.
- Any existing CLI flags — `--providers` is additive only.

## Assumptions

- The three valid provider names are `claude`, `gemini`, and `grok` (matching §1 of
  the constitution). No new providers are introduced.
- `providers.yaml` is optional; its absence is not an error.
- Panelist slots in `providers.yaml` correspond positionally to the three parallel
  panelists. Adding more slots than the pipeline expects is valid (extra slots are used
  if the code supports it); fewer slots may cause a warning.
