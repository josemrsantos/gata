# Implementation Plan: LinkedIn Feature Image Size Correction

**Branch**: `045-linkedin-feature-image-size` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/045-linkedin-feature-image-size/spec.md`

## Summary

Add an opt-in `target_size` parameter to `core/image_generation.py`'s
`ImageGeneration.generate()`. When supplied, it (1) hints Gemini toward the closest
aspect-ratio preset it actually supports, then (2) — regardless of what comes
back — centre-crops and resizes the result in Python (Pillow) to guarantee the
saved file is exactly that resolution before it's ever written to disk.

**Revision note**: the original plan wired `target_size` only into
`core/newsletter_merge.py`'s `generate_engagement_image()`, on the assumption that
`engagement_image.png` was the image LinkedIn covers actually come from. A real
end-to-end run of `pipeline.py --linkedin-post` (done for spec review) showed this
was wrong — the per-story `cartoon.png` is the image currently pasted into
LinkedIn, and it was explicitly out of scope in the original plan. This revision
adds a second, narrower call site: `core/runner.py`'s `run_pipeline()` now also
passes `target_size=(1200, 644)` down through `agents/agent_image_generator.py`,
but **only** when `generate_linkedin_post` is `True` and the chosen layout is
horizontal (covers the single-panel default and multi-panel horizontal; excludes
vertical multi-panel, which a landscape crop would mutilate). The
`engagement_image.png` wiring is kept as-is for when the multi-story merge flow
is actually used.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `google-genai` (`types.ImageConfig.aspect_ratio`, already
present in the installed SDK — confirmed via
`google.genai.types.ImageConfig.model_fields`), `PIL` (already in
`pyproject.toml`; no new dependency)
**Storage**: Files only — no change to what's read; `engagement_image.png` is
written at a corrected resolution instead of Gemini's raw output size
**Testing**: pytest with `unittest.mock` (no real API calls per Constitution §9);
crop/resize correctness tested directly against real (non-mocked) Pillow-generated
PNG bytes, since Pillow itself is not something to mock
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — additive extension to shared rendering code
**Performance Goals**: One extra in-process Pillow crop+resize per corrected
render (`engagement_image.png`, or a `--linkedin-post` cartoon in scope); no
additional network/API call
**Constraints**: ruff `line-length = 88`, `target-version = "py310"`; RULE 12 — a
cartoon generated without `--linkedin-post`, or with a vertical multi-panel
layout, must keep working byte-for-byte unchanged (default `target_size=None`)
**Scale/Scope**: 1 modified core module (`core/image_generation.py`), 3 modified
call sites (`core/newsletter_merge.py`, `agents/agent_image_generator.py`,
`core/runner.py`), 4 modified test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | No new SDK, no model change. Uses `google.genai.types.ImageConfig`, already part of the existing `google-genai` dependency — confirmed present in the installed version before use. |
| 2 | Image Output Rule | ✅ | Binary is still extracted from `response.candidates[0].content.parts[*].inline_data.data` unchanged; the crop/resize step runs on those bytes in memory before the existing atomic `tempfile.NamedTemporaryFile` + `os.replace()` write — that write pattern itself is untouched. |
| 3 | XML and Output Contract | ✅ N/A | This feature touches only image-resolution handling; no `<verdict>` block or inter-agent XML contract involved. |
| 4 | Character Rules | ✅ N/A | No image prompt text changes; `_GATA_CHARACTER` is untouched. |
| 5 | Visual Style Rules | ✅ N/A | No prompt content changes — the crop happens after generation, on the finished pixels, not the prompt. |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ N/A | No Satirist/FairParallelPanel involvement. |
| 7 | Language Rule | ✅ N/A | No text/caption content is touched. |
| 8 | Project Structure | ✅ | All changes stay inside `core/`, `agents/`, and `tests/`; no new top-level directory, no new package. |
| 9 | Testing Rules | ✅ | Tests added to `tests/test_image_generation.py` (crop/resize correctness, config wiring, target_size=None no-op), `tests/test_newsletter_merge.py` (engagement-image call-site wiring), `tests/test_agent_image_generator.py` (target_size pass-through), and `tests/test_pipeline.py` (gating condition: `--linkedin-post` × layout direction, on `run_pipeline()`'s call to `agent_image_generator.generate`); every new test function carries a RULE-3 one-sentence comment; the Gemini client remains fully mocked, only Pillow (a local library, not an API) operates on real bytes. |
| 10 | Secrets and Security | ✅ N/A | No new secret or credential. |
| 11 | Development Stages | ✅ | Work moved to branch `045-linkedin-feature-image-size` before this revision's implementation began; will merge via PR. |
| 12 | Code Quality | ✅ | `ruff check --no-cache` and `ruff format --check --no-cache` will be run on every modified file before this is considered done. |
| 13 | Logging | ✅ | The crop/resize correction logs at INFO (ratio correction and resize events) via the existing `logger = logging.getLogger(__name__)` in `core/image_generation.py`; no `print()`. |

**Constitution Check result**: all gates pass or are N/A.

## Project Structure

### Documentation (this feature)

```text
specs/045-linkedin-feature-image-size/
├── plan.md
└── spec.md
```

### Source Code Changes

```text
core/image_generation.py          MODIFY — add LINKEDIN_FEATURE_IMAGE_SIZE
                                   constant, _closest_gemini_aspect_ratio() and
                                   _fit_to_target_size() helpers, and an opt-in
                                   target_size param on
                                   ImageGeneration.generate() that applies both.
                                   (Unchanged from the original plan.)
core/newsletter_merge.py          MODIFY — generate_engagement_image() passes
                                   target_size=LINKEDIN_FEATURE_IMAGE_SIZE.
                                   (Unchanged from the original plan.)
agents/agent_image_generator.py   MODIFY — generate() accepts an opt-in
                                   target_size: tuple[int, int] | None = None
                                   parameter and passes it straight through to
                                   ImageGeneration.generate().
core/runner.py                    MODIFY — run_pipeline()'s call to
                                   agent_image_generator.generate() passes
                                   target_size=(1200, 644) when
                                   generate_linkedin_post is True AND
                                   chosen_layout.direction == "horizontal";
                                   omitted (None) otherwise.
tests/test_image_generation.py    MODIFY — add coverage for the closest-preset
                                   helper, the crop/resize helper (wide source,
                                   square source, already-correct source), and
                                   generate()'s target_size wiring (both the
                                   Gemini config hint and the on-disk result),
                                   plus a default-path (target_size=None)
                                   regression guard.
tests/test_newsletter_merge.py    MODIFY — add coverage that
                                   generate_engagement_image() calls
                                   ImageGeneration.generate() with
                                   target_size=(1200, 644).
tests/test_agent_image_generator.py MODIFY — add coverage that generate()
                                   passes a supplied target_size through to
                                   ImageGeneration.generate() unchanged, and
                                   that omitting it keeps target_size=None.
tests/test_pipeline.py            MODIFY — add coverage for run_pipeline()'s
                                   gating condition on its
                                   core.runner.agent_image_generator.generate
                                   call: (linkedin_post=True, horizontal) →
                                   target_size=(1200, 644); (linkedin_post=True,
                                   vertical) → target_size=None;
                                   (linkedin_post=False, horizontal) →
                                   target_size=None.
```

**Structure Decision**: Extend the existing shared `ImageGeneration.generate()`
rather than adding a second rendering function or a post-hoc resize step outside
it, because (a) the class's own docstring already documents it as the single
shared rendering core for both the per-story and engagement-image paths, and (b)
correcting the image before the atomic write (rather than after, as a separate
file-mutation step) means a partially-corrected or inconsistent file can never
land on disk — consistent with Constitution §2's atomic-write guarantee.

The `target_size` parameter stays opt-in (`None` default) at every layer so a
cartoon generated without `--linkedin-post`, or with a vertical layout, is
provably unchanged. The original plan additionally kept `agent_image_generator.py`
and `core/runner.py` completely unaware of `target_size`, reasoning that coupling
the rendering module to a run-level flag (`generate_linkedin_post`) was avoidable
complexity. That reasoning is reversed in this revision: the flag-and-layout
gating condition is inherent to *which* image needs correcting (a `--linkedin-post`
cartoon is a LinkedIn cover; a vertical multi-panel one is not croppable to
landscape at all) — there is no way to express "correct this image because it is
about to become a LinkedIn cover" without a caller that knows both facts. The
gating logic lives at the one call site in `run_pipeline()` that already holds
both `generate_linkedin_post` and `chosen_layout`, rather than being pushed down
into `agent_image_generator.py` (which would need `generate_linkedin_post` piped
in as a new parameter it has no other use for) or into `ImageGeneration.generate()`
itself (which must stay a generic, target-size-only renderer per Constitution's
single-responsibility precedent for this class).

## Complexity Tracking

*No entries — the §11 Development Stages gap from the original plan draft is
resolved (branch created before this revision's implementation).*
