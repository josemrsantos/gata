<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/007-multi-panel-cartoon/plan.md

## Project Status (as of 2026-06-12)

Stages 1–9 are complete and merged into main.

| Stage | Name | Status |
|-------|------|--------|
| 1 | Core pipeline (B/C creative loop + image generation) | ✅ Complete |
| 2 | Community config + model fallback chains | ✅ Complete |
| 3 | Agent 0 — Cultural Strategist (Framer + Resonator) | ✅ Complete |
| 4 | Text Output Bundle (logs, HTML explanations, prompt card) | ✅ Complete |
| 5 | Housekeeping + rules redefinition | ✅ Complete |
| 6 | Trend Scout — automated topic discovery via NewsAPI.org + Gemini | ✅ Complete |
| 7 | Comedy style configuration via humor.yaml | ✅ Complete |
| 8 | Free-text community mode — --community accepts any description | ✅ Complete |
| 9 | Multi-panel cartoon format — --panels and --layout flags | ✅ Complete |
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

RULE 5 — Every new stage (whether SDD/Speckit-driven or ad-hoc) must start with a new git branch. No stage work
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
