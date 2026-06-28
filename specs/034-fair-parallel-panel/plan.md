# Plan: Spec 034 — FairParallelPanel Protocol

## Constitution Check

| Principle | Rule | Status | Notes |
|-----------|------|--------|-------|
| §1 | SDK and model rules | ✅ Pass | No new SDKs; `concurrent.futures` is stdlib |
| §2 | Image output rule | ✅ Pass | No image changes |
| §3 | XML and output contract | ✅ Pass | `<verdict>` tags preserved; round-2 prompt instructs panelists to keep using them |
| §4 | Character rules | ✅ Pass | No prompt template changes |
| §5 | Visual style rules | ✅ Pass | No image prompt changes |
| §6 | Verdict JSON schema | ✅ Pass | Schema unchanged; aggregation format unchanged |
| §7 | Language rule | ✅ Pass | No output-language changes |
| §8 | Project structure | ✅ Pass | New file inside approved `llm/` directory |
| §9 | Testing rules | ✅ Pass | Tests written before implementation (TDD) |
| §10 | Secrets and security | ✅ Pass | No credentials involved |
| §11 | Development stages | ✅ Pass | Branch `034-fair-parallel-panel`, sequential after 033 |
| §12 | Code quality | ✅ Pass | ruff check + format before commit |
| §13 | Logging | ✅ Pass | `logger = logging.getLogger(__name__)`, DEBUG/INFO/WARNING levels per §13 |

---

## Architecture

### `FairParallelPanel` class (new)

```python
class FairParallelPanel(ConversationProtocol):
    def __init__(
        self,
        panelists: list[PersonaConfig],
        aggregator: PersonaConfig,
        panel_name: str = "",
        iterations: int = 2,
        panelist_timeout: float = 60.0,
    ) -> None: ...

    def run(self, initial_input: str) -> LoopOutput: ...
```

Inherits `_call_persona()` pattern from `ParallelPanel` (copy, not inherit — keeps
each class independent).

### Round execution helper

```python
def _run_round(
    self,
    panelists: list[PersonaConfig],
    messages_per_panelist: list[list[dict]],
) -> list[tuple[str, str, TokenUsage] | None]:
    # Submits all panelists to ThreadPoolExecutor, collects with timeout.
    # Returns None for each panelist that timed out or raised.
```

Uses `concurrent.futures.ThreadPoolExecutor(max_workers=len(panelists))`.
Per-panelist `Future.result(timeout=self._panelist_timeout)` raises `TimeoutError`
on timeout — caught and logged as WARNING, slot becomes `None`.

### Round-2+ prompt builder

```python
def _build_peer_prompt(
    self,
    initial_input: str,
    my_previous: str,
    peer_responses: list[tuple[str, str]],  # (name, response)
) -> str:
    # Constructs the composite prompt for subsequent rounds.
```

---

## Implementation sequence (TDD)

### Phase 1 — Tests (`tests/test_fair_parallel_panel.py`)

Write these tests BEFORE any implementation:

| # | Test | What it checks |
|---|------|---------------|
| 1 | `test_single_iteration_single_panelist` | `iterations=1`, 1 panelist → same output flow as `ParallelPanel` |
| 2 | `test_single_iteration_three_panelists` | `iterations=1`, 3 panelists → aggregator gets all 3 concepts |
| 3 | `test_second_round_uses_peer_responses` | `iterations=2` → round-2 prompt contains other panelists' round-1 `<verdict>` text |
| 4 | `test_timed_out_panelist_skipped` | Panelist `Future.result()` raises `TimeoutError` → skipped, run completes |
| 5 | `test_failed_panelist_skipped` | Panelist raises `RuntimeError` → skipped, run completes |
| 6 | `test_all_panelists_fail_raises` | All panelists fail → `RuntimeError` raised |
| 7 | `test_single_survivor_skips_sharing` | 1 panelist survives round 1 → no peer content in round 2 |
| 8 | `test_telemetry_aggregates_all_rounds` | `AgentTelemetry.calls` includes token usage from every round + aggregator |
| 9 | `test_panelist_timeout_default` | Default `panelist_timeout` is 60.0 |
| 10 | `test_iterations_default` | Default `iterations` is 2 |
| 11 | `test_log_contains_round_markers` | `ConversationLog` turns have iteration numbers reflecting actual rounds |
| 12 | `test_aggregator_receives_final_round_responses` | Aggregator prompt contains final-round verdicts, not round-1 verdicts |

### Phase 2 — Implementation

1. `llm/fair_parallel_panel.py` — `FairParallelPanel` class
2. `llm/__init__.py` — export
3. `agents/agent_cultural_strategist.py` — swap `ParallelPanel` → `FairParallelPanel`
4. `agents/agent_satirist.py` — swap
5. `agents/agent_explainer.py` — swap
6. `core/__version__.py` — bump to `1.17.0`

### Phase 3 — Verification

- `python -m pytest tests/` — zero failures
- `ruff check . && ruff format .` — exit 0
- Live run — log shows "round 1" and "round 2" panelist calls before aggregation
- Check that a panelist timeout (inject one) is caught, logged as WARNING, run continues

---

## Complexity Notes

- `concurrent.futures.ThreadPoolExecutor` is stdlib — no new dependency
- Mock strategy in tests: patch `_call_persona` to return fast or raise; mock `Future`
  via `unittest.mock` or patch `ThreadPoolExecutor.submit` to control timing
- The round-2 prompt format must preserve `<verdict>` instruction so the aggregator
  can still parse the response (§3 compliance)
- `panelists` list order determines display order in peer messages — stable
- **Spec 032 (cross-provider fallback) compatibility:** `panelist_timeout=60.0` is
  deliberately sized so that if the primary provider fails after ~20s, the Spec 032
  fallback chain still has ~40s to complete. Never set this below the slowest expected
  primary-provider call time (Claude Sonnet observed at 15–20s per call).
