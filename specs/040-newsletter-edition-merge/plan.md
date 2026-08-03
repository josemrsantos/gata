# Implementation Plan: Newsletter Edition Merge

**Branch**: `040-newsletter-edition-merge` | **Date**: 2026-08-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/040-newsletter-edition-merge/spec.md`

## Summary

Add a standalone script, `newsletter_merge.py`, that discovers story sub-folders
inside an edition folder by their mandatory numeric filename prefix, reads each
story's `linkedin_post.md` text and its stored `"Image Generator"` cost from
`telemetry.json`, and sends a single merge request through a cost-ordered
`LLMProvider` fallback chain — every active Gemini text model cheapest-first, then
Claude/Grok cheapest-first — producing a Markdown draft that ends with a
script-computed edition cost note. The key architectural decision is mirroring the
existing `pipeline.py` / `core/` / `agents/` split rather than a monolithic script:
filesystem and arithmetic logic lives in `core/newsletter_merge.py`, the LLM call and
prompt live in a new, human-readably-named agent (`agents/agent_newsletter_editor.py`,
"Newsletter Editor"), and the CLI stays a thin wrapper.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `google-genai`, `anthropic`, `openai` (all already in
`pyproject.toml`; no new dependency added)
**Storage**: Files only — reads `<story>/<audience>/linkedin_post.md` and
`<story>/<audience>/telemetry.json`; writes one Markdown file
**Testing**: pytest with `unittest.mock` (no real API calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI script — additive extension, no changes to the existing
pipeline
**Performance Goals**: One successful Gemini/Claude/Grok call per run; the fallback
chain (FR-013) is bounded (≈11 candidate models) and only pays for attempts beyond the
first on actual failure
**Constraints**: ruff `line-length = 88`, `target-version = "py310"`
**Scale/Scope**: 1 top-level script, 1 `core/` module, 1 `agents/` module, 2 test
files — no existing file is modified

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | Reuses `GeminiProvider`/`ClaudeProvider`/`GrokProvider` from `llm/`; every model in the fallback chain (FR-013) is drawn from the currently-active model lists already in `llm/gemini.py`, `llm/claude.py`, `llm/grok.py` — no retired slug, no new SDK. |
| 2 | Image Output Rule | ✅ N/A | This feature reads existing images' *cost* from telemetry; it generates no image and writes no PNG. |
| 3 | XML and Output Contract | ✅ N/A | No `<verdict>` block — the merge call returns plain Markdown, not a JSON concept. |
| 4 | Character Rules | ✅ N/A | No image prompt is constructed; Gata's visual description is never referenced. |
| 5 | Visual Style Rules | ✅ N/A | No image prompt is constructed. |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ N/A | Not a Satirist/Cultural-Strategist/Explainer agent, so the ParallelPanel topology in §6 doesn't apply — precedent: `agent_linkedin_post.py` is also a single-call agent with no `<verdict>` loop, for the same reason (text reformatting, not concept generation). |
| 7 | Language Rule | ✅ N/A | No translation or language-check step; the merge preserves whatever language each input `linkedin_post.md` was already written in — garbage-in/garbage-out, same as feeding un-language-checked text to any other tool. |
| 8 | Project Structure | ✅ | New files land only in `core/`, `agents/`, `tests/` (all pre-approved) plus one new top-level script — precedent for a second top-level script already exists (`pipeline.py` itself lives outside the four approved directories). No new top-level directory is created. |
| 9 | Testing Rules | ✅ | `tests/test_newsletter_merge.py` and `tests/test_agent_newsletter_editor.py`, written before their implementation files (Phase-3 tasks precede Phase-4 in `tasks.md`); every provider call mocked; one-sentence RULE-3 comment on every test function. |
| 10 | Secrets and Security | ✅ | `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `XAI_API_KEY` read from environment only (FR-017), never hardcoded; no new secret is introduced. |
| 11 | Development Stages | ✅ | Branch `040-newsletter-edition-merge` created off `main` before any file was written; Spec 039 was already merged to `main` first. |
| 12 | Code Quality | ✅ | `ruff check .` and `ruff format .` run on every new/modified file before considering the stage done. |
| 13 | Logging | ✅ | `logger = logging.getLogger(__name__)` in `core/newsletter_merge.py` and `agents/agent_newsletter_editor.py`; all FR-014 model/cost/failure logging goes through `logging`, never `print()`. The top-level `newsletter_merge.py` script uses a small number of `print()` calls for the final result path and top-level error messages — the same pattern `core/cli.py` already uses for its own user-facing output, even though §13's text names only `pipeline.py` explicitly; this plan follows the codebase's actual established practice (a second top-level CLI entry point behaving like the first) rather than the letter of a clause written before a second entry point existed. |

**Constitution Check result**: all gates pass (rows 2–7 are N/A — this feature touches
neither image generation nor the creative-concept/verdict pipeline; row 13 documents
an established precedent rather than a violation).

## Project Structure

### Documentation (this feature)

```text
specs/040-newsletter-edition-merge/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code Changes

```text
newsletter_merge.py               ADD — thin argparse CLI entry point (mirrors
                                   pipeline.py / core/cli.py): positional
                                   edition_folder, --audience, -o/--output,
                                   credential checks (FR-017), logging setup, calls
                                   core.newsletter_merge.merge_edition().

core/newsletter_merge.py          ADD — story discovery + numeric-prefix ordering
                                   (FR-002, FR-004, FR-005, FR-006); per-story
                                   "Image Generator" cost summation from
                                   telemetry.json (FR-010a, FR-012); cost-ordered
                                   LLMProvider fallback chain construction (FR-013);
                                   output file writing (FR-016).

agents/agent_newsletter_editor.py ADD — "Newsletter Editor" agent: builds the merge
                                   prompt (FR-009, FR-010b, FR-011) from ordered
                                   stories and the estimated total cost, then calls
                                   each provider in the fallback chain in turn
                                   (FR-013, FR-014, FR-015), mirroring the
                                   try/except-per-provider loop already used in
                                   agents/agent_linkedin_post.py.

tests/test_newsletter_merge.py            ADD — covers core/newsletter_merge.py and
                                           the CLI script, all mocked.

tests/test_agent_newsletter_editor.py     ADD — covers agents/agent_newsletter_editor.py
                                           (prompt content, fallback ordering,
                                           logging), all mocked.
```

No existing file is modified: `pipeline.py`, `core/cli.py`, `core/runner.py`,
`providers.yaml`, and every file under `agents/` and `llm/` are read-only inputs to
this feature (their public functions and `_COST_PER_M` tables are imported, not
changed).

**Structure Decision**: Mirrors the existing split between a thin top-level CLI
script and the `agents/` (LLM-calling) / `core/` (orchestration, filesystem,
arithmetic) separation used by every other feature in this codebase, rather than one
monolithic script. Rejected alternative: putting everything in a single top-level
`newsletter_merge.py` — would be shorter to write, but couples filesystem/cost-math
logic (easy to unit test with no mocks) to the LLM fallback logic (needs mocking),
making the test suite slower and less precise about what's actually being verified in
each test, and breaks from how every other agent in this project is organised and
named (RULE 9).
