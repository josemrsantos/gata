# Tasks: Image-prompt-only mode

**Input**: Design documents from `specs/056-image-prompt-only/`
**Branch**: `056-image-prompt-only`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅,
contracts/cli-contract.md ✅, quickstart.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions. Test
tasks appear before their corresponding implementation tasks in every phase. Every
test function needs a one-sentence plain-English comment at its top (RULE 3, §9).
Inside function bodies use an inline comment, not a blank line, to mark a change of
focus (RULE 14); `ruff format` forces a blank line after a function-local import, so
use module-level imports in new tests. Zero real API calls in the suite.

**Where the changes go**: the shared request builder and header are in
`agents/agent_image_generator.py` (tests in `tests/test_agent_image_generator.py`); the
prompt-only branch is in `core/runner.py` (tests in `tests/test_pipeline.py`); the file
write is in `core/bundle_writer.py` (tests in `tests/test_bundle_writer.py`); the flag is in
`core/cli.py` (tests in `tests/test_cli.py`) and `pipeline.py` (tests in `tests/test_pipeline.py`).
Because each file is shared by several tasks, tasks inside it are **not** marked [P].

**Decisions already taken** (spec Clarifications, 2026-10-12): the prompt goes in a new
`image_prompt.txt` in each audience's bundle; `prompt_card.txt` is unchanged; the Image
Evaluator is skipped entirely; `--linkedin-post` header states 1200x644; the flag is
ignored with `--research-only` (with a warning).

**Gate**: Constitution §2 forbids writing the image prompt to disk. Task T002 (amendment
v1.5) needs the project lead's explicit approval (G3) before any implementation task starts.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no unmet dependencies)
- **[Story]**: US1 = no image, file and message, US2 = file equals the real request,
  US3 = manual-use header, US4 = several audiences, US5 = entry points and flag combinations
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: Branch hygiene, green baseline, and the governance gate (RULE 5).

- [x] T001 Confirm the branch is `056-image-prompt-only` (not `main`) and run `python -m pytest tests/ -q` and `ruff check .` to record a green baseline before any change
- [x] T002 **[GATE G3 — needs the lead's explicit approval]** Amend `.specify/memory/constitution.md` to v1.5: in §2 replace "The image prompt text is NEVER written to disk; only the final PNG is persisted" with the same rule plus the exception "except in `--image-prompt-only` mode, where the full image request is written to `image_prompt.txt` in the run's bundle at the operator's explicit request"; add the amendment-log entry and an Amendment Record row (v1.5, 2026-10-12, §2, Spec 056). Also update `tests/test_constitution_models.py::test_constitution_version_and_amendment_record_are_1_4` (rename to `..._are_1_5`) to expect v1.5 and the new amendment-record row — write that test change first, so it fails before the amendment and passes after. Show the diff to the lead and wait for "approved" before continuing

---

## Phase 2: Foundational (blocks all stories)

**Purpose**: The shared request builder and header, so the prompt-only and normal paths
cannot drift (FR-004). Every story depends on this.

- [x] T003 Write tests in `tests/test_agent_image_generator.py` first: (a) `build_image_request(concept, layout)` returns exactly `_build_multi_panel_prompt(...)` for a multi-panel concept and exactly `concept.image_prompt` otherwise; (b) `generate()` hands `ImageGeneration` the same string `build_image_request` returns, for single-panel, multi-panel, and the parse-fallback concept (`image_prompt == full_text`). Existing generate() tests must stay green unchanged
- [x] T004 Extract `build_image_request(concept, layout)` from the body of `generate()` in `agents/agent_image_generator.py` and make `generate()` call it; behaviour and prompt text byte-identical to today (SC-006)

**Checkpoint**: T003 passes; all existing `tests/test_agent_image_generator.py` tests still pass.

---

## Phase 3: User Story 1 — Get the Gemini request without paying for an image (P1)

**Goal**: With `--image-prompt-only` no image or evaluator call happens, a prompt file is
written, and the terminal says where it is.

**Independent test**: run the runner with the flag and mocked agents; the image generator
and evaluator mocks are never called, `image_prompt.txt` exists, and the message is printed.

- [x] T005 [US1] Write tests in `tests/test_bundle_writer.py` first: `write_bundle(..., image_prompt_file="X")` writes `image_prompt.txt` with content `X`; without it no `image_prompt.txt` is written; `prompt_card.txt` is written exactly as before in both cases (FR-015)
- [x] T006 [US1] Add the optional `image_prompt_file: str | None = None` parameter to `write_bundle()` in `core/bundle_writer.py` and write `image_prompt.txt` when given; leave the `prompt_card.txt` logic and the return value untouched
- [x] T007 [US1] Write tests in `tests/test_pipeline.py` first (mock all agents): with `image_prompt_only=True`, `agent_image_generator.generate` and `agent_image_evaluator.evaluate` are never called; the telemetry has no "Image Generator" or "Image Evaluator" entry; `write_bundle` receives a non-empty `image_prompt_file`; the printed output contains "No image was auto-generated" and the path ending `image_prompt.txt`; with `image_prompt_only=False` the existing behaviour is unchanged and no `image_prompt_file` is passed
- [x] T008 [US1] Add `image_prompt_only: bool = False` to `run_pipeline()` in `core/runner.py`: after the Satirist, when the flag is set (and not `research_only`) build the request with `build_image_request`, skip the generate/evaluate loop, pass the file text to `write_bundle`, and after it returns print the "No image was auto-generated (--image-prompt-only). Generate it manually: give this file to Gemini as the prompt: <bundle>/image_prompt.txt" message; log an error instead of the path if the file is not on disk
- [x] T009 [US1] Write a test in `tests/test_pipeline.py` first: when the saved request does not contain the verbatim Gata paragraph (parse-fallback concept), a `WARNING` is logged and the file is still written (FR-013, SC-005); when it does, no such warning. The Satirist's existing "verdict parse failed" warning (`agents/agent_satirist.py`) already covers the unreadable-concept case in FR-013 and needs no change
- [x] T010 [US1] Implement the missing-Gata-paragraph check in `core/runner.py` using `_GATA_CHARACTER` from `agents/agent_image_generator.py` (log a `WARNING` via `logger`; never abort)

**Checkpoint**: US1 tests pass; a mocked prompt-only run produces the file and message with no image calls.

---

## Phase 4: User Story 2 — The file is exactly what Gemini would have received (P1)

**Goal**: The request in the file equals what a normal run sends, character for character.

**Independent test**: for a fixed concept, the text after the separator equals the string
`generate()` passes to `ImageGeneration`.

- [x] T011 [US2] Write tests in `tests/test_pipeline.py` first: for single-panel, multi-panel (horizontal and vertical) and parse-fallback concepts, the `image_prompt_file` passed to `write_bundle` ends with `build_image_request(concept, layout)` byte-for-byte (so it holds the request unchanged), and that string equals what the normal path's `generate()` sends (SC-002); the header/separator ahead of it is covered separately in T013/T015
- [x] T012 [US2] Make the runner build the saved file from `build_image_request` only (no second copy of the logic) in `core/runner.py`; confirm T011 passes without changing `agents/agent_image_generator.py`'s request text

**Checkpoint**: SC-002 verified by test for all concept shapes.

---

## Phase 5: User Story 3 — Know the settings that are not in the text (P2)

**Goal**: A short header states the size, title and what is not applied, separated from the pasted text.

**Independent test**: header content for pinned and unpinned sizes, with and without a banner.

- [x] T013 [US3] Write tests in `tests/test_agent_image_generator.py` first: `build_manual_header(title, show_title, target_size)` states the title (or "none"); says the banner is not part of the request and whether the run would have shown one (`show_title` true/false); for `target_size=(1200, 644)` states `1200x644` and the closest Gemini aspect ratio; for `None` says no size is pinned; says the final crop/resize is not applied. `build_prompt_file(...)` returns header + the exact line `===== PASTE EVERYTHING BELOW THIS LINE INTO GEMINI =====` + the request, with the request byte-identical after the separator
- [x] T014 [US3] Implement `build_manual_header()` and `build_prompt_file()` in `agents/agent_image_generator.py`, reusing `_closest_gemini_aspect_ratio` from `core/image_generation.py`
- [x] T015 [US3] Write a test in `tests/test_pipeline.py` first: with `generate_linkedin_post=True` and a horizontal layout the saved header contains `1200x644`; with `generate_linkedin_post=False` it says no size is pinned; with `show_title=False` it says no banner would have been applied (FR-012)
- [x] T016 [US3] In `core/runner.py` build the saved file with `build_prompt_file`, passing the same `_image_target_size` and `show_title` the normal loop uses, so the header can never state a different size than the real run (reuse the existing `_image_target_size` computation, moved above the branch)

**Checkpoint**: header tests pass for all combinations.

---

## Phase 6: User Story 4 — Several audiences give several files (P2)

**Goal**: One prompt file and one message per audience.

**Independent test**: two audiences → two `run_pipeline` calls each with `image_prompt_only=True`, each audience bundle holds its own file, a failing audience does not stop the other.

- [x] T017 [US4] Write tests in `tests/test_cli.py` first: `gata "topic" --audience A --audience B --image-prompt-only` calls `run_pipeline` twice, each with `image_prompt_only=True` and its own `output_path` (so each bundle gets its own file); when the first audience raises, the second still runs and the failure is reported as today; without the flag `run_pipeline` receives `image_prompt_only=False` (FR-001)
- [x] T018 [US4] Add the `--image-prompt-only` argument (store_true, help text from `contracts/cli-contract.md`) to `core/cli.py` and pass `image_prompt_only=args.image_prompt_only` to the audience-loop `run_pipeline` call

**Checkpoint**: multi-audience behaviour verified with mocks.

---

## Phase 7: User Story 5 — Both entry points and flag combinations (P3)

**Goal**: The flag behaves the same on `pipeline.py` and `gata`, and combines correctly with `--research-only`, `--linkedin-post`, `--no-title` and `--html`.

**Independent test**: each `pipeline.py` mode forwards the flag; research-only warns and ignores it.

- [x] T019 [US5] Write tests in `tests/test_pipeline.py` first: `pipeline.py` forwards `image_prompt_only=True` to `run_pipeline` in all four modes (manual, community+topic, named community, free-text community); default is False; with `--research-only --image-prompt-only` a `WARNING` that the flag has no effect is logged and `run_pipeline` is called with the flag ignored (FR-011)
- [x] T020 [US5] Add the `--image-prompt-only` argument to `pipeline.py` (same help text) and pass it at all 4 `run_pipeline` calls; log the research-only warning once at startup
- [x] T021 [US5] Write a test in `tests/test_cli.py` first: `gata "topic" --research-only --image-prompt-only` logs the "no effect" warning and still runs the research-only path once (FR-011)
- [x] T022 [US5] Pass the flag to the research-only `run_pipeline` call in `core/cli.py` and log the warning there
- [x] T023 [US5] Write a test in `tests/test_pipeline.py` first: with `image_prompt_only=True, include_html=True` the explainer is still invoked (no image dependency) and `explanation.html`/`deep_dive_en.html` are produced; with `image_prompt_only=True, generate_linkedin_post=True` the LinkedIn step still runs (FR-009)

**Checkpoint**: both entry points and combinations verified; FR-009 confirmed (nothing extra is skipped).

---

## Phase 8: Polish and cross-cutting

**Purpose**: Docs, version, governance bookkeeping, final checks (RULES 6, 15, 17, 19).

- [x] T024 [P] Update `README.md`: add `--image-prompt-only` to the `gata` and `pipeline.py` option lists and a short "manual image" paragraph; add `image_prompt.txt` to the bundle file table; correct the `prompt_card.txt` row at README.md:204 (it holds the concept text, not the verbatim image request, for multi-panel cartoons); update the status table with row 56 (RULE 17, RULE 6)
- [x] T025 [P] Update `docs/architecture.md`: the image step is skippable; add `image_prompt.txt` to the bundle description; mention the shared request builder (RULE 17)
- [x] T026 [P] Add `v1.33.0` entry to `CHANGELOG.md` in plain English (RULE 17)
- [x] T027 Bump the version `1.32.0` → `1.33.0` in `pyproject.toml` and `core/__version__.py` (RULE 15)
- [x] T028 Add the row `056 | Image-prompt-only mode …` to the Completed Stages table in `CLAUDE.md` (RULE 19 pattern)
- [ ] T029 **[needs the lead's go-ahead — RULE 8 / G3]** Show the exact removal of the "Image-prompt-only mode" item from `TODO.md` and, once approved, remove it in this PR (RULE 19)
- [x] T030 Run `python -m pytest tests/ -q`, `ruff check .` and `ruff format --check .`; all must pass with zero failures (§9, §12)
- [x] T031 Self-review the diff three times, assuming each earlier pass made a mistake (CLAUDE.md SELF-REVIEW), before presenting G4
- [x] T032 **[optional, approved at G2]** Run the live check in `quickstart.md` §2 (`gata "..." --image-prompt-only -v`, text stages only) and inspect `image_prompt.txt`; report what was verified and what was not

---

## Dependencies

```
T001 → T002 (GATE) → T003 → T004 → Phase 3..7
T004 → T011/T012/T013/T014   (builder first)
T005/T006 → T007/T008        (bundle file before runner passes it)
T008 → T010 → T012 → T016    (runner edits in one file, in order)
T017/T018 and T019–T022 are independent of each other after T008
T024–T026 can run in parallel; T027–T029 after all code; T030–T032 last
```

Story order by priority: US1 → US2 → US3 → US4 → US5. Each story's checkpoint is
independently testable with mocks.

## Parallel opportunities

- T024, T025, T026 (three different docs).
- After T008: the `core/cli.py` tasks (T017–T018, T021–T022) and the `pipeline.py` tasks (T019–T020) touch different files and can be done in parallel by two workers; tests in `tests/test_cli.py` and `tests/test_pipeline.py` are separate files, but `tests/test_pipeline.py` is shared by several tasks and is therefore sequential inside itself.

## Implementation strategy

**MVP = Phase 2 + User Story 1 (+ US2)**: the flag works from the runner, the file is the
real request, and the message appears. US3 adds the header, US4 and US5 add the entry points
and combinations. Stop after each checkpoint if cost or scope changes.

## Counts

32 tasks: Setup 2, Foundational 2, US1 6, US2 2, US3 4, US4 2, US5 5, Polish 9.
