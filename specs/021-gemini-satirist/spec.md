# Feature Specification: Gemini-Only Satirist/Co-Satirist Loop

**Feature Branch**: `021-gemini-satirist`
**Created**: 2026-06-13
**Status**: Complete

## Problem

The Satirist role was filled by Claude, and the Critic acted as a gatekeeper evaluating
the Satirist's output against a rules checklist. Empirical observation showed that Gemini
delivers stronger, more culturally-aware jokes than Claude. The adversarial creator/gatekeeper
structure also meant the Critic was optimising for rule compliance rather than for the best
possible joke.

## Goal

Replace Claude with Gemini in the Satirist role. Redesign both agents as co-collaborators
with the same objective — the funniest possible concept — rather than creator vs. evaluator.
The Co-Satirist can respond with an improved JSON concept (not just approve/reject), and the
Satirist incorporates it in the next iteration.

## Technical Design

### Model lists

```python
_GEMINI_SATIRIST_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]
_GEMINI_CO_SATIRIST_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
```

Satirist leads with the most capable model; Co-Satirist leads with the faster model to
keep iteration cost low.

### Co-Satirist behaviour

- `<verdict>APPROVED</verdict>` — terminates the loop.
- `<verdict>NEEDS REVISION</verdict>` followed by improved JSON — the Satirist uses it
  in the next iteration. No meta-commentary; just the improved concept or APPROVED.

### Removed

- `_build_critic_system_prompt()` — replaced by `_build_co_satirist_prompt()`.
- Rules checklist (PUNCHING UP, VISUAL-FIRST, JOKE MECHANICS, etc.) — irrelevant when
  both agents are chasing the joke rather than checking compliance.

## Modified files

| File | Change |
|------|--------|
| `agents/agent_satirist.py` | New model lists; `_build_co_satirist_prompt()`; updated `run()` |
| `agents/runner.py` | Print label updated to "Satirist/Co-Satirist..." |
| `tests/test_agent_satirist.py` | Replace rules-checklist tests with co-satirist contract tests |
| `TODO.md` | Add stage entry |
