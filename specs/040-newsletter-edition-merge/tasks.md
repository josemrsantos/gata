# Tasks: Newsletter Edition Merge

**Input**: Design documents from `specs/040-newsletter-edition-merge/`
**Branch**: `040-newsletter-edition-merge`
**Prerequisites**: plan.md ✅, spec.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions. Test
tasks appear before their corresponding implementation tasks in every phase.

## Format: `[ID] [P?] [Story?] Description`

---

## Phase 1: Setup

- [x] T001 Confirm active git branch is `040-newsletter-edition-merge` (done —
      created before spec.md was written)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types every user story's tests and implementation depend on.

- [ ] T002 Add `OrderedStory`, `EditionMergeRequest`, `MergeCallResult` dataclasses to
      `core/newsletter_merge.py`

**Checkpoint**: `python -c "from core.newsletter_merge import OrderedStory, EditionMergeRequest, MergeCallResult"`

---

## Phase 3: User Story 2 — Order comes from the folder name, not a guess (Priority: P1)

**Goal**: Discover story sub-folders and order them by mandatory numeric prefix,
failing loudly on anything ambiguous — before any Gemini call exists to guess wrong.

**Independent Test**: spec.md User Story 2's `/tmp/edition` no-prefix fixture.

### Tests for User Story 2 — Write FIRST, Confirm FAILING

- [ ] T003 [P] [US2] Write failing tests in `tests/test_newsletter_merge.py` for
      `discover_and_order_stories()`: numeric-prefix ordering ignoring
      directory-listing/creation order (FR-005), missing-prefix hard error naming the
      folder (FR-004), duplicate-prefix hard error naming both folders (FR-005),
      fewer-than-2-candidates hard error (FR-003), missing
      `<audience>/linkedin_post.md` excluded from candidates (FR-002/FR-006)

> **STOP**: Confirm T003 tests FAIL (`python -m pytest tests/test_newsletter_merge.py -v`)
> before proceeding to T004.

### Implementation for User Story 2

- [ ] T004 [US2] Implement `discover_and_order_stories(edition_dir, audience) ->
      list[OrderedStory]` in `core/newsletter_merge.py`

> **STOP**: Run `python -m pytest tests/test_newsletter_merge.py -v` — confirm all
> T003 tests PASS before proceeding.

**Checkpoint**: `python -c "from pathlib import Path; from core.newsletter_merge import discover_and_order_stories; print(discover_and_order_stories(Path('/tmp/edition'), 'uk'))"`
exits non-zero with a clear message on the no-prefix fixture from T003.

---

## Phase 4: User Story 1 — Merge a numbered set of stories into one document (Priority: P1) MVP

**Goal**: Produce one merged Markdown document from N ordered stories via a single
Gemini call.

**Independent Test**: spec.md User Story 1's 3-story fixture.

### Tests for User Story 1 — Write FIRST, Confirm FAILING

- [ ] T005 [P] [US1] Write failing tests in `tests/test_agent_newsletter_editor.py`
      for the prompt builder: story order stated explicitly, each story's full text
      included, dedup instruction present, no template-shape validation applied to
      input text (FR-008, FR-009)
- [ ] T006 [P] [US1] Write failing tests in `tests/test_agent_newsletter_editor.py`
      for `generate_merged_post()` happy path: one mocked `LLMProvider` returns
      merged text, function returns it unmodified (FR-016 verbatim requirement)
- [ ] T007 [P] [US1] Write failing tests in `tests/test_newsletter_merge.py` for the
      CLI script (`newsletter_merge.py`): writes `<edition>/merged_linkedin_post.md`
      by default, `-o/--output` override, `--audience` override

> **STOP**: Confirm T005–T007 tests FAIL before proceeding to T008–T010.

### Implementation for User Story 1

- [ ] T008 [US1] Implement the merge prompt builder in
      `agents/agent_newsletter_editor.py`
- [ ] T009 [US1] Implement `generate_merged_post(providers, ordered_stories,
      estimated_total_cost) -> tuple[str, TokenUsage]` in
      `agents/agent_newsletter_editor.py` (single-provider call for now; fallback
      chain traversal completed in Phase 5)
- [ ] T010 [US1] Implement `newsletter_merge.py` CLI entry point: argparse
      (`edition_folder`, `--audience`, `-o/--output`), calls
      `core.newsletter_merge.merge_edition()`, writes output file

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests PASS before
> proceeding.

**Checkpoint**: spec.md User Story 1's independent test, run against a mocked
provider fixture.

---

## Phase 5: User Story 4 — Cost is tracked and calls degrade cheapest-first (Priority: P1)

**Goal**: Sum stored image-generation cost, estimate this call's cost, order the
fallback chain cheapest-first, log every attempt.

**Independent Test**: `python -m pytest tests/test_newsletter_merge.py -k cost_fallback -v`

### Tests for User Story 4 — Write FIRST, Confirm FAILING

- [ ] T011 [P] [US4] Write failing tests in `tests/test_newsletter_merge.py` for
      `sum_image_generator_cost()` against a fixture `telemetry.json` with multiple
      `"Image Generator"` iterations (FR-010a), and for the hard error on
      missing/unreadable/entry-less `telemetry.json` (FR-012)
- [ ] T012 [P] [US4] Write failing tests in `tests/test_newsletter_merge.py` for
      `estimate_merge_call_cost()`: uses the selected model's rate and `max_tokens`
      ceiling as a conservative upper bound (FR-010b)
- [ ] T013 [P] [US4] Write failing tests in `tests/test_newsletter_merge.py` for
      `build_fallback_chain()`: all active Gemini text models ordered ascending by
      combined per-million-token rate, followed by Claude/Grok models ordered the
      same way (FR-013)
- [ ] T014 [P] [US4] Write failing tests in `tests/test_agent_newsletter_editor.py`
      for fallback-on-failure: first two providers raise, third succeeds; asserts the
      third provider is called and both failures are logged (FR-014); asserts total
      exhaustion (all providers fail) raises / signals a hard error with no partial
      output (FR-015)
- [ ] T015 [P] [US4] Write failing tests in `tests/test_agent_newsletter_editor.py`
      asserting the prompt includes the FR-010 estimated total cost and the FR-011
      fixed human-time disclaimer sentence

> **STOP**: Confirm T011–T015 tests FAIL before proceeding to T016–T019.

### Implementation for User Story 4

- [ ] T016 [US4] Implement `sum_image_generator_cost()` in `core/newsletter_merge.py`
- [ ] T017 [US4] Implement `estimate_merge_call_cost()` in `core/newsletter_merge.py`
- [ ] T018 [US4] Implement `build_fallback_chain()` in `core/newsletter_merge.py`,
      importing `_COST_PER_M` from `llm/gemini.py`, `llm/claude.py`, `llm/grok.py`
- [ ] T019 [US4] Extend `generate_merged_post()` in
      `agents/agent_newsletter_editor.py` to iterate the full fallback chain
      (try/except per provider, mirroring `agents/agent_linkedin_post.py`), logging
      each attempt via `logging`, and wire FR-010/011 cost values into the prompt
      built in T008; wire `core.newsletter_merge.merge_edition()` to call
      `sum_image_generator_cost()` + `estimate_merge_call_cost()` +
      `build_fallback_chain()` before invoking the agent

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests PASS before
> proceeding.

**Checkpoint**: SC-003 and SC-004 from spec.md.

---

## Phase 6: User Story 3 — Merge quality is Gemini's job, correctness is the human reviewer's job (Priority: P2)

**Goal**: Confirm, explicitly, the absence of template-shape validation and the
absence of any auto-publish implication.

- [ ] T020 [P] [US3] Write and pass a test in `tests/test_newsletter_merge.py`
      confirming a `linkedin_post.md` with arbitrary/non-template content is still
      accepted as a valid candidate (no parse-shape rejection) (FR-008)
- [ ] T021 [P] [US3] Write and pass a test confirming no CLI flag or code path in
      `newsletter_merge.py` posts or transmits the output anywhere (FR-018)

**Checkpoint**: `python -m pytest tests/ -v` all green.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T022 [P] Run `ruff check . --fix` and `ruff format .` on all new/modified
      files; confirm `ruff check .` exits 0
- [ ] T023 [P] Add a "Newsletter Editor" row to README.md's agent table (RULE 11 —
      hard requirement, this is a new agent)
- [ ] T024 Note outstanding pre-merge gates for a future PR (not done in this pass,
      since no PR is being opened yet): CHANGELOG.md entry, docs/architecture.md
      update, `pyproject.toml` / `core/__version__.py` version bump (RULE 15, RULE 17)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: done
- **Foundational (Phase 2)**: blocks Phases 3–6
- **US2 (Phase 3)**: depends on Phase 2 — blocks Phase 4 (US1 needs ordered stories)
- **US1 (Phase 4)**: depends on Phase 3
- **US4 (Phase 5)**: depends on Phase 4 (extends the single-call path built there into
  a fallback chain)
- **US3 (Phase 6)**: depends on Phase 4 (nothing new to build, only to verify)
- **Polish (Phase 7)**: depends on all of the above

### Within Each Phase

Test tasks (T003, T005–T007, T011–T015, T020–T021) MUST be written and confirmed
FAILING (or, for T020–T021, written against the finished behaviour and confirmed
PASSING) before their paired implementation tasks proceed.

---

## Parallel Opportunities

T005, T006, T007 (different test concerns, same two files but non-overlapping test
functions) can be drafted together. T011–T015 similarly. T022 and T023 are
independent of each other.

---

## Summary

| Phase | Tasks | Story | Notes |
|-------|-------|-------|-------|
| 1 Setup | T001 | — | Branch hygiene (done) |
| 2 Foundational | T002 | — | Shared dataclasses |
| 3 US2 | T003–T004 | US2 | Discovery + numeric-prefix ordering |
| 4 US1 MVP | T005–T010 | US1 | Single-call merge, prompt, CLI |
| 5 US4 | T011–T019 | US4 | Cost summation, estimate, fallback chain, logging |
| 6 US3 | T020–T021 | US3 | Verify no template validation, no auto-publish |
| 7 Polish | T022–T024 | — | ruff, README, deferred pre-merge gates |
| **Total** | **24 tasks** | | |
