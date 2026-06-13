# Quickstart: Free-Text Community Mode

## Run with a free-text community description

```bash
# No entry in communities.yaml required
python pipeline.py --community "US community that dislikes Trump"

# French-speaking audience — output language inferred as French
python pipeline.py --community "Communauté française qui critique Macron"

# Existing named communities still work identically
python pipeline.py --community uk-politics
```

## What happens under the hood

1. Pipeline checks `communities.yaml` for `"US community that dislikes Trump"` — no match found.
2. Gemini infers: `target_audience="US adults critical of Trump-era policies"`, `output_language="English"`, `tone="sharp political satire"`.
3. NewsAPI.org fetches top headlines for US and GB.
4. Gemini ranks the headlines by relevance to `"US community that dislikes Trump"`.
5. Top headline is passed to the Cultural Strategist and the rest of the pipeline — identical to named-community flow.
6. Bundle saved to `output/us_community_that_dislikes_trump/<language>_<topic>.png`.

## Environment variables (unchanged)

```
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
NEWSAPI_ORG_KEY=...
```

## Logs to watch

```
INFO  pipeline: community description not found in communities.yaml — using free-text inference
INFO  trend_scout: inferred brief: audience='...' language='...' tone='...'
INFO  trend_scout: free-text mode ranked N topics from M headlines via Gemini
```
