# Data Model: Text Output Bundle

## New Types (agents/types.py additions)

### ConversationTurn

Represents a single proposer-reviewer exchange within one iteration of a dual-persona loop.

| Field | Type | Description |
|-------|------|-------------|
| `iteration` | `int` | 1-based iteration number within the loop |
| `role` | `str` | Persona name (e.g. "Framer", "Resonator", "Satirist", "Critic") |
| `text` | `str` | Full text of the response from this persona |
| `verdict` | `str` | `"APPROVED"`, `"NEEDS REVISION"`, or `"FINAL_SAY"` — always set on the reviewer turn; always `""` on the proposer turn |

**Notes**:
- Each iteration produces exactly two `ConversationTurn` objects: one proposer, one reviewer.
- `verdict` is `""` (empty string) on proposer turns to keep the type uniform.
- `"FINAL_SAY"` is used when the proposer invoked the Final Say Protocol (iteration ==
  max_iterations and last_feedback was non-empty).

### ConversationLog

Ordered collection of all turns from a single dual-persona loop run.

| Field | Type | Description |
|-------|------|-------------|
| `loop_name` | `str` | Human-readable loop identifier — `"Agent 0"` or `"B/C"` |
| `turns` | `list[ConversationTurn]` | All turns in chronological order |

**Notes**:
- `turns` length equals `(actual_iterations × 2)` — two turns per iteration.
- The final reviewer turn has `verdict == "APPROVED"` if the loop ended with consensus, or
  `"FINAL_SAY"` if the Final Say Protocol was triggered.

### LoopOutput

Return value of `DualPersonaLoop.run()` — replaces the bare `str`.

| Field | Type | Description |
|-------|------|-------------|
| `verdict` | `str` | The final proposer verdict text (previously the raw return value) |
| `log` | `ConversationLog` | Complete turn-by-turn conversation record |

**Notes**:
- Existing callers (`agent_0`, `agent_bc`) access `loop_output.verdict` to get the same
  string they previously received directly.

---

## Updated Agent Return Signatures

### agent_0.run()

**Before**: `run(topic: str, seed_brief: StrategyBrief) -> EnrichedBrief`

**After**: `run(topic: str, seed_brief: StrategyBrief) -> tuple[EnrichedBrief, ConversationLog]`

Returns both the enriched brief and the full Agent 0 conversation log.

### agent_bc.run()

**Before**: `run(topic: str, enriched_brief: EnrichedBrief) -> CartoonConcept`

**After**: `run(topic: str, enriched_brief: EnrichedBrief) -> tuple[CartoonConcept, ConversationLog]`

Returns both the cartoon concept and the full B/C conversation log.

---

## Data Flow

```
pipeline.py
  │
  ├─ agent_0.run(topic, seed_brief)
  │      └─ returns (EnrichedBrief, ConversationLog[loop_name="Agent 0"])
  │
  ├─ agent_bc.run(topic, enriched_brief)
  │      └─ returns (CartoonConcept, ConversationLog[loop_name="B/C"])
  │
  ├─ agent_d.generate(concept, enriched_brief, output_path)
  │      └─ writes PNG to output_path
  │
  └─ bundle_writer.write_bundle(
         output_path,
         agent0_log,
         bc_log,
         enriched_brief,
         concept.image_prompt
     )
         ├─ formats logs as text → writes agent0_log.txt, bc_log.txt
         ├─ agent_explainer.generate_html(enriched_brief, agent0_log, bc_log, image_prompt)
         │      └─ returns (in_language_html: str, english_html: str)
         ├─ writes explanation.html (in target language)
         ├─ writes deep_dive_en.html (in English)
         └─ writes prompt_card.txt
```

---

## Bundle Folder Layout

Given output path `output/portuguese_adults/pt_sporting_cp.png`, the bundle folder is:

```text
output/portuguese_adults/pt_sporting_cp/
├── agent0_log.txt        # Agent 0 conversation (Framer ↔ Resonator)
├── bc_log.txt            # B/C conversation (Satirist ↔ Critic)
├── explanation.html      # In-language explanation (Portuguese)
├── deep_dive_en.html     # English deep-dive for operator
└── prompt_card.txt       # Verbatim image prompt
```

The bundle folder name equals `Path(output_path).stem` and is located in
`Path(output_path).parent`.
