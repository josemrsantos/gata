# Feature Specification: Run Summary — human-readable time/iteration/cost rollup

**Feature Branch**: `013-run-summary`
**Created**: 2026-06-16
**Status**: Draft

## Summary

`telemetry.json` (added in stage 010) already records per-agent duration, iterations, token
counts, and cost, but it is machine-readable only. This stage adds a plain-text summary —
per agent: time taken, iteration count, cost; then a total time and total cost line — logged
at the end of every run and written into the bundle as `summary.txt`. For the multi-audience
CLI (`gata <topic>`), a second rollup is written to the top-level output folder aggregating
totals across all audiences, since that is the number an operator actually wants when judging
the cost of producing a full release.

## User Scenarios & Testing

### User Story 1 — Per-run summary (Priority: P1)

After any single pipeline run, the operator can see — without parsing JSON — how long each
agent took, how many iterations it ran, what it cost, and the run's total time and cost.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the bundle folder is inspected, **Then** `summary.txt`
   is present and lists each agent with its duration, iteration count, and cost, followed by
   a TOTAL line with total duration and total cost.
2. **Given** a completed run, **When** the logs are inspected, **Then** the same summary text
   was logged at INFO level.

### User Story 2 — Multi-audience grand total (Priority: P1)

After `gata <topic>` finishes generating cartoons for every inferred audience, the operator
can see total time and total cost across the entire run without adding up individual bundles
by hand.

**Acceptance Scenarios**:

1. **Given** a multi-audience run with N audiences, **When** it completes, **Then**
   `{output_dir}/summary.txt` lists each audience with its time and cost, followed by a TOTAL
   line summing across all audiences.
2. **Given** one audience fails, **When** the run completes, **Then** the grand total reflects
   only the audiences that produced telemetry; the failed audience is omitted, not counted as
   zero.

### Edge Cases

- An agent with `duration_seconds == 0.0` and `cost_usd == 0.0` (e.g. it was skipped) still
  appears in the summary — no special-casing.
- If `run_pipeline` raises before any agent completes, `summary.txt` and the logged summary
  still appear (matching existing `telemetry.json` behavior) but list zero agents and a zero
  TOTAL line, rather than being omitted.

## Technical Design

### New function (`agents/bundle_writer.py`)

```python
def format_summary(telemetry: RunTelemetry) -> str:
    """One line per agent (duration, iterations, cost), then a TOTAL line."""
```

Used by `write_bundle()` to write `summary.txt` whenever `telemetry` is provided (same
condition as `telemetry.json`), and by `runner.run_pipeline()` to log the same text at INFO
level once the run completes.

### Changed return type (`agents/runner.py`)

`run_pipeline()` now returns the `RunTelemetry` it built (previously returned `None`), so
callers that run multiple audiences can aggregate. `pipeline.py` (single run per invocation)
ignores the return value, matching its current behavior.

### Multi-audience aggregation (`agents/cli.py`)

`main()` collects the `RunTelemetry` returned by each successful `run_pipeline()` call,
then after the loop builds a flat summary (`{audience_name}: {duration}s — ${cost}` per
audience, then a TOTAL line) and writes it to `{output_dir}/summary.txt`, logging it at INFO
level as well.

### Modified files

| File | Change |
|------|--------|
| `agents/bundle_writer.py` | Add `format_summary()`; write `summary.txt` alongside `telemetry.json` |
| `agents/runner.py` | Return `RunTelemetry` from `run_pipeline()`; log summary at INFO |
| `agents/cli.py` | Collect per-audience telemetry; write/log grand-total `summary.txt` |
| `pyproject.toml` | Bump version to `1.4.0` |
| `agents/__version__.py` | Bump to `1.4.0` |
| `README.md` | Document `summary.txt` in the bundle file list |
