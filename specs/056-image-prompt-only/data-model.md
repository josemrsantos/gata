# Data Model: Image-prompt-only mode

No database or schema changes. New values and one new file:

## Image request (string)

The exact text sent to the image model for one cartoon.
- Source: `build_image_request(concept, layout)`.
- Multi-panel (`concept.panels` present and a layout): header + per-panel blocks + Gata
  character section + visual style section (as today).
- Otherwise: `concept.image_prompt`, verbatim (as today).
- Validation: none added; a missing verbatim Gata paragraph produces a warning, not an error.

## Manual-use header (string)

| Line | Value |
|------|-------|
| Title | `concept.title`, or "none" |
| Title banner | "not part of the request"; notes "this run would have shown a banner" / "no banner (--no-title)" |
| Size | `WxH, aspect ratio R` when `target_size` is pinned (R = closest Gemini preset), else "no size pinned" |
| Crop | "final crop/resize not applied" |

## Prompt file (`image_prompt.txt`)

```
<manual-use header>
===== PASTE EVERYTHING BELOW THIS LINE INTO GEMINI =====
<image request>
```

- Location: `<bundle_dir>/image_prompt.txt` (bundle dir = `Path(output_path).parent / Path(output_path).stem`, same as every other bundle file).
- One per audience / per run. Overwritten if present.
- Written only when `--image-prompt-only` is set and a concept exists.

## New parameters

| Name | Type | Default | Where |
|------|------|---------|-------|
| `image_prompt_only` | bool | False | `run_pipeline()` |
| `image_prompt_file` | str or None | None | `write_bundle()` |

## Unchanged

`CartoonConcept`, `CartoonLayout`, `RunTelemetry`, `prompt_card.txt` content and writing.
