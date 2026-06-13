# Feature Specification: Free-Text Community Mode

**Feature Branch**: `008-free-text-community`
**Created**: 2026-06-10
**Status**: Draft
**Input**: User description: "Free-text community mode: --community accepts any description (e.g. 'US community that dislikes Trump') without requiring a pre-configured entry in communities.yaml. When the description doesn't match a named entry, Trend Scout fetches general current headlines and uses an LLM to rank them by relevance to the community description. Language and tone are inferred from the description via LLM. communities.yaml remains fully supported for saved named communities and is used when a match is found."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run pipeline for an ad-hoc community (Priority: P1)

A developer wants to generate a cartoon for a new audience (e.g. "US community that dislikes Trump") without editing any config file. They run the pipeline with a free-text description and the full cartoon is produced end-to-end — topic chosen, image generated, bundle saved.

**Why this priority**: This is the core feature. Everything else (language inference, config fallback) depends on this path working. Without it, the feature delivers no value.

**Independent Test**: Run `python pipeline.py --community "US community that dislikes Trump"` with no matching entry in communities.yaml; verify a cartoon bundle is produced in `output/`.

**Acceptance Scenarios**:

1. **Given** no entry in communities.yaml matches the description, **When** the user runs `--community "US community that dislikes Trump"`, **Then** the pipeline selects a relevant headline, generates a cartoon, and writes the bundle to `output/`.
2. **Given** the description is in English, **When** no language is specified, **Then** the output language is inferred as English and used throughout the cartoon text.
3. **Given** the description is vague or unusual, **When** headlines are fetched, **Then** the LLM selects the headline most likely to resonate with the described community — not just the most popular headline globally.

---

### User Story 2 - Language and tone inferred from description (Priority: P2)

A developer passes `--community "Communauté française qui critique Macron"` (a French-speaking community). Without any config, the pipeline infers French as the output language and selects an appropriately sharp political tone.

**Why this priority**: Without inference, free-text mode produces English cartoons for non-English audiences — breaking the core audience-fit contract.

**Independent Test**: Run with a description that clearly implies a non-English language; verify the generated cartoon text is in the inferred language.

**Acceptance Scenarios**:

1. **Given** a description containing a non-English language marker (e.g. "Communauté française"), **When** the pipeline runs in free-text mode, **Then** the output language is set to French and all cartoon text is in French.
2. **Given** a description that implies a tone (e.g. "sarcastic US tech workers"), **When** the pipeline runs, **Then** the tone is aligned with that description rather than defaulting to a generic tone.
3. **Given** no language can be reliably inferred, **When** the pipeline runs, **Then** English is used as the default with a log warning that inference fell back to default.

---

### User Story 3 - Named community in communities.yaml still works (Priority: P1)

An existing workflow uses `--community uk-politics`. The new free-text mode must not break this — communities.yaml entries must still be matched and used exactly as before.

**Why this priority**: Backwards compatibility. Existing scripts and automated runs must not regress.

**Independent Test**: Run `python pipeline.py --community uk-politics` and verify behaviour is identical to before this feature was introduced.

**Acceptance Scenarios**:

1. **Given** `uk-politics` exists in communities.yaml, **When** `--community uk-politics` is passed, **Then** the config entry is used (audience, language, tone, seed topics), not the free-text inference path.
2. **Given** a community name that exactly matches communities.yaml, **When** the pipeline runs, **Then** no LLM inference call is made for audience/language/tone.

---

### User Story 4 - Clear error when no headlines found for inferred context (Priority: P3)

The pipeline exits with a clear diagnostic if Trend Scout returns no usable headlines for a free-text community, rather than producing a blank or incorrectly targeted cartoon.

**Why this priority**: Failure handling for the new path. Lower priority because it's a fallback; P1 and P2 cover the happy paths.

**Independent Test**: Simulate an empty headline response; verify the pipeline logs a clear message and exits non-zero rather than proceeding.

**Acceptance Scenarios**:

1. **Given** Trend Scout returns zero relevant headlines for the community description, **When** the pipeline runs, **Then** it logs a clear error ("no headlines found for community: <description>") and exits without writing a bundle.

---

### Edge Cases

- What happens when the description partially matches a communities.yaml name (e.g. "uk politics" vs "uk-politics")? — No fuzzy matching; only exact name match triggers the config path.
- What happens if the description is a single word with no language signal (e.g. "developers")? — English is inferred as default; tone defaults to "dry wit".
- What happens if `--community` is an empty string? — Pipeline exits with a validation error before any network call.
- What happens when communities.yaml is absent entirely? — Free-text path still works; named-community path is unavailable but the pipeline does not crash on startup.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept any non-empty string as the value of `--community`, not just strings that appear in communities.yaml.
- **FR-002**: System MUST check communities.yaml first; if the value exactly matches a community name, the config entry is used and the free-text path is skipped entirely.
- **FR-003**: When no exact match is found in communities.yaml, the system MUST infer target audience, output language, and tone from the free-text description automatically before fetching headlines.
- **FR-004**: When no exact match is found, Trend Scout MUST fetch general current headlines (not community-specific seed topics) and automatically rank them by relevance to the community description.
- **FR-005**: The top-ranked headline from the relevance ranking MUST be passed to the pipeline as the topic, in the same way a community-configured headline would be.
- **FR-006**: If the inferred output language is not English, all cartoon text (caption, chalkboard labels, prompt) MUST be generated in that language.
- **FR-007**: The pipeline MUST log whether it used the config path or the free-text inference path for a given run.
- **FR-008**: If `--community` is an empty string, the pipeline MUST exit with a clear validation error before any network calls are made.
- **FR-009**: communities.yaml MUST remain optional — its absence must not cause the pipeline to crash when `--community` is used with a free-text description.
- **FR-010**: The no-argument (random community) mode MUST continue to load communities.yaml and pick a random community — this mode is unaffected by this feature.

### Key Entities

- **Ad-hoc community**: A community defined solely by a free-text description at runtime. Has no persistent record; its inferred audience, language, and tone exist only for the duration of the run.
- **Named community**: A community defined in communities.yaml with a name, target audience, output language, tone, and optional seed topics. Matched by exact name.
- **Inferred brief**: The StrategyBrief (audience, language, tone) produced by the LLM from a free-text description when no named match exists. Functionally equivalent to a named community's brief once produced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A free-text community description that does not match any communities.yaml entry produces a complete cartoon bundle — end-to-end — with zero code changes by the developer.
- **SC-002**: The inferred output language matches the primary language implied by the community description in at least 9 out of 10 manually reviewed test cases.
- **SC-003**: All existing communities.yaml-based runs (uk-politics, portuguese-adults, us-startup-crowd) continue to produce output identical in structure and quality to pre-feature behaviour — zero regressions.
- **SC-004**: Free-text mode adds no more than one additional LLM round-trip (for inference) compared to the named-community path.
- **SC-005**: When no headlines are available, the pipeline exits in under 5 seconds with a diagnostic message that names the community description — no silent failure, no partial bundle.

## Assumptions

- The LLM inference step for audience/language/tone uses the same LLM already available in the pipeline; no new external service is introduced.
- "Exact match" for communities.yaml lookup is case-sensitive and whitespace-sensitive (no fuzzy matching), keeping the logic simple and predictable.
- communities.yaml is loaded at startup if it exists; its absence is not an error in free-text mode.
- The inferred brief uses sensible defaults when inference is ambiguous: English for language, "dry wit" for tone, "general public" for audience.
- Trend Scout's general headline fetch (for free-text mode) uses the same news sources already configured for the existing community runs — no new sources are required.
- Output folder naming for free-text mode uses a sanitised version of the description (e.g. `output/us-community-that-dislikes-trump/`).
