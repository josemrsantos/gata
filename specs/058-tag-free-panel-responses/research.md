# Research: Tag-free, JSON-free panel responses

All items below were resolved from the code and the spec; no external research was needed.

## R1 — Who uses the strict extractor?
- **Finding**: every production panel is a `FairParallelPanel`. `DualPersonaLoop` and `ParallelPanel` are
  not constructed by any agent (only their own modules and tests).
- **Decision**: leave `_extract_proposer_verdict` and both classes unchanged; add `llm/reply_parsing.py`.
- **Alternatives**: edit the strict function (rejected — it would change `DualPersonaLoop`'s contract);
  delete the unused classes (rejected — out of scope).

## R2 — Truncation vs format-ignoring (TODO question)
- **Finding**: Claude already exposes `stop_reason` (`max_tokens`); Gemini exposes
  `candidates[0].finish_reason`; Grok (OpenAI-compatible) exposes `choices[0].finish_reason`.
- **Decision**: add optional `TokenUsage.stop_reason`; every parse log line includes it plus
  `output_tokens` vs `max_tokens`. If a provider yields nothing the field is simply omitted (FR-008 is
  best effort). Live proof for each provider is part of the quickstart.

## R3 — Which provider/model answered, after fallbacks?
- **Finding**: `PersonaConfig.providers` is a fallback chain, and `_call_persona` returns only
  `(text, usage)`; `usage.model` names the model that actually answered.
- **Decision**: build `ParseContext.model` from `usage.model`; no signature change to `_call_persona`.
  Agent-level parsers (Satirist, Domain Classification) read the aggregator's `usage` from the last entry of
  `loop_output.telemetry.calls`.

## R4 — How is "unusable" decided per agent?
- **Decision**: `FairParallelPanel(reply_check=..., format_reminder=...)`. `reply_check(reply)` returns
  `None` if usable, else a reason string. Agents without a check are retried only for an empty reply
  (Q2 clarification). Satirist's check is the FR-006 required-field rule.
- **Alternatives**: put the rule in `PersonaConfig` (rejected — both panelists and the aggregator share one
  check but need different reminders in a few cases); raise from the agent parser (rejected — parsing
  happens after the panel returns, too late for the retry).

## R5 — Keeping the Spec 052/057 fallbacks (TODO question)
- **Decision**: kept inside `unwrap_reply` (closed tag, unclosed tag, bare fenced JSON). A tagged reply is
  still accepted; the Satirist still accepts JSON content. Both log a WARNING so legacy shapes stay visible.

## R6 — DualPersonaLoop reviewer verdict (TODO question)
- **Decision**: unchanged (already `APPROVED` / `NEEDS REVISION`, and unused by agents). Revisit only if a
  failure is observed.

## R7 — Explainer HTML
- **Finding**: the Explainer's reply is a full HTML page. Whole-reply capture is correct, but models often
  wrap HTML in a ```html fence.
- **Decision**: `unwrap_reply` removes one surrounding code fence for every agent. Preamble prose before
  the HTML is not stripped (same exposure as today when a tag is missing).

## R8 — Out of scope but nearby
- `agent_image_evaluator.py` also parses JSON, but it is a single-model call, not a panel; the spec
  covers panels only. Noted for a possible later spec.

## R9 — Existing tests that assert old prompt wording
- Tests asserting `<verdict>` in prompts will be updated, not deleted, so the new wording is covered. The
  exact list is produced in tasks.md by grepping `tests/` for `verdict`.
