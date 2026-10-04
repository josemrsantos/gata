# Implementation Plan: Single-audience default for gata

**Branch**: `055-single-audience-default` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/055-single-audience-default/spec.md`

## Summary

`gata "<topic>"` stops guessing audiences and instead generates for one built-in
audience, `uk-tech-engineers`. A repeatable `--audience` option picks community
audiences by name (validated against `communities.yaml` before any paid call), and a
new `--infer-audiences` flag keeps today's guessed-plus-UK behaviour. The change is
confined to `core/cli.py`: one constant, two small helpers and two new arguments; the
pipeline, agents and `pipeline.py` are untouched. The bulk of the work is updating
about 10 existing CLI tests that assumed the guessing default, plus docs.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `argparse` (stdlib), `core.config_loader.load_communities`, existing `agents.agent_cultural_strategist.infer_audiences` — no new dependencies
**Storage**: none (reads `communities.yaml` from the current folder when present)
**Testing**: pytest with mocks (no real API calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — behaviour change at the entry point
**Performance Goals**: a default run does 1 pipeline run and 0 guessing calls (today ≈ 2 runs + 1 call)
**Constraints**: ruff `line-length=88`; no bare `print()` for new messages (§13: use `logger`); validation errors before any paid call
**Scale/Scope**: 1 source file (~60 lines changed), 1 test file, 3 docs, version bump

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | No provider, SDK or model change |
| 2 | Image Output Rule | ✅ | Untouched |
| 3 | XML and Output Contract | ✅ | Untouched |
| 4 | Character Rules | ✅ | Untouched |
| 5 | Visual Style Rules | ✅ | Untouched |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ | Untouched |
| 7 | Language Rule | ✅ | Default audience language stays English; named audiences keep their own `output_language` |
| 8 | Project Structure | ✅ | No new directory or package; edits in `core/` and `tests/` only |
| 9 | Testing Rules | ✅ | Tests first; mock-only; every new test has a one-sentence comment |
| 10 | Secrets and Security | ✅ | No new secrets; validation runs before the key check and before any call |
| 11 | Development Stages | ✅ | Branch `055-single-audience-default`; 054 merged |
| 12 | Code Quality | ✅ | `ruff check .` / `ruff format` gate in tasks |
| 13 | Logging | ✅ | New errors and the research-only note use `logger`; existing `print` progress lines untouched |

**Constitution Check result (pre-research)**: all 13 pass; no Complexity Tracking needed.
**Post-design re-check**: unchanged — the design adds no module, dependency or log-level change.

## Project Structure

### Documentation (this feature)

```text
specs/055-single-audience-default/
├── plan.md
├── plan-summary.md    (one-page human summary — gate G2)
├── spec.md
├── research.md        (Phase 0 — decisions D1–D8)
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
core/cli.py            MODIFY  add _DEFAULT_AUDIENCE, _resolve_audience_names(), --audience (append),
                               --infer-audiences; choose the audience list per mode; research-only
                               takes the first selected audience; help text
tests/test_cli.py      MODIFY  update ~10 tests that assume guessing (add --infer-audiences or patch
                               the default); ADD tests for default run, --audience, dedupe, errors,
                               --infer-audiences, research-only, drift guard
README.md              MODIFY  `gata` command section: new default, --audience, --infer-audiences; status row 55
docs/architecture.md   MODIFY  audience-selection description and any "UK always" / inference wording
CHANGELOG.md           MODIFY  v1.31.0 entry (hand-written, RULE 17)
pyproject.toml, core/__version__.py   MODIFY  1.30.0 → 1.31.0 (RULE 15)
CLAUDE.md              MODIFY  Completed Stages row 055 (RULE 19 pattern, in this PR)
TODO.md                MODIFY  remove "Single-audience default for gata" (RULE 19)
```

**Structure Decision**: keep everything in `core/cli.py` beside the existing
`_UK_AUDIENCE`/`_ensure_uk`. Rejected: a new `core/audiences.py` (the logic is one
constant and two short helpers; a module would add structure for no reuse — `pipeline.py`
has its own community mechanism and is out of scope).

## Version and docs gates

- **Version (RULE 15)**: `1.30.0` → `1.31.0` (new flag, changed default) — pending the lead's confirmation (plan-summary decision 4).
- **RULE 17**: CHANGELOG entry, README, `docs/architecture.md` before merge.
- **RULE 19**: remove the TODO item in this PR.

## Decisions awaiting the project lead

See `plan-summary.md` §3. Four: (1) what to do with `newsletter_merge.py`'s default
`--audience uk`, which will no longer match default `gata` output (`uk-tech-engineers/`);
(2) whether to run the optional paid smoke test (about $0.20, 5 minutes); (3) whether to
sanitize named audiences when used as file names; (4) the version bump to `1.31.0`.
Three assumptions to confirm: the built-in default answers to its own name when
`communities.yaml` is absent; when the file exists it is the only source of valid names;
`--infer-audiences` with `--audience` is rejected.

## Complexity Tracking

None — no constitution violations.
