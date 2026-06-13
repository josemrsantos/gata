# Feature Specification: Agent 0 — Cultural Strategist

**Feature Branch**: `003-stage-3-cultural-strategist`
**Created**: 2026-05-08
**Status**: Draft
**Input**: User description: "Stage 3 — Agent 0 Cultural Strategist: add a dual-persona strategy layer that runs before the B/C creative loop. Two LLM personas — The Framer (Claude Sonnet) and The Resonator (Gemini 1.5 Pro) — negotiate iteratively (up to 5 rounds) to produce a strategy brief from a topic and community context. The brief contains: target audience, output language, cultural angle, tone, and culturally-loaded references. The existing StrategyBrief from communities.yaml becomes the seed input to Agent 0, which enriches and contextualises it before passing downstream. The same dual-persona iteration rules already used in the B/C loop apply here."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Pipeline Runs with an Enriched Strategy Brief (Priority: P1)

An operator runs the pipeline for any community or topic. Before any creative work begins, Agent 0 negotiates a strategy brief that goes beyond the seed config — adding a cultural angle and culturally-loaded references specific to the topic and audience. The enriched brief then drives the B/C creative loop.

**Why this priority**: This is the core value of Stage 3. Without Agent 0 producing an enriched brief, the creative loop has no cultural context beyond the seed config. Everything else in this stage depends on Agent 0 running and producing a usable output.

**Independent Test**: Run the pipeline for any community; verify the log shows The Framer's proposal and The Resonator's response for at least one iteration, and that the enriched brief (including cultural angle and references) is logged before the B/C loop starts.

**Acceptance Scenarios**:

1. **Given** a valid community and topic, **When** the pipeline runs, **Then** Agent 0 executes before the B/C creative loop and produces an enriched brief containing target audience, output language, cultural angle, tone, and at least one culturally-loaded reference.
2. **Given** an enriched brief from Agent 0, **When** the B/C creative loop runs, **Then** it uses the enriched brief — not the raw seed brief from `communities.yaml`.
3. **Given** a manual mode run with topic and brief supplied directly, **When** the pipeline runs, **Then** Agent 0 still executes using the supplied topic and brief as seed input.

---

### User Story 2 — Consensus Reached Before Iteration 5 (Priority: P2)

The Framer proposes a brief and The Resonator approves it before the maximum iteration count is reached. The pipeline does not run unnecessary additional iterations and passes the agreed brief downstream immediately.

**Why this priority**: Early consensus is the happy path and must be the common case. Unnecessary iterations waste API quota and add latency.

**Independent Test**: Run the pipeline and observe the logs; when The Resonator approves before iteration 5, verify that the B/C loop starts immediately after approval without further Agent 0 iterations.

**Acceptance Scenarios**:

1. **Given** The Resonator approves The Framer's proposal at iteration N (where N < 5), **When** approval is received, **Then** the enriched brief is passed downstream immediately and no further Agent 0 iterations run.
2. **Given** The Resonator approves at iteration 1, **When** the pipeline continues, **Then** only one Agent 0 iteration ran and the enriched brief is used.

---

### User Story 3 — Final Say Protocol at Iteration 5 (Priority: P2)

The Framer and The Resonator have not reached consensus after 4 iterations. On iteration 5, The Framer makes the final call, genuinely incorporating The Resonator's feedback — producing a brief that reflects both voices, not just The Framer's original position.

**Why this priority**: The pipeline must always produce an output. An unresolved negotiation must not block the cartoon from being generated.

**Independent Test**: Force a 5-iteration run (via test configuration); verify the log shows 5 Agent 0 iterations, that the final brief differs from The Framer's iteration-1 proposal in a way that reflects The Resonator's input, and that the B/C loop starts after iteration 5.

**Acceptance Scenarios**:

1. **Given** no consensus after 4 iterations, **When** iteration 5 runs, **Then** The Framer produces a final brief and the pipeline continues — no error is raised.
2. **Given** the Final Say Protocol activates, **When** the final brief is produced, **Then** it must reflect genuine consideration of The Resonator's feedback — it is not a restatement of The Framer's iteration-1 proposal.
3. **Given** the Final Say Protocol activates, **When** the pipeline continues, **Then** the log indicates that the final brief was produced under the Final Say Protocol.

---

### User Story 4 — Agent 0 Failure Exits Clearly (Priority: P3)

One or both LLMs are unavailable during the Agent 0 negotiation. The pipeline exits immediately with a clear error before any creative work begins.

**Why this priority**: A failed strategy layer must not silently pass an empty or seed-only brief to the creative loop. Fail loudly and early.

**Independent Test**: Simulate an API failure during Agent 0; verify the pipeline exits with a clear error message and that neither the B/C loop nor the image generator was invoked.

**Acceptance Scenarios**:

1. **Given** all models in The Framer's chain are unavailable during Agent 0, **When** Agent 0 exhausts all fallback options, **Then** the pipeline exits with a clear error before the B/C loop starts.
2. **Given** all models in The Resonator's chain are unavailable during Agent 0, **When** Agent 0 exhausts all fallback options, **Then** the pipeline exits with a clear error before the B/C loop starts.
3. **Given** The Framer's primary model fails but a fallback model is available, **When** Agent 0 attempts to run, **Then** the fallback model is used transparently and the pipeline continues without error.

---

### Edge Cases

- What if The Resonator approves on iteration 1 with no changes to the proposal? → Brief is passed downstream immediately; 1 iteration total; no error.
- What if The Framer's iteration-5 brief is substantively identical to iteration 1? → Final Say Protocol still applies; the log must note that The Resonator's feedback was considered even if not adopted.
- What if the enriched brief's culturally-loaded references list is empty? → Pipeline exits with a clear error before the B/C loop; an empty references list indicates Agent 0 failed to enrich the seed brief.
- What if Agent 0 is run in manual mode with no community context? → The Framer uses only the supplied topic and brief fields as seed; Agent 0 still runs and must produce a non-empty cultural angle and at least one reference.
- What if The Resonator's response contains a missing or malformed `<verdict>` tag? → Treated as `NEEDS REVISION`; the iteration count increments and the loop continues normally.
- What happens when both LLMs are unavailable? → Pipeline exits with a clear error once all models in both chains are exhausted; no partial output is produced.
- What happens if Agent 0 exceeds its time budget mid-iteration? → Pipeline exits immediately with a clear timeout error; the in-progress iteration is abandoned and the B/C loop is not started.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST run Agent 0 before the B/C creative loop for every pipeline invocation, in both community mode and manual mode.
- **FR-002**: Agent 0 MUST accept a topic and a seed strategy brief (target audience, output language, tone) as input.
- **FR-003**: Agent 0 MUST run a negotiation loop between The Framer and The Resonator, for a maximum of 5 iterations.
- **FR-004**: Each iteration, The Framer MUST propose or refine the cultural angle and culturally-loaded references only, wrapped in `<verdict>...</verdict>` tags. The seed brief's target audience, output language, and tone are locked inputs — Agent 0 cannot override them. Each iteration must make measurable progress — repeating or restating a previous position is not permitted.
- **FR-005**: Each iteration, The Resonator MUST wrap its verdict in a `<verdict>` tag containing either `APPROVED` or `NEEDS REVISION`, followed by specific, actionable feedback. The orchestrator parses this tag deterministically to decide whether to loop or stop. If the tag is missing or malformed, the orchestrator treats the response as `NEEDS REVISION` and continues to the next iteration.
- **FR-006**: If The Resonator approves before iteration 5, the enriched brief MUST be passed downstream immediately and Agent 0 MUST stop iterating.
- **FR-007**: If no consensus is reached after 5 iterations, The Framer MUST produce a final brief under the Final Say Protocol. The final brief must reflect genuine consideration of The Resonator's feedback.
- **FR-008**: The enriched brief passed downstream MUST contain all five fields: target audience and output language and tone (carried unchanged from the seed brief) plus cultural angle and a non-empty list of culturally-loaded references (added by Agent 0).
- **FR-009**: The B/C creative loop MUST receive the enriched brief from Agent 0, not the raw seed brief from `communities.yaml`.
- **FR-010**: System MUST log each Agent 0 iteration's outcome (iteration number, consensus status) before proceeding.
- **FR-011**: System MUST log the full enriched brief before the B/C loop starts.
- **FR-012**: Each persona in Agent 0 MUST define a prioritised model fail-over chain. If a model call fails, the next model in the chain is tried before raising an error. Only when all models in a persona's chain are exhausted MUST the pipeline exit with a clear error before the B/C loop or image generation is attempted.
- **FR-013**: Agent 0 MUST enforce a maximum wall-clock time budget of 15 minutes across all iterations. If the budget is exceeded before Agent 0 completes, the pipeline MUST exit with a clear error naming the timeout before the B/C loop or image generation is attempted.
- **FR-014**: Stage 3 MUST extract a shared dual-persona negotiation module used by both Agent 0 and B/C. As part of this migration, the B/C loop's existing structured output tag MUST be renamed to `<verdict>` and B/C MUST be updated to use the same model fail-over chain pattern as Agent 0.

### Key Entities

- **Seed Brief**: The strategy brief from `communities.yaml` or manual CLI input — target audience, output language, tone. This is the starting point for Agent 0, not the final output.
- **Enriched Brief**: The output of Agent 0. Extends the seed brief with two additional fields: cultural angle (the satirical reading of the topic for this audience) and culturally-loaded references (a non-empty list of observations not in the topic itself but widely known by the target group).
- **The Framer**: The proposing persona in Agent 0. Identifies the satirical hook, frames the cultural angle, surfaces references, and makes the Final Say call at iteration 5.
- **The Resonator**: The validating persona in Agent 0. Stress-tests the proposed angle against broader cultural context, validates or challenges the references and language, and proposes alternative angles — not just critique.
- **Iteration**: One complete exchange — The Framer proposes or refines wrapped in `<verdict>...</verdict>` tags; The Resonator responds with a `<verdict>APPROVED</verdict>` or `<verdict>NEEDS REVISION</verdict>` tag plus feedback. Maximum 5 per run. A missing or malformed verdict tag is treated as `NEEDS REVISION`. The `<verdict>` tag is the universal output contract for the reusable dual-persona loop module — it is the same tag used by all personas regardless of what the result represents (enriched brief, image prompt, etc.).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every pipeline run produces a log showing at least one complete Agent 0 iteration (Framer proposal + Resonator response) before the B/C loop starts.
- **SC-002**: The enriched brief logged before the B/C loop contains a non-empty cultural angle and at least one culturally-loaded reference for every run.
- **SC-003**: When The Resonator approves before iteration 5, the number of Agent 0 iterations logged equals the iteration at which approval was given — no excess iterations run.
- **SC-004**: When the Final Say Protocol activates, the log explicitly marks iteration 5 as a Final Say outcome, and the enriched brief differs from The Framer's iteration-1 proposal in at least one field.
- **SC-005**: When Agent 0 fails — due to all models in a persona's chain being exhausted, or due to the 15-minute timeout being exceeded — the pipeline exits with a clear error and zero calls are made to the B/C loop or image generator.

---

## Clarifications

### Session 2026-05-09

- Q: Can The Framer modify the seed brief's original fields (target audience, output language, tone)? → A: No — those fields are locked. Agent 0 adds only cultural angle and culturally-loaded references.
- Q: Should each persona define a prioritised model fail-over chain? → A: Yes — each persona slot defines a model chain; Agent 0 tries the next model on failure before exiting, consistent with the image generator pattern.
- Q: Should there be a maximum time budget for Agent 0? → A: Yes — 15 minutes total wall-clock time. If Agent 0 does not complete within 15 minutes, the pipeline exits with a clear error before the B/C loop starts.
- Q: How does the orchestrator detect The Resonator's approval? → A: Structured tag — The Resonator wraps its verdict in a `<verdict>APPROVED</verdict>` or `<verdict>NEEDS REVISION</verdict>` tag, parsed deterministically by the orchestrator.
- Q: How does The Framer wrap its proposal for deterministic parsing? → A: `<verdict>...</verdict>` — the same tag is used by all personas in the shared loop module regardless of what the output represents. This is the universal output contract for the reusable dual-persona loop.
- Q: Should Stage 3 extract the shared dual-persona loop module and migrate B/C? → A: Yes — Stage 3 extracts the shared module, implements Agent 0 on top of it, and migrates B/C at the same time. B/C's existing `<image_prompt>` tag is renamed to `<verdict>` as part of the migration. Both loops use `<verdict>` + fail-over chains from day one.

---

## Open Questions

- [x] **Shared dual-persona loop module**: Stage 3 extracts a shared negotiation module used by both Agent 0 and B/C. B/C's `<image_prompt>` tag is renamed to `<verdict>`. *(Resolved 2026-05-09)*
- [x] **Model fail-over in the shared loop — approach**: Each persona slot defines a prioritised model chain; fail-over is sequential, consistent with the image generator. *(Resolved 2026-05-09)*
- [x] **Model fail-over in the shared loop — scope**: B/C is migrated to the shared module and fail-over chains in Stage 3 alongside Agent 0. *(Resolved 2026-05-09)*

## Assumptions

- The seed brief from `communities.yaml` (target audience, output language, tone) is always passed to Agent 0 as the starting point — Agent 0 enriches it, it does not replace it from scratch.
- Agent 0 is not bypassable in Stage 3 — there is no flag or configuration option to skip it.
- The culturally-loaded references are short, factual observations (one or two sentences each) that the target audience would recognise, not in the news topic itself. They are surfaced by The Framer and validated or challenged by The Resonator.
- The maximum iteration count of 5 is shared with the B/C loop and is configurable in principle, but fixed at 5 for Stage 3.
- Manual mode supplies topic and brief fields directly — Agent 0 still runs using these as seed input; no communities.yaml is required.
- The Framer and Resonator follow the same iteration rules as the B/C loop: both must advance toward consensus each round; circular arguments are a protocol violation.
- The Final Say Protocol gives The Framer the deciding vote at iteration 5 but requires genuine engagement with The Resonator's feedback — the final brief must not be a verbatim copy of The Framer's iteration-1 proposal.
