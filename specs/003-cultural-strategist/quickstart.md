# Quickstart: Agent 0 — Cultural Strategist

## Running the Full Pipeline (Stage 3)

After Stage 3 implementation, the pipeline is unchanged from the operator's perspective:

```bash
# Community mode (Agent 0 enriches the seed brief automatically)
python pipeline.py --community portuguese-adults

# Manual mode (supplied brief is used as seed for Agent 0)
python pipeline.py --topic "Tech layoffs" --audience "Software engineers" --language "English" --tone "dry wit"
```

The log will now show Agent 0 running before the B/C loop:

```
INFO agent_0: framer iteration 1/5 — model=claude-sonnet-4-6
INFO agent_0: resonator iteration 1/5 — model=gemini-2.5-pro — verdict=APPROVED
INFO agent_0: enriched brief produced in 1 iteration
INFO agent_0: cultural_angle="..."
INFO agent_0: references=["...", "..."]
INFO agent_bc: iteration 1/5: starting satirist — model=claude-sonnet-4-6
...
```

---

## Key Integration Scenarios

### Scenario 1: Agent 0 reaches consensus on iteration 1

Expected: one Framer call, one Resonator call (APPROVED). EnrichedBrief logged. B/C loop starts immediately.

### Scenario 2: Agent 0 reaches Final Say at iteration 5

Expected: 5 Framer calls, 5 Resonator calls (last one still NEEDS REVISION). Final Say Protocol activates. Log shows `final_say=True`. EnrichedBrief from Framer's iteration-5 response is used.

### Scenario 3: Agent 0 times out

Expected: Pipeline exits within 15 minutes of Agent 0 starting with:
```
ERROR agent_0: timeout after 900s — no enriched brief produced
```
No B/C loop or image generation attempted.

### Scenario 4: Resonator model fails, fallback used

Expected: Log shows:
```
WARNING agent_0: resonator model gemini-2.5-pro failed — trying gemini-2.5-flash
INFO agent_0: resonator ran on fallback model=gemini-2.5-flash
```
Pipeline continues transparently.

### Scenario 5: All models exhausted for one persona

Expected:
```
ERROR agent_0: all models exhausted for Resonator — cannot continue
```
Pipeline exits. B/C loop not started.

### Scenario 6: B/C loop with migrated `<verdict>` tag

The Satirist now wraps its creative output in `<verdict>` instead of `<image_prompt>`. From the operator's perspective this is invisible — the output image is still produced. In the logs and test assertions the tag name has changed; all existing behaviour is preserved.

---

## Testing Agent 0 in Isolation

```python
from unittest.mock import patch, MagicMock
from agents.agent_0 import run
from agents.types import StrategyBrief

seed = StrategyBrief(
    target_audience="Portuguese adults",
    output_language="Portuguese",
    tone="sarcastic"
)

# Mock DualPersonaLoop to return a fixed verdict content
with patch("agents.agent_0.DualPersonaLoop") as MockLoop:
    instance = MockLoop.return_value
    instance.run.return_value = (
        "CULTURAL ANGLE: Lisbon housing crisis as cat territorial dispute.\n"
        "REFERENCES:\n- The 2024 rent control protests\n- Airbnb landlord memes"
    )
    result = run("Housing crisis in Lisbon", seed)

assert result.cultural_angle != ""
assert len(result.culturally_loaded_references) >= 1
assert result.target_audience == seed.target_audience  # locked
```
