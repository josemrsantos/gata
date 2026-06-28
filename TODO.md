# TODO

## Spec 035 — Direct Satirist mode

Flag (e.g. `--direct`) that bypasses the Cultural Strategist and feeds the user's
intent straight to the Satirist, for cases where the extra agent introduces drift rather
than value.

---

## Spec 036 — Per-provider call timeout

**Goal:** Give each provider in a Spec 032 fallback chain its own individual timeout, so
the total slot budget is divided precisely rather than shared opaquely.

**Reason:** Telemetry from real runs shows wide latency spread across providers:
- Claude Sonnet 4.6: ~15–20s per call (high output token count: 500–750 avg)
- Grok-3 (aggregator): ~10–15s (300–530 output tokens)
- Grok-3-mini: ~5–7s (150–340 output tokens)
- Gemini 2.5 Flash: ~3–10s (output length varies widely: 79–430 tokens)
- Gemini 2.5 Pro (evaluator): ~15–22s regardless of output length (thinking-heavy)
- Gemini image generation: ~8–21s depending on complexity

Today, `FairParallelPanel` has a single `panelist_timeout` for the whole slot (primary +
all fallbacks). If Claude hangs at 55s on a 60s budget, the fallback gets only 5s — which
is enough for Gemini Flash but not for Claude or Grok-3. A per-provider timeout (e.g. 25s)
would let Claude time out cleanly and hand off to a fallback with a full budget of its own.

**Implementation idea:** add `provider_timeout: float | None = None` to `_call_persona()`;
wrap each `provider.generate()` call in a `ThreadPoolExecutor` future with that timeout.
When `None`, call is unbounded (current behaviour, no regression).

**Dependency:** Spec 032 (provider chains) + Spec 034 (FairParallelPanel).

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
