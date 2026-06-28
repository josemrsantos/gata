<!-- SPECKIT START -->
## Speckit Governance

**Constitution**: `.specify/memory/constitution.md`
All implementation plans include a Constitution Check table that gates work.
Read the constitution before starting any new stage.

**Templates**: `.specify/templates/`
- `spec-template.md` — blank spec
- `plan-template.md` — blank plan (includes 13-row Constitution Check table)
- `tasks-template.md` — blank phase-based task breakdown

**Spec artifacts**: `specs/NNN-feature-name/` (spec.md, plan.md, research.md,
data-model.md, contracts/, tasks.md, quickstart.md)

**Active stage**: 030 — documentation overhaul. See TODO.md for next items.

## Completed Stages (as of 2026-06-23)

| Spec | Name                                                    | Status |
|------|---------------------------------------------------------|--------|
| 001 | Core pipeline — B/C creative loop + image generation | ✅ |
| 002 | Community config + model fallback chains | ✅ |
| 003 | Cultural Strategist (Framer + Resonator) | ✅ |
| 004 | Text Output Bundle (logs, HTML, prompt card) | ✅ |
| 005 | Trend Scout — NewsAPI.org + Gemini topic discovery | ✅ |
| 006 | Free-text community mode | ✅ |
| 007 | Multi-panel cartoon format — --panels and --layout | ✅ |
| 008 | Multi-audience CLI | ✅ |
| 009 | Run telemetry — per-agent timing, token counts, cost | ✅ |
| 010 | Dynamic audiences | ✅ |
| 011 | Mood layer | ✅ |
| 012 | Run summary | ✅ |
| 013 | Optional HTML output | ✅ |
| 014 | Image cost pricing | ✅ |
| 015 | Single main audience | ✅ |
| 016 | Clean logging | ✅ |
| 019 | Inference model fallback | ✅ |
| 020 | Auto layout | ✅ |
| 021 | Gemini Satirist | ✅ |
| 022 | Image Evaluator | ✅ |
| 023 | Evaluator fidelity | ✅ |
| 024 | LLM provider abstraction | ✅ |
| 025 | Grok integration | ✅ |
| 026 | Protocol framework + Parallel Panel | ✅ |
| 027 | Cartoon title banner + --no-title flag | ✅ |
| 029 | Grok as primary decider — Grok-3 aggregator across all ParallelPanel agents | ✅ |
| 030 | Documentation overhaul — README + architecture doc | ✅ |
| 032 | LLM provider configurability + cross-provider fallback | ✅ |
| 033 | Enhanced cost reporting — per-model breakdown + disclaimer | ✅ |
| 034 | FairParallelPanel — multi-round parallel protocol | ✅ |
<!-- SPECKIT END -->

LLM REVIEW PROTOCOL — this is a hard stop, not a suggestion. Violating it is not acceptable under any circumstances,
even when the task feels straightforward or the next step seems obvious.

SELF-REVIEW BEFORE STOPPING FOR HUMAN REVIEW — this is a hard rule, not a suggestion, even when the task feels
straightforward or the next step seems obvious. You MUST self-review 3 times assuming on each iteration that you have
made a mistake in the previous iteration, no exceptions:

After completing the 3 self-review passes, STOP. Name the file(s) you have changed and wait for explicit human
approval before touching anything else. Do not proceed, do not summarise the code, do not start the next task.

HOW TO NOTIFY — name the file path(s) only. Do not show file contents, do not summarise the code. Example: "Please
review tests/test_agent_satirist.py before I proceed."

RULE 3 — Every test function must have a plain-English comment at the top (one sentence) explaining what the test is
checking and why it matters.

RULE 4 — Never proceed to the next task without an explicit 'approved' or 'proceed' from the human. Enthusiasm,
momentum, and task context are not substitutes for explicit approval.

RULE 5 — Every new stage (whether SDD/Speckit-driven) must start with a new git branch. No stage work
on main.

RULE 13 — At the start of every conversation, before anything else:
1. Check for pending items: open PRs, branches not yet merged into main, uncommitted changes.
2. If there are pending items, report them clearly and ask the developer how to proceed.
3. If nothing is pending, show the full TODO.md item list as a numbered one-liner list and ask
   what the next stage should be.

RULE 6 — Whenever anything new is added or changed, check README.md for outdated content. If outdated, tell the
developer exactly what is stale and propose the fix. Do not silently leave README behind.

RULE 7 — If the developer asks "what is next" or equivalent, respond with a numbered one-line-per-item list drawn
from TODO.md. Do not reorder, do not filter, do not expand — just the titles.

RULE 8 — If the developer mentions a new feature idea mid-development, ask for the title, propose a reason, reach
consensus, then add title + reason to TODO.md. Do not implement it immediately.

RULE 9 — New agents must have human-readable names (e.g. "Satirist", "Cultural Strategist"). Single-character or
numeric names (A, B, C, 0) are not acceptable.

RULE 10 — Dual-LLM agents name their sub-agents as [AGENT_NAME]_[LLM_NAME] unless a more descriptive role name
exists. E.g. satirist_satirist / satirist_critic, or satirist_Claude / satirist_Gemini.

RULE 11 — README.md must contain a table of all agents and sub-agents with a one-line description of each one's
function.

RULE 12 — It must always be possible to manually invoke the pipeline to generate a specific image. Any refactor
that removes this capability is a breaking change.

RULE 14 — Within Python function bodies, do not use blank lines as logical phase dividers. Replace them with a
short inline comment explaining why the code shifts focus at that point (e.g. what was just established, what is
now being done, or what constraint the next block enforces). Standard PEP 8 blank lines between top-level
definitions and import groups are unaffected by this rule.

RULE 15 - Before pushing anything, make sure the version is up to date.

RULE 16 - if you need secrets run: source set_gata.sh
