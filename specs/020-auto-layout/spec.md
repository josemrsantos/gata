# Feature Specification: Auto-Layout — Satirist Decides Panel Count and Direction

**Feature Branch**: `020-auto-layout`
**Created**: 2026-06-12
**Status**: Complete

## Problem

The pipeline required the caller to pass `--panels` and `--layout` flags to produce
multi-panel cartoons. This put a layout decision — which is a narrative question — in
the hands of the operator rather than the agent that understands the joke. Single-panel
was always the default because users didn't know when multi-panel would serve better.

## Goal

The Satirist chooses the panel count (1–4) and direction (horizontal/vertical) that best
fits the narrative, with no `--panels` or `--layout` flags required. CLI flags remain
available to override when the caller has a specific format in mind.

## Technical Design

### Unified JSON output format

The Satirist always returns the same JSON structure regardless of panel count:

```json
{
  "panels": 2,
  "layout": "horizontal",
  "content": [
    {"scene": "...", "caption": "...", "beat": "..."},
    {"scene": "...", "caption": "...", "beat": "..."}
  ]
}
```

For `panels=1`, `content[0].scene` contains the full image prompt including Gata's
character description. For `panels≥2`, scene is compact and the image generator adds
character/style details via `_build_multi_panel_prompt`.

### `_resolve_layout()` in `pipeline.py`

Returns `None` when no explicit override exists, signalling the Satirist to choose.
`Community.panels` defaults to `1` (same as "not set"), so only `panels > 1` counts as
an explicit override.

### `_parse_verdict()` in `agent_satirist.py`

Parses the JSON verdict, applies any `layout_override`, and returns both a
`CartoonConcept` and a `CartoonLayout`.

## Modified files

| File | Change |
|------|--------|
| `agents/agent_satirist.py` | Unified JSON format; `_parse_verdict()`; `layout_override` param |
| `pipeline.py` | `_resolve_layout()` returns None for auto; `_panel_filename_prefix()` |
| `agents/runner.py` | Receives `chosen_layout` from Satirist; passes to image generator |
| `tests/test_agent_satirist.py` | Update fixtures and assertions for new format |
| `tests/test_pipeline.py` | Update layout resolution tests |
