# Spec 052 — FairParallelPanel Verdict Truncation Fix

**Stage**: 052
**Branch**: `052-fair-parallel-panel-verdict-truncation`
**Status**: Draft — awaiting approval
**Dependency**: none

---

## Problem

A retrospective audit of persisted `agent0_log.txt`/`bc_log.txt` transcripts (92
genuine `FairParallelPanel` runs, post-Spec-034) found that in 29 of them
(≈32%), one panelist — always `gemini-2.5-flash`, never any other provider —
produced a valid round-1 `<verdict>` and then silently vanished starting in
round 2, dropped by the existing `except Exception` handler in
`FairParallelPanel.run()`.

A live run of the LinkedIn Angle Planning panel reproduced and root-caused
the exact mechanism:

```
WARNING: LinkedIn Angle Planning: panelist gemini-2.5-flash failed in round 2
— proposer response missing <verdict> tag: "<verdict>\nANGLE: ...
```

`agents/agent_linkedin_post.py`'s `_plan_angles()` sets `max_tokens=1200` for
both panelists and aggregator (`agents/agent_linkedin_post.py:986,994`).
`llm/dual_loop.py:_extract_proposer_verdict()` (shared by `DualPersonaLoop`,
`FairParallelPanel`, and the legacy `ParallelPanel`) requires **both** an
opening `<verdict>` and a closing `</verdict>` tag
(`re.findall(r"<verdict>(.*?)</verdict>", text, re.DOTALL)`); a response cut
off by `max_tokens` before the closing tag matches nothing and raises
`ValueError`, which `FairParallelPanel.run()` treats as a hard panelist
failure — dropping an otherwise-complete, good-faith response entirely.

Round 2's prompt (`_build_peer_prompt`) asks a panelist to react to every
other panelist's full proposal, not just restate its own — a more discursive
ask that produces longer output than round 1's bare prompt. `gemini-2.5-flash`
appears more prone to this than the other configured providers (0 drops
across `claude-sonnet-4-6`, `grok-build-0.1`, `grok-3-mini` in the same
audit).

**Important caveat, stated plainly**: the truncation mechanism above is
*proven* for LinkedIn Angle Planning (live warning text quoted above). For
Cultural Strategist and Satirist/Co-Satirist — the two panels the 92-run
audit actually covers — it is a well-supported *hypothesis*, not a proven
fact: those panels use `PersonaConfig`'s default `max_tokens=2048` (not
LinkedIn Angle Planning's tight 1200), and the historical audit could not
determine timeout-vs-exception for those drops because neither
`pipeline.py` nor `core/cli.py` persists `logging.warning` output to a file
(a gap Spec 050 addresses separately). This spec does not assume the 2048
budget is also too tight — it does not touch Cultural Strategist's or
Satirist's `max_tokens` at all.

## Goal

1. Make `_extract_proposer_verdict()` tolerant of a missing closing
   `</verdict>` tag: when an opening `<verdict>` tag is present but no
   closing tag is found, recover everything after the last `<verdict>` as
   the verdict content (with a WARNING logged, since the response may still
   be substantively truncated) instead of raising. A response with **no**
   opening `<verdict>` tag at all is unchanged — still a hard `ValueError`,
   since that is a different, genuine protocol violation, not a truncation.
2. Raise `max_tokens` for LinkedIn Angle Planning's panelists and aggregator
   (`agents/agent_linkedin_post.py:986,994`) from `1200` to `2500` — the one
   call site with concrete, live-proven evidence that its budget is too
   tight for a round-2 peer-reactive response.

Because `_extract_proposer_verdict()` is shared by every
`FairParallelPanel`/`DualPersonaLoop`/`ParallelPanel` caller, fix 1 protects
Cultural Strategist and Satirist too — without requiring any unproven
assumption about why their historical drops happened.

## Behaviour

### Before (current)

```
<verdict>
ANGLE: When Your Project's Graph...
FOCUS: Argues that GATA's fixed-stage...
                                          ← max_tokens cutoff, no </verdict>
```
→ `_extract_proposer_verdict` finds zero matches → raises `ValueError` →
`FairParallelPanel` logs a WARNING and drops the panelist from all
subsequent rounds and from the final aggregation entirely.

### After (this spec)

Same truncated response → `_extract_proposer_verdict` finds no *closed*
match, but finds a `<verdict>` opening tag → recovers everything after it
(`ANGLE: When Your Project's Graph...\nFOCUS: Argues that GATA's
fixed-stage...`) as the verdict content, logs a WARNING
(`"...proposer response missing closing </verdict> tag — using truncated
content"`), and the panelist **stays active** for subsequent rounds and
final aggregation, exactly as if its response had closed normally.

A response with no `<verdict>` tag at all (e.g. `"No tags here at all."`)
still raises `ValueError` — unchanged from today.

## Files Changed

| File | Change |
|------|--------|
| `llm/dual_loop.py` | MODIFY `_extract_proposer_verdict()` — add the missing-closing-tag fallback described above |
| `agents/agent_linkedin_post.py` | MODIFY `_plan_angles()` — `max_tokens=1200` → `max_tokens=2500` for both panelists and aggregator (lines 986, 994) |
| `core/__version__.py` | Bump version |
| `tests/test_dual_loop.py` | ADD tests for the missing-closing-tag fallback; existing `test_missing_proposer_verdict_tag_raises_value_error` (no opening tag at all) stays green, unchanged |
| `tests/test_agent_linkedin_post.py` | ADD/UPDATE test asserting `_plan_angles`'s panelist/aggregator `max_tokens` is `2500` |

## Files NOT Changed

- `agents/agent_cultural_strategist.py`, `agents/agent_satirist.py` —
  `max_tokens` left at the `PersonaConfig` default (2048); no evidence yet
  that this budget is the cause of their historical drops (see Problem's
  caveat above).
- `llm/fair_parallel_panel.py`'s round/panelist-drop control flow — a
  recovered verdict is treated identically to a normal one; no change to how
  `active`/`final_results` are managed.
- Every other `FairParallelPanel`/`DualPersonaLoop`/`ParallelPanel` call site
  — automatically protected via the shared parser fix, no per-site changes
  needed.

## Success Criteria

1. Given a proposer response with `<verdict>` present but no closing
   `</verdict>`, `_extract_proposer_verdict()` returns the recovered content
   instead of raising.
2. Given a proposer response with no `<verdict>` tag at all,
   `_extract_proposer_verdict()` still raises `ValueError` (regression
   guard — `test_missing_proposer_verdict_tag_raises_value_error` unchanged).
3. Given a `FairParallelPanel` round where one panelist's response is
   truncated mid-verdict, that panelist is NOT dropped — it remains in
   `active` and participates in subsequent rounds and final aggregation.
4. `_plan_angles()`'s panelist and aggregator `PersonaConfig.max_tokens`
   both equal `2500`.
5. `python -m pytest tests/` — zero failures.
6. `ruff check . && ruff format .` — exit 0.
