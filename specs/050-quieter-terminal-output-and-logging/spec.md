# Spec 050 — Quieter Default Terminal Output + Persistent Logging

**Stage**: 050
**Branch**: `050-quieter-terminal-output-and-logging`
**Status**: Draft — awaiting approval
**Dependency**: none

---

## Problem

A real run's terminal output buries the signal an operator actually wants
(did it succeed, what did it cost, where did the output land) under two
kinds of noise:

1. A full per-agent, per-model token/cost breakdown
   (`core.bundle_writer.format_summary()`, printed unconditionally at the
   end of every `run_pipeline()` call in `core/runner.py:254`) — useful for
   deep debugging, but it duplicates `summary.txt`, which is already saved
   to every bundle.
2. WARNING-level log noise (SDK nags, panelist retries, excluded-source
   classifications) — already routed to stderr today (confirmed:
   `logging.basicConfig()`'s default stream), so `2>/dev/null` already
   hides it, but nothing captures it for later. A retrospective audit of
   `FairParallelPanel` panelist drop-offs (Spec 052) hit a dead end for
   exactly this reason: the real failure detail (timeout vs. exception) was
   logged but never persisted, so the actual root cause couldn't be
   confirmed until a live warning happened to be pasted into a conversation
   by hand.

Separately, the two entry points aren't symmetric today: `pipeline.py`
calls `logging.basicConfig(level=logging.INFO, ...)`, while `core/cli.py`
(`gata`) calls it with `level=logging.WARNING`. `pipeline.py` is therefore
already noisier by default than `gata`, with no way to quiet it.

## Goal

1. **Quiet default terminal output**: keep today's single-line progress
   markers (`"Cultural Strategist..."`, `"Satirist/Co-Satirist..."`, etc. —
   a low-noise "something is happening" signal) but collapse the full
   per-agent/per-model breakdown down to a single `TOTAL: {duration}s —
   ${cost}` line. `summary.txt` in the bundle keeps the full detail,
   unconditionally, regardless of this flag — nothing is lost, only the
   terminal gets quieter.
2. **`--verbose`/`-v` flag** (both `pipeline.py` and `gata`) restores
   today's exact terminal behaviour: the full per-agent/per-model
   breakdown printed, and `INFO`-level (not just `WARNING`-level) log
   messages shown on-screen.
3. **Unify both entry points** to the same quiet-by-default baseline:
   `pipeline.py`'s `logging.basicConfig` moves from `level=logging.INFO` to
   `level=logging.WARNING` by default (matching `gata` today), with
   `--verbose` restoring `INFO` on both.
4. **Persistent per-run log file**: every `run_pipeline()` call captures
   its own `WARNING`-and-above log records (regardless of the terminal
   verbosity level chosen above) and writes them to `run.log` inside that
   run's own bundle directory — the same place `summary.txt` and
   `telemetry.json` already live. Omitted entirely when a run produces no
   `WARNING`-or-above records, matching the existing bundle convention
   (e.g. `prompt_card.txt` omitted when there's no prompt).

## Behaviour

### Terminal, quiet (default)

```
  Cultural Strategist...
  Satirist/Co-Satirist...
  Image Generator...
  Image Evaluator...
TOTAL: 45.2s — $0.1234

All 2 image(s) saved to ./output_dir
```

### Terminal, `--verbose`

Identical to today's full output: every per-agent line, every indented
per-model token/cost sub-line, and `INFO`-level log lines (`"credentials
loaded..."`, `"manual mode: topic=..."`, etc.) all shown.

### Bundle directory, either mode

`summary.txt` and `telemetry.json` are written exactly as today,
unconditionally, full detail — this flag only ever affects the terminal
and the new `run.log`, never the bundle's own saved files. `run.log` is
new: present only when that run logged at least one `WARNING`-or-above
message, containing those formatted log lines (not `INFO`/`DEBUG`).

## Requirements

- **FR-001**: `core.bundle_writer` gains `format_total_line(telemetry) ->
  str`, returning just the `TOTAL: ...` line (same computation
  `format_summary()` already does, no per-agent loop).
- **FR-002**: `run_pipeline()` gains a `verbose: bool = False` parameter.
  Its final `print(...)` call (`core/runner.py:254`) uses
  `format_summary()` when `verbose=True`, `format_total_line()` otherwise.
  Progress-marker `print()` calls (lines 117-222) are unaffected by this
  flag — they print in both modes, unchanged.
- **FR-003**: `run_pipeline()` installs an in-memory logging handler
  (capturing `WARNING`-and-above formatted records on the root logger) at
  the start of its `try` block and removes it in the `finally` block,
  regardless of `verbose`. The captured lines are passed to
  `bundle_writer.write_bundle(..., log_lines=...)`.
- **FR-004**: `bundle_writer.write_bundle()` gains a `log_lines: list[str]
  | None = None` parameter; when non-empty, writes `run.log` in the bundle
  directory (same `_write_text` pattern as every other bundle file).
- **FR-005**: Both `pipeline.py` and `core/cli.py` (`gata`) gain a
  `--verbose`/`-v` flag (`action="store_true"`, default `False`), passed
  through to `run_pipeline(verbose=...)`.
- **FR-006**: `pipeline.py`'s `logging.basicConfig()` call changes from
  `level=logging.INFO` to `level=logging.WARNING if not args.verbose else
  logging.INFO` — matching `core/cli.py`'s existing level, now
  symmetrically controllable on both entry points. `core/cli.py`'s own
  `logging.basicConfig()` call gains the same `--verbose`-controlled level.
- **FR-007**: The per-run log handler (FR-003) captures only `WARNING` and
  above — `INFO`/`DEBUG` records are never written to `run.log`, regardless
  of `--verbose` (verbose only affects the *terminal*, not what's
  persisted).
- **FR-008**: In `core/cli.py`'s multi-audience loop, each `run_pipeline()`
  call installs/removes its own handler independently (FR-003 is scoped
  inside `run_pipeline()` itself) — one audience's warnings never leak into
  another audience's `run.log`.

## Key Entities

- No new persistent types — `log_lines` is a plain `list[str]` of already-
  formatted log messages, not a new dataclass.

## Success Criteria

1. Given `verbose=False` (default), `run_pipeline()`'s final print is a
   single `TOTAL: ...` line — no per-agent/per-model sub-lines appear.
2. Given `verbose=True`, the final print matches today's exact
   `format_summary()` output byte-for-byte (regression guard).
3. `summary.txt`/`telemetry.json` content is identical regardless of
   `verbose` — this flag never touches what's saved to the bundle, only
   what's printed and what additionally goes to `run.log`.
4. Given a run that logs at least one `WARNING`, `run.log` exists in the
   bundle directory and contains that message; given a run with zero
   `WARNING`-or-above messages, no `run.log` is created.
5. `run.log` never contains `INFO`- or `DEBUG`-level lines, in either mode.
6. Given `--verbose` is NOT passed, `pipeline.py`'s console shows no
   `INFO`-level lines (e.g. `"credentials loaded..."`) — only `WARNING`+;
   given `--verbose` IS passed, `INFO`-level lines appear, matching
   `pipeline.py`'s current default behaviour today.
7. In `core/cli.py`'s multi-audience loop, each audience's bundle's
   `run.log` contains only that audience's own warnings, never another
   audience's.
8. `python -m pytest tests/` — zero failures.
9. `ruff check . && ruff format .` — exit 0.

## What does NOT change

- `core/cli.py`'s other `print()` calls (credentials-loaded line, humor-
  config-loaded line, per-audience progress header, grand-total summary,
  "Report saved to..."/"All N images saved to...") are unaffected by
  `--verbose` — they're already lightweight, single-line status messages,
  not per-agent/per-model noise, and stay as-is in both modes.
- `_format_grand_total()`'s output (one line per audience + a TOTAL line)
  is already compact — not touched by this spec.
- WARNING-level messages continue to go to stderr as they do today
  (unaffected default `logging.basicConfig` stream) — `run.log` is an
  *additional* capture, not a replacement for stderr.
- No new dependency — the in-memory log handler is a small
  `logging.Handler` subclass using only the stdlib.

## Assumptions

- "Persistent per-run log file inside the bundle" was the explicit,
  confirmed choice over a single rolling `output/gata.log` — accepting the
  buffering complexity (capture in memory, flush once the bundle directory
  is known) as the cost of one-file-per-run tidiness.
- `--verbose`/`-v` restores *today's exact* output — not a new third
  intermediate verbosity tier.
