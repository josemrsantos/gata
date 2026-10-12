# Feature Specification: Image-prompt-only mode

**Spec**: `056-image-prompt-only`
**Created**: 2026-10-12
**Status**: Draft
**Model**: Flow-Forward (new spec; not an amendment to Spec 004 — decided in TODO.md, RULE 18)

## Problem

Making the cartoon image is the slowest, most expensive and least reliable step of
a run. An operator who wants to see (or fix) the cartoon idea, or who already pays
for a monthly Gemini plan, cannot stop before that step: every run either pays for
image generation or does not run at all.

It is also impossible today to see exactly what the image model is asked to draw.
The saved `prompt_card.txt` is not the real request: for multi-panel cartoons it
holds the Satirist's concept text, while the image model receives a separately
assembled request with extra character and style sections; for a single-panel
cartoon whose concept could not be read, the raw, unparsed text is sent as-is. The
title banner, the exact picture size and the final crop are applied afterwards and
appear nowhere in any saved file.

A real incident shows the cost of this blind spot: a concept that failed to parse
fell back to a request with no description of Gata, so the image showed a human
instead of the cat, was rejected three times and was shipped anyway — three paid
image attempts on a request that a person would have spotted as broken in seconds.

## Goal

When this feature is done, an operator can run any `gata` or `pipeline.py` run with
`--image-prompt-only`: all text stages run and the text bundle is produced as
normal, but no image is created. Instead, for each cartoon the operator gets a file
containing the complete request to paste into Gemini by hand, plus a message saying
that no image was generated and where the file is.

## Clarifications

### Session 2026-10-12

- Q: Where does the prompt go? → A: a new file in each audience's bundle folder (`image_prompt.txt`); `prompt_card.txt` is not reused or replaced
- Q: Is `prompt_card.txt` also corrected in this spec? → A: no; it stays exactly as today, in normal and prompt-only runs
- Q: What do the Image Evaluator and its retry loop do with no image? → A: skipped entirely (default, confirmed with the above)
- Q: What does the header say for `--linkedin-post`? → A: 1200x644 and the matching aspect ratio (default, confirmed with the above)
- Q: What does the flag do with `--research-only`? → A: nothing; the operator is told (default, confirmed with the above)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Get the Gemini request without paying for an image (Priority: P1)

An operator runs `gata "topic" --image-prompt-only` and ends up with the complete
text to give to Gemini, having paid only for the text stages.

**Why this priority**: This is the cost saving and manual workflow the feature
exists for.

**Independent Test**: Run `gata "topic" --image-prompt-only`; no image file and no
image-model call result exist afterwards, a prompt file exists, and the terminal
names its location.

**Acceptance Scenarios**:

1. **Given** `--image-prompt-only`, **When** the run finishes, **Then** no cartoon
   image is created and no image-generation cost appears in the cost summary.
2. **Given** `--image-prompt-only`, **When** the run finishes, **Then** a prompt
   file exists for the cartoon and the terminal prints that no image was
   auto-generated, that it must be generated manually by giving that file to
   Gemini, and the file's location.
3. **Given** `--image-prompt-only`, **When** the run finishes, **Then** every other
   output of a normal run (logs, prompt card, explanation, telemetry, summary) is
   still produced, except those that need the finished image; the prompt card is
   written exactly as in a normal run.
4. **Given** the same topic and settings run without the flag, **Then** behaviour
   is exactly as before this feature.

---

### User Story 2 — The file is exactly what Gemini would have received (Priority: P1)

An operator opens the prompt file and can trust it is the real request, so that
pasting it into Gemini gives the same drawing instructions the automatic run would
have used.

**Why this priority**: A file that differs from the real request defeats the
purpose (inspecting and manually reproducing the image).

**Independent Test**: For one fixed cartoon concept, the text in the prompt file is
identical to the text the normal run sends to the image model.

**Acceptance Scenarios**:

1. **Given** a multi-panel cartoon, **When** the file is written, **Then** it
   contains the full assembled request (panel scenes, captions, Gata description
   and visual style), not just the concept text.
2. **Given** a single-panel cartoon, including one produced by the fallback when
   the concept could not be read, **When** the file is written, **Then** it
   contains exactly the text the normal run would send, so a missing Gata
   description is visible to the operator.
3. **Given** a request that is sent in normal runs, **When** the normal run and the
   prompt-only run are compared, **Then** both are built by the same logic, so
   they cannot drift apart.

---

### User Story 3 — Know the settings that are not in the text (Priority: P2)

An operator pasting the request into Gemini is told what else the automatic run
would have applied, so the manual result can be finished correctly.

**Why this priority**: Picture size, the title banner and the final crop are
applied outside the request text; without a note the manual result will not match.

**Independent Test**: The prompt file starts with a short header stating the
target picture shape/size (when one is set), the cartoon title, and that the title
banner and final crop are not applied by hand.

**Acceptance Scenarios**:

1. **Given** a cartoon with a fixed size (for example the LinkedIn cover with
   `--linkedin-post`), **When** the file is written, **Then** the header states the
   exact size (1200x644) and the matching aspect ratio.
2. **Given** a cartoon with no fixed size, **When** the file is written, **Then**
   the header says no size is pinned.
3. **Given** any cartoon, **When** the file is written, **Then** the header gives
   the title and says the banner and crop are not part of the request, and the
   header is clearly separated from the text to paste.

---

### User Story 4 — Several audiences give several files (Priority: P2)

An operator runs `gata "topic" --audience A --audience B --image-prompt-only` and
gets one prompt file per audience, with each location printed.

**Why this priority**: Multi-audience runs exist; the flag must not break or hide
any of them.

**Independent Test**: With two audiences, two prompt files exist (one per audience
folder) and two locations are printed.

**Acceptance Scenarios**:

1. **Given** two audiences, **When** the run finishes, **Then** two prompt files
   exist, each in its own audience's output folder, and each location is printed.
2. **Given** one audience's text stages fail, **When** the run finishes, **Then**
   the other audience's file is still produced and the failure is reported as
   today.

---

### User Story 5 — Works from both entry points and with research options (Priority: P3)

The flag behaves the same on `pipeline.py` and on `gata`, and combines sensibly
with `--linkedin-post`, `--direct`, `--html`, `--no-title`, `--panels` and
`--layout`.

**Why this priority**: Consistency across the two entry points; combinations are
used in real runs (the incident above used `--linkedin-post`).

**Independent Test**: The same topic with the flag via `pipeline.py` and via
`gata` yields an equivalent prompt file and message.

**Acceptance Scenarios**:

1. **Given** `--image-prompt-only --linkedin-post`, **When** the run finishes,
   **Then** the LinkedIn text outputs are produced as normal and the prompt file
   header states the 1200x644 cover size.
2. **Given** `--image-prompt-only --research-only`, **When** the command starts,
   **Then** the flag has no effect (there is no image) and the operator is told so.

---

### Edge Cases

- The Image Evaluator and its regenerate loop have no image to judge, so they are
  skipped entirely and no evaluator cost is incurred.
- Outputs that require the finished image (for example the HTML page showing the
  image) are skipped or noted, and a skipped output is said so rather than failing.
- The prompt file already exists from an earlier run in the same folder: it is
  overwritten, as other bundle files are today.
- The output folder cannot be written: an error is logged for the file, no location
  message is printed for it, and the rest of the run completes, exactly as for every
  other bundle file today.
- The concept could not be read and the fallback request is used: the file is still
  written (the point is to make that visible), and a visible warning appears.
- `--no-title`: the header says no title banner is applied.
- The new flag is combined with no other flag: all defaults apply.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Both `gata` and `pipeline.py` MUST accept `--image-prompt-only`; when
  absent, behaviour MUST be unchanged.
- **FR-002**: With the flag, the system MUST run every stage of a normal run except
  creating the image, and MUST NOT call the image model.
- **FR-003**: With the flag, the system MUST write, for each cartoon, a prompt file
  containing the complete request that a normal run would send to the image model.
- **FR-004**: The request in the file MUST be produced by the same logic the normal
  run uses to build what it sends, so the two cannot differ.
- **FR-005**: The file MUST begin with a header, clearly separated from the request
  text, stating the picture size/aspect ratio (or that none is pinned), the cartoon
  title, and that the title banner and final crop are not applied.
- **FR-006**: The system MUST print, per prompt file, a message that no image was
  auto-generated, that it must be generated manually using the file as Gemini
  input, and the file's location.
- **FR-007**: For several audiences, the system MUST write one prompt file per
  audience in that audience's own output folder and print each location.
- **FR-008**: The Image Evaluator and its regenerate loop MUST NOT run when no
  image is created.
- **FR-009**: Every other normal output (logs, prompt card, explanation, telemetry,
  summary, LinkedIn outputs) MUST still be produced, except outputs that require
  the finished image, which MUST be skipped with a visible note.
- **FR-010**: The cost summary MUST show no image-generation or evaluator cost for
  a prompt-only run.
- **FR-011**: With `--research-only`, the flag MUST have no effect and the operator
  MUST be told.
- **FR-012**: With `--linkedin-post` on a cartoon pinned to the LinkedIn cover size,
  the header MUST state 1200x644.
- **FR-013**: When the request is the fallback built from an unreadable concept,
  the system MUST still write the file and MUST show a visible warning that the
  concept was not understood. The Satirist's existing "verdict parse failed" warning
  satisfies this; in addition, a request that lacks the verbatim Gata description
  MUST trigger its own visible warning.
- **FR-014**: The prompt file MUST be a new file named `image_prompt.txt` in each
  audience's bundle folder; it MUST NOT replace or reuse `prompt_card.txt`.
- **FR-015**: `prompt_card.txt` MUST be unchanged by this feature, in normal and
  prompt-only runs.

### Key Entities

- **Image request**: the complete text a normal run sends to the image model for
  one cartoon.
- **Prompt file**: a saved copy of the image request, with a manual-use header.
- **Manual-use header**: size/aspect ratio, title, and the notes that banner and
  crop are not applied.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A prompt-only run creates zero images and zero image-model charges;
  its cost is at most the cost of the text stages.
- **SC-002**: For a fixed concept, the request text in the prompt file is
  character-for-character identical to what a normal run sends.
- **SC-003**: Every prompt-only cartoon yields exactly one prompt file and one
  printed location.
- **SC-004**: An operator can paste the prompt file into Gemini without editing
  and get a drawing that follows the same instructions as an automatic run.
- **SC-005**: A request missing the Gata description (as in the incident) is
  visible to the operator in the file without any extra tooling.
- **SC-006**: Runs without the flag behave as before this feature: the same files
  are produced, and for a fixed concept the request sent to the image model is
  unchanged.

## What does NOT change

- Which stages run, their order, their models and costs, other than image
  generation and evaluation being skipped under the flag.
- Image generation, the title banner, the crop and evaluation in normal runs.
- The text bundle contents, except as listed in FR-009, and `prompt_card.txt`
  itself (FR-015).
- The existing `--research-only`, `--linkedin-post`, `--direct`, `--html`,
  `--no-title`, `--panels`, `--layout`, `--audience` and `--verbose` flags.
- Fixing the unreadable-concept fallback itself (missing Gata description,
  truncated concept text) — this spec only makes it visible.

## Assumptions

- The new file is added to each audience's existing bundle folder (FR-014).
- `prompt_card.txt` stays misleading for multi-panel cartoons; correcting it is
  left to a possible later spec.
- A pasted request alone is enough for Gemini; the operator attaches nothing else.
- The title banner and crop are applied by the operator (or skipped) when working
  manually; this spec does not recreate them.
- Image-dependent outputs are limited to those that cannot exist without the image.
- The flag name is `--image-prompt-only` on both entry points.
