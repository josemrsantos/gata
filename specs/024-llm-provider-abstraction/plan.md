# Implementation Plan: LLM Provider Abstraction + Project Restructure

**Branch**: `024-llm-provider-abstraction` | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

## Summary

Introduce a `llm/` top-level package with provider classes (Claude, Gemini), move
`dual_loop.py` into `llm/`, create a `core/` package for pipeline infrastructure, and
strip `agents/` down to Gata agents only. All imports updated throughout. No agent logic,
system prompts, or CLI behaviour changes.

## Constitution Check

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | SDK usage moves into provider classes; same models used |
| 2 | Image Output Rule | ✅ | agent_image_generator unchanged |
| 3 | XML Contract | ✅ | No change to verdict tags or parsing |
| 4 | Character Rules | ✅ | No change to prompts |
| 5 | Visual Style Rules | ✅ | No change to prompts |
| 6 | Dual-Persona Iteration Rules | ✅ | Loop logic unchanged; providers replace model strings |
| 7 | Language Rule | ✅ | No change |
| 8 | Project Structure | ⚠️ RESTRUCTURE | Justified — this spec exists to fix the structure |
| 9 | Testing Rules | ✅ | All tests updated; mock targets change from _call_model to provider.generate() |
| 10 | Secrets and Security | ✅ | Each provider reads its own key; no new exposure |
| 11 | Development Stages | ✅ | Stage 024; branch created |
| 12 | Code Quality | ✅ | ruff must pass before any task is marked complete |
| 13 | Logging | ✅ | No change to logging |

## Technical Context

**Language/Version**: Python 3.10+
**New top-level packages**: `llm/`, `core/`
**pyproject.toml**: packages include, entry point, and version variable path all update
**Circular import**: `core/types.py` uses `from __future__ import annotations` +
`TYPE_CHECKING` to reference `LLMProvider` without a runtime import cycle

## Architecture Decisions

### Provider injection strategy

Agents that run through `runner.py` receive provider lists as function arguments.
Runner.py creates provider instances once. Standalone utility functions (trend_scout,
infer_audiences) instantiate their own `GeminiProvider` internally — they are not
called through runner.py and don't need injection.

### Direct Gemini calls (non-loop)

`agent_cultural_strategist.py` and `agent_image_evaluator.py` make direct Gemini calls
with special config (search grounding, image content). These agents receive a
`GeminiProvider` and access `provider.client` for the non-loop calls. The provider still
owns credential handling and client lifecycle.

### PersonaConfig.providers vs list[str]

`PersonaConfig.providers: list[LLMProvider]` replaces `models: list[str]`.
DualPersonaLoop iterates providers and calls `provider.generate()` — no more
`if model.startswith("claude")` branching.

### cost table ownership

Each provider class owns the rates for its models. `_COST_PER_M` and `compute_cost()`
removed from `core/types.py`. `TokenUsage.cost_usd` is computed inside `generate()`.

## Project Structure (target)

```
llm/
    __init__.py
    base.py          # LLMProvider ABC
    claude.py        # ClaudeProvider + cost table
    gemini.py        # GeminiProvider + cost table; exposes .client for special calls
    dual_loop.py     # moved + refactored; uses provider.generate()

agents/
    __init__.py
    agent_cultural_strategist.py   # updated imports + accepts providers
    agent_explainer.py             # updated imports + accepts providers
    agent_image_evaluator.py       # updated imports + accepts GeminiProvider
    agent_image_generator.py       # updated imports only (keeps own client)
    agent_satirist.py              # updated imports + accepts providers
    trend_scout.py                 # updated imports; creates own GeminiProvider internally
    sources/                       # unchanged

core/
    __init__.py
    __version__.py
    cli.py
    types.py         # PersonaConfig.providers: list[LLMProvider]; no compute_cost
    config_loader.py
    runner.py        # creates provider instances, injects into agents
    humor_utils.py
    bundle_writer.py

pipeline.py          # imports updated
pyproject.toml       # packages, entry point, version variable updated
```

## Tasks

See [tasks.md](tasks.md).
