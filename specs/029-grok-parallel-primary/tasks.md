# Tasks: Grok as Primary Decider Across All Parallel Panel Agents

**Input**: Design documents from `specs/029-grok-parallel-primary/`
**Branch**: `029-grok-parallel-primary`
**Prerequisites**: plan.md ✅, spec.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions. Test
tasks appear before their corresponding implementation tasks in every phase.

---

## Phase 1: Setup

**Purpose**: Confirm branch hygiene before any code is written (RULE 5).

- [ ] T001 Confirm active git branch is `029-grok-parallel-primary`; if on `main`, create and switch before touching any source file

---

## Phase 2: Constitution Amendment

**Purpose**: §6 explicitly names Claude as aggregator — the amendment must land in
version control before any implementation work begins.

- [ ] T002 Edit `.specify/memory/constitution.md` §6: replace "Claude (as panelist or aggregator) has final say" and the Satirist topology description with the Grok-primary wording specified in `plan.md`

**Checkpoint**: `grep -n "Grok" .specify/memory/constitution.md` — confirms Grok-primary language present in §6

---

## Phase 3: Satirist Aggregator (Simplest Change)

**Goal**: Swap the Satirist aggregator from Claude to Grok-3 and Grok panelist from
grok-3 to grok-3-mini. No changes to `agent_satirist.py` itself.

### Tests for Phase 3 — Write FIRST, Confirm FAILING Before Implementation

- [ ] T003 [US1] In `tests/test_agent_satirist.py`: add/update test asserting that the aggregator provider passed into `agent_satirist.run()` is `grok-3` (not a Claude model); add test asserting panelists include `grok-3-mini` and not `grok-3`

> **STOP**: Confirm T003 tests FAIL (`python -m pytest tests/test_agent_satirist.py -v`) before proceeding to T004.

### Implementation for Phase 3

- [ ] T004 [US1] In `core/runner.py`: update `_PARALLEL_PANELISTS` to use `GrokProvider("grok-3-mini")` instead of `GrokProvider("grok-3")`; add `_GROK_AGGREGATOR = [GrokProvider("grok-3")]`; update Satirist call to use `aggregator_providers=_GROK_AGGREGATOR`

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests pass before proceeding.

**Checkpoint**: `python -m pytest tests/test_agent_satirist.py -v`

---

## Phase 4: Cultural Strategist — ParallelPanel Conversion

**Goal**: Replace `DualPersonaLoop` with `ParallelPanel` in `agent_cultural_strategist.py`;
preserve the Resonator quality-gate in the Grok aggregator prompt.

### Tests for Phase 4 — Write FIRST, Confirm FAILING Before Implementation

- [ ] T005 [P] [US2] In `tests/test_agent_cultural_strategist.py`: update/add test asserting `run()` accepts `panelist_providers` + `aggregator_providers` (not `framer_providers` + `resonator_providers`)
- [ ] T006 [P] [US2] In `tests/test_agent_cultural_strategist.py`: add test asserting that `ParallelPanel` is constructed (not `DualPersonaLoop`) when `run()` is called
- [ ] T007 [P] [US2] In `tests/test_agent_cultural_strategist.py`: add test asserting all three panelist providers are called with the Framer system prompt; aggregator called once with the CS aggregator prompt
- [ ] T008 [P] [US2] In `tests/test_agent_cultural_strategist.py`: existing tests for `_parse_verdict`, empty `cultural_angle`, and empty `references` — confirm they still pass (no changes needed; these test isolated parsing logic)

> **STOP**: Confirm T005–T007 tests FAIL before proceeding to T009.

### Implementation for Phase 4

- [ ] T009 [US2] In `agents/agent_cultural_strategist.py`: replace `from llm.dual_loop import DualPersonaLoop` with `from llm.parallel_panel import ParallelPanel`; add `_CS_AGGREGATOR_SYSTEM` constant (Resonator-as-aggregator prompt from spec); rename `resonator_providers` → `aggregator_providers` and `framer_providers` → `panelist_providers` in `run()`; replace `DualPersonaLoop` construction and call with `ParallelPanel` construction and call; remove `_RESONATOR_SYSTEM`
- [ ] T010 [US2] In `core/runner.py`: update `agent_cultural_strategist.run()` call to use `panelist_providers=_PARALLEL_PANELISTS, aggregator_providers=_GROK_AGGREGATOR`; remove `resonator_providers` and `framer_providers` kwargs

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests pass before proceeding.

**Checkpoint**: `python -m pytest tests/test_agent_cultural_strategist.py -v`

---

## Phase 5: Explainer — ParallelPanel Conversion

**Goal**: Replace both `DualPersonaLoop` instances in `agent_explainer.py` with
`ParallelPanel`; preserve the Editor quality-gate in the Grok aggregator prompt.

### Tests for Phase 5 — Write FIRST, Confirm FAILING Before Implementation

- [ ] T011 [P] [US3] In `tests/test_agent_explainer.py`: update/add test asserting `generate_html()` accepts `panelist_providers` + `aggregator_providers` (not `writer_providers` + `editor_providers`)
- [ ] T012 [P] [US3] In `tests/test_agent_explainer.py`: add test asserting two `ParallelPanel` instances are constructed (not two `DualPersonaLoop`) — one for in-lang, one for English
- [ ] T013 [P] [US3] In `tests/test_agent_explainer.py`: add test asserting all three panelist providers are called per run; aggregator called once per run with the Editor aggregator prompt
- [ ] T014 [P] [US3] In `tests/test_bundle_writer.py`: update `write_bundle()` test to assert `agent_explainer.generate_html` is called with `panelist_providers` and `aggregator_providers` kwargs (not `writer_providers` / `editor_providers`)

> **STOP**: Confirm T011–T014 tests FAIL before proceeding to T015.

### Implementation for Phase 5

- [ ] T015 [US3] In `agents/agent_explainer.py`: replace `from llm.dual_loop import DualPersonaLoop` with `from llm.parallel_panel import ParallelPanel`; add `_EXPLAINER_AGGREGATOR_SYSTEM` constant (Editor-as-aggregator prompt from spec); rename `writer_providers` → `panelist_providers` and `editor_providers` → `aggregator_providers` in `generate_html()`; replace both `DualPersonaLoop` constructions and calls with `ParallelPanel`; construct the aggregator `PersonaConfig` once and share between both runs; remove `_EDITOR_SYSTEM`
- [ ] T016 [US3] In `core/bundle_writer.py`: replace `_writer_providers` and `_editor_providers` local constants with `_panelist_providers` (Claude, Grok-mini, Gemini) and `_aggregator_providers` (Grok-3); update `generate_html()` call to use new kwargs; add `from llm import GrokProvider` if not already imported

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests pass before proceeding.

**Checkpoint**: `python -m pytest tests/test_agent_explainer.py tests/test_bundle_writer.py -v`

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T017 [P] Run `ruff check . --fix` and `ruff format .` on all modified files; confirm `ruff check .` exits 0
- [ ] T018 [P] Update `README.md`: agent/sub-agent table rows for Cultural Strategist (remove Resonator, note Grok as decider), Explainer (remove Editor, note Grok as decider), Satirist (note Grok as aggregator) — per RULE 6 and RULE 11
- [ ] T019 [P] Update version in `pyproject.toml` and `core/__version__.py` (RULE 15)
- [ ] T020 [P] Update `CLAUDE.md` completed stages table: add row for `029` once merged

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Constitution)**: Depends on Phase 1 — must land before implementation
- **Phase 3 (Satirist)**: Depends on Phase 2
- **Phase 4 (Cultural Strategist)**: Depends on Phase 2; can run after Phase 3 or in parallel
- **Phase 5 (Explainer)**: Depends on Phase 2; can run after Phase 3 or in parallel
- **Phase 6 (Polish)**: Depends on Phases 3, 4, 5 all complete

### Within Each Phase

- Test tasks (T003, T005–T008, T011–T014) MUST be verified FAILING before implementation tasks begin
- Within Phase 4: T009 before T010 (agent before runner)
- Within Phase 5: T015 before T016 (agent before bundle_writer)

---

## Parallel Opportunities

- T005, T006, T007, T008 — all Phase 4 test tasks are independent of each other
- T011, T012, T013, T014 — all Phase 5 test tasks are independent of each other
- Phase 4 and Phase 5 implementation can proceed simultaneously after Phase 2 completes
- T017, T018, T019, T020 — all Phase 6 tasks are independent of each other

---

## Summary

| Phase | Tasks | Story | Notes |
|-------|-------|-------|-------|
| 1 Setup | T001 | — | Branch hygiene |
| 2 Constitution | T002 | — | §6 amendment — gates all implementation |
| 3 Satirist | T003–T004 | US1 | Aggregator swap only; simplest change |
| 4 Cultural Strategist | T005–T010 | US2 | DualLoop → ParallelPanel |
| 5 Explainer | T011–T016 | US3 | DualLoop → ParallelPanel (x2 runs) |
| 6 Polish | T017–T020 | — | ruff + README + version + CLAUDE.md |
| **Total** | **20 tasks** | | |
