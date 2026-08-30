# Implementation Plan: Research-Only Mode

**Branch**: `046-research-only-mode` | **Date**: 2026-08-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/046-research-only-mode/spec.md`

## Summary

Add a `--research-only` flag to both `pipeline.py` and the `gata` CLI that
skips the entire cartoon pipeline (Cultural Strategist, Satirist, Image
Generator, Image Evaluator) and runs only Spec 042's research →
angle-planning → writing engine against a minimal `EnrichedBrief`. The key
architectural decision: `generate_linkedin_post` gains a `branded: bool`
switch controlling final assembly only — `branded=True` produces today's
Gata-branded `linkedin_post.md` (now reachable without any cartoon concept),
`branded=False` produces a new neutral `research_report.md`. Exactly one of
the two is ever produced per run; the expensive research/writing panels
never run twice.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: none new — reuses `llm/fair_parallel_panel.py` and
existing provider clients
**Storage**: Files only — a new `research_report.md` file in the output
bundle; no new persistent state (the domain-classification DuckDB cache is
unchanged)
**Testing**: pytest with `unittest.mock` (no real API calls per Constitution
§9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — additive extension
**Performance Goals**: Strictly cheaper than today's default run for the same
topic — no Cultural Strategist, Satirist, Image Generator, or Image Evaluator
calls at all; the research/angle-planning/writing panels' cost is unchanged
from Spec 042
**Constraints**: ruff `line-length = 88`, `target-version = "py310"`; RULE 12
— direct image generation must keep working unchanged without
`--research-only`
**Scale/Scope**: 1 modified core module (`core/runner.py`), 1 modified agent
module (`agents/agent_linkedin_post.py`), 1 modified shared writer
(`core/bundle_writer.py`), 2 modified CLI entry points (`pipeline.py`,
`core/cli.py`), 5 modified test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ N/A | No new SDK, no model change — reuses the exact provider clients already threaded through `run_pipeline()`. |
| 2 | Image Output Rule | ✅ N/A | This mode never calls `agent_image_generator` — no image is written, so the atomic-write guarantee has nothing to apply to on this path; the existing rule is untouched for every other mode. |
| 3 | XML and Output Contract | ✅ N/A | No `<verdict>` involvement — `research_only` never calls the Satirist. Spec 042's own `<verdict>` usage inside angle-planning/writing panels is unchanged. |
| 4 | Character Rules | ✅ N/A | No image prompt is ever built in this mode; `_GATA_CHARACTER` is untouched. |
| 5 | Visual Style Rules | ✅ N/A | No image prompt content in this mode. |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ | Satirist/`FairParallelPanel` iteration rules for cartoon generation are untouched; the research/angle-planning/writing panels' own iteration behaviour (Spec 042) is unmodified by this feature. |
| 7 | Language Rule | ✅ | The report still respects `brief.output_language` via the unchanged writing-panel prompt (FR-018 of Spec 042); no new translation step. |
| 8 | Project Structure | ✅ | All changes stay inside `agents/`, `core/`, `tests/`; no new package. `output/research/` is a new subdirectory of the existing gitignored runtime `output/` tree, not a governed source directory. |
| 9 | Testing Rules | ✅ | New/updated tests in `tests/test_pipeline.py`, `tests/test_cli.py`, `tests/test_agent_linkedin_post.py`, `tests/test_bundle_writer.py`; every new test function carries a RULE-3 one-sentence comment; every provider/SDK call mocked, zero real API calls in the suite. |
| 10 | Secrets and Security | ✅ N/A | No new secret or credential. |
| 11 | Development Stages | ✅ | Work proceeds on branch `046-research-only-mode`, created before implementation; merges via PR per RULE 5/RULE 17. |
| 12 | Code Quality | ✅ | `ruff check .` and `ruff format .` run on every modified file before this is considered done. |
| 13 | Logging | ✅ | New skip decisions logged at INFO via each module's existing `logger = logging.getLogger(__name__)` (`core/runner.py`, `core/cli.py`); `pipeline.py` keeps its existing `print()`-for-progress convention, unchanged. |

**Constitution Check result**: all gates pass or are N/A.

## Project Structure

### Documentation (this feature)

```text
specs/046-research-only-mode/
├── plan.md
├── spec.md
└── tasks.md           (Phase 2 output)
```

### Source Code Changes

```text
core/runner.py                    MODIFY — add research_only: bool = False
                                   param to run_pipeline(); extract shared
                                   _minimal_brief(topic, seed_brief) helper
                                   used by both skip_cultural_strategist and
                                   research_only; when research_only=True,
                                   skip Cultural Strategist/Satirist/Image
                                   Generator/Image Evaluator entirely, always
                                   call generate_linkedin_post(...,
                                   branded=generate_linkedin_post) using the
                                   minimal brief, and pass its result to
                                   write_bundle as linkedin_post (branded) or
                                   research_report (neutral), never both.

agents/agent_linkedin_post.py     MODIFY — generate_linkedin_post() gains
                                   branded: bool = True; add _assemble_report()
                                   (neutral title fallback, no
                                   _CLOSING_BLOCK/_SECTION_4_BODY, keeps
                                   Pipeline Metrics line + _DISCLOSURE);
                                   _assemble_article() unchanged for
                                   branded=True callers; NOTIFICATION section
                                   still produced but left for the caller to
                                   discard when branded=False (FR-006).

core/bundle_writer.py             MODIFY — write_bundle() gains
                                   research_report: str | None = None;
                                   writes research_report.md when supplied
                                   and non-empty; independent of the existing
                                   linkedin_post param.

pipeline.py                       MODIFY — add --research-only flag; when
                                   set, build output_path as
                                   output/research/{slug}_{timestamp}.md
                                   (timestamp = datetime.now().strftime(
                                   "%Y%m%d_%H%M%S")) in every mode branch
                                   (manual, community-topic, community,
                                   default-random) instead of the existing
                                   image-based output_path; pass
                                   research_only=args.research_only to
                                   run_pipeline(); log INFO when --direct is
                                   also supplied (no-op, FR-011).

core/cli.py                       MODIFY — add --research-only flag; when
                                   set, use only infer_audiences(args.topic)[0]
                                   (skip _ensure_uk and the per-audience loop),
                                   build output_path the same
                                   output/research/{slug}_{timestamp}.md way,
                                   call run_pipeline() exactly once with
                                   research_only=True.

tests/test_pipeline.py            MODIFY — add coverage for
                                   run_pipeline()'s research_only branch:
                                   Cultural Strategist/Satirist/Image
                                   Generator/Image Evaluator never called;
                                   generate_linkedin_post always called with
                                   the minimal brief; branded value matches
                                   the generate_linkedin_post flag; correct
                                   bundle_writer kwarg (linkedin_post vs.
                                   research_report) populated for each case;
                                   --research-only CLI flag parsing and
                                   output_path construction; --direct-is-
                                   redundant INFO log.

tests/test_cli.py                 MODIFY — add coverage that --research-only
                                   on the gata CLI calls run_pipeline() exactly
                                   once (not once per inferred audience), using
                                   only the first inferred audience.

tests/test_agent_linkedin_post.py MODIFY — add coverage for branded=False:
                                   _assemble_report() output contains no Gata
                                   branding string, uses the neutral title
                                   fallback when TITLE is empty, includes
                                   Pipeline Metrics + disclosure, excludes
                                   _CLOSING_BLOCK/_SECTION_4_BODY content;
                                   branded=True path (existing behaviour)
                                   regression-checked unchanged.

tests/test_bundle_writer.py       MODIFY — add coverage that write_bundle()
                                   writes research_report.md when
                                   research_report is supplied, and that
                                   omitting it (None/"") writes nothing new;
                                   confirms it is independent of the existing
                                   linkedin_post param.
```

**Structure Decision**: The neutral/branded switch lives inside
`agent_linkedin_post.py` as a single parameter on the existing
`generate_linkedin_post()`, rather than as a second, duplicated
research-report module. Every stage before final assembly (research,
angle-planning, citation-numbered writing, domain filtering) is identical
regardless of branding — only the last step (which static template wraps the
writer panel's own sections) differs. This keeps Spec 042's expensive,
already-hardened panels completely untouched and avoids paying for two full
panel runs when both a branded and neutral output might otherwise seem
desirable.

The minimal-brief construction is extracted into `_minimal_brief()` rather
than left duplicated a second time in `run_pipeline()`, since `research_only`
needs exactly the same six-field literal `skip_cultural_strategist` already
builds — a small, non-speculative deduplication of code that now has two call
sites.

`output/research/` is a plain new subdirectory of the existing gitignored
`output/` tree (already true of `output/manual/`, `output/<community>/`) —
not a governed source directory under Constitution §8, so no amendment is
needed.

## Complexity Tracking

*No entries — no constitution violations.*
