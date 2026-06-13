# Tasks: Multi-Panel Cartoon Format

**Input**: Design documents from `/specs/007-multi-panel-cartoon/`
**Branch**: `008-multi-panel-cartoon`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/cli.md ✅, quickstart.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions. Test tasks appear before their corresponding implementation tasks in every phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths included in every description

---

## Phase 1: Setup

**Purpose**: Confirm branch hygiene before any code is written (RULE 5).

- [x] T001 Confirm active git branch is `008-multi-panel-cartoon`; if on `main`, switch to or create `008-multi-panel-cartoon` before touching any source file

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the new data types (`PanelConcept`, `CartoonLayout`) and extend `CartoonConcept` + `Community` — the shared data model all user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T002 Write failing tests for `PanelConcept`, `CartoonLayout`, and `CartoonConcept.panels` extension in `tests/test_types.py` (create file if absent; tests must fail before T003)
- [x] T003 Add `PanelConcept` (scene, caption, beat) and `CartoonLayout` (panels=1, direction="horizontal") dataclasses to `agents/types.py`; extend `CartoonConcept` with `panels: list[PanelConcept] | None = None`; add `panels: int = 1` and `layout: str = "horizontal"` to `Community`
- [x] T004 Write failing tests for `config_loader.py` reading optional `panels` and `layout` fields from community YAML in `tests/test_config_loader.py` (create file if absent; cover present/absent/default cases; must fail before T005)
- [x] T005 Update `agents/config_loader.py` to read optional `panels` (default 1) and `layout` (default "horizontal") fields from each community entry and populate `Community.panels` and `Community.layout`

**Checkpoint**: `python -m pytest tests/test_types.py tests/test_config_loader.py` passes. `CartoonLayout`, `PanelConcept`, updated `CartoonConcept`, and `Community` are importable.

---

## Phase 3: User Stories 1 & 4 — Horizontal Strip + Single-Panel Backwards Compat (Priority: P1) 🎯 MVP

**Goal**: `python pipeline.py --community uk-politics --panels 3 --layout horizontal` produces a single PNG containing 3 horizontally arranged panels. All existing single-panel invocations continue to work unchanged.

**Independent Test (US1)**: `python pipeline.py --community uk-politics --panels 3 --layout horizontal` completes without error and writes a file whose name begins with `3h_` to the output folder.

**Independent Test (US4)**: `python pipeline.py --community uk-politics` (no panel flags) completes and produces a single-panel PNG with the same filename format as before this feature.

### CLI flag validation (FR-001, FR-002, FR-010, US4 AC2)

- [x] T006 [US1] Write failing tests for `--panels` and `--layout` CLI validation in `tests/test_pipeline.py`: exit 1 on `--panels 0`, `--panels 5`, `--layout diagonal`; `--panels 1` produces single-panel; no flags preserves existing behaviour (must fail before T007)
- [x] T007 [US1] Add `--panels` (int, optional) and `--layout` (str, optional) arguments to `pipeline.py` argparse; add guards immediately after `parser.parse_args()` that exit with code 1 and a descriptive error if `--panels` is outside [1, 4] or `--layout` is not in `["horizontal", "vertical"]` (FR-010)

### Satirist multi-panel prompt and verdict parsing (FR-005, FR-006, FR-011)

- [x] T008 [P] [US1] Write failing tests for multi-panel satirist prompt shape and `<verdict>` JSON parsing in `tests/test_agent_satirist.py`: assert system prompt contains panel count and "JSON" when `layout.panels > 1`; assert `CartoonConcept.panels` is populated from a mocked JSON verdict; assert fallback fires when JSON is malformed or panel count mismatches (must fail before T009)
- [x] T009 [US1] Extend `agent_satirist.run()` signature to accept `layout: CartoonLayout` parameter in `agents/agent_satirist.py`; substitute TASK section with multi-panel instructions (panel count, direction, JSON schema for `<verdict>`) when `layout.panels > 1`; keep single-panel TASK text when `layout.panels == 1` (FR-009)
- [x] T010 [US1] Implement `<verdict>` JSON parsing for multi-panel in `agents/agent_satirist.py`: `json.loads` the verdict content, validate `panels` is a list of exactly `layout.panels` objects each with `scene`, `caption`, `beat`; on success return `CartoonConcept` with `panels` field populated and `image_prompt` set to empty string
- [x] T011 [US1] Implement FR-011 fallback in `agents/agent_satirist.py`: on `json.JSONDecodeError`, missing `panels` key, or panel count mismatch log `WARNING` and fall back to a single-panel `CartoonConcept` (treat verdict content as plain text image prompt)

### Image generator multi-panel prompt assembly (FR-007, US1 AC1)

- [x] T012 [P] [US1] Write failing tests for multi-panel image prompt assembly in `tests/test_agent_image_generator.py`: assert prompt contains positional labels (PANEL 1 LEFT, PANEL 2 CENTER, PANEL 3 RIGHT for horizontal), scene text, caption text, and Gata character description when `CartoonConcept.panels` is non-None; assert single-panel path unchanged when `panels` is None (must fail before T013)
- [x] T013 [US1] Extend `agent_image_generator.generate()` signature to accept `layout: CartoonLayout` parameter in `agents/agent_image_generator.py`
- [x] T014 [US1] Implement multi-panel image prompt assembly in `agents/agent_image_generator.py`: when `concept.panels is not None`, build a single composite prompt string describing the full horizontal comic strip — header line stating panel count and direction, one block per panel with positional label (LEFT/CENTER/RIGHT or LEFT/RIGHT for 2-panel), scene description, caption, then the shared Gata character description and visual style block appended once; pass this prompt to the Gemini image call

### Pipeline wiring and output filename encoding (FR-004, FR-008, FR-009)

- [x] T015 [US1] Write failing tests for `CartoonLayout` construction from CLI + community config precedence and `Nh_` filename prefix in `tests/test_pipeline.py` (must fail before T016 and T017)
- [x] T016 [US1] Wire `CartoonLayout` through `pipeline.py`: after resolving CLI flags and community config, construct `CartoonLayout(panels=effective_panels, direction=effective_layout)`; pass it to `agent_satirist.run(layout=layout)` and `agent_image_generator.generate(layout=layout)` in all pipeline entry points (named community, free-text community, manual mode, unattended daily run)
- [x] T017 [US1] Implement multi-panel filename prefix in `pipeline.py`: when `layout.panels > 1`, prepend `{N}{d}_` (e.g. `3h_`) to the output filename slug (FR-008); single-panel filenames receive no prefix (FR-009)

**Checkpoint**: `python -m pytest tests/test_pipeline.py tests/test_agent_satirist.py tests/test_agent_image_generator.py` passes. US1 and US4 are independently testable end-to-end.

---

## Phase 4: User Story 2 — Vertical Strip (Priority: P2)

**Goal**: `python pipeline.py --community uk-politics --panels 3 --layout vertical` produces a single PNG with 3 vertically stacked panels.

**Independent Test**: Run `python pipeline.py --community uk-politics --panels 2 --layout vertical` and verify the output file name begins with `2v_` and the image prompt contains top-to-bottom panel labels.

- [x] T018 [P] [US2] Write failing tests for vertical layout image prompt structure in `tests/test_agent_image_generator.py`: assert prompt contains TOP/BOTTOM (or TOP/MIDDLE/BOTTOM) positional labels when `layout.direction == "vertical"`, and LEFT/CENTER/RIGHT labels when `"horizontal"` (must fail before T019)
- [x] T019 [US2] Extend multi-panel image prompt assembly in `agents/agent_image_generator.py` to handle `layout.direction == "vertical"`: use TOP / MIDDLE / BOTTOM (or TOP / BOTTOM for 2-panel) positional labels instead of LEFT / CENTER / RIGHT; describe the strip as vertically stacked portrait-orientation panels

**Checkpoint**: `python -m pytest tests/test_agent_image_generator.py` passes for both horizontal and vertical paths.

---

## Phase 5: User Story 3 — Community Config panels/layout (Priority: P2)

**Goal**: Adding `panels: 3` and `layout: horizontal` to a community in `communities.yaml` causes the pipeline to produce a 3-panel strip without any CLI flags. CLI flags still override the community config.

**Independent Test**: Add `panels: 3` and `layout: horizontal` to any community entry in `communities.yaml`, run the pipeline for that community without panel flags, verify a 3-panel strip is produced. Run with `--panels 2` for the same community and verify 2 panels are used (CLI overrides config).

- [x] T020 [P] [US3] Write failing tests for CLI-overrides-community-config precedence in `tests/test_pipeline.py`: mock a community with `panels=3, layout="horizontal"`; assert `--panels 2` CLI flag produces `CartoonLayout(panels=2)`; assert no CLI flag produces `CartoonLayout(panels=3)` (must fail before T021)
- [x] T021 [US3] Implement precedence logic in `pipeline.py`: when `args.panels` is provided use it, else fall back to `community.panels`; when `args.layout` is provided use it, else fall back to `community.layout`; apply to named community, free-text community, and unattended daily run paths
- [x] T022 [US3] Add `panels: 3` and `layout: horizontal` example fields to an existing community entry in `communities.yaml` to demonstrate US3 AC1 (operator can switch community to 3-panel with two lines)

**Checkpoint**: `python -m pytest tests/test_pipeline.py` passes for all precedence scenarios. Running the configured community without flags produces a 3-panel strip.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T023 [P] Run `ruff check . --fix` and `ruff format .` on all modified files; fix any remaining violations so `ruff check .` exits 0
- [x] T024 [P] Update `README.md`: add `--panels` and `--layout` to the CLI usage section and flags table; confirm the agent table still accurately describes all agents (RULE 6, RULE 11)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 + US4 (Phase 3)**: Depends on Phase 2 completion
- **US2 (Phase 4)**: Depends on Phase 3 (T013/T014 must exist to extend them)
- **US3 (Phase 5)**: Depends on Phase 2 (Community.panels/layout) and Phase 3 (T016 pipeline wiring)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Foundational complete → can start (no other story dependency)
- **US4 (P1)**: Verified as part of US1 — no additional story dependency
- **US2 (P2)**: Depends on US1 (T013 must exist before T019 extends it)
- **US3 (P2)**: Depends on Foundational (T003, T005) and US1 T016

### Within Each Phase

- Test tasks MUST be written and verified to FAIL before the corresponding implementation tasks
- `agents/types.py` tasks in Phase 2 are sequential (T003 adds types; T005 depends on T003)
- In Phase 3: T008 and T012 can start in parallel (different test files); T009–T011 and T013–T014 can proceed in parallel after their respective tests pass

---

## Parallel Opportunities

### Phase 2

```
T002 (test_types.py) → T003 (types.py) ─────────────────────────────────┐
                                                                           ↓
T004 (test_config_loader.py) → T005 (config_loader.py)   (after T003)   done
```

### Phase 3

```
T006 → T007 (pipeline.py validation)
T008 (test_agent_satirist.py)  ──→  T009 → T010 → T011 (agent_satirist.py)
T012 (test_agent_image_generator.py) ──→ T013 → T014 (agent_image_generator.py)
T015 → T016 → T017 (pipeline.py wiring)
```
T008 and T012 can start in parallel. T009–T011 and T013–T014 can proceed in parallel.

---

## Implementation Strategy

### MVP First (US1 + US4 — Phase 3 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T005)
3. Complete Phase 3: US1 + US4 (T006–T017)
4. **STOP and VALIDATE**: Run full test suite; invoke pipeline manually with `--panels 3 --layout horizontal` and inspect the output PNG
5. Ship MVP if end-to-end output is correct

### Incremental Delivery

1. Phase 1 + 2 → data model ready
2. Phase 3 → horizontal strip + backwards compat (MVP)
3. Phase 4 → vertical strip
4. Phase 5 → community config
5. Phase 6 → polish

### Summary

| Phase | Tasks | User Story | Notes |
|-------|-------|-----------|-------|
| 1 Setup | T001 | — | Branch hygiene |
| 2 Foundational | T002–T005 | — | Data model |
| 3 P1 MVP | T006–T017 | US1 + US4 | Horizontal strip + compat |
| 4 P2 | T018–T019 | US2 | Vertical strip |
| 5 P2 | T020–T022 | US3 | Community config |
| 6 Polish | T023–T024 | — | ruff + README |
| **Total** | **24 tasks** | | |
