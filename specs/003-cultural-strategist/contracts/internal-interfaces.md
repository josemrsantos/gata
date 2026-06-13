# Internal Interface Contracts: Agent 0 — Cultural Strategist

## DualPersonaLoop (`agents/dual_loop.py`)

### Constructor

```python
DualPersonaLoop(
    proposer: PersonaConfig,
    reviewer: PersonaConfig,
    max_iterations: int = 5,
    timeout_seconds: int = 900,
)
```

### `run(initial_input: str) -> str`

Runs the negotiation loop. Returns the raw string content inside the final accepted `<verdict>` tag from the proposer.

**Protocol**:
1. Proposer receives `initial_input` and responds with a `<verdict>...</verdict>` block.
2. Reviewer receives the proposer's full response and replies with `<verdict>APPROVED</verdict>` or `<verdict>NEEDS REVISION</verdict>` plus feedback.
3. If `APPROVED` before `max_iterations`: return proposer's last `<verdict>` content immediately.
4. If `NEEDS REVISION` and iterations remain: pass reviewer feedback back to proposer and loop.
5. At `max_iterations` with no approval: invoke Final Say — proposer receives a modified prompt acknowledging it must make the final call having considered all reviewer feedback. Return its `<verdict>` content.
6. If elapsed wall-clock time exceeds `timeout_seconds` at any iteration boundary: raise `TimeoutError`.

**Tag parsing rules**:
- Proposer output: extract content between first `<verdict>` and `</verdict>` using regex with `re.DOTALL`. If tag is missing or malformed, raise `ValueError`.
- Reviewer output: check if `<verdict>` content starts with `APPROVED` (case-insensitive). Anything else is treated as `NEEDS REVISION`.

**Errors raised**:
- `TimeoutError`: 15-minute budget exceeded.
- `RuntimeError`: all models in a persona's chain exhausted.
- `ValueError`: proposer response missing or malformed `<verdict>` tag.

---

## Agent 0 (`agents/agent_0.py`)

### `run(topic: str, seed_brief: StrategyBrief) -> EnrichedBrief`

Runs the Framer/Resonator negotiation and returns an `EnrichedBrief`.

**Behaviour**:
- Instantiates `DualPersonaLoop` with Framer and Resonator persona configs.
- Calls `loop.run(initial_input)` where `initial_input` is the topic + seed brief formatted as the Framer's initial context.
- Parses the returned `<verdict>` content to extract `cultural_angle` and `culturally_loaded_references`.
- Validates that both fields are non-empty; raises `ValueError` if either is empty.
- Returns `EnrichedBrief` with seed fields carried unchanged.

**Errors raised**:
- `TimeoutError`: propagated from `DualPersonaLoop`.
- `RuntimeError`: propagated from `DualPersonaLoop` (all models exhausted).
- `ValueError`: returned brief has empty `cultural_angle` or empty `culturally_loaded_references`.

---

## Agent B/C (`agents/agent_bc.py`) — Migration Contract

### `run(topic: str, brief: EnrichedBrief) -> CartoonConcept`

Signature change: `brief` type changes from `StrategyBrief` to `EnrichedBrief`. The Satirist prompt now includes `cultural_angle` and `culturally_loaded_references` from the enriched brief.

**XML tag change**:
- Old: Satirist wraps image description in `<image_prompt>...</image_prompt>`
- New: Satirist wraps image description in `<verdict>...</verdict>`
- `CartoonConcept.image_prompt` Python field is unchanged; only the XML tag name changes.

**Loop migration**:
- The hand-written negotiation loop in agent_bc.py is replaced by `DualPersonaLoop`.
- Satirist and Critic are passed as `PersonaConfig` instances.
- Existing model chains (`_CLAUDE_MODELS`, `_GEMINI_CRITIC_MODELS`) are preserved and passed to `PersonaConfig.models`.

---

## Pipeline (`pipeline.py`) — Updated Call Sequence

```python
# Before B/C loop (new):
enriched_brief = agent_0.run(topic, seed_brief)

# B/C loop (signature updated):
concept = agent_bc.run(topic, enriched_brief)

# Image generation (unchanged):
agent_d.generate(concept, enriched_brief, output_path)
```

`agent_d.generate()` receives `EnrichedBrief` instead of `StrategyBrief` — compatible since `EnrichedBrief` is a superset.

---

## XML Tag Contracts Summary

| Agent | Proposer tag | Reviewer tag |
|---|---|---|
| Agent 0 | `<verdict>...</verdict>` (Framer's enriched brief) | `<verdict>APPROVED</verdict>` or `<verdict>NEEDS REVISION</verdict>` (Resonator) |
| Agent B/C | `<verdict>...</verdict>` (Satirist's image prompt) | `<verdict>APPROVED</verdict>` or `<verdict>NEEDS REVISION</verdict>` (Critic) |

Additional tag for B/C only (unchanged):
- `<joke_explanation>...</joke_explanation>` — parsed by orchestrator, not passed to Agent D.
