# Data Model: Tag-free, JSON-free panel responses

No persisted data changes. In-memory types only.

## ParseContext (new, `llm/reply_parsing.py`, frozen dataclass)
| Field | Type | Meaning |
|-------|------|---------|
| agent | str | panel name, e.g. `Satirist/Co-Satirist` |
| role | str | panelist name or `Aggregator` |
| round | int | panel round (aggregator uses the last round) |
| model | str | model that answered (`TokenUsage.model`, so fallbacks are honest) |
| stop_reason | str \| None | provider stop/finish reason if exposed |
| output_tokens | int \| None | tokens produced by the call |
| max_tokens | int \| None | the persona's limit, so truncation is visible |

## TokenUsage (extended, `core/types.py`)
New field `stop_reason: str | None = None` (default keeps all existing constructors valid). Not used by
cost or telemetry totals.

## Labelled reply (text grammar, see contracts/reply-formats.md)
`LABEL: value` lines; a value runs until the next known label. Satirist: `PANELS`, `LAYOUT`, `TITLE`,
then `PANEL n` blocks with `SCENE`, `CAPTION`, `BEAT`. Required vs defaulted fields per spec FR-006:

| Field | Missing → |
|-------|-----------|
| `PANEL n` block (none at all) | unusable → one retry |
| `SCENE` | unusable → one retry |
| `BEAT` (2+ panels, empty) | unusable → one retry |
| `TITLE` | topic text, logged |
| `CAPTION` | empty, logged |
| `LAYOUT` | CLI value, else auto layout, logged |
| `PANELS` | count of `PANEL n` blocks (never trusted over the blocks) |

## Domain classification line
`<domain>: <paywalled|free>, <high|low>` — words in any order, case/bullets/spacing ignored. Unreadable or
absent domain → today's default (unclassified), logged with the domain named.
