# Feature Specification: Newsletter Engagement Image & Notification

**Spec**: `041-newsletter-engagement-image`
**Created**: 2026-08-08
**Status**: Draft

## Problem

`newsletter_merge.py` (Spec 040) automates merging an edition's individual
`linkedin_post.md` files into one draft document, but publishing an edition on
LinkedIn still needs two more things the operator makes by hand: one "engagement
image" — a single picture that represents the whole issue, distinct from each
story's own per-story cartoon — and the short "what do you want to say to your
network" blurb LinkedIn asks for when sharing a newsletter edition, separate from the
article body itself, which is what actually drives readers to open the edition and
potentially subscribe. Today both are produced by hand outside the pipeline — the
image via a chat interface, the blurb by composing it directly in LinkedIn's publish
flow — with no record of what either cost, and no consistent voice or call-to-action.

## Goal

`newsletter_merge.py` gains two steps, on by default, that run alongside the existing
merge-text call:

1. An automatically produced `engagement_image.png`, whose concept comes from a
   multi-LLM deliberation (reusing `llm/fair_parallel_panel.py`, the same protocol
   already used by the Cultural Strategist and Satirist) over the edition's story
   texts only — never the stories' own rendered images — so the result is a fresh,
   unified visual idea rather than a literal collage of mismatched art. The actual
   rendering reuses the same Gemini image-generation call already used for every
   per-story cartoon, extracted into a shared `core/image_generation.py` module so
   both paths render identically.
2. An automatically produced `edition_notification.txt` — a short, catchy
   network-facing teaser for LinkedIn's publish flow, in Gata's established voice,
   that makes the edition worth clicking into and ends with an invitation to
   subscribe. This comes from a second marked section added to the existing
   merge-text call's response (Spec 040's single Gemini call already reads every
   story; it is extended to also write this teaser, rather than adding a whole new
   call), mirroring the `===NOTIFICATION===` marker convention already used
   per-story in `agents/agent_linkedin_post.py`.

Both steps degrade gracefully: if either fails, the merge still produces
`merged_linkedin_post.md`, with a clear warning naming which artifact was skipped.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — One engagement image per edition, no manual step (Priority: P1)

The operator runs `newsletter_merge.py` against an edition folder, as they do today,
and gets back the merged text, a ready-to-attach engagement image, and a
network-facing teaser blurb — with no separate manual trip to a chat interface or to
LinkedIn's compose box.

**Why this priority**: This is the entire point of the feature — replacing the last
manual steps in publishing a newsletter edition.

**Independent Test**:
```
python newsletter_merge.py <edition>
ls <edition>/merged_linkedin_post.md <edition>/engagement_image.png <edition>/edition_notification.txt
```
All three files must exist after a successful run.

**Acceptance Scenarios**:

1. **Given** an edition folder that already satisfies Spec 040's requirements (≥2
   numbered story folders, each with `<audience>/linkedin_post.md`), **When** the
   script runs with no extra flags, **Then** it writes `merged_linkedin_post.md`,
   `engagement_image.png`, and `edition_notification.txt` in the edition folder.
2. **Given** the same run, **When** the operator inspects the image, **Then** it
   depicts Gata in her established visual character (Constitution §4), not any of the
   individual stories' own generated art reused verbatim.

---

### User Story 2 — Concept comes from deliberation, not a single guess (Priority: P2)

Rather than asking one LLM to guess at a unifying image in one shot, several
panelists independently propose a concept from the edition's stories, see each
other's proposals, and an aggregator picks or synthesizes the strongest one — the
same `FairParallelPanel` pattern already trusted for cultural framing and satirical
concepts elsewhere in this project.

**Why this priority**: Improves concept quality over a single-shot call, but the
feature still delivers its core value (User Story 1) even if this were a single call
— hence P2, not P1.

**Independent Test**:
```
python -m pytest tests/test_engagement_image_concept.py -k deliberation -v
```
With two of three mocked panelists returning different concepts and the aggregator
mocked to pick one, the test asserts the final prompt matches the aggregator's pick,
not either raw panelist proposal.

**Acceptance Scenarios**:

1. **Given** all panelists succeed, **When** the panel completes, **Then** the
   aggregator's `<verdict>` content becomes the final image prompt.
2. **Given** one panelist fails, **When** the panel completes, **Then** the
   remaining panelists' proposals still reach the aggregator (existing
   `FairParallelPanel` behaviour — no new failure handling needed here).
3. **Given** every panelist fails, **When** the panel is run, **Then** the step is
   treated as a soft failure (see Edge Cases) — no image is generated, but the merge
   text step is unaffected.

---

### User Story 3 — Manual per-story image generation keeps working (Priority: P1)

An operator manually re-running the image step for a single story (RULE 12) sees no
behaviour change: same command, same output, same retry/fallback across models.

**Why this priority**: This feature extracts shared rendering logic out of
`agents/agent_image_generator.py` into `core/image_generation.py`; a regression here
would break a protected capability, not just add one.

**Independent Test**:
```
python -m pytest tests/test_agent_image_generator.py tests/test_image_generation.py -v
```
All existing per-story image-generation tests continue to pass unmodified in intent
(only updated where the extraction changes an internal call path, never the
public `generate()` contract's behaviour).

**Acceptance Scenarios**:

1. **Given** a `CartoonConcept` and `output_path` as before, **When**
   `agent_image_generator.generate()` is called directly, **Then** it produces the
   same file, same title-overlay behaviour, and same model retry order as before this
   change.
2. **Given** every image model fails, **When** `generate()` is called, **Then** it
   still raises `RuntimeError`, exactly as today.

---

### User Story 4 — Edition cost total includes this step (Priority: P1)

The operator wants the same cost total Spec 040 already appends to
`merged_linkedin_post.md` to include what this new step actually cost — the
deliberation panel's calls plus the image-generation call — not just the per-story
image costs and the merge-text call.

**Why this priority**: Cost visibility has been a first-class concern throughout this
project (Specs 009, 014, 033, 039, 040); silently leaving a paid step out of the
published total would be a regression from that standard.

**Independent Test**:
```
python -m pytest tests/test_newsletter_merge.py -k engagement_image_cost -v
```
With the concept panel and image generator mocked to fixed costs, the test asserts
the published total equals sum(per-story image costs) + merge-call estimate +
concept-panel cost + engagement-image cost.

**Acceptance Scenarios**:

1. **Given** a successful engagement-image step, **When** the total cost line is
   computed, **Then** it includes the concept panel's token costs and the image
   generator's actual cost.
2. **Given** the step is skipped (`--no-image`) or soft-failed, **When** the total
   cost line is computed, **Then** it includes only the costs actually incurred — no
   phantom charge for a step that didn't run or didn't finish.

---

### User Story 5 — Network-facing teaser drives readership and subscriptions (Priority: P1)

Alongside the merged article, the operator gets a short, separate teaser blurb — the
text LinkedIn asks for when sharing a newsletter edition to followers — written in
Gata's voice, that makes the edition worth clicking into and nudges non-subscribers
to subscribe.

**Why this priority**: This text is what actually reaches the operator's network and
drives new subscriptions — without it, the merged article and engagement image have
no way to reach anyone who hasn't already opened the edition.

**Independent Test**:
```
python newsletter_merge.py <edition>
cat <edition>/edition_notification.txt
```
Output must be non-empty, contain no LinkedIn-forbidden formatting (no exclamation
marks, no hyphen-minus used as an em dash), and end with an explicit invitation to
subscribe.

**Acceptance Scenarios**:

1. **Given** a successful merge call, **When** its response is parsed, **Then** the
   `===NOTIFICATION===` section's content is written verbatim to
   `<edition_dir>/edition_notification.txt`.
2. **Given** the merge response is missing the `===NOTIFICATION===` section entirely
   (e.g. an older or misbehaving model ignores the instruction), **When** the script
   finishes, **Then** `merged_linkedin_post.md` is still written, a warning is
   logged, and no `edition_notification.txt` is written.

---

### Edge Cases

- `--no-image` is passed → the concept panel and image generation are never invoked;
  behaviour is identical to Spec 040 today; no additional cost, no additional
  telemetry.
- All deliberation panelists fail → soft failure: log a clear warning, write
  `merged_linkedin_post.md` as usual, do not write `engagement_image.png`, exit 0.
- The concept panel succeeds but every image model fails (same exhaustion path as
  `agent_image_generator.generate()` today) → soft failure, same handling as above.
- An edition's stories are all in a non-English `--audience` → the concept panel
  receives that audience's `linkedin_post.md` text as-is (already loaded by
  `discover_and_order_stories`); no separate translation step is added.
- An operator re-runs the script on an edition that already has an
  `engagement_image.png` → the file is overwritten, same as `merged_linkedin_post.md`
  is today (no versioning in this stage).
- The merge call's response is missing the `===NOTIFICATION===` marker → soft
  failure for that artifact only (see User Story 5, Acceptance Scenario 2); the
  merged article and, independently, the engagement image are unaffected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `newsletter_merge.py` MUST, by default, run a new engagement-image step
  after (or independently of) the existing merge-text call, producing
  `<edition_dir>/engagement_image.png` unless `--no-image` is passed or the step
  soft-fails (FR-008).
- **FR-002**: The engagement-image concept MUST be produced by an `llm.fair_parallel_panel.FairParallelPanel`
  instance — the same protocol class used by the Cultural Strategist and Satirist —
  whose panelists and aggregator are built from `providers.yaml`'s existing
  `panelists`/`aggregator` schema via `core.config_loader.load_providers_config`,
  falling back to hardcoded provider defaults when the file is absent, mirroring
  `core/runner.py`'s existing pattern. No new configuration schema is introduced.
- **FR-003**: The panel's `initial_input` MUST include every story's full
  `linkedin_post.md` text, in edition order, plus the fixed Gata character
  description (Constitution §4). It MUST NOT include any story's rendered image —
  neither as a file reference nor as multimodal image content.
- **FR-004**: Each panelist's system prompt MUST instruct it to propose a single,
  complete image-generation prompt (freeform prose, not the Satirist's multi-panel
  JSON schema — this feature always produces one single-panel image) wrapped in
  `<verdict>...</verdict>` tags, following the same convention as
  `llm/dual_loop._extract_proposer_verdict`. Per Constitution §5 (Visual Style
  Rules — "every image prompt MUST enforce the following aesthetic", with no
  carve-out for a cover/engagement image), the same system prompt MUST also
  include the greyscale-background/Selective-Color/1970s-newsroom/chalkboard
  style block already used for per-story cartoons, so the proposed prompt matches
  the established Gata visual identity rather than an unrelated photorealistic
  scene.
- **FR-005**: The aggregator's system prompt MUST instruct it to pick the strongest
  proposal or synthesise the best elements of several into one final image prompt,
  output a `PICK: N` line, and wrap the final prompt in `<verdict>...</verdict>` —
  mirroring the Cultural Strategist's Resonator convention in
  `agents/agent_cultural_strategist.py`. It MUST also restate the Constitution §5
  style block and instruct the aggregator to correct any panelist proposal that
  drifted from it, rather than carrying that drift into the final prompt.
- **FR-006**: A new `core/image_generation.py` module MUST contain the actual
  Gemini image-rendering logic (the `_MODELS` fallback list, the Gemini
  `generate_content` retry loop, and the title-overlay helper) extracted from
  `agents/agent_image_generator.py`, exposed as a class (`ImageGeneration`) whose
  entry point accepts a plain prompt string, an output path, an optional title
  string, and a `show_title` flag — with no dependency on `CartoonConcept`,
  `StrategyBrief`, or `CartoonLayout`.
- **FR-007**: `agents/agent_image_generator.generate()` MUST keep its existing public
  signature and behaviour for per-story callers (RULE 12), except for dropping its
  currently-unused `brief: StrategyBrief` parameter (dead code discovered during this
  spec's investigation — never read inside the function body); it MUST build its
  prompt from `concept`/`layout` exactly as today and delegate the actual rendering
  to `core.image_generation.ImageGeneration`. The sole call site
  (`core/runner.py`) MUST be updated to match.
- **FR-008**: If every deliberation panelist fails, or the concept panel succeeds but
  `ImageGeneration` exhausts every model, the engagement-image step MUST be treated
  as a soft failure: log a clear warning naming the failure, skip writing
  `engagement_image.png`, and still write `merged_linkedin_post.md` — the script MUST
  exit 0, not abort the whole run.
- **FR-009**: `newsletter_merge.py` MUST accept a `--no-image` flag that skips the
  concept panel and image generation entirely, with no cost or telemetry recorded for
  either.
- **FR-010**: The total cost figure already appended to `merged_linkedin_post.md`
  (Spec 040 FR-010/FR-011) MUST be extended to include the concept panel's token
  costs and, when generated, the engagement image's actual generation cost. When the
  step is skipped or soft-failed, these components MUST be omitted rather than
  estimated.
- **FR-011**: The engagement image MUST always be a single image (no multi-panel
  comic-strip layout) and MUST NOT receive the per-story title-banner overlay
  (`_overlay_title`) — no edition-level title concept exists yet.
- **FR-012**: Every panelist call, the aggregator call, and the image-generation
  attempt(s) MUST be logged via the `logging` module (Constitution §13), naming the
  model used and, on success, its cost.
- **FR-013**: `agent_newsletter_editor.py`'s merge-call system prompt MUST be
  extended to require a second marked section, `===NOTIFICATION===`, containing a
  short (2-4 sentence), catchy network-facing teaser for the edition, in addition to
  the existing merged-article output — parsed the same way
  `agents/agent_linkedin_post.py`'s `_parse_sections` splits its own markers. This
  MUST remain a single Gemini call; no second LLM call is added for this text.
- **FR-014**: The `===NOTIFICATION===` section's content MUST be written verbatim to
  `<edition_dir>/edition_notification.txt`. If the section is absent from an
  otherwise-successful merge response, this MUST be a soft failure: log a warning,
  skip writing the file, and still write `merged_linkedin_post.md`.
- **FR-015**: The `===NOTIFICATION===` copy MUST follow Gata's established voice
  constraints — dry wit, feline metaphors, deadpan tone, no exclamation marks, never
  using the hyphen-minus character as an em dash (matching
  `agents/agent_linkedin_post.py`'s `_SYSTEM_PROMPT`) — MUST be written to make the
  edition worth reading/watching, and MUST end with an explicit invitation to
  subscribe to the newsletter. No follower or subscriber counts are referenced —
  the copy sells the content, not the numbers.
- **FR-016**: The script MUST NOT post `edition_notification.txt` (or any other
  output) anywhere; it remains a local draft file for the operator to paste into
  LinkedIn's publish flow by hand, same as `merged_linkedin_post.md`.

### Key Entities

- **EngagementImageConcept**: the final aggregated image-prompt text produced by the
  `FairParallelPanel` run, plus the `AgentTelemetry` covering every panelist and
  aggregator call.
- **ImageGeneration**: the shared rendering component in `core/image_generation.py` —
  given a prompt string and output path, tries each configured Gemini image model in
  order and returns the written file path plus `AgentTelemetry`. Used by both
  `agents/agent_image_generator.py` (per-story) and this feature (per-edition).
- **EditionNotification**: the `===NOTIFICATION===` section's text, parsed from the
  same merge-call response as the merged article, written to
  `edition_notification.txt`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a fixture edition, running `newsletter_merge.py` with no extra
  flags produces both `merged_linkedin_post.md` and `engagement_image.png`.
- **SC-002**: With every deliberation panelist mocked to fail, the script still
  writes `merged_linkedin_post.md`, logs a warning, writes no
  `engagement_image.png`, and exits 0.
- **SC-003**: With the concept panel and image generator mocked to fixed costs, the
  published total cost line equals sum(per-story image costs) + merge-call cost +
  concept-panel cost + engagement-image cost.
- **SC-004**: `python -m pytest tests/test_agent_image_generator.py tests/test_image_generation.py`
  passes, proving the per-story `generate()` contract (files written, title overlay,
  model retry order) is unchanged by the `core/image_generation.py` extraction.
- **SC-005**: `--no-image` produces output byte-identical (aside from the cost line
  omitting the skipped step) to Spec 040's current behaviour, with zero panel or
  image-generation calls made.
- **SC-006**: `python -m pytest tests/test_newsletter_merge.py tests/test_engagement_image_concept.py`
  passes with every provider call mocked per Constitution §9 — zero real API calls
  during tests.
- **SC-007**: Given a mocked merge response containing both `===NOTIFICATION===` and
  the merged article, the script writes `edition_notification.txt` with exactly the
  notification section's content, and `merged_linkedin_post.md` with the rest.
- **SC-008**: Given a mocked merge response missing `===NOTIFICATION===` entirely,
  `merged_linkedin_post.md` is still written, a warning is logged, and no
  `edition_notification.txt` is written.

## What does NOT change

- The per-story pipeline (`pipeline.py`, `core/cli.py`, `core/runner.py`) keeps
  working exactly as today; `agents/agent_image_generator.generate()`'s call site in
  `core/runner.py` changes only to drop the unused `brief` argument.
- Spec 040's merge-text call (FR-007–FR-018) is untouched: it still never sends or
  requests images, and still uses its own separate cheapest-first fallback chain —
  a deliberately different, non-deliberative mechanism from the `FairParallelPanel`
  used here, because merging text mechanically and proposing a creative visual
  concept are different kinds of task.
- No multi-panel/comic-strip layout is supported for the engagement image in this
  stage.
- Sending the individual stories' rendered PNGs to Gemini as reference or blend
  input is explicitly rejected for this stage — literal image blending risks
  collage artifacts and carries over each story's own baked-in title banner. A
  future spec could revisit this if text-only synthesis proves visually
  disconnected from the edition's actual stories.
- No new CLI subcommand is added; `newsletter_merge.py` keeps its current invocation
  shape with one new optional flag (`--no-image`).
- No LinkedIn API integration is added anywhere — `edition_notification.txt` is a
  local draft file the operator pastes into LinkedIn's publish flow by hand, exactly
  like `merged_linkedin_post.md` is today.

## Assumptions

- `providers.yaml`'s existing `panelists`/`aggregator` schema, already shared by the
  Cultural Strategist and Satirist, is reused as-is; introducing a separate
  newsletter-specific provider list is unnecessary and would fragment configuration.
- The `_GATA_CHARACTER` text block continues to be duplicated into whichever module
  builds the concept-panel prompt, consistent with the existing duplication
  rationale documented in `agents/agent_image_generator.py` (avoiding a circular
  import with `agents/agent_satirist.py`).
- Soft-failing the image step (rather than aborting the whole run) is the right
  default because the merged text document is independently useful and already the
  primary deliverable; an operator who gets a soft failure can still fall back to
  today's fully-manual image process for just that piece.
- Keeping the notification generic (no follower/subscriber counts) is deliberate for
  this stage: the copy's job is to make the edition's content sound worth reading,
  not to report growth metrics. A future spec could reintroduce real numbers if the
  generic version underperforms.
