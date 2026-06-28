# Spec 035 — Direct Satirist Mode

**Stage**: 035
**Branch**: `035-direct-satirist-mode`
**Status**: Draft — awaiting approval
**Dependency**: none

---

## Problem

The Cultural Strategist adds cultural framing, audience-specific references, and mood
context before handing off to the Satirist. This enrichment is valuable for community-
driven topics, but it also introduces creative drift: the Satirist receives a curated
angle rather than working directly from the raw topic.

Developers who already know the satirical angle they want — or who want to test the
Satirist in isolation — have no way to skip the Cultural Strategist without editing
source code.

---

## Goal

Add a `--direct` flag to `pipeline.py` that bypasses the Cultural Strategist entirely.
The Satirist receives a minimal `EnrichedBrief` built from the topic and seed brief
(audience, language, tone) with no additional cultural framing. Everything downstream
(Satirist, Image Generator, Evaluator) runs unchanged.

---

## Behaviour

### Normal mode (unchanged)

```
topic → Cultural Strategist → EnrichedBrief → Satirist → Image Generator
```

### Direct mode (`--direct`)

```
topic → minimal EnrichedBrief → Satirist → Image Generator
```

The minimal `EnrichedBrief` is constructed as:

| Field | Value |
|-------|-------|
| `target_audience` | from `seed_brief.target_audience` |
| `output_language` | from `seed_brief.output_language` |
| `tone` | from `seed_brief.tone` |
| `cultural_angle` | the topic string verbatim |
| `culturally_loaded_references` | `[]` (empty) |
| `joke_type` | `""` (default) |

The Cultural Strategist agent is not called; its telemetry entry is absent from the
summary. The pipeline log line `"Cultural Strategist..."` is replaced by
`"Direct mode — skipping Cultural Strategist"`.

---

## CLI

Available in both entry points:

```
# developer pipeline
python pipeline.py --topic "..." --community uk --direct
python pipeline.py --topic "..." --audience "UK public" --language English --direct

# installed gata CLI
gata "..." --direct
gata "..." --direct --html
```

`--direct` is compatible with all existing flags. It has no effect on community
selection, audience inference, layout, HTML output, or any other option.

---

## Files Changed

| File | Change |
|------|--------|
| `core/runner.py` | ADD `skip_cultural_strategist: bool = False` to `run_pipeline()`; build minimal brief and skip Cultural Strategist when `True` |
| `pipeline.py` | ADD `--direct` flag; pass `skip_cultural_strategist` to `run_pipeline()` |
| `core/cli.py` | ADD `--direct` flag; pass `skip_cultural_strategist` to `run_pipeline()` |
| `core/__version__.py` | Bump to `1.18.0` |
| `tests/test_pipeline.py` | ADD tests for `--direct` flag behaviour |

## Files NOT Changed

- `agents/agent_cultural_strategist.py` — unchanged
- `agents/agent_satirist.py` — unchanged; receives `EnrichedBrief` as before
- `core/types.py` — `EnrichedBrief` unchanged
- All other agents and tests — unchanged

---

## Success Criteria

1. `python pipeline.py --topic "…" --community uk --direct` runs end-to-end and produces an image
2. Log does NOT show `"Cultural Strategist..."` progress line; shows `"Direct mode"` instead
3. Summary does NOT include a Cultural Strategist telemetry row
4. `python -m pytest tests/` — zero failures
5. `ruff check . && ruff format .` — exit 0
