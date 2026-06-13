# Gata Newsroom — Project Blueprint v2.0

## 1. Vision

An automated multi-agent pipeline that transforms daily news into a recurring satirical cartoon series starring **Gata**, a serious, investigative calico cat who views all geopolitics through the lens of feline priorities. The pipeline runs locally during development, then migrates to a low-cost AWS deployment once the core loop is stable.

---

## 2. Collaborative Agent Pattern

Two of the pipeline's agents are **dual-persona collaborative agents**. Each is a single logical agent whose output is the product of two LLM personas negotiating toward consensus. Both agents follow the same structure and the same iteration rules.

### Dual-Persona Iteration Rules *(applies to Agent 0 and the Agent B/C pair)*

These rules are identical for both collaborative agents and must always be implemented the same way:

- Each round, **both personas must agree on something new** — the loop must make measurable progress toward consensus each iteration; repeating or restating previous positions is not permitted
- Maximum **5 iterations** (configurable — to be revisited once timing and cost data is available from real runs)
- If consensus is reached before 5 rounds, the output is passed downstream immediately
- If no consensus is reached after 5 rounds, **the Claude-powered persona makes the final call**, but must genuinely consider the Gemini-powered persona's input and may defer to Gemini's position if it is better grounded — the goal is the best output, not Claude winning
- A cartoon is always generated. What is acceptable is that some cartoons will not be funny.

---

## 3. Agent Definitions

### Agent 0 — The Cultural Strategist *(dual-persona collaborative agent)*

**What it is:** One agent, two personas powered by different LLMs, working iteratively to agree on a cultural strategy brief. The brief governs the target audience, language, satirical angle, tone, and any culturally-loaded references that will be passed downstream to the creative agents.

#### Persona 1 — The Framer *(Claude Sonnet — `claude-sonnet-4-6`)*

| Field | Detail |
|---|---|
| **Role** | Cultural Angle & Tone Proposer |
| **Persona** | A perceptive cultural writer who finds the satirical hook inside a story and frames it for a specific tribe |

**Responsibilities:**
- Identify the target audience — a tribe defined by politics, sport, nationality, community event, or any other axis
- Determine the **output language** — all downstream content (captions, board text, jokes) must be produced in this language
- Propose the cultural angle: what is the satirical reading of this story for this audience?
- Set the tone (e.g. dry and deadpan, sharp and angry, absurdist, warm and ironic)
- Surface **culturally-loaded references** — observations not in the news item itself, but widely known by the target group (e.g. a politician's well-known scandal, a shared cultural memory, an inside reference that sharpens the joke). These are flagged explicitly in the brief

#### Persona 2 — The Resonator *(Gemini 1.5 Pro)*

| Field | Detail |
|---|---|
| **Role** | Context & Sentiment Validator |
| **Persona** | A sharp, globally-aware editor who stress-tests whether a proposed angle will land — or backfire |

**Responsibilities:**
- Stress-test The Framer's proposed angle against broader cultural context and current sentiment
- Validate or challenge the cultural references and the chosen language
- Flag if the angle is likely to confuse, alienate, or offend in a way that undermines the satire
- Propose alternative angles or adjustments — not just critique

**Output of Agent 0:** A strategy brief containing: target audience, output language, cultural angle, tone, and any culturally-loaded references to exploit.

*Iteration rules: see Section 2.*

---

### Agent A — The Trend Scout *(optional single-engine agent)*

| Field | Detail |
|---|---|
| **Role** | Data Aggregator & Filter |
| **Persona** | A cynical, data-driven news editor who understands what makes people angry or excited |
| **Engine** | Gemini 1.5 Flash |
| **Output** | Top 3 ranked headlines with a "Heat Index" score |

**This agent is optional.** In the initial version of the pipeline, news topics are supplied manually or via a pre-configured list of target communities and groups. Agent A is a later addition that automates topic discovery once the rest of the pipeline is stable.

**Responsibilities (when active):**
- Scrape headlines from one or more configured news sources (specific sources TBD — architecture must remain source-agnostic)
- Score each story by volume of discussion / engagement ("Heat Index")
- Pass the top 3 headlines downstream to Agent B/C

---

### Agent B / Agent C — The Creative Studio *(dual-persona collaborative agent)*

**What it is:** One agent, two personas powered by different LLMs, working iteratively to agree on the final image prompt — including the visual gag, the chalkboard content, and Gata's position and pose. All creative output must be in the **language specified in Agent 0's brief**.

#### Persona 1 — The Satirist / Agent B *(Claude Sonnet — `claude-sonnet-4-6`)*

| Field | Detail |
|---|---|
| **Role** | Creative Writer & Pun-smith |
| **Persona** | A witty, slightly subversive comedy writer who sees all human geopolitics as secondary to a warm radiator ("Cat Law") |

**Responsibilities:**
- Receive the top headlines from Agent A and the full strategy brief from Agent 0
- Write the satirical concept through the lens of the target audience, cultural angle, and tone
- Exploit any culturally-loaded references flagged by Agent 0 where they sharpen the joke
- Produce all written content (captions, board text, jokes) in the language specified in the brief
- Propose **Gata's physical position and pose** in the scene — this is a creative decision, not just a prompt detail
- Wrap the final image description in `<image_prompt>...</image_prompt>` tags

#### Persona 2 — The Editorial Critic / Agent C *(Gemini Flash)*

| Field | Detail |
|---|---|
| **Role** | Quality Control & Visual Logic |
| **Persona** | A no-nonsense, minimalist director who hates clutter and cheap jokes |

**Responsibilities:**
- Review the Satirist's image prompt and Gata's proposed position
- Reject prompts that are: too visually busy, unreadable in charcoal, or break the "Gata is a real cat" rule
- Evaluate whether Gata's proposed position serves the visual gag — suggest an alternative pose if not
- Verify that all written content in the prompt is in the correct language per the brief
- Drive refinement toward the "Less is More" standard — approve only when the prompt is visually clean and the joke is sharp

**Output of Agent B/C:** An approved `<image_prompt>` containing the visual scene, chalkboard content, Gata's confirmed position, and a dry caption — all in the target language.

*Iteration rules: see Section 2.*

---

### Agent D — The Image Generator *(execution, not reasoning)*

| Field | Detail |
|---|---|
| **Role** | Visual Output |
| **Engine** | `gemini-3.1-flash-image-preview` via `google-genai` SDK |
| **Output** | `cartoon_output.png` saved as binary from `part.inline_data.data` |

---

## 4. Data Flow

```
[Target community / topic — manual or pre-configured list]
                                   │
                                   ▼
                ┌─────────────────────────────────────────────┐
                │         Agent 0 — Cultural Strategist        │
                │  The Framer (Claude) ◄──────► The Resonator  │
                │              (Gemini 1.5 Pro)                │
                │           up to 5 iterations                 │
                └──────────────────┬──────────────────────────┘
                                   │  strategy brief:
                                   │  target audience, language,
                                   │  cultural angle, tone,
                                   │  cultural references
                                   ▼
          [news topic — manual input
           OR Agent A: Trend Scout (optional, Gemini 1.5 Flash)]
                                   │  topic / headline
                                   ▼
                ┌─────────────────────────────────────────────┐
                │       Agent B/C — Creative Studio            │
                │  The Satirist (Claude) ◄────► The Critic     │
                │                        (Gemini Flash)        │
                │           up to 5 iterations                 │
                └──────────────────┬──────────────────────────┘
                                   │  approved <image_prompt>
                                   │  + Gata's confirmed position
                                   │  + all text in target language
                                   ▼
                Agent D: Image Generator (gemini-3.1-flash-image-preview)
                                   │
                                   ▼
                           cartoon_output.png
                                   │
                                   ▼
                       [Local / S3 distribution]
```

---

## 5. Character Specifications — Gata

These physical traits must be included in every final image prompt to maintain visual consistency across episodes. They do not change with language or audience.

| Feature | Specification |
|---|---|
| **Species** | Domestic Shorthair, tricolor calico-tabby mix |
| **Markings** | White chest, muzzle, and paws; dark grey/black tabby stripes; orange/ginger patches on back |
| **Defining Mark** | A small dark spot on the bridge of her pink nose |
| **Collar** | Simple dark leather collar with a gold/brass nameplate engraved with "GATA" |
| **Personality** | Serious, investigative, slightly tired, highly intelligent |
| **Rule** | No human clothes or accessories — Gata is always a real cat |

### Gata's Pose Library

Rather than describing poses from scratch each episode, Agent B and Agent C will select from a library of **validated named poses**. Named poses ensure the image generator maintains character consistency across episodes. Agent B proposes a pose by name; Agent C approves or substitutes.

> **Pose library TBD.** Deferred to Stage 2 — named poses will be defined based on real run data from Stage 1. May be optionally specified per community in communities.yaml. Each pose will have a short name (e.g. `THE_INVESTIGATOR`) and a precise physical description for the image prompt.

> **Recurring gag note:** Gata's defining dark nose-spot lends itself naturally to identity and biometric jokes (travel bans, border controls, facial recognition). This is not a required recurring element, but worth exploiting when the news topic fits.

---

## 6. Visual Style Guide

The visual environment is fixed and does not change between episodes. What **does** change with the target audience is all written content: captions, board text, jokes, and labels must always be in the **language specified in Agent 0's brief**.

### Fixed Visual Environment

| Element | Specification |
|---|---|
| **Color palette** | Strictly black and white (grayscale) background; Gata rendered in full, vibrant color (Selective Color style) |
| **Setting** | A 1970s-era newspaper newsroom — flickering fluorescent lights, heavy metal desks, blurred background characters in ties and short-sleeve shirts |
| **The board** | A large dark chalkboard with hand-drawn white sketches; heading always reads **"ON THE SPOT"** (or its equivalent in the target language) |
| **Attachments** | Use masking tape for photos or documents on the board — no pins |
| **Visual logic** | Main drawing must be simple and high-contrast; avoid visual clutter |
| **Style descriptor** | Single-panel satirical cartoon, minimalist charcoal-on-chalkboard style, high-contrast, dry caption at the bottom |

### Language Adaptation

All written content in the image prompt adapts fully to the target audience's language and cultural register. This includes:

- The dry caption at the bottom of the panel
- Any text on the chalkboard (labels, diagrams, annotations)
- The board heading ("ON THE SPOT" → "EM DIA" for Portuguese, "EN DIRECTO" for Spanish, etc.)
- Any puns, wordplay, or culturally-loaded references — these must be written to land for the target audience, not translated literally

Agent C (The Editorial Critic) is responsible for verifying that the language and cultural register in the final prompt are correct for the specified audience.

> **Copyright rule:** Never reference copyrighted artists or characters (e.g. The Far Side, Calvin and Hobbes). Always describe the visual style using physical characteristics only.

---

## 7. Technical Stack

| Layer | Tool / Library | Notes |
|---|---|---|
| Concept generation | `anthropic` SDK — `claude-sonnet-4-6` | Never deviate from this model string |
| Image generation | `google-genai` SDK — `gemini-3.1-flash-image-preview` | Never use legacy `google-generativeai` |
| Cultural strategy | `google-genai` — Gemini 1.5 Pro | Agent 0 / The Resonator |
| News scraping | TBD — RSS, NewsAPI, or other | Optional (Agent A); architecture must remain source-agnostic |
| Cloud storage | AWS S3 (`boto3`) | Existing bucket at josemrsantos.com |
| Scheduling | AWS EventBridge | Stage 7 — after compute architecture is decided |
| Local orchestration | Python 3.x, plain scripts | No framework needed for early stages |

### XML Contract

The Satirist (Agent B / Claude) must always be instructed to wrap the image description in XML tags. The orchestrator parses these deterministically:

```python
import re
prompt = re.search(
    r'<image_prompt>(.*?)</image_prompt>',
    response.content[0].text,
    re.DOTALL
).group(1)
```

### Image Extraction (Critical)

The `google-genai` SDK returns images as binary data — never as a URL. Always use:

```python
for part in img_response.candidates[0].content.parts:
    if part.inline_data:
        with open("cartoon_output.png", "wb") as f:
            f.write(part.inline_data.data)
```

---

## 8. Cost Reference (April 2026)

| Model | Cost per image |
|---|---|
| Gemini 3.1 Flash Image — 1024×1024 | ~$0.067 |
| Gemini 3.1 Flash Image — Batch | ~$0.034 |
| Gemini 3 Pro Image — 1024×1024 | ~$0.134 |

> During development, use Google AI Studio's free tier — no billing required.

---

## 9. Open Questions

- [ ] Which initial target communities and groups should the pipeline be configured for? These seed the pipeline before Agent A is available.
- [ ] Agent A (Trend Scout) is optional and a later addition — news source mechanism TBD when the time comes. Architecture must remain source-agnostic.
- [ ] Iteration cap is set to **5** for both collaborative agents. To be revisited once real timing and cost data is available.
- [ ] Static webpage details TBD — technology and hosting approach to be confirmed.
- [ ] Output naming convention — pattern should include community/target group, timestamp, and tone (e.g. `output/{community}/{timestamp}_{tone}.png`). To be defined and implemented in Stage 2 alongside community configuration. Fixed filename `cartoon_output.png` is intentional for Stage 1 only.
- [ ] Dual-persona negotiation loop (Agent B/C and Agent 0) is a reusable pattern — consider extracting as a standalone module or library once both use cases are implemented in Stage 3. A separate "LLM discussion" project may be worth spinning off at that point.
- [ ] Iteration log — save a full log of every B/C loop iteration (concept, critique, approval status) to a separate file per run (e.g. `output/logs/{timestamp}_iterations.json`). To be implemented in Stage 4.
- [ ] Joke explanation — the Satirist includes a `<joke_explanation>` block alongside `<image_prompt>` in its final response. The orchestrator parses and saves it to `output/logs/{timestamp}_explanation.md`. No additional API call needed. To be implemented in Stage 4.
- [ ] Fallback images — two static PNG files (one for Gemini API failure, one for Claude/Anthropic API failure) that are copied to `output/cartoon_output.png` when the respective API fails. Filenames: `assets/fallback_gemini.png` and `assets/fallback_claude.png`. To be implemented in Stage 4.
- [ ] Claude API retry on failure (Stage 4) — replace the Stage 1 fail-fast behaviour with a retry decorator: 3 attempts with delays of 15 min, 30 min, and 60 min. If all retries are exhausted, fail with a clear error. AWS Bedrock as a permanent fallback is a separate consideration for a later stage.
- [ ] Voting system — after each cartoon is published, allow readers to answer three questions: (1) Do you identify with [target group]? (2) Did you understand the joke? (3) Did you find it funny? Optional free-text field TBD. Requires a web interface, user identity mechanism, and database. Deferred until after Stage 5 (S3 distribution) is complete.
- [ ] B/C loop API fallback (Stage 4) — if either Gemini (critic) or Claude (satirist) is unavailable, fall back to the other LLM assuming the opposite persona. The system prompts differ per role even if the same LLM is used. If Claude assumes the critic role, the prompt must include an explicit web search instruction AND the web_search tool must be passed in the `tools` parameter of the `messages.create()` API call — a prompt instruction alone is insufficient to activate web search. If Gemini assumes the satirist role, temperature must be explicitly set to 0.8 in `GenerateContentConfig`.
