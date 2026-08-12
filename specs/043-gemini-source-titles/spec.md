# Feature Specification: Uniform Source Titles

**Spec**: `043-gemini-source-titles`
**Created**: 2026-08-11
**Status**: Draft (revised — extended from Gemini-only to all three providers)

## Problem

Spec 042's Sources list is code-assembled from each panelist provider's own real
search results, but each provider's title quality is different, and none of the
three produce a consistent `domain - title` format:

- **Gemini**'s Google Search grounding API never returns a page title, only the
  bare domain (confirmed live: `GroundingChunkWeb.title` is always just e.g.
  `"ibm.com"`, and `.domain` is always `None`).
- **Claude** already returns a real, good page title via its citation API — but
  with no domain prefix.
- **Grok** (xAI)'s citation `title` field is confirmed live to be the in-text
  footnote number (e.g. `"1"`), not a title at all — the current fallback uses
  the raw URL as the "title", which is not readable.

The result is three visually inconsistent styles in the same Sources list.

## Goal

Every source in the published Sources list reads as `domain - page title`,
regardless of which provider found it:

- **Gemini**: resolve the grounding redirect URL with a direct HTTP fetch and
  read the destination page's real `<title>` (unchanged from the original scope
  of this spec).
- **Claude**: prepend the URL's domain to the title Anthropic's citation API
  already provides — no network fetch needed.
- **Grok**: since xAI's own `title` field is unusable but its URLs are real,
  direct destination URLs (not redirects), apply the same fetch-based title
  resolution used for Gemini.

All of this uses `httpx` (already a dependency) — no new package. Any failure
anywhere in this always degrades to `domain` alone, never blocks a source from
being published, and never fails the research step it belongs to.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Every source reads as "domain - title" (Priority: P1)

The operator runs `--linkedin-post` and every entry in the published Sources
list — regardless of which of the three providers found it — reads as
`domain - page title`, not a bare domain, a domain-less title, or a raw URL.

**Why this priority**: A reader-facing Sources list with three different
presentation styles undermines the credibility the list exists to establish.

**Independent Test**:
```
python -m pytest tests/test_agent_linkedin_post.py -k source_title -v
```

**Acceptance Scenarios**:

1. **Given** a Gemini grounding chunk whose redirect URL resolves to a page with
   a `<title>` tag, **When** the source is built, **Then** its title is
   `"{bare domain} - {fetched page title}"`.
2. **Given** a Claude citation with a real title, **When** the source is built,
   **Then** its title is `"{domain parsed from the citation's URL} - {Claude's
   own title}"`.
3. **Given** a Grok annotation whose URL resolves to a page with a `<title>`
   tag, **When** the source is built, **Then** its title is `"{bare domain} -
   {fetched page title}"`, exactly like Gemini's path.
4. **Given** a fetched or provided title contains HTML entities or extra
   whitespace, **When** the source is built, **Then** the published title is
   decoded and collapsed to a single clean line.

---

### User Story 2 — Any resolution failure degrades to domain alone (Priority: P1)

If resolving a page's title fails for any reason — for any provider — the
source still publishes, with its title falling back to just the bare domain,
never blocking or failing the research step.

**Why this priority**: Spec 042's soft-failure philosophy (a single provider's
trouble never aborts the run) must extend to this cosmetic layer too — a title
decoration must never gate whether a real, verified source gets published.

**Independent Test**:
```
python -m pytest tests/test_agent_linkedin_post.py -k source_title_failure -v
```

**Acceptance Scenarios**:

1. **Given** a fetch (Gemini or Grok path) times out, raises a connection
   error, or returns a non-2xx status, **When** the source is built, **Then**
   its title is exactly the bare domain, nothing else.
2. **Given** the destination page has no `<title>` tag (or an empty one),
   **When** the source is built, **Then** its title is the bare domain.
3. **Given** a Claude citation has no title at all, **When** the source is
   built, **Then** its title is the bare domain (not a domain-less blank).
4. **Given** several sources need resolving, **When** one fails, **Then** the
   others are unaffected — each is resolved independently.
5. **Given** a URL that cannot be parsed into a domain at all (malformed),
   **When** the source is built, **Then** the title falls back to the raw URL
   rather than an empty string.

---

### Edge Cases

- A redirect chain that never resolves (infinite redirects, or exceeds a
  reasonable hop limit) → treated as a failure, bare domain kept.
- A destination page whose `<title>` is only whitespace → treated as no title,
  bare domain kept.
- A URL's domain includes a `www.` prefix → stripped for a cleaner display
  domain (e.g. `www.ibm.com` → `ibm.com`), matching how Gemini's own bare-domain
  title already looks with no prefix.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A shared `_domain_from_url(url)` helper MUST extract a clean
  display domain (network location, `www.` prefix stripped) from any URL,
  falling back to the raw URL itself if parsing yields nothing usable.
- **FR-002**: A shared fetch-based title resolver MUST perform an HTTP GET
  (following redirects) via `httpx`, with a short per-URL timeout and a
  browser-like `User-Agent` header (confirmed live: Wikipedia and likely other
  sites return HTTP 403 for requests with no User-Agent, which is
  indistinguishable from "no title found" without one), extract the
  destination page's `<title>` tag, decode HTML entities, and collapse
  whitespace — returning `None` on any failure (timeout, connection error,
  non-2xx status, missing/empty tag) rather than raising.
- **FR-003**: This resolver MUST be reused, unchanged, for both Gemini's
  redirect URLs and Grok's direct URLs, run in parallel across all of one
  provider's sources so total added latency per provider stays small
  regardless of source count.
- **FR-004**: Gemini sources: title becomes `"{bare domain} - {fetched page
  title}"` on success; the bare domain alone (today's Spec 042 behaviour) on
  any failure.
- **FR-005**: Grok sources: title becomes `"{bare domain of the citation URL} -
  {fetched page title}"` on success; the bare domain alone on any failure
  (replacing today's raw-URL-as-title fallback).
- **FR-006**: Claude sources: title becomes `"{domain parsed from the citation
  URL} - {Claude's own citation title}"` when Claude provides a title; the bare
  domain alone when it doesn't. No network fetch is needed for Claude — its
  title already comes from Anthropic's own citation API.
- **FR-007**: This resolution step MUST fit inside each provider's existing
  120-second research budget (Spec 042 FR-001) — its own per-URL timeout MUST
  be short enough that even a worst-case full set of slow/hanging fetches
  cannot meaningfully threaten that budget.
- **FR-008**: Every resolution failure SHOULD be logged at DEBUG (not WARNING —
  this is a cosmetic enhancement, not a research failure) so it's inspectable
  without adding noise to normal operation.

### Key Entities

- No new entities — this modifies `ResearchSource.title` values produced by all
  three existing research paths (Spec 042).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a mocked HTML response containing `<title>What is Vibe
  Coding ?</title>` for a Gemini or Grok source, the resulting title is exactly
  `"{bare domain} - What is Vibe Coding ?"`.
- **SC-002**: Given a mocked fetch that raises or returns non-2xx (Gemini or
  Grok path), the source title is exactly the bare domain.
- **SC-003**: Given a mocked HTML response with no `<title>` tag, the source
  title is exactly the bare domain.
- **SC-004**: Given a Claude citation with a real title, the source title is
  `"{domain} - {that title}"` with no network call made.
- **SC-005**: Given a Claude citation with no title, the source title is the
  bare domain.
- **SC-006**: A real, manually-run fetch against the actual redirect URL
  already captured in `output/manual/.../linkedin_post.md` (from Spec 042's own
  end-to-end test) resolves to a real page title (manual verification during
  implementation, not an automated test).
- **SC-007**: `python -m pytest tests/` passes with every network call mocked
  per Constitution §9 — zero real HTTP calls during the automated suite.

## What does NOT change

- The published Sources list is still 100% assembled from real, verified
  sources — this only changes what text is *shown* for each entry, not which
  URLs are considered valid or how they're deduplicated.
- No new dependency — `httpx` is already used elsewhere in this project's
  dependency tree.
- Spec 042's soft-failure contract (a provider's research failure doesn't abort
  the run) is unaffected; this resolution step is strictly cosmetic and
  additive.

## Assumptions

- Fetching a URL the operator's own pipeline already decided to cite (via a
  provider's own search/citation decision) to read its `<title>` is a
  reasonable, low-risk use of an already-public URL — no robots.txt or
  scraping-policy concerns beyond what a normal browser visit following that
  same link would trigger.
- This is a `fix:`-scoped correction to Spec 042's Sources-list quality, not a
  new feature — expected to be a patch-level version bump.
