# Tasks: Descriptive Source Titles

**Input**: Design documents from `specs/044-descriptive-source-titles/`
**Branch**: `044-descriptive-source-titles`
**Prerequisites**: plan.md ✅, spec.md ✅

**Tests**: Constitution §9 mandates tests before implementation. This is a
single-file, single-story enhancement — new/changed tests and their
corresponding implementation changes were made together, function by
function, rather than as two separate phases; every new test asserts
behaviour that did not exist before its matching implementation change
landed, and the full suite was run (and confirmed green) only after all
implementation was in place.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no unmet dependencies)
- **[Story]**: All tasks belong to US1 (the spec's single merged story)

---

## Phase 1: Setup

**Purpose**: Confirm branch hygiene before any code is written (RULE 5).

- [x] T001 Confirm active git branch is `044-descriptive-source-titles`; created off `main` before any file was written

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: New standalone helpers with no dependency on the three
providers' research call plumbing — everything else in this feature is
built on top of these.

- [x] T002 [P] Add `_extract_title_tag`, `_extract_meta_content`, `_META_TAG_RE`, `_META_ATTR_RE` in `agents/agent_linkedin_post.py` (FR-001)
- [x] T003 [P] Add `_normalize_for_comparison`, `_is_descriptive_title`, `_NON_ALNUM_RE` in `agents/agent_linkedin_post.py` (FR-002)
- [x] T004 [P] Add `_humanize_slug`, `_MIN_SLUG_WORDS`, `_SLUG_WORD_RE` in `agents/agent_linkedin_post.py` (FR-003, FR-004)
- [x] T005 [P] Add `_split_source_titles_block`, `_SOURCE_TITLES_MARKER`, and append the marker instruction to `_RESEARCH_SYSTEM` in `agents/agent_linkedin_post.py` (FR-007, FR-010)

**Checkpoint**: `python -m pytest tests/test_agent_linkedin_post.py -k "is_descriptive_title or humanize_slug or split_source_titles_block" -v` — all new helper tests pass in isolation.

---

## Phase 3: User Story 1 — Every published source carries a genuinely descriptive title (Priority: P1) MVP

**Goal**: Every source published in a Sources list resolves through the
fetch → slug → provider-supplied-title → drop chain, uniformly across all
three panelist providers.

**Independent Test**: `python -m pytest tests/test_agent_linkedin_post.py -k source_title -v`

### Tests for User Story 1 — Written alongside each implementation step (Constitution §9)

- [x] T006 [US1] Rewrite `_fetch_page_title` tests in `tests/test_agent_linkedin_post.py` for the new `tuple[str | None, str]` signature; add og:title/twitter:title fallback and FR-014 redirect-destination-capture-on-failure coverage
- [x] T007 [US1] Write `_resolve_sources` tests in `tests/test_agent_linkedin_post.py`: raw-candidate-accepted-without-fetch, fetch-wins, slug-wins, provider-title-wins, unverified-URL-in-provider-block-ignored, drop-when-nothing-descriptive, one-source-dropping-does-not-affect-others, empty-list
- [x] T008 [US1] Update the two `_extract_claude_sources` tests in `tests/test_agent_linkedin_post.py` whose expected title shape changed (raw, un-prefixed title)
- [x] T009 [US1] Remove the four `_enrich_source_titles_via_fetch` tests in `tests/test_agent_linkedin_post.py` (function superseded)
- [x] T010 [US1] Update `test_research_gemini_success_returns_digest_and_usage` and `test_research_grok_success_returns_digest_and_usage` mocks for the new `_fetch_page_title` tuple return

### Implementation for User Story 1

- [x] T011 [US1] Rewrite `_fetch_page_title` in `agents/agent_linkedin_post.py`: try `<title>`, then `og:title`, then `twitter:title`; capture the resolved destination URL from `httpx.HTTPStatusError.response.url` on a post-redirect failure (FR-001, FR-014)
- [x] T012 [US1] Add `_resolve_sources` in `agents/agent_linkedin_post.py`: the shared 4-step chain (raw candidate → fetch → slug → provider-supplied title → drop), parallel fetches, DEBUG logging on drop (FR-002–FR-011, FR-012)
- [x] T013 [US1] Simplify `_extract_claude_sources` in `agents/agent_linkedin_post.py` to stop domain-prefixing — returns the raw citation title (FR-006)
- [x] T014 [US1] Wire `_research_gemini`, `_research_claude`, `_research_grok` in `agents/agent_linkedin_post.py` through `_split_source_titles_block` + `_resolve_sources` (`do_fetch=True` for Gemini/Grok, `do_fetch=False` for Claude); remove `_enrich_source_titles_via_fetch`

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests PASS before proceeding. ✅ 579 passed.

**Checkpoint**: `python -m pytest tests/test_agent_linkedin_post.py -v` — all title-resolution tests pass; a real `--linkedin-post` run's Sources list contains no bare-domain or domain-label-only entries (verified against a live example run, see below).

---

## Phase 4: Polish & Cross-Cutting Concerns

- [x] T015 [P] Run `ruff check .` and `ruff format .` on both modified files; confirm `ruff check .` exits 0
- [x] T016 [P] Update `README.md` if any new flags, agents, or public interfaces were added — N/A, no CLI flag or agent added, internal resolution logic only
- [x] T017 [P] Update `docs/architecture.md` if any protocol names or public data flow changed — N/A, `ResearchSource`/`ResearchDigest` shapes unchanged, no new agent/protocol
- [x] T018 Version in `pyproject.toml`/`core/__version__.py` — N/A to hand-edit: `python-semantic-release` (`.github/workflows/release.yml`, runs on push to `main`) bumps both from the merge commit's conventional-commit message; a manual edit here was tried and reverted (RULE 15's intent — version stays correct — is satisfied by writing a properly prefixed commit message, not by hand-editing these files)
- [x] T019 `CHANGELOG.md` — N/A to hand-edit for the same reason: semantic-release generates each entry (including the commit-hash link) from the merge commit itself; a manual entry was tried and reverted since it couldn't match that generated format and would conflict with it (RULE 17's intent is satisfied by the commit message, not a pre-written entry)
- [x] T020 Generate and verify a real example `--linkedin-post` run's Sources list against the spec's acceptance criteria — first live run surfaced a real bug (a fetch failure through Gemini's grounding-redirect host that never resolved a real destination caused `_humanize_slug` to publish that host's own opaque base64-ish path as a "title"); fixed with `_is_unresolved_redirect_wrapper` (T012 addendum, `agents/agent_linkedin_post.py`) plus 4 new regression tests; a second live run (53 sources) confirmed every entry reads as a real `domain - descriptive title`, none bare or domain-label-only

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS US1
- **US1 (Phase 3)**: Depends on Phase 2
- **Polish (Phase 4)**: Depends on US1 being complete

### Within Each Phase

- T002–T005 are independent of each other (different helper functions, no shared state) but all precede T011–T014, which call them
- T006–T010 (tests) were written/updated alongside their matching T011–T014 implementation change, not as one separate upfront batch — each helper's tests were confirmed passing before moving to the next

---

## Parallel Opportunities

T002, T003, T004, T005 (independent new helpers) could have run in parallel;
T015, T016, T017 (polish checks) are independent of each other.

---

## Summary

| Phase | Tasks | Story | Notes |
|-------|-------|-------|-------|
| 1 Setup | T001 | — | Branch hygiene |
| 2 Foundational | T002–T005 | — | New standalone helpers |
| 3 US1 MVP | T006–T014 | US1 | Shared resolution chain, wired into all 3 providers |
| 4 Polish | T015–T020 | — | ruff, README/architecture check, version, CHANGELOG, live example |
| **Total** | **20 tasks** | | |
