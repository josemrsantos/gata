# Plan Summary: Image-prompt-only mode

**Spec**: `056-image-prompt-only` · **Date**: 2026-10-12 · **For**: human approval at gate G2
*One page, plain English, no file-by-file detail. The plan and tasks are the source of
truth; if they disagree with this page, the plan wins and this page is regenerated.*

## 1. What and why
A new `--image-prompt-only` flag (on `gata` and `pipeline.py`) runs every step except making the picture: instead it saves the exact text to give Gemini in a file and tells you where it is.
Image generation is the slowest, most expensive and least reliable step, and today you cannot see what Gemini is actually asked to draw.
In the governance run, the image request had no description of Gata, so the picture showed a human and was shipped after three paid attempts; this file would have shown that in seconds.

## 2. What changes for you
- `gata "topic" --image-prompt-only` produces the usual text bundle plus a new `image_prompt.txt` per audience, and prints "No image was auto-generated…" with the file's path. No picture, no evaluator, no image cost.
- The file starts with a short header (title, picture size such as 1200x644 for `--linkedin-post`, and a note that the title banner and crop are not applied), then a clear line "paste everything below this line into Gemini", then the exact request.
- If the request has no Gata description, you get a visible warning (the file is still written).
- Without the flag nothing changes. `prompt_card.txt` is not touched.
- Risk is low and it is easy to undo (an optional flag, additive code).

## 3. Decisions I need from you
| # | Decision | My recommendation | Why |
|---|----------|-------------------|-----|
| 1 | Approve **Constitution amendment v1.5** to §2 ("the image prompt is never written to disk"), adding an exception for `--image-prompt-only` (gate G3) | Yes | The feature cannot exist without it; every normal run still writes no image prompt. I will show you the exact wording before changing the file |
| 2 | Version bump 1.32.0 → 1.33.0 | Yes | New flag and new output file |
| 3 | Run one real text-only check at the end (`gata … --image-prompt-only`, about $0.15–0.30, no image cost) | Yes | The tests are all mocked; this shows the real file once |
| 4 | Removing the "Image-prompt-only mode" item from TODO.md in this PR (RULE 19 / G3) | Yes, at PR time | I will show you the exact removal first |

## 4. Decisions already made
- New Flow-Forward spec 056, not an amendment to Spec 004 — TODO.md item (RULE 18).
- Skips only image creation; all other stages run; one file per audience — TODO.md item.
- New file `image_prompt.txt`; `prompt_card.txt` unchanged — your answers, 2026-10-12 (spec Clarifications).
- Image Evaluator skipped entirely; `--linkedin-post` header states 1200x644; flag ignored with a warning under `--research-only` — defaults you confirmed 2026-10-12.
- Spec approved at G1, 2026-10-12.

## 5. Scope
**In**: the flag on both entry points; one shared builder so the file equals the real request; the header; the file and message; the Gata-description warning; tests, docs, version.
**Out**: fixing the unreadable-concept fallback itself; correcting `prompt_card.txt`; recreating the banner or crop by hand; any change to normal runs.

## 6. Cost and time
Build: 32 tasks, about 6 source files and 5 test files, roughly one working session. API spend while building: $0 (all mocked) except the optional check in decision 3 (about $0.15–0.30). Could exceed: only if the live check is repeated.

## 7. Verified vs assumed
**Verified** (by reading the code, not by running it): the image step is a single loop in `core/runner.py`; the request is built inside `generate()` and nowhere saved; the explainer HTML needs no image, so nothing else has to be skipped; `write_bundle` logs write errors instead of raising; `run_pipeline` has 2 callers in `core/cli.py` and 4 in `pipeline.py`; `/speckit-analyze` found coverage of all 15 requirements.
**Only assumed**: that pasting the file into the Gemini app gives the picture you expect (SC-004 is judged by eye only, in the optional check); that the existing tests stay green after extracting the builder (checked at implementation).

## 8. What would surprise you
- Constitution §2 conflicts with this feature (analyze finding D1, CRITICAL): it is not fixed in the artifacts but handled by decision 1; implementation will not start before you approve it.
- An existing test (`test_constitution_models.py`, expects v1.4) must change with the amendment — added to the tasks (D2, fixed).
- If the output folder cannot be written, the run does not fail: an error is logged and no path is printed — matches every other bundle file, and the spec wording was corrected to say so (D3, fixed).
- The "concept not understood" warning is the Satirist's existing one; the new warning only fires when the Gata description is missing (D4, fixed).
- The README currently describes `prompt_card.txt` as the "verbatim image prompt", which is wrong for multi-panel cartoons; I will correct that row (D5, fixed).
- Unfixed analyze findings: D7 (no test that an existing `image_prompt.txt` is overwritten) and D8 (variable naming) — LOW, left as is.

## 9. Detail, if you want it
[spec.md](spec.md) · [plan.md](plan.md) · [tasks.md](tasks.md) · [research.md](research.md) · [data-model.md](data-model.md) · [contracts/cli-contract.md](contracts/cli-contract.md) · [quickstart.md](quickstart.md) · analyze result: in this conversation (1 CRITICAL gated, 1 HIGH, 3 MEDIUM, 3 LOW; D2–D6 fixed, D7–D8 left).
