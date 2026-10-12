# Spec 057 — Verdict Tag Tolerance and Panelist Retry

**Stage**: 057 · **Branch**: `057-verdict-tag-tolerance` · **Model**: Flow-Forward (new spec; touches the
Spec 034/052 panel code but is a distinct fix) · **Status**: Implemented — approved by standing
instruction on 2026-10-12 ("go with options 1 and 2 on a new spec ... implement this bug-fix now")
**Dependency**: none (branched from `main`; spec 056 is on hold on its own branch)

## Problem

A `FairParallelPanel` panelist is dropped for the rest of the run when its reply has no `<verdict>`
tag. Gemini 2.5 Flash does this intermittently: the Satirist prompt says both "wrap in `<verdict>`
tags" and "return ONLY valid JSON", and Gemini sometimes obeys only the second and returns bare JSON.
Evidence: the 2026-10-12 live run's `run.log` ("panelist gemini-2.5-flash failed in round 1 —
proposer response missing <verdict> tag: '{ "panels": 3, ...'"), and the same failure in other
recorded runs for Gemini and Grok. A dropped panelist silently reduces the "independent proposals,
peer sharing" design to fewer voices.

## Goal

1. A reply that is entirely valid JSON (optionally in a markdown fence) but has no `<verdict>` tags is
   accepted as the verdict, with a WARNING.
2. A panelist whose reply is still unusable gets exactly one retry with a format reminder before it is
   dropped.

## Requirements

- **FR-001** `_extract_proposer_verdict` MUST return the JSON text (fence removed) when the whole reply
  parses as JSON and has no `<verdict>` tag, and MUST log a WARNING.
- **FR-002** Prose around JSON, invalid/cut-off JSON, and plain text MUST still raise `ValueError`.
- **FR-003** Tagged replies and the Spec 052 unclosed-tag recovery MUST behave exactly as before.
- **FR-004** In `FairParallelPanel`, a `ValueError` from extraction MUST trigger one retry call to the
  same panelist with the conversation plus a format reminder; a second failure drops the panelist as today.
- **FR-005** The unusable first reply and the retry are both counted in telemetry/cost.
- **FR-006** Non-extraction failures (timeout, provider error) are NOT retried.

## Out of scope

Rewording the Satirist/other prompts (option 3 — not chosen); retry in `ParallelPanel`/`DualPersonaLoop`
(they gain only FR-001 through the shared function); the vertical-layout behaviour.

## Success criteria

SC-001 the live-run Gemini reply shape is no longer dropped. SC-002 extra cost is at most one cheap
call per malformed reply. SC-003 all prior tests pass unchanged.
