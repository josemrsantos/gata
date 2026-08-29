# TODO

## Curated, paywall-free references — *amends Spec 042*

**Goal:** Trim the Sources list to only references still relevant to the article's final
published state, exclude any URL behind a paywall, and target 5–9 total references from
academically credible or highly reliable sources rather than minor online outlets.

**Reason:** Today's Sources list can carry outdated leftover links, paywalled URLs a reader
can't actually open, and low-quality outlets — undermining the credibility a "researched,
non-satirical" article is meant to have.

**Confirmed approach:**
- The writer panel cites sources inline (a new marker/format tied to the Sources list), so
  code can verify which sources the final published text actually references and drop the
  rest — not an LLM judgment call after the fact.
- Paywall/reliability filtering is a hybrid: an LLM classifies a domain the first time it's
  seen (paywalled? how reliable/academic?), and that verdict is cached in a persistent,
  version-controlled file — suggested `source_domains.yaml` at the repo root, matching the
  existing `providers.yaml`/`humor.yaml`/`communities.yaml` pattern — so repeat domains skip
  the LLM check entirely.

**Things to figure out:**
- Exact `source_domains.yaml` schema (separate paywalled/reliable/unreliable lists, or a
  per-domain rating?) and whether a cached verdict ever expires/gets re-checked.
- Exact inline-citation-marker mechanics and how they interact with `_parse_sections`/
  `_assemble_article`.
- What happens if the final body cites more than 9 sources — ask the writer to trim, or
  truncate in code?

---

## Research-only mode (no image) — *new Spec 046*

**Goal:** Add a mode that skips the entire satirical pipeline (Cultural Strategist,
Satirist, Image Generator, Image Evaluator) and goes straight from topic to the researched-
article path, so the tool can be used purely for research/reporting rather than a satirical
post.

**Reason:** Every run currently generates a satirical image and concept regardless; the
operator wants a genuine research-only mode, not just a suppressed image with wasted
concept-generation cost behind it.

**Confirmed:** skips the full satirical pipeline, not just image rendering.

**Things to figure out:**
- Exact flag shape, and its relationship to existing flags (e.g. `--direct`, spec 035).
- Whether this requires `--linkedin-post` to be set, since without it there would be no
  output at all.
- Output bundle naming/location — today's bundle directory is derived from the cartoon's
  own `output_path`.
- Whether Gata's branding/byline stays on a pure research report, or this becomes a fully
  neutral output.

---

## Lightweight webserver front-end — *new Spec 047*

**Goal:** Stand up a lightweight webserver that can trigger the `gata` CLI (e.g. "generate a
report on X") over HTTP instead of only via terminal.

**Reason:** Enables using the tool without direct CLI access — a simple request-a-report
workflow.

**Things to figure out:**
- Sync vs. async job model — a report takes roughly 5–10 minutes.
- Auth/access control, since each request triggers real paid API calls.
- Framework choice (stdlib `http.server` vs. FastAPI/Flask).
- Whether this depends on Spec 046 (research-only mode) landing first.

---

## Move generation to AWS (cost-conscious) — *new Spec 048*

**Goal:** Investigate moving the generation workload to AWS, using free-tier or otherwise
minimal-cost resources where possible.

**Reason:** Currently runs locally only; AWS hosting would enable remote/scheduled use
cases, kept as cheap/free as this side project needs.

**Confirmed:** standalone from Spec 047 — not necessarily tied to hosting the webserver.

**Things to figure out:**
- Which free/cheap AWS services to evaluate (Lambda, Fargate Spot, EC2 free tier, etc.).
- Secrets management for API keys.
- Whether this is for scheduled/batch runs, webserver hosting (Spec 047), or both.

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
