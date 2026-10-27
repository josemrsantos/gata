# Tasks: Tag-free, JSON-free panel responses

**Input**: Design documents from `specs/058-tag-free-panel-responses/`
**Branch**: `058-tag-free-panel-responses`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions. Test
tasks appear before their corresponding implementation tasks in every phase. Every test
function gets a one-sentence plain-English comment (RULE 3); no blank-line phase dividers
inside function bodies (RULE 14).

**Shell note**: the Bash tool is broken in this session; run commands through
`mcp__pycharm__execute_terminal_command` (`executeInShell=true`, one simple command per call).

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1 … US4)
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: Confirm branch hygiene before any code is written (RULE 5).

- [x] T001 Confirm active git branch is `058-tag-free-panel-responses`; if on `main`, switch before touching any source file

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared tolerant parser, the log-context type, and `FairParallelPanel` wiring that every
story uses. Strict `_extract_proposer_verdict` in `llm/dual_loop.py` and `llm/parallel_panel.py` are NOT touched.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T002 [P] Write failing tests in `tests/test_reply_parsing.py` for `unwrap_reply` (closed tag → content; unclosed tag → content + WARNING; bare fenced JSON → content + WARNING; plain text → whole reply; one surrounding code fence removed; empty/whitespace reply → `ValueError`), using the 2026-10-27 unclosed-`<verdict>` reply and bare fenced Satirist JSON reply as literal fixtures; also a reply with a `<verdict>` wrapper around labelled lines (unwrapped first) and a reply truncated mid-block (FR-001, FR-009, SC-001)
- [x] T003 [P] Write failing tests in `tests/test_reply_parsing.py` for `split_pick` (`PICK: 2` on its own line; `**PICK: 2**`; `- PICK: 2`; no PICK line → `(None, whole reply)`; rest of reply returned without the PICK line) (FR-002)
- [x] T004 [P] Write failing tests in `tests/test_reply_parsing.py` for `parse_labelled` (canonical labels; `Scene 1:`, `**CAPTION**:`, `## Panel 1` drift; mixed case; code fence; value running to the next known label) (FR-005, SC-003)
- [x] T005 [P] Write failing tests in `tests/test_reply_parsing.py` for `log_parse_issue`: the WARNING contains the agent, role, round, model, field, applied default, `stop_reason`/`output_tokens`/`max_tokens` when set, and exactly the first 400 characters of the reply, never more (FR-007, FR-008, SC-002)
- [x] T006 [P] Write failing tests in `tests/test_types.py`: `TokenUsage(model, input_tokens, output_tokens, cost_usd)` still constructs with 4 arguments and `stop_reason` defaults to `None`
- [x] T007 [P] Write failing tests in `tests/test_fair_parallel_panel.py`: (a) a whole-reply panelist (no tags) is used with no retry and no WARNING; (b) an unclosed-tag panelist reply is used with no retry; (c) `reply_check` returning a reason triggers exactly one retry whose user message is the panel's `format_reminder`; (d) a second unusable reply drops the panelist; (e) an empty reply with no `reply_check` is retried once; (f) the peer-round prompt contains no `<verdict>` text; (g) the aggregator verdict is the text after the `PICK: N` line and the `PICK` label is recorded; (h) an unusable aggregator reply gets one retry (FR-001, FR-002, FR-008a, FR-009)

> **STOP**: Confirm T002–T007 all FAIL (`python -m pytest tests/test_reply_parsing.py tests/test_types.py tests/test_fair_parallel_panel.py -v`) before proceeding to T008.

- [x] T008 Add `stop_reason: str | None = None` as the last field of `TokenUsage` in `core/types.py`
- [x] T009 Create `llm/reply_parsing.py` with frozen dataclass `ParseContext` (agent, role, round, model, stop_reason, output_tokens, max_tokens per data-model.md) and `log_parse_issue(ctx, field, applied, reply)` emitting the WARNING format in `contracts/reply-formats.md` with a 400-character excerpt
- [x] T010 In `llm/reply_parsing.py` implement `unwrap_reply(text, ctx=None)`, `split_pick(text)` and `parse_labelled(text, labels)` per `contracts/reply-formats.md`; legacy fallbacks (unclosed tag, bare JSON) call `log_parse_issue`
- [x] T011 In `llm/fair_parallel_panel.py` replace `_extract_proposer_verdict` with `unwrap_reply`; add optional constructor args `reply_check: Callable[[str], str | None] | None = None` and `format_reminder: str = <generic reminder naming no tags>`; build a `ParseContext` from the panel name, persona name, round and the call's `TokenUsage` (model from `usage.model`, `max_tokens` from the persona); use `format_reminder` for the single retry (also for an unusable aggregator reply); drop the tag sentence from `_build_peer_prompt` ("Reply in the same format as before."); take the aggregator verdict from `split_pick`

> **STOP**: Run `python -m pytest tests/ -v` — confirm T002–T007 PASS and no previously passing test regressed (tests asserting old `<verdict>` wording in `tests/test_fair_parallel_panel.py` are updated here, not deleted).

**Checkpoint**: `python -m pytest tests/test_reply_parsing.py tests/test_types.py tests/test_fair_parallel_panel.py tests/test_dual_loop.py tests/test_parallel_panel.py -q`

---

## Phase 3: User Story 1 — A reply that ignores the old format is still used (Priority: P1) MVP

**Goal**: Cultural Strategist, Explainer, Engagement Image and LinkedIn Angle Planning/Writing ask for the
whole reply with no tags, and the aggregator asks for `PICK: N` + the answer.

**Independent Test**: `python -m pytest tests -k "tag_free" -q`

### Tests for User Story 1 — Write FIRST, Confirm FAILING Before Implementation

- [x] T012 [P] [US1] Write failing tests in `tests/test_agent_cultural_strategist.py`: panelist and aggregator prompts contain no `<verdict>`; aggregator prompt asks for `PICK: N` then the three fields; `_parse_verdict` still extracts angle/references/joke type from a reply that has no tags and from one that still has them
- [x] T013 [P] [US1] Write failing tests in `tests/test_agent_explainer.py`: both prompts (in-language and English) contain no `<verdict>`; HTML returned inside a ```html fence reaches the caller without the fence
- [x] T014 [P] [US1] Write failing tests in `tests/test_agent_engagement_image.py`: panelist and aggregator prompts contain no `<verdict>`; the image prompt equals the stripped reply text after the PICK line
- [x] T015 [P] [US1] Write failing tests in `tests/test_agent_linkedin_post.py` (FR-010 equivalence: the same angle/article content produces the same parsed sections whether the reply is tagged or untagged, and likewise for T012's Cultural Strategist fields and T013's Explainer HTML): `_PLANNER_SYSTEM`, `_PLANNER_AGGREGATOR_SYSTEM`, `_WRITER_SYSTEM`, `_WRITER_AGGREGATOR_SYSTEM` contain no `<verdict>`; `ANGLE:`/`FOCUS:` and `===MARKER===` section parsing works on untagged replies

> **STOP**: Confirm T012–T015 FAIL (`python -m pytest tests/test_agent_cultural_strategist.py tests/test_agent_explainer.py tests/test_agent_engagement_image.py tests/test_agent_linkedin_post.py -v`) before proceeding to T016.

### Implementation for User Story 1

- [x] T016 [P] [US1] Remove tag wording from the framer system prompt (`<verdict>` block around `CULTURAL ANGLE:`/`REFERENCES:`/`JOKE TYPE:`) and `_CS_AGGREGATOR_SYSTEM` (ask for `PICK: N` then the fields) in `agents/agent_cultural_strategist.py`
- [x] T017 [P] [US1] Remove tag wording from both Explainer prompts in `agents/agent_explainer.py` (lines ~21, ~38–40); confirm the returned HTML has one surrounding fence stripped
- [x] T018 [P] [US1] Remove tag wording from the Engagement Image panelist and aggregator prompts in `agents/agent_engagement_image.py` (lines ~48, ~67–70)
- [x] T019 [P] [US1] Remove tag wording from the four LinkedIn Angle Planning/Writing prompts in `agents/agent_linkedin_post.py` (lines ~117, ~137, ~162, ~189), keeping the `ANGLE:`/`FOCUS:` and `===MARKER===` formats

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests in this phase PASS before proceeding.

**Checkpoint**: `python -m pytest tests -k "tag_free or cultural_strategist or explainer or engagement_image or linkedin" -q`

---

## Phase 4: User Story 2 — The Satirist returns `LABEL: value` text (Priority: P1)

**Goal**: The Satirist panel and aggregator use `PANELS`/`LAYOUT`/`TITLE`/`PANEL n` + `SCENE`/`CAPTION`/`BEAT`,
parsed tolerantly into the same `CartoonConcept` and `CartoonLayout` as today.

**GATE G3**: Constitution amendment v1.6 (§3, §6) and the TODO.md removal must be explicitly approved by
the project lead. T028 (the amendment) is executed FIRST in this phase, before T024, because the Satirist
code changes would otherwise break Constitution §3/§6 MUST rules. Test tasks T020–T023 may be written
before approval (they change no behaviour); T024–T027 may not.

**Independent Test**: `python -m pytest tests -k "satirist_labels" -q`

### Tests for User Story 2 — Write FIRST, Confirm FAILING Before Implementation

- [x] T020 [P] [US2] Write failing tests in `tests/test_agent_satirist.py` (`satirist_labels`): a canonical labelled 3-panel reply parses to the same `CartoonConcept`/`CartoonLayout` as the equivalent JSON does today; panel count = number of `PANEL n` blocks even if `PANELS:` disagrees (FR-003)
- [x] T021 [P] [US2] Write failing tests in `tests/test_agent_satirist.py`: drift fixtures (`Scene 1:`, `**CAPTION**:`, `## Panel 1`, a surrounding code fence) parse identically to the canonical form (FR-005, SC-003)
- [x] T022 [P] [US2] Write failing tests in `tests/test_agent_satirist.py`: unusable replies (no `PANEL n` block; a panel with no `SCENE`; 2+ panels with an empty `BEAT`) are reported by the Satirist `reply_check`; a missing `TITLE` falls back to the topic, a missing `CAPTION` to empty, a missing/odd `LAYOUT` to the CLI `layout_override` else auto layout, each with a WARNING naming the field; a reply cut off mid-`PANEL` block is parsed as far as possible and judged by the same required-field rules (FR-006, FR-007)
- [x] T023 [P] [US2] Write failing tests in `tests/test_agent_satirist.py`: the legacy JSON object (and the 2026-10-27 bare fenced JSON fixture) still parses (FR-009); the system prompt and aggregator prompt contain no `<verdict>`, no "valid JSON", and still contain Gata's full description verbatim (Constitution §4) and the output-language rules (§7)

> **STOP**: Confirm T020–T023 FAIL (`python -m pytest tests/test_agent_satirist.py -v`) before proceeding to T028.

### Implementation for User Story 2

- [x] T028 [US2] **Execute first.** After G3 approval only: amend `.specify/memory/constitution.md` to v1.6 — §3 (panel replies are plain text, aggregator uses `PICK: N`, parsers tolerate legacy `<verdict>` tags; remove the Satirist-JSON and regex rules), §6 (replace the JSON schema with the `LABEL: value` schema, same fields and limits), amendment log and record table; check `tests/test_constitution_models.py` still passes

- [x] T024 [US2] (after T028) Replace `_OUTPUT_FORMAT_RULES` in `agents/agent_satirist.py` with the labelled format from `contracts/reply-formats.md`, keeping the CONTENT RULES (scene carries Gata's description for 1 panel, beat required for 2+ panels, caption/title in the output language, 3–8 word title); update the `<joke_explanation>` sentence ("After the JSON") to "After the panels"
- [x] T025 [US2] Replace `_parse_verdict` in `agents/agent_satirist.py` with `parse_satirist_reply(text, layout_override, topic, ctx)` built on `parse_labelled`, legacy-JSON path kept; required-vs-default table from `data-model.md`; every fallback goes through `log_parse_issue`; keep the single-panel last-resort fallback only for a reply with no readable panel after the retry
- [x] T026 [US2] Add `satirist_reply_check(text)` (returns a reason when no `PANEL n`, a panel lacks `SCENE`, or 2+ panels have an empty `BEAT`) and `_SATIRIST_FORMAT_REMINDER` (lists the required labels) in `agents/agent_satirist.py`; pass both to `FairParallelPanel` and update `_build_aggregator_prompt` to ask for `PICK: N` then the chosen concept (no tags)
- [x] T027 [US2] Build the aggregator `ParseContext` in `run()` of `agents/agent_satirist.py` — model, `stop_reason` and `output_tokens` from `loop_output.telemetry.calls[-1]`, round = `loop_output.telemetry.iterations`, `max_tokens` from the aggregator `PersonaConfig`, role `Aggregator` — and pass it to `parse_satirist_reply`; update the stale "verdict parse failed" comment

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests in this phase PASS before proceeding.

- [x] T029 [US2] After G3 approval only: in `TODO.md` remove the "Tag-free, JSON-free panel responses" item and the "Satirist output-format wording" item (RULE 19, RULE 8)

**Checkpoint**: `python -m pytest tests/test_agent_satirist.py tests/test_constitution_models.py -q`

---

## Phase 5: User Story 3 — Parse failures can be traced (Priority: P1)

**Goal**: Every parse failure or fallback in every panel names agent, round, provider/model, field,
default and excerpt, plus stop reason / output length where the provider exposes them.

**Independent Test**: `python -m pytest tests -k "parse_failure_log" -q`

### Tests for User Story 3 — Write FIRST, Confirm FAILING Before Implementation

- [x] T030 [P] [US3] Write failing tests in `tests/test_claude_provider.py`, `tests/test_gemini_provider.py`, `tests/test_grok_provider.py`: each provider's `TokenUsage.stop_reason` is filled from the (mocked) response — Claude `stop_reason`, Gemini `candidates[0].finish_reason`, Grok `choices[0].finish_reason` — and is `None` when the response lacks it (FR-008)
- [x] T031 [P] [US3] Write failing tests in `tests/test_fair_parallel_panel.py` (`parse_failure_log`): a retry caused by an unusable reply logs a WARNING with the panel name, panelist, round, the answering model after a fallback, `stop_reason=max_tokens` vs a normal stop, `output_tokens`/`max_tokens` and the 400-character excerpt; the unclosed-tag recovery log names the same fields (FR-007, FR-008, SC-002)

> **STOP**: Confirm T030–T031 FAIL (`python -m pytest tests/test_claude_provider.py tests/test_gemini_provider.py tests/test_grok_provider.py tests/test_fair_parallel_panel.py -v`) before proceeding to T032.

### Implementation for User Story 3

- [x] T032 [P] [US3] Set `stop_reason` on the returned `TokenUsage` in `llm/claude.py` (already read into a local at line ~116)
- [x] T033 [P] [US3] Set `stop_reason` from `candidates[0].finish_reason` (string name) in `llm/gemini.py`, defensively (`getattr`, no candidates → `None`)
- [x] T034 [P] [US3] Set `stop_reason` from `choices[0].finish_reason` in `llm/grok.py`, defensively
- [x] T035 [US3] Verify every WARNING path in `llm/fair_parallel_panel.py` (timeout, provider failure, unusable reply, dropped panelist) includes the `ParseContext` fields where applicable; fix any that does not

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests in this phase PASS before proceeding.

**Checkpoint**: `python -m pytest tests -k "parse_failure_log or provider" -q`

---

## Phase 6: User Story 4 — LinkedIn Domain Classification as plain lines (Priority: P2)

**Goal**: Domain classification asks for and parses one line per domain.

**Independent Test**: `python -m pytest tests -k "domain_classification" -q`

### Tests for User Story 4 — Write FIRST, Confirm FAILING Before Implementation

- [x] T036 [P] [US4] Write failing tests in `tests/test_agent_linkedin_post.py` (`domain_classification`): `nytimes.com: paywalled, high`, `- some-blog.com: free, low`, `**x.org**: HIGH , Free`, and reversed word order all parse correctly; an absent or unreadable domain gets today's default with a WARNING naming the domain (not the whole panel); the legacy JSON object still parses; the prompts contain no `<verdict>` or JSON example (FR-004)

> **STOP**: Confirm T036 FAILS (`python -m pytest tests/test_agent_linkedin_post.py -k domain_classification -v`) before proceeding to T037.

### Implementation for User Story 4

- [x] T037 [US4] Replace `_DOMAIN_CLASSIFIER_SYSTEM` and `_DOMAIN_CLASSIFIER_AGGREGATOR_SYSTEM` in `agents/agent_linkedin_post.py` with the one-line-per-domain format (`PICK: N` then the lines for the aggregator) and pass a Domain Classification `format_reminder` to the panel
- [x] T038 [US4] Replace the JSON parsing at the end of `_classify_domains_panel` in `agents/agent_linkedin_post.py` with a line parser (`paywalled`/`free`, `high`/`low`, any order, case/bullet/space tolerant), legacy JSON still accepted, unreadable/absent domain → default via `log_parse_issue` with the aggregator `ParseContext` (model, `stop_reason`, `output_tokens` from `loop_output.telemetry.calls[-1]`, round = `loop_output.telemetry.iterations`, `max_tokens` from the aggregator `PersonaConfig`, role `Source Classifier`); the return shape `dict[str, dict]` with `paywalled` and `reliability` keys is unchanged

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests in this phase PASS before proceeding.

**Checkpoint**: `python -m pytest tests -k "domain_classification or linkedin" -q`

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T039 Run `python -m pytest tests/ -q` — zero failures (Constitution §9); confirm every new test function has its one-sentence comment (RULE 3)
- [x] T040 [P] Run `ruff check . --fix` and `ruff format .` on all modified files; confirm `ruff check .` exits 0 (Constitution §12)
- [x] T041 [P] Update `CHANGELOG.md` with a v1.34.0 entry in plain English (RULE 17)
- [x] T042 [P] Update version to 1.34.0 in `pyproject.toml` and `core/__version__.py` (RULE 15)
- [x] T043 [P] Update `README.md`: status table row for Spec 058, and any text describing the `<verdict>` format or JSON output (RULE 6, RULE 17)
- [x] T044 [P] Update `docs/architecture.md`: replace `<verdict>`/JSON descriptions with the plain-text contract, add `llm/reply_parsing.py` and the `reply_check`/`format_reminder` arguments, and update `CLAUDE.md`'s completed-stages table with row 058 (RULE 6, RULE 17; the CLAUDE.md edit is a governance change and needs G3 approval — ask before editing it)
- [x] T045 Run the live check from `quickstart.md` step 4 (real API spend — only after the project lead agrees, per the plan's cost note) and record the result; if it is not run, say so in the PR
- [x] T046 Self-review three times, assuming each pass missed something (G4 requirement); fix findings; push the branch and open the PR (G4)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none
- **Foundational (Phase 2)**: depends on Phase 1 — BLOCKS all stories
- **US1 (Phase 3)**: depends on Phase 2
- **US2 (Phase 4)**: depends on Phase 2; T028 (amendment, needs G3 approval) runs before T024–T027; T029 (TODO removal) also needs G3 approval
- **US3 (Phase 5)**: depends on Phase 2 (its log tests assume `log_parse_issue` and the panel wiring)
- **US4 (Phase 6)**: depends on Phase 2
- **Polish (Phase 7)**: depends on all stories

### Within Each Phase

- Tests first and confirmed FAILING before implementation
- T009 before T010 before T011; T008 before T009
- T024 → T025 → T026 → T027 in `agents/agent_satirist.py` (same file, sequential)
- T037 → T038 in `agents/agent_linkedin_post.py`; T019 (US1) edits the same file, so run US1 before US4

---

## Parallel Opportunities

- Test-writing: T002–T007 (different test files/areas), T012–T015, T020–T023 (same file, write together), T030–T031
- Implementation: T016–T019 (four different agent files); T032–T034 (three provider files)
- Polish: T040–T044

---

## Summary

| Phase | Tasks | Story | Notes |
|-------|-------|-------|-------|
| 1 Setup | T001 | — | Branch hygiene |
| 2 Foundational | T002–T011 | — | Shared parser, log type, panel wiring |
| 3 US1 MVP | T012–T019 | US1 | Tag-free panels + PICK aggregator |
| 4 US2 | T020–T029 | US2 | Labelled Satirist; G3 amendment + TODO removal |
| 5 US3 | T030–T035 | US3 | Traceable failures, stop reasons |
| 6 US4 | T036–T038 | US4 | Domain classification lines |
| 7 Polish | T039–T046 | — | ruff, docs, version, live check, PR |
| **Total** | **46 tasks** | | |
