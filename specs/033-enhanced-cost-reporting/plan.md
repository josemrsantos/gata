# Plan: Spec 033 — Enhanced Cost Reporting

## Constitution Check

| Principle | Rule | Status | Notes |
|-----------|------|--------|-------|
| §1 | SDK and model rules | ✅ Pass | No new providers or models |
| §2 | Image output rule | ✅ Pass | No image changes |
| §3 | XML and output contract | ✅ Pass | No inter-agent message changes |
| §4 | Character rules | ✅ Pass | No prompt changes |
| §5 | Visual style rules | ✅ Pass | No image prompt changes |
| §6 | Verdict JSON schema | ✅ Pass | No schema changes |
| §7 | Language rule | ✅ Pass | No output-language changes |
| §8 | Project structure | ✅ Pass | No new directories |
| §9 | Testing rules | ✅ Pass | Tests written before implementation |
| §10 | Secrets and security | ✅ Pass | No credentials involved |
| §11 | Development stages | ✅ Pass | New branch `033-enhanced-cost-reporting` |
| §12 | Code quality | ✅ Pass | ruff check + format before commit |
| §13 | Logging | ✅ Pass | `format_summary()` returns str; print is in runner.py (pre-existing) |

---

## Design

### `format_summary()` — new behaviour

```python
def format_summary(telemetry: RunTelemetry) -> str:
    lines = []
    for a in telemetry.agents:
        lines.append(
            f"{a.agent_name}: {a.duration_seconds:.1f}s"
            f" — {a.iterations} iteration(s) — ${a.total_cost_usd:.4f}"
        )
        # Aggregate multiple calls to the same model (retry / fallback case)
        model_order: list[str] = []
        model_totals: dict[str, tuple[int, int, float]] = {}
        for call in a.calls:
            if call.model not in model_totals:
                model_order.append(call.model)
                model_totals[call.model] = (0, 0, 0.0)
            prev = model_totals[call.model]
            model_totals[call.model] = (
                prev[0] + call.input_tokens,
                prev[1] + call.output_tokens,
                prev[2] + call.cost_usd,
            )
        for model in model_order:
            in_t, out_t, cost = model_totals[model]
            lines.append(f"  {model}: {in_t:,} in / {out_t:,} out — ${cost:.4f}")
    lines.append("")
    lines.append(
        f"TOTAL: {telemetry.total_duration_seconds:.1f}s"
        f" — ${telemetry.total_cost_usd:.4f}"
    )
    lines.append(
        "* Cost figures are estimates based on publicly listed token pricing"
        " at time of coding."
    )
    return "\n".join(lines)
```

---

## Tasks

### Phase 1 — Tests (TDD)

- [ ] Write tests for enhanced `format_summary()` in `tests/test_bundle_writer.py`
  - Single agent, single model call — sub-line appears with correct values
  - Single agent, two calls to same model — tokens and costs are aggregated
  - Single agent, two different models — both sub-lines appear in order
  - Multiple agents — each has its own sub-lines
  - Agent with zero calls — no sub-lines, no crash
  - Disclaimer is always the last line

### Phase 2 — Implementation

- [ ] Update `format_summary()` in `core/bundle_writer.py`
- [ ] Bump version to `1.16.0` in `core/__version__.py`

### Phase 3 — Verification

- [ ] `python -m pytest tests/` — zero failures
- [ ] `ruff check . && ruff format .` — exit 0
- [ ] Generate image and confirm per-model breakdown appears in stdout and `summary.txt`
