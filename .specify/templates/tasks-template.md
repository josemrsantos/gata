# Tasks: [FEATURE NAME]

**Input**: Design documents from `specs/NNN-feature-slug/`
**Branch**: `NNN-feature-slug`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅ (if created),
contracts/ ✅, quickstart.md ✅

**Tests**: Constitution §9 mandates tests before implementation — no exceptions. Test
tasks appear before their corresponding implementation tasks in every phase.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, …)
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: Confirm branch hygiene before any code is written (RULE 5).

- [ ] T001 Confirm active git branch is `NNN-feature-slug`; if on `main`, switch before touching any source file

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: [What shared types, configs, or infrastructure must exist before user story work begins?]

**CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 [description — exact file path]

**Checkpoint**: `[shell command that verifies this phase is done]`

---

## Phase 3: User Story 1 — [Title] (Priority: P1) MVP

**Goal**: [One sentence.]

**Independent Test**: `[shell command from spec.md]`

### Tests for User Story 1 — Write FIRST, Confirm FAILING Before Implementation

- [ ] T003 [P] [US1] Write failing tests for [feature] in `tests/test_[module].py`

> **STOP**: Confirm T003 tests all FAIL (`python -m pytest tests/test_[module].py -v`)
> before proceeding to T004.

### Implementation for User Story 1

- [ ] T004 [US1] Implement [feature] in `[file path]`

> **STOP**: Run `python -m pytest tests/ -v` — confirm all tests in this phase PASS
> before proceeding.

**Checkpoint**: `[end-to-end shell command demonstrating this story works]`

---

## Phase N: Polish & Cross-Cutting Concerns

- [ ] TNN [P] Run `ruff check . --fix` and `ruff format .` on all modified files; confirm `ruff check .` exits 0
- [ ] TNN [P] Update `README.md` if any new flags, agents, or public interfaces were added (RULE 6, RULE 11)
- [ ] TNN [P] Update version in `pyproject.toml` and `core/__version__.py` (RULE 15)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2
- **Polish (Phase N)**: Depends on all desired user stories being complete

### Within Each Phase

- Test tasks MUST be written and verified to FAIL before implementation tasks begin
- [List any intra-phase sequential constraints]

---

## Parallel Opportunities

[List tasks tagged [P] that can run simultaneously]

---

## Summary

| Phase | Tasks | Story | Notes |
|-------|-------|-------|-------|
| 1 Setup | T001 | — | Branch hygiene |
| 2 Foundational | T002 | — | Shared types |
| 3 US1 MVP | T003–T004 | US1 | Core feature |
| N Polish | TNN–TNN | — | ruff + README + version |
| **Total** | **N tasks** | | |
