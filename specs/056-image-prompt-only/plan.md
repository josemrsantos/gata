# Implementation Plan: Image-prompt-only mode

**Branch**: `056-image-prompt-only` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/056-image-prompt-only/spec.md`

## Summary

A new `--image-prompt-only` flag on `gata` and `pipeline.py` runs every stage except
image creation and image evaluation. The runner builds the exact request the image
model would receive — through the same function the normal path now also uses — adds
a short manual-use header, and saves it as `image_prompt.txt` in the audience's bundle
folder. It then prints that no image was generated, that the file must be given to
Gemini by hand, and where the file is. `prompt_card.txt` is untouched. One thing blocks
a plain implementation: Constitution §2 says the image prompt is never written to disk,
so the lead must approve a constitution amendment (v1.5) before implementation.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: existing only (`argparse`, `pathlib`); no new dependencies
**Storage**: one new text file per audience bundle (`image_prompt.txt`)
**Testing**: pytest with mocks (no real API calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — additive extension
**Performance Goals**: a prompt-only run makes 0 image-model calls and 0 evaluator calls (a normal run makes 1–3 of each)
**Constraints**: ruff `line-length=88`; new messages use `logger` except the user-facing progress/result line, which follows the existing `print` progress pattern in `core/runner.py`; normal-run behaviour and prompt text must be unchanged (SC-006)
**Scale/Scope**: 4 source files plus `pipeline.py`'s 4 call sites, 5 test files, 3 docs, version bump

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | No provider, SDK or model change |
| 2 | Image Output Rule | ❌ → amendment | "The image prompt text is NEVER written to disk" — this feature writes it by design. Needs amendment v1.5 (see Complexity Tracking); gate G3 |
| 3 | XML and Output Contract | ✅ | Untouched |
| 4 | Character Rules | ✅ | The request text is not changed; the plan adds a check that the verbatim Gata paragraph is present in the saved request and warns if not |
| 5 | Visual Style Rules | ✅ | Request text unchanged |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ | Untouched |
| 7 | Language Rule | ✅ | Request text unchanged; header is operator-facing (English) and not part of the pasted text |
| 8 | Project Structure | ✅ | No new directory or package; edits in `agents/`, `core/`, `tests/` only |
| 9 | Testing Rules | ✅ | Tests first; mock-only; every new test has a one-sentence comment |
| 10 | Secrets and Security | ✅ | No new secrets; the saved file holds a prompt only, no keys; `output/` stays gitignored |
| 11 | Development Stages | ✅ | Branch `056-image-prompt-only`; 055 merged |
| 12 | Code Quality | ✅ | `ruff check .` / `ruff format` gate in tasks |
| 13 | Logging | ✅ | New warnings use `logger`; the one result line uses `print` exactly like the existing progress lines in `core/runner.py` |

**Constitution Check result (pre-research)**: 12 pass, 1 needs an amendment (§2).
**Post-design re-check**: unchanged — the design adds no module or dependency; §2 is the only conflict and is tracked below.

## Project Structure

### Documentation (this feature)

```text
specs/056-image-prompt-only/
├── plan.md
├── plan-summary.md    (one-page human summary — gate G2)
├── spec.md
├── research.md        (Phase 0 — decisions D1–D9)
├── data-model.md      (Phase 1)
├── quickstart.md      (Phase 1)
├── contracts/
│   └── cli-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md           (Phase 2 output, via /speckit-tasks)
```

### Source Code Changes

```text
agents/agent_image_generator.py  MODIFY  extract build_image_request(concept, layout) from generate();
                                         generate() calls it (behaviour identical); ADD
                                         build_manual_header(title, show_title, target_size)
                                         and build_prompt_file(...) = header + separator + request
core/runner.py                   MODIFY  run_pipeline(image_prompt_only=False): after the Satirist, build the
                                         request, warn if the Gata paragraph is missing, skip the
                                         generate/evaluate loop, pass the file text to write_bundle, then
                                         print the "no image generated" message with the file location;
                                         research_only + flag -> warning, flag ignored
core/bundle_writer.py            MODIFY  write_bundle(image_prompt_file=None): writes image_prompt.txt when given;
                                         prompt_card.txt logic untouched; returns the bundle dir as today
core/cli.py                      MODIFY  --image-prompt-only argument; pass through to run_pipeline (both calls);
                                         research-only path warns that the flag has no effect
pipeline.py                      MODIFY  --image-prompt-only argument; pass through at all 4 run_pipeline calls
tests/test_agent_image_generator.py  MODIFY  ADD builder-equals-sent-prompt, header and separator tests
tests/test_pipeline.py           MODIFY  ADD prompt-only runner tests (no image/evaluator call, file + message,
                                         missing-Gata warning, unchanged without flag, research-only)
tests/test_bundle_writer.py      MODIFY  ADD image_prompt.txt written / not written; prompt_card.txt unchanged
tests/test_cli.py                MODIFY  ADD flag passthrough (default off and on), multi-audience, research-only warning
tests/test_constitution_models.py  MODIFY  version/amendment-record test 1.4 -> 1.5 (with the amendment)
README.md                        MODIFY  new flag, new bundle file, status row 56
docs/architecture.md             MODIFY  image step is skippable; image_prompt.txt in the bundle
CHANGELOG.md                     MODIFY  v1.33.0 entry (hand-written, RULE 17)
pyproject.toml, core/__version__.py   MODIFY  1.32.0 → 1.33.0 (RULE 15)
.specify/memory/constitution.md  MODIFY  v1.5: §2 exception (only after the lead approves — gate G3)
CLAUDE.md                        MODIFY  Completed Stages row 056 (RULE 19 pattern, in this PR)
TODO.md                          MODIFY  remove "Image-prompt-only mode" (RULE 19; removal shown to the lead first)
```

**Structure Decision**: keep the shared builder in `agents/agent_image_generator.py`,
beside `_build_multi_panel_prompt` and `_GATA_CHARACTER`, so the normal and prompt-only
paths cannot drift (FR-004). Rejected: a new module (one function and one header
helper do not justify it); building the request separately in the runner (it would
duplicate the logic and could drift).

## Version and docs gates

- **Version (RULE 15)**: `1.32.0` → `1.33.0` (new flag, new output file).
- **RULE 17**: CHANGELOG entry, README, `docs/architecture.md` before merge.
- **RULE 19**: remove the TODO item in this PR (removal shown to the lead first, per G3 / RULE 8).

## Decisions needed from the project lead (gate G2 / G3)

1. **Constitution §2 amendment (v1.5)** — recommended: allow the prompt to be written to
   disk only in `--image-prompt-only` mode, at the operator's request; every normal run
   still writes no image prompt.
2. **Version bump to 1.33.0** — recommended: yes.
3. **Optional paid smoke test** — recommended: yes, one real `gata "topic" --image-prompt-only`
   run (text stages only, about $0.15–0.30, no image cost) to check the file by eye.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|-----------|-----------|-------------------------------------|
| §2 "image prompt text is NEVER written to disk" | The whole feature is to write the exact image request to a file for manual use in Gemini | There is no way to hand the operator the request without writing it or printing it; printing loses the header, is lost when the terminal scrolls, and cannot be pasted reliably for long multi-panel prompts. Needs the lead's explicit acceptance and a constitution amendment |
