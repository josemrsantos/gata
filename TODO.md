# TODO

## Spec 032 — LLM provider configurability + cross-provider fallback

Config-driven aggregator/panelist LLM selection, plus automatic failover to a different
LLM provider when all known models of the current one are exhausted — applies to every
agent role (aggregator and panelists).

---

## Spec 033 — Enhanced cost reporting

Per-agent breakdown of which LLM/model was used and its estimated cost, plus a disclaimer
that all figures are estimates based on last-known token pricing.

---

## Spec 034 — FairParallelPanel protocol

New coordination protocol where the aggregator (Python layer) runs configurable iterations:
collects panelist responses within a configurable timeout (default 30s), shares all on-time
responses back to all participating panelists, repeats for N iterations (default 2), then
sends final proposals to the aggregator LLM to decide. Coordination logic lives inside the
Aggregator class.

**Dependency:** Requires Spec 032.

---

## Spec 035 — Direct Satirist mode

Flag (e.g. `--direct-prompt`) that bypasses the Cultural Strategist and feeds the user's
intent straight to the Satirist, for cases where the extra agent introduces drift rather
than value.

---

## Voting system — funny / not funny

Allow people to rate each cartoon. Votes feed back into the pipeline to improve future
output (e.g. weight satirical angles that score well, retire angles that consistently
score low).

Things to figure out:
- Where cartoons are served (needed before voting UI can be designed)
- Vote storage — per cartoon, per community, over time
- Whether votes influence prompt generation or community config directly
- Abuse / ballot stuffing prevention

---

## Self-documenting CLI

**Goal:** Calling the pipeline script with no arguments (or with `--help`) should display all available calling modes with concrete, ready-to-edit examples.

**Reason:** Make it immediately clear what options exist and give the developer an example they can copy and tweak — no need to read the source or the README to know how to run a specific image.

**Success criteria:** Running `python pipeline.py` alone prints usage with at least one fully worked example per mode (manual, community, random).

---

## LLM communication protocol framework

**Goal:** Build a protocol framework inside `llm/` that supports different kinds of
structured conversations between LLM agents — not just the current proposer/reviewer
dual-loop, but other topologies (e.g. round-table, chain-of-thought relay, parallel
panel with aggregation).

**Reason:** `dual_loop.py` is the first inter-LLM protocol but it hardcodes a single
conversation shape. As the pipeline grows, new interaction patterns will be needed.
A protocol framework gives each pattern a clean, testable home and lets agents be wired
into different conversation topologies without changing their own code.

**Dependency:** Requires spec 024 (LLM provider abstraction + `llm/` folder) to be
complete first.

---

## Gemini fact-check gate with FACT tag

**Goal:** After the Satirist produces a concept proposal, the Co-Satirist must also perform
a thorough fact-check of every specific claim (dates, names, events, economic figures). If
any claim is factually wrong, it must be returned with an explicit `FACT:` tag that the
Satirist cannot skip or override.

**Reason:** The Satirist/Co-Satirist loop currently chases the funniest angle but does not
verify factual accuracy. This allowed a clearly impossible detail (Mário Soares "reforma em
2026", when he died in January 2017) to pass through unchallenged and appear in the
generated image.

**Success criteria:** A concept containing a verifiable factual error is caught, returned
with a `FACT:` tag, and corrected before the image prompt is finalised. A concept with no
factual errors passes through without triggering the tag.