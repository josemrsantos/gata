# Feature Specification: Tag-free, JSON-free panel responses

**Spec**: `058-tag-free-panel-responses`
**Created**: 2026-10-27
**Status**: Draft
**Model**: Flow-Forward (new spec; confirmed by the developer 2026-10-27 per RULE 18). Specs 052 and 057
stay as the historical record of the tolerant fallbacks. **Branch**: `058-tag-free-panel-responses`
**Source**: top item of `TODO.md` ("Tag-free, JSON-free panel responses")

## Clarifications

### Session 2026-10-27

- Q: Which missing Satirist labels make a reply unusable (retry) and which fall back to a default? → A:
  `PANEL n` blocks with `SCENE` are required, as is `BEAT` when there are 2+ panels; a missing `TITLE`
  falls back to the topic and a missing `CAPTION` to empty; every fallback is logged.
- Q: What should the single retry message say now that tags are gone? → A: Each agent supplies its own
  short format reminder (Satirist lists the required labels, aggregator asks for a `PICK: N` line, Domain
  Classification asks for one line per domain); agents whose reply is taken whole are retried only for an
  empty reply.
- Q: How long is the reply excerpt in a parse-failure log line? → A: 400 characters from the start of
  the reply.

## Problem

Panel agents are told to wrap their answer in `<verdict>…</verdict>` tags and, for the Satirist, to
return valid JSON. Models routinely ignore one or both instructions. A 2026-10-27 run logged repeated
"missing closing </verdict> tag" warnings (Claude, Grok) and a Gemini 2.5 Flash reply of bare fenced JSON
with no tags, which forced a retry. Specs 052 and 057 made the parser forgiving, but the prompt still
invites the failure, so each occurrence costs a retry, a lost panelist or a noisy warning. A model that
drops XML tags cannot be trusted to return valid JSON either. Today's warnings also carry no provider or
model, so a failure cannot be traced to a panelist.

## Goal

Panelists and aggregators answer in plain text that does not depend on tags or JSON: panel replies are the
whole reply, the aggregator uses a `PICK: N` line, and structured agents (Satirist, LinkedIn Domain
Classification) use simple `LABEL: value` lines that the code parses tolerantly. Format compliance no
longer decides whether a panelist's work is usable, and every parse failure or fallback is logged with
enough context (agent, round, provider, model, failed field, excerpt) to trace it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A reply that ignores the old format is still used (Priority: P1)

The operator runs `gata` or `pipeline.py`. A panelist answers with no tags, an unclosed tag, or a fenced
block. The panelist's work is used as-is and the run continues with the full panel, without a retry.

**Why this priority**: it removes the failure that drops panelists and spends extra calls.

**Independent Test**: `python -m pytest tests -k tag_free` (fixtures are the 2026-10-27 unclosed
`<verdict>` reply and the bare fenced Satirist JSON reply).

**Acceptance Scenarios**:

1. **Given** a panel reply with no wrapper, **When** the panel collects it, **Then** the whole reply is the
   panelist's answer and no warning is logged.
2. **Given** a reply that still uses `<verdict>` tags (closed or unclosed), **When** collected, **Then**
   the tag content is used (Spec 052/057 behaviour is kept as a safety net).
3. **Given** the aggregator reply contains `PICK: 2` on its own line followed by the chosen answer,
   **When** parsed, **Then** concept 2 is recorded as the pick and the rest of the reply is the verdict.

---

### User Story 2 — The Satirist returns `LABEL: value` text (Priority: P1)

The Satirist panel and aggregator produce `PANELS`, `LAYOUT`, `TITLE` and repeated `PANEL n` blocks with
`SCENE`, `CAPTION`, `BEAT`. The cartoon is built from them exactly as before.

**Why this priority**: the Satirist is the agent with the JSON-vs-tags conflict and drives image quality.

**Independent Test**: `python -m pytest tests -k satirist_labels`.

**Acceptance Scenarios**:

1. **Given** a well-formed labelled reply, **When** parsed, **Then** the cartoon concept is identical to the
   one produced from equivalent JSON today.
2. **Given** label drift (`Scene 1:`, `**CAPTION**:`, `## Panel 1`), markdown emphasis or a surrounding
   code fence, **When** parsed, **Then** the reply is still understood.
3. **Given** a missing or unrecognised `LAYOUT`, **When** parsed, **Then** the CLI `--layout` value is used,
   or auto layout if none was given, and the fallback is logged.
4. **Given** a reply with no `PANEL n` block, a panel with no `SCENE`, or (with 2+ panels) an empty
   `BEAT`, **When** parsed, **Then** the reply is unusable and triggers the existing single retry.
5. **Given** a missing `TITLE` or `CAPTION`, **When** parsed, **Then** the title falls back to the topic
   and the caption to empty, and each fallback is logged.

---

### User Story 3 — Parse failures can be traced (Priority: P1)

The operator reads `run.log` after a run and can see which panelist produced an unusable or defaulted
reply, why, and whether it was a format problem or a truncated reply.

**Why this priority**: today's warnings cannot be attributed to a panelist or provider.

**Independent Test**: `python -m pytest tests -k parse_failure_log`.

**Acceptance Scenarios**:

1. **Given** any parse failure or fallback, **When** it occurs, **Then** a WARNING (persisted to `run.log`
   per Spec 050) states the agent/panel (e.g. `Satirist/Co-Satirist`), the round, the provider and model,
   the missing or malformed field and the default applied, and a short excerpt of the reply.
2. **Given** a provider that exposes a stop reason or output length, **When** a parse failure is logged,
   **Then** that information is included so truncation and format-ignoring can be told apart.

---

### User Story 4 — LinkedIn Domain Classification as plain lines (Priority: P2)

Domain classification replies are one line per domain, e.g. `nytimes.com: paywalled, high`.

**Why this priority**: it is the remaining structured reply that depends on JSON.

**Independent Test**: `python -m pytest tests -k domain_classification`.

**Acceptance Scenarios**:

1. **Given** lines in any order of `paywalled`/`free` and `high`/`low`, with bullets, extra spaces or mixed
   case, **When** parsed, **Then** each domain gets the right classification.
2. **Given** a domain with no readable line, **When** parsed, **Then** today's default is applied and
   logged with the domain named.

---

### Edge Cases

- Reply contains both a `<verdict>` wrapper and labels → the wrapper content is unwrapped first, then parsed.
- Reply is truncated mid-block → parsed as far as possible; missing required fields follow the rules
  above, and the log says the reply was cut off when the provider reports it.
- Aggregator reply has no `PICK:` line → the pick is recorded as unknown (as today) and the whole reply is
  the verdict.
- Empty reply → unusable; one retry, then the panelist is dropped as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Panel agents' prompts MUST NOT ask for `<verdict>` tags or JSON; panel replies (Cultural
  Strategist, Explainer, Engagement Image, LinkedIn Angle Planning/Writing) are taken whole.
- **FR-002**: The aggregator prompt MUST ask for `PICK: N` on its own line followed by the chosen answer.
- **FR-003**: The Satirist prompt MUST ask for `LABEL: value` lines (`PANELS`, `LAYOUT`, `TITLE`, repeated
  `PANEL n` with `SCENE`, `CAPTION`, `BEAT`); the panel count MUST be derived from the number of
  `PANEL n` blocks.
- **FR-004**: The LinkedIn Domain Classification prompt MUST ask for one line per domain; the parser MUST
  accept `paywalled`/`free` and `high`/`low` in any order, ignoring case, bullets and extra spaces, and
  an absent domain MUST get today's default.
- **FR-005**: Parsers MUST tolerate label drift, markdown emphasis and a surrounding code fence.
- **FR-006**: A Satirist reply with no `PANEL n` block, a panel without `SCENE`, or (with 2+ panels) an
  empty `BEAT` MUST be treated as unusable and trigger the existing single retry; a missing `TITLE` MUST
  fall back to the topic, a missing `CAPTION` to empty, and a missing/odd `LAYOUT` to the CLI value, else
  auto layout; each fallback MUST be logged per FR-007.
- **FR-007**: Every parse failure or fallback MUST log a WARNING naming the agent/panel, the round, the
  provider and model, what failed and the default applied, and the first 400 characters of the reply as
  an excerpt. The caller, which knows
  the provider, MUST supply that context to the parser.
- **FR-008**: Where a provider exposes it, the log MUST include stop reason or output length so truncation
  can be distinguished from format-ignoring.
- **FR-008a**: The single retry's reminder MUST be supplied by each agent and name that agent's own
  format; agents whose reply is taken whole MUST be retried only when the reply is empty. An unusable
  aggregator reply MUST get the same single retry (a new behaviour: today the aggregator is not retried).
- **FR-009**: The Spec 052/057 `<verdict>`/bare-JSON fallbacks MUST be kept so old-format replies still
  parse; the one-retry behaviour for unusable replies is unchanged.
- **FR-010**: Output for the same cartoon concept, article and notification content MUST be unchanged
  apart from where it came from (downstream files, telemetry and cost reporting are unaffected).

### Key Entities

- **Panel reply**: the raw text a panelist returns; now the answer itself, with optional legacy tags.
- **Labelled reply**: a reply made of `LABEL: value` lines, value running until the next label.
- **Parse-failure record**: the WARNING line with agent, round, provider/model, failed field, default
  applied and excerpt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Replaying the 2026-10-27 unclosed-`<verdict>` and bare-fenced-JSON replies produces a usable
  panelist result with no retry.
- **SC-002**: 100% of parse failures/fallbacks in tests produce a log line containing agent, round,
  provider, model, failed field and an excerpt.
- **SC-003**: Label-drift fixtures (`Scene 1:`, `**CAPTION**:`, `## Panel 1`, fenced reply) parse to the
  same concept as the canonical form.
- **SC-004**: All existing tests pass unchanged except those that assert the old prompt wording.
- **SC-005**: A live run of `gata` on one topic completes with no "missing closing </verdict> tag" warning.

## What does NOT change

- Panel structure, rounds, provider fallback chains, timeouts and cost/telemetry reporting.
- `DualPersonaLoop`'s `APPROVED` / `NEEDS REVISION` reviewer verdict (already plain text; revisit only if a
  failure is observed).
- Image generation, evaluation and the cartoon/article output files.
- `TODO.md` is not edited by this spec; removing the superseded "Satirist output-format wording" item
  (RULE 19) needs the developer's approval at gate G3 (RULE 8).

## Assumptions

- Decisions taken here instead of left open: keep the 052/057 fallbacks (FR-009); leave the
  `DualPersonaLoop` reviewer verdict alone; this spec supersedes the "Satirist output-format wording"
  TODO item, which is removed in the same PR with approval.
- Providers differ in whether they expose a stop reason; FR-008 is best effort.
- Moving every prompt to plain text is judged cheaper than the retries it removes; no extra calls are added.
