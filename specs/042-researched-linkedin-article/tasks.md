# Tasks: Research/Title-Fetch Executor Hang Fix (Amendment, 2026-09-15)

**Input**: `specs/042-researched-linkedin-article/spec.md` (Amendment
2026-09-15), `plan.md` (same amendment)
**Branch**: `042-linkedin-research-hang-fix`
**Prerequisites**: plan.md ✅, spec.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions.

**Scope note**: this `tasks.md` covers only the 2026-09-15 amendment (FR-031,
FR-032). Spec 042's original scope and its two prior amendments were already
implemented and merged; this file does not re-litigate them.

---

## Phase 1: Setup

- [x] T001 Confirm active git branch is `042-linkedin-research-hang-fix`

---

## Phase 2: SDK-level per-call timeouts (FR-031, SC-018)

### Tests — Write FIRST, Confirm FAILING

- [x] T002 [P] In `tests/test_agent_linkedin_post.py`: add
  `test_research_claude_passes_explicit_timeout` — mock
  `provider.client.messages.create`, call `_research_claude`, assert the
  mock was called with `timeout=_RESEARCH_TIMEOUT_SECONDS`
- [x] T003 [P] In `tests/test_agent_linkedin_post.py`: add
  `test_research_grok_passes_explicit_timeout` — mock
  `provider.client.responses.create`, call `_research_grok`, assert the
  mock was called with `timeout=_RESEARCH_TIMEOUT_SECONDS`
- [x] T004 [P] In `tests/test_agent_linkedin_post.py`: add
  `test_research_gemini_passes_explicit_http_timeout` — mock
  `provider.client.models.generate_content`, call `_research_gemini`,
  assert the mock's `config.http_options.timeout` equals
  `int(_RESEARCH_TIMEOUT_SECONDS * 1000)`

> **STOP**: Confirm T002–T004 FAIL before T005.

### Implementation

- [x] T005 In `agents/agent_linkedin_post.py`: `_research_claude` — add
  `timeout=_RESEARCH_TIMEOUT_SECONDS` to the `client.messages.create()` call
- [x] T006 In `agents/agent_linkedin_post.py`: `_research_grok` — add
  `timeout=_RESEARCH_TIMEOUT_SECONDS` to the `client.responses.create()` call
- [x] T007 In `agents/agent_linkedin_post.py`: `_research_gemini` — add
  `http_options=genai_types.HttpOptions(timeout=int(_RESEARCH_TIMEOUT_SECONDS
  * 1000))` to the existing `GenerateContentConfig(...)`

> **STOP**: `python -m pytest tests/test_agent_linkedin_post.py -v` — confirm T002–T004 now pass.

---

## Phase 3: Non-blocking executor shutdown (FR-032, SC-019, SC-020)

### Tests — Write FIRST, Confirm FAILING

- [x] T008 In `tests/test_agent_linkedin_post.py`: add
  `test_research_all_panelists_returns_when_one_panelist_hangs` —
  monkeypatch `_RESEARCH_TIMEOUT_SECONDS` to `0.05`; mock one of three
  panelist research functions to block on a `threading.Event` that the test
  never sets (simulating a genuinely stuck call), the other two returning
  normally; call `research_all_panelists()` from the main thread with a
  wall-clock deadline (e.g. via a helper that fails the test if the call
  takes longer than ~2s); assert it returns within that bound with the
  stuck panelist's digest `None` and the other two populated
- [x] T009 In `tests/test_agent_linkedin_post.py`: add
  `test_resolve_sources_returns_when_one_fetch_hangs` — monkeypatch
  `_TITLE_FETCH_TIMEOUT_SECONDS` to `0.05`; mock `_fetch_page_title` so one
  of several candidate URLs blocks on an unset `threading.Event`, the
  others returning normally; call `_resolve_sources(..., do_fetch=True)`
  with the same wall-clock-deadline pattern as T008; assert it returns
  within bound and the stuck candidate falls through the existing title
  chain (FR-011) instead of hanging the test

> **STOP**: Confirm T008–T009 FAIL (i.e. hang/timeout in the test itself)
> before T010. If your test runner has no hard per-test timeout, verify the
> failure manually by observing the test hang, then Ctrl+C — do not let a
> genuinely hanging test suite block CI once T010 is in place.

### Implementation

- [x] T010 In `agents/agent_linkedin_post.py`: `research_all_panelists()` —
  replace `with concurrent.futures.ThreadPoolExecutor(...) as executor:`
  with `executor = concurrent.futures.ThreadPoolExecutor(...)`; keep the
  existing per-future `result(timeout=_RESEARCH_TIMEOUT_SECONDS)` loop
  un-nested from the removed `with`; add
  `executor.shutdown(wait=False, cancel_futures=True)` immediately after
  that loop
- [x] T011 In `agents/agent_linkedin_post.py`: `_resolve_sources()`'s
  `do_fetch` branch — identical restructuring: drop the `with`, add
  `executor.shutdown(wait=False, cancel_futures=True)` after the per-future
  result loop

> **STOP**: `python -m pytest tests/test_agent_linkedin_post.py -v` — confirm all pass, and confirm the full run completes in a few seconds (no real hang).

**Checkpoint**: `python -m pytest tests/test_agent_linkedin_post.py -v`

---

## Phase 4: Polish & Cross-Cutting Concerns (RULE 6, 15, 17)

- [x] T012 Run `python -m pytest tests/ -v` — confirm zero failures across
  the whole suite
- [x] T013 [P] Run `ruff check . --fix` and `ruff format .`; confirm
  `ruff check .` exits 0
- [x] T014 [P] Add a new `CHANGELOG.md` entry (bug fix: `--linkedin-post`
  research/title-fetch stage could hang indefinitely on a stuck provider
  call; now bounded by an explicit SDK-level timeout plus non-blocking
  executor cleanup)
- [x] T015 [P] Bump version in `pyproject.toml` and `core/__version__.py`
  (patch: 1.29.1 → 1.29.2)
- [x] T016 Check `README.md`/`docs/architecture.md` for staleness — likely
  none needed (no new flag, no new file, no operator-visible behavior
  change beyond "no longer hangs") but confirm before skipping

---

## Phase 5: Real End-to-End Verification

**Deferred** — developer chose to rely on the deterministic simulated-stall
tests (T008/T009) plus the full suite rather than spend a real end-to-end
`--linkedin-post` run's time/cost right now (2026-09-15). Do this before the
next real `--linkedin-post` use, not necessarily before merge.

- [ ] T017 Run a real `--linkedin-post` invocation end to end (real API
  keys via `source set_gata.sh`) and confirm it completes (or soft-fails
  per FR-005/FR-008) without a multi-hour stall; the original network
  stall that caused the two-and-a-half-hour hang is not reliably
  reproducible on demand, so this run's purpose is a normal-path
  regression check — the hang-proof itself lives in T008/T009's
  deterministic simulated-stall tests
- [ ] T018 Confirm no gap longer than a few minutes between consecutive
  log/terminal lines during T017's run

---

## Summary

| Phase | Tasks | Notes |
|-------|-------|-------|
| 1 Setup | T001 | Branch hygiene |
| 2 SDK timeouts | T002–T007 | Claude, Grok, Gemini research calls |
| 3 Non-blocking shutdown | T008–T011 | research_all_panelists + _resolve_sources |
| 4 Polish | T012–T016 | Full suite + ruff + CHANGELOG + version + doc check |
| 5 Verify | T017–T018 | Real end-to-end regression run |
| **Total** | **18 tasks** | |
