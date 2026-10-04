# Data Model: Single-audience default for gata

No new persisted data and no new types. The feature selects existing
`AudienceProfile` values differently.

## Audience (existing `core.types.AudienceProfile`)

- **Fields**: `name` (str, used for the output file and progress line), `audience`
  (str, description), `language` (str), `tone` (str).
- **Built-in default (new constant `_DEFAULT_AUDIENCE`)**: name `uk-tech-engineers`,
  audience `British software engineers and developers`, language `English`, tone
  `dry British wit`. "MUST match the `uk-tech-engineers` entry in `communities.yaml`,
  and a test MUST fail if they drift apart" (FR-006).
- **Built from a community**: `name` ← community `name`; `audience` ← `target_audience`;
  `language` ← `output_language`; `tone` ← `tone`. `panels`, `layout`, `topics` and
  `news_sources` are not read (FR-003a).

## Audience selection (a plain ordered `list[AudienceProfile]`, not a new type)

- **Default (no options)**: `[_DEFAULT_AUDIENCE]`.
- **`--audience` values**: the resolved profiles, in the order given, duplicates
  removed (first occurrence kept); "at least one" because argparse only builds the
  list when the flag is used.
- **`--infer-audiences`**: `_ensure_uk(infer_audiences(topic))`, unchanged.
- **Validation**: every `--audience` value is non-empty and names a community in
  `communities.yaml` (or the built-in default's own name when the file is absent);
  `--infer-audiences` and `--audience` are mutually exclusive.
- **State transitions**: none; the selection is built once, before any paid call.
