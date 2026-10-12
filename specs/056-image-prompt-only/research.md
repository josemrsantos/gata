# Research: Image-prompt-only mode

**Date**: 2026-10-12. All findings come from reading the current code
(`core/runner.py`, `agents/agent_image_generator.py`, `core/image_generation.py`,
`core/bundle_writer.py`, `core/cli.py`, `pipeline.py`, the existing tests) and the
constitution. No external research was needed; no code was run.

## Findings about today's behaviour

- `run_pipeline()` (`core/runner.py`) runs Cultural Strategist → Satirist → then a loop
  of `agent_image_generator.generate()` + `agent_image_evaluator.evaluate()` (up to 3
  attempts). The loop is the only place an image is made.
- `agent_image_generator.generate()` builds the request inline: multi-panel →
  `_build_multi_panel_prompt(panels, layout)`; otherwise `concept.image_prompt` verbatim.
  It then calls `ImageGeneration().generate(prompt, ...)`. The request therefore exists
  only inside that call.
- The Gata paragraph (`_GATA_CHARACTER`) is appended only on the multi-panel path. The
  single-panel path relies on the Satirist writing it into the scene. On the parse-fallback
  path `concept.image_prompt` is the whole raw verdict, so no paragraph is guaranteed —
  the cause of the 2026-10 incident.
- `target_size` (1200x644) is set only when `--linkedin-post` is used and the layout is
  horizontal. Gemini gets an aspect-ratio hint from the closest preset
  (`_closest_gemini_aspect_ratio`); the title banner and the exact crop are applied in
  Python afterwards.
- `prompt_card.txt` is written by `write_bundle()` from `concept.full_text` (multi-panel)
  or `concept.image_prompt` (single). It is not the multi-panel request.
- `write_bundle()` uses only text (`image_prompt` string, logs, brief) — the explainer HTML
  (`--html`) needs no image file. So no current output depends on the finished image.
- `run_pipeline` is called from 2 places in `core/cli.py` and 4 in `pipeline.py`.
- Constitution §2 states the image prompt text is never written to disk. §13 allows
  `print()` only in `pipeline.py`, but `core/runner.py` already prints progress lines.

## Decisions

- **D1 — One shared request builder.** Extract `build_image_request(concept, layout)` in
  `agents/agent_image_generator.py` from the body of `generate()`; `generate()` calls it
  and sends the result unchanged. The prompt-only path calls the same function, so the
  saved file and the normal request cannot drift (FR-004, SC-002). *Rejected*: rebuilding
  the request in the runner (duplicate logic).
- **D2 — Header and separator.** `build_manual_header(title, show_title, target_size)`
  returns a short block: title; "title banner: not part of the request" (and whether the
  run would have shown one); size line — `1200x644, aspect ratio 21:9` style using the
  existing closest-preset helper, or "no size pinned"; "final crop/resize: not applied".
  `build_prompt_file` puts the header first, then one clear separator line
  (`===== PASTE EVERYTHING BELOW THIS LINE INTO GEMINI =====`), then the request.
  The request after the separator is byte-identical to the builder output (SC-002).
- **D3 — Runner placement.** In `run_pipeline`, right after the Satirist, if
  `image_prompt_only`: build the request, add the header, skip the whole generate/evaluate
  loop, and pass the file text to `write_bundle`. Telemetry gets no image or evaluator
  entries, so the cost summary shows none (FR-010).
- **D4 — Location and message.** `write_bundle()` already returns the bundle directory;
  the runner prints, after it, that no image was auto-generated, that the file must be
  given to Gemini manually, and `<bundle>/image_prompt.txt`. One message per audience,
  because `gata` calls `run_pipeline` once per audience (FR-006, FR-007). A write failure
  inside `write_bundle` is logged by its existing "never raises" handling; the runner
  checks the file exists before printing the location, and otherwise logs an error.
- **D5 — Missing Gata paragraph warning.** After building the request, if the verbatim
  `_GATA_CHARACTER` paragraph is not in it, log a `WARNING` ("image request has no Gata
  character description — the image will probably not show Gata") (FR-013, SC-005). This is
  independent of the existing "verdict parse failed" warning and is a stronger signal than
  detecting the fallback by comparing fields. *Rejected*: detecting fallback via
  `image_prompt == full_text` (fragile).
- **D6 — Skipped outputs.** FR-009 allows skipping image-dependent outputs, but reading
  `write_bundle` shows there are none today (the explainer uses text). The plan therefore
  skips nothing else and states so in the docs; the requirement stays as a guard for future
  outputs.
- **D7 — `--research-only`.** `run_pipeline(research_only=True)` already skips the image
  steps; the flag is ignored there. The CLI entry points log a `WARNING` that
  `--image-prompt-only` has no effect with `--research-only` (visible by default) (FR-011).
- **D8 — Flag plumbing.** Add `--image-prompt-only` (store_true, default False) to
  `core/cli.py` and `pipeline.py`; pass `image_prompt_only=args.image_prompt_only` at both
  `core/cli.py` calls and all four `pipeline.py` calls. Default False keeps every
  existing call identical (SC-006).
- **D9 — Constitution §2.** The feature cannot comply with §2 as written. Recommended
  amendment v1.5: "The image prompt text is never written to disk, except in
  `--image-prompt-only` mode, where the full image request is written to `image_prompt.txt`
  in the run's bundle at the operator's explicit request. Only the final PNG is persisted
  in every other mode." Needs the lead's approval (G3) before implementation.

## Alternatives considered for the whole feature

- Print the prompt to the terminal only — rejected: loses the header, easy to lose on
  scroll, unreliable to copy for long prompts.
- Replace `prompt_card.txt` — rejected by the lead (spec FR-014/FR-015).
- Write the file in a separate `--dry-run` command — rejected: the TODO and spec define a
  flag on the existing entry points.
