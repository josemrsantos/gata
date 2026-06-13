# Quickstart: Trend Scout

## 1. Get a NewsAPI.ai key

1. Go to https://eventregistry.org
2. Create a free account
3. Find your API key at https://eventregistry.org/me
4. Free tier: 1 M tokens/month — sufficient for daily pipeline runs

## 2. Add the key to .env

```bash
echo "NEWSAPI_AI_KEY=your_key_here" >> .env
```

## 3. Add news_sources to a community in communities.yaml

```yaml
communities:
  - name: uk-tech-engineers
    target_audience: British software engineers and developers
    output_language: English
    tone: dry British wit
    topics:
      - Agile ceremonies that could have been an email
    news_sources:
      - location_uri: "http://en.wikipedia.org/wiki/United_Kingdom"
        count: 10
```

Communities without `news_sources` still work — they use the seed `topics` list.

## 4. Install the new dependency

```bash
pip install httpx
# or: uv pip install httpx
```

## 5. Run Trend Scout standalone

```bash
python -m agents.trend_scout --community uk-tech-engineers
```

Expected output:
```
1. UK tech firms cut junior developer hiring as AI tools spread
2. Government mandates open-source software for public sector projects
3. Startup accelerator funding falls 40% in Q1
```

## 6. Run the full pipeline (unchanged invocation)

```bash
# Community mode — Trend Scout runs automatically if news_sources configured
python pipeline.py --community uk-tech-engineers

# Manual override — Trend Scout is bypassed entirely (RULE 12)
python pipeline.py --topic "AI replacing junior devs" --audience "British engineers" \
  --language English --tone "dry British wit"
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Falls back to seed topics unexpectedly | `NEWSAPI_AI_KEY` missing or wrong | Check `.env` |
| `Unknown community` error | `--community` name doesn't match YAML | Check `communities.yaml` |
| All headlines in wrong language | `location_uri` too broad | Use a more specific Wikipedia URI |