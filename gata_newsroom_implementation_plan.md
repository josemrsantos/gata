# Gata Newsroom — Implementation Plan v2.0

Development follows a strict **local-first, then cloud** approach. Do not skip or reorder stages. Each stage has a clear success criterion — only move on when it is met.

---

## Stage 1 — Core Loop (Local) ✅ *Start here*

**Goal:** Prove the creative pipeline works end to end with the minimum number of moving parts.

**What is active:**
- A hardcoded news topic (no scraping, no community config)
- A hardcoded target audience and tone (no Agent 0 yet)
- Agent B/C — The Creative Studio (Satirist + Editorial Critic, full 5-iteration loop)
- Agent D — The Image Generator

**What is not active yet:** Agent 0, Agent A, any AWS infrastructure.

**Success criteria:** Running `python pipeline.py` with a hardcoded topic and brief produces a saved `cartoon_output.png`. The B/C loop completes at least one iteration and the critic either approves or refines the prompt before the image is generated.

> **Timing note:** Measure the wall-clock time of this full run carefully. It is the baseline input for the compute architecture decision in Stage 6.

---

## Stage 2 — Community Configuration (Local)

**Goal:** Replace the hardcoded topic and brief with a configurable list of target communities and their associated language, tone defaults, and seed topics.

**What is active:**
- A configuration file (e.g. `communities.yaml`) defining named target groups — each with a language, a default tone, and a list of seed news topics to rotate through
- The orchestrator picks a community and topic from the config and passes them directly to Agent B/C
- Agent 0 and Agent A remain inactive

**Example config entry:**
```yaml
communities:
  - name: portuguese_football_fans
    language: pt
    tone: warm and ironic
    topics:
      - "Sporting CP vs Benfica rivalry"
      - "Portugal national team World Cup qualification"
  - name: uk_political_watchers
    language: en
    tone: dry and deadpan
    topics:
      - "House of Commons PMQs"
      - "NHS waiting times"
```

**Success criteria:** The pipeline runs for at least two different communities from config, producing correctly-languaged cartoons for each, with no hardcoded values in the script.

---

## Stage 3 — Cultural Strategist (Local)

**Goal:** Add Agent 0 (The Framer + The Resonator) to replace the hardcoded tone defaults with a negotiated strategy brief.

**What is active:**
- The community and topic still come from the config file
- Agent 0 receives the community and topic, then negotiates the full strategy brief (cultural angle, tone, language, culturally-loaded references)
- The brief is passed to Agent B/C instead of the config defaults
- Full 5-iteration loop with Claude making the final call if no consensus

**Success criteria:** The pipeline produces a cartoon whose satirical angle and culturally-loaded references were not present in the seed config — they emerged from the Agent 0 negotiation.

---

## Stage 4 — Text Output Bundle (Local)

**Goal:** Produce a rich set of text outputs alongside every cartoon — conversation logs, HTML explanations, and a prompt card — to support publishing, fine-tuning, and cross-cultural review.

**What is active:**
- `DualPersonaLoop` captures every turn (proposals, critiques, verdicts with full reasoning) and writes two human-readable log files: one for the Agent 0 loop (Framer↔Resonator), one for the B/C loop (Satirist↔Critic)
- agent-explainer, a new dual-LLM agent, generates two HTML files: an explanation in the cartoon's target language (for end users / web publishing) and an English deep-dive (for the operator, with cultural and news background for when the target culture is foreign)
- A prompt card plain text file containing the exact image prompt sent to the image generator
- All four files are written to a bundle subfolder named after the image file (without extension), located inside the image's output directory
- If the pipeline fails before producing a concept, any completed conversation logs are still written; HTML files are skipped and the failure is logged without aborting the image output

**Success criteria:** Every successful pipeline run produces a bundle folder containing all four file types. The English deep-dive gives an English speaker with no knowledge of the target culture enough background to evaluate whether the cartoon is culturally accurate and funny.

---

