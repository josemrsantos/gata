# Contract: reply formats

What each agent asks the model for (prompt contract) and what the parser accepts (tolerance).

## All panelists except Satirist and Domain Classification
- **Ask**: just the answer; no wrapper. Cultural Strategist keeps its `CULTURAL ANGLE:` / `REFERENCES:` /
  `JOKE TYPE:` lines; LinkedIn Angle Planning/Writing keep their existing section labels; Explainer returns
  the HTML page; Engagement Image returns the image prompt text.
- **Accept**: the whole reply; a closed or unclosed `<verdict>` wrapper is unwrapped (legacy); one
  surrounding code fence is removed. Empty reply → unusable.

## Aggregator (every panel)
```
PICK: 2
<the chosen answer, in the panel's own format>
```
- **Accept**: `PICK: N` anywhere on its own line (bold/bullet tolerated); the rest is the verdict. No
  `PICK` line → pick unknown (as today), whole reply is the verdict.

## Satirist
```
PANELS: 3
LAYOUT: vertical
TITLE: <3–8 word headline in the output language>
PANEL 1
SCENE: ...
CAPTION: ...
BEAT: ...
PANEL 2
...
```
- **Accept**: label drift (`Scene 1:`, `**CAPTION**:`, `## Panel 1`), markdown emphasis, a code fence, and
  the legacy JSON object. Panel count = number of `PANEL n` blocks. Required/default rules: data-model.md.
- Single-panel: `SCENE` carries Gata's full description verbatim (Constitution §4) — unchanged rule.

## LinkedIn Domain Classification
```
nytimes.com: paywalled, high
some-blog.com: free, low
```
- **Accept**: `paywalled`/`free` and `high`/`low` in any order; case, bullets and extra spaces ignored.
  Absent/unreadable domain → default, logged. Legacy JSON object still accepted.

## Failure log line (every parse failure or fallback)
`WARNING <agent>/<role> round <n> [<model>, stop_reason=<x>, output_tokens=<a>/<max>]: <field> <problem>
— applied <default>; reply starts: '<first 400 chars>'`
