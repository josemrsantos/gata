# Tasks: Agent 0 — Cultural Strategist

**Input**: Design documents from `specs/003-cultural-strategist/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Organization**: Phases 1–2 build shared infrastructure used by both Agent 0 and B/C. Phase 3 adds Agent 0, migrates B/C, and wires the pipeline. US2 (early consensus) and US3 (Final Say Protocol) are both behaviors of `DualPersonaLoop` — their tests and implementation live in Phase 2. US4 (failure exits clearly) is cross-cutting — covered by tests in Phase 2 (loop errors) and Phase 3 (pipeline propagation).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup

**Purpose**: Constitution amendments required before any implementation can begin (plan.md constitution check lists P3 and P8 as blocking).

- [x] T001 Amend `.specify/memory/constitution.md`: update P3 (`<image_prompt>` → `<verdict>` as universal proposer tag) and P8 (add `dual_loop.py` and `agent_0.py` to project structure)

**Checkpoint**: Constitution updated — implementation may proceed.

---

## Phase 2: Foundational — Shared DualPersonaLoop Module

**Purpose**: Build the shared negotiation infrastructure used by both Agent 0 and the migrated B/C loop. This phase covers:
- US2 (early consensus): `DualPersonaLoop.run()` returns immediately on `APPROVED` before iteration 5
- US3 (Final Say Protocol): iteration-5 behaviour — Framer makes the final call with modified prompt
- US4 (failure exits clearly): `TimeoutError` and `RuntimeError` raised by the loop, and model fail-over within each persona

**⚠️ CRITICAL**: Phase 3 (Agent 0 + B/C migration) cannot begin until T002–T004 are complete.

- [x] T002 Add `EnrichedBrief`, `PersonaConfig`, and `DualLoopResult` dataclasses to `agents/types.py`
- [x] T003 [P] Write `tests/test_dual_loop.py` — unit tests for `DualPersonaLoop`: happy path (approval on iteration 1), early exit (approval before iteration 5), Final Say Protocol (no approval after 5 iterations), timeout (`TimeoutError` raised when budget exceeded), model fail-over (next model tried on failure), all models exhausted (`RuntimeError` raised)
- [x] T004 Implement `agents/dual_loop.py` — `DualPersonaLoop` class with `run(initial_input: str) -> str`: iteration loop, `<verdict>` tag parsing (proposer and reviewer), Final Say prompt suffix at iteration 5, `time.monotonic()` timeout check at each iteration boundary, model fail-over chain per `PersonaConfig`

**Checkpoint**: `pytest tests/test_dual_loop.py` passes — shared loop module is functional.

---

## Phase 3: US1 — Pipeline Runs with Enriched Brief (Priority: P1) 🎯 MVP

**Goal**: Every pipeline invocation (community mode and manual mode) runs Agent 0 first, producing an `EnrichedBrief` that drives the B/C creative loop. The B/C loop is migrated to use `DualPersonaLoop` and the `<verdict>` tag at the same time.

**Independent Test**: `python pipeline.py --community portuguese-adults` — log shows at least one Agent 0 iteration (Framer proposal + Resonator response), enriched brief logged before B/C loop starts, cartoon image produced.

**Coverage also includes**: US4 — pipeline exits before B/C when Agent 0 raises `TimeoutError` or `RuntimeError`.

### Tests for US1

- [x] T005 [P] [US1] Write `tests/test_agent_0.py` — unit tests for `agent_0.run()`: returns `EnrichedBrief` with locked seed fields, non-empty `cultural_angle`, non-empty `culturally_loaded_references`; raises `ValueError` when either field is empty; propagates `TimeoutError` from `DualPersonaLoop`; propagates `RuntimeError` from `DualPersonaLoop`; accepts `EnrichedBrief` with one reference (minimum valid list)
- [x] T007 [P] [US1] Update `tests/test_agent_bc.py` — replace all `<image_prompt>` references with `<verdict>`; update `run()` call signature from `StrategyBrief` to `EnrichedBrief`; update `VALID_RESPONSE` fixture; verify `CartoonConcept.image_prompt` field name is unchanged; add test that `run()` accepts `EnrichedBrief` and that `cultural_angle` and `culturally_loaded_references` appear in the Satirist system prompt
- [x] T008 [P] [US1] Update `tests/test_pipeline.py` — add test that `agent_0.run()` is called before `agent_bc.run()`; add test that `agent_bc.run()` receives the `EnrichedBrief` returned by `agent_0.run()`; add test that pipeline exits (raises or calls `sys.exit`) before `agent_bc.run()` when `agent_0.run()` raises `RuntimeError`; add test for `TimeoutError` from Agent 0

### Implementation for US1

- [x] T006 [US1] Implement `agents/agent_0.py` — `run(topic: str, seed_brief: StrategyBrief) -> EnrichedBrief`: instantiate `DualPersonaLoop` with Framer (`PersonaConfig`) and Resonator (`PersonaConfig`) configs; call `loop.run(initial_input)` with topic + seed brief formatted as context; parse returned `<verdict>` content to extract `cultural_angle` (after `CULTURAL ANGLE:` label) and `culturally_loaded_references` (bullet list after `REFERENCES:` label); validate both fields non-empty; return `EnrichedBrief` with seed fields locked; log each iteration outcome and the final enriched brief (FR-010, FR-011); include Framer model chain (`claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5-20251001`) and Resonator model chain (`gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-1.5-pro`)
- [x] T009 [US1] Migrate `agents/agent_bc.py` — replace hand-written negotiation loop with `DualPersonaLoop`; pass Satirist and Critic as `PersonaConfig` instances using existing model chains (`_CLAUDE_MODELS`, `_GEMINI_CRITIC_MODELS`); replace all `<image_prompt>` tag references with `<verdict>` in system prompt text and regex (`_extract_image_prompt` → extracts from `<verdict>`); update `run()` signature from `StrategyBrief` to `EnrichedBrief`; include `cultural_angle` and `culturally_loaded_references` in the Satirist system prompt; preserve `CartoonConcept.image_prompt` Python field name unchanged
- [x] T010 [US1] Update `pipeline.py` — call `agent_0.run(topic, seed_brief)` before `agent_bc.run()`; pass returned `EnrichedBrief` to `agent_bc.run()` and `agent_d.generate()`; propagate `TimeoutError` and `RuntimeError` from Agent 0 (exit before B/C); update both community mode and manual mode paths

**Checkpoint**: `pytest tests/` passes; `python pipeline.py --community portuguese-adults` produces an image with enriched brief logged.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [x] T011 [P] Run `ruff check agents/types.py agents/dual_loop.py agents/agent_0.py agents/agent_bc.py pipeline.py` and fix any violations
- [x] T012 [P] Run full test suite `pytest tests/` — all tests must pass; confirm no existing tests broken by B/C migration
- [x] T013 End-to-end validation: run `python pipeline.py --community portuguese-adults` and verify log contains Agent 0 iteration(s), enriched brief with non-empty `cultural_angle` and at least one `culturally_loaded_references` entry, B/C loop start, and output image written to disk

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS Phase 3
- **Phase 3 (US1)**: Depends on Phase 2 — all six tasks can begin once Phase 2 completes
- **Phase 4 (Polish)**: Depends on Phase 3 completion

### Within Phase 2

- T002 (types.py) → T003 (test_dual_loop.py) → T004 (dual_loop.py)
- T002 must complete before T003 (types imported in tests)
- T003 must complete and be reviewed before T004 (TDD — test before implement)

### Within Phase 3

- T005, T007, T008 are [P]: different test files, no mutual dependencies — can be written in any order
- T005 → T006: test_agent_0.py must be reviewed before implementing agent_0.py
- T007 → T009: test_agent_bc.py updates must be reviewed before migrating agent_bc.py
- T008 → T010: test_pipeline.py updates must be reviewed before updating pipeline.py
- T009 must complete before T010 (pipeline imports agent_bc)

### Human Review Protocol (CLAUDE.md)

After **every** test file (T003, T005, T007, T008): STOP and wait for explicit approval before writing the corresponding implementation.
After **every** implementation file (T002, T004, T006, T009, T010): STOP and wait for explicit approval before proceeding.

---

## Parallel Opportunities

```
# Phase 2 — sequential (TDD dependency chain):
T002 → T003 (review) → T004 (review)

# Phase 3 — test files can be written in parallel (different files):
T005 (test_agent_0.py)   ─┐
T007 (test_agent_bc.py)  ─┼─ then review each → T006, T009, T010
T008 (test_pipeline.py)  ─┘

# Phase 4 — ruff and pytest can run together:
T011 ─┐
T012 ─┘ → T013
```

---

## Implementation Strategy

### MVP (Phase 1 + Phase 2 + Phase 3)

1. Amend constitution (T001)
2. Add types (T002)
3. Write + review test_dual_loop.py (T003)
4. Implement + review dual_loop.py (T004)
5. Write + review test_agent_0.py (T005) and test_agent_bc.py (T007) and test_pipeline.py (T008)
6. Implement + review agent_0.py (T006)
7. Migrate + review agent_bc.py (T009)
8. Update + review pipeline.py (T010)
9. Polish (T011–T013)

Each step requires explicit human approval before proceeding (CLAUDE.md Human Review Protocol).

---

## Summary

| Phase | Tasks | Files |
|-------|-------|-------|
| 1 — Setup | T001 | constitution.md |
| 2 — Foundational | T002–T004 | types.py, test_dual_loop.py, dual_loop.py |
| 3 — US1 MVP | T005–T010 | test_agent_0.py, agent_0.py, test_agent_bc.py, test_pipeline.py, agent_bc.py, pipeline.py |
| 4 — Polish | T011–T013 | (run checks) |
| **Total** | **13 tasks** | **9 files** |
