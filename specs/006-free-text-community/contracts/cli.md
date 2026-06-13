# CLI Contract: --community flag

## Current behaviour (named-community mode)

```
python pipeline.py --community <NAME>
```

`NAME` must exactly match a `name:` field in `communities.yaml`. If not found, the pipeline exits with an error.

## New behaviour (free-text mode)

```
python pipeline.py --community "<free-text description>"
```

`<free-text description>` is any non-empty string. The pipeline:

1. Checks `communities.yaml` for an exact name match.
2. If found: uses the named-community path (unchanged behaviour).
3. If not found (or `communities.yaml` is absent): enters free-text mode — infers audience/language/tone, fetches and ranks general headlines.

## Validation

| Input | Result |
|-------|--------|
| Exact match in communities.yaml | Named-community path |
| Any non-empty string not in communities.yaml | Free-text inference path |
| Empty string `""` | Exit with error: `--community must not be empty` |
| Not provided | Random community mode (unchanged) |

## Exit codes

| Condition | Exit code |
|-----------|-----------|
| Success | 0 |
| Empty `--community` | 1 |
| No headlines returned for community | 1 |
| API key missing | 1 |

## Output path

| Mode | Output path pattern |
|------|-------------------|
| Named community | `output/<sanitized-name>/<sanitized-language>_<sanitized-topic>.png` |
| Free-text community | `output/<sanitized-description>/<sanitized-language>_<sanitized-topic>.png` |
| Manual | `output/manual/<sanitized-language>_<sanitized-topic>.png` |
