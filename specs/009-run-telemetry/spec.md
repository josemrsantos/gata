# Feature Specification: Run Telemetry — per-agent timing, token counts, cost estimate

**Feature Branch**: `010-run-telemetry`
**Created**: 2026-06-14
**Status**: Draft

## Summary

After each pipeline run, write a `telemetry.json` file to the output bundle. It records
how long each agent took, how many tokens each LLM call consumed, which model was used,
and an estimated USD cost derived from published per-token rates. No new flags or
configuration are required; telemetry is always on.

## User Scenarios & Testing

### User Story 1 — telemetry.json appears in every bundle (Priority: P1)

After any pipeline run (`python pipeline.py ...` or `gata ...`) the bundle folder contains
a `telemetry.json` alongside the existing files.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the bundle folder is inspected, **Then**
   `telemetry.json` is present.
2. **Given** `telemetry.json`, **When** parsed, **Then** it contains
   `total_duration_seconds`, `total_cost_usd`, `total_input_tokens`,
   `total_output_tokens`, and an `agents` array.
3. **Given** an `agents` entry, **When** inspected, **Then** it contains `agent`,
   `duration_seconds`, `iterations`, `total_input_tokens`, `total_output_tokens`,
   `total_cost_usd`, and a `calls` array.
4. **Given** a `calls` entry, **When** inspected, **Then** it contains `model`,
   `input_tokens`, `output_tokens`, `cost_usd`.

---

### User Story 2 — telemetry survives a partial pipeline failure (Priority: P1)

If an agent fails partway through a run, telemetry for the agents that did complete is
still written to the bundle.

**Acceptance Scenarios**:

1. **Given** Cultural Strategist succeeds and Satirist fails, **When** the bundle is
   written, **Then** `telemetry.json` contains the Cultural Strategist entry and no
   Satirist entry.

---

### Edge Cases

- If the Anthropic or Gemini SDK does not return usage metadata for a call (SDK bug or
  model not supporting it), the call is recorded with `input_tokens: 0`,
  `output_tokens: 0`, `cost_usd: 0.0` rather than raising.
- Unknown model names not in the pricing table produce `cost_usd: 0.0` rather than
  raising.

## Technical Design

### New / changed types (`agents/types.py`)

| Type | Purpose |
|------|---------|
| `TokenUsage` | Single LLM call: model, input_tokens, output_tokens, cost_usd |
| `AgentTelemetry` | One agent's full run: name, duration, iterations, list of TokenUsage |
| `RunTelemetry` | Aggregates all AgentTelemetry for a complete pipeline run |
| `LoopOutput.telemetry` | New optional field — populated by `DualPersonaLoop.run()` |

### Pricing table

Stored as `_COST_PER_M` dict in `agents/types.py` — `(input_usd_per_m, output_usd_per_m)`
per model name. Image generation models are listed with `(0.0, 0.0)` as they are billed
per image, not per token. Unknown models default to `(0.0, 0.0)`.

### Changed call chains

```
_call_model()          → tuple[str, TokenUsage]
_call_persona()        → tuple[str, TokenUsage]
DualPersonaLoop.run()  → LoopOutput  (telemetry field populated)
agent_cultural_strategist.run() → tuple[EnrichedBrief, ConversationLog, AgentTelemetry]
agent_satirist.run()            → tuple[CartoonConcept, ConversationLog, AgentTelemetry]
agent_image_generator.generate() → tuple[str, AgentTelemetry]
runner.run_pipeline()           → None  (collects telemetry, passes to bundle_writer)
bundle_writer.write_bundle()    → str   (accepts optional RunTelemetry, writes telemetry.json)
```

### Output format (`telemetry.json`)

```json
{
  "total_duration_seconds": 45.2,
  "total_input_tokens": 5200,
  "total_output_tokens": 2100,
  "total_cost_usd": 0.0412,
  "agents": [
    {
      "agent": "Agent 0",
      "duration_seconds": 18.3,
      "iterations": 2,
      "total_input_tokens": 1800,
      "total_output_tokens": 700,
      "total_cost_usd": 0.016,
      "calls": [
        {"model": "claude-sonnet-4-6", "input_tokens": 900, "output_tokens": 350, "cost_usd": 0.008}
      ]
    }
  ]
}
```

### Modified files

| File | Change |
|------|--------|
| `agents/types.py` | Add `TokenUsage`, `AgentTelemetry`, `RunTelemetry`, `compute_cost()`; extend `LoopOutput` |
| `agents/dual_loop.py` | `_call_model` / `_call_persona` return token usage; `run()` builds telemetry |
| `agents/agent_cultural_strategist.py` | Return `AgentTelemetry` as third element |
| `agents/agent_satirist.py` | Return `AgentTelemetry` as third element |
| `agents/agent_image_generator.py` | Track timing; return `(path, AgentTelemetry)` |
| `agents/runner.py` | Collect all telemetry, pass `RunTelemetry` to `bundle_writer` |
| `agents/bundle_writer.py` | Accept optional `RunTelemetry`; write `telemetry.json` |
| `pyproject.toml` | Bump version to `1.1.0` |
| `agents/__version__.py` | Bump to `1.1.0` |
