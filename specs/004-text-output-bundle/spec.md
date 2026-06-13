# Feature Specification: Text Output Bundle

**Feature Branch**: `004-text-output-bundle`
**Created**: 2026-05-10
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Conversation Logs (Priority: P1)

After the pipeline produces a cartoon, the operator can read a complete, human-readable record of every negotiation turn that took place — for both the cultural enrichment loop and the creative loop. The record covers every proposal, every critique, and the full reasoning behind each rejection and each approval.

**Why this priority**: Without this, the pipeline is a black box. The operator cannot audit quality, diagnose failures, or understand why a particular concept was chosen over others. This is the most fundamental transparency tool.

**Independent Test**: Run the pipeline for any community; verify two log files appear in the output bundle folder, each containing every proposer and reviewer turn with clear labels and the full text of each message.

**Acceptance Scenarios**:

1. **Given** a completed pipeline run, **When** the operator opens the Agent 0 log, **Then** every Framer proposal and every Resonator response is present in order, each labelled with iteration number, role, and verdict (approved / needs revision), including the full reasoning text.
2. **Given** a run where the B/C loop ran 3 iterations before approval, **When** the operator opens the B/C log, **Then** all 3 Satirist proposals and all 3 Critic responses appear, including the critiques that caused revisions and the final approval reason.
3. **Given** a run where the Final Say Protocol was triggered, **When** the operator opens the log, **Then** the log clearly marks the final iteration as Final Say and includes the last reviewer feedback that the proposer had to address.
4. **Given** a failed run (all models exhausted), **When** the operator checks the log, **Then** the log contains all turns up to the point of failure with a clear failure marker at the end.

---

### User Story 2 — In-Language Explanation HTML (Priority: P2)

After the pipeline produces a cartoon, an end user who does not immediately understand the joke can read a polished explanation in the same language as the cartoon. The explanation is suitable for publishing as a web page alongside the image.

**Why this priority**: The cartoon is the primary output; the explanation amplifies its reach. Without it, audience members who lack the specific cultural context are excluded. This directly affects publishability.

**Independent Test**: Run the pipeline for the Portuguese community; verify an HTML file is produced in Portuguese that explains the cartoon's premise, the satirical angle, and why it is funny — readable by a native speaker with no further context.

**Acceptance Scenarios**:

1. **Given** a completed pipeline run targeting Portuguese adults, **When** the operator opens the explanation HTML, **Then** all text is in Portuguese and the file explains the cartoon's satirical angle, the specific references used, and the punchline without assuming prior knowledge.
2. **Given** an explanation HTML, **When** opened in a browser, **Then** it renders as a valid, self-contained web page with legible structure (heading, body paragraphs, no broken markup).
3. **Given** a cartoon with multiple cultural references, **When** the explanation is generated, **Then** each reference is acknowledged and briefly contextualised for the target audience.

---

### User Story 3 — English Deep-Dive HTML (Priority: P3)

After the pipeline produces a cartoon targeting a non-English-speaking culture, the operator can read a detailed English-language explanation covering the news background, the cultural references, and why the joke lands for that specific audience — even when the operator has no prior knowledge of that culture.

**Why this priority**: Enables the operator to oversee and fine-tune the pipeline across cultures they do not personally understand (e.g. Korean, Chinese, Arabic). Secondary to the in-language explanation because it serves internal use rather than end users.

**Independent Test**: Run the pipeline for a non-English community (e.g. Portuguese adults); verify an English HTML file is produced that gives enough background for an English speaker with no Portuguese cultural knowledge to understand and evaluate the cartoon.

**Acceptance Scenarios**:

1. **Given** a cartoon targeting Portuguese adults, **When** the operator opens the English deep-dive HTML, **Then** the file explains in English: what the news event is, what cultural references were used and why they resonate, and what makes the angle satirically effective for that audience.
2. **Given** a cartoon where Agent 0 identified culturally specific references, **When** the English deep-dive is generated, **Then** each reference from the enriched brief is explained with enough background for a culturally uninformed English speaker.
3. **Given** a deep-dive HTML, **When** opened in a browser, **Then** it renders as a valid, self-contained web page.

---

### User Story 4 — Prompt Card (Priority: P4)

After the pipeline produces a cartoon, the operator can retrieve the exact text prompt that was sent to the image generator, in isolation, as a plain text file.

**Why this priority**: Enables prompt-level debugging and rerunning the image generation step independently without re-running the full pipeline. Lowest priority because it duplicates information available in the B/C log, but its standalone form is practically useful.

**Independent Test**: Run the pipeline; verify a plain text file exists in the bundle folder containing only the image prompt, identical to what was passed to the image generator.

**Acceptance Scenarios**:

1. **Given** a completed pipeline run, **When** the operator opens the prompt card, **Then** the file contains exactly the image prompt text — nothing else.
2. **Given** a prompt card, **When** its content is pasted directly into the image generation tool, **Then** it produces the same image as the pipeline did (within model variance).

---

### Edge Cases

- What happens when the pipeline fails before producing a concept (Agent 0 or B/C raises a terminal error)? The conversation log up to the point of failure must still be written; the HTML files and prompt card are not produced.
- What happens if the HTML generation step fails? The cartoon image and logs are preserved; the pipeline logs the failure but does not exit with an error code.
- What happens when the target language uses a non-Latin script (e.g. Korean, Arabic)? The in-language HTML must correctly declare the character encoding and render the script without corruption.
- What happens when the bundle folder already exists (rerun over the same output path)? Existing files are overwritten without error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: After every successful pipeline run, the system MUST create a bundle folder named identically to the output image file (without its extension), as a subfolder within the image's output directory.
- **FR-002**: The bundle folder MUST contain an Agent 0 conversation log covering every Framer–Resonator turn: iteration number, role, full proposal or response text, and verdict with reasoning.
- **FR-003**: The bundle folder MUST contain a B/C conversation log covering every Satirist–Critic turn: iteration number, role, full proposal or response text, and verdict with reasoning.
- **FR-004**: Both conversation logs MUST be human-readable plain text, formatted with clear section headers per iteration and explicit APPROVED / NEEDS REVISION markers.
- **FR-005**: The bundle folder MUST contain an HTML explanation file written in the cartoon's target language, suitable for publishing as a web page, explaining the joke, the satirical angle, and the cultural references to an end user.
- **FR-006**: The bundle folder MUST contain an English deep-dive HTML file explaining the news background, cultural references, and satirical logic in English, with enough detail for an operator unfamiliar with the target culture.
- **FR-007**: The bundle folder MUST contain a prompt card plain text file containing exactly the image prompt that was sent to the image generator.
- **FR-008**: The HTML files MUST be generated by agent-explainer, a dual-LLM agent using the same model infrastructure already present in the pipeline — no new external services.
- **FR-009**: agent-explainer MUST receive as input: the enriched brief, both conversation logs, and the final image prompt.
- **FR-010**: If the pipeline fails before producing a cartoon concept, the system MUST still write any conversation logs that were completed before the failure; HTML files and prompt card are skipped.
- **FR-011**: If HTML generation fails, the system MUST log the failure and continue — the cartoon image and logs must not be lost.
- **FR-012**: In-language HTML files MUST declare UTF-8 encoding and correctly render non-Latin scripts.
- **FR-013**: Rerunning the pipeline over the same output path MUST overwrite existing bundle files without error.

### Key Entities

- **Bundle folder**: Named `{image_filename_without_extension}`, located at `{image_output_directory}/{image_filename_without_extension}/`
- **Agent 0 conversation log**: Plain text file covering all Framer↔Resonator turns
- **B/C conversation log**: Plain text file covering all Satirist↔Critic turns
- **In-language explanation HTML**: Web-publishable HTML in the cartoon's target language
- **English deep-dive HTML**: Web-publishable HTML in English for the operator
- **Prompt card**: Plain text file containing only the image prompt

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every successful pipeline run produces a bundle folder containing all four file types without manual intervention.
- **SC-002**: Both conversation logs contain every turn that occurred during the run — zero turns are omitted.
- **SC-003**: The in-language HTML and English deep-dive HTML each render without errors in a standard browser.
- **SC-004**: A cultural outsider reading the English deep-dive for a non-English cartoon can describe the satirical angle and the key cultural references accurately without any other source — verifiable by the operator.
- **SC-005**: Pipeline failure before cartoon production results in partial bundle (logs only) within 5 seconds of failure — no additional delay.
- **SC-006**: HTML generation failure does not cause the pipeline to exit with an error code; the cartoon image is always the primary deliverable.

## Assumptions

- The conversation log content is captured by `DualPersonaLoop`, which already has access to all turns; no changes to how models are called are required to capture this data.
- agent-explainer uses existing Claude and Gemini models already configured in the pipeline — no new API keys or services.
- The HTML files are static (no JavaScript, no dynamic data fetching) — suitable for serving as plain files or embedding in a CMS.
- The prompt card is a verbatim copy of the image prompt string passed to agent-d; no reformatting is needed.
- Bundle folder creation is handled by the pipeline after agent-d completes (or after failure, if partial).
- The agent-explainer dual-LLM loop follows the same `<verdict>` tag protocol as Agent 0 and B/C.
