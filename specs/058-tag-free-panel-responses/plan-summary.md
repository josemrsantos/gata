# Plan Summary: Tag-free, JSON-free panel responses

**Spec**: `058-tag-free-panel-responses` · **Date**: 2026-10-27 · **For**: human approval at gate G2
*One page, plain English, no file-by-file detail. The plan and tasks are the source of
truth; if they disagree with this page, the plan wins and this page is regenerated.*

## 1. What and why
Models keep ignoring our `<verdict>` tags and "return JSON" instructions, so each slip costs a retry, a
lost panelist or a noisy warning. We stop asking for tags and JSON: panelists just answer, the aggregator
writes `PICK: N` then its answer, and the Satirist and the source-classifier use simple `LABEL: value`
lines that the code reads forgivingly. Every parse failure is logged with who, which round, which model,
what was wrong and what we did about it.

## 2. What changes for you
- Prompts change for all panels; the cartoons, articles and files you get should look the same.
- `run.log` warnings become traceable (agent, round, model, field, default, first 400 characters, and stop
  reason where the provider gives one, so truncation can be told from format-ignoring).
- Cost: no extra calls on the normal path; an unusable aggregator reply now gets one retry (new).
- Risk: a prompt change can shift model behaviour; old-format replies are still accepted as a safety net.
- Reversible: yes, by reverting the PR; the old strict parser is left untouched.

## 3. Decisions I need from you
| # | Decision | My recommendation | Why |
|---|----------|-------------------|-----|
| 1 | Approve constitution amendment v1.6 (§3 and §6: plain-text/`PICK: N` contract and a `LABEL: value` Satirist schema with the same fields) | Approve | The current rules require `<verdict>` JSON; the feature cannot ship without it. Done before any Satirist code (T028). |
| 2 | Approve removing the "Tag-free, JSON-free" and "Satirist output-format wording" items from `TODO.md` in the PR (RULE 19 / RULE 8) | Approve | The second is a subset of this spec. |
| 3 | Approve a `CLAUDE.md` completed-stages row for 058 (governance edit) | Approve | Keeps the stage table current. |
| 4 | Run one live `gata` check (SC-005) at the end | Yes, once | Only real proof the warnings are gone; cost not estimated (see 6). |

## 4. Decisions already made
- New spec 058, Flow-Forward — your answer to the RULE 18 question, this session.
- Keep the Spec 052/057 fallbacks; leave the `DualPersonaLoop` reviewer verdict alone; this supersedes the
  Satirist wording TODO item — spec Assumptions, shown at G1 and approved.
- Missing Satirist labels: scene/beat required, title/caption/layout default — clarification Q1.
- Each agent supplies its own retry reminder — Q2. Log excerpt is 400 characters — Q3.

## 5. Scope
**In**: Cultural Strategist, Satirist, Explainer, Engagement Image, LinkedIn Angle Planning/Writing and
Domain Classification prompts and parsing; a new shared tolerant parser; stop reason on all three
providers; tests, docs, changelog and version 1.34.0.
**Out**: `DualPersonaLoop`/`ParallelPanel` (unused by agents, kept strict); the Image Evaluator's JSON;
image generation; panel structure, rounds, timeouts and cost reporting.

## 6. Cost and time
- Development: no API spend; all tests mock providers.
- Live check: one normal `gata` run. **I could not estimate it** — no `TOTAL:` line was found under
  `output/`. You would see the real figure in that run's `TOTAL:` line; say if you want a cap.
- Effort: 46 tasks, roughly the size of specs 052 plus 057 combined; most work is prompt/parse edits in
  six agent files plus one new module.
- Could exceed estimate if a provider hides its stop reason (we then log without it) or if prompt changes
  need tuning after the live run.

## 7. Verified vs assumed
**Verified**: the code paths in the shared panel, strict extractor, Satirist, Cultural Strategist and
Domain Classification were read; every production panel is a `FairParallelPanel`; Claude exposes
`stop_reason`; current version is 1.33.0.
**Only assumed**: Gemini and Grok expose a finish reason as expected; the Explainer, Engagement Image and
LinkedIn Angle prompts need only wording changes (read by prompt lines, not end to end); the full list of
existing tests asserting old prompt wording (found by running the suite). Nothing has been run yet.

## 8. What would surprise you
- New behaviour not in your original TODO item: an unusable **aggregator** reply is now retried once
  (added to spec FR-008a at analyze).
- The Explainer's HTML only has a surrounding code fence stripped; prose before the HTML is not removed.
- Analyze findings: D1 (constitution ordering), I1, U1, C1, C2, G1 were all fixed in `tasks.md`/`spec.md`.
  **B1 (live-run cost) is not fixed** — no estimate exists.
- `tasks.md` task T028 (the amendment) is numbered after T024 but runs first; the file says so.
- The Bash tool is broken in this session; commands run through the PyCharm terminal.

## 9. Detail, if you want it
[spec.md](spec.md) · [plan.md](plan.md) · [tasks.md](tasks.md) · [research.md](research.md) ·
[data-model.md](data-model.md) · [contracts/reply-formats.md](contracts/reply-formats.md) ·
[quickstart.md](quickstart.md) · analyze result: the report in this session (7 findings, 1 CRITICAL, all
fixed except B1).
