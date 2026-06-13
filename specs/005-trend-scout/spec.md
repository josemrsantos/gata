# Feature Specification: Trend Scout

**Feature Branch**: `006-trend-scout`  
**Created**: 2026-05-16  
**Status**: Draft  
**Input**: User description: "Trend Scout — Agent A that scrapes and ranks today's news headlines, replacing the manual seed topic list in communities.yaml."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automated Topic Discovery (Priority: P1)

The developer runs the pipeline for a community with no seed topics configured. Agent A (Trend Scout) fetches today's headlines from the configured news sources, scores them using the Heat Index for that community's profile, and passes the top-ranked topics to the rest of the pipeline. A cartoon is produced without any manual topic input.

**Why this priority**: This is the core value of the feature — removing the manual maintenance burden while keeping cartoons relevant to today's news.

**Independent Test**: Can be fully tested by removing all seed topics from `communities.yaml` for one community, running the pipeline, and confirming a cartoon is generated about a real news story from that day.

**Acceptance Scenarios**:

1. **Given** a community with no seed topics in config, **When** the pipeline runs, **Then** Agent A fetches headlines, scores them, and the top topic is passed to the downstream agents.
2. **Given** Agent A successfully returns ranked topics, **When** the pipeline continues, **Then** the final cartoon is based on one of the top-ranked topics, not a hard-coded or placeholder topic.
3. **Given** multiple communities are configured, **When** the pipeline runs for each, **Then** each community receives topics scored by its own Heat Index profile (not a shared ranking).

---

### User Story 2 - Graceful Fallback to Seed Topics (Priority: P2)

When Agent A returns no results (network error, source unavailable, empty feed), the pipeline falls back silently to the seed topic list in `communities.yaml` and continues normally. No crash, no silent empty run.

**Why this priority**: Resilience — the pipeline must always produce a cartoon even when news scraping fails.

**Independent Test**: Can be fully tested by configuring Agent A with an intentionally broken source URL, running the pipeline with seed topics present, and confirming a cartoon is generated from the seed list.

**Acceptance Scenarios**:

1. **Given** Agent A fails to retrieve any headlines, **When** the pipeline continues, **Then** it falls back to the seed topic list and generates a cartoon from those topics.
2. **Given** Agent A returns an empty result set, **When** the pipeline continues, **Then** it behaves identically to the fallback case — no difference in output behaviour.
3. **Given** no seed topics exist and Agent A also fails, **When** the pipeline runs, **Then** it logs a clear error and exits without generating a partial or broken output.

---

### User Story 3 - Manual Topic Override (Priority: P1)

The developer invokes the pipeline with an explicit topic argument. Agent A is bypassed entirely; the manually specified topic goes directly to the downstream agents. This preserves RULE 12 — manual invocation must always be possible.

**Why this priority**: Equal priority to automated discovery — manual override is a hard project constraint (RULE 12), not an optional convenience.

**Independent Test**: Can be fully tested by running `python pipeline.py --topic "specific topic"` and confirming Agent A is not invoked and the cartoon reflects the supplied topic.

**Acceptance Scenarios**:

1. **Given** a manual topic is supplied at invocation, **When** the pipeline runs, **Then** Agent A is not called and the topic passes directly to the downstream agents.
2. **Given** a manual topic override is active, **When** seed topics are also present in config, **Then** the manual topic takes precedence over both Agent A and the seed list.

---

### User Story 4 - Swap News Source Without Code Changes (Priority: P3)

A developer adds a new news ingestion source (e.g., switching from RSS to a NewsAPI client) by editing configuration or dropping in a new source module, without modifying the Heat Index scoring logic or the pipeline orchestration.

**Why this priority**: Source-agnostic architecture is a stated constraint but is not needed for the first working version; it shapes how the code is structured.

**Independent Test**: Can be fully tested by replacing the configured source adapter with a stub that returns a hardcoded list of headlines, and confirming the rest of the pipeline behaves identically.

**Acceptance Scenarios**:

1. **Given** a new source adapter is configured, **When** Agent A runs, **Then** it uses the new adapter and the downstream pipeline is unaffected.
2. **Given** two source adapters are configured for the same community, **When** Agent A runs, **Then** it merges results from both before scoring.

---

### Edge Cases

- What happens when all fetched headlines score equally on the Heat Index? (Top-N selection is stable; ties broken by recency.)
- How does the system handle a headline feed that returns duplicate stories across sources?
- What if the network request to a news source times out mid-fetch?
- What if a community's Heat Index configuration is missing or malformed?
- What if Agent A returns fewer than the requested top-N topics? (Pass all available topics downstream.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST fetch headlines from at least one configured news source per community run without requiring manual topic input.
- **FR-002**: The system MUST score each headline using a per-community Heat Index and rank them in descending order.
- **FR-003**: The system MUST pass the top-ranked topic (or top-N, configurable) from Agent A to Agent 0 (Cultural Strategist) and Agent B/C (Satirist/Critic) as the pipeline's starting input.
- **FR-004**: The system MUST fall back to the community's seed topic list in `communities.yaml` when Agent A returns no results, with no change in pipeline behaviour.
- **FR-005**: The system MUST allow manual topic override at invocation time, bypassing Agent A entirely.
- **FR-006**: The system MUST log whether topics came from Agent A, the seed fallback, or a manual override.
- **FR-007**: The news ingestion layer MUST be source-agnostic — swapping a source adapter must not require changes to the scoring logic or pipeline orchestration.
- **FR-008**: Agent A MUST handle individual source failures gracefully (timeout, HTTP error, malformed feed) without crashing the pipeline.
- **FR-009**: Each community MUST have its own Heat Index profile; scores are not shared across communities.
- **FR-010**: The system MUST deduplicate headlines across multiple sources before scoring.

### Key Entities

- **Headline**: A news story with a title, source, publication timestamp, and optional summary. The atomic input to the Heat Index scorer.
- **Heat Index Score**: A numeric score assigned to a headline for a specific community, reflecting relevance and virality. Higher is more relevant.
- **Source Adapter**: A pluggable component that retrieves headlines from one news source (RSS feed, API, etc.) and returns a normalised list of Headlines.
- **Topic**: A headline (or derived summary) selected by Agent A and passed as the starting point to downstream agents.
- **Seed Topic**: A manually maintained fallback topic string stored in `communities.yaml`, used only when Agent A returns nothing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The pipeline produces a cartoon about a real news story when run with no seed topics configured — verifiable by human review of the output image and bundle.
- **SC-002**: Agent A completes headline fetching and scoring within 60 seconds for a single community on a normal network connection.
- **SC-003**: When Agent A fails, the pipeline completes using seed topics with zero additional user intervention required.
- **SC-004**: Manual topic override (`--topic` flag or equivalent) bypasses Agent A 100% of the time with no regression in cartoon quality.
- **SC-005**: Swapping a source adapter requires changes to configuration only — zero changes to scoring or orchestration code.

## Assumptions

- RSS feeds are the primary ingestion mechanism for the first implementation; NewsAPI or other HTTP sources are supported via adapters added later.
- The Heat Index is a weighted score computed from signals such as keyword overlap with community interests, headline recency, and source authority — exact weights are defined during planning.
- Top-N defaults to 3 topics passed downstream; the pipeline uses the highest-ranked one unless Agent 0 or B/C requests alternatives.
- Network access is available at pipeline runtime; offline mode is out of scope.
- `communities.yaml` schema is extended (not replaced) to add source configuration alongside the existing seed topics.
- Agent A is named "Trend Scout" in human-readable output, consistent with RULE 9.
