# Data Model: Model currency refresh II

No new runtime data structures or persisted data. The feature edits existing
constant tables. The entities below are the existing shapes plus the one
document this feature records.

## Default model assignment (existing)

A model identifier in an ordered chain for a role. Roles: panelist, aggregator,
Gemini inference/evaluator chain, trend-scout, image generation, newsletter text.

- **Fields**: provider (claude | gemini | grok), model id (string), position in
  chain (order is significant and unchanged).
- **Validation**: model id exists in that provider's price table; not on the
  retired list; Grok panelist and aggregator differ (§6).

## Price entry (existing)

`model id → (input $/MTok, output $/MTok)` per provider module
(`llm/claude.py`, `llm/gemini.py`, `llm/grok.py`); Gemini image models carry the
image-output rate as the output value.

- **Validation**: value equals the provider's published rate on the verification
  date; entries for retired models are removed, except an alias the provider
  still bills (FR-005).
- **State**: Active → Deprecated (kept until retirement date) → Retired
  (removed at the next refresh).

## Verification record (this feature's document)

Lives in `research.md`; not code.

- **Fields**: model id, tier, state, price, source URL, verification date,
  live-call result (filled in during implementation, see `quickstart.md`).
