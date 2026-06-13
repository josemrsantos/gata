# Implementation Plan: Trend Scout

**Branch**: `006-trend-scout` | **Date**: 2026-05-29 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/005-trend-scout/spec.md`

## Summary

Add Agent Trend Scout — a self-contained module that fetches today's top headlines from
NewsAPI.ai (sorted by social engagement score), passes them to Gemini for satirical-potential
ranking, and returns the top-N topics to the pipeline as the starting input. When news
fetching fails or returns nothing, the module falls back silently to the community seed topic
list. Manual `--topic` override bypasses Trend Scout entirely, preserving RULE 12.

The module is designed to be fully independent: it imports nothing from other agents, exposes
a single function (`get_topics`), and can be invoked standalone from the command line.

---

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: `httpx` (HTTP client for NewsAPI.ai), `google-genai` (already present — Gemini ranking), `pyyaml` (already present — config), `anthropic` (not used by this module)  
**Storage**: N/A — no persistence; topics are ephemeral per run  
**Testing**: pytest (already present)  
**Target Platform**: Local Linux / same environment as existing pipeline  
**Project Type**: Agent module within existing CLI pipeline  
**Performance Goals**: SC-002 — headline fetch + ranking completes within 60 seconds  
**Constraints**: Must not import from agent_0, agent_bc, agent_d, dual_loop, or bundle_writer; must not crash the pipeline on any network failure  
**Scale/Scope**: 5 communities × 1 run/day; each run fetches ~10 headlines per community

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| 1 — SDK/Model rules | ✅ Pass | Gemini ranking uses `gemini-2.5-flash`; no Claude calls in this module |
| 2 — Image output rule | ✅ N/A | No image generation in this module |
| 3 — XML contract | ✅ N/A | Trend Scout does not use the dual-loop XML contract |
| 8 — Project structure | ✅ Pass | New files follow existing `agents/` layout; documented below |
| 9 — Agent naming | ✅ Pass | Human-readable name: "Trend Scout" |
| 9 — Testing rules | ✅ Pass | Tests written before implementation; no real API calls in tests |
| 10 — Secrets | ✅ Pass | `NEWSAPI_AI_KEY` loaded from `.env` via `python-dotenv` |
| 12 — Code quality | ✅ Pass | `ruff check` and `ruff format` run before each task is marked complete |
| 13 — Logging | ✅ Pass | `logging` module used; log source of topics (NewsAPI / fallback / override) |

No violations — Complexity Tracking table not required.

---

## Project Structure

### Documentation (this feature)

```text
specs/005-trend-scout/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── cli.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (additions to repository root)

```text
agents/
├── trend_scout.py          # Trend Scout agent — public interface: get_topics()
└── sources/
    ├── __init__.py
    ├── base.py             # Abstract SourceAdapter + Headline dataclass
    └── newsapi.py          # NewsAPI.ai (EventRegistry) adapter

tests/
├── test_trend_scout.py     # Unit tests for get_topics(), fallback, Gemini ranking mock
└── test_sources_newsapi.py # Unit tests for NewsAPI.ai adapter (mocked HTTP)
```

**Existing files modified:**

```text
agents/types.py             # Add Headline dataclass; extend Community with news_sources
communities.yaml            # Add news_sources list per community (optional field)
pipeline.py                 # Replace random.choice(community.topics) with get_topics() call
pyproject.toml              # Add httpx to dependencies
CLAUDE.md                   # Update plan reference
```

**Structure Decision**: Single-project layout (Option 1) — new files slot into the existing
`agents/` and `tests/` directories. The `agents/sources/` sub-package is the only new
directory.

---

## Complexity Tracking

*No constitution violations — table omitted.*