# Implementation Plan: Grok as Primary Decider Across All Parallel Panel Agents

**Branch**: `029-grok-parallel-primary` | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/029-grok-parallel-primary/spec.md`

## Summary

Every `ParallelPanel` agent (Satirist, Cultural Strategist, Explainer) adopts Grok-3 as
its aggregator/decider. Cultural Strategist and Explainer are converted from
`DualPersonaLoop` to `ParallelPanel`; their quality-gate logic (Resonator and Editor)
is preserved by moving it into Grok's aggregator system prompt. Grok-3-mini participates
as a panelist alongside Claude and Gemini in all three agents, keeping it distinct from
the Grok-3 aggregator.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: openai (Grok), anthropic (Claude), google-genai (Gemini)
**Storage**: None — no new files on disk
**Testing**: pytest with mocks (no real API calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — additive extension
**Performance Goals**: No regression in latency; Grok-3-mini panelist may be faster
  than Grok-3 panelist
**Constraints**: ruff `line-length=88`; must pass `ruff check .` before commit
**Scale/Scope**: Medium — 5 source files modified, no new files, test updates required

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | Grok SDK unchanged; `grok-3` and `grok-3-mini` are listed in `grok.py` |
| 2 | Image Output Rule | ✅ | Image generation untouched |
| 3 | XML and Output Contract | ✅ | `<verdict>` tags preserved; aggregator prompts require them |
| 4 | Character Rules | ✅ | Gata description untouched |
| 5 | Visual Style Rules | ✅ | Image prompts untouched |
| 6 | Verdict JSON Schema and Iteration Rules | ⚠️ | §6 names Claude as aggregator — **amendment required** (see Complexity Tracking) |
| 7 | Language Rule | ✅ | Language enforcement unchanged |
| 8 | Project Structure | ✅ | No new directories or packages |
| 9 | Testing Rules | ✅ | Tests written before implementation; mocks only |
| 10 | Secrets and Security | ✅ | `XAI_API_KEY` already in use; no new secrets |
| 11 | Development Stages | ✅ | Branch `029-grok-parallel-primary` |
| 12 | Code Quality | ✅ | ruff check and format on all modified files |
| 13 | Logging | ✅ | No new log calls needed; existing infrastructure sufficient |

**Constitution Check result**: 1 violation — §6 requires amendment (approved below).

## Project Structure

### Documentation (this feature)

```text
specs/029-grok-parallel-primary/
├── plan.md      (this file)
├── spec.md
└── tasks.md
```

### Source Code Changes

```text
agents/agent_cultural_strategist.py  MODIFY — DualPersonaLoop → ParallelPanel; new aggregator prompt; signature rename
agents/agent_explainer.py            MODIFY — DualPersonaLoop → ParallelPanel; new aggregator prompt; signature rename
core/runner.py                       MODIFY — aggregator_providers for Satirist and Cultural Strategist; _PARALLEL_PANELISTS constant
core/bundle_writer.py                MODIFY — generate_html call site; new local provider constants
.specify/memory/constitution.md      MODIFY — §6 amendment: Grok replaces Claude as aggregator
tests/test_agent_cultural_strategist.py  MODIFY — rename provider params; mock ParallelPanel not DualPersonaLoop
tests/test_agent_explainer.py        MODIFY — rename provider params; mock ParallelPanel not DualPersonaLoop
tests/test_bundle_writer.py          MODIFY — updated generate_html call site
```

**Structure Decision**: All changes are confined to existing files. No new modules
needed — `ParallelPanel` already exists in `llm/parallel_panel.py`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| §6 — "Claude as aggregator" and "Claude has final say" — must change to Grok | The spec goal is precisely to give Grok the aggregator/decider role across all agents | Keeping Claude as aggregator contradicts the spec goal; there is no simpler path |

**Amendment**: §6 updated to read "Grok (`grok-3`) is the aggregator/decider across all
`ParallelPanel` agents. Grok-3-mini participates as panelist. The quality-gate behaviour
(Resonator, Editor) is encoded in Grok's aggregator prompt."
