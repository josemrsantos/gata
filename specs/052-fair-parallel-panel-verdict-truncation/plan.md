# Implementation Plan: FairParallelPanel Verdict Truncation Fix

**Branch**: `052-fair-parallel-panel-verdict-truncation` | **Date**: 2026-08-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/052-fair-parallel-panel-verdict-truncation/spec.md`

## Summary

Two small, independently-safe fixes for the proven `max_tokens`-truncation
failure mode where a panelist's `<verdict>` block is cut off before its
closing tag, causing `_extract_proposer_verdict()` to raise and the panelist
to be dropped entirely. Fix 1 (the load-bearing one): make that shared
parser recover a truncated-but-opened verdict instead of raising, protecting
every current and future caller. Fix 2: raise the one call site
(`_plan_angles`) with live-proven evidence its `max_tokens` budget is too
tight, reducing how often truncation happens there in the first place.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: none new — pure stdlib `re` change plus a config
literal change
**Storage**: none
**Testing**: pytest with `unittest.mock` (no real API calls per Constitution
§9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — bug fix to shared protocol code
**Performance Goals**: None — this fix trades a small amount of extra
output-token cost (2500 vs. 1200 `max_tokens` ceiling, only actually spent if
a panelist needs it) for eliminating a ~32%-of-runs panelist-drop failure
mode
**Constraints**: ruff `line-length = 88`, `target-version = "py310"`; the
existing regression test `test_missing_proposer_verdict_tag_raises_value_error`
(no `<verdict>` tag at all) must keep passing unchanged — this fix only
changes behaviour for the narrower "opened but not closed" case
**Scale/Scope**: 2 modified source files (`llm/dual_loop.py`,
`agents/agent_linkedin_post.py`), 1 version bump, 2 modified test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ N/A | No SDK or model change — this is protocol/parsing code and a token-budget literal. |
| 2 | Image Output Rule | ✅ N/A | No image involvement. |
| 3 | XML and Output Contract | ✅ | The `<verdict>...</verdict>` contract itself is unchanged — a well-formed response is parsed identically to today; only a malformed (truncated) one is now recovered instead of discarded. |
| 4 | Character Rules | ✅ N/A | No image prompt content touched. |
| 5 | Visual Style Rules | ✅ N/A | No image prompt content touched. |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ | No change to iteration count, round structure, or aggregation logic — only to whether a truncated response survives to be used. |
| 7 | Language Rule | ✅ N/A | No text/caption content touched. |
| 8 | Project Structure | ✅ | Changes stay inside `llm/`, `agents/`, `tests/`; no new file, no new package. |
| 9 | Testing Rules | ✅ | New tests in `tests/test_dual_loop.py` (parser fallback) and `tests/test_agent_linkedin_post.py` (max_tokens=2500); every new test function carries a RULE-3 one-sentence comment; existing regression test unchanged and still asserted green; no real API calls. |
| 10 | Secrets and Security | ✅ N/A | No new secret or credential. |
| 11 | Development Stages | ✅ | Work proceeds on branch `052-fair-parallel-panel-verdict-truncation`, created before implementation; merges via PR per RULE 5/RULE 17. |
| 12 | Code Quality | ✅ | `ruff check .` and `ruff format .` run on every modified file before this is considered done. |
| 13 | Logging | ✅ | The recovered-verdict case logs at WARNING (visible, since the response may still be incomplete) via the module's existing `logger = logging.getLogger(__name__)` in `llm/dual_loop.py` — no `print()`. |

**Constitution Check result**: all gates pass or are N/A.

## Project Structure

### Documentation (this feature)

```text
specs/052-fair-parallel-panel-verdict-truncation/
├── plan.md
├── spec.md
└── tasks.md           (Phase 2 output)
```

### Source Code Changes

```text
llm/dual_loop.py                  MODIFY — _extract_proposer_verdict(): when
                                   re.findall finds zero closed matches, check
                                   for an unclosed opening <verdict> tag via
                                   a second regex; if found, log a WARNING and
                                   return everything after the last such tag,
                                   stripped. No opening tag at all still
                                   raises ValueError, unchanged.

agents/agent_linkedin_post.py     MODIFY — _plan_angles(): panelist and
                                   aggregator PersonaConfig max_tokens
                                   1200 -> 2500 (lines 986, 994).

core/__version__.py               MODIFY — bump to 1.28.1 (patch: bug fix,
                                   no new capability).
pyproject.toml                    MODIFY — matching version bump.

tests/test_dual_loop.py           MODIFY — add tests for the missing-
                                   closing-tag fallback (recovers content,
                                   logs WARNING); confirm the existing
                                   no-opening-tag-at-all test is unaffected;
                                   add a FairParallelPanel-level test (or
                                   confirm existing coverage) that a
                                   recovered verdict keeps that panelist
                                   active for subsequent rounds.

tests/test_agent_linkedin_post.py MODIFY — add/update a test asserting
                                   _plan_angles's panelist and aggregator
                                   PersonaConfig.max_tokens both equal 2500.
```

**Structure Decision**: The fix lives at the single shared choke point
(`_extract_proposer_verdict` in `llm/dual_loop.py`) rather than being
patched into `FairParallelPanel`'s exception handling, because the
"opened-but-truncated verdict" failure mode is a parsing-contract question
(what counts as a valid verdict), not a panel-orchestration question (what
to do when a panelist fails) — and because `DualPersonaLoop` and the legacy
`ParallelPanel` both import the same function and get the same protection
for free. `FairParallelPanel.run()`'s round/active-panelist bookkeeping is
completely unchanged: a recovered verdict is, from its point of view, just
a normal successful response.

The `max_tokens` bump is scoped to exactly the one call site with live
evidence (`_plan_angles`), not applied speculatively to Cultural
Strategist/Satirist (see spec.md's Problem section) — raising an unproven
budget would be scope creep this stage doesn't have evidence to justify.

## Complexity Tracking

*No entries — no constitution violations.*
