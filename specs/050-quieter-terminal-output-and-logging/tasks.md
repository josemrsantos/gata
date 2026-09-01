# Tasks: Quieter Default Terminal Output + Persistent Logging

**Input**: Design documents from `specs/050-quieter-terminal-output-and-logging/`
**Branch**: `050-quieter-terminal-output-and-logging`
**Prerequisites**: plan.md ✅, spec.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions.

---

## Phase 1: Setup

- [x] T001 Confirm active git branch is `050-quieter-terminal-output-and-logging`

---

## Phase 2: bundle_writer additions (FR-001, FR-004)

### Tests — Write FIRST, Confirm FAILING

- [ ] T002 [P] In `tests/test_bundle_writer.py`: add
  `test_format_total_line_returns_only_total` — given a multi-agent
  telemetry, `format_total_line()` returns exactly one line matching
  `TOTAL: {duration}s — ${cost}`, no per-agent/per-model content
- [ ] T003 [P] In `tests/test_bundle_writer.py`: add
  `test_write_bundle_creates_run_log_when_lines_given` and
  `test_write_bundle_skips_run_log_when_lines_empty_or_none` for
  `write_bundle(log_lines=...)`

> **STOP**: Confirm T002–T003 FAIL before T004.

### Implementation

- [ ] T004 In `core/bundle_writer.py`: add `format_total_line(telemetry) ->
  str`; add `log_lines: list[str] | None = None` param to `write_bundle()`,
  writing `run.log` (one line per entry) when non-empty

> **STOP**: `python -m pytest tests/test_bundle_writer.py -v` — confirm all pass.

**Checkpoint**: `python -m pytest tests/test_bundle_writer.py -v`

---

## Phase 3: run_pipeline() verbose + log capture (FR-002, FR-003, FR-007, FR-008)

### Tests — Write FIRST, Confirm FAILING

- [ ] T005 [P] In `tests/test_pipeline.py`: add
  `test_run_pipeline_verbose_false_prints_total_line_only`,
  `test_run_pipeline_verbose_true_prints_full_summary` (mock
  `bundle_writer.format_summary`/`format_total_line` and assert which is
  printed)
- [ ] T006 [P] In `tests/test_pipeline.py`: add
  `test_run_pipeline_captures_warning_and_passes_to_write_bundle` (a
  mocked agent call that logs a WARNING must result in
  `write_bundle(log_lines=[...])` containing that message) and
  `test_run_pipeline_no_warnings_passes_empty_log_lines`
  and `test_run_pipeline_run_log_excludes_info_level` (an INFO-level log
  during the run must NOT appear in `log_lines`)

> **STOP**: Confirm T005–T006 FAIL before T007.

### Implementation

- [ ] T007 In `core/runner.py`: add a small `logging.Handler` subclass that
  appends formatted records to a list; add `verbose: bool = False` param to
  `run_pipeline()`; install the handler (level `WARNING`) on the root
  logger at the start of the `try` block, remove it in `finally`; pass
  captured lines to `bundle_writer.write_bundle(log_lines=...)`; final
  `print()` uses `format_summary(telemetry)` when `verbose` else
  `format_total_line(telemetry)`

> **STOP**: `python -m pytest tests/test_pipeline.py -v` — confirm all pass.

**Checkpoint**: `python -m pytest tests/test_pipeline.py -v`

---

## Phase 4: CLI flags + level unification (FR-005, FR-006)

### Tests — Write FIRST, Confirm FAILING

- [ ] T008 [P] In `tests/test_pipeline.py`: add
  `test_pipeline_verbose_flag_sets_info_level` and
  `test_pipeline_default_sets_warning_level` (assert the effective
  `logging.basicConfig` level chosen); add
  `test_pipeline_verbose_passed_to_run_pipeline` (all 4 mode branches, or
  at least manual mode as representative)
- [ ] T009 [P] In `tests/test_cli.py`: add the same trio of tests for
  `gata` — verbose flag sets INFO, default sets WARNING,
  `verbose=args.verbose` reaches `run_pipeline` in both the research-only
  branch and the per-audience loop; add
  `test_per_audience_run_log_isolation` (two audiences' mocked
  `run_pipeline` calls must each receive their own distinct `log_lines`,
  not a shared/accumulated list) — likely satisfied automatically by T007's
  per-call handler scoping, but assert it explicitly here

> **STOP**: Confirm T008–T009 FAIL before T010.

### Implementation

- [ ] T010 [US] In `pipeline.py`: add `--verbose`/`-v` flag; `logging.
  basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
  ...)`; pass `verbose=args.verbose` to every `run_pipeline()` call (all 4
  mode branches)
- [ ] T011 [US] In `core/cli.py`: add `--verbose`/`-v` flag; same level
  logic; pass `verbose=args.verbose` to both the research-only branch's
  and the per-audience loop's `run_pipeline()` calls

> **STOP**: `python -m pytest tests/test_pipeline.py tests/test_cli.py -v` — confirm all pass.

**Checkpoint**: `python -m pytest tests/test_pipeline.py tests/test_cli.py -v`

---

## Phase 5: Polish & Cross-Cutting Concerns (RULE 6, 15, 17)

- [ ] T012 Run `python -m pytest tests/ -v` — confirm zero failures
- [ ] T013 [P] Run `ruff check . --fix` and `ruff format .`; confirm
  `ruff check .` exits 0
- [ ] T014 [P] Update `README.md`: document `--verbose`/`-v` on both entry
  points, and the new `run.log` bundle file
- [ ] T015 [P] Update `docs/architecture.md`: note the quiet-default
  terminal behaviour and the new per-run `run.log` capture point
- [ ] T016 [P] Add a new `CHANGELOG.md` entry
- [ ] T017 [P] Bump version in `pyproject.toml`/`core/__version__.py`
  (1.28.1 → 1.29.0)
- [ ] T018 Update `CLAUDE.md`'s Completed Stages table: add a row for `050`
- [ ] T019 Remove the Spec 050 item from `TODO.md` as part of this same PR
  (RULE 19)

---

## Phase 6: Real End-to-End Verification (operator request, no image generation)

- [ ] T020 Run 1: `gata "<real topic>" --research-only` (default, quiet) —
  confirm terminal shows progress markers + single `TOTAL:` line (no
  per-agent/per-model breakdown), and inspect the bundle for `run.log`
  (present iff a WARNING was logged) alongside the unaffected
  `summary.txt`/`telemetry.json`
- [ ] T021 Run 2: same command with `--verbose` — confirm terminal shows
  the full per-agent/per-model breakdown and `INFO`-level log lines,
  matching today's pre-this-spec behaviour

---

## Summary

| Phase | Tasks | Notes |
|-------|-------|-------|
| 1 Setup | T001 | Branch hygiene |
| 2 bundle_writer | T002–T004 | `format_total_line` + `run.log` writing |
| 3 run_pipeline | T005–T007 | `verbose` param + log capture handler |
| 4 CLI flags | T008–T011 | `--verbose` on both entry points |
| 5 Polish | T012–T019 | Full suite + ruff + docs + CHANGELOG + version + CLAUDE.md + TODO.md |
| 6 Verify | T020–T021 | 2 real runs (quiet vs. verbose), no image generation |
| **Total** | **21 tasks** | |
