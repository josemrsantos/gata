# Spec 053 — LinkedIn Post Panel max_tokens Follow-Up

**Stage**: 053
**Branch**: `053-linkedin-post-max-tokens`
**Status**: Draft — awaiting approval
**Dependency**: Spec 052 (verdict truncation recovery), Spec 050 (`run.log`
persistence — the mechanism that surfaced this evidence)

---

## Problem

Spec 052 fixed `_extract_proposer_verdict()` to recover a `<verdict>` cut
off before its closing tag, and raised LinkedIn Angle Planning's
`max_tokens` from `1200` to `2500` — the one call site with live-proven
evidence at the time.

A real `--research-only` run on 2026-09-02 (`run.log`, now persisted thanks
to Spec 050) shows the same truncation mechanism recurring at **two other**
call sites in `agents/agent_linkedin_post.py`, neither touched by Spec 052:

| Panel | `max_tokens` | Truncations in that one run | Rounds |
|---|---|---|---|
| Domain Classification (`_classify_domains_panel`) | `1000` | 3 | 3 |
| LinkedIn Article Writing (`_write_article`) | `3000` | 1 | 2 |

Domain Classification's budget is tighter than Angle Planning's original
(already-proven-too-tight) `1200`, and it runs one more round (3 vs. 2),
giving each round's peer-reactive prompt (every panelist's growing
domain→classification JSON, shared with its peers) more opportunity to
exceed the ceiling. The Writing panel — despite already carrying the
largest budget in the file — still truncated once, unsurprising given it
drafts a full 500–800 word article per round.

Because of Spec 052's recovery fix, this run did **not** lose a panelist or
publish broken content — the final `research_report.md` was read in full
and confirmed complete and coherent. This is a proactive tightening based
on fresh evidence, not a regression or an unfixed bug.

## Goal

Raise `max_tokens` at both remaining call sites, following the same
proportional-bump reasoning already applied to Angle Planning:

1. `_classify_domains_panel()`'s panelist and aggregator `PersonaConfig`:
   `1000` → `2000`.
2. `_write_article()`'s panelist and aggregator `PersonaConfig`: `3000` →
   `4000`.

No change to `_extract_proposer_verdict()` itself — Spec 052's recovery
fallback already applies uniformly to every `FairParallelPanel` caller,
including these two; this spec only reduces how often recovery is needed.

## Files Changed

| File | Change |
|------|--------|
| `agents/agent_linkedin_post.py` | MODIFY — `_classify_domains_panel()`: `max_tokens=1000` → `max_tokens=2000` (panelist + aggregator); `_write_article()`: `max_tokens=3000` → `max_tokens=4000` (panelist + aggregator) |
| `core/__version__.py` | Bump version (patch) |
| `tests/test_agent_linkedin_post.py` | ADD/UPDATE tests asserting the new `max_tokens` values for both panels |

## Files NOT Changed

- `llm/dual_loop.py`'s `_extract_proposer_verdict()` — Spec 052's fallback
  is unmodified.
- LinkedIn Angle Planning's `max_tokens` (already `2500` since Spec 052).
- `_research_gemini`/`_research_claude`/`_research_grok` (line 584,
  `max_tokens=1200`) — this is the initial research call, not a
  peer-reactive `FairParallelPanel` round; no truncation evidence for it in
  this run's `run.log`, so it stays untouched pending its own evidence.

## Success Criteria

1. `_classify_domains_panel()`'s panelist and aggregator `PersonaConfig.max_tokens`
   both equal `2000`.
2. `_write_article()`'s panelist and aggregator `PersonaConfig.max_tokens`
   both equal `4000`.
3. `python -m pytest tests/` — zero failures.
4. `ruff check . && ruff format .` — exit 0.
5. A real, manually-run `--research-only` invocation shows fewer (ideally
   zero) truncation-recovery WARNING lines for Domain Classification and
   LinkedIn Article Writing compared to before this change — verified via
   `run.log`, the same mechanism that surfaced this evidence in the first
   place.
