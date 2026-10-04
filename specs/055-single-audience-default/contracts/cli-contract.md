# Contract: `gata` audience selection

The user-visible interface of this feature. Everything not listed is unchanged.

## Command forms

| Command | Audiences generated | Audience-guessing call |
|---|---|---|
| `gata "T"` | exactly one: `uk-tech-engineers` (built in) | none |
| `gata "T" --audience A` | exactly one: community `A` | none |
| `gata "T" --audience A --audience B` | two, in that order | none |
| `gata "T" --infer-audiences` | today's: guessed audiences, `UK public` added if none is UK | yes (as today) |
| `gata "T" --research-only` | one report, for the default audience | none |
| `gata "T" --audience A --audience B --research-only` | one report, for `A`; a warning says `B` is ignored | none |
| `gata "T" --infer-audiences --research-only` | one report, first guessed audience (as today) | yes |

Repeated identical `--audience` values run once. All other options (`--direct`,
`--html`, `--no-title`, `--linkedin-post`, `--angle`, `--verbose`) apply to every
selected audience exactly as today.

## Output

- One image per audience: `<topic-folder>/<audience-name>.png`
  (default: `uk-tech-engineers.png`).
- Progress line per audience: `[i/N] <audience-name> — <language>`.
- Cost: `summary.txt` always written; the on-screen grand total is shown when more
  than one audience ran (unchanged).

## Errors (all exit status 1, before any paid call; logged at ERROR like the API-key errors, so they show as `ERROR: <message>`)

| Situation | Message (wording fixed by tests, shown after `ERROR: `) |
|---|---|
| unknown `--audience` value | `unknown audience 'X' — valid audiences: <comma-separated names>` |
| empty `--audience ""` | same message, naming the empty value |
| `communities.yaml` absent and a name other than `uk-tech-engineers` | `communities.yaml not found in the current folder — only the built-in audience 'uk-tech-engineers' is available (got 'X')` |
| `communities.yaml` present but invalid | `<the loader's message>` |
| `--infer-audiences` with `--audience` | `--infer-audiences and --audience cannot be used together` |

## Help text

`gata --help` states the default audience, describes `--audience` (repeatable,
names from `communities.yaml`) and `--infer-audiences`.

## Compatibility

The change of default is intentional and breaking for anyone relying on the guessed
audiences or on the always-added UK audience: they now add `--infer-audiences`.
