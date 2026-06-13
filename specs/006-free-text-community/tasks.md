# Tasks: Free-Text Community Mode

**Input**: Design documents from `specs/006-free-text-community/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/cli.md ✅, quickstart.md ✅

**Tests**: Included (constitution Principle 9 requires tests before implementation — no exceptions).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared state dependency)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup

**Purpose**: No new project initialization is needed — this is an additive feature on an existing project with all tooling already configured.

*(No tasks — skip to Phase 2)*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Refactor the internal Gemini ranking helper in `agents/trend_scout.py` so it is reusable by both the existing named-community path and the new free-text path. Must complete before any user story work begins.

**⚠️ CRITICAL**: US1 and US3 both depend on this refactor. No user story work can begin until T002 passes.

- [ ] T001 Write regression tests for the current `_rank_with_gemini()` behaviour (inputs: headline list + Community fields; output: ranked title list) in `tests/test_trend_scout.py` — these must pass both before and after the refactor in T002
- [ ] T002 Refactor `_rank_with_gemini(headlines, community, n)` → `_rank_headlines(headlines, audience, language, tone, description_hint, n)` in `agents/trend_scout.py`; update the single call site in `get_topics()` to pass community fields and `description_hint=""`; run T001 tests to confirm no regression

**Checkpoint**: `python -m pytest tests/test_trend_scout.py` passes — existing ranking behaviour preserved.

---

## Phase 3: User Story 1 — Ad-hoc community produces cartoon (Priority: P1) 🎯 MVP

**Goal**: `python pipeline.py --community "US community that dislikes Trump"` produces a complete cartoon bundle end-to-end.

**Independent Test**: Run the command above with no matching entry in `communities.yaml`; verify `output/us_community_that_dislikes_trump/` bundle is created.

### Tests for US1

- [ ] T003 [P] [US1] Write unit tests for `infer_brief_from_description()` in `tests/test_trend_scout.py`: mocked Gemini returns valid JSON → StrategyBrief fields populated correctly; mocked Gemini returns malformed JSON → defaults applied; mocked Gemini returns partial JSON (missing one key) → missing field gets default
- [ ] T004 [P] [US1] Write unit tests for `get_topics_for_description()` in `tests/test_trend_scout.py`: mocked inference + mocked adapter + mocked `_rank_headlines` → returns (list[Headline], StrategyBrief, "trend_scout"); mocked adapter returns empty list → returns ([], brief, "none")
- [ ] T005 [P] [US1] Write pipeline integration tests for free-text path in `tests/test_pipeline.py`: `--community "unknown desc"` with no communities.yaml match → calls `get_topics_for_description`; output path uses sanitized description as folder name; `_run_pipeline` called with inferred StrategyBrief

### Implementation for US1

- [ ] T006 [P] [US1] Add module-level constants to `agents/trend_scout.py`: `_INFERENCE_SYSTEM` (system prompt asking for JSON `{target_audience, output_language, tone}`), `_INFERENCE_DEFAULTS` dict with fallback values, `_DEFAULT_NEWS_SOURCES` list (US general + GB general, 10 articles each)
- [ ] T007 [US1] Implement `infer_brief_from_description(description: str) -> StrategyBrief` in `agents/trend_scout.py`: single Gemini call using `_GEMINI_MODEL`; strip markdown fences; `json.loads()`; apply `_INFERENCE_DEFAULTS` for any absent or blank field; log inferred values at INFO; log WARNING when a default is applied
- [ ] T008 [US1] Implement `get_topics_for_description(description: str, n: int = 3, *, adapter: SourceAdapter | None = None) -> tuple[list[Headline], StrategyBrief, str]` in `agents/trend_scout.py`: calls `infer_brief_from_description`; fetches headlines via `_DEFAULT_NEWS_SOURCES` using a synthetic `Community`; calls `_rank_headlines` with `description_hint=description`; returns `(ranked, brief, "trend_scout")` or `([], brief, "none")` on empty fetch
- [ ] T009 [US1] Modify `pipeline.py` `elif args.community:` branch: check `os.path.exists("communities.yaml")` before calling `load_communities()`; set `communities = []` when file absent; if exact name match found use existing named-community path unchanged; if no match call `trend_scout.get_topics_for_description(args.community)`; build `output_path` using `sanitize_path_segment(args.community)` as folder; log which path was taken at INFO

**Checkpoint**: `python -m pytest tests/test_trend_scout.py tests/test_pipeline.py` — all T003–T005 tests pass. Manual run with a free-text description produces a bundle.

---

## Phase 4: User Story 2 — Language and tone inferred from description (Priority: P2)

**Goal**: `--community "Communauté française qui critique Macron"` produces a cartoon in French.

**Independent Test**: Run with a French description; verify `output_language` in the inferred brief is `"French"` and cartoon text is in French.

### Tests for US2

- [ ] T010 [P] [US2] Write parameterised tests for language inference in `tests/test_trend_scout.py`: French description → `output_language="French"`; Portuguese description → `output_language="Portuguese"`; English description with no explicit language signal → `output_language="English"`; ambiguous description → English default applied with WARNING logged

### Implementation for US2

- [ ] T011 [US2] Verify `infer_brief_from_description()` prompt explicitly instructs Gemini to infer the primary language from the community description and return it as `output_language`; update `_INFERENCE_SYSTEM` constant if the language instruction is missing or ambiguous

**Checkpoint**: `python -m pytest tests/test_trend_scout.py -k "language"` — all T010 tests pass.

---

## Phase 5: User Story 3 — Named community backwards compat (Priority: P1)

**Goal**: `python pipeline.py --community uk-politics` behaviour is identical to before this feature.

**Independent Test**: Run with `--community uk-politics`; verify no inference call is made; output is produced using the config entry's audience/language/tone.

### Tests for US3

- [ ] T012 [P] [US3] Write tests in `tests/test_pipeline.py` verifying that when `--community` exactly matches a communities.yaml entry: `get_topics_for_description` is NOT called; `trend_scout.get_topics()` IS called; output folder uses the community name (not sanitized description)
- [ ] T013 [P] [US3] Write tests in `tests/test_trend_scout.py` verifying `get_topics()` (existing function) produces identical output after the `_rank_headlines` refactor from T002 — use same mock inputs as T001 and assert results match

### Implementation for US3

*(No new implementation — the `os.path.exists` check and exact-match-first logic in T009 ensures backwards compat. The tests in T012 and T013 are the deliverable.)*

**Checkpoint**: `python -m pytest tests/test_pipeline.py -k "community"` — all T012 tests pass. Existing communities.yaml entries work without regression.

---

## Phase 6: User Story 4 — Clear error when no headlines found (Priority: P3)

**Goal**: Pipeline exits with a diagnostic message when no headlines are available; no partial or broken bundle is written.

**Independent Test**: Simulate empty headline response; verify exit code 1, error message names the community description, no bundle folder created.

### Tests for US4

- [ ] T014 [P] [US4] Write tests in `tests/test_pipeline.py` for empty `--community ""` argument: pipeline exits code 1 before any API call; error message includes "must not be empty"
- [ ] T015 [P] [US4] Write tests in `tests/test_pipeline.py` for missing `communities.yaml` with free-text description: no crash; free-text inference path taken normally
- [ ] T016 [P] [US4] Write tests in `tests/test_pipeline.py` for `get_topics_for_description()` returning empty headline list: pipeline logs "no topics available for..." and exits code 1; no bundle written

### Implementation for US4

- [ ] T017 [US4] Add empty-string validation to `pipeline.py` immediately after argument parsing (before any file load or API call): if `args.community is not None and not args.community.strip()`, log error "–-community must not be empty" and `sys.exit(1)`
- [ ] T018 [US4] Verify `pipeline.py` free-text branch handles `([], brief, "none")` return from `get_topics_for_description()` the same way the named-community branch handles empty headlines — log error with the community description and `sys.exit(1)`

**Checkpoint**: `python -m pytest tests/test_pipeline.py -k "error or empty"` — all T014–T016 tests pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T019 Update `README.md` usage section to include a free-text community example (`python pipeline.py --community "US community that dislikes Trump"`) alongside the existing named-community example
- [ ] T020 [P] Run `ruff check . && ruff format .` and fix any linting or formatting issues across all modified files
- [ ] T021 Run full test suite `python -m pytest` and verify all tests pass (new tests included)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — skip
- **Foundational (Phase 2)**: No dependencies — start immediately
- **US1 (Phase 3)**: Depends on Phase 2 (T002) — blocks on ranking helper
- **US2 (Phase 4)**: Depends on Phase 3 (T007) — `infer_brief_from_description` must exist
- **US3 (Phase 5)**: Depends on Phase 2 (T002) — ranking refactor must be complete
- **US4 (Phase 6)**: Depends on Phase 3 (T009) — pipeline branch must exist
- **Polish (Phase 7)**: Depends on all story phases

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2 — core feature
- **US3 (P1)**: Starts after Phase 2 — can run in parallel with US1 (different test focus)
- **US2 (P2)**: Starts after US1 (T007 must exist) — language inference extension
- **US4 (P3)**: Starts after US1 (T009 must exist) — error handling layer

### Within Each Phase

- Tests must be written first and FAIL before implementation begins (constitution Principle 9)
- Parallel [P] test tasks within a phase can be written simultaneously
- Implementation tasks follow tests in the same phase

### Parallel Opportunities

- T003, T004, T005 (US1 tests) can be written in parallel
- T006 (constants) can be written in parallel with T003–T005
- T012, T013 (US3 tests) can be written in parallel
- T014, T015, T016 (US4 tests) can be written in parallel
- T019 (README), T020 (ruff) can run in parallel

---

## Parallel Example: US1

```
# Write all US1 tests in parallel (different functions in same test file):
T003: infer_brief_from_description tests
T004: get_topics_for_description tests
T005: pipeline free-text branch tests

# After tests fail → implement in order:
T006: add constants (no dependencies)
T007: implement infer_brief_from_description (depends on T006)
T008: implement get_topics_for_description (depends on T007)
T009: modify pipeline.py (depends on T008)
```

---

## Implementation Strategy

### MVP First (US1 + US3 Only)

1. Complete Phase 2: Foundational (T001–T002) — ranking refactor
2. Complete Phase 3: US1 (T003–T009) — free-text pipeline works end-to-end
3. Complete Phase 5: US3 (T012–T013) — verify no regression in named-community path
4. **STOP and VALIDATE**: manual run with free-text description + existing community name
5. Add US2 (language inference tests), US4 (error handling), Polish

### Incremental Delivery

1. T001–T002: Ranking refactor — foundation
2. T003–T009: Free-text pipeline — MVP
3. T010–T011: Language inference — polish on inference quality
4. T012–T013: Backwards compat — confidence in existing paths
5. T014–T018: Error handling — production robustness
6. T019–T021: Polish + ruff + full test run

---

## Notes

- [P] tasks = different files or no shared incomplete dependencies
- Constitution Principle 9: tests written and failing before implementation
- Each user story checkpoint should be manually verified before moving to next
- No new Python modules needed — all changes in existing files
- `ruff` must pass on all modified files (T020) before the feature is considered complete
