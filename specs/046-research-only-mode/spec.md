# Feature Specification: Research-Only Mode

**Spec**: `046-research-only-mode`
**Branch**: `046-research-only-mode`
**Created**: 2026-08-30
**Status**: Draft — awaiting approval
**Dependency**: builds on Spec 042 (researched article engine) and Spec 035
(minimal-brief precedent); does not modify either's core internals.

## Problem

Every run of the pipeline generates a satirical cartoon (Cultural Strategist,
Satirist, Image Generator, Image Evaluator) regardless of what the operator
actually wants. There is no way to use the tool purely for research/reporting:
even suppressing the image would still pay for Cultural Strategist and
Satirist concept-generation cost, which produce nothing usable in a
research-only context. Separately, `agent_linkedin_post.generate_linkedin_post`
has never actually needed a cartoon concept — `core/runner.py`'s
`_can_generate_post` gate requires one anyway, an artificial coupling that
this spec removes for the new mode.

## Goal

Add a `--research-only` flag (both `pipeline.py` and the installed `gata`
CLI) that skips the entire satirical pipeline — Cultural Strategist,
Satirist, Image Generator, Image Evaluator — and runs only Spec 042's
research → angle-planning → writing engine against a minimal `EnrichedBrief`
built directly from the topic/seed brief (same construction already used by
`--direct`). By default this produces a new, fully neutral, unbranded
`research_report.md`. When `--linkedin-post` is also supplied, it instead
produces the existing Gata-branded `linkedin_post.md` /
`linkedin_notification.txt` — usable for the first time without any cartoon
concept behind it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Pure, neutral research report (Priority: P1)

The operator wants only a researched report on a topic, with no cartoon, no
image cost, and no Gata branding.

**Why this priority**: This is the entire point of the feature — a genuine
research-only mode, not a suppressed-image cartoon run.

**Independent Test**:
```
python pipeline.py --topic "AI regulation in the EU" --audience "policy analysts" \
  --language English --tone neutral --research-only
```

**Acceptance Scenarios**:

1. **Given** `--research-only` alone, **When** the run completes, **Then** no
   image file is produced, no Cultural Strategist / Satirist / Image
   Generator / Image Evaluator telemetry entries appear in the summary, and
   `research_report.md` is written to the output bundle.
2. **Given** a successful run, **When** `research_report.md` is inspected,
   **Then** it contains a Title, an optional Executive Summary, the per-angle
   body, a Sources section (when any citations survived), a Pipeline Metrics
   line, and the AI-authorship disclosure — and contains no "Behind the
   Scenes" tech-stack promo, no closing/subscribe block, and no reference to
   "Gata" anywhere.
3. **Given** every provider's research fails (Spec 042's existing total
   soft-failure), **When** the run completes, **Then** no
   `research_report.md` is written, a warning is logged, and the run does not
   crash — identical soft-failure contract to Spec 042.

---

### User Story 2 — Research-only + LinkedIn post, no cartoon required (Priority: P1)

The operator wants the existing branded LinkedIn article, but without paying
for cartoon generation at all.

**Why this priority**: Removes an artificial limitation — the LinkedIn
article never needed a cartoon concept in the first place.

**Independent Test**:
```
gata "AI regulation in the EU" --research-only --linkedin-post
```

**Acceptance Scenarios**:

1. **Given** both flags, **When** the run completes, **Then**
   `linkedin_post.md` and `linkedin_notification.txt` are written in exactly
   today's Spec 042 format, no `research_report.md` is written, and no image
   or cartoon telemetry is produced.
2. **Given** both flags, **When** `generate_linkedin_post` is invoked,
   **Then** it is called with `branded=True`, producing byte-for-byte the
   same kind of output today's `--linkedin-post` (with a cartoon) produces,
   aside from the metrics line naturally reflecting the cheaper run.

---

### User Story 3 — `gata` CLI runs once, not per audience (Priority: P1)

`gata`'s normal behaviour infers several audiences from the topic and
generates one cartoon per audience (Spec 008). That model doesn't fit a
single neutral report.

**Why this priority**: Without this, `--research-only` on `gata` would
wastefully generate the same report N times, once per inferred audience.

**Independent Test**:
```
gata "AI regulation in the EU" --research-only
```

**Acceptance Scenarios**:

1. **Given** `--research-only` on the `gata` CLI, **When** the run executes,
   **Then** audience inference still runs (to derive language/tone/audience
   context) but the per-audience loop is bypassed — `run_pipeline` is called
   exactly once, using only the first inferred audience, not once per
   audience.

---

### User Story 4 — Output bundle independent of any image path (Priority: P1)

Today's bundle directory is derived from the cartoon's own `output_path`
(`Path(output_path).parent / Path(output_path).stem`). Research-only mode has
no image, so it needs its own naming scheme.

**Why this priority**: Without this, there is no defined location for the
bundle at all in this mode.

**Independent Test**: inspect the `output/` tree after a `--research-only`
run.

**Acceptance Scenarios**:

1. **Given** `--research-only`, **When** the run completes, **Then** the
   bundle directory lives under `output/research/`, named from the topic
   slug plus a timestamp (`%Y%m%d_%H%M%S`) — never derived from or requiring
   any image file.

---

### Edge Cases

- `--research-only` + `--direct` → `--direct` is redundant (Cultural
  Strategist is already skipped by `--research-only`); logged at INFO, not
  an error — same treatment as `--angle` without `--linkedin-post`.
- `--research-only` + `--panels` / `--layout` / `--no-title` → silently
  inert; no image is ever generated in this mode, so these flags are simply
  never read on this path.
- `--research-only` + `--html` → no effect; `bundle_writer`'s existing
  `include_html` guard already requires a non-`None` `image_prompt`, which
  is always `None` in this mode — no new guard needed.
- `--research-only` without `--linkedin-post`, total research failure → no
  `research_report.md` is written; run still exits normally (soft failure,
  per Spec 042's existing contract).
- `--research-only` + `--angle` → works identically to today; angles feed
  the same angle-planning panel regardless of branding.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `core/runner.py`'s `run_pipeline()` gains a new
  `research_only: bool = False` parameter. When `True`, the Cultural
  Strategist, Satirist, Image Generator, and Image Evaluator are never
  called — none of their `AgentTelemetry` entries appear in the returned
  `RunTelemetry`.
- **FR-002**: When `research_only=True`, a minimal `EnrichedBrief` is built
  directly from `topic`/`seed_brief` — the same fields/values as today's
  `skip_cultural_strategist` minimal-brief construction. This construction is
  factored into a shared private helper (e.g. `_minimal_brief(topic,
  seed_brief)`) used by both `--direct` and `--research-only`, removing the
  duplication rather than copying the six-field literal a second time.
- **FR-003**: When `research_only=True`,
  `agent_linkedin_post.generate_linkedin_post` is **always** invoked
  (regardless of the existing `generate_linkedin_post` flag's value), using
  the minimal `EnrichedBrief` (FR-002), the run's panelist/aggregator
  providers, and `angles`. It is called with `branded=<generate_linkedin_post
  flag's value>` — `True` only when `--linkedin-post` was also supplied.
- **FR-004**: `agent_linkedin_post.generate_linkedin_post` gains a
  `branded: bool = True` parameter. The default preserves every existing
  caller's behaviour unchanged (today's `--linkedin-post`, without
  `--research-only`, is unaffected).
- **FR-005**: A new `_assemble_report` function (parallel to
  `_assemble_article`) is used when `branded=False`: Title (H1, falling back
  to `"Research Report: {topic}"` instead of `"Gata's Panel Weighs In"` when
  the writer panel's own `TITLE` is empty), Executive Summary (when
  present), Body, Sources (when any citations survived), then only the
  Pipeline Metrics line and the existing `_DISCLOSURE` text — omitting
  `_CLOSING_BLOCK` and `_SECTION_4_BODY` (the Gata/GitHub/Newsletter
  promotional content) entirely. The writer panel's prompts and section
  markers (`TITLE`/`EXECUTIVE_SUMMARY`/`BODY`/`COMMENT`/`NOTIFICATION`) are
  completely unchanged — `COMMENT` and `NOTIFICATION` are simply unused when
  `branded=False`.
- **FR-006**: When `branded=False`, only the assembled article text is used
  by the caller — the writer panel's `NOTIFICATION` output is still produced
  (same call) but discarded, never written to disk. A neutral research
  report has no LinkedIn-notification concept.
- **FR-007**: `core/bundle_writer.write_bundle` gains a new optional
  parameter `research_report: str | None = None`; when non-empty, it is
  written to `research_report.md` in the bundle directory. This is
  independent of the existing `linkedin_post` parameter — `run_pipeline`
  populates exactly one of the two per run (FR-003), never both.
- **FR-008**: When `research_only=True`, no image is ever written and
  `output_path` is never required to point at a real image location. Both
  CLI entry points build `output_path` for this mode as
  `output/research/{sanitize_path_segment(topic)}_{timestamp}.md`
  (`timestamp` formatted `%Y%m%d_%H%M%S`), passed to `run_pipeline`/
  `write_bundle` purely as the bundle-directory-naming key (`Path(output_path
  ).parent / Path(output_path).stem`, unchanged) — no file is ever written at
  `output_path` itself in this mode.
- **FR-009**: Both `pipeline.py` and `core/cli.py` gain a `--research-only`
  flag (`action="store_true"`, default `False`), passed through to
  `run_pipeline(research_only=...)`.
- **FR-010**: In `core/cli.py`, when `--research-only` is set, the
  per-audience loop is bypassed: only the first entry of
  `infer_audiences(args.topic)` (before `_ensure_uk`) is used to build a
  single `StrategyBrief`, and `run_pipeline` is invoked exactly once — never
  once per audience.
- **FR-011**: When `--research-only` and `--direct` are both supplied,
  `--direct` has no additional effect (Cultural Strategist is already
  skipped); this MUST be logged at INFO, never treated as an error — the
  same precedent as `--angle` without `--linkedin-post`.
- **FR-012**: Every skip decision under `research_only=True` MUST be logged
  at INFO, mirroring today's `"Direct mode — skipping Cultural Strategist"`
  precedent (e.g. `"Research-only mode — skipping Cultural Strategist,
  Satirist, Image Generator, Image Evaluator"`).

### Key Entities

No new entities — reuses the existing `EnrichedBrief`, `ResearchDigest`, and
`ResearchSource` types from Spec 042 unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given `research_only=True` and `generate_linkedin_post=False`
  (all panels mocked), the returned `RunTelemetry` contains zero entries
  named for Cultural Strategist, Satirist, Image Generator, or Image
  Evaluator.
- **SC-002**: Given `research_only=True` and `generate_linkedin_post=False`,
  the assembled report text contains no occurrence of `"Gata"`, the support
  email address, or the GitHub repository URL.
- **SC-003**: Given `research_only=True` and `generate_linkedin_post=True`,
  `bundle_writer.write_bundle` is called with `linkedin_post=(article_md,
  notification_txt)` and `research_report=None`.
- **SC-004**: Given `research_only=True` and `generate_linkedin_post=False`,
  `bundle_writer.write_bundle` is called with `research_report=article_md`
  and `linkedin_post=None`.
- **SC-005**: Given `research_only=True` on the `gata` CLI with an
  `infer_audiences` mock returning 3 audiences, the mocked `run_pipeline` is
  called exactly once.
- **SC-006**: A real, manually-run
  `python pipeline.py --topic "..." --audience "..." --language English \
  --tone neutral --research-only` produces `research_report.md` under
  `output/research/<slug>_<timestamp>/`, contains no `.png` or
  `prompt_card.txt` in that bundle, and reads as neutral/unbranded (manual
  verification during implementation, same discipline as Spec 042's SC-005).
- **SC-007**: `python -m pytest tests/` passes with every provider/SDK call
  mocked — zero real API calls during the automated suite.

## What does NOT change

- `agent_cultural_strategist.py`, `agent_satirist.py`,
  `agent_image_generator.py`, `agent_image_evaluator.py` are completely
  untouched — `research_only` simply never calls them.
- Existing `--linkedin-post` behaviour without `--research-only` is
  unchanged: same gate on a real cartoon concept, same branded output, same
  file names.
- Spec 042's research → angle-planning → writing `FairParallelPanel`
  internals, citation extraction/renumbering, and domain-classification
  cache (`source_domains.duckdb`) are unchanged — only the final assembly
  step gains a neutral/branded switch.
- RULE 12 (manual pipeline invocation to generate a specific image) is
  unaffected — `--research-only` is an additional mode; direct image
  generation remains fully available without it.

## Assumptions

- "Fully neutral, no branding" means omitting Gata-specific closing content
  (`_CLOSING_BLOCK`) and the tech-stack promo (`_SECTION_4_BODY`), plus using
  a neutral title fallback. The factual Pipeline Metrics line and the
  AI-authorship disclosure (`_DISCLOSURE`, already free of any Gata
  reference) are kept — they are informational, not promotional.
- On the `gata` CLI, "the first inferred audience" (before UK-ensure) is
  treated as the single most relevant context for the report's
  language/tone/target audience — an engineering default; there is currently
  no way for the operator to pick a specific audience for a research-only
  `gata` run.
- The neutral report never writes a notification/teaser file — that concept
  is LinkedIn-specific and does not apply to a generic research report.
