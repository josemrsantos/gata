# Implementation Plan: Researched LinkedIn Article

**Branch**: `042-researched-linkedin-article` | **Date**: 2026-08-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/042-researched-linkedin-article/spec.md`

## Summary

Rewrite `agents/agent_linkedin_post.py`'s content-generation pipeline from a single
ungrounded LLM call into four stages: three independent, provider-native web
searches (one per panelist provider — Gemini's Google Search grounding, Claude's
`web_search_20250305` tool, xAI's Agent Tools `web_search` tool), an angle-planning
`FairParallelPanel` deliberation, and a writing `FairParallelPanel` deliberation.
Each panelist's own research is embedded into that panelist's own system prompt —
`FairParallelPanel` itself is untouched. The published Sources list is the
deduplicated union of every panelist's own real sources, assembled by code — never
parsed from or trusted to LLM output — so no citation in the final article can be
fabricated. A new repeatable `--angle` flag on both `gata` and `pipeline.py` seeds
the angle-planning stage without touching cartoon generation at all.

**Revision note**: an earlier version of this plan used one shared Gemini-only
search digest hedged as safer to build unattended overnight. The developer
explicitly rejected that trade-off — independent per-provider research was
requested even at higher cost/latency — so this plan (and the implementation) was
redone accordingly before any further code was written.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `google-genai` (Google Search grounding, already used by
`infer_mood()`), `anthropic` (web search tool, already a dependency),
`openai`-compatible client pointed at xAI (Responses API, already a dependency) —
no new package added
**Storage**: Files only — same output contract as Spec 038
(`linkedin_post.md`, `linkedin_notification.txt`)
**Testing**: pytest with `unittest.mock` (no real API calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: Rewrite of one agent's internals + two new CLI flags; no new
top-level entry point
**Performance Goals**: Three parallel research calls (each bounded to 120s) + two
`FairParallelPanel` runs (3 panelists + aggregator each, writing panel's
`panelist_timeout` raised to 120s) per `--linkedin-post` invocation. Confirmed via
a real end-to-end run: ~360s wall time, ~$0.64 total for one full cartoon + article
run (LinkedIn portion alone: ~4 minutes, ~$0.20) — this is significantly more than
Spec 038's single-call version, an explicitly accepted trade-off.
**Constraints**: ruff `line-length = 88`, `target-version = "py310"`; RULE 12 — the
cartoon's own manual invocation must keep working unchanged (confirmed via the same
live run — cartoon generation and its retry/evaluator behaviour were unaffected);
the two panels reuse `panelist_providers`/`aggregator_providers` already threaded
through `run_pipeline()`, no new provider-config surface
**Scale/Scope**: 1 file rewritten (`agents/agent_linkedin_post.py`), 2 provider
classes gain a `client` property (`llm/claude.py`, `llm/grok.py`), 3 files gain a
small parameter (`core/runner.py`, `core/cli.py`, `pipeline.py`), 2 new dataclasses
in `core/types.py`, 1 test file added, 2 test files gain `client`-property coverage

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | All three research calls use each provider's own already-active SDK (`google-genai`, `anthropic`, `openai`-compatible xAI client); no new SDK, no retired model. |
| 2 | Image Output Rule | ✅ N/A | No image is generated or touched by this feature. |
| 3 | XML and Output Contract | ✅ | Both `FairParallelPanel` runs use `<verdict>...</verdict>` — confirmed live: the writing panel's system prompt initially omitted this instruction and every panelist response was rejected as malformed; fixed and re-verified against a real run before considering this row satisfied. |
| 4 | Character Rules | ✅ N/A | This feature produces text only; no image prompt is built. |
| 5 | Visual Style Rules | ✅ N/A | No image prompt is constructed. |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ N/A | Verdicts here are freeform prose (an angle list, then an article), not the Satirist's JSON contract — same precedent as Spec 041's Engagement Image Concept. |
| 7 | Language Rule | ✅ | Article language follows `brief.output_language`, unchanged from Spec 038. |
| 8 | Project Structure | ✅ | Changes land in `agents/`, `core/`, `llm/`, `tests/` only, plus the two existing top-level CLI scripts. |
| 9 | Testing Rules | ✅ | `tests/test_agent_linkedin_post.py` covers all three research paths, both panels, source merging, and end-to-end soft-failure chaining, all mocked; every test carries a RULE-3 comment; zero real API calls in the suite (verified separately against real APIs via a live end-to-end run, per the developer's explicit request). |
| 10 | Secrets and Security | ✅ | No new secret; reuses `GEMINI_API_KEY`/`ANTHROPIC_API_KEY`/`XAI_API_KEY` already required. |
| 11 | Development Stages | ✅ | Branch `042-researched-linkedin-article` created off `main` before any file was written. |
| 12 | Code Quality | ✅ | `ruff check .` / `ruff format .` clean on every changed file; RULE 14 followed. |
| 13 | Logging | ✅ | Every research attempt (per provider), angle-planning call, and writing call logs success/failure with model and cost; a real per-provider duration-measurement bug (fixed-order result collection reporting near-zero duration for whichever future finished first) was caught during self-review and fixed by timing each call internally rather than at the collection point. |

**Constitution Check result**: all gates pass (rows 2, 4, 5, 6 are N/A). Row 3 and
row 13 each surfaced a real bug during live testing/self-review, both fixed and
re-verified before this row was marked ✅ — noted explicitly rather than silently
corrected, since the developer asked to see what was found.

## Project Structure

### Documentation (this feature)

```text
specs/042-researched-linkedin-article/
├── spec.md
└── plan.md
```

### Source Code Changes

```text
agents/agent_linkedin_post.py   REWRITE — keeps generate_linkedin_post() as the
                                 public entry point and the file output contract
                                 (linkedin_post.md / linkedin_notification.txt),
                                 but internally:
                                 - _research_gemini/_research_claude/_research_grok:
                                   one real web-search call per provider, each
                                   returning (ResearchDigest | None, TokenUsage |
                                   None, elapsed_seconds) (FR-001, FR-003)
                                 - _research_for_provider: isinstance-based
                                   dispatch to the right one (FR-001)
                                 - research_all_panelists: runs all three in
                                   parallel via ThreadPoolExecutor, each bounded
                                   to 120s; a single failure/timeout yields None
                                   for that slot only (FR-001, FR-005)
                                 - _panelist_research_context: builds the
                                   per-panelist system-prompt addendum (that
                                   panelist's own findings/sources, or an
                                   explicit "no research available" instruction)
                                   (FR-004)
                                 - _plan_angles: FairParallelPanel run (default
                                   60s panelist_timeout), panelists named by
                                   model_id, aggregator named "Managing Editor",
                                   operator angles injected as mandatory
                                   (FR-006, FR-007)
                                 - _write_article: second FairParallelPanel run
                                   with panelist_timeout=120 (FR-009)
                                 - _merge_sources / _build_sources_section: pure
                                   code, deduplicated union of every digest's
                                   real sources, never LLM output (FR-011)
                                 - _assemble_article: code-inserted AI-authorship
                                   disclosure (FR-013) + code-built Sources
                                   section
                                 generate_linkedin_post() signature:
                                 (brief, topic, telemetry, panelist_providers,
                                 aggregator_providers, angles=None) — image_prompt
                                 parameter dropped (FR-014)

llm/claude.py, llm/grok.py      MODIFY — each gains a `client` property mirroring
                                 GeminiProvider.client, exposing the underlying
                                 SDK client for this feature's direct search calls
                                 without changing generate()'s signature (FR-002).

core/types.py                   ADD — ResearchSource, ResearchDigest dataclasses
                                 (one digest per panelist provider, never merged
                                 into a single shared digest).

core/runner.py                  MODIFY — run_pipeline() gains angles: list[str] |
                                 None = None; the LinkedIn Post call site passes
                                 panelist_providers, aggregator_providers, and
                                 angles instead of the old single aggregator-only
                                 providers list + image_prompt (FR-015).

core/cli.py                     MODIFY — gata command gains repeatable --angle
                                 TEXT (action="append"); passed to
                                 run_pipeline(angles=args.angle); logs at INFO
                                 (not an error) when supplied without
                                 --linkedin-post (FR-016).

pipeline.py                     MODIFY — same --angle flag added once; passed to
                                 all four existing run_pipeline(...) call sites
                                 (manual, community+topic, random,
                                 community-only) (FR-016).

tests/test_agent_linkedin_post.py   ADD — covers every research path (success,
                                     API exception, empty-text/output failure),
                                     source extraction per provider (including
                                     xAI's confirmed-live annotation shape and
                                     its footnote-number "title" quirk),
                                     dispatch, parallel research orchestration
                                     and per-call timing, angle-planning and
                                     writing panel construction (mandatory
                                     angles, per-panelist research embedding,
                                     120s writing timeout), source merging, and
                                     generate_linkedin_post()'s end-to-end
                                     soft-failure chaining.

tests/test_claude_provider.py,      MODIFY — add coverage for the new `client`
tests/test_grok_provider.py         property.
```

**Structure Decision**: Rewrite in place rather than a new module — this is the
same feature (Spec 038) evolving, not a new agent; `generate_linkedin_post()`
stays the one public entry point `core/runner.py` calls. Each panelist's own
research lives in that panelist's own `PersonaConfig.system_prompt` rather than
`FairParallelPanel`'s shared `initial_input`, which is what let this feature avoid
touching `llm/fair_parallel_panel.py` at all despite needing per-panelist-distinct
context — the shared protocol used by every other panel-based agent in this
project (Cultural Strategist, Satirist, Explainer, Spec 041's Engagement Image
Concept) is completely unmodified. Rejected alternative: extending
`FairParallelPanel.run()` to accept a list of per-panelist initial inputs instead
of one shared string — would have worked, but touches shared infrastructure four
other agents depend on for a need this feature can meet entirely through the
per-panelist system prompt it already has.

## Issues found and fixed during implementation (for the record)

1. **Missing `<verdict>` wrapping instruction** in the writing panel's system
   prompt — every panelist's response was rejected by `FairParallelPanel` as
   malformed, so the entire writing stage failed on the first live run. Fixed by
   adding the same wrapping instruction already present in the angle-planning
   prompt; re-verified on a second live run.
2. **xAI's Live Search (`search_parameters` via chat completions) is fully
   deprecated** — confirmed live via an HTTP 410 response with a link to the
   replacement API, not merely "migrating soon" as originally hedged in the
   spec's Assumptions. Rebuilt `_research_grok` against xAI's current Agent
   Tools / Responses API (`client.responses.create(..., tools=[{"type":
   "web_search"}])`), confirmed working live (5–8 real sources returned).
3. **xAI's citation `title` field is the in-text footnote number** (e.g. `"1"`),
   not a page title — confirmed by inspecting a real response. Fixed to use the
   URL itself as the display title, matching the fallback behaviour already used
   when Gemini/Claude don't supply one.
4. **Per-provider research duration was measured at the wrong point** —
   `research_all_panelists` started its timer immediately before calling
   `.result()` on each future, in a fixed iteration order; since the futures run
   in parallel and may already be complete by the time a given one is checked,
   whichever provider happened to finish first (observed live: Gemini) reported
   a misleading ~0.0s duration. Fixed by timing each research call internally,
   inside the function actually submitted to the executor, so the reported
   duration is that call's own real wall time regardless of collection order.
5. **Known, not fixed — cosmetic only**: Gemini's grounding metadata returns
   Google redirect URLs (`vertexaisearch.cloud.google.com/grounding-api-redirect/...`)
   with only a bare domain as the title (e.g. `"ibm.com"`), rather than the
   source page's direct URL and full title. This is inherent to how Gemini's
   grounding API responds, not a defect in this feature's extraction code — the
   links are still real and resolve to the actual source, just less
   human-readable than Claude's fully-titled citations in the same Sources list.

## Amendment (2026-08-29): Executive Summary + reordered meta content

**Living Spec amendment** (CLAUDE.md RULE 18) implementing `spec.md`'s
"Amendment (2026-08-29)" section (FR-020–FR-023, SC-008–SC-011). Branch:
`042-linkedin-article-structure` — a fresh branch per RULE 5 for this stage of
work, distinct from the original `042-researched-linkedin-article` branch that
already merged.

### Source Code Changes (this amendment)

```text
agents/agent_linkedin_post.py   MODIFY:
                                 - _WRITER_SYSTEM: insert a new
                                   ===EXECUTIVE_SUMMARY=== marker between
                                   ===TITLE=== and ===BODY=== (3-5 sentence
                                   summary of the article's core finding);
                                   drop "introduction plus" from the BODY
                                   instruction — BODY becomes per-angle
                                   sections only (FR-020, FR-021).
                                 - _WRITER_AGGREGATOR_SYSTEM: add
                                   ===EXECUTIVE_SUMMARY=== to the marker list
                                   it requires the Managing Editor to preserve
                                   (FR-021).
                                 - _parse_sections: add
                                   "===EXECUTIVE_SUMMARY===" to the markers
                                   list.
                                 - _assemble_article: pull
                                   sections.get("EXECUTIVE_SUMMARY", ""); build
                                   "## Executive Summary\n\n{summary}" as its
                                   own part right after the title, omitted
                                   entirely when empty (FR-020). Remove
                                   _DISCLOSURE and the Pipeline Metrics line
                                   from their current position (right after
                                   title); append both, in that order, to the
                                   end of the static _SECTION_4_BODY
                                   ("Behind the Scenes") instead (FR-022). New
                                   part order matches FR-023.

tests/test_agent_linkedin_post.py   MODIFY — add coverage for: Executive
                                     Summary heading placement (present vs.
                                     omitted-when-empty), Pipeline
                                     Metrics/disclosure now landing inside
                                     Behind the Scenes rather than near the
                                     top, and the overall part order via
                                     string-index comparisons (SC-008–SC-010).
                                     Existing presence-only tests
                                     (`test_assemble_article_includes_disclosure_and_omits_empty_sources`,
                                     `test_assemble_article_includes_sources_section_when_present`)
                                     need no changes — they assert presence,
                                     not position, and remain true after the
                                     move.
```

**Structure Decision**: extend the existing five-marker parsing contract
(`_parse_sections`) with a sixth marker rather than post-processing `BODY` text
to guess where an intro paragraph ends — consistent with how `TITLE`/`COMMENT`/
`NOTIFICATION` are already each their own explicit block, and avoids coupling
correctness to markdown heading conventions the writer prompt encourages but
doesn't strictly enforce. Considered and rejected: splitting `BODY` on its first
`## ` heading in code (zero prompt/LLM-contract risk, but silently wrong for any
panelist that doesn't emit a bare lead-in paragraph before its first heading).

Because this changes the writing panel's `<verdict>` marker contract, it
requires the same live re-verification discipline as when the format was first
introduced (see "Issues found and fixed during implementation" above, item 1) —
a real `--linkedin-post` run must be inspected before this is considered done,
not just the mocked test suite.

### Constitution Check (re-run for this amendment)

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 3 | XML and Output Contract | ✅ | The `<verdict>` wrapper and marker-block convention is extended (new `===EXECUTIVE_SUMMARY===`), not replaced — re-verified live per the discipline noted above. |
| 9 | Testing Rules | ✅ | New tests use string-index ordering assertions (`article.index(...)`), all mocked; every new test carries a RULE-3 comment. |
| 11 | Development Stages | ✅ | Branch `042-linkedin-article-structure` created off `main` before any file was written for this amendment. |
| 12 | Code Quality | ✅ | `ruff check --no-cache` / `ruff format --check --no-cache` clean on every changed file. |
| 13 | Logging | ✅ N/A | No new logging behaviour — same call sites, same telemetry. |

All other Constitution Check rows from the original plan are unaffected by this
amendment.

## Amendment (2026-08-29, part 2): Curated, paywall-free, numbered references

Implements `spec.md`'s "Amendment (2026-08-29, part 2)" (FR-024–FR-030,
SC-012–SC-017). Branch: `042-curated-references`. Design finalized after three
rounds of discussion — superseded drafts (single-model classifier + YAML
cache) are not implemented; this section reflects only the final form.

### Source Code Changes (this amendment)

```text
pyproject.toml                  MODIFY — add `duckdb` as a new dependency.

.gitignore                      MODIFY — add `source_domains.duckdb` (a
                                 regenerating local cache, not checked in).

llm/fair_parallel_panel.py      MODIFY — FairParallelPanel gains an optional
                                 `round_validator:
                                 Callable[[dict[str, str]], dict[str, str]]
                                 | None = None` constructor parameter. After
                                 each non-final round, if set, it's called
                                 with {panelist_name: verdict_content} for
                                 that round's survivors and returns
                                 {panelist_name: extra_feedback_text} for any
                                 panelist that needs it; that text is appended
                                 to the next round's peer-prompt (or to
                                 initial_input, in the single-survivor no-
                                 peers case). Defaults to None — every
                                 existing caller (Cultural Strategist,
                                 Satirist, Explainer, Engagement Image
                                 Concept, LinkedIn Angle Planning, LinkedIn
                                 Article Writing itself for every other
                                 concern) is unaffected unless it opts in
                                 (FR-028).

agents/agent_linkedin_post.py   MODIFY:
                                 - _build_research_query: adds the
                                   academic/highly-reputable-sources steer
                                   (FR-024).
                                 - _domain_cache module: thin DuckDB
                                   open/read/write helpers against
                                   source_domains.duckdb — one `domains`
                                   table (FR-025).
                                 - _classify_domains_panel: builds a
                                   FairParallelPanel (same panelist/
                                   aggregator providers already threaded
                                   through this feature), panelist_timeout=90,
                                   iterations=3, asking for a strict JSON
                                   verdict per unclassified domain; persists
                                   results to the DuckDB cache; fails open
                                   (no write, domain stays eligible) on total
                                   panel failure (FR-026.2).
                                 - research_all_panelists: after collecting
                                   all three digests, runs the cache-lookup +
                                   _classify_domains_panel step, strips
                                   sources for any now-excluded domain from
                                   each digest, and logs a WARNING per
                                   excluded source (FR-026.3/4) — before
                                   returning digests to its caller.
                                 - _build_citable_sources_block: renders the
                                   filtered, numbered candidate list embedded
                                   in each writing panelist's system prompt
                                   (FR-027).
                                 - _WRITER_SYSTEM: instruct panelists to cite
                                   inline via [N] against the supplied list,
                                   ~2 distinct citations per body section,
                                   outer cap 15, never inventing a number
                                   (FR-027).
                                 - _citation_round_validator: the
                                   round_validator passed to the writing
                                   FairParallelPanel — parses each survivor's
                                   BODY into sections, counts [N] occurrences
                                   per section, and for any section over 2,
                                   returns feedback text asking that panelist
                                   to trim it before the next round (FR-028).
                                 - _extract_and_renumber_citations: parses
                                   [N] markers from EXECUTIVE_SUMMARY+BODY in
                                   first-appearance order, drops invalid
                                   indices, caps at 15 distinct, renumbers
                                   sequentially, rewrites markers in the
                                   text, returns (rewritten_summary,
                                   rewritten_body, final_ordered_sources)
                                   (FR-029, FR-030).
                                 - _build_sources_section: rewritten to emit
                                   an ordered markdown list (`1. ...`, `2.
                                   ...`) instead of a bullet list, matching
                                   the new numbering.
                                 - _write_article: takes the numbered
                                   candidate list, embeds
                                   _build_citable_sources_block's text into
                                   each panelist's system prompt, and passes
                                   _citation_round_validator to the
                                   FairParallelPanel constructor.
                                 - generate_linkedin_post: sequences the new
                                   classify/filter/number step right after
                                   research_all_panelists returns (before
                                   _plan_angles), passes the numbered
                                   candidates into _write_article, and runs
                                   _extract_and_renumber_citations on the
                                   returned EXECUTIVE_SUMMARY/BODY before
                                   _assemble_article.

tests/test_fair_parallel_panel.py   MODIFY — add coverage for the new
                                     round_validator hook: called with the
                                     right survivor verdicts after each
                                     non-final round, its feedback reaching
                                     the next round's prompt, and every
                                     existing test still passing unchanged
                                     with the parameter omitted (backward
                                     compatibility).

tests/test_agent_linkedin_post.py   MODIFY — add coverage for: DuckDB cache
                                     read/write round-trip, classification
                                     panel construction (panelist_timeout=90,
                                     iterations=3) and fail-open behaviour
                                     (SC-013), paywalled/low-reliability
                                     exclusion happening on the digest before
                                     angle-planning ever sees it (SC-012),
                                     the per-section round_validator logic,
                                     citation extraction + invalid-index
                                     stripping + renumbering (SC-014), the
                                     15-source cap (SC-015), and the
                                     reordered generate_linkedin_post call
                                     sequence.
```

**Structure Decision**: filter immediately inside `research_all_panelists`,
not later in `generate_linkedin_post` — confirmed with the operator that this
is the earliest point this pipeline can act, since each provider's own search
tool is a server-side black box (no earlier hook exists to classify a URL
before that provider's tool fetches it; see spec.md's Assumptions). Domain
classification is a full `FairParallelPanel` deliberation, not a single-model
call — a deliberate reversal of this amendment's first draft, per the
developer's explicit ask for cross-checked judgment over a single model's
opinion, accepting the added latency (mitigated over time by the persistent
cache). `round_validator` is added to the shared `FairParallelPanel` class
(rather than duplicating the round loop in `agent_linkedin_post.py`) so the
per-section citation check can see and influence panelist rounds using the
class's own existing peer-prompt machinery — but strictly opt-in, so it can
never change behaviour for the four other agents already depending on this
class.

Rejected alternative, discussed and ruled out with the operator: true pre-
fetch gating (classify a URL before any provider's tool reads it). Not
implementable without replacing provider-native search tools (Gemini
grounding, Claude `web_search`, Grok Agent Tools) with a fully custom search
step — a much larger, different change than this amendment; recorded as an
Assumption in spec.md rather than attempted.

Rejected alternative for the citation cap: silently letting the writer's own
per-section instruction be the only enforcement (simpler, but the developer
explicitly asked for both a mid-round nudge and a hard code-level backstop,
consistent with this project's general stance that LLM instruction-following
on hard numeric limits isn't reliable enough to trust alone).

Because this again changes what the writing panel receives and produces (a
new citable-sources block in its prompt, round-to-round validator feedback, a
stricter output contract on citation markers) and adds a wholly new panel
stage (domain classification) between research and angle-planning, it
requires the same live re-verification discipline as the Executive Summary
amendment — a real `--linkedin-post` run must be inspected (in-text `[N]`
markers matching the Sources list, no paywalled/low-reliability domain
present, ≤15 sources, excluded-domain warnings visible in the log) before
this is considered done.

### Constitution Check (re-run for this amendment)

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | Domain classification reuses the existing panelist/aggregator provider chains and `FairParallelPanel`; `duckdb` is a new dependency (embedded, no server) — justified in spec.md's Assumptions. |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ N/A | The classification panel's verdict is a plain JSON object keyed by domain, not the Satirist's schema — same precedent as Engagement Image Concept and LinkedIn Angle Planning's freeform verdicts. |
| 9 | Testing Rules | ✅ | New tests cover DuckDB round-trip, fail-open classification, filtering-before-angle-planning, the `round_validator` hook (both in `fair_parallel_panel.py` and this feature's own validator function), citation extraction/renumbering/capping, all mocked; every new test carries a RULE-3 comment. |
| 11 | Development Stages | ✅ | Branch `042-curated-references` created off `main` before any file was written for this amendment. |
| 12 | Code Quality | ✅ | `ruff check --no-cache` / `ruff format --check --no-cache` clean on every changed file. |
| 13 | Logging | ✅ | Each excluded source (domain + reason), classification panel success/failure, and citation counts kept/stripped/capped are all logged via the existing `logger`. |

All other Constitution Check rows from the original plan and the first
amendment are unaffected.
