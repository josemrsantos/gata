# Implementation Plan: Stage 1 Core Loop

**Branch**: `001-stage-1-core-loop` | **Date**: 2026-04-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-stage-1-core-loop/spec.md`

## Summary

Build the first runnable end-to-end pipeline: a hardcoded news topic and strategy brief flow through a dual-agent
creative loop (Satirist + Critic, up to 5 iterations), producing an approved cartoon concept that is handed to an
image-generation agent and saved as `output/cartoon_output.png`. All agent calls are mocked in tests; no real API calls
occur during testing.

## Technical Context

**Language/Version**: Python 3.x (3.10+ recommended for `match` and modern type hints)  
**Primary Dependencies**: `anthropic` (Claude SDK), `google-genai` (Gemini SDK), `python-dotenv` (secrets loading),  
`pytest` + `unittest.mock` (testing), `ruff` (linting + formatting); declared in `pyproject.toml`  
**Storage**: Files — `output/cartoon_output.png` written to disk; no database  
**Testing**: `pytest` with `unittest.mock.patch`; zero real API calls permitted in tests  
**Target Platform**: Local developer workstation (Linux/macOS)  
**Project Type**: CLI pipeline script  
**Performance Goals**: No strict latency target for Stage 1 — single run, no concurrency  
**Constraints**: Hardcoded inputs (topic + brief); output always `output/cartoon_output.png`; partial image writes  
prohibited  
**Scale/Scope**: Single pipeline run producing one image; no batch, no scheduling

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle                       | Status | Notes                                                                                                                                                                                             |
|---------------------------------|--------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1. SDK and Model Rules          | ✅ PASS | Plan mandates `import anthropic`, `claude-sonnet-4-6`, `from google import genai`, `gemini-3.1-flash-image-preview`, `gemini-2.0-flash`                                                           |
| 2. Image Output Rule            | ✅ PASS | `inline_data.data` binary extraction pattern required; URL assumption is a blocking error                                                                                                         |
| 3. XML Contract                 | ✅ PASS | Agent B wraps image prompt in `<image_prompt>…</image_prompt>`; orchestrator parses with `re.search`; missing tag triggers retry                                                                  |
| 4. Character Rules — Gata       | ✅ PASS | Gata's physical description (calico-tabby, collar, spot) MUST appear verbatim in every generated image prompt                                                                                     |
| 5. Visual Style Rules           | ✅ PASS | Selective Color palette, 1970s newsroom, chalkboard heading "ON THE SPOT" (or translated equivalent), dry caption                                                                                 |
| 6. Dual-Persona Iteration Rules | ✅ PASS | Max 5 iterations; measurable progress per round; Claude (Satirist) has final say at limit with three-part Final Say Protocol (acknowledge objection, state override rationale, produce synthesis) |
| 7. Language Rule                | ✅ PASS | Output language sourced from strategy brief; Agent C verifies no English leakage before approving                                                                                                 |
| 8. Project Structure            | ✅ PASS | `pipeline.py`, `agents/agent_bc.py`, `agents/agent_d.py`, `output/`, `tests/` per constitution                                                                                                    |
| 9. Testing Rules                | ✅ PASS | Tests written before implementation; pytest; all SDK calls mocked; XML parse and image-extract logic each have explicit unit tests                                                                |
| 10. Secrets and Security        | ✅ PASS | `.env` + `python-dotenv`; keys are `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`; `.gitignore` covers `.env` and `output/`; no hardcoded keys                                                          |
| 11. Development Stages          | ✅ PASS | This plan targets Stage 1 only; no later-stage features included                                                                                                                                  |
| 12. Code Quality                | ✅ PASS | `ruff` in dev dependencies; `ruff check .` and `ruff format .` run in Phase 6 before end-to-end validation                                                                                       |

**Constitution Check result: all gates pass. Proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/001-stage-1-core-loop/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── internal-interfaces.md   # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
gata/
├── .env                     # API keys — never committed
├── .gitignore
├── pipeline.py              # Main orchestrator — loads inputs, calls agents, saves output
├── agents/
│   ├── agent_bc.py          # Creative Studio: Satirist + Critic loop
│   └── agent_d.py           # Image Generator
├── output/                  # Generated PNGs — gitignored
└── tests/
    ├── test_agent_bc.py     # Unit tests for the B/C loop (mocked SDK calls)
    ├── test_agent_d.py      # Unit tests for image generation (mocked SDK calls)
    └── test_pipeline.py     # Integration test for full pipeline (mocked SDK calls)
```

**Structure Decision**: Single-project layout matching the constitution (Principle 8). No monorepo, no sub-packages for
Stage 1.

## Complexity Tracking

*No constitution violations — table omitted.*
