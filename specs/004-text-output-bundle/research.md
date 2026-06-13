# Research: Text Output Bundle

## Decision 1 — How to expose conversation history from DualPersonaLoop

**Decision**: Change `DualPersonaLoop.run()` to return a new `LoopOutput` dataclass
containing both `verdict: str` (the current return value) and `log: ConversationLog`
(the full turn-by-turn history).

**Rationale**: The loop already has all turn data in local variables; collecting it into a
`ConversationLog` requires no additional API calls. Wrapping both values in `LoopOutput`
is a single structural change that keeps callers clean — they just unpack `.verdict`.

**Alternatives considered**:
- Add a `history` property on the `DualPersonaLoop` instance (caller reads it after `run()`).
  Rejected: statefulness makes testing harder and introduces a temporal coupling bug if
  `run()` is called multiple times.
- Pass a mutable list into `run()` for the caller to collect turns. Rejected: side-effect
  interface is harder to test and less readable than a return value.
- Add a separate `run_with_log()` method. Rejected: code duplication; the log is always
  needed from now on.

---

## Decision 2 — DualPersonaLoop return-type change and backwards compatibility

**Decision**: Update both `agent_0.run()` and `agent_bc.run()` to unpack `LoopOutput.verdict`
immediately at the point where they currently use the raw `str` from `DualPersonaLoop.run()`.
Each agent function stores the `LoopOutput.log` internally and either returns it as part of
its own return value or passes it up to the caller.

**Rationale**: `agent_0.run()` returns `EnrichedBrief` and `agent_bc.run()` returns
`CartoonConcept`. Neither currently returns logs. The cleanest approach is to update both
signatures to return `(EnrichedBrief, ConversationLog)` and `(CartoonConcept, ConversationLog)`
respectively — pipeline.py already calls both and will collect the logs for bundle_writer.

**Alternatives considered**:
- Store logs as module-level variables in agent_0/agent_bc (thread-unsafe, hard to test).
  Rejected.
- Return a new wrapper dataclass per agent. Rejected: equivalent to a tuple return but
  adds two new types for no benefit.

---

## Decision 3 — agent_explainer dual-LLM design

**Decision**: Claude Sonnet 4.6 is the Writer (generates HTML drafts); Gemini 2.5 Flash is
the Editor (reviews and approves). The loop uses the same `DualPersonaLoop` infrastructure
with a 3-iteration maximum (shorter than the creative loops because HTML quality converges
faster than satirical angle selection). Two independent calls generate in-language HTML and
English HTML sequentially.

**Rationale**: Reusing `DualPersonaLoop` means the `<verdict>` tag protocol and model
fallback chains come for free. Claude as Writer is correct because it produces well-structured
HTML reliably; Gemini as Editor matches the existing Agent 0 Resonator role and can verify
language accuracy for non-English outputs.

**Alternatives considered**:
- Single-LLM generation (no reviewer). Rejected: spec explicitly says dual-LLM; reviewer
  is important for language quality on non-Latin scripts.
- Gemini Writer / Claude Editor. Rejected: Claude is more reliable for structured HTML with
  correct UTF-8 declaration and semantic markup.

---

## Decision 4 — bundle_writer module boundaries

**Decision**: `bundle_writer.write_bundle()` is the single entry point for all bundle I/O.
It accepts the image output path plus the two `ConversationLog` objects, the `EnrichedBrief`,
and the image prompt string. It derives the bundle folder path from the image path
(`{dir}/{stem}/`). It formats the logs as text, calls `agent_explainer`, and writes all files.
If `agent_explainer` raises, it catches the exception, logs the error, and returns — leaving
the cartoon image and logs untouched (FR-011).

**Rationale**: Isolating all bundle I/O in one module means the pipeline only needs to call
one function and the partial-failure logic is contained.

**Alternatives considered**:
- Pipeline directly writes logs and calls agent_explainer. Rejected: duplicates path logic
  across pipeline.py; harder to test.

---

## Decision 5 — ConversationTurn verdict field values

**Decision**: `ConversationTurn.verdict` uses three string values:
`"APPROVED"`, `"NEEDS REVISION"`, and `"FINAL_SAY"`. These align with the existing
`_parse_reviewer_verdict()` return values and the Final Say Protocol flag in the loop.

**Rationale**: Keeping the same string values as the existing internal logic avoids a
translation step; the plain-text log formatter maps these to human-readable labels
(`APPROVED ✓`, `NEEDS REVISION`, `FINAL SAY (approved)`).

---

## Decision 6 — Plain-text log format

**Decision**: Each log file uses this structure per iteration:

```
=== Iteration N [/ M] ===

[ROLE — e.g. FRAMER / SATIRIST]
{full proposer text}

[ROLE — e.g. RESONATOR / CRITIC]
Verdict: APPROVED / NEEDS REVISION / FINAL SAY
{full reviewer text}

---
```

**Rationale**: Section headers make the log scannable; explicit verdict labels enable
grep-based auditing. The separator `---` cleanly delineates iterations.
