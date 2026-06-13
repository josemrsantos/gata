# Tasks: Trend Scout

**Input**: Design documents from `/specs/005-trend-scout/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story. Tests are written first per Constitution Principle 9.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 1: Setup

**Purpose**: Add new dependency and create the source adapter package skeleton.

- [x] T001 Add `httpx` to `[project] dependencies` in `pyproject.toml` and run `pip install httpx`
- [x] T002 Create empty `agents/sources/__init__.py` to make `sources` a Python package

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types and abstract interface that all user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Add `Headline` dataclass to `agents/types.py` (fields: `title: str`, `abstract: str`, `source: str`, `published_at: str`, `social_score: float`)
- [x] T004 Add `NewsSource` dataclass to `agents/types.py` (fields: `location_uri: str`, `count: int = 10`)
- [x] T005 Extend `Community` dataclass in `agents/types.py` with `news_sources: list[NewsSource] = field(default_factory=list)`
- [x] T006 Update `config_loader.py` to parse the optional `news_sources` list from `communities.yaml` into `Community.news_sources`
- [x] T007 Create `agents/sources/base.py` with abstract `SourceAdapter(ABC)` class and `fetch(community: Community) -> list[Headline]` abstract method

**Checkpoint**: Shared types and adapter interface are in place — user story phases can now begin.

---

## Phase 3: User Story 1 — Automated Topic Discovery (Priority: P1) 🎯 MVP

**Goal**: Pipeline fetches today's top headlines from NewsAPI.ai, Gemini ranks them by
satirical potential for the community, and the top topic is passed downstream.

**Independent Test**: Add `news_sources` to `uk-tech-engineers` in `communities.yaml`, run
`python -m agents.trend_scout --community uk-tech-engineers`, confirm 3 real news topics
are printed (requires a valid `NEWSAPI_AI_KEY` in `.env`).

### Tests for User Story 1 (write first — must FAIL before implementation)

- [x] T008 [P] [US1] Write unit tests for `NewsApiAdapter.fetch()` in `tests/test_sources_newsapi.py`: mock `httpx.post` to return a sample EventRegistry response and assert the adapter returns a correctly populated `list[Headline]`; test HTTP error returns `[]` without raising
- [x] T009 [P] [US1] Write unit tests for `get_topics()` in `tests/test_trend_scout.py`: mock `NewsApiAdapter.fetch` to return a fixed headline list and mock the Gemini SDK call to return a ranked JSON array; assert `get_topics()` returns the expected list of strings

### Implementation for User Story 1

- [x] T010 [US1] Implement `agents/sources/newsapi.py`: `NewsApiAdapter(SourceAdapter)` that calls the EventRegistry API (`POST https://eventregistry.org/api/v1/event/getEvents`) sorted by `socialScore`, loads `NEWSAPI_AI_KEY` from env, and returns `list[Headline]`; returns `[]` and logs WARNING on any `httpx` or HTTP error
- [x] T011 [US1] Implement `agents/trend_scout.py`: `get_topics(community: Community, n: int = 3) -> list[str]` that instantiates `NewsApiAdapter`, calls `fetch()`, passes the headline list to `gemini-2.5-flash` with a community-aware ranking prompt, parses the returned JSON array, and returns the top-N title strings
- [x] T012 [US1] Add `news_sources` block to `uk-tech-engineers` in `communities.yaml` (`location_uri: "http://en.wikipedia.org/wiki/United_Kingdom"`, `count: 10`)

**Checkpoint**: `python -m agents.trend_scout --community uk-tech-engineers` prints ranked topics. US1 is independently testable.

---

## Phase 4: User Story 2 — Graceful Fallback to Seed Topics (Priority: P2)

**Goal**: When `get_topics()` returns nothing (network error, empty feed, missing
`news_sources`), the pipeline silently uses the seed `topics` list with no crash.

**Independent Test**: Point `uk-tech-engineers` at a deliberately broken URL, run
`python pipeline.py --community uk-tech-engineers`, confirm a cartoon is generated from the
seed topic list and a WARNING is logged.

### Tests for User Story 2 (write first — must FAIL before implementation)

- [x] T013 [US2] Add fallback tests to `tests/test_trend_scout.py`: mock `NewsApiAdapter.fetch` to raise `httpx.RequestError`; assert `get_topics()` returns the community's `topics` seed list; add separate test for empty `news_sources` list returning seed topics; add test for no seed topics AND empty fetch returning `[]`

### Implementation for User Story 2

- [x] T014 [US2] Add fallback logic in `agents/trend_scout.py`: if `community.news_sources` is empty or `fetch()` returns `[]` or Gemini ranking fails, fall back to `community.topics`; log `WARNING` with the reason and log `INFO` when topics come from Trend Scout vs fallback
- [x] T015 [US2] Add `news_sources` to the remaining four communities in `communities.yaml` (`portuguese-adults`, `us-startup-crowd`, `uk-politics`, `portuguese-politics`) using appropriate Wikipedia location URIs

**Checkpoint**: Broken or missing `news_sources` gracefully falls back to seed topics. US2 is independently testable.

---

## Phase 5: User Story 3 — Manual Topic Override (Priority: P1)

**Goal**: `--topic` flag bypasses Trend Scout entirely. RULE 12 is preserved.

**Independent Test**: Run `python pipeline.py --topic "test topic" --audience "engineers" --language English --tone "dry"`, confirm Trend Scout is never called (no NewsAPI.ai or Gemini ranking call in logs).

### Tests for User Story 3 (write first — must FAIL before implementation)

- [x] T016 [US3] Add test to `tests/test_pipeline.py`: patch `trend_scout.get_topics` and confirm it is NOT called when `--topic` is supplied via `args`; assert the supplied topic string is passed directly to `_run_pipeline`

### Implementation for User Story 3

- [x] T017 [US3] Update `pipeline.py` community and random-community branches: replace `topic = random.choice(community.topics)` with `topics = trend_scout.get_topics(community)` and `topic = topics[0] if topics else random.choice(community.topics)`; import `trend_scout` at the top of the file; the `all_manual` branch is unchanged (already bypasses Trend Scout)
- [x] T018 [US3] Log topic source in `pipeline.py`: after topic selection, log `INFO` stating whether the topic came from Trend Scout, seed fallback, or manual override

**Checkpoint**: `--topic` override works unchanged. Community mode uses Trend Scout. US3 is independently testable.

---

## Phase 6: User Story 4 — Swap News Source Without Code Changes (Priority: P3)

**Goal**: A developer can replace the NewsAPI.ai adapter with a stub or alternative source
by changing configuration only — no changes to scoring or orchestration code.

**Independent Test**: Replace `NewsApiAdapter` with a `StubAdapter` that returns a
hardcoded headline list; run `python -m agents.trend_scout --community uk-tech-engineers`
and confirm it uses the stub headlines without touching `trend_scout.py`.

### Tests for User Story 4 (write first — must FAIL before implementation)

- [x] T019 [US4] Add adapter-swap test to `tests/test_trend_scout.py`: create an inline `StubAdapter(SourceAdapter)` returning three fixed `Headline` objects; pass it to `get_topics()` and assert results come from the stub, not from NewsAPI.ai

### Implementation for User Story 4

- [x] T020 [US4] Update `agents/trend_scout.py` to accept an optional `adapter: SourceAdapter | None = None` parameter in `get_topics()`; if `None`, default to `NewsApiAdapter`; this makes the adapter injectable for testing and future source swaps
- [x] T021 [US4] Add `__main__` block and argparse CLI to `agents/trend_scout.py`: `--community` (required), `--top` (default 3); load `.env`, load `communities.yaml`, call `get_topics()`, print numbered results; exit 1 for unknown community, exit 2 for missing env vars

**Checkpoint**: Source adapter is injectable. Standalone CLI works. US4 is independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T022 [P] Run `ruff check . && ruff format .` on all new and modified files; fix any violations before marking complete
- [x] T023 Update `README.md` agents table to add Trend Scout with a one-line description of its function (RULE 11)
- [x] T024 [P] Verify `NEWSAPI_AI_KEY` is listed in `.gitignore`-protected `.env` and NOT present in any committed file (Constitution Principle 10)
- [x] T025 [P] Update `agents/types.py` module-level docstring (or leading comment) to reflect the two new dataclasses `Headline` and `NewsSource`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — blocks all user story phases
- **US1 (Phase 3)**: Depends on Phase 2
- **US2 (Phase 4)**: Depends on Phase 3 (fallback logic lives in `trend_scout.py`)
- **US3 (Phase 5)**: Depends on Phase 3 (needs `get_topics()` to exist for pipeline integration)
- **US4 (Phase 6)**: Depends on Phase 3 (injectable adapter refines existing `get_topics()`)
- **Polish (Phase 7)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: Earliest — no dependency on other stories
- **US2 (P2)**: Extends US1 — fallback logic added to `trend_scout.py`
- **US3 (P1)**: Depends on US1 (`get_topics()` must exist to wire bypass correctly)
- **US4 (P3)**: Depends on US1 (adapter injection refines existing implementation)

### Within Each User Story

- Tests MUST be written and confirmed FAILING before implementation begins
- Models/types before services
- Adapter before orchestrator (`newsapi.py` before `trend_scout.py`)
- Implementation before pipeline integration

### Parallel Opportunities

- T008 and T009 (tests for US1) can run in parallel
- T022, T024, T025 (polish) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch test tasks together (must fail first):
Task: T008 — NewsApiAdapter unit tests in tests/test_sources_newsapi.py
Task: T009 — get_topics() unit tests in tests/test_trend_scout.py

# Then implement sequentially:
Task: T010 — agents/sources/newsapi.py
Task: T011 — agents/trend_scout.py
Task: T012 — communities.yaml (uk-tech-engineers)
```

---

## Implementation Strategy

### MVP (User Stories 1 + 2 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 — Automated Discovery
4. Complete Phase 4: US2 — Fallback
5. **STOP and VALIDATE**: `python -m agents.trend_scout --community uk-tech-engineers` returns real topics; broken URL falls back to seeds
6. Proceed to US3 + US4

### Incremental Delivery

1. Setup + Foundational → types and adapter interface ready
2. US1 → Trend Scout fetches and ranks topics (standalone testable)
3. US2 → Fallback makes it production-safe
4. US3 → Pipeline integration complete (full pipeline usable)
5. US4 → Source swap ready for future adapters (architecture hardened)

---

## Notes

- [P] tasks operate on different files with no cross-dependencies
- Constitution Principle 9: tests MUST be written and confirmed FAILING before implementation
- `NEWSAPI_AI_KEY` must be in `.env` for integration tests; unit tests mock the HTTP call
- The `--topic` manual override path in `pipeline.py` is unchanged — Trend Scout is additive
- `agents/trend_scout.py` imports ONLY from `agents/types.py`, `agents/sources/`, and standard library / SDK — never from `agent_0`, `agent_bc`, `agent_d`, `dual_loop`, or `bundle_writer`