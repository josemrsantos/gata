# Feature Specification: Single Main Audience + UK Default

**Feature Branch**: `016-single-main-audience`
**Created**: 2026-06-16
**Status**: Draft

## Summary

`gata <topic>` currently infers 2–4 audiences and generates one image per audience. For
typical use (sharing a single post, preparing an announcement) this is more images than
needed and multiplies API cost and run time. This stage changes the default to the single
most relevant audience plus UK — typically 2 images per run.

## Technical Design

### `agents/agent_cultural_strategist.py`

- `_AUDIENCE_INFERENCE_SYSTEM`: change "2 to 4 most relevant audiences" → "the single most
  relevant audience". Return value is still a JSON array, but with exactly one element.
- `_AUDIENCE_FALLBACK`: reduce from 3 entries to 1 (global English-speaking public), since
  `_ensure_uk` in `cli.py` always appends UK if not already present — the fallback path
  also produces "main + UK".

### No other changes needed

`_ensure_uk` in `cli.py` already handles the UK guarantee. The pipeline loop, output paths,
and summary logic all work the same for 1 or 2 audiences.

### Modified files

| File | Change |
|------|--------|
| `agents/agent_cultural_strategist.py` | Prompt asks for 1 audience; fallback reduced to 1 entry |
| `tests/test_agent_cultural_strategist.py` | Cover single-audience inference and fallback |
