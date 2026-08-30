# Tasks: Research-Only Mode

**Input**: Design documents from `specs/046-research-only-mode/`
**Branch**: `046-research-only-mode`
**Prerequisites**: plan.md ✅, spec.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions. Test
tasks appear before their corresponding implementation tasks in every phase.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths included in every task description

---

## Phase 1: Setup

- [x] T001 Confirm active git branch is `046-research-only-mode` (already created)

---

## Phase 2: Foundational — Branded/Neutral Assembly + `research_only` Mechanism

**Purpose**: The neutral/branded switch (`agent_linkedin_post.py`), the new
bundle-writer output slot, and `run_pipeline()`'s skip-everything mechanism are
shared by every user story — none of US1–US4 can be independently verified
until this exists.

**CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Phase 2 — Write FIRST, Confirm FAILING Before Implementation

- [x] T002 [P] In `tests/test_agent_linkedin_post.py`: add tests for
  `generate_linkedin_post(..., branded=False)` — mocked research/planning/
  writing panels; assert the returned `article_md` contains no `"Gata"`, no
  support email address, no GitHub URL; assert the neutral title fallback
  (`"Research Report: {topic}"`) is used when the writer's `TITLE` section is
  empty; assert the Pipeline Metrics line and `_DISCLOSURE` text are present;
  assert no `_CLOSING_BLOCK`/`_SECTION_4_BODY` content appears. Add a
  regression test that `branded=True` (default, omitted) still produces
  today's exact `_assemble_article` output — unchanged.
- [x] T003 [P] In `tests/test_bundle_writer.py`: add a test that
  `write_bundle(..., research_report="some markdown")` writes
  `research_report.md` in the bundle directory with that content; add a test
  that omitting `research_report` (default `None`) writes no such file;
  confirm it does not interfere with the existing `linkedin_post` param when
  both happen to be passed.
- [x] T004 [P] In `tests/test_pipeline.py`: add tests for
  `run_pipeline(research_only=True)` (all agents mocked) —
  `agent_cultural_strategist.run`, `agent_satirist.run`,
  `agent_image_generator.generate`, `agent_image_evaluator.evaluate` are never
  called; `agent_linkedin_post.generate_linkedin_post` IS called (regardless
  of the `generate_linkedin_post` flag's value) with a minimal `EnrichedBrief`
  built from `topic`/`seed_brief`; `branded` passed to it equals the
  `generate_linkedin_post` flag's value; `bundle_writer.write_bundle` is
  called with `linkedin_post=(...)`/`research_report=None` when
  `generate_linkedin_post=True`, or `research_report=...`/`linkedin_post=None`
  when `generate_linkedin_post=False`.

> **STOP**: Confirm T002–T004 all FAIL
> (`python -m pytest tests/test_agent_linkedin_post.py tests/test_bundle_writer.py tests/test_pipeline.py -v`)
> before proceeding to T005.

### Implementation for Phase 2

- [x] T005 In `agents/agent_linkedin_post.py`: add `branded: bool = True`
  parameter to `generate_linkedin_post()`; add `_assemble_report()` (neutral
  title fallback, Executive Summary, Body, Sources, Pipeline Metrics line +
  `_DISCLOSURE` only — no `_CLOSING_BLOCK`/`_SECTION_4_BODY`); route to
  `_assemble_report()` when `branded=False`, `_assemble_article()` (unchanged)
  when `branded=True`
- [x] T006 In `core/bundle_writer.py`: add `research_report: str | None = None`
  parameter to `write_bundle()`; when non-empty, write it to
  `research_report.md` in `bundle_dir`
- [x] T007 In `core/runner.py`: extract the existing minimal-`EnrichedBrief`
  construction (currently inline under `skip_cultural_strategist`) into a
  private helper `_minimal_brief(topic, seed_brief) -> EnrichedBrief`; update
  the `skip_cultural_strategist` branch to call it — no behaviour change
- [x] T008 In `core/runner.py`: add `research_only: bool = False` parameter to
  `run_pipeline()`. When `True`: log INFO
  (`"Research-only mode — skipping Cultural Strategist, Satirist, Image
  Generator, Image Evaluator"`), skip straight past all four agents using
  `_minimal_brief()` (T007) for `enriched_brief`, and — in the `finally`
  block — always call `generate_linkedin_post(..., branded=generate_linkedin_post)`
  using that minimal brief; pass its result to `write_bundle` as
  `linkedin_post=(...)` when `branded` was `True`, or `research_report=article_md`
  (discarding `notification_txt` per FR-006) when `branded` was `False`

> **STOP**: `python -m pytest tests/test_agent_linkedin_post.py tests/test_bundle_writer.py tests/test_pipeline.py -v`
> — confirm all pass before proceeding.

**Checkpoint**: `python -m pytest tests/test_agent_linkedin_post.py tests/test_bundle_writer.py tests/test_pipeline.py -v`

---

## Phase 3: User Story 1 — `pipeline.py` CLI Support (Priority: P1) MVP

**Goal**: `python pipeline.py ... --research-only` produces a neutral
`research_report.md`, no image, no cartoon telemetry.

**Independent Test**:
```
python pipeline.py --topic "AI regulation in the EU" --audience "policy analysts" \
  --language English --tone neutral --research-only
```

### Tests for User Story 1 — Write FIRST, Confirm FAILING Before Implementation

- [x] T009 [P] [US1] In `tests/test_pipeline.py`: add tests that `pipeline.py`
  accepts `--research-only`; in each of the four mode branches (manual,
  community-topic, named-community, default-random), `output_path` is built
  as `output/research/{sanitize_path_segment(topic)}_{timestamp}.md`
  (assert against the regex `output/research/.+_\d{8}_\d{6}\.md`, mocking
  `datetime.now` for a deterministic timestamp); `research_only=True` is
  passed to `run_pipeline`; when `--direct` is also supplied, an INFO log
  states it has no effect (FR-011), not an error

> **STOP**: Confirm T009 FAILS before T010.

### Implementation for User Story 1

- [x] T010 [US1] In `pipeline.py`: add `--research-only` flag
  (`action="store_true"`, default `False`); when set, build `output_path` as
  `output/research/{sanitize_path_segment(topic)}_{timestamp}.md`
  (`timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")`) in place of the
  existing image-based path, in every mode branch; pass
  `research_only=args.research_only` to `run_pipeline`; log INFO when
  `args.direct and args.research_only` are both set

> **STOP**: `python -m pytest tests/test_pipeline.py -v` — confirm all pass.

**Checkpoint**: `python -m pytest tests/test_pipeline.py -v`

---

## Phase 4: User Stories 2 & 3 — `gata` CLI Support (Priority: P1)

**Goal**: `--research-only` on the `gata` CLI produces the branded
`linkedin_post.md` when combined with `--linkedin-post` (US2), and runs
exactly once — not once per inferred audience (US3).

**Independent Test**:
```
gata "AI regulation in the EU" --research-only --linkedin-post
gata "AI regulation in the EU" --research-only
```

### Tests for User Stories 2 & 3 — Write FIRST, Confirm FAILING Before Implementation

- [x] T011 [P] [US2] In `tests/test_cli.py`: add a test that
  `--research-only --linkedin-post` calls `run_pipeline` with
  `research_only=True, generate_linkedin_post=True`, and that `output_path`
  matches `output/research/.+_\d{8}_\d{6}\.md`
- [x] T012 [P] [US3] In `tests/test_cli.py`: add a test that, with
  `infer_audiences` mocked to return 3 audiences, `--research-only` (with or
  without `--linkedin-post`) calls `run_pipeline` exactly once, using only
  `infer_audiences(...)[0]` (not `_ensure_uk`'s output, not a loop); add a
  test that `--direct --research-only` logs the FR-011 INFO no-op

> **STOP**: Confirm T011–T012 FAIL before T013.

### Implementation for User Stories 2 & 3

- [x] T013 [US2] [US3] In `core/cli.py`: add `--research-only` flag
  (`action="store_true"`, default `False`); when set, skip `_ensure_uk` and
  the per-audience loop entirely — build a single `StrategyBrief` from
  `infer_audiences(args.topic)[0]`, build `output_path` as
  `output/research/{sanitize_path_segment(args.topic)}_{timestamp}.md`, and
  call `run_pipeline` exactly once with `research_only=True,
  generate_linkedin_post=args.linkedin_post`; log INFO when `--direct` is
  also supplied

> **STOP**: `python -m pytest tests/test_cli.py -v` — confirm all pass.

**Checkpoint**: `python -m pytest tests/test_cli.py -v`

---

## Phase 5: Polish & Cross-Cutting Concerns (RULE 6, 11, 15, 17, 19)

- [x] T014 Run `python -m pytest tests/ -v` — confirm zero failures across the
  whole suite (Constitution §9)
- [x] T015 [P] Run `ruff check . --fix` and `ruff format .` on all modified
  files; confirm `ruff check .` exits 0
- [x] T016 [P] Update `README.md`: add `--research-only` to the CLI flag
  reference for both entry points, and note the new `research_report.md` /
  `output/research/` output in the relevant section (RULE 6, RULE 11)
- [x] T017 [P] Update `docs/architecture.md`: document the research-only skip
  path (which agents are bypassed) and the neutral/branded assembly switch
  (RULE 6)
- [x] T018 [P] Add a new `CHANGELOG.md` entry summarising the `--research-only`
  flag, the neutral `research_report.md` output, and the newly-unlocked
  cartoon-free `--linkedin-post` path (RULE 17)
- [x] T019 [P] Bump version in `pyproject.toml` and `core/__version__.py`
  (RULE 15)
- [x] T020 Update `CLAUDE.md`'s Completed Stages table: add a row for `046`
  once this stage is merged
- [x] T021 Remove the "Research-only mode (no image) — new Spec 046" item
  from `TODO.md` as part of this same PR (RULE 19)

---

## Phase 6: End-to-End Verification (RULE 12 spirit, SC-006)

- [x] T022 Manually run (real API keys via `source set_gata.sh`):
  `python pipeline.py --topic "<real topic>" --audience "<...>" --language English \
  --tone neutral --research-only` — confirm `research_report.md` is written
  under `output/research/<slug>_<timestamp>/`, contains no `.png` or
  `prompt_card.txt`, and reads as neutral/unbranded (no "Gata", no closing
  block, no tech-stack promo)
- [x] T023 Manually run: `gata "<real topic>" --research-only --linkedin-post`
  — confirm `linkedin_post.md`/`linkedin_notification.txt` are written in
  today's branded format, no image or cartoon telemetry appears, and
  `run_pipeline` executed exactly once

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2
- **US2 + US3 (Phase 4)**: Depends on Phase 2 (independent of Phase 3 — different files, `pipeline.py` vs. `core/cli.py`)
- **Polish (Phase 5)**: Depends on Phases 3 and 4 both being complete
- **Verification (Phase 6)**: Depends on Phase 5 (version/docs should reflect the shipped state before a "real" run, though not strictly required for the pipeline to function)

### Within Each Phase

- Test tasks MUST be written and verified to FAIL before implementation tasks begin
- T007 (extract `_minimal_brief`) MUST land before T008 (which calls it) — same file, sequential
- T005/T006/T007/T008 touch four different files and could technically be written in parallel, but T008 depends on both T005 (branded param signature) and T007 (helper) already existing — implement in the listed order

---

## Parallel Opportunities

- T002, T003, T004 (different test files, Phase 2)
- T009 alone in Phase 3 (single file)
- T011, T012 (same file `tests/test_cli.py`, but distinct test functions — write in the same pass, not truly independent processes)
- T015, T016, T017, T018, T019 (Phase 5 polish tasks, independent files)
- Phase 3 and Phase 4 implementation (T010 vs. T013) can proceed in parallel once Phase 2 is done — disjoint files

---

## Summary

| Phase | Tasks | Story | Notes |
|-------|-------|-------|-------|
| 1 Setup | T001 | — | Branch hygiene |
| 2 Foundational | T002–T008 | — | Branded/neutral switch, bundle writer slot, `research_only` mechanism |
| 3 US1 MVP | T009–T010 | US1 | `pipeline.py` flag + neutral report path |
| 4 US2 + US3 | T011–T013 | US2, US3 | `gata` CLI flag + single-run bypass |
| 5 Polish | T014–T021 | — | Full suite + ruff + README + architecture + CHANGELOG + version + CLAUDE.md + TODO.md |
| 6 Verify | T022–T023 | — | Real end-to-end runs (neutral and branded) |
| **Total** | **23 tasks** | | |
