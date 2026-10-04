# Tasks: Model currency refresh II

**Input**: Design documents from `specs/054-model-currency-refresh-ii/`
**Branch**: `054-model-currency-refresh-ii`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅,
contracts/model-matrix.md ✅, quickstart.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions. Test
tasks appear before their corresponding implementation tasks in every phase.
Every test function needs a one-sentence plain-English comment at its top (RULE 3,
§9). Inside function bodies use an inline comment, not a blank line, to mark a
change of focus (RULE 14). Zero real API calls in the suite; the live checks in
Phase 2 are manual and outside it.

**Lead decisions already taken** (plan.md): keep `grok-4.3` and `grok-build-0.1`;
keep Haiku 4.5; version bump to 1.30.0; Gemini Flash / Flash-Lite move **only if the
live check shows 2.5 no longer works**; the constitution amendment v1.3 is **approved as described** (2026-10-04).

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no unmet dependencies)
- **[Story]**: US1 = runs use current models, US2 = correct cost tables, US3 = governance
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: Branch hygiene and a green baseline (RULE 5).

- [X] T001 Confirm active git branch is `054-model-currency-refresh-ii`; if on `main`, switch before touching any source file
- [X] T002 Run `python -m pytest tests/ -q` and `ruff check .`; record that both pass on the untouched code so later failures are attributable to this feature
- [X] T003 Run `source set_gata.sh` (RULE 16) and confirm `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY` are set (names only, never print values)

---

## Phase 2: Foundational — live verification (Blocking)

**Purpose**: FR-001 / SC-004 — confirm every proposed model with one real call before any
default changes, and settle the Gemini condition. Manual, outside the test suite.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Run the text-model live check from `specs/054-model-currency-refresh-ii/quickstart.md` §2 (claude-sonnet-5-5, claude-opus-5-5, claude-haiku-4-5-20251001, gemini-3.8-flash, gemini-3.5-flash-lite, gemini-2.5-pro, grok-4.3, grok-build-0.1, grok-3) **plus** `gemini-2.5-flash` and `gemini-2.5-flash-lite` (add both to the list: they decide the Gemini condition)
- [X] T005 Run the image-model check from `quickstart.md` §2b (`gemini-3.1-flash-image`, `gemini-3-pro-image`); expected cost about $0.07 and $0.13
- [X] T006 Record every result (OK/FAIL, `billed_as`, cost, date) in the table in `specs/054-model-currency-refresh-ii/research.md` §6, replacing the `_pending_` row
- [X] T007 Gemini gate (lead's condition, plan.md decision 2), decided **per model** from T004: for `gemini-2.5-flash` and for `gemini-2.5-flash-lite` separately, mark the swap **GO** in `research.md` §6 if that model FAILED, **HOLD** if it still works. Every task marked "only if T007 is GO" (T011, T013, T017, T018, T019, T020, T028) applies only to the models marked GO. For any HOLD, skip those edits and report to the lead before continuing — do not decide alone.
- [X] T008 Decide the retired `grok-3*` aliases from T004's `grok-3` result: if it still redirects/bills as grok-4.3 keep them in `llm/grok.py`, otherwise they are to be removed in T022 (FR-005); write the decision in `research.md` §6
- [X] T009 Any default model whose live call FAILED stops its swap: note it in `research.md` §6 and tell the lead before continuing

**Checkpoint**: `grep -n "pending" specs/054-model-currency-refresh-ii/research.md` returns nothing, and the Gemini gate says GO or HOLD.

**Phase 2 outcome (2026-10-04, see `research.md` §6–§7)**: `gemini-2.5-flash` still works →
**HOLD** (Gemini Flash stays `gemini-2.5-flash` everywhere). `gemini-2.5-flash-lite` returns
404 → **GO** (moves to `gemini-3.5-flash-lite`). `grok-3*` aliases **KEEP**. The three image
names the docs call shut down still respond: removed from the image chain, **kept** in the
price table. All planned defaults passed. Tasks below are already rewritten to these outcomes.

---

## Phase 3: User Story 1 — Runs use current, available models (Priority: P1)

**Goal**: Every built-in default model, fallback chain entry and the image chain is a currently available model, with provider order unchanged (FR-002, FR-003, FR-008).

**Independent Test**: `python -m pytest tests/test_default_models.py -v` passes, and `python pipeline.py --topic "model currency smoke test" --audience "UK engineers" --language English --tone dry` completes with no model-not-found warning in `run.log`.

### Tests for User Story 1 — Write FIRST, Confirm FAILING Before Implementation

- [X] T010 [P] [US1] Create `tests/test_default_models.py` with failing tests, each with a one-sentence comment at the top (RULE 3): (a) no retired model name (`gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`, `gemini-2.5-flash-image`, `gemini-2.5-flash-lite`, `claude-sonnet-4-6` as a default, `claude-opus-4-7` as a default) appears in `core/runner.py` chains, `core/image_generation.py::_MODELS`, `core/newsletter_merge.py` lists, `agents/agent_cultural_strategist.py::_INFERENCE_MODELS`, `agents/trend_scout.py::_GEMINI_MODEL`, or the parsed defaults of `providers.yaml`; (b) `core.image_generation._MODELS == ["gemini-3.1-flash-image", "gemini-3-pro-image"]`; (c) `core.runner._CLAUDE_CHAIN` model ids are `["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-4-5-20251001"]`; (d) the Grok panelist and the Grok aggregator are different models (constitution §6) and `_GROK_AGGREGATOR` is `grok-4.3`, the Grok panelist `grok-build-0.1`; (e) the provider order inside `providers.yaml` panelist/aggregator chains matches today's order (claude, gemini, grok / grok, gemini, claude / gemini, grok, claude; aggregator grok, claude, gemini) — FR-003; (f) `core.newsletter_merge._GROK_MODELS` is unchanged
- [X] T011 [P] [US1] In `tests/test_newsletter_merge.py` update the assertions at lines ~214 and ~234 to the new `_GEMINI_TEXT_MODELS` order `["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.1-pro-preview"]` and the new `_CLAUDE_MODELS` (`["claude-haiku-4-5-20251001", "claude-sonnet-5-5", "claude-opus-5-5"]`)
- [X] T012 [P] [US1] In `tests/test_image_generation.py` update the assertions at lines ~157 and ~183 from `gemini-3.1-flash-image-preview` to `gemini-3.1-flash-image` so the first-tried model is the stable one
- [X] T013 [P] [US1] Check `tests/test_agent_image_evaluator.py` (`_DEFAULT_MODELS`, line ~72): if it asserts the real `core.runner._GEMINI_EVAL_CHAIN`, update it to the new chain `["gemini-2.5-pro", "gemini-2.5-flash", "gemini-3.5-flash-lite"]`; if it only uses those names as mock labels, leave it unchanged and note "no change needed" in the task — **Result: no change needed** (it builds mock providers from its own `_DEFAULT_MODELS` labels and never reads `core.runner`)

> **STOP**: Confirm the new and edited tests FAIL (`python -m pytest tests/test_default_models.py tests/test_newsletter_merge.py tests/test_image_generation.py tests/test_agent_image_evaluator.py -v`) before proceeding to T014.

### Implementation for User Story 1

- [X] T014 [P] [US1] In `core/image_generation.py` set `_MODELS` to `["gemini-3.1-flash-image", "gemini-3-pro-image"]` — remove `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`, `gemini-2.5-flash-image`; keep the existing order (FR-003)
- [X] T015 [US1] In `core/runner.py` set `_CLAUDE_CHAIN` to `claude-sonnet-5-5` → `claude-opus-5-5` → `claude-haiku-4-5-20251001` and `_PARALLEL_PANELISTS` Claude entry to `claude-sonnet-5-5`; leave `grok-build-0.1` and `_GROK_AGGREGATOR = grok-4.3` unchanged
- [X] T016 [P] [US1] In `core/newsletter_merge.py` set `_CLAUDE_MODELS` to `["claude-haiku-4-5-20251001", "claude-sonnet-5-5", "claude-opus-5-5"]` and the default panelist `ClaudeProvider` to `claude-sonnet-5-5`; leave `_GROK_MODELS` and the aggregator unchanged
- [X] T017 [US1] Move **Flash-Lite only** (T007: Flash is HOLD). In `core/runner.py` set `_GEMINI_PRO_CHAIN` to `gemini-2.5-pro` → `gemini-2.5-flash` → `gemini-3.5-flash-lite` (the `_PARALLEL_PANELISTS` Gemini entry stays `gemini-2.5-flash`); in `core/newsletter_merge.py` set `_GEMINI_TEXT_MODELS` to the order in T011; in `agents/agent_cultural_strategist.py` set `_INFERENCE_MODELS` to `["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.5-flash-lite"]`; `agents/trend_scout.py` needs no change
- [X] T018 [P] [US1] In `core/bundle_writer.py` (lines ~130–134) update the fallback default Claude provider to `claude-sonnet-5-5`; the Gemini and Grok entries are unchanged (Flash is HOLD)
- [X] T019 [P] [US1] In `providers.yaml` update the built-in defaults per `contracts/model-matrix.md` §1: Claude `claude-sonnet-4-6` → `claude-sonnet-5-5` everywhere (panelist 1 and aggregator slot 2); keep provider order, `gemini-2.5-flash` (HOLD), `grok-4.3`, `grok-build-0.1`, `claude-haiku-4-5-20251001` and the aggregator's `gemini-2.5-pro` as they are
- [X] T020 [US1] In the `providers.yaml` header comment block carry the recommended timeouts over unchanged to the successors: `claude-sonnet-5-5: timeout: 25.0` (from `claude-sonnet-4-6`); no Gemini comment changes (Flash is HOLD; Flash-Lite had none); do not enable any timeout (FR-006)

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests in this phase PASS before proceeding. Tests that merely use an old model name as a mock label (for example `_make_provider("claude-sonnet-4-6")` in `tests/test_dual_loop.py`) are intentionally NOT changed.

**Checkpoint**: `python -m pytest tests/test_default_models.py -v`

> Do not commit-and-merge here; continue straight to Phase 4 (see Implementation Strategy).

---

## Phase 4: User Story 2 — Cost reports show correct prices (Priority: P2)

**Goal**: Every default model, and every non-retired generally available model, has its published rate in the cost table; retired names are removed unless the provider still bills them (FR-004, FR-005).

**Independent Test**: `python -m pytest tests/test_claude_provider.py tests/test_gemini_provider.py tests/test_grok_provider.py -v`

### Tests for User Story 2 — Write FIRST, Confirm FAILING Before Implementation

- [X] T021 [P] [US2] In `tests/test_claude_provider.py` add failing tests (comment each, RULE 3) asserting `llm.claude._COST_PER_M` equals: `claude-sonnet-5-5` (2.00, 10.00); `claude-opus-5-5` (4.00, 20.00); `claude-opus-4-6`, `claude-opus-4-5-20251101`, `claude-opus-4-5` (5.00, 25.00); `claude-sonnet-4-5-20250929` (3.00, 15.00); `claude-fable-5-1`, `claude-fable-5` (10.00, 50.00); `claude-sonnet-5` **(2.00, 10.00) — the price-bug fix**; existing rows unchanged; no key for any Mythos model. Quote this rule from `data-model.md` in the test comment: "value equals the provider's published rate on the verification date"
- [X] T022 [P] [US2] In `tests/test_gemini_provider.py` add failing tests asserting `llm.gemini._COST_PER_M` has `gemini-3.8-flash` (0.75, 3.75), `gemini-3.5-flash-lite` (0.30, 2.50), `gemini-3.5-flash` (1.50, 9.00) and still `gemini-3.1-flash-image` (0.50, 60.00), `gemini-3-pro-image` (2.00, 120.00), `gemini-2.5-pro`/`-flash`/`-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.1-pro-preview`; and **still has** the keys `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`, `gemini-2.5-flash-image` — the live check shows they still respond, so under FR-005 they are still-billed names ("entries for retired models are removed, except an alias the provider still bills (FR-005)")
- [X] T023 [P] [US2] In `tests/test_grok_provider.py` add failing tests asserting `llm.grok._COST_PER_M` has `grok-4.6` and `grok-4.7` at (2.00, 6.00) and unchanged `grok-4.5` (2.00, 6.00), `grok-4.3` (1.25, 2.50), `grok-build-0.1` (1.00, 2.00); update the existing `grok-3*` alias tests (lines ~149–161) — T008 decision is KEEP, so they stay and no alias test changes
- [X] T024 [US2] In `tests/test_default_models.py` add a failing test that every default model id from all chains/providers.yaml/image chain is a key of its provider's `_COST_PER_M` ("model id exists in that provider's price table")

> **STOP**: Confirm T021–T024 tests FAIL before proceeding to T025.

### Implementation for User Story 2

- [X] T025 [P] [US2] In `llm/claude.py` update `_COST_PER_M` per `contracts/model-matrix.md` §2 and T021 (add, fix `claude-sonnet-5`; do not add Mythos); keep exact-string keys for both alias and dated IDs
- [X] T026 [P] [US2] In `llm/gemini.py` update `_COST_PER_M` per T022; add a code comment on the `gemini-3.8-flash` row: promotional rate through 2026-12-31, then $1.50/$7.50; update the existing retired-models comment block (the three image names are kept because they still respond)
- [X] T027 [P] [US2] In `llm/grok.py` add `grok-4.6` and `grok-4.7` and apply the T008 decision to the `grok-3*` aliases

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests in this phase PASS before proceeding.

**Checkpoint**: `python -m pytest tests/test_claude_provider.py tests/test_gemini_provider.py tests/test_grok_provider.py tests/test_default_models.py -v`

---

## Phase 5: User Story 3 — Governance matches the code (Priority: P3)

**Goal**: The constitution's §1 (and §6 only if a Grok model changed — it did not) names the same models the code defaults to (FR-007, SC-006).

**Independent Test**: `python -m pytest tests/test_constitution_models.py -v`

**Approval**: the project lead approved constitution amendment v1.3 as described on 2026-10-04 (Amendment Procedure steps 1–3 satisfied; the spec 054 plan and PR are the proposal). Apply exactly the §1 changes in plan.md decision 1; nothing more.

### Tests for User Story 3 — Write FIRST, Confirm FAILING Before Implementation

- [X] T028 [US3] Create `tests/test_constitution_models.py` with a failing test (one-sentence comment, RULE 3) that parses `.specify/memory/constitution.md` §1 and asserts every backticked model name there is one of the current defaults (`claude-sonnet-5-5`, `gemini-3.1-flash-image`, `gemini-2.5-flash`, `gemini-2.5-pro`, `grok-4.3`) and that §1 no longer names `claude-sonnet-4-6` or `gemini-3.1-flash-image-preview`

> **STOP**: Confirm T028 FAILS before proceeding to T029.

### Implementation for User Story 3

- [X] T029 [US3] In `.specify/memory/constitution.md` update §1 model names, bump the header **Version** to 1.3, add a v1.3 entry to the **Amendment log** at the top and a row to the **Amendment Record** table (date 2026-10-04 or the approval date, "Spec 054", approved by Jose Santos); also correct §1's pointer to the image fallback chain from `agents/agent_image_generator.py` to `core/image_generation.py`; leave §6 untouched because `grok-4.3` and `grok-build-0.1` are unchanged

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests PASS before proceeding.

**Checkpoint**: `python -m pytest tests/test_constitution_models.py -v`

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T030 [P] Run `ruff check . --fix` and `ruff format .` on all modified files; confirm `ruff check .` exits 0 (§12)
- [X] T031 [P] Update `README.md` for every changed model name and price note, and add the spec 054 row to its status table (RULE 6, RULE 11, RULE 17); list exactly what was stale before editing
- [X] T032 [P] Update `docs/architecture.md` for changed model names, chains and examples (RULE 17)
- [X] T033 [P] Add a v1.30.0 entry to `CHANGELOG.md` in plain English: defaults and cost tables refreshed, retired image models removed, sonnet-5 price corrected, constitution v1.3 (RULE 17)
- [X] T034 [P] Bump the version to `1.30.0` in `pyproject.toml` and `core/__version__.py` (RULE 15; approved by the lead)
- [X] T035 [P] Remove the "Model currency refresh II" item from `TODO.md` in this same PR (RULE 19); touch no other TODO item
- [X] T036 [P] Add the 054 row to the "Completed Stages" table in `CLAUDE.md` (and update its "as of" date), in this PR, as specs 046, 050 and 052 did
- [X] T037 Check for stale names: `grep -rnE "claude-sonnet-4-6|gemini-2\.5-flash\b|-image-preview" README.md docs CHANGELOG.md` — only historical CHANGELOG lines may match; fix the rest
- [X] T038 [P] Add a "Dated follow-ups" section to `specs/054-model-currency-refresh-ii/research.md` and one sentence to the `CHANGELOG.md` v1.30.0 entry listing: re-check Haiku 4.5 after 2026-10-15; remove the Opus 4.5 price rows after 2026-11-24 and the Sonnet 4.5 rows after 2026-11-30; update `gemini-3.8-flash` to $1.50/$7.50 after 2026-12-31. Do not edit `TODO.md` for these (RULE 8)
- [X] T039 Re-run the live checks of T004/T005 against the final defaults actually in the code and append the results to `research.md` §6 (SC-001, SC-004); optionally run the end-to-end smoke test in `quickstart.md` §3
- [X] T040 Run `python -m pytest tests/ -q` — must report 0 failures; then do the three self-review passes and stop for human review (RULE 4)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories (live checks decide the Gemini gate and the grok-3 alias)
- **US1 (Phase 3)**: Depends on Phase 2
- **US2 (Phase 4)**: Depends on Phase 2; independent of US1 except T024, which checks every default from US1 against the price tables, so run T024 after T019
- **US3 (Phase 5)**: Depends on Phase 3 (needs the final defaults); the amendment is already approved
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### Within Each Phase

- Test tasks MUST be written and verified to FAIL before implementation tasks begin
- T015, T017 and T018 all edit or depend on `core/runner.py` / shared lists: do T015 before T017
- T019 before T020 (same file)
- T006–T009 are written into the same `research.md` §6: do them in order
- **Found during implementation**: `core/newsletter_merge.py::build_fallback_chain` reads `_CLAUDE_COST_PER_M[model]` / `_GEMINI_COST_PER_M[model]` directly (KeyError if a row is missing), so the price rows (T025–T027) must exist before the chain edits (T016/T017). Tests T010–T013 and T021–T024 were written first, then T025–T027, then T014–T020.

---

## Parallel Opportunities

- Phase 3 tests: T010, T011, T012, T013 (different files)
- Phase 3 implementation: T014, T016, T018, T019 (different files); T015 and T017 share `core/runner.py` and run in sequence
- Phase 4 tests: T021, T022, T023 (different files); implementation T025, T026, T027 (different files)
- US2 can run in parallel with US1 after Phase 2 if two people work; with one person, do US1 first
- Polish: T030–T035 (different files)

---

## Implementation Strategy

- **MVP**: Phase 1 + Phase 2 + Phase 3 (US1) + Phase 4 (US2) together. US1 alone must not be committed as a release point: `llm/*.py` return $0.00 for any model without a price entry, so the new defaults would report zero cost until US2 lands.
- **Incremental**: after the US1 + US2 MVP, add US3 (constitution, approved), then Polish.
- **Risk controls**: the live checks come first, the Gemini change is conditional, every swap is the same tier, and nothing is merged with a stale constitution unless the lead decides so.

---

## Summary

| Phase | Tasks | Story | Notes |
|-------|-------|-------|-------|
| 1 Setup | T001–T003 | — | Branch, baseline, secrets |
| 2 Foundational | T004–T009 | — | Live verification + Gemini gate |
| 3 US1 | T010–T020 | US1 | Chains, image chain, providers.yaml (ships with US2) |
| 4 US2 | T021–T027 | US2 | Cost tables |
| 5 US3 | T028–T029 | US3 | Constitution v1.3 — approved |
| 6 Polish | T030–T040 | — | ruff, docs, version, TODO, follow-ups, final checks |
| **Total** | **40 tasks** | | |

---

## Amendment A tasks (2026-10-04) — Claude 5 thinking blocks

- [X] T047 Measure on real prompts (research.md §9): block order, thinking tokens, stop reason, effort variants
- [X] T048 Write failing tests in `tests/test_claude_provider.py`: leading thinking block, several text blocks, no text block (error names model/stop reason), `max_tokens` warning, effort sent / not sent / ignored for Haiku (FR-011–FR-013)
- [X] T049 Write failing tests in `tests/test_default_models.py`: panelists low effort, other roles unchanged, factory `panelist` flag, newsletter engagement panel, bundle_writer constant
- [X] T050 Implement in `llm/claude.py`: text-block extraction, error, `max_tokens` warning, `effort` + `PANELIST_CLAUDE_EFFORT`
- [X] T051 Wire panelist-only effort in `core/runner.py`, `core/newsletter_merge.py`, `core/bundle_writer.py`; update `tests/test_providers_config.py`
- [X] T052 Verify the fixed provider live on real Satirist prompts for Sonnet 5.5, Opus 5.5 and Haiku 4.5 (research.md §9)
- [X] T053 Update `quickstart.md` live check to realistic prompts (FR-014); CHANGELOG v1.31.1; version 1.31.1; README and architecture notes
