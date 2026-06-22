# Feature Specification: Cartoon Title

**Spec**: `027-cartoon-title`
**Created**: 2026-06-21
**Status**: Draft

## Problem

Generated cartoons are self-contained images but carry no headline. The filename
(a sanitised topic slug) is technical, not editorial. A reader encountering the
image without surrounding context has no immediate anchor for the satirical angle.

## Goal

Each cartoon carries a punchy, Satirist-authored title rendered as a dark banner
at the very top of the image. The title is the satirist's own framing of the joke
— not a description, not the raw topic string.

`--no-title` suppresses the overlay in both `gata` and `pipeline.py` (default: on).

## Design

### 1. Satirist JSON — new `"title"` field

`_OUTPUT_FORMAT_RULES` in `agents/agent_satirist.py` gains one line:

```
"title": "<punchy 3–8 word headline in the output language>",
```

The title rules (injected into every panelist's system prompt):
- 3–8 words
- In the output language (matches captions)
- Captures the satirical angle, not just the topic
- NOT a description of the image — an editorial headline

### 2. `CartoonConcept` — new `title` field

```python
@dataclass
class CartoonConcept:
    full_text: str
    image_prompt: str
    iteration: int
    panels: list[PanelConcept] | None = None
    title: str = ""          # NEW — populated by _parse_verdict
```

### 3. `_parse_verdict` — extract title

```python
title = str(parsed.get("title", ""))
```

Passed into every `CartoonConcept(...)` constructor call inside `_parse_verdict`.
Fallback path (JSON parse failure) leaves `title=""`.

### 4. `agent_satirist.run()` — topic fallback

After `_parse_verdict`, if `concept.title` is empty, set `concept.title = topic`.
This covers the JSON-parse-failure fallback and any panelist that omits the field.

### 5. `agent_image_generator` — title overlay

New helper:

```python
def _overlay_title(image_path: str, title: str) -> None:
```

Uses Pillow (`pillow` added to project dependencies) to:
1. Open the generated PNG and convert to RGB
2. Create a new canvas: dark banner (`#1a1a1a`) on top + original image below
3. Center white title text in the banner (font size proportional to banner height)
4. Save back to `image_path`

Banner height: `max(50, int(image_height * 0.08))` — minimum 50 px; scales with image.

`generate()` gains a `show_title: bool = True` parameter. After a successful image
write, if `show_title and concept.title`, it calls `_overlay_title`.

### 6. `core/runner.py` — thread `show_title` through

`run_pipeline()` gains `show_title: bool = True`, forwarded to
`agent_image_generator.generate()`.

### 7. `pipeline.py` and `core/cli.py` — `--no-title` flag

```
--no-title    suppress title overlay on generated images (default: title shown)
```

`show_title = not args.no_title` passed to `run_pipeline()`.

## What does NOT change

- `DualPersonaLoop`, `ParallelPanel`, `ConversationProtocol` — untouched
- `bundle_writer`, `agent_image_evaluator`, `agent_cultural_strategist` — untouched
- `communities.yaml`, `humor.yaml` — no new config fields
- The public manual-invocation interface is preserved (RULE 12)

## Tests

`tests/test_agent_satirist.py` additions:
- Title extracted from verdict JSON → `CartoonConcept.title` populated
- Missing title in JSON → `CartoonConcept.title` is `""`
- `run()` with empty title → falls back to topic string

`tests/test_agent_image_generator.py` additions:
- `_overlay_title` expands image height and preserves width
- `_overlay_title` with empty title is not called (guard in `generate()`)
- `generate()` calls `_overlay_title` when `show_title=True` and title non-empty
- `generate()` skips `_overlay_title` when `show_title=False`
- `generate()` skips `_overlay_title` when `concept.title` is empty

## Verification

- `pytest tests/` — all tests pass
- `python pipeline.py --topic "..." --audience "..." --language "..." --tone "..."` runs end-to-end
- Generated PNG has a dark title banner visible at the top
- `--no-title` flag produces an image with no banner
