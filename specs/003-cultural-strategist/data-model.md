# Data Model: Agent 0 — Cultural Strategist

## Entities

### EnrichedBrief *(new)*

The output of Agent 0. Carries the three locked seed fields plus the two fields added by Agent 0.

| Field | Type | Source | Notes |
|---|---|---|---|
| `target_audience` | `str` | Locked from seed | Never modified by Agent 0 |
| `output_language` | `str` | Locked from seed | Never modified by Agent 0 |
| `tone` | `str` | Locked from seed | Never modified by Agent 0 |
| `cultural_angle` | `str` | Agent 0 output | Non-empty; the satirical reading of the topic for the audience |
| `culturally_loaded_references` | `list[str]` | Agent 0 output | Non-empty list; each item is one short observation known to the target audience |

**Validation rules**:
- `cultural_angle` must be non-empty after Agent 0 completes
- `culturally_loaded_references` must contain at least one non-empty string
- If either is empty, Agent 0 raises `ValueError` before returning

---

### PersonaConfig *(new)*

Configuration for one side of the dual-persona loop. Used by `DualPersonaLoop`.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Display name for logging (e.g., "Framer", "Resonator") |
| `models` | `list[str]` | Ordered fail-over chain; at least one model required |
| `system_prompt` | `str` | Full system prompt for this persona |

---

### DualLoopResult *(internal)*

Internal state tracked per iteration inside `DualPersonaLoop`. Not exposed outside the module.

| Field | Type | Notes |
|---|---|---|
| `iteration` | `int` | 1-based iteration counter |
| `proposer_output` | `str` | Raw content of the proposer's `<verdict>` tag |
| `reviewer_verdict` | `str` | `"APPROVED"` or `"NEEDS REVISION"` |
| `reviewer_feedback` | `str` | Full reviewer response text |
| `final_say` | `bool` | True if this iteration was the Final Say (iteration == max_iterations) |

---

### StrategyBrief *(existing — unchanged)*

Input to Agent 0. Loaded from `communities.yaml` or supplied via CLI in manual mode.

| Field | Type |
|---|---|
| `target_audience` | `str` |
| `output_language` | `str` |
| `tone` | `str` |

---

### CartoonConcept *(existing — field unchanged, tag renamed)*

Output of agent_bc. The `image_prompt` Python field is unchanged. The XML tag that wraps it in the LLM response changes from `<image_prompt>` to `<verdict>` as part of the B/C migration.

| Field | Type | Notes |
|---|---|---|
| `full_text` | `str` | Complete Satirist response |
| `image_prompt` | `str` | Extracted from `<verdict>` tag (was `<image_prompt>`) |

---

## Data Flow

```
communities.yaml / CLI args
         │
         ▼
   StrategyBrief (seed)
         │
         ▼
   agent_0.run(topic, seed_brief)
     ┌─────────────────────────────┐
     │  DualPersonaLoop            │
     │  Framer ◄──────► Resonator  │
     │  up to 5 iterations         │
     └──────────────┬──────────────┘
                    │
                    ▼
           EnrichedBrief
     (seed fields + cultural_angle
      + culturally_loaded_references)
                    │
                    ▼
   agent_bc.run(topic, enriched_brief)
     ┌─────────────────────────────┐
     │  DualPersonaLoop            │
     │  Satirist ◄─────► Critic    │
     │  up to 5 iterations         │
     └──────────────┬──────────────┘
                    │
                    ▼
           CartoonConcept
        (image_prompt from <verdict>)
                    │
                    ▼
           agent_d.generate()
                    │
                    ▼
         output/{community}/{topic}.png
```
