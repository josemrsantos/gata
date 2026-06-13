# CLI Contract: Trend Scout standalone

## Invocation

```bash
python -m agents.trend_scout --community <community-name> [--top N]
```

## Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--community` | Yes | — | Community name as defined in `communities.yaml` |
| `--top` | No | `3` | Number of ranked topics to return |

## Output (stdout)

One topic per line, ranked by satirical potential (highest first):

```
1. Headline text A
2. Headline text B
3. Headline text C
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Topics returned (from NewsAPI.ai or fallback) |
| 1 | Unknown community name |
| 2 | Missing required env vars (`GEMINI_API_KEY` or `NEWSAPI_AI_KEY`) |

## Environment variables required

| Variable | Description |
|----------|-------------|
| `NEWSAPI_AI_KEY` | NewsAPI.ai (EventRegistry) API key |
| `GEMINI_API_KEY` | Gemini API key (already used by pipeline) |

## Examples

```bash
# Fetch today's top 3 topics for the UK tech community
python -m agents.trend_scout --community uk-tech-engineers

# Fetch top 5
python -m agents.trend_scout --community uk-tech-engineers --top 5

# Community with no news_sources configured — returns seed topics from YAML
python -m agents.trend_scout --community portuguese-adults
```

## Pipeline integration contract

`get_topics(community: Community, n: int = 3) -> list[str]`

- Returns a list of topic strings, length 1–n
- Returns `[]` only if both news fetch and seed topic list are empty (never raises)
- Caller is responsible for fallback when `[]` is returned