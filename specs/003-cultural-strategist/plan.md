# Implementation Plan: Agent 0 — Cultural Strategist

**Branch**: `003-stage-3-cultural-strategist` | **Date**: 2026-05-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/003-cultural-strategist/spec.md`

## Summary

Add Agent 0 (Cultural Strategist) as a dual-persona negotiation layer that runs before the B/C creative loop, enriching the seed brief with a cultural angle and culturally-loaded references. Simultaneously extract a shared `DualPersonaLoop` module used by both Agent 0 and B/C, and migrate the B/C loop to use it — replacing the `<image_prompt>` XML tag with `<verdict>` across both agents. Both loops gain model fail-over chains and the shared 15-minute timeout for Agent 0.

---

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `anthropic` SDK, `google-genai` SDK, `pyyaml` (all existing)
**Storage**: N/A
**Testing**: `pytest` with `unittest.mock`
**Target Platform**: Linux/local (same as existing pipeline)
**Project Type**: CLI pipeline
**Performance Goals**: Agent 0 must complete within 15 minutes (FR-013)
**Constraints**: Max 5 iterations per loop; `<verdict>` tag must be parseable by regex; no real API calls in tests
**Scale/Scope**: Single pipeline run; no concurrency

---

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| P1 — SDK & Model Rules | ✓ PASS | Framer uses `claude-sonnet-4-6`; Resonator uses Gemini chain |
| P3 — XML Contract | ⚠️ AMENDMENT REQUIRED | `<image_prompt>` renamed to `<verdict>` in B/C; constitution must be updated before implementation |
| P6 — Dual-Persona Iteration Rules | ✓ PASS | 5-iteration cap, Final Say Protocol, progress requirement — all applied to Agent 0 |
| P8 — Project Structure | ⚠️ UPDATE REQUIRED | `dual_loop.py` and `agent_0.py` must be added to the structure definition |
| P9 — Testing Rules | ✓ PASS | Tests written before implementation; no real API calls |
| P11 — Development Stages | ✓ PASS | Stage 2 complete; Stage 3 is current target |
| P12 — Code Quality | ✓ PASS | `ruff` enforced throughout |
| P13 — Logging | ✓ PASS | All agent modules use `logging` |

**Blocking items before implementation:**
1. Constitution Principle 3 must be amended: `<image_prompt>` → `<verdict>` as the Satirist's structured output tag
2. Constitution Principle 8 must be amended: add `dual_loop.py` and `agent_0.py` to project structure

---

## Project Structure

### Documentation (this feature)

```text
specs/003-cultural-strategist/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── internal-interfaces.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code Changes

```text
agents/
├── types.py          # ADD: EnrichedBrief dataclass
├── dual_loop.py      # NEW: shared DualPersonaLoop module
├── agent_0.py        # NEW: Cultural Strategist (uses DualPersonaLoop)
├── agent_bc.py       # MIGRATE: use DualPersonaLoop; <image_prompt> → <verdict>
├── agent_d.py        # unchanged
└── config_loader.py  # unchanged

tests/
├── test_dual_loop.py # NEW: shared module unit tests
├── test_agent_0.py   # NEW: Agent 0 unit tests
├── test_agent_bc.py  # UPDATE: <verdict> tag, DualPersonaLoop integration
└── test_pipeline.py  # UPDATE: Agent 0 call in pipeline flow

pipeline.py           # UPDATE: call agent_0.run() before agent_bc.run()
.specify/memory/constitution.md  # AMEND: P3, P8
```

**Structure Decision**: Flat `agents/` layout consistent with existing project. `dual_loop.py` is the only new shared module; no new subdirectories needed.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Constitution P3 amendment (`<image_prompt>` → `<verdict>`) | Universal tag required for shared loop module to be truly reusable — the loop cannot know what the output represents | Keeping `<image_prompt>` in B/C and using a different tag in Agent 0 breaks the shared-module design and requires the loop to be parameterised on tag name, adding complexity rather than removing it |
