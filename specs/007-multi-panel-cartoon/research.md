# Research: Multi-Panel Cartoon Format

**Feature**: specs/007-multi-panel-cartoon/
**Phase**: 0 — Pre-Design Research
**Date**: 2026-06-11

## Decision Log

### D-001: Single-call vs. per-panel image generation

**Decision**: Use a single `gemini-3.1-flash-image-preview` call with a composite image prompt that describes the full comic strip — all panels, their layout direction, scenes, and captions — in one structured prompt.

**Rationale**: Minimises API calls and latency; produces visually consistent styling across panels; the spec's FR-007 says "produce a single output file containing all panels, separated by visible borders, with per-panel captions rendered beneath each panel" — a single-call approach satisfies this directly without post-processing.

**Alternatives considered**:
- Per-panel calls + Pillow stitch: More reliable panel count guarantee but higher latency, more API quota, and visual inconsistency between panels.
- Multiple images in one call: Not supported by the current Gemini SDK `inline_data` response format.

**Fallback** (FR-011): If the model produces an image that cannot be verified to contain the expected panels, log `WARNING` and fall back to single-panel output. The stitch path (Pillow) is deferred post-MVP.

---

### D-002: `<verdict>` content schema for multi-panel

**Decision**: For multi-panel mode the Satirist wraps a JSON object inside `<verdict>`:

```json
{
  "panels": [
    {"scene": "...", "caption": "...", "beat": "setup"},
    {"scene": "...", "caption": "...", "beat": "escalation"},
    {"scene": "...", "caption": "...", "beat": "punchline"}
  ]
}
```

For single-panel mode `<verdict>` continues to contain plain text (the image prompt string) — unchanged.

**Rationale**: Structured JSON enables deterministic parsing of N panel descriptions. The `<verdict>` XML wrapper is preserved, satisfying Constitution §3's regex contract. The schema is minimal (3 keys per panel) and maps directly to `PanelConcept` fields.

**Alternatives considered**:
- XML sub-tags inside `<verdict>` (`<panel1>`, `<panel2>`): More verbose; parsing variable counts requires non-trivial regex.
- Plain text with separator lines: Unreliable — the model produces inconsistent separators across runs.

**Parsing logic**: `json.loads(verdict_content.strip())` → validate `panels` is a list with length == requested count. If parse fails or length mismatches, log `WARNING` and fall back to single-panel (FR-011).

---

### D-003: `CartoonConcept` extension strategy

**Decision**: Add an optional `panels: list[PanelConcept] | None = None` field to the existing `CartoonConcept` dataclass. When `panels` is `None` (the default), the single-panel path runs unchanged. When `panels` is populated, the multi-panel path runs.

**Rationale**: Backwards compatible — every existing call site that never sets `panels` continues to work without modification. No new class or changed import needed at sites that don't use multi-panel.

**Invariant**: For a given `CartoonConcept` instance exactly one of `image_prompt` (non-empty) or `panels` (non-None) is set. The image generator uses `panels is not None` as the branch condition.

---

### D-004: `CartoonLayout` — placement and flow

**Decision**: `CartoonLayout` is created in `pipeline.py` from CLI flags and/or community config, then passed as a keyword argument to `agent_satirist.run(layout=layout)` and `agent_image_generator.generate(layout=layout)`.

**Source precedence** (FR-004: CLI takes precedence):
1. CLI `--panels` / `--layout` — highest priority when provided
2. Community `panels` / `layout` fields from `communities.yaml`
3. Global defaults: `panels=1`, `direction="horizontal"`

**Rationale**: Keeps both agents stateless with respect to layout. The layout is fully resolved before any agent call, so both agents can use it without coupling to each other.

---

### D-005: Satirist prompt extension for multi-panel

**Decision**: When `layout.panels > 1`, the TASK section of the satirist system prompt is replaced with:

```
TASK: Given a news topic, generate a satirical {N}-panel {direction} comic strip concept featuring Gata.
Return ONLY a JSON object inside the <verdict> tags with a "panels" key containing an array of exactly {N} panel objects.
Each panel object MUST have three keys: "scene" (full scene description for this panel, including all relevant visual details),
"caption" (1–2 sentence caption in the output language), and "beat" (narrative position — e.g. "setup", "escalation",
"punchline" for 3 panels; adapt labels for other panel counts).
The Gata character description and visual style rules MUST be embedded in the scene description of each panel.
```

The `<joke_explanation>` tag remains required and is appended after `</verdict>` as today.

**Rationale**: Explicit instruction for JSON output format with exact field names avoids ambiguity. Requiring the model to name the beat enforces FR-006 (coherent narrative arc) without pipeline-side narrative quality validation.

---

### D-006: Output filename encoding (FR-008)

**Decision**: For multi-panel runs, prepend `{N}{d}_` to the standard filename slug, where `N` is the panel count and `d` is `h` (horizontal) or `v` (vertical). Example: `3h_english_ai_hype_reaches_peak.png`.

Single-panel filenames are unchanged — no prefix added (FR-008 applies only when `panels > 1`).

---

### D-007: Pillow dependency

**Decision**: Declare `Pillow` in `pyproject.toml` but defer the stitch implementation post-MVP. The fallback path (FR-011) logs a WARNING and falls back to single-panel rather than stitching, so Pillow is not exercised in the MVP. It is declared now so future work can use it without a dependency PR.

---

### D-008: Community dataclass fields

**Decision**: Add `panels: int = 1` and `layout: str = "horizontal"` to the `Community` dataclass in `agents/types.py`. Both have defaults, so existing `communities.yaml` files that omit these fields continue to load without errors (SC-002, US4 AC3).

`config_loader.py` reads them with `community_data.get("panels", 1)` and `community_data.get("layout", "horizontal")`.

---

### D-009: Constitution §3 compliance for multi-panel JSON in `<verdict>`

**Clarification**: Constitution §3 says "If any required tag is missing or malformed, the pipeline MUST retry — not skip or guess." This applies to the `<verdict>` XML tag being absent from the response. When `<verdict>` is present but its JSON content is malformed or has the wrong panel count, that is a content-level failure — the spec's FR-011 explicitly defines the response as "log a warning and fall back to single-panel". These two rules govern different failure modes and are not contradictory.
