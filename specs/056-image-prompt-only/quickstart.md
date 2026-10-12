# Quickstart: validating Image-prompt-only mode

Prerequisites: `source set_gata.sh` (RULE 16); an installed `gata` from this branch.

## 1. Automated (no network)

```bash
python -m pytest tests/ -q
ruff check . && ruff format --check .
```

Expected: all pass, including the new prompt-only tests (builder equals sent prompt,
no image/evaluator call, file + message, missing-Gata warning, flag passthrough).

## 2. Live check (optional, text stages only, about $0.15–0.30)

```bash
cd output/newsletter
gata "Governance in the Agentic AI World" --image-prompt-only -v
```

Expected:
- No `.png` appears in the topic folder.
- The terminal ends with "No image was auto-generated…" and the path to
  `uk-tech-engineers/image_prompt.txt`.
- `uk-tech-engineers/summary.txt` shows no "Image Generator" or "Image Evaluator" lines.
- `image_prompt.txt` starts with the header, then the separator, then the request; the
  request contains the Gata paragraph.
- `prompt_card.txt` is present and unchanged in format.

## 3. Variants

- `--linkedin-post` (needs the research cost): header says `1200x644`.
- `--audience A --audience B`: two `image_prompt.txt` files, two messages.
- `--research-only --image-prompt-only`: a warning that the flag has no effect.
- Without the flag: an image is produced and no `image_prompt.txt` exists.

## 4. Manual use

Open `image_prompt.txt`, copy everything below the separator line into the Gemini app,
and compare with an automatic run's picture if desired.
