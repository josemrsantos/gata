# Research: Trend Scout

## Decision 1 — News source: NewsAPI.ai (EventRegistry)

**Decision**: Use NewsAPI.ai (https://eventregistry.org) as the first source adapter.

**Rationale**: Provides a `socialScore` field on each event — a composite of Twitter/social
engagement — which is the primary trendiness signal. Free tier: 1 M tokens/month, sufficient
for daily runs across 5 communities.

**API endpoint**: `POST https://eventregistry.org/api/v1/event/getEvents`

**Key request parameters**:
```json
{
  "action": "getEvents",
  "apiKey": "<NEWSAPI_AI_KEY>",
  "locationUri": "http://en.wikipedia.org/wiki/United_Kingdom",
  "dateStart": "<today>",
  "dateEnd": "<today>",
  "dataType": ["news"],
  "sortBy": "socialScore",
  "sortByAsc": false,
  "count": 10,
  "eventImageCount": 0,
  "includeEventSocialScore": true,
  "includeEventSentiment": false
}
```

**Response shape (abbreviated)**:
```json
{
  "events": {
    "results": [
      {
        "uri": "...",
        "title": { "eng": "Headline text" },
        "summary": { "eng": "Short abstract..." },
        "eventDate": "2026-05-29",
        "socialScore": 1542.3
      }
    ]
  }
}
```

**Alternatives considered**:
- RSS feeds: free and simple, but no social engagement signal — trendiness would be based on
  recency only
- NewsAPI.org: free tier (100 requests/day), but headline-only — no event clustering or social
  score
- Firecrawl: full-content scraper — rejected because Gemini only needs title + abstract to
  rank satirical potential

---

## Decision 2 — Ranking mechanism: Gemini JSON mode

**Decision**: Pass headlines to Gemini (`gemini-2.5-flash`) and ask it to return a JSON
array of the top-N titles ranked by satirical potential for the community profile.

**Rationale**: Gemini already has access to the community's `target_audience` and `tone`
via the brief. Asking Gemini to rank avoids hand-crafted scoring weights and handles
multilingual communities correctly (Portuguese community gets Portuguese-language ranking
reasoning).

**Prompt structure**:
```
You are ranking news headlines for satirical potential.

Community profile:
- Audience: {target_audience}
- Tone: {tone}
- Language: {output_language}

Headlines (title | social_score):
1. {title} | {score}
2. ...

Return a JSON array of the top {n} headline titles, ranked by satirical potential for this
community. Return only the JSON array — no explanation.

Example: ["Headline A", "Headline B", "Headline C"]
```

**Gemini model**: `gemini-2.5-flash` — text-only, matches constitution Principle 1.

**Alternatives considered**:
- Keyword overlap scoring: brittle, requires manual keyword lists per community
- socialScore as sole ranking: ignores community fit (a UK finance story may rank high on
  social score but be irrelevant for the Portuguese politics community)
- LLM with structured schema via `response_schema`: adds schema maintenance overhead; a plain
  JSON array prompt is simpler and sufficient

---

## Decision 3 — HTTP client: httpx

**Decision**: Use `httpx` for the NewsAPI.ai HTTP call.

**Rationale**: Modern, type-hinted, supports both sync and async. Clean timeout/error
handling. Consistent with the project's Python 3.12 target.

**Alternatives considered**:
- `requests`: widely used but no async support; acceptable but `httpx` is preferred for new code
- `urllib`: too low-level

---

## Decision 4 — Source adapter location filter

**Decision**: Each community in `communities.yaml` lists one or more `location_uris`
(Wikipedia URIs for countries/regions) under `news_sources`. If omitted, no location filter
is applied — the adapter fetches global top stories.

**Rationale**: UK communities need UK-specific news; Portuguese communities need PT/EU news.
A single global feed would mix contexts incorrectly.

**`communities.yaml` extension (new optional field)**:
```yaml
news_sources:
  - location_uri: "http://en.wikipedia.org/wiki/United_Kingdom"
    count: 10
```

---

## Decision 5 — Fallback behaviour

**Decision**: If `get_topics()` returns an empty list (network error, API error, no results),
the caller falls back to `random.choice(community.topics)`. Trend Scout logs a WARNING with
the reason but does not raise.

**Rationale**: Pipeline must always produce a cartoon. A missing news source is a WARNING,
not a fatal error. The seed topic list is the safety net.

---

## Decision 6 — Standalone CLI entry point

**Decision**: `agents/trend_scout.py` includes a `__main__` block so it can be invoked as
`python -m agents.trend_scout --community <name>`. It prints the ranked topic list and exits.

**Rationale**: Supports manual inspection and debugging without running the full pipeline.
Satisfies the "independent" requirement from the developer.