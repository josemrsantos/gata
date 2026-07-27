# Research: Provider Pricing & Model Currency (2026-07-27)

Sources fetched directly from each provider's official docs (not aggregator/SEO
blogs, which disagree with official docs and each other on several points).

## Claude (Anthropic)

Source: [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing)

| Model | Input | Output | Status |
|---|---|---|---|
| claude-sonnet-4-6 | $3 / MTok | $15 / MTok | Active — matches current `llm/claude.py` entry |
| claude-sonnet-4-5 | $3 / MTok | $15 / MTok | Active — matches current entry |
| claude-haiku-4-5(-20251001) | $1 / MTok | $5 / MTok | Active — **current entry is wrong**: code has (0.80, 4.00), i.e. the old Haiku 3.5 rate |
| claude-opus-4-8 | $5 / MTok | $25 / MTok | Active — **current entry is wrong**: code has (15.00, 75.00) |
| claude-opus-4-7 | $5 / MTok | $25 / MTok | Active — **current entry is wrong**: code has (15.00, 75.00) |
| claude-opus-5 | $5 / MTok | $25 / MTok | New, not in cost table |
| claude-sonnet-5 | $2/$10 (intro, through 2026-08-31), then $3/$15 | New, not in cost table |
| claude-haiku-3.5 | $0.80 / MTok | $4 / MTok | Retired except Bedrock/GCP |
| claude-opus-4.1 / opus-4 | $15 / MTok | $75 / MTok | Retired except Bedrock/GCP |

No model referenced in this codebase (`claude-sonnet-4-6`, `claude-haiku-4-5-20251001`,
`claude-opus-4-7`) is deprecated. This provider only needs **price-table corrections**,
not a model swap. Two of the three current cost-table entries are stale — they still
carry the old Opus/Haiku rates from before a repricing.

## Gemini (Google)

Sources: [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing),
[ai.google.dev/gemini-api/docs/deprecations.md.txt](https://ai.google.dev/gemini-api/docs/deprecations.md.txt)

| Model | Input | Output | Status |
|---|---|---|---|
| gemini-2.5-flash | $0.30 / MTok | $2.50 / MTok | Active — matches current entry. **Shuts down 2026-10-16** → `gemini-3.6-flash` |
| gemini-2.5-pro | $1.25 (≤200k) / $2.50 (>200k) per MTok | $10.00 (≤200k) / $15.00 (>200k) per MTok | Active — code's flat (1.25, 10.00) matches the ≤200k tier, no change needed. **Shuts down 2026-10-16** → `gemini-3.1-pro-preview` |
| gemini-2.0-flash | — | — | **DEAD.** Shut down 2026-06-01. Replacement: `gemini-3.6-flash` (or `gemini-3.1-flash-lite` for the lite variant) |
| gemini-2.5-flash-image | $0.30 / MTok | $0.039 / image (flat, not per-token) | Active — matches current entry. Shuts down 2026-10-02 → `gemini-3.1-flash-image-preview` |
| gemini-3.1-flash-image(-preview) | $0.50 / MTok | $60.00 / MTok | Active — matches current entry exactly |
| gemini-3.1-flash-lite | $0.25 / MTok | $1.50 / MTok | **Current entry is wrong**: code has (0.10, 0.40) — that was the old promo/launch rate |
| gemini-3.1-pro-preview | $2.00 (≤200k) / $4.00 (>200k) per MTok | $12.00 (≤200k) / $18.00 (>200k) per MTok | **Current entry is wrong**: code has (1.25, 10.00) — that's the 2.5-pro rate, not 3.1-pro's |

`gemini-2.0-flash` is used today as the last-resort fallback in `core/runner.py`
(`_FALLBACK` chains) and `agents/agent_cultural_strategist.py`. Any run that falls
through to it today gets a hard API error, not a graceful degrade — the fallback
chain's safety net has a hole in it right now.

`gemini-2.5-flash` / `gemini-2.5-pro` (today's primary Gemini models) are not yet
dead, but both retire 2026-10-16 — about 11 weeks from today. Migrating the primary
models is a bigger call (new pricing tier, possible quality/latency shift) and is
flagged as an assumption/open question below rather than folded silently into this
pricing-table fix.

## Grok (xAI)

Sources: [docs.x.ai/docs/models](https://docs.x.ai/docs/models),
[docs.x.ai/developers/migration/may-15-retirement](https://docs.x.ai/developers/migration/may-15-retirement)

| Model | Input (<200k / ≥200k) | Output (<200k / ≥200k) | Status |
|---|---|---|---|
| grok-4.5 | $2.00 / $4.00 | $6.00 / $12.00 | Active, flagship |
| grok-4.3 | $1.25 / $2.50 | $2.50 / $5.00 | Active, cheaper tier |
| grok-build-0.1 | $1.00 / $2.00 | $2.00 / $4.00 | Active, cheapest tier (code-oriented) |
| grok-3, grok-3-mini, grok-3-fast, grok-3-mini-fast | — | — | **Confirmed retired by live API call** (2026-07-27, `set_gata.sh` credentials, `max_tokens=10` smoke test on each): all four slugs return HTTP 200 but the response's `model` field comes back as `grok-4.3` — every one of them is silently redirected and billed at `grok-4.3` rates ($1.25/$2.50), regardless of which of the four was requested |

This is the provider with a real functional problem, not just stale numbers. Live
verification (not just docs) confirms:

- `providers.yaml` (aggregator), `core/runner.py` (`_GROK_AGGREGATOR`), and
  `core/bundle_writer.py` default to `grok-3`. It still works via redirect today, but
  bills at `grok-4.3` rates while our `_COST_PER_M` table still charges it at the old
  `grok-3` rate ($3.00/$15.00), so telemetry has been **overstating** Grok aggregator
  cost by roughly 2.4x since the May 15 retirement.
- `providers.yaml` (panelists), `core/runner.py` (`_PARALLEL_PANELISTS`), and
  `core/bundle_writer.py` default to `grok-3-mini` for the cheap panelist slot. It
  also redirects to `grok-4.3` — **the same model the aggregator now resolves to**.
  This quietly breaks the Spec 029 / constitution §6 design intent that the Grok
  panelist and the Grok aggregator be different models ("not both judge and sole
  proposer"): today, both roles are silently the same underlying model.
  `_COST_PER_M`'s old grok-3-mini rate ($0.30/$0.50) is ~4x under the real billed
  rate ($1.25/$2.50).
- `grok-4.5`, `grok-4.3`, and `grok-build-0.1` all resolved to themselves (no
  redirect) in the same live check — these are the genuinely current models.

**Decision** (resolves the spec's open question): aggregator → `grok-4.3` (the
documented redirect target, matches what's already being billed); panelist →
`grok-build-0.1` (cheapest genuinely-live model, restores the "aggregator ≠
panelist" distinction that the grok-3/grok-3-mini redirect had collapsed).

## Summary of required code changes (implementation deferred to plan.md)

1. `llm/claude.py` — fix Opus 4.7/4.8 and Haiku 4.5 rates; add Sonnet 5 / Opus 5 entries.
2. `llm/gemini.py` — fix 3.1-flash-lite and 3.1-pro-preview rates; remove/flag
   `gemini-2.0-flash` (dead) and pick its replacement.
3. `llm/grok.py` — add `grok-4.5`/`grok-4.3`/`grok-build-0.1` rows at their real
   rates; keep `grok-3`/`grok-3-mini`/`grok-3-fast`/`grok-3-mini-fast` as deprecated
   aliases priced at the `grok-4.3` rate (what they actually bill now, confirmed
   live), so any leftover custom `providers.yaml` still gets a correct cost instead
   of a silent $0.00.
4. `providers.yaml`, `core/runner.py`, `core/bundle_writer.py` — swap default model
   IDs off retired/dead slugs: `grok-3` → `grok-4.3` (aggregator), `grok-3-mini` →
   `grok-build-0.1` (panelist, confirmed live to stay distinct from the `grok-4.3`
   aggregator), `gemini-2.0-flash` → `gemini-2.5-flash-lite` (active today, cheap,
   matches the "last-resort cheap fallback" role better than Google's literal
   suggested replacement `gemini-3.6-flash`, which costs 5x more than the primary
   `gemini-2.5-flash` model it would be a fallback for).
5. `.specify/memory/constitution.md` §1 and §6 — these hardcode `grok-3` as the
   aggregator model by name. Changing the default model requires a constitution
   amendment per the Amendment Procedure (project-lead approval), not just a code
   edit.
6. README.md, docs/architecture.md, CHANGELOG.md — RULE 17 doc-sync gate.
7. Tests referencing old model IDs/prices (`tests/test_grok_provider.py`,
   `tests/test_providers_config.py`, `tests/test_agent_satirist.py`, etc.).
