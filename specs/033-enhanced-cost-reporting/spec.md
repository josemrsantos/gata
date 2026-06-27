# Spec 033 — Enhanced Cost Reporting

**Stage**: 033
**Branch**: `033-enhanced-cost-reporting`
**Status**: In progress

---

## Problem

The current telemetry summary shows one cost line per agent:

```
Cultural Strategist: 35.2s — 1 iteration(s) — $0.0197
Satirist/Co-Satirist: 38.4s — 1 iteration(s) — $0.0260
...
TOTAL: 119.1s — $0.2521
```

There is no visibility into which specific LLM model was responsible for each cost,
and no disclaimer that the figures are estimates.

---

## Goal

Add a per-model breakdown under each agent line and a disclaimer at the end of the
summary. The summary is produced by `bundle_writer.format_summary()` and is both
printed to stdout (via `runner.py`) and written to `summary.txt` in the bundle.

---

## Success Criteria

Running the pipeline produces output of the form:

```
Cultural Strategist: 35.2s — 1 iteration(s) — $0.0197
  claude-sonnet-4-6:   1,234 in / 456 out — $0.0102
  grok-3-mini:           800 in / 320 out — $0.0048
  gemini-2.5-flash:      900 in / 280 out — $0.0047
Satirist/Co-Satirist: 38.4s — 1 iteration(s) — $0.0260
  ...
TOTAL: 119.1s — $0.2521
* Cost figures are estimates based on publicly listed token pricing at time of coding.
```

Rules:
- Multiple calls to the same model within one agent are aggregated (tokens and cost summed).
- Model lines appear in first-call order.
- Agents with zero model calls emit no sub-lines (graceful degradation).
- The disclaimer is always the last line.

---

## Files Changed

| File | Change |
|------|--------|
| `core/bundle_writer.py` | Extend `format_summary()` with per-model sub-lines and disclaimer |
| `core/__version__.py` | Bump to `1.16.0` |
| `tests/test_bundle_writer.py` | New/extended tests for the enhanced format |

## Files NOT Changed

All other files — no agent, protocol, or config changes required.
