# Feature Specification: Image Evaluator Agent

**Feature Branch**: `022-image-evaluator`
**Created**: 2026-06-19
**Status**: Complete

## Problem

After image generation there was no feedback loop. The image model could produce an
image with rendering artifacts (duplicate text, garbled labels, wrong character colours,
missing elements) or generate a visually competent but unfunny cartoon, and the pipeline
would accept it without question.

## Goal

After each image is generated, a Gemini vision model evaluates it on two criteria:

1. **Technical artifacts** — duplicate text, garbled chalkboard text, Gata character
   integrity failures, missing load-bearing elements.
2. **Funniness** — would the target audience actually laugh at this?

If the image is rejected on either criterion, regeneration is triggered up to 2 times
before accepting the last image. The evaluator never blocks the pipeline: it fails open
on parse errors or model exhaustion.

## Technical Design

### New type: `ImageEvaluation`

```python
@dataclass
class ImageEvaluation:
    verdict: str        # "APPROVED" or "REJECTED"
    artifacts: list[str]
    is_funny: bool
    funny_notes: str
    model_used: str
```

### Model fallback chain

`gemini-2.5-pro` → `gemini-2.5-flash` → `gemini-2.0-flash` (all support vision input).

### Vision API call

Image bytes are passed as `genai_types.Part(inline_data=genai_types.Blob(...))` alongside
the text evaluation prompt. The MIME type is detected from the file extension.

### Verdict derivation

`_parse_evaluation()` derives the verdict from `artifacts` and `is_funny` rather than
trusting the model's own `verdict` field. This prevents a model from listing artifacts
while still returning APPROVED.

### Retry loop in `runner.py`

```python
for _attempt in range(3):  # up to 2 retries
    generate image
    evaluate image
    if APPROVED: break
    log warning with artifacts and is_funny
```

## Modified files

| File | Change |
|------|--------|
| `agents/agent_image_evaluator.py` | New agent |
| `agents/types.py` | Add `ImageEvaluation` dataclass |
| `agents/runner.py` | Retry loop around image generation + evaluation |
| `tests/test_agent_image_evaluator.py` | 20 tests covering all paths |
| `README.md` | Add Image Evaluator to agent table; update Creative Loop row |
| `TODO.md` | Add stage entry |
