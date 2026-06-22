# Feature Specification: Grok as Primary Decider Across All Parallel Panel Agents

**Spec**: `029-grok-parallel-primary`
**Created**: 2026-06-22
**Status**: Draft

## Problem

The pipeline has three distinct topologies in use:

- **Satirist** uses `ParallelPanel` with Claude, Grok-3, and Gemini as panelists and
  **Claude** as the aggregator/decider.
- **Cultural Strategist** uses `DualPersonaLoop` with Claude as Framer and Gemini as
  Resonator — a sequential proposer/reviewer shape.
- **Explainer** uses `DualPersonaLoop` (x2) with Claude as Writer and Gemini as Editor.

There is no consistent decider across agents, and two agents still use an older topology
that cannot easily swap which provider holds the quality-gate role.

## Goal

1. **Grok (`grok-3`) becomes the aggregator/decider in every agent** that uses
   `ParallelPanel` — including the Satirist (already on `ParallelPanel`) and the two
   agents converted in this stage.
2. **Grok also participates as a panelist** but uses `grok-3-mini` (a different model
   from the `grok-3` aggregator) so it is not both judge and sole proposer.
3. **Cultural Strategist** is converted from `DualPersonaLoop` to `ParallelPanel`.
   Three framers (Claude, Grok-mini, Gemini) independently propose a cultural angle;
   Grok-3 evaluates all proposals for cultural resonance and picks/synthesises the best.
   The Resonator quality-gate behaviour is preserved — just moved into Grok's aggregator
   prompt instead of a separate reviewer persona.
4. **Explainer** is converted from `DualPersonaLoop` to `ParallelPanel` (applied to
   both the in-language and English runs). Three writers independently produce an HTML
   page; Grok-3 evaluates all pages against the Editor's quality criteria and picks the
   best. The Editor quality-gate behaviour is preserved in Grok's aggregator prompt.

## Design

### Provider constants — `core/runner.py` and `core/bundle_writer.py`

```python
_PARALLEL_PANELISTS = [
    ClaudeProvider("claude-sonnet-4-6"),
    GrokProvider("grok-3-mini"),        # was grok-3; different model from aggregator
    GeminiProvider("gemini-2.5-flash"),
]
_GROK_AGGREGATOR = [GrokProvider("grok-3")]
```

`_CLAUDE_CHAIN` and `_GEMINI_PRO_CHAIN` are unchanged; they remain available for
non-panel use (e.g. image evaluator).

### Satirist — `agents/agent_satirist.py` + `core/runner.py`

Only the aggregator changes. The panelists already include Grok (`grok-3` → `grok-3-mini`
after the constant update above). No changes to `agent_satirist.py` itself.

In `core/runner.py`:
```python
agent_satirist.run(
    ...,
    panelist_providers=_PARALLEL_PANELISTS,
    aggregator_providers=_GROK_AGGREGATOR,   # was _CLAUDE_CHAIN
    ...
)
```

### Cultural Strategist — `agents/agent_cultural_strategist.py` + `core/runner.py`

#### New aggregator system prompt

```
You are The Resonator — a cultural critic and chief editor for Gata Newsroom.
Three Framers have independently proposed a cultural angle and reference list for
the topic below. Your job is to:
1. Evaluate each proposal for genuine cultural resonance with the stated target
   audience — specificity, accuracy, and satirical sharpness matter most.
2. Pick the single strongest proposal, or synthesise the best elements from multiple
   proposals into one superior angle.
3. Output a PICK: N line (N = the proposal number you selected as primary), then your
   final cultural angle in the exact format below, wrapped in <verdict>...</verdict>:

<verdict>
CULTURAL ANGLE: [one paragraph]
REFERENCES:
- [reference 1]
- [reference 2]
JOKE TYPE: [type]
</verdict>

If a JOKE TYPE field was present in the proposals, carry the best one forward.
If none was present, omit the field.
Do not add preamble. Output only PICK: N and the <verdict> block.
```

#### Signature change

```python
# Before
def run(topic, seed_brief, framer_providers, resonator_providers, ...):

# After
def run(topic, seed_brief, panelist_providers, aggregator_providers, ...):
```

Inside `run()`:
- One `PersonaConfig` per provider in `panelist_providers`, all using the Framer system
  prompt (unchanged).
- One `PersonaConfig` for the aggregator using `aggregator_providers` and the new
  Resonator-as-aggregator system prompt above.
- `ParallelPanel` replaces `DualPersonaLoop`. No `max_iterations` — `ParallelPanel`
  runs one pass.

`_parse_verdict`, `_build_framer_system_prompt`, and all other logic are unchanged.
`_RESONATOR_SYSTEM` is removed (no longer wired into any protocol).

In `core/runner.py`:
```python
agent_cultural_strategist.run(
    topic,
    seed_brief,
    panelist_providers=_PARALLEL_PANELISTS,   # was framer_providers=_CLAUDE_CHAIN
    aggregator_providers=_GROK_AGGREGATOR,     # was resonator_providers=_GEMINI_PRO_CHAIN
    ...
)
```

### Explainer — `agents/agent_explainer.py` + `core/bundle_writer.py`

#### New aggregator system prompt

```
You are The Editor — an HTML quality judge for Gata Newsroom.
Three writers have independently produced an HTML explanation page.
Your job is to:
1. Evaluate each page against ALL of these criteria:
   a. Contains <!DOCTYPE html>
   b. Contains <meta charset="UTF-8"> in the <head>
   c. The lang attribute on <html> matches the target language
   d. All body text is in the correct language (no leakage)
   e. Content clearly explains the satirical angle and cultural references
   f. No external resource links
2. Pick the page that best satisfies all criteria. If multiple pages pass, prefer
   the most thorough explanation.
3. Output a PICK: N line (N = the chosen page number), then the complete chosen
   HTML page wrapped in <verdict>...</verdict> tags.

Do not add preamble. Do not modify the chosen HTML. Output only PICK: N and the
<verdict> block containing the verbatim HTML.
```

#### Signature change

```python
# Before
def generate_html(enriched_brief, agent0_log, bc_log, image_prompt,
                  writer_providers, editor_providers):

# After
def generate_html(enriched_brief, agent0_log, bc_log, image_prompt,
                  panelist_providers, aggregator_providers):
```

Inside `generate_html()`:
- `_WRITER_SYSTEM` is unchanged; every panelist uses it.
- Two `ParallelPanel` runs (in-language, English) each with the same panelists but
  different `initial_input`. The aggregator `PersonaConfig` is constructed once and
  shared across both runs.
- `_EDITOR_SYSTEM` is removed (no longer wired into any protocol).

In `core/bundle_writer.py`:
```python
_panelist_providers = [
    ClaudeProvider("claude-sonnet-4-6"),
    GrokProvider("grok-3-mini"),
    GeminiProvider("gemini-2.5-flash"),
]
_aggregator_providers = [GrokProvider("grok-3")]
agent_explainer.generate_html(
    ...,
    panelist_providers=_panelist_providers,
    aggregator_providers=_aggregator_providers,
)
```

### Constitution amendment — §6

§6 currently states:
> "Claude (as panelist or aggregator) has final say via the three-part Final Say Protocol"
> "The ParallelPanel topology (Claude + Grok + Gemini as independent panelists;
>  Claude as aggregator) is the current Satirist implementation"

Post-stage §6 will read:
> "Grok (`grok-3`) is the aggregator/decider across all `ParallelPanel` agents.
>  Grok also participates as a panelist using `grok-3-mini`.
>  The Final Say Protocol (acknowledge → override rationale → synthesis) is now
>  expressed in Grok's aggregator prompt rather than in the DualPersonaLoop."

## What does NOT change

- `ParallelPanel` and `DualPersonaLoop` implementations are untouched.
- `_parse_verdict` in `agent_cultural_strategist.py` is untouched.
- `_WRITER_SYSTEM` in `agent_explainer.py` is untouched.
- `_build_framer_system_prompt` in `agent_cultural_strategist.py` is untouched.
- `_build_satirist_system_prompt` and `_build_aggregator_prompt` in
  `agent_satirist.py` are untouched — the Satirist aggregator prompt already exists
  and works; only the provider changes.
- Image generation, image evaluation, bundle writing structure, CLI, and Trend Scout
  are untouched.
- `RULE 12` (manual invocation always possible) is preserved — pipeline signature
  unchanged at the CLI level.

## Tests

### `tests/test_agent_cultural_strategist.py`

- `run()` with `panelist_providers` (3 providers) and `aggregator_providers` (1 Grok
  provider) creates a `ParallelPanel`, not a `DualPersonaLoop`.
- All three panelist providers are called once with the Framer system prompt.
- The aggregator provider is called once with the CS aggregator system prompt.
- `LoopOutput.verdict` containing a valid cultural angle → `EnrichedBrief` correctly
  populated (cultural_angle, references, joke_type).
- Empty `cultural_angle` in verdict → `ValueError` raised.
- Empty `references` in verdict → `ValueError` raised.

### `tests/test_agent_explainer.py`

- `generate_html()` with `panelist_providers` and `aggregator_providers` creates two
  `ParallelPanel` runs (in-lang, English) — not two `DualPersonaLoop` instances.
- All three panelist providers are called for each run.
- The aggregator provider is called once per run with the Editor aggregator prompt.
- Returns a 2-tuple of strings (in-lang HTML, English HTML).

### `tests/test_bundle_writer.py`

- `write_bundle()` calls `agent_explainer.generate_html` with `panelist_providers`
  and `aggregator_providers` keyword args (not `writer_providers` / `editor_providers`).

### `tests/test_pipeline.py` (or equivalent)

- Cultural Strategist call in runner uses `panelist_providers` and
  `aggregator_providers`.
- Satirist call in runner uses `aggregator_providers=_GROK_AGGREGATOR`.

## Verification

- `pytest tests/` — all tests pass, zero failures.
- `gata "some topic"` runs end-to-end; console shows all three agent steps completing.
- Telemetry shows: Cultural Strategist has 3 panelist calls + 1 Grok aggregator call;
  Satirist has 3 panelist calls + 1 Grok aggregator call; Explainer (if HTML enabled)
  has 3 panelist calls + 1 Grok aggregator call per HTML page.
- `python pipeline.py --topic "..." --audience "..." --language "..." --tone "..."` runs
  end-to-end successfully.
