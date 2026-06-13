# Internal Interfaces: Stage 1 Core Loop

**Branch**: `001-stage-1-core-loop` | **Date**: 2026-04-25

This project has no external HTTP API. The contracts here define the function-level interfaces between the three
modules, so each can be developed and tested in isolation.

---

## `agents/agent_bc.py`

### `run(topic: str, brief: StrategyBrief) -> CartoonConcept`

Executes the Satirist + Critic creative loop and returns the final approved (or iteration-limit) concept.

**Preconditions**:

- `topic` is non-empty
- `brief` is a valid `StrategyBrief` (all three fields non-empty)
- Anthropic client is initialised (API key loaded)
- Gemini client is initialised (API key loaded)

**Postconditions**:

- Returns a `CartoonConcept` where `image_prompt` is non-empty
- Loop ran at most 5 iterations
- If Critic approved before iteration 5, loop exited early
- If limit reached without approval, last Satirist output is returned

**Error conditions**:

- If XML extraction fails on every attempt for a single iteration (all 3 retries exhausted) → raises
  `RuntimeError("Satirist failed to produce valid XML after retries")`; the caller (`pipeline.py`) catches this,
  prints a clear error message, and exits with code 1; no partial output is written; using the last malformed
  response as a fallback is deferred to Stage 4
- API errors propagate as-raised (caller handles)

**Side effects**: None — no files written, no global state mutated

---

## `agents/agent_d.py`

### `generate(concept: CartoonConcept, brief: StrategyBrief) -> str`

Generates the cartoon image from the approved concept and saves it to disk.

**Preconditions**:

- `concept.image_prompt` is non-empty
- `brief.output_language` is set (used to verify caption language in prompt)
- Gemini client is initialised
- `output/` directory exists (created by pipeline.py if absent)

**Postconditions**:

- `output/cartoon_output.png` exists and is a valid PNG
- Returns the absolute path to the saved file
- Write is atomic: temp file written first, then renamed

**Error conditions**:

- If Gemini returns a response with no `inline_data` part → raises
  `RuntimeError("Image generation produced no binary data")`
- No partial or empty file is left on disk on failure
- API errors propagate as-raised

**Side effects**: Writes `output/cartoon_output.png`

---

## `pipeline.py`

### Entry point (run as `python pipeline.py`)

**Responsibilities**:

1. Load `.env` via `python-dotenv`
2. Validate `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` are present
3. Define hardcoded `TOPIC: str` and `BRIEF: StrategyBrief`
4. Validate `BRIEF` fields (raise `ValueError` on blank)
5. Ensure `output/` directory exists
6. Call `agent_bc.run(TOPIC, BRIEF)` → concept
7. Call `agent_d.generate(concept, BRIEF)` → output path
8. Print confirmation and output path to stdout
9. Exit 0 on success; exit 1 with error message on any failure

**No public functions** — not importable as a library in Stage 1

---

## Shared Types (`agents/types.py`)

```python
from dataclasses import dataclass


@dataclass
class StrategyBrief:
    target_audience: str
    output_language: str
    tone: str


@dataclass
class CartoonConcept:
    full_text: str
    image_prompt: str
    iteration: int


@dataclass
class Critique:
    feedback: str
    approved: bool
    language_check_passed: bool
```

These types are the only shared contract between modules. They carry no methods and impose no framework dependencies.
