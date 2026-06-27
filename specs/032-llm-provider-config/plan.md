# Implementation Plan: LLM Provider Configurability + Cross-Provider Fallback

**Branch**: `032-llm-provider-config` | **Date**: 2026-06-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/032-llm-provider-config/spec.md`

## Summary

Adds an optional `providers.yaml` config file that declares which LLM/model handles
each agent role. Cross-provider fallback is achieved by populating `PersonaConfig.providers`
with an ordered, cross-provider list — the existing `_call_persona` iteration loop
in `ParallelPanel` and `DualPersonaLoop` handles the fallback without any changes to
those protocols. Agent function signatures change `panelist_providers` from
`list[LLMProvider]` to `list[list[LLMProvider]]` so each panelist slot carries its
own fallback chain.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `pyyaml` (already in use), existing `llm/` providers
**Storage**: `providers.yaml` (optional config file at project root)
**Testing**: pytest with mocks (no real API calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — additive extension
**Performance Goals**: None — config load is O(1) at startup
**Constraints**: ruff `line-length=88`; no new providers or SDKs (§1)
**Scale/Scope**: ~8 files changed; no new source directories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | No new providers; existing Claude/Gemini/Grok SDKs only |
| 2 | Image Output Rule | ✅ | Not touched |
| 3 | XML and Output Contract | ✅ | Not touched |
| 4 | Character Rules | ✅ | Not touched |
| 5 | Visual Style Rules | ✅ | Not touched |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ | Aggregator model may change; schema unchanged |
| 7 | Language Rule | ✅ | Not touched |
| 8 | Project Structure | ✅ | All changes in approved dirs; providers.yaml at root matches pattern of communities.yaml |
| 9 | Testing Rules | ✅ | TDD; all API calls mocked; tests written before implementation |
| 10 | Secrets and Security | ✅ | No new secrets; API keys remain in env vars |
| 11 | Development Stages | ✅ | Branch 032-llm-provider-config from main |
| 12 | Code Quality | ✅ | ruff check + format before commit |
| 13 | Logging | ✅ | Use logging module; no bare print() in source |

**Constitution Check result**: all gates pass

## Project Structure

### Documentation (this feature)

```text
specs/032-llm-provider-config/
├── plan.md
└── spec.md
```

### Source Code Changes

```text
core/types.py           ADD  ModelSpec, ProvidersConfig dataclasses
core/config_loader.py   ADD  load_providers_config(path) -> ProvidersConfig | None
core/runner.py          ADD  _build_provider(spec) factory
                        MOD  run_pipeline() gains providers_config param; passes
                             panelist/aggregator lists to write_bundle
core/bundle_writer.py   MOD  write_bundle() gains optional panelist_providers /
                             aggregator_providers params; passes to agent_explainer
agents/agent_satirist.py        MOD  panelist_providers: list[LLMProvider] → list[list[LLMProvider]]
agents/agent_cultural_strategist.py  MOD  same
agents/agent_explainer.py       MOD  same
pipeline.py             ADD  --providers PATH flag; loads config; passes to run_pipeline
providers.yaml          NEW  sample config mirroring current hardcoded defaults
tests/test_providers_config.py  NEW  factory, config loader, cross-provider fallback
tests/test_config_loader.py     EXT  load_providers_config tests
```

**Structure Decision**: `providers.yaml` at project root matches the existing pattern
of `communities.yaml` and `humor.yaml`. No new package needed — the loader goes in
`core/config_loader.py` alongside existing loaders.

## Key design decision: panelist_providers type change

Agent `run()` functions gain `panelist_providers: list[list[LLMProvider]]` instead of
`list[LLMProvider]`. Each inner list is one panelist slot's ordered fallback chain.
`PersonaConfig(providers=slot, ...)` — the existing protocol already iterates this list.
The slot name uses `slot[0].model_id` (the primary provider). When no `providers.yaml`
is present, runner.py wraps each existing single provider as `[[p] for p in _PARALLEL_PANELISTS]`
preserving current behaviour exactly.
