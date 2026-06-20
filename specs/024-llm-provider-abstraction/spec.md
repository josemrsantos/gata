# Feature Specification: LLM Provider Abstraction + Project Restructure

**Spec**: `024-llm-provider-abstraction`
**Created**: 2026-06-20
**Status**: Draft

## Problem

Two problems that share the same root cause (no architectural separation of concerns):

### 1. LLM calls are scattered

API calls are spread across five modules (`dual_loop.py`, `agent_cultural_strategist.py`,
`trend_scout.py`, `agent_image_evaluator.py`, `agent_satirist.py`). Each module holds its
own lazy SDK client, its own SDK import, and relies on a shared cost table in `types.py`.
Adding a new provider (e.g. Grok) requires touching every module that routes calls.

### 2. `agents/` is not an agents folder

The current `agents/` package contains Gata agents alongside unrelated infrastructure:
pipeline runner, data types, config loader, dual-loop engine, humor utilities, bundle
writer, news source adapters, and the CLI entry point. This makes the folder name
misleading and the project structure hard to navigate.

## Goal

1. Create a dedicated top-level `llm/` package for LLM provider classes. Each provider
   owns its SDK client, credential check, cost table, and `generate()` call. Grok or any
   future provider is added by creating one new file in `llm/` — no existing agent code
   changes.
2. Restructure the project so folder names match what they contain:
   - `agents/` — Gata agents only
   - `llm/` — LLM provider classes (and future inter-LLM communication protocols)
   - `core/` — pipeline infrastructure shared by agents and the CLI

## Folder name: `llm/`

`llm/` is a top-level Python package alongside `agents/` and `core/`. It is intentionally
not nested inside `agents/` — LLM providers are infrastructure, not Gata agents. The
folder is named for what it contains now and what it will grow into: the place where LLM
provider classes live and where, in a future spec, the protocol that lets multiple LLMs
communicate with each other will be defined.

## Target project structure

```
llm/                        # NEW — LLM providers and future inter-LLM protocols
    __init__.py
    base.py                 # LLMProvider abstract base class
    claude.py               # ClaudeProvider + Claude cost table
    gemini.py               # GeminiProvider + Gemini text-model cost table
    dual_loop.py            # DualPersonaLoop — the first inter-LLM protocol

agents/                     # Gata agents ONLY — all non-agent files removed
    __init__.py
    agent_cultural_strategist.py
    agent_explainer.py
    agent_image_evaluator.py
    agent_image_generator.py
    agent_satirist.py
    trend_scout.py
    sources/                # news source adapters — used only by trend_scout.py; unchanged
        __init__.py
        base.py             # SourceAdapter abstract base
        newsapi.py          # NewsAPI.org adapter

core/                       # NEW — pipeline infrastructure (moved from agents/)
    __init__.py
    __version__.py
    cli.py                  # entry point for the gata command
    types.py
    config_loader.py
    runner.py               # composition root — creates providers, wires agents
    humor_utils.py
    bundle_writer.py

pipeline.py                 # unchanged — CLI entry for pipeline.py direct use
communities.yaml
humor.yaml
pyproject.toml
```

## LLM provider design

### Base class (`llm/base.py`)

```python
from abc import ABC, abstractmethod
from core.types import TokenUsage

class LLMProvider(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> tuple[str, TokenUsage]: ...
```

`generate()` returns the response text plus a fully-populated `TokenUsage` (including
`cost_usd`) so callers never compute cost themselves.

### `ClaudeProvider` (`llm/claude.py`)

- Holds the Claude cost table for all supported model IDs.
- Lazily initialises `anthropic.Anthropic()` on first `generate()` call.
- Raises `RuntimeError` on API failure so the caller's fallback chain can catch it.

### `GeminiProvider` (`llm/gemini.py`)

- Holds the Gemini text-model cost table (flash, pro, flash-lite variants).
- Lazily initialises `genai.Client()` on first `generate()` call.
- Image-generation models are **not included** here — `agent_image_generator.py` returns
  binary data via a fundamentally different code path and manages its own Gemini client.

### Cost tables move

`_COST_PER_M` and `compute_cost()` are removed from `core/types.py`. Each provider class
owns the rates for its own models; `TokenUsage.cost_usd` is computed inside `generate()`.

## `PersonaConfig` update

```python
# Before
@dataclass
class PersonaConfig:
    models: list[str]
    ...

# After
@dataclass
class PersonaConfig:
    providers: list[LLMProvider]
    ...
```

`DualPersonaLoop._call_persona()` iterates `persona.providers` and calls
`provider.generate()` instead of `_call_model(model, ...)`. Fallback-chain behaviour
(try next provider on exception) is unchanged.

## Wiring: `core/runner.py`

Provider instances are created once in `runner.py` (the composition root) and injected
into each agent. `pipeline.py` has no visibility of provider classes — it only calls
`run_pipeline()`.

## pyproject.toml changes

```toml
[tool.setuptools.packages.find]
include = ["agents*", "core*", "llm*"]   # was: ["agents*"]

[project.scripts]
gata = "core.cli:main"                   # was: "agents.cli:main"

[tool.semantic_release]
version_variables = ["core/__version__.py:__version__"]  # was: agents/
```

## Scope and impact

This is a large structural change. Every `from agents.X import Y` and `from agents import X`
across all source files and tests becomes `from core.X import Y` or `from agents.X import Y`
(agents-only imports stay, infrastructure imports point to `core`). New `from llm.X import Y`
imports appear in `core/runner.py` and `llm/dual_loop.py`.

Files touched:
- All files in `agents/` (imports updated; non-agent files moved to `core/` or `llm/`)
- `pipeline.py` (imports updated)
- `tests/` (all imports updated)
- `pyproject.toml` (packages, entry point, version variable)
- `specs/` plan files that reference `agents/types.py` etc. (documentation only)

## What this does NOT do

- Does not change any agent logic, system prompts, or pipeline behaviour.
- Does not change the public CLI interface (`gata` command, `pipeline.py` flags).
- Does not add Grok support — Grok is tracked separately in TODO.md (see below).
- Does not change image generation — `agent_image_generator.py` manages its own
  Gemini client and is out of scope for the provider abstraction.

## TODO.md addition

Add to TODO.md after this spec is approved:

> **Grok integration — add xAI Grok as a third LLM provider**
> Once `llm/` exists, add `llm/grok.py` (GrokProvider) and wire it into `runner.py`.
> No existing agent code changes required.

## Verification

- All existing tests pass without modification (provider objects are injected via mock,
  replacing the current `unittest.mock.patch` on SDK methods).
- `gata "some topic"` runs end-to-end and telemetry shows correct per-call costs.
- `python pipeline.py --community uk-politics` runs end-to-end.
- Removing `ANTHROPIC_API_KEY` raises a clear error from `ClaudeProvider` before any
  network call.
- `ruff check .` passes with zero errors.
