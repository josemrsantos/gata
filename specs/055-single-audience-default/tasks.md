# Tasks: Single-audience default for gata

**Input**: Design documents from `specs/055-single-audience-default/`
**Branch**: `055-single-audience-default`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅,
contracts/cli-contract.md ✅, quickstart.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions. Test
tasks appear before their corresponding implementation tasks in every phase. Every
test function needs a one-sentence plain-English comment at its top (RULE 3, §9).
Inside function bodies use an inline comment, not a blank line, to mark a change of
focus (RULE 14); `ruff format` forces a blank line after a function-local import, so
use module-level imports in new tests. Zero real API calls in the suite.

**Where the changes go**: all source changes are in `core/cli.py`; all test changes in
`tests/test_cli.py`. Because both files are shared by every story, tasks inside them
are **not** marked [P].

**Decisions already taken** (spec Clarifications): `--audience` takes community names
only; it replaces the default; `--infer-audiences` restores today's behaviour; the
default is built into `gata`; layout stays automatic; `--research-only` uses the first
selected audience. Three assumptions are for the lead to confirm at G2: the built-in
default answers to its own name when `communities.yaml` is absent; the file's entry wins
when `uk-tech-engineers` is named and the file exists; `--infer-audiences` with
`--audience` is rejected.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no unmet dependencies)
- **[Story]**: US1 = default is one audience, US2 = `--audience`, US3 = other options
  keep working, US4 = `--infer-audiences`
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: Branch hygiene and a green baseline (RULE 5).

- [ ] T001 Confirm active git branch is `055-single-audience-default`; if on `main`, switch before touching any source file
- [ ] T002 Run `python -m pytest tests/ -q` and `ruff check .`; record that both pass on the untouched code (717 tests at the start)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The built-in default and the two new options exist (parsing only) so every
story can build on them.

**CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Write failing tests in `tests/test_cli.py` (one-sentence comment each): (a) `core.cli._DEFAULT_AUDIENCE` equals the `uk-tech-engineers` entry of the repo's `communities.yaml` on `target_audience`/`output_language`/`tone` — "the built-in values MUST match the `uk-tech-engineers` entry in `communities.yaml`, and a test MUST fail if they drift apart" (FR-006); (b) `gata --help` (run via `main()` with `sys.argv = ["gata", "--help"]`, expecting `SystemExit(0)`, text read with `capsys`) mentions `uk-tech-engineers`, `--audience` and `--infer-audiences` (FR-011, SC-006)
- [ ] T004 In `core/cli.py` add the module constant `_DEFAULT_AUDIENCE = AudienceProfile(name="uk-tech-engineers", audience="British software engineers and developers", language="English", tone="dry British wit")` next to `_UK_AUDIENCE`
- [ ] T005 In `core/cli.py` register `--audience` (`action="append"`, `metavar="NAME"`) and `--infer-audiences` (`action="store_true"`) with the help text from `contracts/cli-contract.md`, and change the parser description to state the default audience (parsing only — no behaviour yet)

**Checkpoint**: `python -m pytest tests/test_cli.py -k "default_audience or help" -v`

---

## Phase 3: User Story 1 — A default run produces one cartoon (Priority: P1) MVP

**Goal**: With no audience option, `gata` runs the pipeline exactly once, for `uk-tech-engineers`, with no guessing call and no "UK public" (FR-001, FR-002, FR-010).

**Independent Test**: `gata "some topic"` writes exactly one image `<topic-folder>/uk-tech-engineers.png` and shows a single `[1/1]` line.

### Tests for User Story 1 — Write FIRST, Confirm FAILING Before Implementation

- [ ] T006 [US1] In `tests/test_cli.py` write a failing test: running `gata "topic"` (patched `run_pipeline`, patched `infer_audiences`, `os.makedirs`) calls `run_pipeline` exactly once, with a seed brief built from `_DEFAULT_AUDIENCE` and an output path ending `uk-tech-engineers.png`, and `infer_audiences` is **not** called (SC-001, SC-002)
- [ ] T007 [US1] In `tests/test_cli.py` write a failing test: the default run prints `[1/1] uk-tech-engineers — English` (read with `capsys`), the output contains no `UK public`, and the written `summary.txt` has exactly one audience line (`uk-tech-engineers: …`) followed by a `TOTAL:` line (FR-002, FR-010, US1 scenario 3)
- [ ] T008 [US1] In `tests/test_cli.py` write a failing test: the default run still works when the current folder has no `communities.yaml` (`monkeypatch.chdir(tmp_path)`), with one `run_pipeline` call (FR-006)

> **STOP**: Confirm T006–T008 FAIL (`python -m pytest tests/test_cli.py -v`) before proceeding to T009.

### Implementation for User Story 1

- [ ] T009 [US1] In `core/cli.py` make the non-research path use `audiences = [_DEFAULT_AUDIENCE]` instead of `_ensure_uk(infer_audiences(args.topic))` (the `--infer-audiences` path is restored in Phase 4)
- [ ] T010 [US1] In `core/cli.py` make the `--research-only` path use `_DEFAULT_AUDIENCE` instead of `infer_audiences(args.topic)[0]` (the first-selected-audience rule is completed in Phase 6). Note: `infer_audiences` is imported but unused until T014, so `ruff check` would report F401 here — expected; do not run ruff as a gate before T014

> **STOP**: T006–T008 now PASS. Several older tests that assume guessing will FAIL — that is expected and is fixed in T016. Do not push until Phase 4 is done.

**Checkpoint**: `python -m pytest tests/test_cli.py -k "default" -v`

---

## Phase 4: User Story 4 — Ask for the old behaviour (Priority: P3, built before US2 so old tests keep their meaning)

**Goal**: `--infer-audiences` reproduces today's audience selection exactly (FR-005, SC-007).

**Independent Test**: `gata "topic" --infer-audiences` guesses audiences and adds UK when none is UK.

### Tests for User Story 4 — Write FIRST, Confirm FAILING Before Implementation

- [ ] T011 [US4] In `tests/test_cli.py` write a failing test: `--infer-audiences` calls `infer_audiences` once and runs `run_pipeline` once per returned audience, adding the `UK public` audience when none of them is UK (use the file's `_AUDIENCES` fixture and a no-UK variant) (SC-007)
- [ ] T012 [US4] In `tests/test_cli.py` write a failing test: `--infer-audiences --research-only` runs `run_pipeline` once, using the first guessed audience (as today)
- [ ] T013 [US4] In `tests/test_cli.py` write a failing test: `--infer-audiences` together with `--audience uk-politics` exits with status 1, logs `--infer-audiences and --audience cannot be used together` at ERROR (caplog), and calls neither `infer_audiences` nor `run_pipeline`

> **STOP**: Confirm T011–T013 FAIL before proceeding to T014.

### Implementation for User Story 4

- [ ] T014 [US4] In `core/cli.py` restore the guessing path behind the flag: with `args.infer_audiences`, normal runs use `_ensure_uk(infer_audiences(args.topic))` and `--research-only` uses `infer_audiences(args.topic)[0]`; keep `_UK_AUDIENCE`, `_ensure_uk`, and the `infer_audiences` import
- [ ] T015 [US4] In `core/cli.py` reject `--infer-audiences` with `--audience`: after `logging.basicConfig` and before the API-key check, `logger.error("--infer-audiences and --audience cannot be used together")` and `sys.exit(1)`
- [ ] T016 [US4] Run `python -m pytest tests/test_cli.py -v`. For every PRE-EXISTING test in `tests/test_cli.py` that now fails because it assumed the guessed-audience default (expected: the per-audience verbose test, the research-only tests that expect the first *inferred* audience, and any test relying on `_ensure_uk`): if its intent is the guessing behaviour, add `--infer-audiences` to its `sys.argv`; if its intent is generic, change its expectation to the default audience. Add a one-line note in each edited test's comment saying which and why (FR-012)

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests PASS before proceeding.

**Checkpoint**: `python -m pytest tests/test_cli.py -v`

---

## Phase 5: User Story 2 — Choose the audiences yourself (Priority: P2)

**Goal**: `--audience` selects community audiences by name, in order, de-duplicated, validated before any paid call (FR-003, FR-003a, FR-004, FR-007).

**Independent Test**: `gata "topic" --audience uk-politics --audience portuguese-adults` produces two images and `[1/2]`/`[2/2]` lines.

### Tests for User Story 2 — Write FIRST, Confirm FAILING Before Implementation

Use `monkeypatch.chdir(tmp_path)` with a small `communities.yaml` written to `tmp_path` (names `uk-politics`, `portuguese-adults`, `uk-tech-engineers`, each with the three required fields plus `panels: 3`, `layout: vertical`).

- [ ] T017 [US2] In `tests/test_cli.py` write a failing test: `--audience uk-politics` runs once, with a seed brief built from that community's `target_audience`/`output_language`/`tone`, output path ending `uk-politics.png`, no `infer_audiences` call (FR-003, FR-004)
- [ ] T018 [US2] In `tests/test_cli.py` write a failing test: two `--audience` values run in the order given, output paths `<a>.png` then `<b>.png` in the same folder, and the progress lines `[1/2]` and `[2/2]` appear (SC-003, FR-010)
- [ ] T019 [US2] In `tests/test_cli.py` write a failing test: the same audience given twice runs once (spec scenario 3)
- [ ] T020 [US2] In `tests/test_cli.py` write a failing test: an unknown name exits 1, logs a message containing the value and the valid names (e.g. `unknown audience 'nope' — valid audiences:` plus the names), and calls neither `infer_audiences` nor `run_pipeline` (FR-007, SC-004)
- [ ] T021 [US2] In `tests/test_cli.py` write a failing test: `--audience ""` is rejected the same way, naming the empty value (FR-007)
- [ ] T022 [US2] In `tests/test_cli.py` write failing tests for a folder with **no** `communities.yaml`: `--audience uk-tech-engineers` runs once with the built-in default; `--audience uk-politics` exits 1 with a message containing `communities.yaml not found in the current folder` and `only the built-in audience 'uk-tech-engineers'` (FR-007); and a folder whose `communities.yaml` exists but has **no** `uk-tech-engineers` entry: `--audience uk-tech-engineers` is rejected as unknown (the file wins; the built-in copy only serves the file-absent case)
- [ ] T023 [US2] In `tests/test_cli.py` write a failing test: for a community with `panels: 3` / `layout: vertical`, `run_pipeline` is called without any `panels` or `layout` keyword and nothing about them reaches the call (FR-003a)
- [ ] T024 [US2] In `tests/test_cli.py` write a failing test: an invalid `communities.yaml` (e.g. missing `communities` key) with `--audience x` exits 1 and logs the loader's message at ERROR (contract row 4)

> **STOP**: Confirm T017–T024 FAIL before proceeding to T025.

### Implementation for User Story 2

- [ ] T025 [US2] In `core/cli.py` add `_resolve_audience_names(names: list[str]) -> list[AudienceProfile]` per research D3: strip values, reject empty, de-duplicate keeping first position, load `communities.yaml` from the current folder only if it exists (else accept only `_DEFAULT_AUDIENCE.name`; when the file exists it is the only source of valid names, even for `uk-tech-engineers`), build `AudienceProfile(name, audience=target_audience, language=output_language, tone=tone)` from each community, and raise `ValueError` with the exact messages in `contracts/cli-contract.md` (unknown value + valid choices; file not found; loader errors passed through)
- [ ] T026 [US2] In `core/cli.py` wire it into `main()`: after `logging.basicConfig` and before the API-key check, when `args.audience` is given call `_resolve_audience_names(args.audience)`; on `ValueError` `logger.error(str(exc))` and `sys.exit(1)`; the resulting list becomes `audiences` for the existing per-audience loop

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests PASS before proceeding.

**Checkpoint**: `python -m pytest tests/test_cli.py -k audience -v`

---

## Phase 6: User Story 3 — Other options keep working per audience (Priority: P3)

**Goal**: The existing options behave as today for every selected audience, and `--research-only` uses the first selected audience (FR-008, FR-009).

**Independent Test**: `gata "topic" --audience uk-politics --audience portuguese-adults --no-title --html` passes `show_title=False` and `include_html=True` to both runs.

### Tests for User Story 3 — Write FIRST, Confirm FAILING Before Implementation

- [ ] T027 [US3] In `tests/test_cli.py` write a failing test: `--research-only --audience uk-politics --audience portuguese-adults` runs `run_pipeline` once for `uk-politics` and logs a WARNING (caplog) saying `portuguese-adults` is ignored; and `--research-only` alone uses the default audience (FR-008, SC-008)
- [ ] T028 [US3] In `tests/test_cli.py` write a test (regression guard, expected to pass already): with two `--audience` values plus `--no-title --html --direct --linkedin-post --angle X --verbose`, every `run_pipeline` call receives `show_title=False`, `include_html=True`, `skip_cultural_strategist=True`, `generate_linkedin_post=True`, `angles=["X"]`, `verbose=True` (FR-009)
- [ ] T029 [US3] In `tests/test_cli.py` write a test (regression guard, expected to pass already): when the first of two audiences raises `RuntimeError`, the second still runs and `main()` exits 1 with the partial-failure message (spec edge case)

> **STOP**: Confirm T027 FAILS (T028 and T029 may already pass) before proceeding to T030.

### Implementation for User Story 3

- [ ] T030 [US3] In `core/cli.py` make the `--research-only` branch use the first selected audience (`audiences[0]`; or `infer_audiences(topic)[0]` with `--infer-audiences`), and when more than one `--audience` value was resolved emit `logger.warning` naming the ignored audiences

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests PASS before proceeding.

**Checkpoint**: `python -m pytest tests/test_cli.py -v`

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T031 [P] Run `ruff check . --fix` and `ruff format .` on all modified files; confirm `ruff check .` exits 0 (§12)
- [ ] T032 [P] Update `README.md`: the `gata` command section (new default, `--audience` with examples, `--infer-audiences`), the Communities section if it implies `gata` ignores communities, and add the spec 055 row to the status table (RULE 6, RULE 17); list exactly what was stale before editing
- [ ] T033 [P] Update `docs/architecture.md`: the audience-selection description and any wording that says a UK audience is always added or that audiences are always inferred (RULE 17)
- [ ] T034 [P] Add a v1.31.0 entry at the top of `CHANGELOG.md` in plain English: default is one audience (`uk-tech-engineers`), `--audience`, `--infer-audiences`, what changed for users who relied on the guessed audiences (RULE 17)
- [ ] T035 [P] Bump the version to `1.31.0` in `pyproject.toml` and `core/__version__.py` (RULE 15)
- [ ] T036 [P] Add the 055 row to the "Completed Stages" table in `CLAUDE.md` (and update its "as of" date), in this PR, as specs 050, 052 and 054 did
- [ ] T037 [P] Remove the "Single-audience default for `gata`" item from `TODO.md` in this same PR (RULE 19); touch no other item
- [ ] T038 Check for stale claims: `grep -rniE "always (added|present|included)|UK public|inferred" README.md docs` — only text that correctly describes `--infer-audiences` may remain
- [ ] T039 Run the free manual checks in `specs/055-single-audience-default/quickstart.md` §2 (they exit before any model call, so they cost nothing) and confirm each prints the expected `ERROR:` text and exits 1
- [ ] T040 Optional — only if the project lead approves it at G2: run the paid smoke test in `quickstart.md` §3 (`gata "model currency smoke test"`, one pipeline run) and confirm one `[1/1] uk-tech-engineers — English` line and one image; otherwise mark it skipped and say so in the PR
- [ ] T041 Run `python -m pytest tests/ -q` — must report 0 failures; do the three self-review passes (G4 rules), commit, push the branch and open the PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2. After T009 the older guessing-based tests fail until T016.
- **US4 (Phase 4)**: Depends on Phase 3. It is P3 in the spec but is built second because it restores the old behaviour that the pre-existing tests need (T016) and is needed for the `--infer-audiences`/`--audience` conflict check.
- **US2 (Phase 5)**: Depends on Phase 4
- **US3 (Phase 6)**: Depends on Phase 5 (it uses named audiences)
- **Polish (Phase 7)**: Depends on all stories being complete

### Within Each Phase

- Test tasks MUST be written and verified to FAIL before implementation tasks begin
- Everything in Phases 2–6 edits `core/cli.py` and `tests/test_cli.py`: do tasks in numeric order
- Do not push between T009 and T016 (the suite is knowingly red)

---

## Parallel Opportunities

- Phase 7: T031–T037 touch different files and can run together (T031 last if it reformats files others edit)
- Phases 2–6 are sequential by design: one source file, one test file

---

## Implementation Strategy

- **MVP**: Phases 1–4 together (US1 + US4): the default is one audience and the old behaviour stays reachable behind a flag. Stop and validate with the Phase 3 and 4 checkpoints.
- **Incremental**: add US2 (`--audience`), then US3 (research-only and the regression guards), then Polish.
- **Risk controls**: validation happens before any paid call; the old behaviour is preserved verbatim behind `--infer-audiences`; no model, layout or `communities.yaml` change.

---

## Summary

| Phase | Tasks | Story | Notes |
|-------|-------|-------|-------|
| 1 Setup | T001–T002 | — | Branch, baseline |
| 2 Foundational | T003–T005 | — | Built-in default, drift test, option parsing |
| 3 US1 MVP | T006–T010 | US1 | Default = one audience |
| 4 US4 | T011–T016 | US4 | `--infer-audiences`, fix old tests |
| 5 US2 | T017–T026 | US2 | `--audience` |
| 6 US3 | T027–T030 | US3 | research-only, option regression guards |
| 7 Polish | T031–T041 | — | ruff, docs, version, TODO, checks, PR |
| **Total** | **41 tasks** | | |
