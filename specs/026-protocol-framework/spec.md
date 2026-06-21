# Feature Specification: LLM Communication Protocol Framework + Parallel Panel

**Spec**: `026-protocol-framework`
**Created**: 2026-06-21
**Status**: Draft

## Problem

`DualPersonaLoop` is the only conversation topology in the pipeline. It hardcodes a
single shape: one proposer alternates with one reviewer until `APPROVED` or max
iterations. As the pipeline grows, new interaction patterns are needed — and there
is no shared interface that would let `agent_satirist` (or any other agent) be
indifferent to which topology is underneath.

## Goal

1. Define a `ConversationProtocol` ABC as the shared interface for all topologies.
2. Make `DualPersonaLoop` implement it (no behaviour change).
3. Implement `ParallelPanel` — N panelists each independently generate a concept;
   an aggregator picks the strongest one.
4. Replace the `DualPersonaLoop` in `agent_satirist` with `ParallelPanel`: Claude,
   Grok, and Gemini each independently produce a cartoon concept; Claude aggregates
   and picks the best.

## Design

### `ConversationProtocol` ABC — add to `llm/base.py`

```python
class ConversationProtocol(ABC):
    @abstractmethod
    def run(self, initial_input: str) -> LoopOutput: ...
```

`DualPersonaLoop` already has a matching `run()` signature — it just needs to
inherit from `ConversationProtocol`.

### `llm/parallel_panel.py` — new file

```python
class ParallelPanel(ConversationProtocol):
    def __init__(
        self,
        panelists: list[PersonaConfig],   # one PersonaConfig per panelist
        aggregator: PersonaConfig,         # picks the best output
        panel_name: str = "",
    ): ...

    def run(self, initial_input: str) -> LoopOutput: ...
```

**`run()` flow:**

1. Call each panelist independently with `initial_input`. Each panelist has its own
   `PersonaConfig` (same system prompt, different provider). Failures fall through
   via the provider fallback chain; a panelist that fully exhausts its providers is
   skipped with a warning (minimum 1 panelist must succeed or `RuntimeError` is raised).

2. Build an aggregation message listing all successful panelist outputs, numbered,
   with the contributing model name:

   ```
   You are a chief editor at Gata Newsroom. Three satirists have independently
   proposed a cartoon concept for the topic below. Pick the single funniest,
   most specific, most uncomfortable one — the kind that makes you wince because
   it is so accurate.

   Topic: {initial_input}

   CONCEPT 1 (claude-sonnet-4-6):
   {panelist_1_verdict}

   CONCEPT 2 (grok-3):
   {panelist_2_verdict}

   CONCEPT 3 (gemini-2.5-flash):
   {panelist_3_verdict}

   Respond with ONLY: PICK: <number>
   Then on the next line copy the chosen concept verbatim inside
   <verdict>...</verdict> tags. No other text.
   ```

3. Call the aggregator with the above message. Extract the `<verdict>` content
   (using `_extract_proposer_verdict` from `llm/dual_loop.py`) as the final output.

4. Return `LoopOutput(verdict=chosen_concept, log=..., telemetry=...)`.

**Log structure:** one `ConversationTurn` per panelist (role = panelist name,
iteration = 1), then one `ConversationTurn` for the aggregator (role = "Aggregator",
iteration = 1, verdict = "PICK: N").

### `agent_satirist.py` — updated `run()` signature

```python
def run(
    topic: str,
    brief: EnrichedBrief,
    panelist_providers: list[LLMProvider],   # renamed from satirist_providers
    aggregator_providers: list[LLMProvider], # renamed from co_satirist_providers
    humor: HumorConfig | None = None,
    layout_override: CartoonLayout | None = None,
) -> tuple[CartoonConcept, ConversationLog, AgentTelemetry, CartoonLayout]:
```

Inside `run()`:
- Build the satirist system prompt once (same for all panelists).
- Create one `PersonaConfig` per provider in `panelist_providers`, each with the
  same system prompt and a single-item provider list.
- Create the aggregator `PersonaConfig` using `aggregator_providers`.
- Run `ParallelPanel` and parse the verdict with `_parse_verdict` (unchanged).

### `core/runner.py` — updated chains

```python
_PARALLEL_PANELISTS = [
    ClaudeProvider("claude-sonnet-4-6"),
    GrokProvider("grok-3"),
    GeminiProvider("gemini-2.5-flash"),
]
# _GROK_CO_SATIRIST_CHAIN removed (no longer needed)

agent_satirist.run(
    topic,
    enriched_brief,
    panelist_providers=_PARALLEL_PANELISTS,
    aggregator_providers=_CLAUDE_CHAIN,
    humor=humor,
    layout_override=layout,
)
```

### `llm/__init__.py` — export `ParallelPanel`

Add `ParallelPanel` to `__all__`.

## What does NOT change

- `DualPersonaLoop` behaviour is unchanged (Cultural Strategist and Explainer keep it).
- `_parse_verdict`, `_build_satirist_system_prompt` in `agent_satirist.py` are unchanged.
- `LoopOutput`, `ConversationLog`, `AgentTelemetry`, `PersonaConfig` in `core/types.py`
  are unchanged.
- The public CLI (`gata`, `pipeline.py`) interface is unchanged.
- Image generation, evaluation, and bundle writing are unchanged.

## Tests

New file `tests/test_parallel_panel.py`:

- Happy path: 3 panelists succeed, aggregator picks concept 2 — `LoopOutput.verdict`
  equals panelist 2's output.
- Panelist failure: one panelist exhausts providers — is skipped; remaining two are
  passed to aggregator.
- All panelists fail: `RuntimeError` raised.
- Aggregator failure: `RuntimeError` raised.
- Log structure: correct number of turns, roles, and iteration numbers.
- Telemetry: all panelist + aggregator token usages accumulated in `telemetry.calls`.
- `ConversationProtocol` ABC: `ParallelPanel` and `DualPersonaLoop` both satisfy it.

Update `tests/test_agent_satirist.py`: rename `satirist_providers` →
`panelist_providers`, `co_satirist_providers` → `aggregator_providers` in all mock
calls.

Update `tests/test_pipeline.py`: same rename in any `agent_satirist.run()` call sites.

## Verification

- All existing tests pass.
- `gata "some topic"` runs end-to-end; console shows `Satirist/Co-Satirist...` step
  completing; telemetry shows three panelist model calls + one aggregator call.
- `python pipeline.py` also runs end-to-end successfully.