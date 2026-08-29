# Feature Specification: Researched LinkedIn Article

**Spec**: `042-researched-linkedin-article`
**Created**: 2026-08-10
**Status**: Draft (revised — independent per-provider research, multiple angles)

## Problem

The `--linkedin-post` feature (Spec 038) writes its companion article in Gata's
sardonic, joke-driven voice — the same tone as the cartoon it accompanies. That
duplication of tone wastes the format: the cartoon already carries the joke, so the
text underneath it should carry something the image can't — a substantive,
credible take on the topic. Today's article is also a single ungrounded LLM call:
one model free-associates a "Message from Gata" with no research step and no
citations, so anything factual in it is incidental, not verified. The operator
also has no way to steer what the article should focus on.

## Goal

`--linkedin-post` still produces `linkedin_post.md` and `linkedin_notification.txt`
in the output bundle, but the article's generation changes fundamentally:

1. **Every panelist researches independently.** Rather than one shared search
   pass, each of the three panelist providers (Claude, Grok, Gemini) performs its
   own real, provider-native web search on the topic before drafting — Gemini via
   its existing Google Search grounding tool, Claude via Anthropic's server-side
   web search tool, Grok via xAI's Live Search. This is explicitly accepted by the
   operator as more expensive and slower than a single shared search, in exchange
   for genuine cross-provider research rather than one model's search results
   handed to the other two.
2. **Angles are planned, not assumed**, via a `FairParallelPanel` deliberation
   (the same three panelists + aggregator used everywhere else in this project),
   each panelist proposing from its *own* research. The operator can supply one
   or more angles to explore (new, repeatable `--angle` flag on both `gata` and
   `pipeline.py`) — every supplied angle is mandatory in the final set.
3. **A second panel writes the article** from the agreed angles, each panelist
   again drawing on its own research — a serious, professional, moderate-length
   piece (roughly 500–800 words), explicitly disclosed as AI-researched-and-
   written, ending with a Sources list. That list is the deduplicated union of
   every panelist's real sources, assembled by code — never left to an LLM to
   produce — so no URL in it can be invented.
4. **Gata's byline stays**, but not her sardonic voice — this article is
   professional/analytical in register; jokes, feline metaphors, and dry wit are
   the cartoon's job, not this article's.

The cartoon's own generation (Cultural Strategist, Satirist, Image Generator) is
completely unaffected — `--angle` only reaches this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Independently researched, not relayed (Priority: P1)

The operator runs `--linkedin-post` and gets an article whose research came from
three separate real web searches (one per provider), not from one model's search
results copied to the other two.

**Why this priority**: This is the entire point of the revision — the earlier
single-shared-search design was rejected specifically because it meant only one
of three "researching" models actually researched anything.

**Independent Test**:
```
gata "Vibe coding in production" --linkedin-post
```
Logs must show three separate research attempts (one per configured panelist
provider), each naming its own model and search mechanism, before the
angle-planning panel runs.

**Acceptance Scenarios**:

1. **Given** a successful run, **When** the logs are inspected, **Then** each
   panelist's own research attempt (success or failure) is logged separately,
   naming its provider and model.
2. **Given** all three providers' research succeeds, **When** the Sources section
   is inspected, **Then** it contains the deduplicated union of all three
   providers' real sources — not just one provider's.
3. **Given** one provider's research fails (e.g. an unsupported response shape),
   **When** the run continues, **Then** that panelist still participates using
   its own general knowledge, explicitly instructed not to present unverified
   specifics as researched fact — the run is not aborted by one provider's
   failure.

---

### User Story 2 — Operator can set several angles (Priority: P1)

The operator can supply more than one angle to explore, not just one, on both
entry points.

**Why this priority**: A single angle is often not enough to scope a genuinely
multi-perspective article (e.g. the vibe-coding example needs both "when it's
wrong" and "when it's acceptable" specified, not just one).

**Independent Test**:
```
gata "Vibe coding in production" --linkedin-post \
  --angle "when it's the wrong approach" --angle "when it's an acceptable shortcut"
python pipeline.py --topic "Vibe coding in production" --audience "engineering leaders" \
  --language English --tone neutral --linkedin-post \
  --angle "when it's the wrong approach" --angle "when it's an acceptable shortcut"
```
Both commands must run without error; the resulting article must contain a
section engaging with each supplied angle.

**Acceptance Scenarios**:

1. **Given** `--angle` is supplied multiple times, **When** the angle-planning
   panel runs, **Then** all supplied angles are included among the final
   angles — the panel may add complementary ones but may not drop any supplied
   one.
2. **Given** `--angle` is omitted entirely, **When** the angle-planning panel
   runs, **Then** it proposes 2–4 angles on its own, exactly as today's
   autonomous behaviour elsewhere in the pipeline.
3. **Given** `--angle` is supplied but `--linkedin-post` is not, **When** the CLI
   runs, **Then** `--angle` is accepted but has no effect (logged at INFO, not an
   error) — it never reaches cartoon generation.

---

### User Story 3 — Total research failure is loud, partial failure is not (Priority: P1)

If every provider's research fails, the operator gets no article at all rather
than one that claims to be researched but isn't. If only some providers' research
fails, the article is still produced, honestly reflecting only what was actually
grounded.

**Why this priority**: The value of this feature over Spec 038's version is that
its claims are backed by real sources; misrepresenting an ungrounded article as
researched — fully or partially — would undermine the entire premise.

**Independent Test**:
```
python -m pytest tests/test_agent_linkedin_post.py -k research_failure -v
```

**Acceptance Scenarios**:

1. **Given** all three providers' research fails, **When**
   `generate_linkedin_post` runs, **Then** it returns empty strings (the existing
   Spec 038 failure contract) and logs a warning — the angle-planning and writing
   panels are never invoked.
2. **Given** exactly one or two providers' research succeeds, **When** the run
   continues, **Then** the angle-planning and writing panels still run normally,
   using whichever real research is available; the panelist(s) without research
   are explicitly told not to present unverified claims as fact.
3. **Given** research succeeds for at least one panelist but every panelist in
   the angle-planning panel fails outright (a separate, unrelated failure mode —
   e.g. every provider's normal text call fails), **When** the run continues,
   **Then** the same total soft failure applies — the writing panel is never
   invoked with a missing outline.

---

### Edge Cases

- `--angle` supplied as an empty/whitespace-only string (in any one occurrence) →
  that occurrence is dropped; if none remain, treated as if `--angle` were never
  supplied.
- A provider's search call succeeds but returns zero sources (a real but
  sourceless grounded response) → that provider still contributes its findings
  summary; only its source-list contribution is empty.
- A provider's search response has a shape this project's parser doesn't
  recognise (Anthropic/xAI's search response formats are less thoroughly
  verified in this codebase than Gemini's, see Assumptions) → treated the same
  as that provider's research failing outright: logged, that panelist proceeds
  ungrounded, the run continues.
- Multi-panel image runs (`--panels`/`--layout`) and `--direct` mode are
  unaffected — `--angle` and this feature's research/panels have no interaction
  with cartoon concept generation at all.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each configured panelist provider (the primary provider in each of
  the three `panelist_providers` slots already threaded through `run_pipeline()`)
  MUST perform its own web-search-grounded research call before any drafting,
  using that provider's own native search mechanism:
  - **Gemini**: the existing `google_search` grounding tool (as
    `infer_mood()` already uses).
  - **Claude**: Anthropic's server-side web search tool
    (`web_search_20250305`), via a new call using the provider's own client.
  - **Grok**: xAI's Live Search, via a new call using the provider's own
    client.
  Each of these three research calls MUST be bounded by an explicit 120-second
  timeout, independent of anything in `FairParallelPanel` (these calls happen
  before any panel starts, per FR-004) — a provider exceeding it is treated as
  that provider's research failing (FR-005), not a hang.
- **FR-002**: Each of these three providers MUST gain a `client` property
  exposing its underlying SDK client (mirroring `GeminiProvider.client`'s
  existing precedent), so this feature can make provider-specific search calls
  without adding a `enable_search` parameter to the shared `LLMProvider.generate()`
  interface or modifying `FairParallelPanel` — every other agent using these
  providers is unaffected.
- **FR-003**: Each provider's real sources (title + URL) MUST be extracted from
  that provider's own response as defensively as possible; a response shape this
  project doesn't recognise MUST be treated as that provider's research failing
  (FR-005), never as a crash.
- **FR-004**: Each panelist's own research digest (findings summary + real
  sources) MUST be embedded into that specific panelist's own `PersonaConfig.system_prompt`
  for both the angle-planning and writing stages — not the `FairParallelPanel`
  shared `initial_input`, which stays identical for every panelist (topic +
  operator-supplied angles only). This keeps `llm/fair_parallel_panel.py`
  completely unmodified.
- **FR-005**: A single provider's research failure MUST NOT abort the run: that
  panelist's system prompt instead states plainly that no search results were
  available and instructs it not to present unverified specifics as researched
  fact. Only when **every** provider's research fails does the whole feature
  soft-fail (FR-008).
- **FR-006**: An angle-planning step MUST run as an `llm.fair_parallel_panel.FairParallelPanel`
  deliberation using the three panelists (named by `model_id`) and aggregator
  (named **Managing Editor**) providers already threaded through `run_pipeline()`.
  Each panelist proposes 2–4 distinct angles from its own research.
- **FR-007**: The operator MAY supply one or more angles via a repeatable
  `--angle` flag. When supplied (after dropping empty/whitespace-only entries),
  the angle-planning system prompt MUST instruct every panelist that all
  supplied angles are mandatory in the final set; the panel may still add
  complementary or contrasting angles alongside them.
- **FR-008**: If every provider's research fails (FR-005), OR every panelist in
  the angle-planning panel fails outright, the feature MUST soft-fail: return
  `("", "")` from `generate_linkedin_post`, log a warning, and skip the writing
  panel entirely.
- **FR-009**: A writing step MUST run as a second `FairParallelPanel`
  deliberation (same panelists, same **Managing Editor** aggregator), each
  panelist drawing on its own research digest (FR-004) plus the finalized
  angles (FR-006/FR-007), producing the article body: professional/analytical
  register, no jokes/feline metaphors/dry wit, one section per agreed angle,
  targeting roughly 500–800 words. This panel MUST be constructed with
  `panelist_timeout=120` (vs. the class default of 60s) — its system prompt is
  longer (an embedded research digest) and its expected output is longer
  (500–800 words) than any other `FairParallelPanel` use in this project, so
  the default budget is too tight. The angle-planning panel (FR-006) keeps the
  default 60s — its output is a short angle list, not a full article.
- **FR-010**: The writing panel's system prompt MUST explicitly forbid citing or
  linking any URL not present in that panelist's own research digest, and MUST
  instruct it to write prose only — the Sources list itself is never requested
  from any LLM (see FR-011).
- **FR-011**: The published Sources section MUST be assembled by code as the
  deduplicated union (by URL) of every panelist's own real research sources,
  never parsed from or trusted to LLM output. An empty combined source list
  produces an empty (or omitted) Sources section, not an error.
- **FR-012**: If every panelist in the writing panel fails, the feature MUST
  soft-fail per FR-008's contract.
- **FR-013**: The assembled article MUST include a visible, explicit statement
  that it was independently researched (naming that multiple providers each
  searched independently) and drafted by a panel of AI models — this MUST NOT be
  described as satirical or read as Gata's usual sardonic voice.
- **FR-014**: `agents/agent_linkedin_post.py`'s public function keeps the same
  output contract (files `linkedin_post.md` / `linkedin_notification.txt`, same
  soft-failure behaviour on total failure) but its signature accepts
  `panelist_providers: list[list[LLMProvider]]` and `aggregator_providers:
  list[LLMProvider]` (replacing the single `providers` fallback list) plus a new
  optional `angles: list[str] | None = None`. The unused `image_prompt`
  dependency on the cartoon's own concept is dropped.
- **FR-015**: `core/runner.py`'s `run_pipeline()` gains an optional `angles:
  list[str] | None = None` parameter, passed through to `generate_linkedin_post()`
  only when `generate_linkedin_post=True`; it has no effect on Cultural
  Strategist, Satirist, or Image Generator.
- **FR-016**: Both `core/cli.py` (`gata`) and `pipeline.py` gain a repeatable
  `--angle TEXT` flag (`action="append"`), collected into a list and threaded
  through to `run_pipeline(angles=...)`. Supplying `--angle` without
  `--linkedin-post` MUST NOT error — it is accepted and logged as unused.
- **FR-017**: The push-notification snippet (written to
  `linkedin_notification.txt`) MUST also be a serious, compelling teaser, not a
  joke hook — generated by the same writing-panel call, not a separate one.
- **FR-018**: The article's language MUST match `brief.output_language` (existing
  behaviour, unchanged) — no new translation step is introduced.
- **FR-019**: Every research attempt (per provider), angle-planning call, and
  writing call — success or failure — MUST be logged via the `logging` module
  (Constitution §13), naming the provider/model and, on success, tokens/cost.

### Key Entities

- **ResearchDigest**: one provider's own grounded findings summary plus its own
  list of `ResearchSource` (title, URL) pairs. Up to three exist per run (one per
  panelist provider) — never merged into a single shared digest.
- **ResearchSource**: one real source — a title and a URL taken verbatim from a
  provider's own search response.
- **AngleSet**: the angle-planning panel's finalized list of 2–4 (or more, if
  many operator angles were supplied) angle titles/one-line descriptions,
  feeding directly into the writing panel's prompts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given three mocked provider research calls returning distinct
  sources each, the assembled article's Sources section contains the
  deduplicated union of all three, and no others.
- **SC-002**: Given `--angle "X" --angle "Y"` supplied, both `X` and `Y` appear
  in the angle-planning system prompts as mandatory, for every panelist.
- **SC-003**: Given all three providers' research mocked to fail,
  `generate_linkedin_post()` returns `("", "")`, logs a warning, and neither the
  angle-planning nor the writing panel's mocked `run()` is called.
- **SC-004**: Given exactly one provider's research mocked to succeed and the
  other two mocked to fail, the angle-planning and writing panels still run, and
  the two ungrounded panelists' system prompts explicitly instruct them not to
  present unverified claims as fact.
- **SC-005**: A real, manually-run end-to-end invocation (`gata "<topic>"
  --linkedin-post --angle "<angle>"`) produces a `linkedin_post.md` containing
  the supplied angle, a disclosure statement, and a Sources section whose links
  are independently verifiable as real (manual verification during
  implementation, not an automated test).
- **SC-006**: `python -m pytest tests/` passes with every provider/SDK call
  mocked per Constitution §9 — zero real API calls during the automated suite.
- **SC-007**: Each of the three per-provider research calls is made with a
  120-second timeout; the writing `FairParallelPanel` is constructed with
  `panelist_timeout=120`; the angle-planning `FairParallelPanel` is constructed
  with the class default (60s, no explicit override).

## What does NOT change

- Cartoon generation (Cultural Strategist, Satirist, Image Generator, Image
  Evaluator) is completely untouched; `--angle` never reaches it.
- `llm/fair_parallel_panel.py` and `LLMProvider.generate()`'s signature are
  unmodified — this feature only adds a new `client` property to three provider
  classes (FR-002), used solely by this feature.
- Output file names and bundle location (`linkedin_post.md`,
  `linkedin_notification.txt`) are unchanged — only their generation process and
  content changes.
- The Newsletter Editor / Engagement Image Concept (Spec 041) are unrelated
  features and are not touched by this spec.
- Nothing publishes automatically anywhere — `linkedin_post.md` remains a draft
  for human review, same as every other text artifact in this project.

## Assumptions

- The operator has explicitly accepted higher cost and latency (three real
  search-grounded calls instead of one, for both the angle-planning and writing
  stages' underlying research) as the price of genuine independent research —
  this is a deliberate trade-off, not an oversight.
- **Real engineering risk, stated plainly**: this codebase has one verified,
  field-checked integration with a grounded search API (Gemini's
  `grounding_metadata.grounding_chunks`, confirmed against the installed
  `google-genai` SDK). Claude's `web_search_20250305` tool and xAI's Live Search
  are new integrations for this project; their exact response/citation shapes
  will be confirmed and hardened during implementation against real API calls,
  not just documentation. xAI's own documentation indicates Live Search via
  `search_parameters` is being migrated toward a newer Agent Tools/Responses API
  — this integration may need revisiting sooner than Gemini's or Claude's if
  that migration affects the endpoint this project uses
  (`/v1/chat/completions`).
- A response-shape mismatch for any one provider degrades that provider to
  "ungrounded panelist" rather than failing the run — this is intentional
  graceful degradation, not a bug, per FR-005.
- "Serious and researched" means professional register plus real search-grounded
  facts and sources where available; it does not mean academic rigor, peer
  review, or a guarantee of completeness — the output is still a draft for human
  review before publishing, like every other artifact in this project.
- Target article length (500–800 words) is a prompt instruction, not a hard
  validation — LLM output length is approximate by nature.

## Amendment (2026-08-29): Executive Summary + reordered meta content

**Living Spec amendment** (per CLAUDE.md RULE 18) — this section revises this
spec's own requirements in place rather than creating a new spec number, since
this is an evolution of `linkedin_post.md`'s already-shipped assembly, not new
capability.

**Motivation**: the operator manually edits every generated `linkedin_post.md`
before publishing — moving the Pipeline Metrics line and the AI-authorship
disclosure (FR-013) from immediately after the title down to the bottom of the
article, and adding an "Executive Summary" heading above the previously-unlabeled
lead paragraph. This amendment makes the generated file match what's actually
published, removing that manual step.

**Supersedes**: `specs/038-linkedin-post/spec.md`'s requirement that
`linkedin_post.md` contain its five sections "in order" (Title → Metrics → Body →
Behind the Scenes → Notification). That fixed ordering no longer applies; this
amendment is the current source of truth for section order.

### New Functional Requirements

- **FR-020**: The assembled article MUST include a distinct Executive Summary —
  a `## Executive Summary` heading followed by a short (3–5 sentence) paragraph —
  placed immediately after the title (H1) and before the per-angle body sections.
  This text MUST come from the writing panel as its own explicitly marked block
  (a new `===EXECUTIVE_SUMMARY===` section, parsed the same way as
  `===TITLE===`/`===BODY===`/`===COMMENT===`/`===NOTIFICATION===`), never
  inferred by code splitting the body text on its first heading — that would
  depend on markdown structure the writer prompt encourages but doesn't
  guarantee. When absent or empty, the heading is omitted entirely rather than
  published blank (same pattern as the existing conditional Sources section).
- **FR-021**: The `===BODY===` instruction in `_WRITER_SYSTEM` no longer asks
  for an introduction — that role transfers entirely to FR-020's
  `===EXECUTIVE_SUMMARY===`. `_WRITER_AGGREGATOR_SYSTEM` MUST also require the
  synthesized/selected article to use the same five-marker format (adding
  `===EXECUTIVE_SUMMARY===` to the four it already requires).
- **FR-022**: The Pipeline Metrics line (code-built from `RunTelemetry`, no LLM
  involvement) and the AI-authorship disclosure (FR-013) MUST both move to the
  bottom of the article, appended after the existing static "Behind the Scenes:
  The Tech Stack" content, in that order (metrics line, then disclosure) — no
  longer placed immediately after the title. The static "Behind the Scenes" text
  itself is unchanged.
- **FR-023**: New article section order:  Title → Executive Summary (FR-020) →
  per-angle body sections → closing block → Sources (FR-011, when non-empty) →
  Behind the Scenes (ending with Pipeline Metrics + disclosure, per FR-022).
  `linkedin_notification.txt` is unaffected — it remains the writing panel's own
  independent `===NOTIFICATION===` block, unrelated to this reordering.

### New Success Criteria

- **SC-008**: Given an assembled-article test with `EXECUTIVE_SUMMARY` set in
  `sections`, `## Executive Summary` appears in the output at a lower string
  index than the per-angle body content, and at a higher index than the title.
- **SC-009**: Given `EXECUTIVE_SUMMARY` absent or empty, the assembled article
  contains no `## Executive Summary` heading at all.
- **SC-010**: In the assembled article, both the Pipeline Metrics line and the
  disclosure sentence appear at a string index higher than `## Sources` (or, if
  Sources is empty/omitted, higher than the closing block) — i.e. genuinely at
  the bottom, inside the Behind the Scenes section.
- **SC-011**: A real, manually-run end-to-end `--linkedin-post` invocation
  produces a `linkedin_post.md` matching the FR-023 order exactly (manual
  verification during implementation, same discipline as SC-005).

## Amendment (2026-08-29, part 2): Curated, paywall-free, numbered references

**Living Spec amendment** (CLAUDE.md RULE 18) — a second amendment to this spec
on the same day, further evolving the Sources feature (FR-011) rather than
adding new capability. Superseded twice during discussion before this final
form (a single-model classifier and a `.yaml` cache were both replaced by a
panel-based classifier and a DuckDB cache — see rationale inline).

**Motivation**: today's Sources list is the deduplicated union of every
panelist's *own* research sources (FR-011) — every source anyone happened to
find, whether or not the final published article actually references it, with
no check for paywalls or outlet quality. The operator wants: (1) domains
actively steered toward academic/highly-reputable sources during research
itself, (2) any paywalled or low-reliability domain excluded from influencing
the article at all — not just from the final citation list — as early as it's
technically possible to act on that, (3) visible numbered footnotes (`[1]`,
`[2]`, ...) in the article body matching the Sources list, for credibility,
and (4) roughly 2 citations per body section, capped at 15 total.

**Technical constraint, confirmed with the operator**: Gemini's grounding,
Claude's `web_search`, and Grok's Agent Tools search are provider-native,
server-side tools — a fetch happens inside the provider's own black-box tool
loop, and we only see the result (findings + the sources actually used) after
the whole research call finishes. There is no hook to classify a URL *before*
the provider's own tool fetches it. The earliest point this pipeline can act is
immediately after each provider's research call returns, before that digest's
sources reach any further prompt (angle planning or writing).

### New Functional Requirements

- **FR-024**: `_build_research_query` (shared by all three providers' research
  calls) MUST add an instruction steering each provider's own search toward
  academic, government, or otherwise highly-reputable sources, to reduce how
  many low-quality domains appear at all — a best-effort nudge, not a
  guarantee; FR-026 remains the actual enforcement point.
- **FR-025**: A new DuckDB database file (`source_domains.duckdb`, repo root,
  **gitignored** — a regenerating local cache, not a hand-edited config; each
  clone/machine builds its own over time) caches a paywall/reliability verdict
  per domain in a `domains` table: `domain TEXT PRIMARY KEY, paywalled
  BOOLEAN, reliability TEXT ('high'|'low'), classified_at TIMESTAMP`. An
  existing entry is trusted indefinitely (no automatic expiry); the operator
  may delete a row (or the whole file) at any time to force re-classification.
- **FR-026**: Immediately after `research_all_panelists` collects all three
  providers' digests (still in parallel, per FR-001), before any digest is used
  in `_panelist_research_context` (which feeds both angle-planning and
  writing) or in the merged candidate list:
  1. Collect every domain across all three digests' sources not already in the
     DuckDB cache (FR-025).
  2. Classify all of them in a single `FairParallelPanel` deliberation (the
     same panelist/aggregator providers already threaded through this
     feature — a panel decision, not a single model's call, since this is a
     judgment call worth cross-checking), with `panelist_timeout=90` and
     `iterations=3` (one more than the class default, since early runs with an
     empty/small cache are expected to disagree more before converging).
     Verdicts are persisted to the cache (FR-025) — if this panel fails
     entirely, the run proceeds without failing; those domains are treated as
     unclassified this run (step 3) and are **not** cached, so they're
     retried on a future run.
  3. Any domain now classified `paywalled: true` OR `reliability: low` has
     every one of its `ResearchSource` entries stripped from that digest's
     `sources` list. A domain with no classification at all (cache miss and
     the panel failed) is treated as eligible — filtering only ever excludes a
     *positively classified* bad domain, never an unknown one, so a
     classification failure degrades to today's unfiltered behaviour rather
     than zeroing out the Sources feature.
  4. Each excluded source is logged at WARNING, naming the domain and why
     (paywalled, low reliability, or both) — visible, not silent.
- **FR-027**: The (now-filtered) merged candidate list — `_merge_sources`
  applied to the filtered digests — is assigned stable numbers (1-based, merge
  order) and embedded, identically, into every writing-panelist's system
  prompt as a citable numbered list. Panelists MUST cite a specific claim
  inline as `[N]` against that shared numbering, MUST NOT invent a number not
  in the list, and MUST NOT fabricate a source outside it. The prompt
  instructs panelists to cite roughly 2 sources per body section (scaling
  naturally with however many angle sections exist), with an outer cap of 15
  distinct citations total.
- **FR-028**: The writing `FairParallelPanel` (`_write_article`) checks, after
  each round, each surviving panelist's own draft for any body section citing
  more than 2 distinct sources; any panelist over the limit receives that
  finding as extra feedback text for its next round (in addition to the
  existing peer-verdict context), asking it to trim to ≤2 per section. This
  requires a new optional hook on `FairParallelPanel` (e.g. a post-round
  validator callback), added so it defaults to `None`/inert for every other
  caller of that shared class (Cultural Strategist, Satirist, Explainer,
  Engagement Image Concept, LinkedIn Angle Planning) — backward compatible,
  opt-in only for this call site. This is a best-effort nudge during
  deliberation, not the final enforcement — FR-030 remains the hard backstop
  regardless of whether every panelist complied.
- **FR-029**: After the writing panel produces its final `EXECUTIVE_SUMMARY`
  and `BODY` text, code MUST:
  1. Extract every `[N]` citation marker across both, in order of first
     appearance; drop (strip from the text) any marker whose `N` does not
     correspond to a real candidate from FR-027 (a hallucinated index).
  2. Keep only the first 15 *distinct* validly-cited candidates, by
     first-appearance order (FR-030); strip any citation marker referencing a
     16th-or-later distinct source entirely from the text.
  3. Renumber the kept candidates sequentially (1..K, K ≤ 15) in
     first-appearance order, and rewrite every surviving `[old]` marker in the
     text to `[new]`.
  4. Build the final Sources section from the kept, renumbered candidates, in
     that same order (replacing FR-011's plain deduplicated-union list with
     this filtered/numbered/capped one) — an ordered markdown list
     (`1. [title](url)`, `2. ...`) so the visible numbering matches the
     in-text `[N]` markers exactly.
  If zero sources end up cited, the Sources section is omitted entirely,
  exactly as today's empty-list case.
- **FR-030**: The 15-source cap (FR-029.2) is a hard code-level backstop, on
  top of FR-027's prompt-level ~2-per-section guidance and FR-028's mid-round
  nudge — neither of those is itself enforced; only the outer bound of 15 is.

### New Success Criteria

- **SC-012**: Given a digest containing a source whose domain is classified
  `paywalled: true`, that source is absent from the digest by the time
  `research_all_panelists` returns — not merely absent from the final
  citations, but absent from what angle-planning/writing ever see.
- **SC-013**: Given a domain not present in the DuckDB cache and a mocked
  classification-panel failure, that domain's source is still treated as
  eligible (fails open, per FR-026.3), and no row is written to the cache for
  it.
- **SC-014**: Given a final article body citing candidates `[2]`, `[5]`, and an
  invalid `[9]` (out of range), the assembled article contains renumbered
  citations `[1]` and `[2]` only (matching the original `[2]` and `[5]` in
  first-appearance order), the `[9]` marker is stripped entirely, and the
  Sources section lists exactly those two sources in that order.
- **SC-015**: Given a final article body citing 17 distinct valid candidates,
  only the first 15 (by first-appearance order) survive renumbering and appear
  in the Sources section; citation markers for the remaining 2 are stripped.
- **SC-016**: Given a mocked writing-panel round-1 draft citing 3 sources in
  one body section, the round-2 input built for that panelist includes an
  explicit note to trim that section to at most 2 citations.
- **SC-017**: A real, manually-run end-to-end `--linkedin-post` invocation
  produces a `linkedin_post.md` whose in-text `[N]` markers match the Sources
  list's own numbering exactly, contains no domain classified paywalled/low in
  the DuckDB cache (manually cross-checked), and lists no more than 15 sources
  total, with excluded-domain warnings visible in the run's log output.

## What does NOT change (Amendment 2)

- `linkedin_notification.txt` is unaffected.
- Angle planning (`_plan_angles`) receives the *filtered* digests (FR-026) but
  not the numbered candidate list itself — only the writing panel needs to
  cite sources by number.
- A source's **URL** is still never parsed from or trusted to LLM output
  (FR-011's original guarantee) — the writing panel only ever selects *which*
  of the code-supplied candidates to cite by number; it cannot introduce a new
  URL.
- Every other `FairParallelPanel` caller (Cultural Strategist, Satirist,
  Explainer, Engagement Image Concept, LinkedIn Angle Planning) is unaffected
  by FR-028's new hook — it's optional and unused by them.

## Assumptions (Amendment 2)

- True pre-fetch URL gating (classifying a domain before any provider's own
  search tool reads it) is not achievable without replacing each provider's
  native search tool with a fully custom search step — out of scope; this
  amendment classifies as early as the current architecture allows
  (immediately after each research call returns).
- `duckdb` is a new project dependency (Python package, no external service —
  single embedded file, no server process).