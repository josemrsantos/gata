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

---

## Curated, paywall-free references

**Goal:** Trim the Sources list to only references still relevant to the article's final
published state (drop stale ones left over from earlier drafts), exclude any URL behind a
paywall, and target 5–9 total references from academically credible or highly reliable
sources rather than minor online outlets.

**Reason:** Today's Sources list can carry outdated leftover links, paywalled URLs a reader
can't actually open, and low-quality outlets — undermining the credibility a "researched,
non-satirical" article is meant to have.

---

## Optional image-free mode

**Goal:** Add a flag to skip cartoon/image generation entirely, so the pipeline can produce
just the researched article/report.

**Reason:** Every run currently generates a satirical image regardless; the operator wants
to use the researched-article path as a standalone research tool without the cost/latency
of image generation.

---

## Lightweight webserver front-end

**Goal:** Stand up a lightweight webserver that can trigger the `gata` CLI (e.g. "generate a
report on X") over HTTP instead of only via terminal.

**Reason:** Enables using the tool without direct CLI access — a simple request-a-report
workflow.

---

## Move generation to AWS (cost-conscious)

**Goal:** Investigate moving the generation workload to AWS, using free-tier or otherwise
minimal-cost resources where possible.

**Reason:** Currently runs locally only; AWS hosting would enable the webserver idea and
other remote-access use cases, kept as cheap/free as this side project needs.
