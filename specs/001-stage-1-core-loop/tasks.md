# Tasks: Stage 1 Core Loop

**Input**: Design documents from `specs/001-stage-1-core-loop/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**Tests**: Included — Constitution Principle 9 mandates test-first with no exceptions. Tests MUST be written and
confirmed FAILING before any implementation task in the same phase begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no blocking dependency)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization — directory structure, dependencies, security config.

- [x] T001 Create project directory structure: `agents/`, `output/`, `tests/` at repo root
- [x] T002 [P] Create `pyproject.toml` with project metadata, dependencies (`anthropic`, `google-genai`, `python-dotenv`) and dev dependencies (`pytest`, `ruff`); set `requires-python = ">=3.10"`; add `[tool.ruff]` section with `line-length = 88`, `target-version = "py310"`, `select = ["E", "F", "I"]`
- [x] T003 [P] Update `.gitignore` — add `output/`, `.env`, `__pycache__/`, `*.pyc`, `.venv/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared data types that every module and test depends on. MUST be complete before any user story work
begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Create `agents/types.py` — define `StrategyBrief`, `CartoonConcept`, and `Critique` dataclasses exactly as
  specified in `specs/001-stage-1-core-loop/data-model.md`

**Checkpoint**: Shared types available — user story implementation can begin.

---

## Phase 3: User Story 1 — End-to-End Pipeline Run (Priority: P1) 🎯 MVP

**Goal**: A single pipeline run with hardcoded topic + strategy brief produces `output/cartoon_output.png` without any
manual intervention.

**Independent Test**: Run `python pipeline.py`; verify `output/cartoon_output.png` exists and is a valid PNG image.

### Tests for User Story 1 ⚠️ Constitution-Mandated: Write FIRST, Confirm FAILING Before T009

- [x] T006 [P] [US1] Write `tests/test_agent_bc.py`: (a) XML tag present → `image_prompt` extracted correctly via
  regex; (b) XML tag missing → retry triggered, not silently skipped; (c) blank `StrategyBrief` field → `ValueError`
  raised before any API call; (d) Critic response containing `"APPROVED"` → `Critique.approved is True`; Critic response
  containing `"NEEDS REVISION"` → `Critique.approved is False`; (e) all 3 XML retries exhausted →
  `RuntimeError` raised and pipeline exits with code 1, no `output/cartoon_output.png` written
- [x] T007 [P] [US1] Write `tests/test_agent_d.py`: (a) `inline_data` present → binary data written to temp file then
  renamed to `output/cartoon_output.png`; (b) `inline_data` absent → `RuntimeError` raised, no partial file written to
  disk
- [x] T008 [P] [US1] Write `tests/test_pipeline.py`: full pipeline run with all SDK calls mocked (Anthropic + Gemini) →
  `output/cartoon_output.png` produced; mock returns valid `CartoonConcept` with non-empty `image_prompt`

> **STOP**: Confirm T006–T008 tests all FAIL before proceeding to T009.

### Implementation for User Story 1

- [x] T009 [US1] Implement `agents/agent_bc.py`: `_call_satirist(topic, brief, previous_critique=None)` — Anthropic
  client, model `claude-sonnet-4-6`, `temperature=0.8`; system prompt includes Gata's full character description
  sourced verbatim from constitution.md Section 4 (never paraphrase), visual style rules per constitution.md Section 5,
  strategy brief fields, and instruction to
  wrap the image prompt in `<image_prompt>…</image_prompt>` XML tags
- [x] T010 [US1] Implement `_extract_image_prompt(text)` in `agents/agent_bc.py` —
  `re.search(r'<image_prompt>(.*?)</image_prompt>', text, re.DOTALL)`; if no match, raise `ValueError` to trigger caller
  retry; add retry wrapper calling `_call_satirist` up to 3 times before raising `RuntimeError`; the retry does NOT
  increment the iteration counter — it is a technical recovery mechanism invisible to the loop logic; the iteration
  counter advances only after a valid `CartoonConcept` has been produced and evaluated by the Critic; when all 3
  retries are exhausted, raise `RuntimeError` — `pipeline.py` catches this, prints a clear error message, and exits
  with code 1; no partial output is written; fallback to last malformed response is deferred to Stage 4
- [x] T011 [P] [US1] Implement `agents/agent_d.py`: `generate(concept, brief)` — Gemini client (
  `from google import genai`), model `gemini-3.1-flash-image-preview`; extract binary from
  `response.candidates[0].content.parts` checking `part.inline_data`; raise
  `RuntimeError("Image generation produced no binary data")` if no `inline_data` part found
- [x] T012 [US1] Implement atomic file write in `agents/agent_d.py`: write binary to `tempfile.NamedTemporaryFile` in
  `output/`, then `os.replace(tmp_path, "output/cartoon_output.png")`; return absolute path; never leave a partial file
  if an exception occurs
- [x] T013 [US1] Implement `_call_critic(concept, brief)` in `agents/agent_bc.py` — Gemini client, model
  `gemini-2.0-flash`, `temperature=0.2` via `GenerateContentConfig`; prompt instructs Critic to return structured
  feedback and an explicit approval verdict (`APPROVED` / `NEEDS REVISION`); parse response into `Critique` dataclass
  with `approved: bool` and `language_check_passed: bool`
- [x] T014 [US1] Implement `agents/agent_bc.run(topic, brief)` — single-iteration skeleton: call `_call_satirist` →
  `_extract_image_prompt` (with retry) → call `_call_critic` → return `CartoonConcept`; this is the foundation the loop
  logic will be layered onto in Phase 4
- [x] T015 [US1] Implement `pipeline.py` entry point: load `.env` via `python-dotenv`; validate `ANTHROPIC_API_KEY` and
  `GEMINI_API_KEY` present (exit 1 if missing); define hardcoded `TOPIC: str` and `BRIEF: StrategyBrief`; validate all
  three `BRIEF` fields are non-empty (raise `ValueError` identifying the blank field); call
  `os.makedirs("output", exist_ok=True)`; call `agent_bc.run(TOPIC, BRIEF)` → call `agent_d.generate(concept, BRIEF)` →
  print output path; exit 0 on success, exit 1 with error message on any exception

> **STOP**: Run `pytest tests/ -v` — confirm all tests written in this phase now PASS before proceeding to the next phase.

**Checkpoint**: `python pipeline.py` runs end-to-end with real API keys and saves `output/cartoon_output.png`.

---

## Phase 4: User Story 2 — Iterative Creative Refinement (Priority: P2)

**Goal**: The B/C loop iterates up to 5 times; exits early on Critic approval; applies the Final Say Protocol at
iteration 5; verifies language compliance on every iteration.

**Independent Test**: Observe pipeline stdout logs showing multiple iteration numbers and critique feedback before image
generation begins. Confirm loop does not exceed 5 iterations.

### Tests for User Story 2 ⚠️ Constitution-Mandated: Write FIRST, Confirm FAILING Before T021

- [x] T016 [P] [US2] Add to `tests/test_agent_bc.py`: Critic returns `approved=True` on iteration 2 → `agent_bc.run()`
  exits loop and returns that concept without reaching iteration 3, 4, or 5 (mock returns approved on second call)
- [x] T017 [P] [US2] Add to `tests/test_agent_bc.py`: Critic never returns `approved=True` → loop runs exactly 5
  iterations and returns the last `CartoonConcept` without raising an exception
- [x] T018 [P] [US2] Add to `tests/test_agent_bc.py`: at iteration 5, the Satirist system/user prompt contains all three
  Final Say Protocol elements — Gemini's objection summary, override rationale, and synthesis instruction (assert prompt
  string contains the required sections)
- [x] T019 [P] [US2] Add to `tests/test_agent_bc.py`: Critic receives a concept with English text when `output_language`
  is not `"English"` → `Critique.language_check_passed` is `False` and `Critique.approved` is `False`
- [x] T020 [US2] Add to `tests/test_agent_bc.py`: Critic response does not reference the previous iteration's concept →
  loop requests a new critique rather than accepting the generic feedback (assert `_call_critic` is called a second time
  for the same iteration)

> **STOP**: Confirm T016–T020 tests all FAIL before proceeding to T021.

### Implementation for User Story 2

- [x] T021 [US2] Add iteration counter and loop to `agents/agent_bc.run()` — replace single-iteration skeleton (T014)
  with `for iteration in range(1, 6)` loop; pass `iteration` into each `CartoonConcept`; pass previous
  `Critique.feedback` into each `_call_satirist` call when `iteration > 1`
- [x] T022 [US2] Add early-exit on Critic approval to loop in `agents/agent_bc.py` — after each `_call_critic` call, if
  `critique.approved is True`, break immediately and return current concept
- [x] T023 [US2] Add Final Say Protocol prompt construction at iteration 5 in `agents/agent_bc.py` — when
  `iteration == 5`, build a dedicated prompt section instructing the Satirist to: (a) summarise Gemini's last objection
  in one sentence, (b) state in one sentence why the satirical payoff justifies overruling it, (c) produce a synthesis
  visibly incorporating all accumulated feedback — not a copy of iteration 1; log a warning if the final `image_prompt`
  is substantially identical to the first iteration's `image_prompt` (simple string similarity check), but always
  proceed
- [x] T024 [US2] Add language leakage check to `_call_critic` in `agents/agent_bc.py` — if `brief.output_language` is
  not `"English"`, Critic prompt explicitly instructs Gemini to check for English text in the image prompt; parse
  presence of English leakage into `Critique.language_check_passed`; if `language_check_passed is False`, force
  `approved = False` regardless of other feedback
- [x] T025 [US2] Add measurable-progress validation in `agents/agent_bc.py` — after receiving Critic response on
  iterations > 1, check that the feedback references a specific change from the previous concept (heuristic: feedback
  must not be identical or near-identical to previous feedback); if invalid, call `_call_critic` again once with a
  prompt noting the generic response; accept the second response regardless

> **STOP**: Run `pytest tests/ -v` — confirm all tests written in this phase now PASS before proceeding to the next phase.

**Checkpoint**: Pipeline stdout shows iteration counts; loop exits early on approval or at iteration 5 with Final Say
Protocol; language leakage blocks approval.

---

## Phase 5: User Story 3 — Predictable Output Location (Priority: P3)

**Goal**: `output/cartoon_output.png` is always written to a consistent location and safely overwritten on each run;
generation failure leaves the previous file intact.

**Independent Test**: Run `python pipeline.py` twice consecutively; confirm `output/cartoon_output.png` is replaced (not
duplicated); confirm timestamp changes between runs.

### Tests for User Story 3 ⚠️ Constitution-Mandated: Write FIRST, Confirm FAILING Before T028

- [x] T026 [P] [US3] Add to `tests/test_pipeline.py`: run pipeline twice with mocks; confirm `output/cartoon_output.png`
  is overwritten (not accumulated) — assert file modification time is updated
- [x] T027 [P] [US3] Add to `tests/test_pipeline.py`: `output/` directory does not exist at pipeline start; assert
  pipeline creates it and completes successfully rather than raising a `FileNotFoundError`
- [x] T027b [US3] Add to `tests/test_agent_d.py`: `generate()` raises `RuntimeError` mid-write → existing
  `output/cartoon_output.png` is left intact (assert pre-existing file content is unchanged after the failed call)

> **STOP**: Confirm T026–T027b tests FAIL before proceeding to T028.

### Implementation for User Story 3

- [x] T028 [US3] Verify `pipeline.py` calls `os.makedirs("output", exist_ok=True)` before any agent call — if already
  present from T015, confirm it is correctly placed before `agent_d.generate()`
- [x] T029 [US3] Verify `agents/agent_d.py` atomic write preserves existing file on failure — confirmed by test written
  in T027b

> **STOP**: Run `pytest tests/ -v` — confirm all tests written in this phase now PASS before proceeding to the next phase.

**Checkpoint**: All three user stories are independently functional and testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Observability, final validation, and suite hygiene.

- [x] T030 [P] Add structured stdout progress logging throughout `pipeline.py` and `agents/agent_bc.py` — log: pipeline
  start with topic/brief summary, each iteration number and approval status, Final Say Protocol trigger at iteration 5,
  image write confirmation with output path
- [x] T031 Anthropic API failure: fail fast with a clear error
  Tests first (write and confirm FAILING before implementation):
  - Anthropic API raises any exception → pipeline exits immediately with code 1
  - Error message must include: the module name, the model string (`claude-sonnet-4-6`), and the original exception message
  - No partial output is written on failure
  - Exit is clean — no stack trace shown to the user

  Implementation:
  - In `agent_bc.py`, wrap all Anthropic client calls in a try/except block catching `anthropic.APIError` and
    `anthropic.APIConnectionError`
  - On any exception, log at ERROR level: `'Claude API unavailable (claude-sonnet-4-6): {exception message}'`
  - Re-raise as `RuntimeError` so `pipeline.py` catches it and exits with code 1
  - No retry logic — fail fast is the correct behaviour for Stage 1

  Stage 4 upgrade: this fail-fast behaviour will be replaced with a retry decorator (see open questions in
  `gata_newsroom_blueprint.md`)
- [x] T032 Run `ruff check .` and `ruff format .` on all source files — confirm zero violations before end-to-end validation
- [x] T033 Run `pytest tests/ -v` — confirm all tests pass with mocked SDK calls; no real API calls occur during test
  run
- [x] T034 End-to-end validation per `specs/001-stage-1-core-loop/quickstart.md` — run `python pipeline.py` with real
  `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`; verify `output/cartoon_output.png` is a valid, viewable PNG; test at least 3
  different hardcoded topic/brief combinations

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T002 and T003 can run in parallel
- **Foundational (Phase 2)**: Requires Phase 1 completion; T004 is the only task
- **User Story 1 (Phase 3)**: Requires Phase 2; tests T006–T008 are parallel; implementation is sequential per task
  order
- **User Story 2 (Phase 4)**: Requires Phase 3 checkpoint (working single-iteration loop); tests T016–T019 are parallel;
  T020 is sequential
- **User Story 3 (Phase 5)**: Requires Phase 3 checkpoint (agent_d.py atomic write in place); tests T026–T027 are
  parallel
- **Polish (Phase 6)**: Requires all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2; no dependency on US2 or US3
- **US2 (P2)**: Depends on US1 Phase 3 checkpoint — extends `agent_bc.py`
- **US3 (P3)**: Depends on US1 Phase 3 checkpoint — extends `agent_d.py` and `pipeline.py`; can proceed in parallel with
  US2

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Constitution Principle 9)
- `agents/types.py` (T004) before any agent implementation
- Satirist helper (T009) before XML extractor (T010) before Critic helper (T013) before `run()` (T014) before
  `pipeline.py` (T015)
- `agent_d.py` image call (T011) before atomic write (T012); both can proceed in parallel with T009–T013

---

## Parallel Opportunities

### Phase 1

```
T002 (pyproject.toml)    ──┐
T003 (.gitignore)          ├── Parallel after T001
```

### Phase 3 — Tests

```
T006 (test_agent_bc.py)  ──┐
T007 (test_agent_d.py)     ├── All parallel (different files)
T008 (test_pipeline.py)  ──┘
```

### Phase 3 — Implementation

```
T009 → T010 → T013 → T014 → T015   (agent_bc.py chain, sequential)
T011 → T012                         (agent_d.py chain, parallel with T009–T013)
```

### Phase 4 — Tests

```
T016 ──┐
T017   │
T018   ├── Parallel (independent test functions in test_agent_bc.py)
T019 ──┘
T020     (sequential — depends on mock call-count behaviour)
```

### Phase 5 — Tests

```
T026 (overwrite test) ──┬── Parallel (different test functions)
T027 (mkdir test)     ──┘
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Write tests T006–T008, confirm FAILING
4. Complete Phase 3 implementation (T009–T015)
5. **STOP and VALIDATE**: `python pipeline.py` produces `output/cartoon_output.png`
6. Run `pytest tests/ -v` — all mocked tests pass

### Incremental Delivery

1. MVP: Phases 1–3 → working single-iteration pipeline
2. Add US2 (Phase 4) → full 5-iteration loop with Final Say Protocol and language check
3. Add US3 (Phase 5) → output durability and idempotency
4. Polish (Phase 6) → observability and end-to-end validation

---

## Notes

- `[P]` tasks operate on different files with no blocking dependency between them
- `[Story]` label maps each task to its user story for traceability
- Each user story phase is independently completable and testable
- Constitution §3 (XML contract) and §2 (image binary extraction) each require explicit unit tests — covered by T006 and
  T007 respectively
- Never commit `.env` or `output/` — both are in `.gitignore` (T003)
- Use `os.replace()` not `shutil.move()` for atomic rename (POSIX-atomic on same filesystem)
