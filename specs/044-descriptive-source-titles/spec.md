# Feature Specification: Descriptive Source Titles

**Spec**: `044-descriptive-source-titles`
**Created**: 2026-08-23
**Status**: Draft

## Problem

Spec 043 made every source read as `domain - title`, but in real runs a
meaningful share of published sources still fall back to something that is
not actually descriptive of the page. Confirmed live in
`output/newsletter/07_AI_Slop/ai_slop_myth_or_reality/uk/linkedin_post.md`'s
own Sources list:

- Bare domain, no title at all: `medium.com`, `facebook.com`,
  `sciencedirect.com`, `fidelity.com`.
- Domain plus a title that is only the site's own domain label restated as
  a word, not a description of the specific page: `reddit.com - Reddit`.

This happens because `_fetch_page_title` (`agents/agent_linkedin_post.py`)
only parses the raw `<title>` tag and returns `None` on any failure — a
non-2xx status, a timeout, or a missing tag — with nothing else attempted:

1. Sites that gate their real content behind a login wall or bot detection
   (Facebook, Reddit, ScienceDirect, Fidelity) commonly return a 403, an
   empty page, or a generic shell page to a plain `httpx` GET — but many of
   these same sites still render Open Graph (`og:title`) or Twitter Card
   (`twitter:title`) meta tags server-side for link-preview purposes, which
   `_fetch_page_title` never looks at.
2. When a `<title>` tag IS returned, it is accepted verbatim even when it is
   just the site's own domain label restated (e.g. a gated Reddit page whose
   `<title>` is literally `"Reddit"`) — there is no check for whether the
   title actually describes the specific page rather than the site in
   general.
3. The URL itself is never used as a signal. Several of the sites above
   (Medium, Facebook) encode the actual post text directly in their URL slug
   (e.g. `.../slop-defined-as-digital-content-of-low-quality-...`), which is
   real, page-specific, non-fabricated data that the current resolver
   ignores entirely.
4. Every panelist provider (Claude, Gemini, Grok) already reads real content
   from each page it cites as part of performing its own web search — that
   knowledge is currently discarded once the search call returns; nothing
   asks the provider what a specific cited page was actually about.

## Goal

Every source published in a Sources list — regardless of which of the three
panelist providers (Claude, Gemini, Grok) found it — carries a genuinely
descriptive title. Real, literal signals are always preferred first, since
they need no interpretation: a fetched `<title>`/`og:title`/`twitter:title`,
or a humanised URL slug. When none of those yield anything descriptive, the
source's own originating provider — which already read that page's content
while forming its citation — supplies a short descriptive title for it, in
the *same* research call that found it (no extra network or LLM call, no
re-reading the source a second time). Only when neither track yields
anything descriptive is a source dropped from the published list, rather
than published under a bare domain or domain-label-only title.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Every published source carries a genuinely descriptive title (Priority: P1)

A source's title is resolved through one ordered chain of signals, each
tried only if the one before it didn't yield anything descriptive, so that
every published source ends up with real, page-specific text rather than a
bare domain or the site's own name restated:

1. **Fetched page metadata** — the already-fetched HTML's `<title>` tag,
   then (if that's missing or rejected) its `og:title` and `twitter:title`
   meta tags. Claude sources start instead from the real title its own
   citation API already provides (no fetch needed).
2. **A humanised URL-path slug** — when no fetched signal is descriptive, or
   the fetch fails outright (timeout, connection error, non-2xx), the most
   specific hyphen/underscore-delimited path segment with enough real words
   is turned into readable prose (e.g.
   `/gen-z-workers-sabotage-ai-rollout-backlash/` becomes
   `"Gen Z workers sabotage AI rollout backlash"`); purely numeric or
   hex-like ID segments are rejected.
3. **A title supplied by the source's own originating provider, in the same
   call** — every research call (Gemini, Claude, and Grok alike) is
   prompted, as part of its normal response, to append a short,
   code-parseable block after its prose giving a descriptive title for each
   URL it cites, grounded in content it already read while performing that
   search. No separate follow-up call is made, and the provider is never
   asked to re-read or re-interpret a source a second time. A
   provider-supplied title is only used if it matches, by URL, one of that
   same response's own verified citation/grounding URLs — an entry for any
   other URL is discarded and never introduces a new source.
4. **Drop** — if none of the above yields anything descriptive, the source
   is left out of the published list entirely, rather than published as a
   bare domain or a domain-label-only title.

At every step, a candidate title is rejected as non-descriptive — and the
chain moves to the next step — when, once normalised (case-folded,
punctuation and whitespace stripped), it is empty or equals the first label
of the source's own domain (the segment before the first `.` — e.g.
`"reddit"` for `reddit.com`, `"sciencedirect"` for `sciencedirect.com`).
Containing that label within a longer, real title is not disqualifying —
only the title being *only* the label is (e.g. `"Reddit"` for `reddit.com`
is rejected; `"TechCrunch: AI slop is everywhere"` for `techcrunch.com` is
not).

**Why this priority**: This is the whole point of the spec — real sources
currently publish as `medium.com`, `facebook.com`, `sciencedirect.com`,
`fidelity.com`, or `reddit.com - Reddit` in
`output/newsletter/07_AI_Slop/ai_slop_myth_or_reality/uk/linkedin_post.md`,
undermining the credibility a Sources list exists to establish. Ordering the
chain real-signal-first keeps every accepted title traceable to data the
source itself published (a meta tag or its own URL) before ever relying on
a provider's own characterisation of a page, and only drops a source when
even that characterisation has nothing to offer.

**Independent Test**:
```
python -m pytest tests/test_agent_linkedin_post.py -k source_title -v
```

**Acceptance Scenarios**:

1. **Given** fetched HTML with no `<title>` tag but a
   `<meta property="og:title" content="Real Page Title">` tag, **When** the
   source is resolved, **Then** its title is `"{domain} - Real Page Title"`.
2. **Given** fetched HTML where `<title>` is rejected as non-descriptive but
   `<meta name="twitter:title" content="...">` is present and descriptive,
   **When** the source is resolved, **Then** the `twitter:title` value is
   used.
3. **Given** fetched HTML with none of `<title>`, `og:title`, or
   `twitter:title` present or descriptive, **When** the source is resolved,
   **Then** resolution proceeds to the URL-slug fallback.
4. **Given** a fetched `<title>` of exactly `"Reddit"` for a source at
   `reddit.com`, **When** classified, **Then** it is treated as
   non-descriptive.
5. **Given** a short but substantive title such as `"AI Bubble"`, **When**
   classified, **Then** it is treated as descriptive — brevity alone is not
   disqualifying.
6. **Given** Claude's own citation title equals its domain's first label,
   **When** the source is built, **Then** it is rejected the same way and
   falls through to the URL-slug fallback on the citation's URL.
7. **Given** a fetch failure (403/timeout/connection error) for
   `https://www.facebook.com/newshour/posts/slop-defined-as-digital-content-of-low-quality-that-is-produced-usually-in-quant/1326081292720447/`,
   **When** the source is resolved, **Then** its title is derived from the
   descriptive slug segment, not left as the bare domain.
8. **Given** a URL whose only path segment is a numeric or hex-like ID (e.g.
   `.../pii/S2666799123000436`), **When** evaluated, **Then** the segment is
   rejected as non-descriptive and resolution proceeds to the
   provider-supplied-title step.
9. **Given** a URL with multiple path segments, **When** deriving a slug
   title, **Then** the last segment with enough real words is used, not
   necessarily the final raw segment (e.g. a trailing numeric ID after a
   descriptive segment is skipped).
10. **Given** a provider's response includes an appended titles block with a
    descriptive title for a cited URL, **When** no earlier signal resolved
    that source, **Then** the provider-supplied title is used, in the same
    `"{domain} - {title}"` format as any other signal.
11. **Given** the appended titles block includes a line for a URL that is
    **not** among that same response's verified citation/grounding URLs,
    **When** parsing, **Then** that line is discarded and never introduces a
    new source into the published list.
12. **Given** a provider-supplied title that, once normalised, equals the
    domain's first label, **When** classified, **Then** it is rejected the
    same as any other non-descriptive title and resolution proceeds to drop
    the source.
13. **Given** a provider's response omits the titles block entirely, or the
    block is malformed and fails to parse, **When** resolving that
    provider's remaining sources, **Then** each proceeds as if no
    provider-supplied title existed (falls through to being dropped, absent
    any other resolving signal), and the rest of that provider's digest
    (`summary`, other sources) is unaffected.
14. **Given** the titles block is present in a provider's raw response text,
    **When** the digest's `summary` is stored, **Then** the block's own
    markers and content are stripped and never appear in the summary passed
    to later pipeline stages (planner, writer).
15. **Given** a source URL with no path (e.g. `https://reddit.com`), a fetch
    that yields nothing descriptive, and no provider-supplied title for it,
    **When** the Sources list is built, **Then** that source is absent from
    the final list, and no other source is affected.
16. **Given** a run where every source resolves descriptively (via any
    signal), **When** the Sources list is built, **Then** none are dropped.
17. Dropping a source is logged at `DEBUG` and does not raise or fail the
    research step it belongs to.

---

### Edge Cases

- Gemini's redirect URLs (`vertexaisearch.cloud.google.com/grounding-api-redirect/...`):
  fetch-based resolution (both meta-tag parsing and, if needed, slug
  humanisation) operates on the final destination URL after redirects are
  followed (unchanged from Spec 043), never on the redirect wrapper's own
  path. The provider-supplied title (chain step 3) is matched against
  whichever URL form that provider's own citation/grounding metadata used
  originally (the redirect URL for Gemini, since that's what its grounding
  metadata contains) — not the fetch-resolved destination.
- When a redirect chain resolves successfully but the final destination then
  returns a non-2xx status (e.g. a 403 from a bot-gated site), the resolved
  destination URL MUST still be captured for slug humanisation — the
  current fetch helper discards the destination URL entirely on any
  exception, which would otherwise leave slug humanisation operating on the
  original redirect-wrapper URL instead of the real destination (see
  FR-014).
- Claude does not get a live fetch (Spec 043 FR-006 — its citation title is
  already real, no network call needed); when its citation title is
  non-descriptive or absent, it still goes through the same chain order as
  every other source: slug humanisation (step 2) on the citation URL first,
  then its own provider-supplied title (step 3, matched against its own
  citation URL) if that also fails.
- Matching a provider-supplied title's URL against verified citation URLs
  tolerates only trivial formatting differences (trailing slash, URL
  scheme case) — it MUST NOT match two different URLs merely by sharing a
  domain or a similar path.
- A title recovered via `og:title`/`twitter:title`, or supplied by the
  provider, still goes through the same non-descriptive check as `<title>`
  — it is not automatically trusted just because it came from a different
  tag or from the provider itself.
- Deduplication of sources by URL (existing behaviour) happens before
  title resolution; dropping a source for lacking a descriptive title never
  causes a different source to be silently duplicated in its place.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST parse `og:title` and `twitter:title` meta tags
  from an already-fetched page's HTML whenever `<title>` is absent or
  rejected as non-descriptive, before treating the fetch as yielding no
  title.
- **FR-002**: The system MUST classify a candidate title as non-descriptive
  when, after normalising (case-folded, punctuation and whitespace
  stripped), it is empty, or it equals the first label of the source's
  domain (the segment before the first `.` in the value `_domain_from_url`
  already returns, e.g. `"reddit"` for `reddit.com`). This check applies to
  every candidate title regardless of its source (fetched tag, Claude
  citation, or provider-supplied per FR-007).
- **FR-003**: The system MUST derive a fallback title from the URL's own
  path when no fetched signal is descriptive: take the most specific
  hyphen/underscore-delimited path segment with at least a minimum number of
  real words, and convert separators to spaces to form readable prose.
- **FR-004**: The system MUST reject path segments that are purely numeric,
  hex-like IDs, or below the minimum word count from FR-003, and continue
  to the provider-supplied-title check (FR-007) if none qualify.
- **FR-005**: URL-slug humanisation (FR-003/FR-004) MUST apply uniformly to
  sources from all three providers — Gemini and Grok (after their live fetch
  yields nothing descriptive) and Claude (after its citation title is
  rejected or absent).
- **FR-006**: The system MUST apply the FR-002 non-descriptive check to
  Claude's own citation-provided title, not only to fetched titles.
- **FR-007**: Each provider's research system prompt MUST instruct the
  model to append, after its normal response, a short, code-parseable block
  giving a descriptive title for every URL it cites in that same call — no
  separate follow-up call, and no request to re-read or re-search a source
  a second time.
- **FR-008**: The system MUST parse this appended block and match each
  entry's URL against that same response's own verified citation/grounding
  URLs (tolerating only trivial formatting differences, e.g. a trailing
  slash); any entry whose URL does not match a verified citation MUST be
  discarded and MUST NOT be treated as introducing a new source.
- **FR-009**: A provider-supplied title MUST pass the FR-002
  non-descriptive check before being accepted, exactly like any other
  candidate title.
- **FR-010**: The appended titles block MUST be stripped from the stored
  `ResearchDigest.summary` text and MUST NOT appear anywhere in text passed
  to later pipeline stages (planner, writer).
- **FR-011**: A source for which no signal — fetched `<title>`, `og:title`,
  `twitter:title`, Claude's citation title, a humanised URL-path segment, or
  a provider-supplied title — is descriptive MUST be dropped from the
  published Sources list rather than published under a bare domain or
  domain-label-only title.
- **FR-012**: Dropping a source for lacking a descriptive title MUST be
  logged at `DEBUG` and MUST NOT raise, block, or fail the research step it
  belongs to (same soft-failure posture as Spec 043).
- **FR-013**: Slug humanisation and meta-tag parsing MUST operate on the
  final destination URL after redirects are followed (unchanged from Spec
  043's existing redirect handling for Gemini/Grok).
- **FR-014**: When a redirect chain resolves to a final destination URL but
  the subsequent request to that destination fails (non-2xx status,
  malformed content, or any other error after the redirect itself
  succeeded), the resolver MUST still retain that final destination URL for
  slug humanisation (FR-003) — the redirect-wrapper URL MUST NOT be used for
  slug humanisation when a real destination URL was reached.

### Key Entities

- **ResearchSource** *(existing, unchanged shape)*: `title` and `url` pair
  published in the Sources list; this spec changes only how `title` is
  resolved, and adds the possibility that a source is dropped before ever
  becoming part of the returned list.
- **ResearchDigest** *(existing, unchanged shape)*: its `summary` field must
  never contain the raw appended titles block (FR-010) — the block is
  consumed during source resolution and discarded from the stored text.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a mocked fetch response with no `<title>` but a present
  `og:title`, the resolved title is `"{domain} - {og:title content}"`.
- **SC-002**: Given a mocked fetch response with no `<title>` and no
  `og:title` but a present `twitter:title`, the resolved title uses the
  `twitter:title` content.
- **SC-003**: Given a mocked `<title>` equal to the domain's first label,
  the title is rejected and resolution proceeds to the next signal.
- **SC-004**: Given a mocked `<title>` that contains the domain's first
  label within a longer, real title, the title is accepted as-is.
- **SC-005**: Given a mocked fetch failure (exception or non-2xx) for a URL
  whose path contains a descriptive hyphenated segment, the resolved title
  is the humanised slug, not the bare domain.
- **SC-006**: Given a mocked provider response whose appended titles block
  supplies a descriptive title for a URL with no other resolvable signal
  (e.g. a numeric-ID-only path), the published source uses that
  provider-supplied title, domain-prefixed.
- **SC-007**: Given a mocked provider response whose appended titles block
  references a URL absent from that response's own verified citations, that
  entry is ignored and no phantom source appears in the published list.
- **SC-008**: Given a mocked provider response with a missing or malformed
  titles block, the digest's `summary` and other sources are unaffected,
  and the affected source(s) fall through to being dropped (assuming no
  other signal resolves them).
- **SC-009**: Given a mocked provider response containing a titles block,
  the stored `ResearchDigest.summary` never contains the block's raw
  marker text or content.
- **SC-010**: Given a URL whose only path segment is numeric/hex-like, or
  whose path is empty, with no fetched signal and no provider-supplied
  title descriptive, the source is absent from the final Sources list.
- **SC-011**: Given a Claude citation whose title equals its domain's first
  label and no provider-supplied title rescues it, the source falls through
  to slug humanisation on the citation URL instead of publishing the
  domain-label-only title.
- **SC-012**: Replaying the real fixture inputs behind
  `output/newsletter/07_AI_Slop/ai_slop_myth_or_reality/uk/linkedin_post.md`
  through the updated resolver no longer produces any of `medium.com`,
  `facebook.com`, `sciencedirect.com`, `fidelity.com`, or
  `reddit.com - Reddit` as a published source line (manual/fixture-driven
  verification during implementation, matching Spec 043's SC-006 approach).
- **SC-013**: Given a mocked redirect chain that resolves to a final
  destination URL before that destination's request fails (non-2xx), a
  subsequent slug-humanisation fallback uses the resolved destination URL's
  path, not the original redirect-wrapper URL's path.
- **SC-014**: `python -m pytest tests/` passes with every network and LLM
  call mocked per Constitution §9 — zero real HTTP or API calls during the
  automated suite.

## What does NOT change

- The `"{domain} - {title}"` display format itself (Spec 043) is unchanged
  when a descriptive title is found by any signal.
- No new network call is added: `og:title`/`twitter:title` are parsed from
  the same already-fetched HTML response Spec 043 already requests; no
  second request is made.
- No new LLM call is added either: the provider-supplied title (chain step
  3) is folded into each provider's existing research call via an appended
  response section, at normal marginal per-token cost already covered by
  that call's existing token/cost tracking — no second call, no re-reading
  a source.
- No new third-party dependency — still stdlib (`urllib.parse`, `re`) plus
  `httpx`, both already in use.
- The per-provider 120s research timeout and the 5s per-URL title-fetch
  timeout (Spec 043) are unchanged.
- How each provider *discovers* sources via its own web search is untouched
  — this spec changes only how a discovered source's title is resolved (or
  whether it is dropped), never which sources are found.
- No source's URL is ever supplied or altered by an LLM: every published
  URL still traces back to a provider's own verified citation/grounding
  metadata (Spec 042 FR-011, unchanged) — only a source's title text may, as
  a last resort, be that same provider's own description of a page it has
  already verified citing.

## Assumptions

- Asking each provider to restate a descriptive title for URLs it already
  cited, in the same call, is grounded rather than fabricated — the model
  has already read that content moments earlier while performing the
  search that produced the citation, not inventing a description from
  nothing.
- Matching provider-supplied titles strictly against already-verified
  citation URLs (FR-008) is what prevents this addition from ever letting
  an LLM introduce a new, unverified source into the published list —
  loosening that match to anything fuzzier would reopen exactly the risk
  this spec's "no fabrication" posture is meant to close.
- Dropping a source outright, rather than publishing it under a
  non-descriptive label, remains the correct final safety net — even with
  the provider-supplied-title rescue in place, a bare-root URL with no path
  and no citeable content can still legitimately have nothing descriptive
  to say.
- The exact minimum word count for a valid slug segment (FR-003/FR-004), the
  precise normalisation rule for comparing a title against the domain's
  first label (FR-002), and the exact appended-block format/parser (FR-007)
  are pinned to concrete values in `plan.md`; this spec's acceptance
  criteria are the contract implementation must satisfy, not the literal
  thresholds or syntax.
- Satisfying FR-014 (retaining the resolved destination URL across a failed
  request) requires restructuring `_fetch_page_title`'s current
  try/except — which discards all response state on any exception — to
  capture the destination URL separately from whether the title-tag parse
  succeeded; this is treated as an implementation detail for `plan.md`, not
  a reason to weaken FR-014 itself.
