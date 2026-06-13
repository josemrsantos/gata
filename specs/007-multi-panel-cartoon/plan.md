# Implementation Plan: Multi-Panel Cartoon Format

**Branch**: `008-multi-panel-cartoon` | **Date**: 2026-06-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/007-multi-panel-cartoon/spec.md`

## Summary

Add 2–4 panel comic-strip output to the existing single-panel cartoon pipeline. The satirist agent receives a `CartoonLayout` describing panel count and direction, returns a structured `MultiPanelConcept` with one `PanelConcept` per panel inside `<verdict>` tags, and the image generator assembles a single image prompt describing the full strip layout. The single-panel path (panels=1) remains entirely unchanged.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `google-genai` (Gemini SDK), `anthropic` (Claude SDK), `Pillow` (PIL — image stitching fallback, declared but MVP uses single-call), `pytest`, `pyyaml`, `python-dotenv`, `ruff`
**Storage**: Files — PNG output in `output/`, YAML community config in `communities.yaml`
**Testing**: pytest with mocks (no real API calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — additive extension
**Performance Goals**: Multi-panel run completes in same order of magnitude as single-panel (~2–5 min, SC-001)
**Constraints**: ruff `line-length=88`; single-panel backwards compatibility non-negotiable (SC-002); `--panels` valid range 1–4 (FR-010)
**Scale/Scope**: Small community set; 2–4 panels per run; no concurrency

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | `gemini-3.1-flash-image-preview` for images, `claude-sonnet-4-6` for Claude, `from google import genai` |
| 2 | Image Output Rule | ✅ | Binary extraction pattern unchanged; same `inline_data.data` path |
| 3 | XML Contract | ⚠️ VIOLATION | `<verdict>` content schema changes to JSON for multi-panel. Justified — see Complexity Tracking |
| 4 | Character Rules | ✅ | Gata description appears verbatim in the image prompt for every multi-panel run |
| 5 | Visual Style Rules | ⚠️ VIOLATION | Style descriptor says "single-panel satirical cartoon"; multi-panel needs "N-panel comic strip". Justified — see Complexity Tracking |
| 6 | Dual-Persona Iteration Rules | ✅ | Same 5-iteration max; Critic evaluates the full narrative arc as a unit |
| 7 | Language Rule | ✅ | Language applies to all panel captions and board text across all panels |
| 8 | Project Structure | ✅ | Additive changes only; no new top-level directories |
| 9 | Testing Rules | ✅ | Tests written before implementation; mocks for all SDK calls |
| 10 | Secrets and Security | ✅ | No changes to key handling |
| 11 | Development Stages | ✅ | This is Stage 9; Stage 8 (free-text community) is complete and merged |
| 12 | Code Quality | ✅ | ruff must pass before any task is marked complete |
| 13 | Logging | ✅ | logging module throughout; no bare print() in agent code |

## Project Structure

### Documentation (this feature)

```text
specs/007-multi-panel-cartoon/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli.md           # CLI flag contracts
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
agents/
├── types.py                       # ADD PanelConcept, CartoonLayout; EXTEND CartoonConcept + Community
├── agent_satirist.py              # EXTEND: multi-panel prompt template + verdict JSON parsing
├── agent_image_generator.py       # EXTEND: multi-panel image prompt assembly
└── config_loader.py               # EXTEND: load optional panels/layout fields from community YAML

pipeline.py                        # ADD --panels, --layout flags; CartoonLayout plumbing

communities.yaml                   # EXTEND schema: optional panels (int) and layout (str) per entry

tests/
├── test_agent_satirist.py         # ADD: multi-panel prompt shape, JSON verdict parsing, fallback
├── test_agent_image_generator.py  # ADD: multi-panel image prompt assembly tests
├── test_config_loader.py          # ADD: panels/layout loading and defaults tests
└── test_pipeline.py               # ADD: --panels/--layout flag + precedence + exit-1 tests
```

**Structure Decision**: Option 1 (single project). All changes are additive to existing modules. No new agent files or top-level directories needed.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| §3 XML Contract — `<verdict>` content changes to JSON for multi-panel | The satirist must return N structured panel descriptions (scene + caption + beat) that the image generator can iterate over deterministically. Plain text cannot carry this structure reliably. | Free-text panel descriptions inside `<verdict>` would require brittle regex parsing and cannot guarantee exact panel count. Single-panel `<verdict>` content is unchanged — only multi-panel mode uses JSON. |
| §5 Visual Style — "single-panel" descriptor changes for multi-panel runs | The image model must be told the panel count and direction to compose the correct layout. Using "single-panel" for a 3-panel strip produces wrong output. | Adding a separate override variable would duplicate the style rule and create divergence. The single-panel path keeps the existing descriptor unchanged. Multi-panel mode substitutes the descriptor only for that run. |
