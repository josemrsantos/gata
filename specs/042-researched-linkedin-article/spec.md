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