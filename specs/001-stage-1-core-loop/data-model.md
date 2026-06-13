# Data Model: Stage 1 Core Loop

**Branch**: `001-stage-1-core-loop` | **Date**: 2026-04-25


All entities are in-memory Python dataclasses passed between modules. The only persisted output
is `output/cartoon_output.png`.

---

## Entities

### StrategyBrief

Captures the creative framing for the pipeline run. Validated at entry — all three fields must be non-empty strings.

| Field           | Type | Required | Description                                                          |
|-----------------|------|----------|----------------------------------------------------------------------|
| target_audience | str  | Yes      | Who the cartoon is made for (e.g., "Portuguese-speaking adults")     |
| output_language | str  | Yes      | Language for all textual content in the cartoon (e.g., "Portuguese") |
| tone            | str  | Yes      | Stylistic register (e.g., "dry wit", "absurdist", "sharp satire")    |

**Validation rules**:

- Each field must be non-empty after stripping whitespace
- A `ValueError` is raised identifying the missing field(s) before any agent is called

---

### CartoonConcept

Produced by Agent B (Satirist) on each iteration. Represents one candidate cartoon.

| Field        | Type | Description                                                             |
|--------------|------|-------------------------------------------------------------------------|
| full_text    | str  | The full raw response from the Satirist, including prose and XML tags   |
| image_prompt | str  | Extracted content of `<image_prompt>…</image_prompt>` — sent to Agent D |
| iteration    | int  | Which loop iteration produced this concept (1–5)                        |

**Invariant**: `image_prompt` is never empty. If regex extraction fails, the concept is invalid and the pipeline retries
the Satirist call.

**image_prompt must include** (per constitution):

- Gata's full character description — always source verbatim from constitution.md Section 4, never paraphrase or summarise
- Visual style descriptors (Selective Color, 1970s newsroom, chalkboard)
- Board heading "ON THE SPOT" or its target-language equivalent
- Caption in `output_language`
- No reference to copyrighted characters or artists

---

### Critique

Produced by Agent C (Critic/Gemini) for each `CartoonConcept`. Informs the next Satirist iteration.

| Field                 | Type | Description                                                                       |
|-----------------------|------|-----------------------------------------------------------------------------------|
| feedback              | str  | Structured feedback text; MUST reference specific changes from previous iteration |
| approved              | bool | True = concept meets quality bar and language rules; False = revise               |
| language_check_passed | bool | True = all text in image_prompt is in `output_language` with no English leakage   |

**Validation rules**:

- If `language_check_passed=False`, `approved` MUST also be `False`
- Feedback on iteration > 1 MUST reference the delta from the previous concept; generic feedback not referencing the
  previous iteration is invalid

---

## State Transitions

```
                    ┌─────────────────────────────────────┐
                    │            Pipeline Start            │
                    │  inputs: NewsTopic + StrategyBrief  │
                    └──────────────┬──────────────────────┘
                                   │ validate inputs
                                   ▼
                         ┌─────────────────┐
                         │  Satirist (B)   │  iteration = 1
                         │  → CartoonConcept│
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Critic (C)     │
                         │  → Critique     │
                         └────────┬────────┘
                                  │
                    ┌─────────────┴──────────────┐
                    │                            │
              approved=True              approved=False
              OR iteration=5             AND iteration<5
                    │                            │
                    ▼                            ▼
           ┌──────────────┐            iteration += 1
           │ Agent D:     │       Satirist receives critique
           │ Image Gen    │            (loop back to B)
           └──────┬───────┘
                  │
                  ▼
        output/cartoon_output.png
```

---

## Data Flow Between Modules

```
pipeline.py
  │  NewsTopic (str)
  │  StrategyBrief (dataclass)
  │
  ├─► agent_bc.run(topic, brief)
  │     internal loop:
  │       CartoonConcept ← Satirist
  │       Critique       ← Critic
  │     returns: CartoonConcept (approved or final)
  │
  └─► agent_d.generate(concept, brief)
        reads:  concept.image_prompt
        writes: output/cartoon_output.png
        returns: Path (str)
```

---

## File Output

| Path                        | Format | Lifecycle                                                |
|-----------------------------|--------|----------------------------------------------------------|
| `output/cartoon_output.png` | PNG    | Overwritten on each successful run; not committed to git |

Write safety: Agent D writes to a temporary path first, then performs an atomic rename to `output/cartoon_output.png`.
If image generation fails, the existing file (if any) is left intact.
