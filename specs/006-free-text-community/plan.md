# Implementation Plan: Free-Text Community Mode

**Branch**: `008-free-text-community` | **Date**: 2026-06-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/006-free-text-community/spec.md`

## Summary

Allow `--community` to accept any free-text description (e.g. "US community that dislikes Trump") without requiring a pre-configured entry in `communities.yaml`. When no exact match is found, Trend Scout infers audience/language/tone from the description via a single Gemini call, then fetches general current headlines and ranks them by relevance to the description. Named communities in `communities.yaml` continue to work exactly as before.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: google-genai (Gemini), anthropic, httpx, pytest, pyyaml
**Storage**: `communities.yaml` (optional read), `output/` (write)
**Testing**: pytest, all API calls mocked
**Target Platform**: Linux CLI (same as existing pipeline)
**Project Type**: CLI tool
**Performance Goals**: At most one additional inference call vs. named-community path; total latency unchanged in the common case
**Constraints**: `communities.yaml` absence must not crash free-text mode; exact-name match must not trigger inference path
**Scale/Scope**: Single-operator development tool; one run at a time

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| 1 — SDK & model strings | ✅ Pass | New Gemini call uses `gemini-2.5-flash` per constitution; `from google import genai` |
| 2 — Image output (binary) | ✅ Pass | No image generation changes |
| 3 — XML contract | ✅ Pass | No changes to `<verdict>` or `<joke_explanation>` parsing |
| 7 — Language rule | ✅ Pass | Inferred `output_language` is set in `StrategyBrief` and flows through the full pipeline |
| 8 — Project structure | ✅ Pass | New code in existing `agents/trend_scout.py` and `pipeline.py` only |
| 9 — Testing rules | ✅ Pass | New test file required; all API calls mocked |
| 12 — Code quality | ✅ Pass | ruff required; no blank-line section dividers |
| 13 — Logging | ✅ Pass | INFO for path chosen; WARNING for inference fallbacks |

No constitution violations. No Complexity Tracking required.

## Project Structure

### Documentation (this feature)

```text
specs/006-free-text-community/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── cli.md
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
agents/
├── trend_scout.py       # ADD: infer_brief_from_description(), get_topics_for_description()
├── config_loader.py     # MODIFY: load_communities() — tolerate missing file in free-text path

pipeline.py              # MODIFY: --community branch — exact-match first, free-text fallback

tests/
├── test_trend_scout.py  # ADD: tests for infer_brief_from_description, get_topics_for_description
└── test_pipeline.py     # ADD: tests for free-text path, missing yaml, empty --community
```

**Structure Decision**: Single project. All changes are additive or minimal edits inside existing files. No new modules needed.
