# Feature Specification: Community Configuration

**Feature Branch**: `002-community-config`
**Created**: 2026-05-01
**Status**: Draft
**Input**: User description: "Stage 2 community configuration: replace hardcoded TOPIC and BRIEF in pipeline.py with a
communities.yaml file. Each community entry defines: name, target_audience, output_language, tone, and a list of seed
topics. The pipeline reads the config, selects a community and topic, and runs the full pipeline for that combination."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Run the Pipeline for a Specific Community (Priority: P1)

An operator wants to generate a cartoon for a named community. They invoke the pipeline with the community name and it
runs end-to-end using that community's audience, language, tone, and a randomly selected seed topic from its list.

**Why this priority**: This is the primary use case — targeted cartoon generation for a known audience. Everything else
depends on communities being loadable and usable.

**Independent Test**: Invoke the pipeline with a valid community name; verify the output image is produced and the logs
confirm the correct community name and a topic from that community's list were used.

**Acceptance Scenarios**:

1. **Given** a valid `communities.yaml` with at least one community entry, **When** the pipeline is invoked with that
   community's name, **Then** it runs to completion using that community's `target_audience`, `output_language`, and
   `tone`, and selects one topic from that community's `topics` list.
2. **Given** a community with multiple seed topics, **When** the pipeline runs, **Then** one topic is selected at random
   from the list.
3. **Given** a community name that does not exist in the config, **When** the pipeline is invoked with that name, **Then
   ** it exits immediately with a clear error identifying the unknown community name.

---

### User Story 2 — Run the Pipeline Without Specifying a Community (Priority: P2)

An operator runs the pipeline without specifying a community. The pipeline picks one at random from the config and
selects a seed topic from that community's list, then runs end-to-end.

**Why this priority**: Enables automated/scheduled runs without manual input, which is the target operating mode for
Stage 7+.

**Independent Test**: Invoke the pipeline with no community argument; verify the output image is produced and the logs
confirm which community and topic were selected.

**Acceptance Scenarios**:

1. **Given** a valid `communities.yaml` with multiple entries, **When** the pipeline is invoked with no community
   specified, **Then** one community is selected at random and the pipeline runs to completion.
2. **Given** a valid `communities.yaml` with exactly one community, **When** the pipeline is invoked with no community
   specified, **Then** that community is always used.

---

### User Story 3 — Run the Pipeline in Manual Mode (Priority: P2)

A developer wants to test the pipeline or generate a one-off cartoon without setting up or modifying `communities.yaml`.
They invoke the pipeline with a topic and strategy brief supplied directly, and it runs end-to-end using those values.

**Why this priority**: Manual mode is the developer's primary escape hatch for testing and ad-hoc runs. It preserves
Stage 1 behaviour and must not regress. It also means `communities.yaml` is strictly optional when not using community
mode.

**Independent Test**: Invoke the pipeline with manual topic and brief arguments and no `communities.yaml` present;
verify the output image is produced and no error about a missing config file is raised.

**Acceptance Scenarios**:

1. **Given** no `communities.yaml` exists, **When** the pipeline is invoked in manual mode with a topic and brief, *
   *Then** it runs to completion without any config-related error.
2. **Given** a topic and brief are supplied directly, **When** the pipeline runs in manual mode, **Then** those values —
   not any community entry — drive the run.
3. **Given** both community mode arguments and manual mode arguments are supplied simultaneously, **When** the pipeline
   starts, **Then** it exits immediately with a clear error indicating the conflict before any API call.

---

### User Story 4 — Config Validation Fails Clearly (Priority: P3)

An operator has a missing or malformed config file. The pipeline exits immediately with a message that identifies the
problem precisely — without attempting any API calls.

**Why this priority**: Silent failures or cryptic errors waste API quota and make debugging painful. Clear validation is
essential for operational confidence.

**Independent Test**: Invoke the pipeline with a missing file, a malformed YAML file, and a file with a community
missing required fields; verify each produces a distinct, actionable error message and exits before any API call is
made.

**Acceptance Scenarios**:

1. **Given** `communities.yaml` does not exist, **When** the pipeline starts, **Then** it exits with an error naming the
   expected file path.
2. **Given** `communities.yaml` contains invalid YAML, **When** the pipeline starts, **Then** it exits with a parse
   error before any API call.
3. **Given** a community entry is missing a required field (`name`, `target_audience`, `output_language`, `tone`, or
   `topics`), **When** the pipeline starts, **Then** it exits with an error naming the community and the missing field.
4. **Given** a community entry has an empty `topics` list, **When** the pipeline starts, **Then** it exits with an error
   naming that community.
5. **Given** two community entries share the same `name` value, **When** the pipeline starts, **Then** it exits with an
   error naming the duplicate before any API call.

---

### Edge Cases

- What happens when `communities.yaml` exists but contains zero valid community entries? → Pipeline exits with a clear
  error before any API call.
- What happens when a community's `topics` list has only one entry? → That topic is always used; no error.
- What happens when the config file path contains an environment variable reference or relative path? → Resolved
  relative to the project root; not an error unless the resolved path does not exist.
- What happens when two community entries share the same `name` value? → Pipeline exits with a clear error naming the
  duplicate before any API call.
- What happens when both community mode and manual mode arguments are supplied together? → Pipeline exits with a clear
  error before any API call; the two modes are mutually exclusive.
- What is the output path in manual mode? → `output/manual/{topic}.png`, following the same
  `output/{community-name}/{topic}.png` pattern with `manual` as the fixed directory name.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load community configuration from a YAML file at a fixed location: `communities.yaml` at the
  project root. No alternative path or override mechanism is supported in Stage 2.
- **FR-002**: Each community entry in the config MUST define five fields: `name` (string), `target_audience` (string),
  `output_language` (string), `tone` (string), and `topics` (non-empty list of strings).
- **FR-003**: System MUST accept an optional `--community <name>` CLI argument to select a specific community by name.
- **FR-004**: When no community is specified, the system MUST select one at random from all valid entries in the config.
- **FR-005**: System MUST select one topic at random from the selected community's `topics` list.
- **FR-006**: System MUST pass the selected community's `target_audience`, `output_language`, and `tone` to the pipeline
  as the strategy brief.
- **FR-007**: System MUST log the selected community name and topic before any API call is made.
- **FR-008**: System MUST validate the config file on startup and exit with a clear, actionable error message before any
  API call if the file is missing, unparseable, contains invalid entries, or contains duplicate community names.
- **FR-009**: System MUST remove all hardcoded topic and brief values from the pipeline entry point.
- **FR-010**: System MUST save the output image to `output/{community-name}/{topic}.png`. Both the `{community-name}`
  and `{topic}` segments MUST be sanitized using the same rules: lowercased, spaces replaced with underscores, all
  characters that are not alphanumeric, underscores, or hyphens stripped, truncated to 50 characters. Example: a
  community named `"Portuguese Adults (18-35)"` with topic `"Is Scrum really Agile?"` produces
  `output/portuguese_adults_18-35/is_scrum_really_agile.png`. The `output/` directory and the community subdirectory
  MUST be created automatically if they do not exist.
- **FR-011**: System MUST support a manual mode in which the operator supplies a topic and strategy brief directly via
  the CLI flags `--topic <text>`, `--audience <text>`, `--language <text>`, and `--tone <text>`, bypassing
  `communities.yaml` entirely. These flags map to the strategy brief as follows: `--audience` → `target_audience`,
  `--language` → `output_language`, `--tone` → `tone`.
- **FR-012**: When running in manual mode, the system MUST NOT require `communities.yaml` to exist and MUST NOT attempt
  to load or validate it.
- **FR-013**: The two modes (community mode and manual mode) MUST be mutually exclusive. If arguments for both modes are
  supplied simultaneously, the system MUST exit with a clear error before any API call.
- **FR-014**: In manual mode, the output image MUST be saved to `output/manual/{topic}.png`, where `{topic}` is
  sanitized using the same rules as FR-010 (lowercased, spaces→underscores, non-alphanumeric/non-hyphen stripped,
  truncated to 50 characters).
- **FR-015**: All log output in agent and pipeline code MUST use Python's `logging` module (Constitution Principle 13).
  Bare `print()` calls inherited from Stage 1 (`agent_bc.py`, `agent_d.py`, `pipeline.py`) MUST be migrated to
  `logging` as part of this stage. Log levels: `INFO` for normal flow, `WARNING` for recoverable issues, `ERROR` for
  failures.

### Key Entities

- **Community**: A named audience configuration. Attributes: `name`, `target_audience`, `output_language`, `tone`,
  `topics` (list of strings). Each community maps directly to a `StrategyBrief` plus a topic selection.
- **Configuration file** (`communities.yaml`): A YAML file containing a list of community entries. Located at a known
  path relative to the project root. Not committed if it contains sensitive audience targeting data — assumption: it is
  safe to commit for Stage 2.
- **Operating mode**: Either *community mode* (topic and brief derived from `communities.yaml`) or *manual mode* (topic
  and brief supplied directly by the operator). The mode is determined by the arguments present at invocation; the two
  modes are mutually exclusive.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can add a new community to `communities.yaml` and run the pipeline for it without modifying
  any code. A working `communities.yaml` with at least two communities (one English, one non-English) is committed to
  the repository as part of this stage.
- **SC-002**: The pipeline produces a valid output image for every valid community entry in the config.
- **SC-003**: The pipeline exits with a clear error message within 2 seconds of startup when the config file is missing
  or malformed — before making any API call.
- **SC-004**: All hardcoded topic and brief values are removed from the pipeline entry point; values are always supplied
  at runtime either from `communities.yaml` or from operator-provided arguments.
- **SC-005**: The selected community name and topic appear in the pipeline log output for every run, enabling
  traceability of which cartoon was generated for which audience.
- **SC-006**: The output image is saved to `output/{community-name}/{topic}.png`; the path is derivable from the
  community name and topic without inspecting any config or log file.
- **SC-007**: A developer can run the pipeline end-to-end in manual mode with no `communities.yaml` present, using only
  `--topic`, `--audience`, `--language`, and `--tone` CLI flags, and receive a valid output image.
- **SC-008**: All agent and pipeline log output uses Python's `logging` module; no bare `print()` calls remain in any
  source file after this stage.

---

## Clarifications

### Session 2026-05-01

- Q: How is the community name passed at invocation? → A: CLI argument (`--community <name>`)
- Q: What should the output file path be? → A: `output/{community-name}/{topic}.png`. Topic sanitization: lowercase,
  spaces→underscores, non-alphanumeric stripped, truncated to 50 characters. Example:
  `output/portuguese-adults/is_scrum_really_agile.png`.
- Q: How should duplicate community names in `communities.yaml` be handled? → A: Fail on startup with a clear error
  naming the duplicate — treated as a config validation error, no API calls made.

### Session 2026-05-03

- Q: Should `{community-name}` in the output path be sanitized the same way as `{topic}`? → A: Yes — same rules apply to both segments (lowercase, spaces→underscores, non-alphanumeric stripped, truncated to 50 chars).
- Q: Is the `communities.yaml` path configurable or fixed? → A: Fixed at project root for Stage 2; no `--config` flag or environment variable override. FR-001 updated accordingly.
- Q: Should YAML field names match CLI flag names? → A: No — YAML keeps `target_audience` / `output_language` (matching `StrategyBrief`); CLI flags `--audience` / `--language` are documented shorthands. Mapping added to FR-011.
- Q: Should a `communities.yaml` be committed to the repo as part of Stage 2 delivery? → A: Yes — a `communities.yaml` with 2–3 diverse example communities (at least one non-English) is committed as part of this stage. SC-001 is only testable with a real config file present.

---

## Assumptions

- The `communities.yaml` file is safe to commit to the repository for Stage 2; no community entry contains sensitive or
  private information.
- Community selection when none is specified uses uniform random selection across all valid entries — no weighting,
  scheduling, or rotation logic is required for Stage 2.
- Topic selection within a community uses uniform random selection — no deduplication or "avoid recent topics" logic is
  required for Stage 2.
- The config file path is fixed at `communities.yaml` in the project root for Stage 2; dynamic or
  environment-variable-driven paths are out of scope.
- A minimum of one community with at least one topic is required for the pipeline to run; the config schema does not
  need to support optional fields.
- The existing `StrategyBrief` datatype is sufficient to represent a community's configuration; no new shared types are
  needed beyond a community loader.
- Manual mode accepts topic and brief fields via `--topic`, `--audience`, `--language`, and `--tone` CLI flags; it
  writes output to `output/manual/{topic}.png`, consistent with the community mode path pattern.
- The two modes are detected from the CLI arguments present at invocation; no environment variable or config-file flag
  is needed to switch between them.
