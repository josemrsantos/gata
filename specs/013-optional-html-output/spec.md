# Feature Specification: Optional HTML Output — opt-in, default disabled

**Feature Branch**: `014-optional-html-output`
**Created**: 2026-06-16
**Status**: Draft

## Summary

`bundle_writer.write_bundle()` currently always calls `agent_explainer.generate_html()` and
writes `explanation.html` / `deep_dive_en.html` whenever an `EnrichedBrief` and image prompt
are available — an extra Claude + Gemini round trip on every run whether or not anyone reads
the HTML. This stage makes HTML generation opt-in via a new `--html` flag on both `gata
<topic>` and `pipeline.py`, defaulting to off. The image, logs, prompt card, telemetry, and
summary are unaffected — they remain unconditional.

## User Scenarios & Testing

### User Story 1 — HTML is off by default (Priority: P1)

Running the pipeline with no special flags no longer produces `explanation.html` or
`deep_dive_en.html`, and no longer pays for the Explainer's Claude/Gemini calls.

**Acceptance Scenarios**:

1. **Given** a default run (`gata <topic>` or `pipeline.py` with no `--html`), **When** the
   bundle is inspected, **Then** `explanation.html` and `deep_dive_en.html` are absent and
   `agent_explainer.generate_html()` was never called.
2. **Given** a default run, **When** `telemetry.json` is inspected, **Then** no Explainer
   entry appears (it never ran).

### User Story 2 — HTML on request (Priority: P1)

An operator who wants the HTML pages for publishing passes `--html` and gets the same output
this project has always produced.

**Acceptance Scenarios**:

1. **Given** `--html` is passed, **When** the bundle is inspected, **Then**
   `explanation.html` and `deep_dive_en.html` are present with the same content as before
   this stage.

### Edge Cases

- `--html` with no `enriched_brief` or no `image_prompt` (e.g. a failed run) still skips HTML
  generation — the existing guard is unchanged, `include_html` only adds a second condition.
- Explainer failure with `--html` set still falls back the same way it does today: logged and
  swallowed, bundle still written.

## Technical Design

### Changed signature (`agents/bundle_writer.py`)

```python
def write_bundle(
    output_path: str,
    agent0_log: ConversationLog | None,
    bc_log: ConversationLog | None,
    enriched_brief: EnrichedBrief | None,
    image_prompt: str | None,
    telemetry: RunTelemetry | None = None,
    include_html: bool = False,
) -> str:
```

HTML generation block gains `include_html and` to its existing guard condition. Default
`False` so any caller that doesn't pass it explicitly gets the new, cheaper behavior.

### Threaded through

```
runner.run_pipeline(..., include_html: bool = False) → write_bundle(..., include_html=include_html)
cli.py:      argparse "--html" (store_true) → run_pipeline(..., include_html=args.html)
pipeline.py: argparse "--html" (store_true) → run_pipeline(..., include_html=args.html)
```

### Modified files

| File | Change |
|------|--------|
| `agents/bundle_writer.py` | Add `include_html: bool = False` param; gate HTML block on it |
| `agents/runner.py` | Add `include_html: bool = False` param; pass through to `write_bundle` |
| `agents/cli.py` | Add `--html` flag (default off); pass to `run_pipeline` |
| `pipeline.py` | Add `--html` flag (default off); pass to every `run_pipeline` call site |
| `pyproject.toml` | Bump version to `1.5.0` |
| `agents/__version__.py` | Bump to `1.5.0` |
| `README.md` | Document `--html` flag; note HTML files are opt-in |
