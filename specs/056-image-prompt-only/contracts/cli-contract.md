# CLI Contract: `--image-prompt-only`

## Flag

`--image-prompt-only` — boolean, default off, on both `gata` and `python pipeline.py`.
Help text: "run every stage except image creation and evaluation; write the full image
request to image_prompt.txt in the output bundle for pasting into Gemini by hand".

## Behaviour

| Situation | Result |
|-----------|--------|
| Flag absent | Exactly as today |
| Flag present | No image model call, no Image Evaluator call; all other stages and bundle files as normal; `image_prompt.txt` added |
| Several audiences (`gata --audience A --audience B`) | One `image_prompt.txt` per audience bundle; one message each |
| `--research-only` also given | Flag ignored; `WARNING` says so; research output as today |
| `--linkedin-post` (horizontal) | Header states `1200x644` and its aspect ratio |
| `--no-title` | Header says no banner would have been applied |
| Request lacks the Gata paragraph | File still written; `WARNING` on screen |
| Image-dependent outputs | None exist today, so nothing extra is skipped |

## Terminal message (per cartoon, after the bundle is written)

```
No image was auto-generated (--image-prompt-only).
Generate it manually: give this file to Gemini as the prompt:
  <path to bundle>/image_prompt.txt
```

## File contract (`image_prompt.txt`)

1. A manual-use header (title, banner note, size/aspect ratio or "none pinned", crop note).
2. The separator line `===== PASTE EVERYTHING BELOW THIS LINE INTO GEMINI =====`.
3. The image request, byte-identical to what a normal run sends.

## Exit codes / errors

Unchanged. A failed text stage fails the audience as today; no file is written for a run
that produced no concept.
