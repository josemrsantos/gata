# Implementation Plan: Newsletter Engagement Image & Notification

**Branch**: `041-newsletter-engagement-image` | **Date**: 2026-08-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/041-newsletter-engagement-image/spec.md`

## Summary

Extend `newsletter_merge.py` with two new default-on steps that run around the
existing merge-text call: (1) a `FairParallelPanel` deliberation over the edition's
story texts produces a single image-generation prompt, rendered via a newly
extracted `core/image_generation.py` into `engagement_image.png`; (2) the existing
merge-text call's system prompt is extended to also emit a `===NOTIFICATION===`
section, written to `edition_notification.txt`. The key architectural decision is
extraction, not duplication: `agents/agent_image_generator.py`'s Gemini-call/retry
logic moves into a provider-agnostic `ImageGeneration` class so the per-story and
per-edition paths render through identical code, and the notification text rides on
the merge call's existing single Gemini request rather than adding a second call.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `google-genai`, `PIL` (already in `pyproject.toml`; no new
dependency)
**Storage**: Files only — reads each story's `linkedin_post.md`; writes
`engagement_image.png` and `edition_notification.txt` alongside the existing
`merged_linkedin_post.md`
**Testing**: pytest with `unittest.mock` (no real API calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI script extension + one refactor of shared pipeline code
**Performance Goals**: One `FairParallelPanel` run (N panelists + 1 aggregator, all
text) + one image-generation call per edition, in addition to Spec 040's existing
single merge call — no change to per-story pipeline latency
**Constraints**: ruff `line-length = 88`, `target-version = "py310"`; RULE 12 — the
per-story manual image-generation path must keep working unchanged
**Scale/Scope**: 2 new modules (`core/image_generation.py`,
`agents/agent_engagement_image.py`), 4 modified files
(`agents/agent_image_generator.py`, `core/runner.py`,
`agents/agent_newsletter_editor.py`, `core/newsletter_merge.py`,
`newsletter_merge.py`), 5 test files (2 new, 3 modified), 1 fixture directory

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | `core/image_generation.py` reuses the exact `_MODELS` fallback list and `google.genai` call pattern already in `agent_image_generator.py` — no new SDK, no retired model. |
| 2 | Image Output Rule | ✅ | Extraction preserves the existing atomic-write pattern (`tempfile.NamedTemporaryFile` + `os.replace()`) verbatim; the image prompt itself is still never written to disk. |
| 3 | XML and Output Contract | ✅ | `agents/agent_engagement_image.py`'s panelists/aggregator use `<verdict>...</verdict>`, parsed via `llm.dual_loop._extract_proposer_verdict` — the same extraction helper every other `FairParallelPanel` agent uses. |
| 4 | Character Rules | ✅ | The verbatim `_GATA_CHARACTER` paragraph is duplicated into `agents/agent_engagement_image.py`'s panelist system prompt (same duplication rationale already documented in `agent_image_generator.py`); a test asserts the exact string is present. |
| 5 | Visual Style Rules | ✅ | Corrected during implementation: an earlier draft of this plan wrongly marked this row N/A, and the first real end-to-end run produced a photorealistic office scene with no greyscale/Selective-Color/newsroom styling. Constitution §5 applies to "every image prompt" with no engagement-image carve-out — `agents/agent_engagement_image.py`'s panelist and aggregator system prompts now both include the same style block used in `agent_image_generator.py`'s `_build_multi_panel_prompt`, and a test asserts its presence in both. |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ N/A | The panel's verdict is freeform prose (the final image prompt itself, per spec FR-004), not the Satirist's panels/layout/title/content JSON — that schema is specific to multi-panel comic-strip generation, which this feature explicitly excludes (FR-011). |
| 7 | Language Rule | ✅ N/A | No translation step; stories are already in the edition's chosen `--audience` language, same as Spec 040. |
| 8 | Project Structure | ✅ | New files land in `agents/`, `core/`, `tests/` only — no new top-level directory. |
| 9 | Testing Rules | ✅ | `tests/test_image_generation.py` and `tests/test_agent_engagement_image.py` are new; `tests/test_agent_image_generator.py`, `tests/test_agent_newsletter_editor.py`, `tests/test_newsletter_merge.py` are updated for the refactor; every test function carries a RULE-3 one-sentence comment; all provider/SDK calls mocked. |
| 10 | Secrets and Security | ✅ | No new secret; the manual end-to-end fixture run (`041_test_edition`) uses `source set_gata.sh` per RULE 16, same as any other manual pipeline run — not part of the automated test suite. |
| 11 | Development Stages | ✅ | Branch `041-newsletter-engagement-image` created off `main` before any file was written. |
| 12 | Code Quality | ✅ | `ruff check .` and `ruff format .` run on every new/modified file; RULE 14 (no blank-line phase dividers inside function bodies) followed in all new/modified function bodies. |
| 13 | Logging | ✅ | `logger = logging.getLogger(__name__)` in both new modules; every panelist/aggregator/image-generation attempt and the two soft-failure paths (FR-008, FR-014) are logged via `logging`, never `print()`. |

**Constitution Check result**: all gates pass (row 6 is N/A — this feature's verdict
is a single freeform prompt, not the Satirist's fixed comic-strip scene/JSON
contract; row 5 applies in full, see note above).

## Project Structure

### Documentation (this feature)

```text
specs/041-newsletter-engagement-image/
├── spec.md
└── plan.md
```

### Source Code Changes

```text
core/image_generation.py          ADD — ImageGeneration class: the Gemini image-model
                                   fallback loop, atomic file write, and
                                   _overlay_title helper extracted verbatim from
                                   agents/agent_image_generator.py (FR-006). Entry
                                   point: generate(prompt: str, output_path: str,
                                   title: str | None = None, show_title: bool =
                                   True) -> tuple[str, AgentTelemetry]. No
                                   dependency on CartoonConcept/StrategyBrief/
                                   CartoonLayout.

agents/agent_image_generator.py   MODIFY — generate() keeps its existing signature
                                   minus the unused brief parameter (FR-007);
                                   builds the prompt from concept/layout exactly as
                                   today (_build_multi_panel_prompt unchanged), then
                                   delegates rendering to
                                   core.image_generation.ImageGeneration.

core/runner.py                    MODIFY — one call site updated to drop the
                                   brief argument (FR-007).

agents/agent_engagement_image.py  ADD — "Engagement Image Concept" agent: builds
                                   panelist/aggregator PersonaConfigs (panelists
                                   named by model_id, aggregator named "Art
                                   Director", mirroring
                                   agents/agent_cultural_strategist.py's
                                   convention), runs llm.fair_parallel_panel.
                                   FairParallelPanel over the edition's story texts
                                   plus the duplicated _GATA_CHARACTER block
                                   (FR-002-005), returns the aggregator's verdict
                                   (the final image prompt) and its AgentTelemetry.

agents/agent_newsletter_editor.py MODIFY — _SYSTEM_PROMPT and build_merge_prompt
                                   extended to require a second
                                   ===NOTIFICATION=== section (FR-013); new
                                   parse_merge_response(raw) -> tuple[str, str |
                                   None] splits the response into (article_text,
                                   notification_text_or_None), lenient about a
                                   missing marker (FR-014).

core/newsletter_merge.py          MODIFY — merge_edition() gains a generate_image:
                                   bool = True parameter; when True, runs
                                   agent_engagement_image.run() then
                                   core.image_generation.ImageGeneration().generate()
                                   before the merge-text call, catching any
                                   exception as a soft failure (FR-008) with a
                                   logged warning; folds the resulting exact costs
                                   into the total passed to generate_merged_post
                                   (FR-010); calls
                                   agent_newsletter_editor.parse_merge_response() on
                                   the result and returns both the article text and
                                   the optional notification text.

newsletter_merge.py               MODIFY — adds --no-image flag (FR-009); writes
                                   edition_notification.txt alongside
                                   merged_linkedin_post.md when notification text is
                                   present (FR-014); prints a warning line when the
                                   image or notification step was skipped.

tests/test_image_generation.py            ADD — covers core/image_generation.py in
                                           isolation (moved/adapted from the
                                           relevant tests currently in
                                           test_agent_image_generator.py).

tests/test_agent_image_generator.py       MODIFY — updated to assert generate()
                                           delegates to ImageGeneration and no
                                           longer accepts brief; prompt-building
                                           tests (multi-panel, Gata description,
                                           title overlay routing) stay in this file
                                           since they test agent_image_generator's
                                           own responsibility.

tests/test_agent_engagement_image.py      ADD — covers panel wiring, the verbatim
                                           Gata-description assertion (Constitution
                                           §4), and that no story image is ever
                                           included in the panel's input.

tests/test_agent_newsletter_editor.py     MODIFY — adds coverage for
                                           parse_merge_response() (both sections
                                           present, notification absent).

tests/test_newsletter_merge.py            MODIFY — adds coverage for the
                                           engagement-image soft-failure path,
                                           --no-image, and the extended cost total
                                           (FR-008-010).

041_test_edition/                 ADD — 3-story fixture (adapted from the existing
                                   local 040-newsletter-edition-merge-test content)
                                   used for one real, manually-run end-to-end pass
                                   producing an actual engagement_image.png and
                                   edition_notification.txt for human review — not
                                   part of the automated pytest suite.
```

**Structure Decision**: Extraction over duplication for the rendering code (RULE 12
risk is real — this is the one path both per-story and per-edition images share, so
it needs exactly one implementation, not two that can drift). The notification text
rides the existing merge call rather than becoming a third Gemini call, mirroring
how `agents/agent_linkedin_post.py` already produces five sections from one call —
precedent for "one call, several marked outputs" already exists in this codebase.
Rejected alternative: a bespoke Framer/Resonator pair for the image concept (as
first discussed) — `FairParallelPanel` already does independent-propose →
peer-aware-revise → aggregate-pick, which is exactly what's needed, so introducing a
second, narrower protocol class would be duplication with no benefit.
