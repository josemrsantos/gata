# Tasks: 024 — LLM Provider Abstraction + Project Restructure

## Phase 1 — Create `llm/` package

- [ ] T01 — Create `llm/__init__.py`
- [ ] T02 — Create `llm/base.py` (LLMProvider ABC)
- [ ] T03 — Create `llm/claude.py` (ClaudeProvider + cost table)
- [ ] T04 — Create `llm/gemini.py` (GeminiProvider + cost table + .client property)
- [ ] T05 — Create `llm/dual_loop.py` (moved + refactored from agents/dual_loop.py)

## Phase 2 — Create `core/` package

- [ ] T06 — Create `core/__init__.py`
- [ ] T07 — Create `core/__version__.py` (copy from agents/)
- [ ] T08 — Create `core/types.py` (from agents/types.py; PersonaConfig uses providers; no compute_cost)
- [ ] T09 — Create `core/config_loader.py` (from agents/config_loader.py; updated imports)
- [ ] T10 — Create `core/humor_utils.py` (from agents/humor_utils.py; updated imports)
- [ ] T11 — Create `core/bundle_writer.py` (from agents/bundle_writer.py; updated imports)
- [ ] T12 — Create `core/runner.py` (from agents/runner.py; creates providers, injects)
- [ ] T13 — Create `core/cli.py` (from agents/cli.py; updated imports)

## Phase 3 — Update `agents/` package

- [ ] T14 — Update `agents/__init__.py` (remove non-agent exports)
- [ ] T15 — Update `agents/agent_satirist.py` (imports + accept provider lists)
- [ ] T16 — Update `agents/agent_cultural_strategist.py` (imports + accept providers)
- [ ] T17 — Update `agents/agent_explainer.py` (imports + accept providers)
- [ ] T18 — Update `agents/agent_image_evaluator.py` (imports + accept GeminiProvider)
- [ ] T19 — Update `agents/agent_image_generator.py` (imports only)
- [ ] T20 — Update `agents/trend_scout.py` (imports; GeminiProvider internally)

## Phase 4 — Update root files

- [ ] T21 — Update `pipeline.py` (imports from core/llm)
- [ ] T22 — Update `pyproject.toml` (packages, entry point, version variable)

## Phase 5 — Update tests

- [ ] T23 — Update `tests/test_dual_loop.py` (new import paths + mock via provider objects)
- [ ] T24 — Update `tests/test_types.py` (import from core.types)
- [ ] T25 — Update `tests/test_config_loader.py` (import from core.config_loader)
- [ ] T26 — Update `tests/test_humor_utils.py` (import from core.humor_utils)
- [ ] T27 — Update `tests/test_bundle_writer.py` (import from core.bundle_writer)
- [ ] T28 — Update `tests/test_agent_satirist.py` (imports + PersonaConfig.providers)
- [ ] T29 — Update `tests/test_agent_cultural_strategist.py` (imports)
- [ ] T30 — Update `tests/test_agent_explainer.py` (imports)
- [ ] T31 — Update `tests/test_agent_image_evaluator.py` (imports)
- [ ] T32 — Update `tests/test_agent_image_generator.py` (imports)
- [ ] T33 — Update `tests/test_trend_scout.py` (imports)
- [ ] T34 — Update `tests/test_sources_newsapi.py` (imports)
- [ ] T35 — Update `tests/test_pipeline.py` (imports)
- [ ] T36 — Update `tests/test_cli.py` (imports)

## Phase 6 — Cleanup and verification

- [ ] T37 — Remove non-agent files from `agents/` (after core/ and llm/ are in place)
- [ ] T38 — Run `ruff check .` — fix all errors
- [ ] T39 — Run full test suite — all tests pass
- [ ] T40 — Generate image via pipeline.py (news topic)
- [ ] T41 — Generate image via gata command
