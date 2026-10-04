# Feature Specification: Single-audience default for gata

**Spec**: `055-single-audience-default`
**Created**: 2026-10-04
**Status**: Draft

## Problem

Running `gata "<topic>"` today makes the system guess several audiences for the
topic and then always adds a "UK public" one, so a typical run produces about two
cartoons. Each audience is a full paid pipeline run (strategy, writing, image,
evaluation), so the default doubles cost and time, and there is no way to ask for
"just one" or to pick which audiences to generate for.

## Goal

When this feature is done, `gata "<topic>"` produces one cartoon, for UK software
engineers, by default; an operator can name other audiences with a repeatable
`--audience` option; and generating for several audiences remains possible on
request.

## Clarifications

### Session 2026-10-04

- Q: What can `--audience` take? → A: community names from `communities.yaml` only
- Q: Does `--audience` replace the default or add to it, and does the old behaviour stay available? → A: it replaces the default; a separate option (`--infer-audiences`) restores the old topic-guessed behaviour
- Q: Where does the default audience come from? → A: a built-in copy inside `gata`, so the default works from any folder
- Q: Should a named audience's panel count and layout apply in `gata`? (FR-003) → A: no; layout stays automatic for every audience, as today
- Q: Which audience does `--research-only` use? (FR-008) → A: the first selected audience (the default, or the first `--audience` value); extra values are ignored with a visible note

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A default run produces one cartoon (Priority: P1)

An operator runs `gata "some topic"` with no audience option and gets one cartoon
for the UK software-engineer audience, paying for one pipeline run.

**Why this priority**: This is the cost and time saving the feature exists for.

**Independent Test**: `gata "some topic"` writes exactly one image,
`<topic-folder>/uk-tech-engineers.png`, and the terminal shows a single `[1/1]`
audience line.

**Acceptance Scenarios**:

1. **Given** no audience option, **When** the operator runs `gata "topic"`,
   **Then** exactly one pipeline run happens and exactly one image is produced.
2. **Given** no audience option, **When** the run starts, **Then** no
   audience-guessing step runs and no extra "UK public" audience is added.
3. **Given** a default run, **When** it finishes, **Then** the cost summary shows
   one audience's time and cost as the total.

---

### User Story 2 — Choose the audiences yourself (Priority: P2)

An operator runs `gata "topic" --audience A --audience B` and gets one cartoon per
named audience, in the order given, in the same output folder.

**Why this priority**: It keeps multi-audience runs available and lets the
operator target a specific audience instead of the default.

**Independent Test**: `gata "topic" --audience <A> --audience <B>` produces
exactly two images, one per audience, and progress lines `[1/2]` and `[2/2]`.

**Acceptance Scenarios**:

1. **Given** two distinct valid `--audience` values, **When** the run completes,
   **Then** two images exist, one per audience, in the order given.
2. **Given** an `--audience` value that matches no audience in `communities.yaml`, **When** the
   command starts, **Then** it stops with a clear message naming the value and
   listing the valid choices, before any paid call is made.
3. **Given** the same audience given twice, **When** the run starts, **Then** it
   is generated once.

---

### User Story 3 — Other options keep working per audience (Priority: P3)

An operator combines the audience selection with the existing options
(`--direct`, `--html`, `--no-title`, `--linkedin-post`, `--angle`, `--verbose`,
`--research-only`) and each behaves as it does today.

**Why this priority**: The change must not break existing use.

**Independent Test**: `gata "topic" --no-title --html` still produces one image
without a title banner, plus its HTML for the single default audience.

**Acceptance Scenarios**:

1. **Given** `--research-only`, **When** it runs, **Then** it runs once, for the
   first selected audience (the default when none is named).
2. **Given** several `--audience` values and `--no-title`, **When** the run
   completes, **Then** every image is produced without a title banner.

---

### User Story 4 — Ask for the old behaviour (Priority: P3)

An operator who wants topic-guessed audiences runs `gata "topic" --infer-audiences`
and gets exactly today's behaviour.

**Why this priority**: Nothing is lost for anyone who relied on the guessing.

**Independent Test**: `gata "topic" --infer-audiences` produces the same audiences
it produced before this feature (guessed audiences plus UK when needed).

**Acceptance Scenarios**:

1. **Given** `--infer-audiences`, **When** the run starts, **Then** audiences are
   guessed for the topic and "UK public" is added if none is UK.
2. **Given** `--infer-audiences` and `--research-only`, **When** it runs, **Then**
   it runs once using the first guessed audience, as today.

---

### Edge Cases

- No audience option and no `communities.yaml` in the current folder → the default
  run still works, because the default is built into `gata`.
- `--audience` names an audience but `communities.yaml` is absent → a clear error
  saying the file was not found (the built-in default's own name still works).
- `--infer-audiences` together with `--audience` → rejected with a clear message
  (they are two different ways of choosing audiences).
- An audience's own settings include a panel count and layout that `gata` does not
  use today → they stay ignored; layout remains chosen automatically (FR-003a).
- One audience in a multi-audience run fails → the others still run, and the
  summary reports the partial result, as it does today.
- `--audience` given with `--research-only` and several values → only the first is
  used for the report; the rest are ignored with a visible note.
- An empty `--audience ""` → rejected like an unknown audience.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: With no audience option, `gata` MUST run exactly once, for the
  `uk-tech-engineers` audience (British software engineers and developers; English;
  dry British wit).
- **FR-002**: A default run MUST NOT run the audience-guessing step and MUST NOT
  add a "UK public" audience.
- **FR-003**: `gata` MUST accept `--audience` any number of times; each value
  selects one audience, and the run produces one cartoon per distinct selected
  audience, in the order given, in the same output folder, named after the audience.
- **FR-003a**: Every audience, default or named, MUST keep `gata`'s automatic layout
  choice; a community's `panels` and `layout` settings are ignored by `gata`.
- **FR-004**: `--audience` MUST accept only the names of audiences defined in
  `communities.yaml` (read from the current folder); free-text descriptions are not
  accepted.
- **FR-005**: When `--audience` is given, it replaces the default: only the named
  audiences are generated. A separate option (`--infer-audiences`)
  MUST restore today's behaviour exactly — audiences guessed for the topic, with
  "UK public" always added when none of them is UK.
- **FR-006**: The default audience's definition MUST be built into `gata`, so a
  default run works from any folder without `communities.yaml`. The built-in values
  MUST match the `uk-tech-engineers` entry in `communities.yaml`, and a test MUST
  fail if they drift apart.
- **FR-007**: An unknown, empty or unusable `--audience` value MUST stop the
  command with a message that names the value and lists the valid choices, before
  any paid call. If `communities.yaml` is absent, the only valid name is the
  built-in default's own name (`uk-tech-engineers`), and the message says the file
  was not found.
- **FR-008**: `--research-only` MUST keep running once, using the first selected
  audience (the default audience when none is named, otherwise the first
  `--audience` value); any further values are ignored and a visible note says so.
- **FR-009**: `--direct`, `--html`, `--no-title`, `--linkedin-post`, `--angle` and
  `--verbose` MUST apply to every selected audience exactly as they do today.
- **FR-010**: Progress and cost output MUST show `[i/N]` per audience, and the
  cost summary MUST total all selected audiences; a single audience shows one total.
- **FR-011**: `gata --help` MUST describe the default audience, `--audience` and
  `--infer-audiences`.
- **FR-012**: Existing tests that assume the guessed-audience behaviour MUST be
  updated so the suite passes with zero failures; `README.md`,
  `docs/architecture.md` and `CHANGELOG.md` MUST be updated (RULE 17), the version
  bumped (RULE 15), and this item removed from `TODO.md` in the same PR (RULE 19).

### Key Entities

- **Audience**: who a cartoon is for — a name used for the file, a description, an
  output language and a tone.
- **Audience selection**: the ordered list of distinct audiences a run will
  generate for; one default audience when the operator names none.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A default run performs 1 pipeline run and writes 1 image (today:
  about 2 pipeline runs plus an audience-guessing call).
- **SC-002**: A default run makes 0 audience-guessing calls.
- **SC-003**: With N distinct valid `--audience` values, exactly N images are
  produced, in the order given.
- **SC-004**: An invalid `--audience` value is rejected with no API call made.
- **SC-005**: The test suite passes with 0 failures and `ruff check .` exits 0.
- **SC-006**: `gata --help` states the default audience, `--audience` and
  `--infer-audiences`.
- **SC-007**: `--infer-audiences` reproduces today's audience selection (same guessed
  audiences, same "UK public" rule).
- **SC-008**: `--research-only` produces exactly 1 report, for the first selected
  audience.

## What does NOT change

- `pipeline.py` and its own `--community` mode (the other entry point).
- The pipeline stages, agents, protocols and the output folder layout
  (`<topic-folder>/<audience-name>.png`).
- Which models are used (spec 054) and their cost reporting.
- `communities.yaml` itself: no audience is added, removed or edited by this feature.
- The existing options `--direct`, `--html`, `--no-title`, `--linkedin-post`,
  `--angle`, `--research-only` and `--verbose` themselves.
- Layout selection: `gata` keeps choosing the layout automatically for every
  audience; panel and layout settings in `communities.yaml` stay unused by `gata`.

## Assumptions

- This is a new Flow-Forward spec (RULE 18), confirmed by the project lead; it
  evolves Specs 008, 015 and possibly 010 without amending them.
- **Supersedes, for default runs only**: Spec 010's rule that a UK audience is always
  present, and Spec 015's "main audience plus UK" default. Both still describe the
  behaviour under `--infer-audiences`. Their own documents are left unchanged
  (historical record); the README and architecture doc, which describe the current
  behaviour, are updated (FR-012).
- The next stage is numbered 055, the next free number after 054.
- The default audience's fields used by `gata` are its description, language and
  tone, as defined for `uk-tech-engineers` today.
- The audience-guessing function stays in the code and is reached through
  `--infer-audiences` (FR-005).
- The built-in default also answers to its own name `uk-tech-engineers` when
  `communities.yaml` is absent (proposed; see FR-007).
- When `communities.yaml` is present and the operator names `uk-tech-engineers`
  explicitly, the file's entry is used; the built-in copy only serves the default
  and the file-missing case.
