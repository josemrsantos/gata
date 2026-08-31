# Tasks: FairParallelPanel Verdict Truncation Fix

**Input**: Design documents from `specs/052-fair-parallel-panel-verdict-truncation/`
**Branch**: `052-fair-parallel-panel-verdict-truncation`
**Prerequisites**: plan.md ✅, spec.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions.

---

## Phase 1: Setup

- [x] T001 Confirm active git branch is `052-fair-parallel-panel-verdict-truncation`

---

## Phase 2: Parser Fallback (SC-001, SC-002, SC-003)

### Tests — Write FIRST, Confirm FAILING

- [ ] T002 [P] In `tests/test_dual_loop.py`: add
  `test_missing_closing_tag_recovers_truncated_content` — a proposer response
  with `<verdict>ANGLE: X\nFOCUS: Y` (opening tag, no closing tag) must
  return the content after `<verdict>` instead of raising; add
  `test_missing_closing_tag_logs_warning` — same input must log a WARNING
  naming the truncation; confirm the existing
  `test_missing_proposer_verdict_tag_raises_value_error` (no opening tag at
  all) is unaffected
- [ ] T003 [P] In `tests/test_fair_parallel_panel.py`: add
  `test_truncated_round2_verdict_keeps_panelist_active` — a panelist whose
  round-1 response is well-formed but whose round-2 response has an opening
  `<verdict>` with no closing tag must remain in the panel through
  aggregation, not be dropped

> **STOP**: Confirm T002–T003 FAIL before T004.

### Implementation

- [ ] T004 In `llm/dual_loop.py`: modify `_extract_proposer_verdict()` — when
  `re.findall(r"<verdict>(.*?)</verdict>", text, re.DOTALL)` finds no
  matches, check for an unclosed `<verdict>` via
  `re.search(r"<verdict>(.*)$", text, re.DOTALL)`; if found, log
  `logger.warning(...)` and return the captured group stripped; otherwise
  raise `ValueError` as today

> **STOP**: `python -m pytest tests/test_dual_loop.py tests/test_fair_parallel_panel.py -v` — confirm all pass.

**Checkpoint**: `python -m pytest tests/test_dual_loop.py tests/test_fair_parallel_panel.py tests/test_parallel_panel.py -v`

---

## Phase 3: LinkedIn Angle Planning max_tokens (SC-004)

### Tests — Write FIRST, Confirm FAILING

- [ ] T005 [P] In `tests/test_agent_linkedin_post.py`: add
  `test_plan_angles_panelist_and_aggregator_use_2500_max_tokens` — captures
  the `PersonaConfig` objects `_plan_angles` builds and asserts both
  panelist and aggregator `max_tokens == 2500`

> **STOP**: Confirm T005 FAILS before T006.

### Implementation

- [ ] T006 In `agents/agent_linkedin_post.py`: `_plan_angles()` —
  `max_tokens=1200` → `max_tokens=2500` at lines 986 and 994

> **STOP**: `python -m pytest tests/test_agent_linkedin_post.py -v` — confirm all pass.

**Checkpoint**: `python -m pytest tests/test_agent_linkedin_post.py -v`

---

## Phase 4: Polish & Cross-Cutting Concerns (RULE 6, 15, 17)

- [ ] T007 Run `python -m pytest tests/ -v` — confirm zero failures across
  the whole suite
- [ ] T008 [P] Run `ruff check . --fix` and `ruff format .`; confirm
  `ruff check .` exits 0
- [ ] T009 [P] Add a new `CHANGELOG.md` entry (bug fix: verdict-truncation
  recovery + max_tokens bump)
- [ ] T010 [P] Bump version in `pyproject.toml` and `core/__version__.py`
  (patch: 1.28.0 → 1.28.1)
- [ ] T011 Check `README.md`/`docs/architecture.md` for staleness — likely
  none needed (no new flag, no new file, no behavior an operator configures)
  but confirm before skipping
- [ ] T012 Update `CLAUDE.md`'s Completed Stages table: add a row for `052`

---

## Phase 5: Real End-to-End Verification (×4, per operator request)

- [ ] T013 Run `gata "<real topic>" --research-only` **four times** (real
  API keys via `source set_gata.sh`) — for each run, confirm the log
  contains no `"panelist gemini-2.5-flash failed"` drop message, or if
  truncation still occurs, confirm it now logs as a *recovered* warning
  (not a drop) and `gemini-2.5-flash` still contributes to the final
  aggregation
- [ ] T014 Summarize the 4 runs' outcomes (recovered vs. clean vs. any
  unexpected failure) before opening the PR

---

## Summary

| Phase | Tasks | Notes |
|-------|-------|-------|
| 1 Setup | T001 | Branch hygiene |
| 2 Parser fallback | T002–T004 | Shared fix, protects every caller |
| 3 max_tokens | T005–T006 | LinkedIn Angle Planning only |
| 4 Polish | T007–T012 | Full suite + ruff + CHANGELOG + version + CLAUDE.md |
| 5 Verify | T013–T014 | 4× real `--research-only` runs |
| **Total** | **14 tasks** | |
