# TODO

## Voting system — funny / not funny

Allow people to rate each cartoon. Votes feed back into the pipeline to improve future
output (e.g. weight satirical angles that score well, retire angles that consistently
score low).

Things to figure out:
- Where cartoons are served (needed before voting UI can be designed)
- Vote storage — per cartoon, per community, over time
- Whether votes influence prompt generation or community config directly
- Abuse / ballot stuffing prevention


## Post-generation image review

After `agent_image_generator.generate()` saves the image, pass it to a vision model to check for
rendering artifacts before accepting the output. Known failure modes to detect:

- Duplicate text labels (e.g. "Interest Rates — Now Yours" appearing twice on the board)
- Illegible or garbled chalkboard text
- Gata character integrity failures (wrong colours, accessories added, not present)
- Missing elements from the prompt that are load-bearing for the joke

If the review fails, trigger a regeneration (up to N retries) before writing the bundle.

---
## Error Handling (Local)

**Goal:** Make the pipeline robust before any cloud deployment or automated scheduling.

**What to harden:**
- Agent B/C parse failure (proposer response missing `<verdict>` tag) → retry with a clarification prompt rather than crashing
- Gemini image generation content policy rejection → feed rejection back to Agent B/C to produce an alternative prompt; a cartoon is always generated (current behaviour: model fallback chain only, no B/C feedback loop)
- All errors and loop outcomes logged to a per-run local file (current behaviour: stdout logging only)

**Success criteria:** Deliberately triggering each failure mode produces a graceful recovery and a generated cartoon, not a crash or a skipped run.


## Distribution (AWS)

**Goal:** Push output to AWS for the first externally visible deliverable.

**What is active:**
- Upload `cartoon_output.png` to S3 via `boto3`
- Output folder structure TBD — likely organised by community or target (e.g. `cartoons/portuguese_football_fans/2026-04-19.png`)
- A static webpage will display the cartoons — technology and hosting details TBD
- IAM role / credentials scoped to S3 write only

> **Note:** Complete this stage before resolving the compute architecture question — it delivers something visible regardless of which compute path is chosen.

**Success criteria:** After a local run, the cartoon is accessible via the web in the expected folder location.

---

## Compute Architecture Decision

**Goal:** Choose the right AWS compute model before committing to scheduling infrastructure.

**Input required:** Wall-clock timings from Stage 1 (core loop only) and Stage 3 (with Agent 0 active) — Agent 0 adds meaningful latency through its negotiation loop.

| Option                | Best if                        | Trade-offs                                      |
|-----------------------|--------------------------------|-------------------------------------------------|
| **AWS Lambda**        | Total runtime < 15 min         | Simplest setup; cold starts; 10 GB memory limit |
| **AWS Batch (Spot)**  | Runtime 15–60 min              | Significant cost saving; more setup overhead    |
| **EC2 Spot**          | Runtime > 60 min or GPU needed | Most flexible; most operational overhead        |
| **Local RaspberryPi** | Already own one                | Must have it always running                     |

**Success criteria:** A documented decision with the chosen option and rationale, ready to hand off to Stage 8.

---

## Scheduling (AWS)

**Goal:** Run the pipeline automatically on a daily schedule with no manual intervention.

**What is active:**
- AWS EventBridge cron rule triggers the chosen compute target daily
- The orchestrator iterates through the configured community list, producing one cartoon per community per run
- Output lands in S3 automatically under the correct community folder
- Failure notifications via SNS or CloudWatch alarm

**Success criteria:** The pipeline runs overnight without being manually triggered, and cartoons appear in S3 the next morning for every configured community.

---

## Self-documenting CLI

**Goal:** Calling the pipeline script with no arguments (or with `--help`) should display all available calling modes with concrete, ready-to-edit examples.

**Reason:** Make it immediately clear what options exist and give the developer an example they can copy and tweak — no need to read the source or the README to know how to run a specific image.

**Success criteria:** Running `python pipeline.py` alone prints usage with at least one fully worked example per mode (manual, community, random).

---

## Web research before image proposal (Claude / Cultural Strategist)

**Goal:** Before Claude proposes a satirical concept, it must perform a web search on the topic to ground the proposal in verifiable facts.

**Reason:** Without research, Claude invents plausible-sounding but factually wrong details (e.g. placing a living milestone for a person who has been dead for years). Research must happen before the concept is written, not after.

**Success criteria:** Agent 0 / the proposer always runs at least one web search on the topic before producing the cultural angle and enriched brief — and repeats a web search for every reply from Gemini that is marked with a `FACT:` tag before formulating its response.

---

## Gemini fact-check gate with FACT tag

**Goal:** After Claude produces a concept proposal, Gemini must perform a thorough fact-check of every specific claim (dates, names, events, economic figures). If any claim is factually wrong, Gemini must return it to Claude with an explicit `FACT:` tag that Claude cannot skip or override.

**Reason:** The B/C loop currently checks tone and quality but not factual accuracy. This allowed a clearly impossible detail (Mário Soares "reforma em 2026", when he died in January 2017) to pass through unchallenged and appear in the generated image.

**Success criteria:** A concept containing a verifiable factual error is caught by Gemini, returned to Claude with a `FACT:` tag, and Claude must correct the error before the image prompt is finalised. A concept with no factual errors passes through without triggering the tag.
