# Research: Agent 0 — Cultural Strategist

## Decision 1 — Shared Module Architecture

**Decision**: A `DualPersonaLoop` class in `agents/dual_loop.py`, instantiated by both Agent 0 and the migrated B/C loop.

**Interface**:
```python
@dataclass
class PersonaConfig:
    name: str                   # "Framer", "Resonator", "Satirist", "Critic"
    models: list[str]           # ordered fail-over chain
    system_prompt: str          # persona-specific instructions

class DualPersonaLoop:
    def __init__(
        self,
        proposer: PersonaConfig,
        reviewer: PersonaConfig,
        max_iterations: int = 5,
        timeout_seconds: int = 900,  # 15 minutes
    ): ...

    def run(self, initial_input: str) -> str:
        """Run the negotiation loop. Returns the content of the final <verdict> tag."""
```

**Rationale**: Both Agent 0 and B/C follow an identical protocol — proposer wraps output in `<verdict>`, reviewer wraps decision in `<verdict>APPROVED</verdict>` or `<verdict>NEEDS REVISION</verdict>`. The loop logic (iteration counting, Final Say Protocol, timeout, fail-over) is identical. A single class eliminates duplication and ensures both loops evolve together.

**Alternatives considered**:
- Independent implementations: rejected — duplicates ~200 lines of identical loop logic; bugs fixed in one won't be fixed in the other.
- Inheritance: rejected — no shared state beyond the loop protocol; composition via `PersonaConfig` is simpler and testable.

---

## Decision 2 — `<verdict>` Tag as Universal Output Contract

**Decision**: The proposer (Framer in Agent 0, Satirist in B/C) always wraps its structured output in `<verdict>...</verdict>`. The reviewer always wraps its decision in `<verdict>APPROVED</verdict>` or `<verdict>NEEDS REVISION</verdict>` followed by feedback. The orchestrator distinguishes proposer from reviewer by which persona it called — not by tag content.

**Rationale**: One tag name; the loop module parses it identically regardless of agent. The `CartoonConcept.image_prompt` field name in Python is unchanged (it's internal); only the XML tag in the LLM prompt and the regex pattern change.

**Migration impact on B/C**:
- Satirist system prompt: replace all `<image_prompt>` instructions with `<verdict>`
- `_extract_image_prompt()` in agent_bc.py: regex changes from `<image_prompt>` to `<verdict>`
- All tests checking `<image_prompt>` tag: updated to `<verdict>`
- `CartoonConcept.image_prompt` Python field: unchanged

**Constitution amendment required**: Principle 3 must be updated before implementation begins.

---

## Decision 3 — Timeout Implementation

**Decision**: Track wall-clock start time using `time.monotonic()` at the beginning of `DualPersonaLoop.run()`. Check elapsed time at the start of each iteration (before the proposer call and before the reviewer call). Raise `TimeoutError` if `elapsed > timeout_seconds`.

**Rationale**: Synchronous check at iteration boundaries is sufficient — LLM calls are the only time-consuming operations. No threading or async required; no risk of partial writes or torn state. The timeout fires between calls, not mid-call (a call already in flight will complete, then the timeout is detected at the next boundary).

**Alternatives considered**:
- `threading.Timer`: fires mid-call but cannot safely interrupt a blocking HTTP request; requires thread-safe state management.
- `asyncio` timeout: would require rewriting the entire pipeline as async — disproportionate to the problem.

---

## Decision 4 — EnrichedBrief Data Type

**Decision**: Add `EnrichedBrief` as a new dataclass in `agents/types.py`:

```python
@dataclass
class EnrichedBrief:
    target_audience: str                       # locked from seed
    output_language: str                       # locked from seed
    tone: str                                  # locked from seed
    cultural_angle: str                        # added by Agent 0
    culturally_loaded_references: list[str]    # added by Agent 0
```

Agent 0's `run()` returns `EnrichedBrief`. `agent_bc.run()` accepts `EnrichedBrief` (replacing `StrategyBrief`). `pipeline.py` passes `EnrichedBrief` from Agent 0 to B/C.

**Rationale**: A distinct type makes the contract explicit — B/C always receives an enriched brief in Stage 3+; the seed-only path is removed from the pipeline entry point. `StrategyBrief` remains for config loading and as Agent 0's input type.

---

## Decision 5 — Model Chains

**The Framer (Claude)**:
```python
["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"]
```
Primary mandated by constitution (P1). Fallbacks to other Claude models consistent with existing agent_bc.py.

**The Resonator (Gemini — text reasoning)**:
```python
["gemini-2.5-pro", "gemini-2.5-flash", "gemini-1.5-pro"]
```
Gemini 2.5 Pro is the most capable available text model for cultural analysis. Flash as fallback for availability. 1.5 Pro as final fallback per blueprint specification.

**The Satirist (Claude) — B/C migration**:
No change to model chain (already implemented in agent_bc.py).

**The Critic (Gemini) — B/C migration**:
No change to model chain (already implemented in agent_bc.py).

---

## Decision 6 — Final Say Protocol Implementation

**Decision**: At iteration 5 (the last allowed), the proposer is given a special system prompt suffix instructing it to produce its final answer, explicitly acknowledging The Resonator's most recent feedback and noting which elements it adopted and which it did not. The output is always wrapped in `<verdict>` regardless.

**Rationale**: The Final Say Protocol requires "genuine consideration" (FR-007, SC-004). Injecting a prompt suffix at the final iteration forces the LLM to acknowledge the feedback explicitly — making the "genuine consideration" requirement testable (the final output text must reference the reviewer's position).

---

## Decision 7 — Agent 0 Framer Prompt Structure

The Framer's `<verdict>` block for Agent 0 must contain a structured response that Agent 0's orchestrator can parse to extract `cultural_angle` and `culturally_loaded_references`. The internal structure uses clearly labelled sections within the `<verdict>` block:

```
<verdict>
CULTURAL ANGLE: [one paragraph]
REFERENCES:
- [reference 1]
- [reference 2]
</verdict>
```

Agent 0 parses this with regex to populate `EnrichedBrief`. The `DualPersonaLoop` returns the raw `<verdict>` content as a string; Agent 0 is responsible for parsing it into the `EnrichedBrief` fields.

---

## Constitution Amendments Required Before Implementation

### Principle 3 — XML Contract (PATCH amendment)

**Current**: Satirist wraps output in `<image_prompt>...</image_prompt>` and `<joke_explanation>...</joke_explanation>`.

**New**: Satirist wraps its creative output in `<verdict>...</verdict>` and `<joke_explanation>...</joke_explanation>`. The `<verdict>` tag is the universal structured output tag for all proposing personas in the dual-persona loop.

Regex change:
```python
# Old
re.search(r'<image_prompt>(.*?)</image_prompt>', text, re.DOTALL)
# New
re.search(r'<verdict>(.*?)</verdict>', text, re.DOTALL)
```

### Principle 8 — Project Structure (PATCH amendment)

Add to `agents/`:
```
├── dual_loop.py      # Shared DualPersonaLoop module
└── agent_0.py        # Cultural Strategist
```
