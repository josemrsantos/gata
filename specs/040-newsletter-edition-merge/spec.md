# Feature Specification: Newsletter Edition Merge

**Spec**: `040-newsletter-edition-merge`
**Created**: 2026-08-03
**Status**: Draft

## Problem

Every couple of weeks, several individually generated Gata stories (each already a
complete bundle with its own image and `linkedin_post.md`, produced via
`gata "<topic>" --linkedin-post`) are bundled into a single "newsletter edition"
folder, so LinkedIn readers see one issue per week instead of one per story. Today,
publishing an edition means manually pasting every story's `linkedin_post.md` into
Gemini with a free-text prompt asking it to merge them, strip the boilerplate that's
repeated in each post, and infer the reading order from context. This is repetitive
and entirely manual — there's no scripted way to hand Gemini the same set of inputs
in a chosen order and get the merge back, and no record of what that merge actually
cost on top of the cost already spent generating each story's image.

## Goal

A standalone script accepts an edition folder containing two or more story
sub-folders, each named with a leading number that fixes its position in the merged
output, and sends their `linkedin_post.md` text (no images — cost and latency are not
worth it for this step) to a single Gemini call that merges them into one Markdown
document: each story in its numbered order, boilerplate repeated across stories
consolidated to appear once, and a total cost figure for the edition appended at the
end. The call itself is attempted against the cheapest available model first, falling
back through progressively more expensive options — first across Gemini's own models,
then across other configured providers — so a single model outage doesn't block the
run. The output is always a draft for human review before publishing, not a final,
byte-exact document.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Merge a numbered set of stories into one document (Priority: P1)

The operator has finished generating several stories for one newsletter edition, has
named each story's folder with a leading number fixing its reading order, and runs
the script once against the edition folder — instead of manually feeding text into
Gemini by hand.

**Why this priority**: This is the entire point of the feature — replacing the manual
per-edition Gemini step with a repeatable local command that still uses Gemini to do
the actual merging.

**Independent Test**:
```
# fixture: <edition>/01_scene-setter/uk/linkedin_post.md
#          <edition>/02_second-story/uk/linkedin_post.md
#          <edition>/03_third-story/uk/linkedin_post.md
python newsletter_merge.py <edition>
cat <edition>/merged_linkedin_post.md
```
Output must contain a section per story, in numeric-prefix order, and exactly one
shared closing section (no boilerplate repeated once per story).

**Acceptance Scenarios**:

1. **Given** N numbered story folders (N ≥ 2) each containing
   `uk/linkedin_post.md`, **When** the script runs against their parent edition
   folder, **Then** it writes one merged Markdown document containing every story's
   title, message, and closing line, sections ordered by numeric prefix.
2. **Given** the same input, **When** the output is inspected, **Then** the
   repost/contact/subscribe links and the tech-stack section each appear exactly
   once, not once per story.

---

### User Story 2 — Order comes from the folder name, not a guess (Priority: P1)

The operator decides which order best tells the story for a given edition — which is
not always the order the stories happened to be generated in — and fixes that order
once, on disk, by naming each story folder with a leading number.

**Why this priority**: The manual process today leaves order to the model's guess
("I believe the order is obvious, but if you have doubts, ask"). A required,
inspectable prefix removes that ambiguity entirely and makes the order visible without
opening the script or the output.

**Independent Test**:
```
mkdir -p /tmp/edition/{no_prefix_here,also_missing}/uk
touch /tmp/edition/no_prefix_here/uk/linkedin_post.md
touch /tmp/edition/also_missing/uk/linkedin_post.md
python newsletter_merge.py /tmp/edition; echo "exit=$?"
```
Must exit non-zero, naming both folders, before any Gemini call is attempted.

**Acceptance Scenarios**:

1. **Given** story folders named `02_...`, `01_...`, `03_...` on disk (creation order
   unrelated to the numbers), **When** the script runs, **Then** the output order is
   `01`, `02`, `03` — the numeric prefix, not creation time or directory-listing
   order.
2. **Given** two story folders sharing the same numeric prefix, **When** the script
   runs, **Then** it exits non-zero naming both, before any Gemini call.
3. **Given** a story folder with no numeric prefix at all, **When** the script runs,
   **Then** it exits non-zero, names that folder, and asks the operator to add a
   leading number to fix its position — no partial merge is attempted.

---

### User Story 3 — Merge quality is Gemini's job; correctness is the human reviewer's job (Priority: P2)

The operator understands that Gemini's phrasing won't be perfectly deterministic run
to run, the same way the individual `linkedin_post.md` files aren't perfectly
deterministic today — and accepts that trade-off because the merged output is always
reviewed and edited by a human before it's published, never posted automatically.

**Why this priority**: Chasing deterministic, template-exact merging is the wrong bar
for a tool whose output is always human-reviewed; the script's job is to save the
manual copy-paste step, not to guarantee publish-ready text.

**Independent Test**: Run the script twice on the same input and diff the two
outputs — they are not required to be identical, only both structurally complete
(every story present, boilerplate deduped once, cost note present).

**Acceptance Scenarios**:

1. **Given** a `linkedin_post.md` whose wording has drifted from any fixed template
   (hand-edited, or produced by a future version of the LinkedIn Post agent), **When**
   the script sends it to Gemini, **Then** the story is still merged — there is no
   parse step that rejects it for not matching an expected shape.
2. **Given** a successful run, **When** the operator opens the output file, **Then**
   nothing about the tool implies the text is ready to publish without being read
   first.

---

### User Story 4 — Cost is tracked and calls degrade cheapest-first (Priority: P1)

The operator wants to know what an edition actually cost — including the image
generation already paid for when each story was made, plus this merge step — and
wants the merge call itself to prefer the cheapest model that can do the job, only
paying more if a cheaper option fails.

**Why this priority**: Cost visibility has been a first-class concern throughout this
project (Specs 009, 014, 033, 039); a merge step that silently picks an expensive
model, or reports no cost at all, would be a regression from that standard.

**Independent Test**:
```
python -m pytest tests/test_newsletter_merge.py -k cost_fallback -v
```
With the two cheapest models in the chain mocked to fail, the test asserts the third
model in cost order is the one actually called, and that both failures and the
eventual success are logged with their model names.

**Acceptance Scenarios**:

1. **Given** the cheapest model in the chain fails, **When** the script retries,
   **Then** the next-cheapest model is tried next — first exhausting Gemini's own
   models, then falling through to other configured providers, always cheapest of
   what remains.
2. **Given** a successful call, **When** the script logs the outcome, **Then** the log
   shows which model served the request, its token counts, and its actual cost.
3. **Given** stored per-story image-generation costs and a successful merge call,
   **When** the merged document is written, **Then** it ends with a total cost figure
   and a sentence stating that human time spent was not included in that total.

---

### Edge Cases

- Fewer than 2 numbered story folders under the edition folder → hard error; merging
  one story is meaningless, use its own `linkedin_post.md` directly.
- A story folder is missing `<audience>/linkedin_post.md` (default audience `uk`,
  overridable via `--audience`) → hard error naming that folder and the expected
  path, before any Gemini call is made.
- A story folder's `<audience>/telemetry.json` is missing, unreadable, or contains no
  `"Image Generator"` entry → hard error naming that story; an incomplete or wrong
  cost total is treated as worse than no merge.
- Every model in the fallback chain fails (all Gemini options, then all other
  configured providers) → hard error, no output file written.
- The merge call succeeds but its actual realized cost differs from the estimate that
  was baked into the prompt (see FR-010) → both figures are logged; only the estimate
  appears in the published document, since the real figure isn't known until after
  the call returns.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The script MUST accept one positional argument: the path to an edition
  folder.
- **FR-002**: The script MUST treat each immediate child directory of the edition
  folder containing `<audience>/linkedin_post.md` (audience configurable via
  `--audience`, default `uk`) as a candidate story.
- **FR-003**: The script MUST require at least 2 candidate stories; given fewer, it
  MUST exit non-zero before making any Gemini call.
- **FR-004**: Every candidate story folder's name MUST start with one or more digits
  followed by `_` or `-` (e.g. `01_story-name`, `2-story-name`). A candidate missing
  this prefix MUST cause a hard error, before any Gemini call, naming every offending
  folder and instructing the operator to add a leading number to fix its position.
- **FR-005**: Candidates MUST be ordered ascending by the numeric value of that
  prefix (no zero-padding or contiguity requirement — the numbers are only a sort
  key). Two candidates sharing the same numeric prefix MUST cause a hard error naming
  the colliding folders, before any Gemini call.
- **FR-006**: A candidate missing `<audience>/linkedin_post.md` MUST cause a hard
  error naming the folder and the expected path — already covered by FR-002's
  candidate definition, but a folder that looks like a story and isn't one must fail
  loudly, not be silently skipped.
- **FR-007**: The script MUST NOT send images to Gemini — the request is built from
  each candidate's `linkedin_post.md` text only.
- **FR-008**: The script MUST NOT validate `linkedin_post.md` content against any
  fixed template shape — hand-edited or drifted text is passed to Gemini as-is.
- **FR-009**: The script MUST produce the merged content from exactly one successful
  Gemini call (FR-013's fallback chain may make multiple attempts, but only one
  produces the final output), whose prompt: states the numeric story order
  explicitly, includes each story's full text, instructs consolidation of content
  repeated across stories into a single shared section, and gives the model latitude
  to merge and phrase content in ways that aren't mechanically dictated by the input.
- **FR-010**: Before making the call, the script MUST compute an estimated total
  edition cost: (a) the exact sum of every `total_cost_usd` value recorded under an
  agent entry named exactly `"Image Generator"` in each candidate's
  `<audience>/telemetry.json` (every iteration/attempt recorded, not just the
  approved one — all of them were paid for), plus (b) an estimate for the merge call
  itself, computed from the selected model's published per-million-token rate and its
  `max_tokens` output ceiling as a conservative upper bound for the output portion, so
  the published figure does not understate the call's actual cost.
- **FR-011**: The same prompt (FR-009) MUST instruct Gemini to append, as the final
  line(s) of the merged document, the total from FR-010 and a fixed sentence stating
  that human time spent was not included in that figure.
- **FR-012**: A candidate whose `<audience>/telemetry.json` is missing, unreadable, or
  contains no `"Image Generator"` entry MUST cause a hard error naming the story,
  before any Gemini call.
- **FR-013**: The merge call MUST be attempted against an ordered list of candidate
  models, cheapest first: every currently-active Gemini text model (excluding image
  models), ranked ascending by combined (input + output) rate per million tokens from
  `llm/gemini.py`'s `_COST_PER_M` table; if every Gemini option fails, the script MUST
  fall through to other configured providers' models (Claude, Grok), again ranked
  ascending by the same combined-rate metric from their own `_COST_PER_M` tables.
  (Illustrative ranking as of the current tables: `gemini-2.5-flash-lite` →
  `gemini-3.1-flash-lite` → `gemini-2.5-flash` → `gemini-2.5-pro` →
  `gemini-3.1-pro-preview` → `grok-build-0.1` → `grok-4.3` → `claude-haiku-4-5` →
  `grok-4.5` → `claude-sonnet-4-6` → `claude-opus-4-8` — this list is expected to
  shift whenever pricing is refreshed, e.g. by a future Spec-039-style update.)
- **FR-014**: For every model attempted, the script MUST log (via the `logging`
  module, per Constitution §13) success or failure; on success it MUST log the model
  used, its token counts, and its actual computed cost.
- **FR-015**: If every model in the fallback chain fails, the script MUST exit
  non-zero and write no output file.
- **FR-016**: The script MUST write Gemini's output verbatim (including the cost note
  it appended per FR-011) to `<edition_folder>/merged_linkedin_post.md` by default, or
  a path given via `-o/--output`.
- **FR-017**: The script MUST verify that the credentials needed for the full
  fallback chain (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `XAI_API_KEY`, loaded per
  RULE 16) are present before making any call, and fail clearly naming which are
  missing.
- **FR-018**: The script's output is explicitly a draft. Nothing in its behaviour,
  naming, or output implies auto-publishing; there is no flag or code path that posts
  the result anywhere.

### Key Entities

- **OrderedStory**: one candidate's folder path, its numeric prefix, its
  `linkedin_post.md` text, and its summed `"Image Generator"` cost from
  `telemetry.json`.
- **EditionMergeRequest**: the ordered list of `OrderedStory` entries, the audience
  name, the FR-010 estimated total cost, and the cost-ordered model fallback chain.
- **MergeCallResult**: the model that actually served the request, its token usage,
  and its actual (as opposed to estimated) cost.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a fixture with story folders renamed to carry numeric prefixes
  matching the known-good hand-merged order from `03_special_holiday_edition`, the
  script reproduces that section order.
- **SC-002**: Given candidate folders with no numeric prefix, the script exits
  non-zero before any Gemini call, and no output file is written.
- **SC-003**: With the two cheapest models in the fallback chain mocked to fail, the
  third-cheapest is the one actually called, and the log records both failures and
  the eventual success with model names.
- **SC-004**: Given fixture `telemetry.json` files with known `"Image Generator"`
  costs, the total figure the (mocked) Gemini response is asked to include matches
  sum(image costs) + the FR-010 merge-call estimate, and the log separately records
  the actual realized cost of the winning call.
- **SC-005**: `python -m pytest tests/test_newsletter_merge.py` passes with every
  provider call mocked per Constitution §9 — zero real API calls during tests.

## What does NOT change

- `pipeline.py` and `core/cli.py` are untouched; `gata <topic>` remains a
  single-topic generator with no awareness of newsletter editions.
- No new CLI subcommand is added in this stage — the script is invoked directly
  (`python newsletter_merge.py <edition_folder>`). Worth revisiting as its own later
  spec once the script is in regular use.
- Multi-audience / multi-language edition merging (a story with both `uk` and
  `portuguese` sub-folders, wanting both merged) is out of scope; one audience per run
  via `--audience`.
- Any manual preamble (e.g. a "Collaborators Wanted!" call-out prepended before the
  numbered stories) is not generated by this script — it's added by hand before
  publishing, same as today.
- The script never publishes anywhere; its only output is a local Markdown file for a
  human to review and post manually.
- The cost-ordered fallback chain (FR-013) is a new, hardcoded-by-default list local
  to this script — it is not added to `providers.yaml`'s existing `panelists` /
  `aggregator` schema, which serves the FairParallelPanel/dual-loop execution model, a
  different concept. A future spec could move it there if config-driven override
  becomes desirable.

## Assumptions

- None of the existing newsletter edition folders on disk currently carry numeric
  prefixes — they were named directly from each story's topic slug. Using this script
  on existing editions requires a one-time manual rename to add leading numbers; this
  is expected setup, not a defect.
- The total cost figure Gemini is asked to append is an estimate at prompt-build
  time (exact image-generation costs plus an upper-bound estimate of the merge call's
  own cost), not a receipt — the actual realized cost, logged separately, is expected
  to be at or below the published figure by design (FR-010's conservative estimate),
  never above it.
- The cost ordering in FR-013 reflects the `_COST_PER_M` tables as they stand today
  (most recently refreshed by Spec 039); like any hardcoded pricing reference in this
  codebase, it drifts if a provider changes rates without a corresponding refresh.
- Non-determinism (User Story 3) applies to Gemini's prose; it does not apply to the
  appended cost figure, which is script-computed, not model-computed — the model is
  only asked to place it, not calculate it.
