# Implementation Plan: Single-audience default for gata

**Branch**: `055-single-audience-default` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/055-single-audience-default/spec.md`

## Summary

`gata "<topic>"` stops guessing audiences and instead generates for one built-in
audience, `uk-tech-engineers`. A repeatable `--audience` option picks community
audiences by name (validated against `communities.yaml` before any paid call), and a
new `--infer-audiences` flag keeps today's guessed-plus-UK behaviour. The change is
confined to `core/cli.py`: one constant, two small helpers and two new arguments, plus the one-line
default change in the newsletter merge; the pipeline, agents and `pipeline.py` are untouched. The bulk of the work is updating
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
**Scale/Scope**: 3 source files (`core/cli.py` mainly), 2 test files, 3 docs, version bump

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
newsletter_merge.py    MODIFY  `--audience` default and help text: `uk` → `uk-tech-engineers` (FR-013)
core/newsletter_merge.py  MODIFY  `merge_edition(audience=...)` default `uk` → `uk-tech-engineers`
tests/test_newsletter_merge.py  MODIFY  ADD default-audience tests (default, script default + help, `--audience uk` still honoured)
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

- **Version (RULE 15)**: `1.30.0` → `1.31.0` (new flag, changed default) — approved by the lead.
- **RULE 17**: CHANGELOG entry, README, `docs/architecture.md` before merge.
- **RULE 19**: remove the TODO item in this PR.

## Decisions (project lead, 2026-10-04, gate G2)

1. **Newsletter merge default** — answered **A**: change `newsletter_merge.py`'s default
   audience to `uk-tech-engineers` (spec FR-013, user story 5); earlier editions use `--audience uk`.
2. **Optional paid smoke test** — answered **yes** (about $0.20, 5 minutes).
3. **File-safe names for named audiences** — answered **yes** (FR-014).
4. **Version bump to 1.31.0** — answered **yes**.
5. **Assumptions** — confirmed: the built-in default answers to its own name only when
   `communities.yaml` is absent; an existing file is the only source of valid names;
   `--infer-audiences` with `--audience` is rejected.

## Complexity Tracking

None — no constitution violations.
