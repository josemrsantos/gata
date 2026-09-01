# Implementation Plan: Quieter Default Terminal Output + Persistent Logging

**Branch**: `050-quieter-terminal-output-and-logging` | **Date**: 2026-09-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/050-quieter-terminal-output-and-logging/spec.md`

## Summary

Add a `--verbose`/`-v` flag to both entry points that controls two
independent things: (1) whether `run_pipeline()`'s final terminal print is
the full per-agent/per-model breakdown or a single `TOTAL:` line, and (2)
whether each entry point's `logging.basicConfig()` level is `INFO` or
`WARNING`. Separately (unconditional on `--verbose`), `run_pipeline()`
captures its own `WARNING`-and-above log records via a small in-memory
handler installed for the duration of the call, and hands them to
`bundle_writer.write_bundle()` to persist as `run.log` in that run's bundle
directory when non-empty.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: none new — `logging.Handler` subclass, stdlib only
**Storage**: one new optional file per bundle (`run.log`); no new database
or config file
**Testing**: pytest with `unittest.mock`/`caplog` (no real API calls per
Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — additive extension to shared runner/CLI code
**Performance Goals**: Negligible — one extra in-memory list append per
WARNING+ log record during a run, freed after each `run_pipeline()` call
**Constraints**: ruff `line-length = 88`, `target-version = "py310"`;
`summary.txt`/`telemetry.json` content must stay byte-for-byte identical
regardless of `--verbose` (SC-003) — this is a terminal/log-file feature
only, never a bundle-content change
**Scale/Scope**: 3 modified source files (`core/runner.py`,
`core/bundle_writer.py`, plus both `pipeline.py` and `core/cli.py`, so 4),
1 new small handler class, 1 version bump, 4 modified test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ N/A | No SDK or model involvement. |
| 2 | Image Output Rule | ✅ N/A | No image handling touched. |
| 3 | XML and Output Contract | ✅ N/A | No `<verdict>` involvement. |
| 4 | Character Rules | ✅ N/A | No image prompt content touched. |
| 5 | Visual Style Rules | ✅ N/A | No image prompt content touched. |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ N/A | No panel/iteration logic touched. |
| 7 | Language Rule | ✅ N/A | No text/caption content touched. |
| 8 | Project Structure | ✅ | Changes stay inside `core/`, `agents/` untouched, `tests/`; no new package — the new handler class lives in `core/runner.py` (or `core/bundle_writer.py`) alongside its only caller. |
| 9 | Testing Rules | ✅ | New tests in `tests/test_pipeline.py` (both entry points' `--verbose` flag + logging level), `tests/test_bundle_writer.py` (`run.log` writing), `tests/test_cli.py` (gata's `--verbose`), and a new/updated `format_total_line` test; every new test carries a RULE-3 comment; no real API calls. |
| 10 | Secrets and Security | ✅ N/A | No new secret or credential. |
| 11 | Development Stages | ✅ | Work proceeds on branch `050-quieter-terminal-output-and-logging`, created before implementation; merges via PR per RULE 5/RULE 17. |
| 12 | Code Quality | ✅ | `ruff check .` and `ruff format .` run on every modified file before this is considered done. |
| 13 | Logging | ✅ | This spec IS the logging-infrastructure work — the new handler uses the existing `logger = logging.getLogger(__name__)` pattern; no `print()` added outside `pipeline.py`/existing `core/runner.py`/`core/cli.py` call sites (RULE 12's print() exception already covers those). |

**Constitution Check result**: all gates pass or are N/A.

## Project Structure

### Documentation (this feature)

```text
specs/050-quieter-terminal-output-and-logging/
├── plan.md
├── spec.md
└── tasks.md           (Phase 2 output)
```

### Source Code Changes

```text
core/bundle_writer.py   MODIFY — add format_total_line(telemetry) -> str;
                         add log_lines: list[str] | None = None param to
                         write_bundle(), writing run.log when non-empty.

core/runner.py           MODIFY — add verbose: bool = False param to
                         run_pipeline(); add a small _ListHandler(logging.
                         Handler) class (or reuse logging.handlers.
                         MemoryHandler with an in-memory target) installed
                         on the root logger at WARNING level at the start
                         of the try block, removed in finally; captured
                         lines passed to write_bundle(log_lines=...); final
                         print() branches on verbose between format_summary
                         and format_total_line.

pipeline.py               MODIFY — add --verbose/-v flag; logging.
                         basicConfig level becomes logging.INFO if
                         args.verbose else logging.WARNING; pass
                         verbose=args.verbose to every run_pipeline() call
                         (all 4 mode branches).

core/cli.py               MODIFY — add --verbose/-v flag; logging.
                         basicConfig level becomes logging.INFO if
                         args.verbose else logging.WARNING; pass
                         verbose=args.verbose to run_pipeline() (both the
                         research-only branch and the per-audience loop).

core/__version__.py       MODIFY — bump to 1.29.0 (minor: new capability).
pyproject.toml            MODIFY — matching version bump.

tests/test_bundle_writer.py MODIFY — add tests for format_total_line() and
                         write_bundle(log_lines=...).
tests/test_pipeline.py    MODIFY — add tests for run_pipeline(verbose=...)
                         print branching, run.log capture/omission,
                         per-audience isolation is N/A here (pipeline.py
                         has no multi-audience loop), and pipeline.py's
                         --verbose flag controlling logging level.
tests/test_cli.py         MODIFY — add tests for gata's --verbose flag
                         (logging level + verbose threaded to
                         run_pipeline) and per-audience run.log isolation
                         in the multi-audience loop.
```

**Structure Decision**: The capture handler lives inside `run_pipeline()`
itself (`core/runner.py`), not in either CLI entry point, so it protects
every caller uniformly — including direct programmatic use (RULE 12) — and
so `core/cli.py`'s per-audience loop gets automatic isolation for free
(each `run_pipeline()` call installs and tears down its own handler,
scoped to exactly that call's bundle). This mirrors the same reasoning
already used for Spec 046's `_minimal_brief()` helper and Spec 052's
`_extract_proposer_verdict()` fix: put the shared behaviour at the one
choke point every caller already passes through, not duplicated at each
call site.

`format_total_line()` is a new, small, separate function rather than a
parameter on `format_summary()` (e.g. `format_summary(telemetry,
detailed=True)`), because the two have almost no shared logic — pulling
out just the `TOTAL:` computation as its own one-line function is simpler
than branching inside the existing one, and keeps `format_summary()`
itself (already relied on for `summary.txt`, unconditionally) completely
untouched.

## Complexity Tracking

*No entries — no constitution violations.*
