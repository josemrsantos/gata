# Feature Specification: Inference Model Fallback + Agent Rename

**Feature Branch**: `019-inference-model-fallback`
**Created**: 2026-06-12
**Status**: Complete

## Problem

Two issues coexisted on this branch:

1. The Cultural Strategist's `infer_audiences()` and `infer_mood()` calls used a single
   hardcoded model with no fallback. A single model failure would abort the entire run.

2. Agent names violated RULE 9: "Agent 0" (Cultural Strategist), "B" (Satirist), and
   "C" (Critic) are single-character or numeric names. All names must be human-readable.

## Goal

- Add a 3-model Gemini fallback chain to `infer_audiences()` and `infer_mood()`.
- Rename all agents to human-readable names throughout the codebase and tests.

## Technical Design

### Model fallback chain

`gemini-2.5-flash` → `gemini-2.5-pro` → `gemini-2.0-flash` (cheaper-first ordering so
the cheapest capable model is tried first, escalating only on failure).

### Renames

| Old name | New name |
|----------|----------|
| Agent 0 | Cultural Strategist |
| B / Satirist | Satirist |
| C / Critic | Critic |

Applied across: `agents/agent_cultural_strategist.py`, `agents/agent_satirist.py`,
`agents/runner.py`, all test files, and log/telemetry strings.

## Modified files

| File | Change |
|------|--------|
| `agents/agent_cultural_strategist.py` | Add fallback chain to inference calls; rename loop_name and telemetry |
| `agents/agent_satirist.py` | Rename loop_name, telemetry, and error strings |
| `agents/runner.py` | Rename print labels |
| `tests/test_agent_cultural_strategist.py` | Update agent name assertions |
| `tests/test_agent_satirist.py` | Update loop_name assertions |
