# Tasks: Provider Pricing & Model Currency Refresh

**Input**: Design documents from `specs/039-provider-pricing-refresh/`
**Branch**: `039-provider-pricing-refresh`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions. Test
tasks appear before their corresponding implementation tasks in every phase.

---

## Phase 1: Setup

- [ ] T001 Confirm active git branch is `039-provider-pricing-refresh`

---

## Phase 2: Constitution Amendment

**Purpose**: §1 and §6 hardcode `grok-3`/`grok-3-mini` by name — the amendment must
land before any default-model code change (precedent: Spec 029).

- [ ] T002 Edit `.specify/memory/constitution.md` §1 (Grok primary model) and §6
  (aggregator/panelist model names, both occurrences) per the exact diff in
  `plan.md`'s Amendment section; bump version to v1.1, dated 2026-07-27, with an
  amendment-log entry

**Checkpoint**: `grep -n "grok-3\b" .specify/memory/constitution.md` returns no matches

---

## Phase 3: Claude Pricing Fix (US1)

**Goal**: `llm/claude.py` `_COST_PER_M` matches official rates.

### Tests — Write FIRST, Confirm FAILING

- [ ] T003 [P] [US1] Create `tests/test_claude_provider.py` (mirrors
  `tests/test_grok_provider.py` pattern): test `_COST_PER_M["claude-opus-4-7"] ==
  (5.00, 25.00)`, `_COST_PER_M["claude-opus-4-8"] == (5.00, 25.00)`,
  `_COST_PER_M["claude-haiku-4-5-20251001"] == (1.00, 5.00)`; test
  `generate()` computes correct `cost_usd` for an Opus 4.7 call; test unknown model
  defaults to `cost_usd=0.0`; test `_COST_PER_M` includes `claude-sonnet-5` and
  `claude-opus-5`

> **STOP**: Confirm T003 FAILS (`python -m pytest tests/test_claude_provider.py -v`) before T004.

### Implementation

- [ ] T004 [US1] In `llm/claude.py`: fix `claude-opus-4-7`/`claude-opus-4-8` to
  `(5.00, 25.00)`; fix `claude-haiku-4-5-20251001` to `(1.00, 5.00)`; add
  `claude-sonnet-5: (3.00, 15.00)` and `claude-opus-5: (5.00, 25.00)`

> **STOP**: `python -m pytest tests/test_claude_provider.py -v` passes.

**Checkpoint**: `python -m pytest tests/test_claude_provider.py -v`

---

## Phase 4: Gemini Pricing Fix + Dead Model Removal (US1 + US2)

**Goal**: `llm/gemini.py` `_COST_PER_M` matches official rates; `gemini-2.0-flash`
(confirmed dead 2026-06-01) is gone from every default fallback chain.

### Tests — Write FIRST, Confirm FAILING

- [ ] T005 [P] [US1] Create `tests/test_gemini_provider.py`: test
  `_COST_PER_M["gemini-3.1-flash-lite"] == (0.25, 1.50)`; test
  `_COST_PER_M["gemini-3.1-pro-preview"] == (2.00, 12.00)`; test
  `"gemini-2.0-flash" not in _COST_PER_M`; test `compute_cost()` for a known model
- [ ] T006 [P] [US2] In `tests/test_agent_satirist.py` or a new
  `tests/test_runner_defaults.py`: test `"gemini-2.0-flash" not in [p.model_id for p
  in _GEMINI_PRO_CHAIN]` (import from `core.runner`)
- [ ] T007 [P] [US2] In `tests/test_agent_cultural_strategist.py`: test
  `"gemini-2.0-flash" not in agent_cultural_strategist._INFERENCE_MODELS`

> **STOP**: Confirm T005–T007 FAIL before T008.

### Implementation

- [ ] T008 [US1] In `llm/gemini.py`: fix `gemini-3.1-flash-lite` to `(0.25, 1.50)`;
  fix `gemini-3.1-pro-preview` to `(2.00, 12.00)`; remove the `gemini-2.0-flash` entry
- [ ] T009 [US2] In `core/runner.py`: replace `gemini-2.0-flash` with
  `gemini-2.5-flash-lite` as the last entry of `_GEMINI_PRO_CHAIN`
- [ ] T010 [US2] In `agents/agent_cultural_strategist.py`: replace `gemini-2.0-flash`
  with `gemini-2.5-flash-lite` in `_INFERENCE_MODELS`

> **STOP**: `python -m pytest tests/test_gemini_provider.py tests/test_agent_cultural_strategist.py -v` passes.

**Checkpoint**: `grep -rn "gemini-2.0-flash" core/ agents/ llm/` returns no matches

---

## Phase 5: Grok Pricing Fix + Retired Model Aliasing (US1 + US2)

**Goal**: `llm/grok.py` `_COST_PER_M` has correct entries for live models and
correctly-repriced aliases for retired ones; every default aggregator/panelist slot
moves off `grok-3`/`grok-3-mini`.

### Tests — Write FIRST, Confirm FAILING

- [ ] T011 [US1] In `tests/test_grok_provider.py`: update
  `test_generate_computes_correct_cost_for_grok3` to expect the `grok-4.3` rate
  ($1.25/$2.50 → $3.75 for 1M/1M, adjust to the test's actual token counts) instead
  of the old $3.00/$15.00; update `test_generate_computes_correct_cost_for_grok3_mini`
  the same way; update `test_cost_table_covers_all_expected_models` to also assert
  `grok-4.5`, `grok-4.3`, `grok-build-0.1`, `grok-3-fast`, `grok-3-mini-fast` are
  present; update the stale one-sentence comments (RULE 3) to state the current
  redirect fact, not the old standalone rate
- [ ] T012 [US2] In `tests/test_agent_satirist.py`: update
  `test_runner_parallel_panelists_uses_grok_mini` → assert `grok-build-0.1` present;
  `test_runner_parallel_panelists_excludes_grok3` → assert `grok-4.3` absent from
  panelists; `test_runner_grok_aggregator_constant_uses_grok3` → assert `grok-4.3`
  present in `_GROK_AGGREGATOR`; rename tests and update their one-sentence comments
  to match (RULE 3)

> **STOP**: Confirm T011–T012 FAIL before T013.

### Implementation

- [ ] T013 [US1] In `llm/grok.py`: add `grok-4.5: (2.00, 6.00)`,
  `grok-4.3: (1.25, 2.50)`, `grok-build-0.1: (1.00, 2.00)`; reprice
  `grok-3`, `grok-3-mini`, `grok-3-fast`, `grok-3-mini-fast` to `(1.25, 2.50)` (the
  `grok-4.3` rate they now actually bill, confirmed live) with a comment noting they
  are retired aliases
- [ ] T014 [US2] In `providers.yaml`: change aggregator `grok-3` → `grok-4.3`; change
  both panelist `grok-3-mini` entries → `grok-build-0.1`; update the timeout comment
  block's example model names to match
- [ ] T015 [US2] In `core/runner.py`: `_PARALLEL_PANELISTS` `grok-3-mini` →
  `grok-build-0.1`; `_GROK_AGGREGATOR` `grok-3` → `grok-4.3`
- [ ] T016 [US2] In `core/bundle_writer.py`: hardcoded default `grok-3-mini` →
  `grok-build-0.1`, `grok-3` → `grok-4.3`

> **STOP**: `python -m pytest tests/test_grok_provider.py tests/test_agent_satirist.py -v` passes.

**Checkpoint**: `grep -rn "grok-3\b" core/ providers.yaml agents/` returns no matches

---

## Phase 6: Test Audit Sweep

- [ ] T017 [P] Run `grep -rln "grok-3\b\|gemini-2.0-flash" tests/` and inspect every
  remaining hit; fix any assertion tied to a *production default* (not an arbitrary
  YAML-parsing fixture string, which may stay as-is — e.g.
  `tests/test_providers_config.py`'s generic parsing fixtures do not need to change,
  but should be spot-checked)
- [ ] T018 [P] `python -m pytest tests/ -v` — confirm zero failures across the whole suite

---

## Phase 7: Polish & Cross-Cutting Concerns (RULE 6, 11, 15, 17)

- [ ] T019 [P] Run `ruff check . --fix` and `ruff format .` on all modified files;
  confirm `ruff check .` exits 0
- [ ] T020 [P] Update `README.md`: providers.yaml example block (lines ~195–210),
  built-in-defaults sentence (line ~189), and the three agent-table rows naming
  `Grok-mini`/`Grok-3` (lines ~61–83) — replace with `grok-build-0.1`/`grok-4.3`
- [ ] T021 [P] Update `docs/architecture.md`: every diagram node and prose line
  naming `grok-3-mini`, `grok-3`/`Grok-3`, or `Grok-mini` (found via
  `grep -n "grok-3\|Grok-mini" docs/architecture.md`)
- [ ] T022 [P] Add a new CHANGELOG.md entry: pricing-table corrections (Claude
  Opus/Haiku, Gemini 3.1-flash-lite/pro-preview) + default model swap
  (`grok-3`→`grok-4.3`, `grok-3-mini`→`grok-build-0.1`, `gemini-2.0-flash`→
  `gemini-2.5-flash-lite`) + constitution v1.1 amendment
- [ ] T023 [P] Bump version in `pyproject.toml` and `core/__version__.py`
  (resolve the pre-existing 1.19.0/1.20.0 mismatch by bumping both from the higher
  of the two)
- [ ] T024 Update `CLAUDE.md` completed-stages table: add row for `039` once this
  stage is considered done

---

## Phase 8: End-to-End Verification (RULE 12)

- [ ] T025 Manually invoke the pipeline for one real cartoon (real API keys via
  `source set_gata.sh`) to prove the new defaults work end-to-end and produce a real
  image; record the output image path

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 (constitution must land first, precedent: Spec 029)
- Phase 2 → Phases 3, 4, 5 (any of which may run after Phase 2; 3/4/5 touch disjoint
  files and could be done in either order, but Grok's Phase 5 depends on the live
  verification already captured in `research.md`/`plan.md`, not on Phases 3–4)
- Phases 3, 4, 5 → Phase 6 (audit needs all production edits done first)
- Phase 6 → Phase 7 (docs describe the final state)
- Phase 7 → Phase 8 (version bump before a "real" run, though not strictly required
  for the pipeline to function)

## Summary

| Phase | Tasks | Story | Notes |
|-------|-------|-------|-------|
| 1 Setup | T001 | — | Branch hygiene |
| 2 Constitution | T002 | — | §1/§6 amendment — gates Phases 3–5 |
| 3 Claude | T003–T004 | US1 | New test file + cost fix |
| 4 Gemini | T005–T010 | US1, US2 | New test file + cost fix + dead-model removal |
| 5 Grok | T011–T016 | US1, US2 | Cost fix + retired-alias repricing + default swap |
| 6 Audit | T017–T018 | — | Full-suite sweep |
| 7 Polish | T019–T024 | — | ruff + README + architecture + CHANGELOG + version + CLAUDE.md |
| 8 Verify | T025 | — | Real end-to-end run |
| **Total** | **25 tasks** | | |
