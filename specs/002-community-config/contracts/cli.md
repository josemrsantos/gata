# CLI Contract: Stage 2 Community Configuration

**Branch**: `002-stage-2-community-config` | **Date**: 2026-05-03

---

## Invocation Patterns

### Pattern 1 — Random community mode (no arguments)

```
python pipeline.py
```

- Loads `communities.yaml` from project root
- Selects one community at random (uniform distribution)
- Selects one topic at random from that community's list
- Runs full pipeline; saves output to `output/{community_name}/{topic}.png`

### Pattern 2 — Named community mode

```
python pipeline.py --community <name>
```

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--community` | `str` | No | Name of the community as it appears in `communities.yaml` |

- Loads `communities.yaml` from project root
- Looks up the community by name (exact match, case-sensitive)
- Selects one topic at random from that community's list
- Runs full pipeline; saves output to `output/{community_name}/{topic}.png`

### Pattern 3 — Manual mode

```
python pipeline.py --topic <text> --audience <text> --language <text> --tone <text>
```

| Argument | Type | Required | Maps to | Description |
|----------|------|----------|---------|-------------|
| `--topic` | `str` | Yes (in manual mode) | topic string | The news topic for this run |
| `--audience` | `str` | Yes (in manual mode) | `StrategyBrief.target_audience` | Target audience description |
| `--language` | `str` | Yes (in manual mode) | `StrategyBrief.output_language` | Output language for the cartoon |
| `--tone` | `str` | Yes (in manual mode) | `StrategyBrief.tone` | Satirical tone |

- Does NOT load or validate `communities.yaml`
- Runs full pipeline with the supplied values
- Saves output to `output/manual/{topic}.png` (topic sanitized by the same rules)

---

## Mutual Exclusion Rules

| Condition | Behaviour |
|-----------|-----------|
| `--community` only | Named community mode |
| No arguments | Random community mode |
| `--topic` + `--audience` + `--language` + `--tone` | Manual mode |
| `--community` + any of `--topic/--audience/--language/--tone` | **ERROR** — exits before any API call with message: `"Error: --community and manual mode flags (--topic, --audience, --language, --tone) are mutually exclusive"` |
| Any manual flag present but not all four | **ERROR** — exits before any API call with message: `"Error: manual mode requires all four flags: --topic, --audience, --language, --tone"` |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Pipeline completed successfully; image saved |
| `1` | Any error: config validation failure, argument conflict, API failure, image extraction failure |

---

## Log Output (INFO level, written before any API call)

**Community mode**:
```
2026-05-03 10:00:00 [pipeline] INFO Selected community: uk-tech-engineers
2026-05-03 10:00:00 [pipeline] INFO Selected topic: Agile ceremonies that could have been an email
2026-05-03 10:00:00 [pipeline] INFO Output path: output/uk_tech_engineers/agile_ceremonies_that_could_have_been_an_ema.png
```

**Manual mode**:
```
2026-05-03 10:00:00 [pipeline] INFO Manual mode — topic: AI hype
2026-05-03 10:00:00 [pipeline] INFO Output path: output/manual/ai_hype.png
```

---

## Error Message Examples

| Scenario | Error message (stderr) |
|----------|----------------------|
| `communities.yaml` not found | `Error: communities.yaml not found at /path/to/project/communities.yaml` |
| Invalid YAML | `Error: communities.yaml is not valid YAML: <parse error detail>` |
| Missing field in community | `Error: community "uk-tech-engineers" is missing required field: topics` |
| Empty topics list | `Error: community "uk-tech-engineers" has an empty topics list` |
| Duplicate community name | `Error: duplicate community name "uk-tech-engineers" in communities.yaml` |
| Unknown community name | `Error: community "unknown-name" not found in communities.yaml` |
| Argument conflict | `Error: --community and manual mode flags (--topic, --audience, --language, --tone) are mutually exclusive` |
| Incomplete manual flags | `Error: manual mode requires all four flags: --topic, --audience, --language, --tone` |
