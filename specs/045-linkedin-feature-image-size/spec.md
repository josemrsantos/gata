# Feature Specification: LinkedIn Feature Image Size Correction

**Spec**: `045-linkedin-feature-image-size`
**Created**: 2026-08-28
**Status**: Draft

## Problem

Two images end up as a LinkedIn Article/Newsletter cover, and both are rendered by
`core/image_generation.py`'s `ImageGeneration.generate()` with no resolution or
aspect-ratio request to Gemini at all:

1. `engagement_image.png` — the header image for a merged multi-story newsletter
   edition (Spec 041, `core/newsletter_merge.py`).
2. `cartoon.png` — the per-story image, when the operator runs `pipeline.py
   --linkedin-post` for a single story (Spec 042). **This is the image path
   actually in current use**: an operator running `--linkedin-post` today pastes
   this cartoon into LinkedIn as the article's cover, not `engagement_image.png`.

In practice Gemini returns 1408x768 (ratio 1.833:1) or similar. LinkedIn's
documented Article/Newsletter cover spec is 1200x644 (ratio ~1.91:1). Because the
saved file doesn't match what LinkedIn expects, LinkedIn auto-crops it on upload,
clipping parts of the image the operator never intended to lose.

The per-story cartoon path also supports multi-panel **vertical** layouts
(`CartoonLayout.direction == "vertical"`, per Constitution §6) — force-cropping
one of those to a landscape 1.91:1 would mutilate it, so the cartoon-side fix must
not apply there.

## Goal

- `engagement_image.png` is always saved at exactly 1200x644px, regardless of what
  resolution/ratio the underlying Gemini call actually returns.
- `cartoon.png` is also saved at exactly 1200x644px whenever it is generated in a
  `--linkedin-post` run **and** its layout is single-panel or horizontal
  (`CartoonLayout.direction == "horizontal"`, the default). A vertical multi-panel
  cartoon, or any cartoon generated without `--linkedin-post`, is left exactly as
  it is today.
- In both cases, LinkedIn's own auto-crop never runs on the saved file, so nothing
  the operator sees in the generated image is clipped after upload.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — LinkedIn-post cartoon matches LinkedIn's spec exactly (Priority: P1)

The operator runs `pipeline.py --topic ... --linkedin-post` for a single story.
The resulting `cartoon.png` — the image the operator actually pastes into
LinkedIn's Article cover slot today — is exactly 1200x644px and needs no further
cropping.

**Why this priority**: This is the image path in current, real-world use for
publishing to LinkedIn; it is the actual bug being fixed, not a theoretical one.

**Independent Test**:
```
python -c "from PIL import Image; im = Image.open('<output_dir>/<topic>.png'); assert im.size == (1200, 644)"
```

**Acceptance Scenarios**:

1. **Given** `--linkedin-post` is set and the chosen layout is single-panel
   (the default) or multi-panel horizontal, **When** the cartoon is generated,
   **Then** the file saved to disk is exactly 1200x644px.
2. **Given** `--linkedin-post` is set but the chosen layout is multi-panel
   **vertical**, **When** the cartoon is generated, **Then** the file is saved
   at its normal resolution, untouched — forcing a landscape crop would mutilate
   a vertical composition.
3. **Given** `--linkedin-post` is NOT set, **When** the cartoon is generated,
   **Then** the file is saved at its normal resolution, untouched — this feature
   only applies to images headed to LinkedIn.

---

### User Story 2 — Edition cover matches LinkedIn's spec exactly (Priority: P2)

The operator runs `newsletter_merge.py` on a merged multi-story edition. The
resulting `engagement_image.png` is exactly 1200x644px and can be uploaded as a
LinkedIn Article/Newsletter cover with no further cropping needed.

**Why this priority**: Lower priority than User Story 1 because this path isn't
in active use yet, but the same correction is cheap to keep in place for when
multi-story editions are published this way.

**Independent Test**:
```
python -c "from PIL import Image; im = Image.open('<edition>/engagement_image.png'); assert im.size == (1200, 644)"
```

**Acceptance Scenarios**:

1. **Given** Gemini returns its native default resolution (1408x768, ratio
   1.833:1), **When** the engagement image is generated, **Then** the file saved
   to disk is exactly 1200x644px.
2. **Given** Gemini returns some other resolution or ratio (e.g. a square image),
   **When** the engagement image is generated, **Then** the file saved to disk is
   still exactly 1200x644px, cropped rather than stretched/squeezed so the subject
   isn't distorted.
3. **Given** Gemini happens to return exactly 1200x644px already, **When** the
   engagement image is generated, **Then** the file is saved unchanged at that
   size (no redundant crop/resize drift).

---

### Edge Cases

- Gemini returns an image smaller than 1200x644 in one dimension after cropping to
  the target ratio → still resized up to exactly 1200x644 (Pillow LANCZOS); no
  special-cased rejection, since Gemini's image models do not return anything
  that small in practice.
- Every model in the existing `_MODELS` fallback chain fails → unchanged existing
  behaviour (`RuntimeError`, no file written); this feature does not touch that
  path.
- The Image Evaluator's regenerate-on-REJECTED retry loop (`core/runner.py`,
  `_MAX_IMAGE_RETRIES`) calls `agent_image_generator.generate()` again on each
  retry — the `target_size` gating condition (`--linkedin-post` + horizontal
  layout) is re-evaluated identically on every retry, so a rejected-and-retried
  cartoon still ends up corrected the same way as the first attempt.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `ImageGeneration.generate()` MUST accept an optional `target_size:
  tuple[int, int] | None` parameter, defaulting to `None`.
- **FR-002**: When `target_size` is supplied, the Gemini `generate_content` call
  MUST pass an `image_config.aspect_ratio` hint set to whichever of Gemini's fixed
  supported presets (`1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `9:16`, `16:9`, `21:9` —
  confirmed via the installed `google-genai` SDK's `types.ImageConfig` schema, no
  arbitrary ratio is accepted) is numerically closest to `target_size`'s ratio.
  This is a best-effort steering hint only — FR-003 is what actually guarantees
  the output, since no preset equals 1200:644 exactly.
- **FR-003**: Before the image is written to disk, if `target_size` is supplied,
  the actual returned image MUST be checked in Python (Pillow) and corrected:
  - If its aspect ratio differs from `target_size`'s ratio by more than a small
    tolerance, it MUST be centre-cropped to that ratio first (never stretched).
  - The (possibly cropped) image MUST then be resized to exactly `target_size`
    if it is not already that exact size.
- **FR-004**: `core/newsletter_merge.py`'s `generate_engagement_image()` MUST call
  `ImageGeneration.generate()` with `target_size=(1200, 644)`.
- **FR-005**: `agents/agent_image_generator.py`'s `generate()` MUST accept an
  optional `target_size: tuple[int, int] | None` parameter and pass it straight
  through to `ImageGeneration.generate()`.
- **FR-006**: `core/runner.py`'s `run_pipeline()` MUST call
  `agent_image_generator.generate()` with `target_size=(1200, 644)` when, and only
  when, both of the following hold for that call:
  - `generate_linkedin_post` is `True` (the run requested `--linkedin-post`), AND
  - `chosen_layout.direction == "horizontal"` (covers both the default
    single-panel case and multi-panel horizontal; excludes vertical multi-panel).
  Otherwise it MUST call `agent_image_generator.generate()` exactly as today
  (`target_size` omitted / `None`), leaving the cartoon at its normal resolution.
- **FR-007**: No other caller of `ImageGeneration.generate()` or
  `agent_image_generator.generate()` changes behaviour — both `target_size`
  parameters default to `None`.

### Key Entities

- **target_size**: an explicit `(width, height)` pixel tuple a caller of
  `ImageGeneration.generate()` (or, one level up, `agent_image_generator.generate()`)
  opts into; when present, guarantees the saved file is exactly that resolution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `engagement_image.png` is 1200x644px on every run, verified by an
  automated test that feeds `_fit_to_target_size` a non-matching source
  resolution and asserts the output size.
- **SC-002**: `cartoon.png` is 1200x644px on every `--linkedin-post` run whose
  chosen layout is single-panel or horizontal, verified by an automated test on
  `run_pipeline()`'s call to `agent_image_generator.generate()`.
- **SC-003**: A `--linkedin-post` run with a vertical multi-panel layout, and any
  run without `--linkedin-post`, leaves `cartoon.png` at its normal resolution —
  verified by automated tests asserting `target_size=None` reaches
  `agent_image_generator.generate()` in both cases.
- **SC-004**: The existing per-story cartoon test suite
  (`tests/test_image_generation.py`'s pre-existing cases,
  `tests/test_agent_image_generator.py`'s pre-existing cases) passes unchanged —
  this feature adds behaviour, it does not alter the default path.

## What does NOT change

- A vertical multi-panel cartoon (`CartoonLayout.direction == "vertical"`, per
  Constitution §6) is never forced to 1200x644 by this feature, in or out of a
  `--linkedin-post` run — force-cropping it to a landscape 1.91:1 would silently
  mutilate the composition.
- A cartoon generated without `--linkedin-post` keeps its current resolution
  unchanged — this feature only corrects images that are actually headed to
  LinkedIn.
- Gemini model fallback chain (`_MODELS`), title-overlay behaviour
  (`_overlay_title`), and telemetry/cost recording are unchanged.

## Assumptions

- LinkedIn's documented Article/Newsletter cover spec (1200x644px, ~1.91:1) is
  the correct target — confirmed via web search against current (2026)
  third-party LinkedIn image-size guides, since LinkedIn does not appear to
  publish this as a single canonical first-party page.
- A centre crop (rather than e.g. a smart/content-aware crop) is an acceptable
  correction strategy — Gemini's own composition already tends to keep the
  subject centred, and no existing agent in this codebase does content-aware
  cropping.
