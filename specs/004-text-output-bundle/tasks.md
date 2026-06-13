# Tasks: Text Output Bundle

**Input**: Design documents from `/specs/004-text-output-bundle/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**Constitution Principle 9**: Tests are written before implementation — no exceptions.
Every implementation task in this list is preceded by its corresponding test task.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup (Baseline Verification)

**Purpose**: Confirm the existing codebase passes ruff before any changes are made.
This prevents false failures during development from pre-existing lint issues.

- [X] T001 Run `ruff check .` and `ruff format --check .` on the current codebase and fix any pre-existing issues before touching any feature files

---

## Phase 2: Foundational — New Types + DualPersonaLoop Refactor

**Purpose**: Add the shared data types and refactor DualPersonaLoop to capture conversation
history. Every user story depends on this foundation — no story can be implemented until
DualPersonaLoop.run() returns LoopOutput and both agent_0 and agent_bc return tuples.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add ConversationTurn, ConversationLog, and LoopOutput dataclasses to agents/types.py per data-model.md (no tests needed — pure data definitions with no logic)

- [X] T003 Write tests in tests/test_dual_loop.py covering: (a) run() returns a LoopOutput with a non-empty verdict string; (b) LoopOutput.log is a ConversationLog with loop_name set correctly; (c) log.turns has exactly 2 entries per iteration (proposer + reviewer); (d) each ConversationTurn has correct role, text, and verdict fields; (e) Final Say Protocol sets verdict="FINAL_SAY" on the last reviewer turn — tests MUST FAIL before T004

- [X] T004 Modify DualPersonaLoop.run() in agents/dual_loop.py to accumulate ConversationTurn objects and return LoopOutput(verdict=last_proposer_verdict, log=ConversationLog(...)) — makes T003 pass

- [X] T005 [P] Write tests in tests/test_agent_0.py covering: (a) run() returns a 2-tuple of (EnrichedBrief, ConversationLog); (b) the ConversationLog has loop_name="Agent 0"; (c) existing EnrichedBrief content is unchanged — tests MUST FAIL before T007

- [X] T006 [P] Write tests in tests/test_agent_bc.py covering: (a) run() returns a 2-tuple of (CartoonConcept, ConversationLog); (b) the ConversationLog has loop_name="B/C"; (c) existing CartoonConcept content is unchanged — tests MUST FAIL before T008

- [X] T007 Update agents/agent_0.py: change run() to unpack LoopOutput from DualPersonaLoop, return (enriched_brief, loop_output.log) as a tuple — makes T005 pass

- [X] T008 Update agents/agent_bc.py: change run() to unpack LoopOutput from DualPersonaLoop, return (concept, loop_output.log) as a tuple — makes T006 pass

- [X] T009 Update pipeline.py to unpack both tuple returns: `enriched_brief, agent0_log = agent_0.run(...)` and `concept, bc_log = agent_bc.run(...)` — pipeline must still run end-to-end without errors

**Checkpoint**: `pytest tests/test_dual_loop.py tests/test_agent_0.py tests/test_agent_bc.py` — all pass. `python pipeline.py --help` — no import errors.

---

## Phase 3: User Story 1 — Conversation Logs (Priority: P1) 🎯 MVP

**Goal**: After every pipeline run, two plain-text conversation logs appear in the bundle
folder covering every proposer and reviewer turn with full text, role labels, and verdict.

**Independent Test**: Run `python pipeline.py --community portuguese_adults`; verify
`output/portuguese_adults/{stem}/agent0_log.txt` and `bc_log.txt` exist and contain every
turn with iteration headers and APPROVED / NEEDS REVISION / FINAL SAY markers.

- [X] T010 [US1] Write tests in tests/test_bundle_writer.py covering format_log(): (a) output contains "=== Iteration N ===" header for each iteration; (b) proposer role name appears before proposer text; (c) reviewer role name and "Verdict: APPROVED" appear on approved turns; (d) "Verdict: NEEDS REVISION" appears on non-approved turns; (e) "FINAL SAY" appears when verdict is "FINAL_SAY"; (f) iterations are separated by "---" — tests MUST FAIL before T012

- [X] T011 [US1] Write tests in tests/test_bundle_writer.py covering write_bundle() log-writing paths: (a) bundle folder is created at correct path derived from output_path stem; (b) agent0_log.txt is written when agent0_log is not None; (c) bc_log.txt is written when bc_log is not None; (d) existing files are overwritten without error; (e) None logs are silently skipped — tests MUST FAIL before T012

- [X] T012 [US1] Create agents/bundle_writer.py implementing format_log(log: ConversationLog) -> str and write_bundle() that creates the bundle folder, formats logs, and writes agent0_log.txt and bc_log.txt per contracts/bundle_writer.md — makes T010 and T011 pass

- [X] T013 [US1] Write tests in tests/test_pipeline.py covering: (a) write_bundle is called after agent_d.generate() with the correct output_path, agent0_log, bc_log, enriched_brief, and image_prompt arguments; (b) write_bundle is called with available logs even when pipeline raises an exception after agent_0 completes — tests MUST FAIL before T014 and T015

- [X] T014 [US1] Update pipeline.py: pass agent0_log, bc_log, enriched_brief, and concept.image_prompt to bundle_writer.write_bundle() after agent_d.generate() in all three pipeline branches (community, manual, default)

- [X] T015 [US1] Update pipeline.py: wrap the agent_0/agent_bc/agent_d block in a try/finally so write_bundle() is always called with whatever logs are available — even on exception — implementing FR-010 partial bundle behaviour

**Checkpoint**: `pytest tests/test_bundle_writer.py tests/test_pipeline.py` — all pass. Manual run produces both log files.

---

## Phase 4: User Story 2 — In-Language Explanation HTML (Priority: P2)

**Goal**: After a pipeline run, an HTML file written in the cartoon's target language appears
in the bundle folder, suitable for publishing alongside the image.

**Independent Test**: Run pipeline for a Portuguese community; verify
`explanation.html` opens in a browser, all text is in Portuguese, the file contains a
`<meta charset="UTF-8">` declaration, and it explains the joke and cultural references.

- [X] T016 [US2] Write tests in tests/test_agent_explainer.py covering generate_html(): (a) returns a 2-tuple of (in_language_html, english_html); (b) in_language_html contains "<!DOCTYPE html>"; (c) in_language_html contains '<meta charset="UTF-8">'; (d) in_language_html contains the target language code in the lang attribute; (e) DualPersonaLoop is called exactly twice (once per HTML type); (f) RuntimeError propagates when all models are exhausted — tests MUST FAIL before T017

- [X] T017 [US2] Create agents/agent_explainer.py implementing generate_html(enriched_brief, agent0_log, bc_log, image_prompt) -> tuple[str, str] using DualPersonaLoop with Claude Writer (claude-sonnet-4-6) and Gemini Editor (gemini-2.5-flash), 3-iteration max, <verdict> tag protocol per contracts/agent_explainer.md — makes T016 pass

- [X] T018 [US2] Update agents/bundle_writer.py: call agent_explainer.generate_html() and write explanation.html and deep_dive_en.html to the bundle folder when enriched_brief and image_prompt are both non-None

- [X] T019 [US2] Write tests in tests/test_bundle_writer.py covering agent_explainer failure handling: (a) when agent_explainer.generate_html() raises, bundle_writer logs the error and returns normally; (b) agent0_log.txt and bc_log.txt are still present after an explainer failure; (c) pipeline does not exit with error code when explainer fails — tests MUST FAIL before updating bundle_writer error handling, then update bundle_writer.write_bundle() to catch explainer exceptions per FR-011

**Checkpoint**: `pytest tests/test_agent_explainer.py tests/test_bundle_writer.py` — all pass. Manual run produces explanation.html.

---

## Phase 5: User Story 3 — English Deep-Dive HTML (Priority: P3)

**Goal**: After a pipeline run, an English-language HTML file explaining the news background,
cultural references, and satirical logic appears in the bundle folder for operator use.

**Independent Test**: Open deep_dive_en.html for a Portuguese run in a browser; verify all
text is in English and a cultural outsider can describe the satirical angle and key
references after reading it.

- [X] T020 [P] [US3] Write tests in tests/test_agent_explainer.py covering the English deep-dive specifically: (a) english_html contains "<!DOCTYPE html>"; (b) english_html contains '<meta charset="UTF-8">'; (c) english_html lang attribute is "en"; (d) generate_html() passes distinct prompts to each DualPersonaLoop call — one requesting in-language output and one requesting English — tests MUST FAIL if agent_explainer uses the same prompt for both calls, then fix agent_explainer.py if needed

- [X] T021 [P] [US3] Write tests in tests/test_bundle_writer.py verifying deep_dive_en.html is written to the bundle folder independently of explanation.html (an explainer returning only english_html still writes deep_dive_en.html) — tests MUST FAIL before verifying bundle_writer handles the two HTML files independently

**Checkpoint**: `pytest tests/test_agent_explainer.py` — all pass including English-specific assertions.

---

## Phase 6: User Story 4 — Prompt Card (Priority: P4)

**Goal**: After a pipeline run, a plain-text file containing only the verbatim image prompt
appears in the bundle folder, enabling standalone reuse of the prompt.

**Independent Test**: Run pipeline; verify `prompt_card.txt` contains exactly
`concept.image_prompt` — byte-for-byte identical — with no surrounding text or newlines
beyond the prompt itself.

- [X] T022 [US4] Write tests in tests/test_bundle_writer.py covering prompt card: (a) prompt_card.txt is written to the bundle folder when image_prompt is not None; (b) file contents equal the verbatim image_prompt string with no extra whitespace; (c) when image_prompt is None, prompt_card.txt is not written — tests MUST FAIL before T023

- [X] T023 [US4] Update agents/bundle_writer.py to write prompt_card.txt containing only the image_prompt string when image_prompt is non-None — makes T022 pass

**Checkpoint**: `pytest tests/test_bundle_writer.py` — all pass. Manual run produces prompt_card.txt.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Ruff compliance, UTF-8 safety, and quickstart validation across all stories.

- [X] T024 [P] Run `ruff check agents/types.py agents/dual_loop.py agents/agent_0.py agents/agent_bc.py agents/agent_explainer.py agents/bundle_writer.py pipeline.py tests/test_dual_loop.py tests/test_agent_0.py tests/test_agent_bc.py tests/test_agent_explainer.py tests/test_bundle_writer.py tests/test_pipeline.py` and fix all issues

- [X] T025 [P] Run `ruff format agents/types.py agents/dual_loop.py agents/agent_0.py agents/agent_bc.py agents/agent_explainer.py agents/bundle_writer.py pipeline.py tests/test_dual_loop.py tests/test_agent_0.py tests/test_agent_bc.py tests/test_agent_explainer.py tests/test_bundle_writer.py tests/test_pipeline.py` and verify no diffs

- [X] T026 Write a test in tests/test_agent_explainer.py verifying that generate_html() produces in_language_html containing `<meta charset="UTF-8">` regardless of the target language (FR-012 UTF-8 safety)

- [X] T027 Run the full test suite `pytest` and confirm zero failures before marking feature complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — run immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 Logs)**: Depends on Phase 2 — first story to implement
- **Phase 4 (US2 In-Language HTML)**: Depends on Phase 3 (bundle_writer must exist)
- **Phase 5 (US3 English HTML)**: Depends on Phase 4 (agent_explainer must exist)
- **Phase 6 (US4 Prompt Card)**: Depends on Phase 3 (bundle_writer must exist); can run in parallel with Phase 4 and 5
- **Phase 7 (Polish)**: Depends on all phases complete

### Within Each Phase

- Test tasks MUST be written and confirmed to FAIL before their paired implementation task
- Within Phase 2: T002 → T003 → T004 → (T005 ∥ T006) → T007 → T008 → T009
- Within Phase 3: T010 → T011 → T012 → T013 → T014 → T015
- Within Phase 4: T016 → T017 → T018 → T019
- Within Phase 5: T020 ∥ T021 (different files)
- Within Phase 6: T022 → T023

### Parallel Opportunities

- T005 and T006 (Phase 2): Both test files are independent — write simultaneously
- T007 and T008 (Phase 2): Both agent updates are independent — implement simultaneously
- T020 and T021 (Phase 5): Different test files — write simultaneously
- T024 and T025 (Phase 7): ruff check and ruff format are independent

---

## Parallel Example: Phase 2 (Foundational)

```
# After T002 (types) and T004 (DualPersonaLoop):
Launch in parallel:
  Task T005: Write agent_0 tuple-return tests in tests/test_agent_0.py
  Task T006: Write agent_bc tuple-return tests in tests/test_agent_bc.py

# After T005 and T006 both confirmed failing:
Launch in parallel:
  Task T007: Update agents/agent_0.py
  Task T008: Update agents/agent_bc.py
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T009)
3. Complete Phase 3: Conversation Logs (T010–T015)
4. **STOP and VALIDATE**: Both log files appear after a real pipeline run
5. Feature is already useful for pipeline auditing

### Incremental Delivery

1. Setup + Foundational → DualPersonaLoop refactored; existing pipeline unbroken
2. US1 (Logs) → Audit trail available; MVP complete
3. US2 (In-Language HTML) → End-user explanation publishable
4. US3 (English HTML) → Operator deep-dive available
5. US4 (Prompt Card) → Prompt reuse enabled
6. Polish → All ruff checks pass; UTF-8 verified

---

## Notes

- Constitution Principle 9 mandates TDD — confirm each test FAILS before writing the implementation
- Constitution Principle 12: all imports at top of file; no blank lines as section dividers
- Constitution Principle 13: use logging module; no bare print()
- All [P] tasks touch different files — safe to parallelize
- bundle_writer.write_bundle() must never raise — all exceptions are caught and logged
- agent_explainer.generate_html() may raise — bundle_writer catches it per FR-011
