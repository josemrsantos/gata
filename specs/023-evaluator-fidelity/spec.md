# Feature Specification: Image Evaluator — Concept Fidelity Check

**Feature Branch**: `023-evaluator-fidelity`
**Created**: 2026-06-19
**Status**: Complete

## Problem

The Stage 022 evaluator checked for technical artifacts and funniness but did not verify
that the rendered image actually depicted the intended concept. Demonstrated by a real run:

- Topic: "Why did the chicken cross the road"
- Approved concept: Gata beside a spider diagram dissecting the joke — nodes labelled
  "PROTEST VOTE?", "FIXED-RATE MORTGAGE", "LITERAL OBLIVION (STATISTICALLY PREFERABLE)"
- Actual image: "THE PERPETUAL GRIEVANCE CYCLE" — a circular British weather diagram

The image was visually convincing (Gata present, correct newsroom, funny chalkboard
diagram) and would have passed the Stage 022 artifact + funniness checks. The image model
had silently substituted a different-but-related visual.

## Goal

The evaluator must explicitly compare the rendered image against the specific intended
concept, not just check for technical defects. Thematic similarity is not concept fidelity.

## Technical Design

### New evaluation criterion: concept fidelity

A dedicated **CONCEPT FIDELITY CHECK** section is added to `_build_eval_prompt()`,
positioned before the funniness check (objective question first, subjective second).

Key prompt additions:
- Explicit statement: "Thematic similarity is NOT sufficient."
- Concrete counter-example: weather cycle vs. chicken-joke spider diagram.
- Named-element check: "Are the specific diagrams, labels, objects, and board text present?"
- Substitution detector: "Has the image model silently replaced the concept with a
  different-but-related visual?"
- Prefix convention: fidelity failures are reported as
  `"Fidelity failure: intended [X], image shows [Y]"` so they are distinguishable from
  technical artifacts in logs.

### No schema change

Fidelity failures land in the existing `artifacts` list. The verdict logic
(`not artifacts and is_funny → APPROVED`) handles them automatically.

### System prompt update

`_SYSTEM_PROMPT` updated from "two criteria" to "three criteria" and documents the
prefix convention for both artifact types.

## Modified files

| File | Change |
|------|--------|
| `agents/agent_image_evaluator.py` | `_SYSTEM_PROMPT` + `_build_eval_prompt()` |
| `tests/test_agent_image_evaluator.py` | 6 new fidelity tests (26 total) |
| `TODO.md` | Add stage entry |
