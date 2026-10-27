# Implementation Plan: Tag-free, JSON-free panel responses

**Branch**: `058-tag-free-panel-responses` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/058-tag-free-panel-responses/spec.md`

## Summary

Every production panel is a `FairParallelPanel` (Cultural Strategist, Satirist, Explainer x2, Engagement
Image, LinkedIn Angle Planning / Writing / Domain Classification). Today each prompt demands
`<verdict>` tags and `FairParallelPanel` rejects any reply the shared strict extractor cannot read. The key
decision: add one new tolerant module, `llm/reply_parsing.py`, that turns any reply (tagged, unclosed,
fenced, bare, labelled) into the answer and logs every fallback with full context; `FairParallelPanel`
switches to it and takes an optional per-agent usability check and retry reminder. The strict
`_extract_proposer_verdict` stays untouched for `DualPersonaLoop`/`ParallelPanel` (not used by any agent
today) so nothing else changes behaviour. Prompts then drop the tags and JSON.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: stdlib only (`re`, `json`, `logging`, `dataclasses`); existing provider SDKs
(`anthropic`, `google-genai`, `openai`) are touched only to read a stop reason
**Storage**: none (run bundle `run.log` already persists WARNINGs per Spec 050)
**Testing**: pytest with mocks (no real API calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — additive extension
**Performance Goals**: none; no extra calls on the happy path
**Constraints**: ruff `line-length=88`; RULE 3 test comments; RULE 14 no blank-line phase dividers in
function bodies; Constitution §3/§6 currently mandate `<verdict>` JSON for the Satirist (see below)
**Scale/Scope**: 1 new module, ~8 modified source files, prompts in 6 agents, ~10 test files touched

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | No new SDK or model; providers only expose an already-returned stop reason |
| 2 | Image Output Rule | ✅ | Untouched |
| 3 | XML and Output Contract | ⚠️ | §3 says the Satirist wraps JSON in `<verdict>` and parsers use that regex. This spec removes both. **Amendment v1.6 required** (G3) — see Complexity Tracking |
| 4 | Character Rules | ✅ | Gata description stays verbatim in the Satirist prompt; existing test keeps asserting it |
| 5 | Visual Style Rules | ✅ | Untouched |
| 6 | Verdict JSON Schema and Iteration Rules | ⚠️ | The JSON schema becomes a `LABEL: value` schema with the same fields; iteration rules untouched. Covered by the same amendment |
| 7 | Language Rule | ✅ | Title/caption language rules are kept in the new Satirist prompt |
| 8 | Project Structure | ✅ | One new file in an approved directory (`llm/reply_parsing.py`); no new package |
| 9 | Testing Rules | ✅ | Tests first; all provider calls mocked |
| 10 | Secrets and Security | ✅ | Log excerpts are 400 chars of model output; no keys involved |
| 11 | Development Stages | ✅ | Branch `058-tag-free-panel-responses`; stage 058 |
| 12 | Code Quality | ✅ | ruff check + format; logging module only |
| 13 | Logging | ✅ | WARNINGs carry agent, round, model; no bare `print()` |

**Constitution Check result**: 11 pass, 2 flagged (§3, §6) — resolved by one amendment, v1.6, which the
project lead must approve at G3 before implementation touches the Satirist contract.

## Design

### New: `llm/reply_parsing.py` (ADD)
- `ParseContext` (frozen dataclass): `agent` (panel name, e.g. `Satirist/Co-Satirist`), `role`
  (panelist name or `Aggregator`), `round`, `model`, `stop_reason`, `output_tokens`, `max_tokens`.
- `unwrap_reply(text) -> str`: legacy-tolerant. Closed `<verdict>` → content (Spec 052/057 behaviour,
  warns only for the unclosed and bare-JSON cases as today but via `log_parse_issue`); otherwise the whole
  reply with one surrounding code fence removed. Raises `ValueError` only for an empty reply.
- `split_pick(text) -> tuple[int | None, str]`: finds `PICK: N` on its own line (tolerates bold/bullets),
  returns the number and the rest of the reply.
- `parse_labelled(text, labels) -> dict[str, str]`: `LABEL: value` lines, value runs to the next known
  label; tolerates case, `**LABEL**:`, `## LABEL`, `Scene 1:`-style drift and a surrounding fence.
- `log_parse_issue(ctx, field, applied, reply)`: the single WARNING emitter (FR-007/008): agent, role,
  round, model, stop reason / `output_tokens` vs `max_tokens`, failed field, default applied, first 400
  characters.

### Modified
- `core/types.py` (EXTEND): `TokenUsage` gains `stop_reason: str | None = None` (default keeps every
  existing constructor call valid).
- `llm/claude.py`, `llm/gemini.py`, `llm/grok.py` (EXTEND): fill `stop_reason` from the response
  (`stop_reason` / `finish_reason`), best effort (FR-008).
- `llm/fair_parallel_panel.py` (MODIFY): use `unwrap_reply`; new optional constructor args
  `reply_check: Callable[[str], str | None] | None` (returns a reason when the reply is unusable) and
  `format_reminder: str`; the single retry uses `format_reminder` (FR-008a), and the same one-retry rule
  now also covers an unusable aggregator reply; the peer-round prompt no longer mentions tags; the
  aggregator verdict is the text after `split_pick`; builds a `ParseContext` from the persona, the round
  and the call's `TokenUsage` (its `model` names the provider that answered after any fallback).
- `agents/agent_satirist.py` (MODIFY): labelled prompt + `parse_satirist_reply()` replacing the JSON-only
  `_parse_verdict` (legacy JSON still accepted per FR-009); implements FR-003/FR-006 required-vs-default
  rules; supplies `reply_check` and `format_reminder`; aggregator prompt drops tags.
- `agents/agent_cultural_strategist.py`, `agent_explainer.py`, `agent_engagement_image.py`,
  `agent_linkedin_post.py` (MODIFY): prompts drop `<verdict>` wording; Explainer strips a surrounding code
  fence; LinkedIn Domain Classification prompt and parser move to one line per domain (FR-004).
- `llm/dual_loop.py`, `llm/parallel_panel.py` (UNCHANGED): keep the strict extractor.
- `CHANGELOG.md`, `README.md`, `docs/architecture.md`, version file (MODIFY, RULE 15/17).
- `.specify/memory/constitution.md` (MODIFY at G3): v1.6, §3 and §6.
- `TODO.md` (MODIFY at G3, RULE 19): remove this item and the superseded "Satirist output-format wording".

### Tests (written first, RULE 3 comments)
`tests/test_reply_parsing.py` (ADD), updates to `tests/test_fair_parallel_panel.py`,
`test_agent_satirist.py`, `test_agent_cultural_strategist.py`, `test_agent_linkedin_post.py`, explainer
and engagement-image tests, plus provider tests for `stop_reason`. Fixtures: the 2026-10-27 unclosed
`<verdict>` reply and the bare fenced Satirist JSON reply (copied from `run.log` evidence).

## Project Structure

### Documentation (this feature)

```text
specs/058-tag-free-panel-responses/
├── plan.md
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/reply-formats.md
├── plan-summary.md    (written after tasks + analyze, for G2)
└── tasks.md           (/speckit-tasks)
```

**Structure Decision**: a new shared module rather than editing `_extract_proposer_verdict`, because that
function is also the contract of `DualPersonaLoop`/`ParallelPanel`; changing it would silently change code
paths this spec says it leaves alone. The per-agent check and reminder are constructor arguments, matching
the existing opt-in `round_validator` pattern.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| §3 — Satirist no longer wraps JSON in `<verdict>`; parsers no longer rely on that regex | The tags and JSON are the failure being removed | Keeping them in the prompt keeps the retries and lost panelists this spec exists to remove |
| §6 — verdict JSON schema replaced by a `LABEL: value` schema (same fields) | Same | Same; the fields and limits (1–4 panels, layout, title, scene/caption/beat) are unchanged |
