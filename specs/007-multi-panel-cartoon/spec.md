# Feature Specification: Multi-Panel Cartoon Format

**Feature Branch**: `008-multi-panel-cartoon`
**Created**: 2026-06-11
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Produce a multi-panel horizontal comic strip (Priority: P1)

A content creator runs the pipeline with a named or free-text community and receives a single output image composed of 2–4 horizontally arranged panels (left-to-right), each panel containing a distinct scene and a caption beneath it. The joke is set up in the early panels and delivered in the final panel. The resulting image resembles the comic-strip format shown in the reference example.

**Why this priority**: Horizontal strips are the most recognisable comic format and the direct motivation for the feature. All other layout options build on this foundation.

**Independent Test**: Run `python pipeline.py --community uk-politics --panels 3 --layout horizontal` and verify the output image contains three distinct framed panels side-by-side with per-panel captions and a coherent three-beat joke.

**Acceptance Scenarios**:

1. **Given** a named community with no panel config, **When** `--panels 3 --layout horizontal` is passed, **Then** the output image contains exactly 3 horizontally arranged panels, each with a visible border, a scene, and a caption below it.
2. **Given** a 3-panel horizontal layout, **When** the image is inspected, **Then** the satirical concept spans all three panels as a progressive narrative (setup → escalation → punchline).
3. **Given** a panel count of 2, **When** the pipeline runs, **Then** the output image contains exactly 2 panels.
4. **Given** a panel count of 4, **When** the pipeline runs, **Then** the output image contains exactly 4 panels.

---

### User Story 2 — Produce a multi-panel vertical strip (Priority: P2)

A content creator runs the pipeline and receives a single output image composed of 2–4 vertically stacked panels (top-to-bottom), each panel containing a distinct scene and a caption. This format suits portrait-oriented distribution channels (e.g., Instagram stories, phone screens).

**Why this priority**: Vertical layout extends the same multi-panel capability to a second orientation, but is a secondary format; horizontal is the primary one.

**Independent Test**: Run `python pipeline.py --community uk-politics --panels 3 --layout vertical` and verify the output image contains three stacked panels with per-panel captions in a portrait orientation.

**Acceptance Scenarios**:

1. **Given** `--panels 3 --layout vertical` is passed, **When** the pipeline completes, **Then** the output image contains 3 vertically stacked panels, each framed and captioned.
2. **Given** a vertical layout, **When** the panels are inspected, **Then** reading order is top-to-bottom and the narrative beats follow that order.

---

### User Story 3 — Configure panel layout per community in communities.yaml (Priority: P2)

A pipeline operator adds `panels: 3` and `layout: horizontal` to a community entry in `communities.yaml`. From that point on, every run for that community produces a 3-panel strip without requiring CLI flags.

**Why this priority**: Community-level config avoids repetition for operators who always want a fixed format for a given audience; it also enables automation without extra flags.

**Independent Test**: Add `panels: 3` and `layout: horizontal` to the `uk-politics` entry in `communities.yaml`, run `python pipeline.py --community uk-politics` with no panel flags, and verify the output is a 3-panel strip.

**Acceptance Scenarios**:

1. **Given** a community entry with `panels: 3` and `layout: horizontal`, **When** the pipeline runs with no CLI panel flags, **Then** the output is a 3-panel horizontal strip.
2. **Given** a community with no panel config, **When** the pipeline runs with no CLI panel flags, **Then** the output is a single-panel image (existing behaviour, unchanged).
3. **Given** a CLI flag `--panels 2` and a community config of `panels: 3`, **When** the pipeline runs, **Then** the CLI flag takes precedence and the output has 2 panels.

---

### User Story 4 — Single-panel path remains fully functional (Priority: P1)

All existing commands and community configurations that do not specify a panel count continue to produce a single-panel image indistinguishable from the output before this feature was introduced. No existing user workflow breaks.

**Why this priority**: Backwards compatibility is non-negotiable; any regression here invalidates all existing communities and automation.

**Independent Test**: Run every existing community with no panel flags and compare output structure to pre-feature runs — same image dimensions, same folder layout, same bundle contents.

**Acceptance Scenarios**:

1. **Given** no `--panels` flag and no `panels` key in the community config, **When** the pipeline runs, **Then** the output is a single image identical in format to the pre-feature output.
2. **Given** `--panels 1` is passed explicitly, **When** the pipeline runs, **Then** the output is a single-panel image.
3. **Given** an existing `communities.yaml` with no panel fields, **When** loaded, **Then** the pipeline starts without errors or warnings about missing panel configuration.

---

### Edge Cases

- What happens when `--panels 1` is combined with `--layout horizontal`? → Treated as single-panel (layout direction is irrelevant for one panel).
- What happens when the satirist agent produces fewer narrative beats than the requested panel count? → The pipeline logs a warning and falls back to a single-panel image rather than producing an incomplete strip.
- What happens when the satirist agent produces more narrative beats than the requested panel count? → Only the first N beats are used; excess beats are discarded.
- What if the image generation model cannot produce a multi-panel layout in a single call? → Each panel is generated as a separate image and stitched together by the pipeline into one output file.
- What panel counts are valid? → 1 (default, single-panel), 2, 3, or 4. Requests outside this range are rejected with a clear error message before any API call is made.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST accept a `--panels` CLI flag (integer, 1–4) specifying the number of panels in the output image; default is 1.
- **FR-002**: The pipeline MUST accept a `--layout` CLI flag (`horizontal` or `vertical`) specifying the panel arrangement direction; default is `horizontal` when `--panels` > 1.
- **FR-003**: Communities in `communities.yaml` MAY include optional `panels` (integer, 1–4) and `layout` (`horizontal` or `vertical`) fields; when absent, the pipeline uses the CLI flag or the global default.
- **FR-004**: CLI flags MUST take precedence over community config values when both are present.
- **FR-005**: The satirist agent MUST receive the requested panel count as part of its input and MUST return a structured concept containing exactly that many panel descriptions, each with a distinct scene and a short caption.
- **FR-006**: Each panel description in the concept MUST represent one beat in a coherent narrative arc (setup, escalation, punchline, or equivalent story structure appropriate to the panel count).
- **FR-007**: The image generator MUST produce a single output file containing all panels, separated by visible borders, with per-panel captions rendered beneath each panel.
- **FR-008**: When panels > 1, the output folder name MUST reflect the community and topic as it does today; the file name MUST additionally encode the layout and panel count (e.g., `3h_` prefix for 3-panel horizontal).
- **FR-009**: When `--panels 1` is used (or no panel flag), the pipeline MUST follow the existing single-panel code path without modification.
- **FR-010**: Invalid `--panels` values (< 1 or > 4) MUST cause the pipeline to exit with code 1 and a descriptive error message before any API call.
- **FR-011**: A fallback to single-panel MUST occur (with a logged warning) if the satirist agent fails to produce the requested number of panel descriptions.

### Key Entities

- **PanelConcept**: A single panel's content — scene description, caption text, and its position in the narrative arc (e.g., "setup", "escalation", "punchline").
- **CartoonLayout**: The configuration for a multi-panel run — number of panels (1–4) and direction (horizontal or vertical).
- **MultiPanelConcept**: The full satirical concept for a multi-panel cartoon — an ordered list of PanelConcepts that form a coherent narrative, plus a global title/theme.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A 3-panel horizontal strip can be produced end-to-end in under 5 minutes (same order of magnitude as a single-panel run).
- **SC-002**: 100% of existing single-panel communities run without modification or error after this feature is deployed.
- **SC-003**: The satirist agent produces the correct number of panel beats (matching the requested panel count) in at least 90% of runs without fallback.
- **SC-004**: The output image for a multi-panel run is a single file containing all panels stitched in the correct order with visible separators and per-panel captions.
- **SC-005**: An operator can switch any community from single-panel to 3-panel by adding two lines to `communities.yaml` with no code changes.

## Assumptions

- The image generation model used (or the post-processing step) is capable of producing or stitching multiple panels into a single output file; if not, the pipeline handles stitching externally.
- Panel captions are short (1–2 sentences maximum) and are supplied by the satirist agent as part of the concept; they are not generated separately.
- The narrative arc structure is left to the satirist agent to determine — the pipeline only enforces that the correct number of distinct panels is produced.
- A "panel" is a rectangular framed region; styling (border thickness, caption font, spacing) follows the existing visual style of the cartoon and is not configurable in this version.
- Mobile/responsive rendering of the output image is out of scope; the output is a fixed-dimension PNG.
- The `--layout` flag defaults to `horizontal` when `--panels` > 1 and no layout is specified; there is no separate default for vertical.
