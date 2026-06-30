# Spec 036 — Per-Provider Call Timeout

**Stage**: 036
**Branch**: `036-per-provider-timeout`
**Status**: Draft — awaiting approval
**Dependency**: Spec 032 ✅, Spec 034 ✅

---

## Problem

`FairParallelPanel` has a single `panelist_timeout` (60s) that covers the entire
panelist slot — primary provider call plus all fallback providers in the Spec 032
chain. The slot budget is shared opaquely:

- If Claude Sonnet hangs for 55s, the next provider in the chain (e.g. Grok-3-mini)
  has only 5s remaining — enough for Grok-mini but not for Claude or Grok-3.
- There is no way to configure a per-provider timeout from `providers.yaml` or
  any other config without editing source code.

## Goal

Add an optional `timeout` field to each entry in `providers.yaml`. When set, that
provider's `generate()` call is wrapped in its own `ThreadPoolExecutor` future with
that timeout. If it exceeds the budget, the next provider in the chain is tried
with a full budget of its own.

The timeout travels with the provider object (`LLMProvider.timeout`), so it works
automatically in `_call_persona()` without any new CLI flags or constructor changes
to `FairParallelPanel`.

When `timeout` is absent from `providers.yaml` (or when using built-in defaults),
behaviour is identical to today — no overhead, no regression.

---

## Behaviour

### Without `timeout` in `providers.yaml` (default — unchanged)

```
slot starts
  → provider A: generate() called directly, no time limit
  → if A raises → provider B: generate() called directly, no time limit
  → ...
slot ends (panelist_timeout governs the outer future)
```

### With `timeout: 25.0` on each provider

```yaml
panelists:
  - - provider: claude
      model: claude-sonnet-4-6
      timeout: 25.0
    - provider: grok
      model: grok-3-mini
      timeout: 10.0
```

```
slot starts
  → provider A (timeout=25.0): generate() wrapped in 1-worker executor, 25s limit
    → A completes in time  → return result ✓
    → A times out (25s)   → log WARNING, try provider B
    → A raises exception  → log WARNING, try provider B
  → provider B (timeout=10.0): generate() wrapped in 1-worker executor, 10s limit
    → B completes in time  → return result ✓
    → ...
  → all providers exhausted → raise RuntimeError
slot ends (panelist_timeout still the hard ceiling for the outer slot)
```

Each provider gets its own dedicated budget. The outer `panelist_timeout` (60s)
remains as the hard ceiling for the whole slot.

---

## Recommended values (from observed latencies)

| Provider + model | Observed latency | Suggested `timeout` |
|------------------|-----------------|---------------------|
| claude-sonnet-4-6 | 15–20s | 25.0 |
| grok-3 | 10–15s | 20.0 |
| grok-3-mini | 5–7s | 12.0 |
| gemini-2.5-flash | 3–10s | 15.0 |
| gemini-2.5-pro | 15–22s | 30.0 |

---

## Design

### Layer 1 — `providers.yaml`

Add optional `timeout` (seconds, float) per provider entry. Absent = no timeout.

```yaml
panelists:
  - - provider: claude
      model: claude-sonnet-4-6
      timeout: 25.0        # optional; omit for unbounded
    - provider: gemini
      model: gemini-2.5-flash
      timeout: 15.0
    - provider: grok
      model: grok-3-mini
      timeout: 10.0
  ...
aggregator:
  - provider: grok
    model: grok-3
    timeout: 20.0
  - provider: claude
    model: claude-sonnet-4-6
    timeout: 25.0
  ...
```

### Layer 2 — `core/types.py` → `ModelSpec`

Add one field:

```python
@dataclass
class ModelSpec:
    provider: str
    model: str
    timeout: float | None = None    # NEW — per-call limit; None = unbounded
```

### Layer 3 — `llm/base.py` → `LLMProvider` ABC

Add abstract property:

```python
@property
@abstractmethod
def timeout(self) -> float | None: ...
```

### Layer 4 — `llm/claude.py`, `llm/gemini.py`, `llm/grok.py`

Each `__init__` gains `timeout: float | None = None`:

```python
def __init__(self, model: str, timeout: float | None = None) -> None:
    self._model = model
    self._timeout = timeout

@property
def timeout(self) -> float | None:
    return self._timeout
```

### Layer 5 — `core/runner.py` → `_build_provider()`

Pass `timeout` from spec:

```python
def _build_provider(spec: ModelSpec) -> LLMProvider:
    if spec.provider == "claude":  return ClaudeProvider(spec.model, timeout=spec.timeout)
    if spec.provider == "gemini":  return GeminiProvider(spec.model, timeout=spec.timeout)
    if spec.provider == "grok":    return GrokProvider(spec.model, timeout=spec.timeout)
    raise ValueError(f"unknown provider: {spec.provider}")
```

### Layer 6 — `core/config_loader.py` → `_parse_spec()`

Parse the optional `timeout` field:

```python
timeout_raw = item.get("timeout")
if timeout_raw is not None:
    if not isinstance(timeout_raw, (int, float)) or timeout_raw <= 0:
        raise ValueError(f"{path}: {context} timeout must be a positive number")
timeout = float(timeout_raw) if timeout_raw is not None else None
return ModelSpec(provider=provider, model=model, timeout=timeout)
```

### Layer 7 — `llm/fair_parallel_panel.py` → `_call_persona()`

Read `provider.timeout`; wrap in executor only when set:

```python
def _call_persona(self, persona, messages):
    for provider in persona.providers:
        try:
            if provider.timeout is None:
                # No timeout configured — call directly, no executor overhead.
                return provider.generate(
                    persona.system_prompt, messages, max_tokens=persona.max_tokens
                )
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(
                    provider.generate,
                    persona.system_prompt,
                    messages,
                    max_tokens=persona.max_tokens,
                )
                return future.result(timeout=provider.timeout)
        except concurrent.futures.TimeoutError:
            logger.warning(
                "%s: provider %s exceeded %ss — trying next provider",
                persona.name,
                provider.model_id,
                provider.timeout,
            )
        except Exception as exc:
            logger.warning(
                "%s: provider %s failed — %s — trying next provider",
                persona.name,
                provider.model_id,
                exc,
            )
    raise RuntimeError(f"all providers exhausted for {persona.name}")
```

No change to `FairParallelPanel.__init__` — no new constructor arg needed.

---

## Files Changed

| File | Change |
|------|--------|
| `providers.yaml` | ADD optional `timeout` field to each entry (example values) |
| `core/types.py` | ADD `timeout: float \| None = None` to `ModelSpec` |
| `llm/base.py` | ADD abstract `timeout` property to `LLMProvider` |
| `llm/claude.py` | ADD `timeout` arg to `__init__` + property |
| `llm/gemini.py` | ADD `timeout` arg to `__init__` + property |
| `llm/grok.py` | ADD `timeout` arg to `__init__` + property |
| `core/config_loader.py` | PARSE optional `timeout` in `_parse_spec()` |
| `core/runner.py` | PASS `timeout=spec.timeout` in `_build_provider()` |
| `llm/fair_parallel_panel.py` | READ `provider.timeout` in `_call_persona()` |
| `core/__version__.py` | Bump to `1.19.0` |
| `tests/test_fair_parallel_panel.py` | ADD per-provider timeout tests |
| `tests/test_config_loader.py` | ADD timeout parsing tests |

## Files NOT Changed

- `pipeline.py`, `core/cli.py` — no new flags; timeout is config-driven, not CLI-driven
- `agents/agent_*.py` — unchanged; `PersonaConfig.providers` type stays `list[LLMProvider]`
- `FairParallelPanel.__init__` — no new arg; timeout lives on the provider object

---

## Key Design Properties

- **Zero regression**: built-in default providers are constructed with `timeout=None`; `_call_persona()` takes the direct path — no executor, no overhead.
- **Per-model precision**: Claude can get 25s, Grok-mini 10s, within the same panelist slot — actual latency characteristics matched to each model.
- **Config-only**: no code changes needed to tune or disable timeouts; edit `providers.yaml`.
- **`panelist_timeout` still the hard ceiling**: if per-provider timeouts are generous and a chain runs long, the outer 60s slot budget still terminates the slot.

---

## Success Criteria

1. `timeout: 25.0` in `providers.yaml` → provider exceeding 25s is abandoned and next tried
2. `timeout` omitted → no executor overhead, identical to current behaviour
3. Second provider in chain gets its own full budget (not leftover from first)
4. `load_providers_config()` rejects non-positive timeout values with a clear error
5. `python -m pytest tests/` — zero failures
6. `ruff check . && ruff format .` — exit 0
