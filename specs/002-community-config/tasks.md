# Tasks: Community Configuration (Stage 2)

**Input**: Design documents from `specs/002-community-config/`
**Branch**: `002-stage-2-community-config`
**Constitution**: Principle 9 — tests MUST be written before implementation, no exceptions.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unresolved dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths are required in every description

---

## Phase 1: Setup

**Purpose**: Add the one new dependency and the new shared datatype that every subsequent task depends on.

- [ ] T001 Add `pyyaml` to `[project] dependencies` in `pyproject.toml` and run `.venv/bin/pip install pyyaml` to make it available immediately
- [ ] T002 Add `Community` dataclass to `agents/types.py` with fields `name: str`, `target_audience: str`, `output_language: str`, `tone: str`, `topics: list[str]` and a `to_brief(self) -> StrategyBrief` method that returns `StrategyBrief(target_audience=self.target_audience, output_language=self.output_language, tone=self.tone)`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config loader + sanitization + agent_d signature change + logging migration — all must be complete before any user story pipeline work begins.

**⚠️ CRITICAL**: No user story pipeline work can begin until this phase is complete.

- [ ] T003 [P] Write `tests/test_config_loader.py` — tests for `sanitize_path_segment` (lowercase, spaces→underscores, non-alphanum stripped, 50-char truncation, empty string, accented characters stripped), and tests for `load_communities` covering: valid config returns list of `Community` objects; file not found raises `ValueError` naming the path; invalid YAML raises `ValueError`; missing required field raises `ValueError` naming the community and field; empty topics list raises `ValueError`; duplicate community names raises `ValueError` naming the duplicate; empty communities list raises `ValueError`
- [ ] T004 [P] Update `tests/test_agent_d.py` — replace all `patch("agents.agent_d.OUTPUT_PATH", ...)` patches with direct `output_path` argument in `generate()` calls; update every test that calls `generate(concept, brief)` to `generate(concept, brief, output_path="output/test_output.png")`
- [ ] T005 [P] Migrate `print()` → `logging` in `agents/agent_bc.py` — add `import logging` and `logger = logging.getLogger(__name__)` at module level; replace every `print(...)` call with the appropriate `logger.info(...)` or `logger.warning(...)` call; preserve all existing message text
- [ ] T006 Implement `agents/config_loader.py` — `sanitize_path_segment(text: str) -> str` (lowercase, spaces→underscores, strip `[^a-z0-9_]`, truncate to 50 chars) and `load_communities(path: str) -> list[Community]` that reads YAML, validates the `communities` top-level key, validates each entry has all 5 required non-blank fields, validates `topics` is non-empty with all non-blank items, validates no duplicate `name` values, and raises `ValueError` with a precise message for every failure case. Depends on T003 (tests must exist first).
- [ ] T007 Update `agents/agent_d.py` — remove module-level `OUTPUT_PATH` constant; add `output_path: str` as a third required parameter to `generate(concept: CartoonConcept, brief: StrategyBrief, output_path: str) -> str`; replace `OUTPUT_PATH` references with the `output_path` parameter; add `import logging` and `logger = logging.getLogger(__name__)`; replace all `print()` calls with appropriate `logger.info()` / `logger.error()` calls. Depends on T004 (tests must exist first).

**Checkpoint**: `pytest tests/test_config_loader.py tests/test_agent_d.py` passes. `ruff check agents/config_loader.py agents/agent_bc.py agents/agent_d.py` passes.

---

## Phase 3: User Story 1 — Named Community Mode (Priority: P1) 🎯 MVP

**Goal**: `python pipeline.py --community uk-tech-engineers` runs the full pipeline using that community's settings and saves the cartoon to `output/uk_tech_engineers/<sanitized_topic>.png`.

**Independent Test**: `pytest tests/test_pipeline.py -k community` passes; manual run `python pipeline.py --community uk-tech-engineers` produces an image at the expected path.

- [ ] T008 [US1] Write tests for `--community` mode in `tests/test_pipeline.py` — mock `load_communities`, `agent_bc.run`, and `agent_d.generate`; test that: a valid `--community` name selects the correct community and passes its `to_brief()` to `agent_bc.run`; an unknown community name prints to stderr and exits with code 1 before any agent call; the output path passed to `agent_d.generate` is `output/{sanitized_community}/{sanitized_topic}.png`
- [ ] T009 [US1] Rewrite `pipeline.py` — remove hardcoded `TOPIC`/`BRIEF` constants; add `import logging`, `import argparse`, `import random`; call `logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")` at the top of `main()`; build an `argparse.ArgumentParser` with `--community` (optional str); in community mode: call `load_communities("communities.yaml")`, look up the named community (exit code 1 if not found), `random.choice(community.topics)`, compute `output_path = f"output/{sanitize_path_segment(community.name)}/{sanitize_path_segment(topic)}.png"`, `os.makedirs` the directory, log selected community and topic, call `agent_bc.run(topic, community.to_brief())` then `agent_d.generate(concept, community.to_brief(), output_path)`. Depends on T008.

**Checkpoint**: `pytest tests/test_pipeline.py -k community` passes. `python pipeline.py --community uk-tech-engineers` produces `output/uk_tech_engineers/<topic>.png`.

---

## Phase 4: User Story 2 — Random Community Mode (Priority: P2)

**Goal**: `python pipeline.py` (no arguments) selects a community at random and runs the full pipeline.

**Independent Test**: `pytest tests/test_pipeline.py -k random` passes; manual run `python pipeline.py` with no args completes and logs which community and topic were selected.

- [ ] T010 [US2] Write tests for no-args random community mode in `tests/test_pipeline.py` — mock `load_communities`, `agent_bc.run`, `agent_d.generate`; test that: when no arguments are provided, one community is selected from the list (use `side_effect` to verify `random.choice` is called on the communities list); the selected community's topic list is used for the second `random.choice`; the pipeline completes without error
- [ ] T011 [US2] Add random community mode to `pipeline.py` — when no `--community` and no manual flags are present, call `load_communities("communities.yaml")` then `random.choice(communities)` to pick a community, `random.choice(community.topics)` for the topic, then follow the same path as T009 (compute path, log, run agents). Depends on T010.

**Checkpoint**: `pytest tests/test_pipeline.py -k "community or random"` passes. `python pipeline.py` completes and saves an image.

---

## Phase 5: User Story 3 — Manual Mode (Priority: P2)

**Goal**: `python pipeline.py --topic "AI hype" --audience "developers" --language "English" --tone "dry"` runs the full pipeline without loading `communities.yaml`.

**Independent Test**: `pytest tests/test_pipeline.py -k manual` passes; manual run with the four flags and no `communities.yaml` present completes without error.

- [ ] T012 [US3] Write tests for manual mode in `tests/test_pipeline.py` — mock `load_communities`, `agent_bc.run`, `agent_d.generate`; test that: all four flags provided runs pipeline without calling `load_communities`; output path is `output/manual/{sanitized_topic}.png`; missing any one of the four flags exits code 1 with error before any agent call; providing `--community` alongside any manual flag exits code 1 with conflict error before any agent call
- [ ] T013 [US3] Add manual mode to `pipeline.py` — extend argparse with `--topic`, `--audience`, `--language`, `--tone`; post-parse: if any manual flag present but not all four, exit code 1 with `"Error: manual mode requires all four flags: --topic, --audience, --language, --tone"`; if `--community` and any manual flag both present, exit code 1 with `"Error: --community and manual mode flags (--topic, --audience, --language, --tone) are mutually exclusive"`; in manual mode: do NOT call `load_communities`; build `StrategyBrief` from flags; output path is `f"output/manual/{sanitize_path_segment(topic)}.png"`; `os.makedirs` the directory; log topic and output path; call agents. Depends on T012.

**Checkpoint**: `pytest tests/test_pipeline.py -k manual` passes. Running with all four flags and no `communities.yaml` present produces `output/manual/<topic>.png`.

---

## Phase 6: User Story 4 — Config Validation (Priority: P3)

**Goal**: Missing, malformed, or invalid `communities.yaml` exits with a clear error message before any API call.

**Independent Test**: `pytest tests/test_pipeline.py -k validation` passes; manual runs with bad config produce precise error messages and exit code 1.

**Note**: Validation logic is fully implemented in `agents/config_loader.py` (T006) and tested in `tests/test_config_loader.py` (T003). This phase adds pipeline-level integration tests confirming the errors propagate correctly to stderr and exit code 1.

- [ ] T014 [US4] Write pipeline integration tests for config validation in `tests/test_pipeline.py` — test that: `load_communities` raising `ValueError` for a missing file causes `main()` to print the error to stderr and exit code 1 without calling any agent; same for malformed YAML error; same for duplicate community name error; no `agent_bc.run` or `agent_d.generate` call is made in any of these cases
- [ ] T015 [US4] Verify `pipeline.py` exception handling — confirm the `try/except Exception` block in `main()` catches `ValueError` from `load_communities` and routes it to `logger.error(str(exc))` + `sys.exit(1)`; update the handler if it currently uses `print()` (migrate to `logger.error`). Depends on T014.

**Checkpoint**: `pytest tests/test_pipeline.py -k validation` passes. `python pipeline.py --community nonexistent` exits 1 with the correct error.

---

## Phase 7: Polish & Verification

**Purpose**: Quality gate — ruff, full test suite, and one live end-to-end run.

- [ ] T016 [P] Run `ruff check . && ruff format .` — fix all violations in `pipeline.py`, `agents/config_loader.py`, `agents/types.py`, `agents/agent_bc.py`, `agents/agent_d.py`, and all test files; no violations permitted before this task is marked complete
- [ ] T017 [P] Run `pytest tests/` — all tests must pass; fix any failures before marking complete
- [ ] T018 Run end-to-end: `python pipeline.py --community uk-tech-engineers` — verify log output includes selected community, selected topic, and output path; verify image file exists at `output/uk_tech_engineers/<sanitized_topic>.png`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — blocks all user story work
- **US1 (Phase 3)**: Depends on Phase 2 — first story to implement
- **US2 (Phase 4)**: Depends on Phase 3 (shares `pipeline.py` — builds on argparse skeleton from T009)
- **US3 (Phase 5)**: Depends on Phase 4 (same reason — extends the same argparse setup)
- **US4 (Phase 6)**: Depends on Phase 3 (config loading already wired by T009)
- **Polish (Phase 7)**: Depends on all story phases

### Within Each Phase

- T003, T004, T005 can run in parallel (different files)
- T006 depends on T003 — tests must exist before config_loader implementation
- T007 depends on T004 — tests must exist before agent_d update
- T008 (test) before T009 (implementation) — constitution Principle 9
- T010 (test) before T011 (implementation)
- T012 (test) before T013 (implementation)
- T014 (test) before T015 (implementation)
- T016 and T017 can run in parallel; T018 runs after both

### Parallel Opportunities

```bash
# Phase 2 — run these three together:
Task T003: "Write tests/test_config_loader.py"
Task T004: "Update tests/test_agent_d.py"
Task T005: "Migrate agent_bc.py print()→logging"

# Phase 7 — run together:
Task T016: "ruff check && ruff format"
Task T017: "pytest tests/"
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T007)
3. Complete Phase 3: US1 — Named Community Mode (T008–T009)
4. **STOP and VALIDATE**: `python pipeline.py --community uk-tech-engineers` produces a cartoon
5. Proceed to US2, US3, US4 in order

### Incremental Delivery

1. Setup + Foundational → Community loader and logging infrastructure ready
2. US1 → Named community mode works → MVP demonstrated
3. US2 → Random community mode adds automation capability
4. US3 → Manual mode restores developer escape hatch
5. US4 → Validation integration confirmed
6. Polish → Full test suite and ruff pass; stage complete

---

## Notes

- Every test file must be written and its tests confirmed to FAIL before the corresponding implementation task starts (Constitution Principle 9)
- `ruff check` must pass on every file before that file's task is marked `[x]`
- CLAUDE.md Human Review Protocol applies: stop after each test file and each implementation file for explicit approval before proceeding
- `communities.yaml` is already committed — do not recreate it
