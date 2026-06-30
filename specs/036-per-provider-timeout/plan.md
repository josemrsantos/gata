# Plan: Spec 036 — Per-Provider Call Timeout

## Constitution Check

| Principle | Rule | Status | Notes |
|-----------|------|--------|-------|
| §1 | SDK and model rules | ✅ Pass | No new SDKs; `concurrent.futures` already imported |
| §2 | Image output rule | ✅ Pass | No image changes |
| §3 | XML and output contract | ✅ Pass | `<verdict>` tags unchanged |
| §4 | Character rules | ✅ Pass | No prompt changes |
| §5 | Visual style rules | ✅ Pass | No image prompt changes |
| §6 | Verdict JSON schema | ✅ Pass | Schema unchanged |
| §7 | Language rule | ✅ Pass | No output-language changes |
| §8 | Project structure | ✅ Pass | All changes inside existing files |
| §9 | Testing rules | ✅ Pass | Tests written before implementation (TDD) |
| §10 | Secrets and security | ✅ Pass | No credentials involved |
| §11 | Development stages | ✅ Pass | Branch `036-per-provider-timeout` |
| §12 | Code quality | ✅ Pass | ruff check + format before commit |
| §13 | Logging | ✅ Pass | Timeout logged at WARNING, matching existing pattern |

---

## Implementation Sequence (TDD — tests before code)

### Phase 1 — Tests

#### `tests/test_config_loader.py` — add 3 tests

| # | Test | What it checks |
|---|------|----------------|
| 1 | `test_providers_timeout_parsed` | `timeout: 25.0` in YAML → `ModelSpec.timeout == 25.0` |
| 2 | `test_providers_timeout_absent_is_none` | Entry without `timeout` → `ModelSpec.timeout is None` |
| 3 | `test_providers_timeout_invalid_raises` | `timeout: -5` and `timeout: "abc"` both raise `ValueError` |

#### `tests/test_fair_parallel_panel.py` — add 4 tests

| # | Test | What it checks |
|---|------|----------------|
| 4 | `test_per_provider_timeout_none_calls_directly` | `provider.timeout=None` → `generate()` called without executor |
| 5 | `test_per_provider_timeout_fires_tries_next` | First provider's `generate()` raises `TimeoutError`; second provider succeeds |
| 6 | `test_per_provider_timeout_second_gets_full_budget` | After first provider times out, second is attempted (not skipped) |
| 7 | `test_per_provider_timeout_all_timeout_raises` | All providers time out → `RuntimeError("all providers exhausted")` |

---

### Phase 2 — Implementation order

1. `core/types.py` — add `timeout: float | None = None` to `ModelSpec`
2. `llm/base.py` — add abstract `timeout` property to `LLMProvider`
3. `llm/claude.py` — add `timeout` arg + property
4. `llm/gemini.py` — add `timeout` arg + property
5. `llm/grok.py` — add `timeout` arg + property
6. `core/config_loader.py` — parse optional `timeout` in `_parse_spec()`
7. `core/runner.py` — pass `timeout=spec.timeout` in `_build_provider()`
8. `llm/fair_parallel_panel.py` — read `provider.timeout` in `_call_persona()`
9. `providers.yaml` — add commented-out `timeout` examples showing syntax (leave values absent so live behaviour is unchanged until the user deliberately opts in)
10. `core/__version__.py` — bump to `1.19.0`

---

### Phase 3 — Verification

- `python -m pytest tests/` — zero failures
- `ruff check . && ruff format .` — exit 0

---

## `_call_persona()` detailed logic (RULE 14 compliance)

```
for provider in persona.providers:
    # provider.timeout is None → no executor, direct call (current behaviour)
    # provider.timeout is set → wrap in 1-worker executor for this provider only

    if provider.timeout is None:
        try:
            return provider.generate(...)
        except Exception: log + continue

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(provider.generate, ...).result(timeout=provider.timeout)
    except concurrent.futures.TimeoutError: log + continue
    except Exception: log + continue

raise RuntimeError("all providers exhausted")
```

No blank lines between phases inside the function body (RULE 14).

---

## Test mock strategy

Tests for `_call_persona()` with per-provider timeouts use the existing `_CallMock`
pattern from the file, with providers carrying a `.timeout` attribute:

```python
class _MockProvider:
    def __init__(self, response, timeout=None):
        self._response = response
        self._timeout = timeout

    @property
    def model_id(self): return "mock"

    @property
    def timeout(self): return self._timeout

    def generate(self, system, messages, max_tokens=None):
        if isinstance(self._response, BaseException):
            raise self._response
        return self._response
```

For `test_per_provider_timeout_fires_tries_next`: the per-provider `TimeoutError` is
raised by `future.result(timeout=...)`, NOT by `generate()` itself. To test this path
correctly, patch `concurrent.futures.Future.result` to raise
`concurrent.futures.TimeoutError`. Raising it from `generate()` directly would land in
`except Exception`, not `except concurrent.futures.TimeoutError`, which tests the wrong
branch.

---

## Complexity Notes

- `LLMProvider` is an ABC (not a `Protocol`), so adding an abstract property requires all three concrete subclasses to implement it. This is intentional — a provider without an explicit `timeout` decision is incomplete.
- `timeout=None` is the correct default in all three providers — it preserves current behaviour for built-in defaults (which don't go through `_build_provider()`).
- When a future times out, the underlying thread keeps running until `generate()` returns (Python threads are non-preemptive). The `with ThreadPoolExecutor` block waits for the thread on exit, but the thread will eventually complete or raise a network error. This is the same trade-off as the outer `panelist_timeout`.
- `FairParallelPanel.__init__` is NOT changed — no new arg. Timeout lives on the provider, not the panel.
