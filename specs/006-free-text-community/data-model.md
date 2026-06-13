# Data Model: Free-Text Community Mode

## Entities

### Ad-hoc Community (transient — not persisted)

There is no new stored entity. An ad-hoc community exists only as a `StrategyBrief` for the duration of a single pipeline run. It is produced by `infer_brief_from_description()` and consumed identically to a named community's brief via `community.to_brief()`.

No schema changes to `communities.yaml` are required.

### StrategyBrief (existing, unchanged)

```
StrategyBrief
  target_audience : str   — e.g. "US adults critical of Trump-era policies"
  output_language : str   — e.g. "English"
  tone            : str   — e.g. "sharp political satire"
```

This is what `infer_brief_from_description()` returns. It is already the common currency between the community config path and the pipeline's downstream agents.

## State Transitions

None. Free-text mode is a lookup path, not a state machine. The pipeline enters the same `_run_pipeline()` call regardless of whether the brief came from config or inference.

## Inference JSON contract (internal)

Gemini is asked to return exactly this JSON shape when inferring a brief:

```json
{
  "target_audience": "...",
  "output_language": "...",
  "tone": "..."
}
```

Parsing uses `json.loads()` after stripping any markdown fences. If any key is absent or blank, the corresponding default is applied (see research.md Decision 2).
