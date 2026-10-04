# Research: Model currency refresh II

**Verification date**: 2026-10-04 (all claims below are dated to this day)
**Method (FR-001)**: official provider documentation fetched on the date above,
then — before any code merges — one short real call per distinct default model
(see `quickstart.md`). Claims marked **[docs-only]** are not confirmed by a live
call yet. The fetch tool summarises pages, so Gemini and xAI rows that rest on a
single summary are re-confirmed by the live call.

## 1. Claude (Anthropic) — verified from three official pages

Sources: `platform.claude.com/docs/en/about-claude/models/overview`,
`.../about-claude/pricing`, `.../about-claude/model-deprecations`.

Complete list of every non-retired model on the pricing and deprecations pages
as of 2026-10-04 ("Used" = referenced by a default/chain today or after this
feature; "price only" = kept in the cost table because the API still serves it):

| Model ID | Tier | State | $/MTok in/out | Earliest retirement | Used |
|---|---|---|---|---|---|
| `claude-fable-5-1` | Fable | Active | 10 / 50 | 2027-09-01 | price only |
| `claude-fable-5` | Fable | Active | 10 / 50 | 2027-06-09 | price only |
| `claude-mythos-5-1`, `claude-mythos-5` | Mythos | Active, **invitation-only** (Project Glasswing) | 10 / 50 | 2027-09-01 / 2027-06-09 | not priced (not generally accessible) |
| `claude-mythos-preview` | Mythos | Deprecated 2026-06-09, retirement TBA | not on pricing page | TBA | not priced |
| `claude-opus-5-5` | Opus | Active | 4 / 20 | 2027-09-22 | **default chain** (new) |
| `claude-opus-5` | Opus | Active | 5 / 25 | 2027-07-24 | price only (already in table) |
| `claude-opus-4-8` | Opus | Active | 5 / 25 | 2027-05-28 | price only (already in table) |
| `claude-opus-4-7` | Opus | Active | 5 / 25 | 2027-04-16 | in chain today; replaced by 5-5 |
| `claude-opus-4-6` | Opus | Active | 5 / 25 | 2027-02-05 | price only (**add**) |
| `claude-opus-4-5-20251101` (alias `claude-opus-4-5`) | Opus | Active | 5 / 25 | 2026-11-24 | price only (**add both IDs**) |
| `claude-sonnet-5-5` | Sonnet | Active | 2 / 10 | 2027-09-28 | **default** (new) |
| `claude-sonnet-5` | Sonnet | Active | 2 / 10 | 2027-06-30 | price only (**fix price**) |
| `claude-sonnet-4-6` | Sonnet | Active | 3 / 15 | 2027-02-17 | in defaults today; replaced by 5-5 |
| `claude-sonnet-4-5-20250929` (alias `claude-sonnet-4-5`) | Sonnet | **Deprecated** 2026-09-30 | 3 / 15 | **2026-11-30** | price only (add dated ID; alias exists) |
| `claude-haiku-4-5-20251001` (alias `claude-haiku-4-5`) | Haiku | Active | 1 / 5 | **2026-10-15** (not sooner than) | **default** (kept) |

Retired and therefore **not** kept in the table: Opus 4.1, Opus 4, Sonnet 4,
Haiku 3.5 and older.

**Decisions**
- **D-C1** `claude-sonnet-4-6` → `claude-sonnet-5-5` (same tier, newest stable).
  Price drops 3/15 → 2/10. *Alternatives*: stay on 4.6 (still Active) — rejected,
  policy is newest stable same-tier.
- **D-C2** `claude-haiku-4-5-20251001` — **no change**. No newer Haiku exists in
  the documentation, so there is no successor. Retirement is "not sooner than
  2026-10-15", i.e. 11 days away, with no replacement named. Flagged for the
  project lead (see §5, item 3).
- **D-C3 (price bug)** `claude-sonnet-5` is in `llm/claude.py` at 3.00/15.00, but
  Anthropic states the introductory 2/10 is now the standard price and the 9/1
  increase "will not occur". Correct to 2.00/10.00.
- **D-C5** `claude-opus-4-7` (in `_CLAUDE_CHAIN` and the newsletter Claude
  list) → `claude-opus-5-5` (Opus tier, newest stable). Price drops 5/25 → 4/20.
- **D-C4** Price table = every non-retired, generally available model in the
  table above: ADD `claude-sonnet-5-5` (2/10), `claude-opus-5-5` (4/20),
  `claude-opus-4-6` (5/25), `claude-opus-4-5-20251101` and `claude-opus-4-5`
  (5/25), `claude-sonnet-4-5-20250929` (3/15), `claude-fable-5-1` and
  `claude-fable-5` (10/50); FIX `claude-sonnet-5`. KEEP `claude-sonnet-4-5`
  (alias), `-4-6`, opus 4-7/4-8/5 and haiku. Mythos is not priced (invitation
  only). Lookups are exact-string, so a model with an alias and a dated ID needs
  both keys. `claude-sonnet-4-5*` and `claude-opus-4-5*` retire 2026-11-30 /
  2026-11-24 at the earliest: remove them in the next refresh after those dates
  (FR-005: still billed until then).

## 2. Gemini (Google) — docs fetched; live call confirms

Sources: `ai.google.dev/gemini-api/docs/models`, `.../pricing`,
`.../deprecations`, `.../changelog`. Two fetches disagreed on one point (below).

| Model code | State | $/MTok in/out |
|---|---|---|
| `gemini-3.8-flash` | Stable (newest Flash) | 0.75 / 3.75 until 2026-12-31, then 1.50 / 7.50 |
| `gemini-3.5-flash` | Stable | 1.50 / 9.00 |
| `gemini-3.5-flash-lite` | Stable (newest Flash-Lite) | 0.30 / 2.50 |
| `gemini-3.1-flash-lite` | Stable | 0.25 / 1.50 |
| `gemini-3.1-pro-preview` | **Preview only** (no stable Pro 3.x) | 2.00 / 12.00 |
| `gemini-2.5-flash` / `-pro` / `-flash-lite` | **Limited access to prior users since 2026-09-18**; no shutdown announced | 0.30/2.50, 1.25/10.00, 0.10/0.40 |
| `gemini-3.1-flash-image` | Stable | 0.50 in; image out 60.00 (≈$0.067/1K image) |
| `gemini-3-pro-image` | Stable | 2.00 in; image out 120.00 (≈$0.134/1K–2K) |
| `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview` | Docs: GA'd 2026-05-28, previews shut down 2026-06-25. **Live check 2026-10-04: still generates images** | still billed (works) |
| `gemini-2.5-flash-image` | Docs conflict (shut down 2026-10-02 vs 2026-01-15). **Live check 2026-10-04: still generates images** | still billed (works) |

**Decisions**
- **D-G1** `gemini-2.5-flash` → `gemini-3.8-flash` (Flash tier, newest stable) —
  **only if the live check shows 2.5 no longer works** (lead's condition,
  2026-10-04). **Live result: `gemini-2.5-flash` still works → HOLD, no move.**
  **Cost effect**: input 0.30 → 0.75 (+150%), output 2.50 → 3.75 (+50%) until
  2026-12-31, then 1.50/7.50 (5× / 3×). Moves are mandated by policy A, but the
  lead must see this (§5, item 2). A follow-up price edit is due after 2026-12-31.
- **D-G2** `gemini-2.5-flash-lite` → `gemini-3.5-flash-lite` (0.30/2.50).
  **Live result: `gemini-2.5-flash-lite` returns 404 "no longer available to new
  users" for our key → GO.** This one is already a dead fallback today.
- **D-G3** `gemini-2.5-pro` — **no change (preview only)**: the only 3.x Pro is
  `gemini-3.1-pro-preview`, and Q4 forbids preview-only successors. It is still
  served (limited access), no shutdown announced.
- **D-G4** Image chain: replace the two `-preview` names with their GA names and
  drop `gemini-2.5-flash-image`; result `gemini-3.1-flash-image` →
  `gemini-3-pro-image` (existing order kept, FR-003). **Correction (live check,
  2026-10-04):** the preview names and `gemini-2.5-flash-image` still generate
  images today, so the earlier claim that every run wastes a failing call on a
  retired model was wrong. The move is still made because Google's docs
  announce those names as shut down, so they can stop at any time.
- **D-G5** Price table: add `gemini-3.8-flash`, `gemini-3.5-flash-lite`,
  `gemini-3.5-flash`. **Keep** the three image names above (they still respond,
  so under FR-005 they are still-billed names; changed from the earlier plan to
  remove them). Keep `gemini-3.1-flash-lite`, `gemini-3.1-pro-preview`, the 2.5
  text rows, `gemini-3.1-flash-image` (0.50/60.00) and `gemini-3-pro-image`
  (2.00/120.00). Existing prices for these already match docs.
- **Risk**: `gemini-2.5-*` limited access means a key without prior 2.5 usage
  would fail on the retained `gemini-2.5-pro` aggregator fallback and as the old
  flash defaults; the live call confirms our key still has access.

## 3. Grok (xAI) — docs fetched; live call confirms

Sources: `docs.x.ai/docs/models`, `docs.x.ai/docs/models/grok-build-0.1`,
`docs.x.ai/docs/release-notes` (`/docs/deprecations` returned 404).

| Model ID | $/MTok in/out (<200k prompt) | Notes |
|---|---|---|
| `grok-4.7` | 2.00 / 6.00 | newest, released 2026-09 |
| `grok-4.6` | 2.00 / 6.00 | 2026-08 |
| `grok-4.5` | 2.00 / 6.00 | 2026-07 |
| `grok-4.3` | 1.25 / 2.50 | no retirement or successor announced |
| `grok-build-0.1` | 1.00 / 2.00 | coding model (early access 2026-05); no retirement or successor announced |

**Decisions**
- **D-X1** `grok-build-0.1` (panelist) — **no change**: no successor in its line.
- **D-X2** `grok-4.3` (aggregator) — **no change (approved by the lead, 2026-10-04)**.
  xAI has no tier names, so "same tier" is not defined for Grok. 4.5/4.6/4.7 are
  newer but priced 2.00/6.00 (+60% input, +140% output). Keeping 4.3 respects
  the cost-stable policy; moving to 4.7 gives the final decider the newest
  model. §6 also requires panelist ≠ aggregator, which holds either way.
- **D-X3** Price table: add `grok-4.6`, `grok-4.7` (2.00/6.00); rows for
  4.5, 4.3, build-0.1 already match.
- **D-X4** The retired `grok-3*` aliases priced at 4.3's rate (Spec 039): the
  docs no longer mention them, so the redirect is unconfirmed. The live check
  includes one `grok-3` call; if it still redirects/bills as 4.3 keep the alias,
  otherwise drop it (FR-005). No removal without evidence.

## 4. Where model names live (blast radius)

`providers.yaml`; `llm/claude.py`, `llm/gemini.py`, `llm/grok.py` (price tables);
`core/runner.py` (inference + Grok chains); `core/image_generation.py` (image
chain); `core/newsletter_merge.py` (newsletter chains); `core/bundle_writer.py`
(fallback defaults); `agents/agent_cultural_strategist.py`
(`_INFERENCE_MODELS`); `agents/trend_scout.py` (`_GEMINI_MODEL`); constitution
§1/§6; README and `docs/architecture.md`; tests that cite names or prices.
The Image Evaluator has no model names of its own: `_GEMINI_EVAL_CHAIN` in
`core/runner.py` is the same list as `_GEMINI_PRO_CHAIN`, so it moves with it.

## 5. Lead decisions (answered 2026-10-04; see plan.md)

1. **Constitution amendment v1.3** (FR-007) — §1 model names change (Sonnet
   `claude-sonnet-5-5`, Gemini image `gemini-3.1-flash-image`, Gemini text
   primary `gemini-3.8-flash`). Not written until explicitly approved.
2. **Gemini Flash cost increase** (D-G1) — confirm the same-tier move despite the
   +150% / +50% token price (and 5× / 3× after 2026-12-31).
3. **Haiku 4.5 retirement window** (D-C2) — no successor exists; confirm
   keeping it as the fallback and re-checking after 2026-10-15.
4. **Grok aggregator** (D-X2) — confirm keeping `grok-4.3`, or choose a newer one.

## 6. Live-call verification record (FR-001 / SC-004)

Run 2026-10-04 with the project keys. Total cost about $0.45 (five image calls
at published rates plus a few cents of text). "OK" = a real call returned text
or a valid image.

| Model | Result | Notes |
|---|---|---|
| `claude-sonnet-5-5` | OK | priced $0 today (no table row yet — US2 fixes) |
| `claude-opus-5-5` | OK | priced $0 today (same) |
| `claude-haiku-4-5-20251001` | OK | |
| `gemini-3.8-flash` | OK | first try with `max_tokens=16` returned empty (thinking model used the budget); OK with 1024 |
| `gemini-3.5-flash-lite` | OK | |
| `gemini-2.5-pro` | OK | same empty-at-16-tokens behaviour, OK with 1024 |
| `gemini-2.5-flash` | **OK — still works** | → Gemini Flash swap **HOLD** |
| `gemini-2.5-flash-lite` | **FAIL 404 "no longer available to new users"** | → Flash-Lite swap **GO** |
| `grok-4.3` | OK | xAI reports model `grok-4.3` |
| `grok-build-0.1` | OK | xAI reports `grok-build-0.1` |
| `grok-3`, `grok-3-mini` | OK | xAI reports `grok-4.3` → aliases still redirect → **keep the `grok-3*` aliases** |
| `gemini-3.1-flash-image` | OK | 1408×768 PNG |
| `gemini-3-pro-image` | OK | 1408×768 PNG |
| `gemini-3.1-flash-image-preview` | **OK (docs say shut down)** | still served |
| `gemini-3-pro-image-preview` | **OK (docs say shut down)** | still served |
| `gemini-2.5-flash-image` | **OK (docs conflict)** | still served |

**Final re-check against the shipped defaults (T039, 2026-10-04, about $0.25):** every
distinct default model, read from the code itself, answered a real call — 11 text
models (`claude-haiku-4-5-20251001`, `claude-opus-5-5`, `claude-sonnet-5-5`,
`gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3.1-flash-lite`, `gemini-3.1-pro-preview`,
`gemini-3.5-flash-lite`, `grok-4.3`, `grok-4.5`, `grok-build-0.1`) plus both image
models (`gemini-3.1-flash-image`, `gemini-3-pro-image`). 13 OK, 0 failed, and no model
reported a $0.00 cost (the new Claude defaults are priced). SC-001, SC-002 and SC-004 met.

**Gate outcomes (tasks T007–T009):** `gemini-2.5-flash` HOLD; `gemini-2.5-flash-lite`
GO; `grok-3*` aliases KEEP; no planned default failed.

## 7. Plan changes caused by the live results

1. Gemini Flash stays `gemini-2.5-flash` everywhere; only Flash-Lite moves to
   `gemini-3.5-flash-lite` (inference chain, `_GEMINI_PRO_CHAIN`, newsletter list).
2. The constitution's Gemini text line is therefore unchanged (the approved
   amendment was conditional on 2.5 failing).
3. The three image names that the docs call shut down are removed from the image
   chain but **kept** in the price table (they still respond).
4. The `grok-3*` aliases stay as they are.

## 8. Dated follow-ups

Not done in this spec; recorded so they are not forgotten (also in the v1.30.0
CHANGELOG entry). Adding any of these to `TODO.md` needs the project lead's approval.

| When | Action |
|---|---|
| after 2026-10-15 | Re-check `claude-haiku-4-5-20251001` (earliest retirement date; no successor exists today) |
| after 2026-11-24 | Remove the `claude-opus-4-5-20251101` / `claude-opus-4-5` price rows |
| after 2026-11-30 | Remove the `claude-sonnet-4-5-20250929` / `claude-sonnet-4-5` price rows |
| after 2026-12-31 | Update `gemini-3.8-flash` in `llm/gemini.py` to $1.50 / $7.50 (promotion ends) |
| next refresh | Re-test the three `-preview` / 2.5 image names; drop their price rows once they stop answering |

## 9. Amendment A — thinking-block measurements (2026-10-04, about $0.60 of real calls)

Same real prompts the pipeline sends (framer and Satirist system prompts, same message
format), 2048 `max_tokens` unless stated. "Thinking first" = the reply began with a thinking block.

| Model / setting | Prompt | Thinking first | Thinking tokens | Hit max_tokens |
|---|---|---|---|---|
| Sonnet 5.5 default | Satirist | 6 of 6 | 514–880 | 0 |
| Sonnet 5.5 default | framer round 2 (sees other proposals) | 1 of 3 | 822 | 0 |
| Sonnet 5.5 default | framer round 1 | 0 of 10 | 0 | 0 |
| Sonnet 5.5 default | aggregator-style | 2 of 2 | 599–880 | 0 |
| Opus 5.5 default | framer | 3 of 3 | 487–594 | 0 |
| Sonnet 5.5 `effort=low` or `thinking=between_tools` | Satirist / framer | 0 of 7 | 0 | 0 |
| Haiku 4.5, Sonnet 4.6 (controls) | framer, Satirist | 0 | none | 0 |

Largest reply: 1703 of 2048 tokens. Sonnet 5.5 at default effort writes about 1,200–1,700
output tokens on the Satirist prompt versus about 450 for Sonnet 4.6 (about twice the cost per
call despite the lower price per token). **After the fix** (real `ClaudeProvider`, Satirist
prompt, 2 calls each): Sonnet 5.5 without effort — OK, $0.017/call; with panelist effort low —
OK, $0.009/call, ~700 tokens; Opus 5.5 default $0.034 vs low $0.021; Haiku 4.5 with effort
requested — OK, field not sent. Haiku's replies did not contain `</verdict>` (a model habit
that the truncation recovery from spec 052 handles; unrelated to this fix).

**Also found**: 39 "missing closing `</verdict>`" warnings in 11 pre-054 `run.log` files
(older, separate issue); a failed call is billed by Anthropic but was never recorded in the
cost report (the error message now includes the billed tokens and cost); the test suite
writes real folders into `output/` (not addressed here).

**LinkedIn research call checked, left unchanged (2026-10-04)**: `agent_linkedin_post` reads
only `text` blocks (so it cannot hit the thinking-block crash) and calls the client directly
(so the panelist effort setting does not reach it). A real Sonnet 5.5 web-search call with
`max_tokens=1200`, twice default and twice effort low, returned text every time; thinking was
71–89 tokens at default and 0 at low. All four calls stopped at `max_tokens` regardless of
effort, so that truncation is an older, separate limit (not caused by thinking) and is not
changed here.
