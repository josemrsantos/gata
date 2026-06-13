# Feature Specification: Stage 1 Core Loop

**Feature Branch**: `001-stage-1-core-loop`
**Created**: 2026-04-25
**Status**: Draft
**Input**: User description: "Stage 1 core loop: hardcoded news topic + hardcoded strategy brief → Agent B/C creative studio (Claude Satirist + Gemini Critic, up to 5 iterations) → Agent D image generation (Gemini) → saved cartoon_output.png"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - End-to-End Pipeline Run (Priority: P1)

A developer runs the pipeline with a hardcoded news topic and a hardcoded strategy brief (specifying target audience, output language, and tone) and, without any further interaction, receives a completed satirical cartoon image file saved to disk. The pipeline uses both inputs to guide all creative and generation steps automatically.

**Why this priority**: This is the entire value proposition of Stage 1 — proving the full pipeline works end-to-end from topic and brief to saved image. Everything else builds on this.

**Independent Test**: Can be tested by executing the pipeline script and verifying that `cartoon_output.png` exists and is a valid image file at the end of the run.

**Acceptance Scenarios**:

1. **Given** the pipeline is started with a hardcoded news topic and strategy brief, **When** the pipeline completes all stages, **Then** a file named `cartoon_output.png` exists on disk and is a valid image.
2. **Given** a valid news topic and strategy brief, **When** the creative loop completes, **Then** the generated image visually depicts a satirical scene that reflects the brief's specified audience, language, and tone, featuring Gata the calico cat.
3. **Given** the pipeline runs from start to finish, **When** no errors occur, **Then** the full run completes without any manual intervention required.

---

### User Story 2 - Iterative Creative Refinement (Priority: P2)

The creative loop between the Satirist Agent and the Critic Agent visibly iterates — generating a concept, receiving critique, and revising — up to 5 times before the best concept is passed to image generation. Both agents use the strategy brief throughout all iterations to ensure the satirical angle stays aligned with the intended audience, language, and tone.

**Why this priority**: The refinement loop is the creative quality mechanism. Without it, the pipeline degenerates to a single-shot generation with no quality control, and the brief has no opportunity to shape the output.

**Independent Test**: Can be tested by observing pipeline logs/output showing multiple iterations of concept generation and critique before image generation begins, with brief-alignment noted in each critique.

**Acceptance Scenarios**:

1. **Given** an initial concept does not meet the Critic Agent's quality threshold, **When** the loop is within 5 iterations, **Then** the Satirist Agent receives the critique and generates a revised concept that still conforms to the strategy brief.
2. **Given** the loop reaches 5 iterations without explicit approval, **When** iteration 5 completes, **Then** the pipeline proceeds to image generation using the final iteration's concept rather than halting.
3. **Given** the Critic Agent approves a concept before iteration 5, **When** approval is received, **Then** the loop exits early and image generation begins immediately with the approved concept.
4. **Given** a strategy brief specifying a particular output language, **When** the Satirist Agent generates any concept, **Then** all textual elements of the concept (captions, speech, descriptors) are in the specified language.

---

### User Story 3 - Predictable Output Location (Priority: P3)

After every pipeline run, the output image is always saved to the same known filename and location, making it easy to find and use downstream.

**Why this priority**: Consistent output paths are essential for integrating with downstream steps (sharing, reviewing, publishing) even in this early stage.

**Independent Test**: Run the pipeline twice consecutively and verify that `cartoon_output.png` is overwritten (not accumulated) and is always in the expected location.

**Acceptance Scenarios**:

1. **Given** a pipeline run completes successfully, **When** checking the output location, **Then** a file named `cartoon_output.png` exists at the project root or designated output directory.
2. **Given** a previous `cartoon_output.png` already exists, **When** the pipeline runs again, **Then** the existing file is replaced with the new output.

---

### Edge Cases

- What happens when the creative loop reaches 5 iterations without Critic approval? The pipeline MUST still proceed to image generation using the last concept produced rather than failing.
- What if image generation fails after a successful creative loop? The pipeline MUST surface a clear error and MUST NOT save a corrupted or partial image file.
- What if the hardcoded news topic is empty or blank? The pipeline MUST fail with a descriptive error before entering the creative loop.
- What if the strategy brief is missing one or more required fields (target audience, output language, or tone)? The pipeline MUST fail with a descriptive error identifying the missing field(s) before entering the creative loop.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST accept two hardcoded inputs: a news topic string and a strategy brief.
- **FR-002**: The strategy brief MUST define three fields: target audience (who the cartoon is made for), output language (the language of all textual content in the cartoon), and tone (the emotional or stylistic register, e.g., dry wit, absurdist, sharp satire).
- **FR-003**: The pipeline MUST validate that both inputs are present and that the strategy brief contains all three required fields before proceeding; missing or blank fields MUST cause the pipeline to halt with a descriptive error.
- **FR-004**: The Satirist Agent MUST generate a satirical cartoon concept informed by both the news topic and all three fields of the strategy brief, featuring Gata the calico cat interpreting geopolitics through feline priorities.
- **FR-005**: The Critic Agent MUST evaluate each cartoon concept against both the satirical quality standards and the strategy brief, providing structured feedback that identifies any deviation from the intended audience, language, or tone.
- **FR-006**: The pipeline MUST iterate between the Satirist Agent and Critic Agent up to a maximum of 5 refinement cycles per run.
- **FR-007**: The creative loop MUST exit early if the Critic Agent explicitly approves a concept before the 5-iteration limit is reached.
- **FR-008**: At iteration limit (5 cycles), the pipeline MUST proceed to image generation using the most recent concept rather than halting or erroring.
- **FR-009**: The Image Generation Agent MUST produce a cartoon image from the approved (or final) concept description.
- **FR-010**: The pipeline MUST save the generated image as `cartoon_output.png` to a consistent, known output location.
- **FR-011**: If image generation fails, the pipeline MUST report a clear error and MUST NOT write a partial or invalid image file.
- **FR-012**: The full pipeline MUST complete a run without requiring any human interaction after being triggered.

### Key Entities

- **News Topic**: The seed input for the pipeline — a short description of a current news event or geopolitical situation.
- **Strategy Brief**: The creative framing input — contains three fields: target audience (who the cartoon is for), output language (language of all textual cartoon content), and tone (stylistic register). Hardcoded for Stage 1.
- **Cartoon Concept**: A textual description of a satirical cartoon scene, including visual elements, Gata's pose or action, the satirical angle, and any in-cartoon text. Must reflect the strategy brief. Produced and refined by the creative loop.
- **Critique**: Structured feedback from the Critic Agent assessing the concept's satirical sharpness, coherence, alignment with the strategy brief, and suitability for image generation. Includes a quality verdict (approved / needs revision).
- **Cartoon Image**: The final visual output — a PNG image depicting the approved cartoon concept.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A complete pipeline run from hardcoded topic and strategy brief to saved `cartoon_output.png` completes without manual intervention in a single execution.
- **SC-002**: The creative loop always terminates within 5 iterations — it never runs indefinitely or exceeds the iteration cap.
- **SC-003**: The saved `cartoon_output.png` is a valid, viewable image file after every successful pipeline run.
- **SC-004**: The pipeline produces consistent, interpretable output for at least 3 different combinations of hardcoded news topic and strategy brief without code changes.
- **SC-005**: When the strategy brief specifies an output language, all textual content visible in the generated cartoon (captions, speech, labels) is in that language.
- **SC-006**: An observer unfamiliar with the news topic can identify the satirical angle and intended tone by viewing the output image alone, without reading the inputs.
- **SC-007**: Pipeline errors (e.g., failed image generation, blank topic, incomplete brief) produce descriptive messages that allow a developer to diagnose the failure without reading source code.

## Assumptions

- Both the news topic and strategy brief are hardcoded in the pipeline for Stage 1; dynamic topic fetching and runtime brief configuration are out of scope.
- A single successful end-to-end run is sufficient to validate Stage 1; no batch processing or scheduling is required.
- The Critic Agent uses a defined internal quality rubric (e.g., satirical relevance, visual clarity, Gata characterisation); the exact rubric is an implementation detail.
- `cartoon_output.png` is written to a fixed location (project root or designated output directory); no configurable output path is required for Stage 1.
- The pipeline is run locally by a developer; no web interface, API endpoint, or deployment infrastructure is required.
- Only one pipeline instance runs at a time; concurrent execution is out of scope.
