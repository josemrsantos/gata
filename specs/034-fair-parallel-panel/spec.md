# Spec 034 — FairParallelPanel Protocol

**Stage**: 034
**Branch**: `034-fair-parallel-panel`
**Status**: Draft — awaiting approval
**Dependency**: Spec 032 ✅

---

## Problem

The current `ParallelPanel` protocol calls panelists sequentially, gives each panelist
only the original topic (no exposure to peers' thinking), and has no timeout per panelist.
A slow or hung provider holds up the entire panel.

Additionally, because panelists never see each other's responses, there is no collaborative
refinement — the best idea wins, but a weaker idea cannot improve by seeing the stronger one.

---

## Goal

Implement `FairParallelPanel`: a multi-round coordination protocol where panelists run in
parallel threads, respond within a configurable timeout, and — in subsequent rounds —
receive all on-time peers' previous responses as context before finalising their proposal.
After the last round, the aggregator LLM picks the winner as before.

---

## Behaviour

### Round 1

All panelists receive the original `initial_input` and are called concurrently using
`concurrent.futures.ThreadPoolExecutor`. Any panelist that:
- raises an exception from its provider chain, OR
- does not respond within `panelist_timeout` seconds

…is logged as a warning and **skipped** for all subsequent rounds.

**Cross-provider fallback compatibility (Spec 032):** the `panelist_timeout` applies to
the *entire* panelist slot — including any fallback providers. Based on observed latencies
(Claude ~15–20s, Grok-mini ~5–7s, Gemini Flash ~3–10s), a 60s slot budget gives enough
room for a primary provider to fail (at ~20s) and a fallback to still complete. This
ensures Spec 032's cross-provider chains remain effective rather than being cut short.

### Rounds 2 … N (where N = `iterations`)

For each surviving panelist, a composite prompt is built:

```
Original request:
{initial_input}

Your previous proposal:
{my_round_N_minus_1_response}

Other panelists proposed:

--- Panelist: {peer_name} ---
{peer_round_N_minus_1_response}

[… one block per other surviving panelist …]

Given the perspectives above, please revise your proposal or confirm it stands.
Wrap your final response in <verdict>…</verdict> tags as before.
```

Panelists are again called concurrently with the same `panelist_timeout`. A panelist
that times out or fails in a later round is skipped for that round's output, but its
last-successful response is still offered to the aggregator.

If only one panelist survives round 1, the sharing step is skipped (no peers to share).

### Aggregation

After the final round, the aggregator receives all surviving panelists' final-round
responses (same numbered-concept message format as current `ParallelPanel`). If no
panelist survived any round, `RuntimeError` is raised.

---

## Parameters

| Parameter | Type | Default | Meaning |
|-----------|------|---------|---------|
| `panelists` | `list[PersonaConfig]` | — | Panelist personas (unchanged from ParallelPanel) |
| `aggregator` | `PersonaConfig` | — | Aggregator persona (unchanged) |
| `panel_name` | `str` | `""` | Display name for logs (unchanged) |
| `iterations` | `int` | `2` | Number of exchange rounds (1 = single round, same as ParallelPanel) |
| `panelist_timeout` | `float` | `60.0` | Per-panelist slot seconds before a round call is abandoned; sized to let a primary provider fail (~20s) and a Spec 032 fallback still complete |

---

## Files Changed

| File | Change |
|------|--------|
| `llm/fair_parallel_panel.py` | NEW — `FairParallelPanel(ConversationProtocol)` |
| `llm/__init__.py` | Export `FairParallelPanel` |
| `agents/agent_cultural_strategist.py` | Switch from `ParallelPanel` to `FairParallelPanel` |
| `agents/agent_satirist.py` | Switch from `ParallelPanel` to `FairParallelPanel` |
| `agents/agent_explainer.py` | Switch from `ParallelPanel` to `FairParallelPanel` |
| `core/__version__.py` | Bump to `1.17.0` |
| `tests/test_fair_parallel_panel.py` | NEW — protocol tests |

## Files NOT Changed

- `llm/parallel_panel.py` — kept as-is for backward compatibility
- `llm/dual_loop.py` — no change
- `core/runner.py`, `pipeline.py` — no change (agents own the protocol choice)

---

## Success Criteria

1. `python -m pytest tests/` — zero failures
2. `ruff check . && ruff format .` — exit 0
3. Live run with `iterations=2` logs two rounds of panelist activity before aggregation
4. A panelist that exceeds `panelist_timeout` is skipped and the run still completes
5. Round-2 prompts contain other panelists' round-1 `<verdict>` content
