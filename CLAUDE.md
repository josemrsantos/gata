<!-- SPECKIT START -->
## Speckit Governance

**Constitution**: `.specify/memory/constitution.md`
All implementation plans include a Constitution Check table that gates work.
Read the constitution before starting any new stage.

**Templates**: `.specify/templates/`
- `spec-template.md` — blank spec
- `plan-template.md` — blank plan (includes 13-row Constitution Check table)
- `tasks-template.md` — blank phase-based task breakdown
- `plan-summary-template.md` — the one-page human summary approved at gate G2

**Spec artifacts**: `specs/NNN-feature-name/` (spec.md, plan.md, plan-summary.md,
research.md, data-model.md, contracts/, tasks.md, quickstart.md)

**Active stage**: See TODO.md for candidate next features; the table below reflects
what has already merged to `main`.

## Completed Stages (as of 2026-10-04)

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
| 035 | Direct Satirist mode — --direct flag bypasses Cultural Strategist | ✅ |
| 036 | Per-provider call timeout — optional timeout field in providers.yaml | ✅ |
| 039 | Provider pricing & model currency refresh — corrected cost tables, replaced retired/dead default models (grok-3→grok-4.3, grok-3-mini→grok-build-0.1, gemini-2.0-flash→gemini-2.5-flash-lite) | ✅ |
| 041 | Newsletter engagement image & notification — `newsletter_merge.py` auto-generates `engagement_image.png` (FairParallelPanel concept panel + shared `core/image_generation.py` renderer) and `edition_notification.txt` (network teaser, same merge call) | ✅ |
| 042 | Researched LinkedIn article — `--linkedin-post` article is independently researched by Claude/Gemini/Grok (each with its own real web search), angle-planned and written via two FairParallelPanel stages, with a repeatable `--angle` flag and a code-built Sources list | ✅ |
| 043 | Uniform source titles — every Sources-list entry reads as `domain - page title` regardless of provider; Gemini/Grok resolve it via a direct `httpx` fetch of the cited URL, Claude gets a domain prefix added to its own already-good title | ✅ |
| 044 | Descriptive source titles — a 4-step chain (fetched `<title>`/`og:title`/`twitter:title` → humanised URL-path slug → the source's own provider's same-call title → drop) replaces the single-tier fetch, so no source is ever published as a bare domain or the site's own name restated | ✅ |
| 045 | LinkedIn feature image size correction — `engagement_image.png` and, with `--linkedin-post` on a single-panel/horizontal cartoon, `cartoon.png` are corrected in Python (Gemini aspect-ratio hint + Pillow centre-crop/resize) to exactly LinkedIn's 1200x644 Article-cover size, so LinkedIn's own auto-crop never clips the image | ✅ |
| 046 | Research-only mode — `--research-only` skips the entire satirical pipeline (Cultural Strategist, Satirist, Image Generator, Image Evaluator) and runs only the research/angle-planning/writing engine, producing a neutral `research_report.md` by default or the branded `linkedin_post.md` when combined with `--linkedin-post`; on the `gata` CLI it runs once (first inferred audience) instead of once per audience | ✅ |
| 050 | Quieter default terminal output + persistent logging — terminal print collapses to progress markers + a single `TOTAL:` line by default, restored via new `--verbose`/`-v` flag (also unifies `pipeline.py`'s log level with `gata`'s); every run persists its own `WARNING`+ messages to a new `run.log` in its bundle regardless of verbosity | ✅ |
| 052 | FairParallelPanel verdict truncation fix — `_extract_proposer_verdict()` recovers a response truncated before its closing `</verdict>` tag (max_tokens cutoff) instead of dropping the panelist; LinkedIn Angle Planning's `max_tokens` raised 1200→2500, the one call site with live-proven evidence | ✅ |
| 054 | Model currency refresh II — default models, fallback chains and cost tables refreshed for Claude, Gemini and Grok (verified against official docs plus a live call per default); Claude defaults → `claude-sonnet-5-5`/`claude-opus-5-5`, Gemini Flash-Lite → `gemini-3.5-flash-lite`, image chain → `gemini-3.1-flash-image` → `gemini-3-pro-image`; constitution v1.3 | ✅ |
| 055 | Single-audience default for `gata` — `gata "topic"` generates one cartoon for the built-in `uk-tech-engineers` audience (no audience guessing, no always-added UK); repeatable `--audience NAME` (community names, replaces the default) and `--infer-audiences` (restores the old behaviour); `newsletter_merge.py` defaults to the `uk-tech-engineers` folder | ✅ |
<!-- SPECKIT END -->

LLM REVIEW PROTOCOL — approval gates. These are hard stops; nothing else is. Violating a gate is not acceptable.

STOP and wait for an explicit "approved"/"proceed" at exactly these gates:

  G1  SPEC        after /speckit-specify + /speckit-clarify. The spec is the contract.
  G2  PLAN SUMMARY after /speckit-plan + /speckit-tasks + /speckit-analyze (findings fixed or
                  listed). The human approves ONE page of plain English, `specs/NNN/plan-summary.md`
                  (template: `.specify/templates/plan-summary-template.md`). The plan and tasks stay
                  LLM-facing and are the source of truth; if they disagree with the summary, the
                  plan wins and the summary is regenerated.
  G3  GOVERNANCE  any constitution amendment, any CLAUDE.md rule change, any TODO.md add/remove/
                  reorder (RULE 8), any new spec number (RULE 18). G3 fires only when one of these
                  actually happens, not on every spec.
  G4  PR READY    after implementation, the self-review below, and the PR is opened. Merging or
                  approving a PR happens only on an explicit instruction.

STOP and ask, mid-work, only when:
  - a result contradicts the approved spec/plan or an earlier decision (e.g. a live check fails, or a
    plan assumption turns out wrong);
  - the work would exceed the approved scope or the stated cost estimate;
  - the next action is destructive or outward-facing beyond the stage branch (anything on main,
    deleting branches, spending money not covered by the plan).

Do NOT stop for approval between tasks, between phases, or before commits on the stage branch. Once G2
is approved, run /speckit-implement to PR-ready without asking to continue. Pushing the stage branch
and opening the PR are part of G4.

SELF-REVIEW — before presenting G1, G2 or G4, self-review 3 times, assuming on each pass that the
previous pass made a mistake; fix what you find. Not after every task.

HOW TO PRESENT A GATE — list the files to review as clickable links, list the decisions needed from the
human, and state what was verified (tests, lint, live checks) and what was not. Do not summarise the code.

PLAN SUMMARY RULES — plain English, about one page. It MUST contain: (1) what and why in 3 lines;
(2) what changes for the human — behaviour, cost, risk, reversibility; (3) decisions needed, each with a
recommendation; (4) decisions already made, with where they were made; (5) in scope / out of scope;
(6) cost and time estimate; (7) what was verified versus only assumed; (8) what would surprise the human —
every deviation from the spec and every unfixed /speckit-analyze finding; (9) links to the spec, plan,
tasks and analyze result. Nothing in the plan may be hidden from it.

SPEC-KIT FLOW — use the full sequence: specify → clarify → plan → tasks → analyze → implement.
/speckit-analyze runs after tasks and before implement; its CRITICAL and HIGH findings are fixed (with the
human's approval of the edits) before G2. /speckit-checklist only when the human asks for it.

RULE 3 — Every test function must have a plain-English comment at the top (one sentence) explaining what the test is
checking and why it matters.

RULE 4 — Never cross a gate (G1–G4) without an explicit 'approved' or 'proceed' from the human.
Enthusiasm, momentum and task context are not approval. A standing instruction from the human
("run to PR-ready") is approval for that spec only.

RULE 5 — Every new stage (whether SDD/Speckit-driven) must start with a new git branch. No stage work
on main.

RULE 13 — At the start of every conversation, before anything else:
1. Check for pending items: open PRs, branches not yet merged into main, uncommitted changes.
2. If there are pending items, report them clearly and ask the developer how to proceed.
3. If nothing is pending, show the full TODO.md item list as a numbered one-liner list and ask
   what the next stage should be.

RULE 6 — Whenever anything new is added or changed, check README.md and docs/architecture.md for outdated
content. If outdated, tell the developer exactly what is stale and propose the fix. Do not silently leave README
or architecture docs behind.

RULE 7 — If the developer asks "what is next" or equivalent, respond with a numbered one-line-per-item list drawn
from TODO.md. Do not reorder, do not filter, do not expand — just the titles.

RULE 8 — If the developer mentions a new feature idea mid-development, ask for the title, propose a reason, reach
consensus, then add title + reason to TODO.md. Do not implement it immediately. Nothing may be added to, or removed
from, TODO.md without the developer's express approval of that specific change — reaching consensus on the idea
itself is not approval to write it to the file; show the proposed entry (or removal) and wait for an explicit go-ahead.

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

RULE 17 — Before a spec PR is merged, three documents must be updated as hard gates (not suggestions):
1. CHANGELOG.md — add a new version entry with a plain-English summary of what changed.
2. README.md — reflect any new CLI flags, config files, or agent behaviour; update the status table.
3. docs/architecture.md — update protocol names, add new flags, update any diagrams or examples that reference changed components.
If any of these is stale, do not merge until it is fixed.

RULE 18 — Before creating a new spec number for a feature/change request, check whether it is an evolution of an
already-shipped, still-active spec. If so, default to spec-kit's "Living Spec" model: amend that spec's existing
spec.md/plan.md in place (regenerating plan.md/tasks.md as needed) rather than creating a new spec folder. Reserve a
new spec number ("Flow-Forward") for genuinely new capability, or when the developer explicitly wants a preserved
historical record for this specific change. State which model applies, and to which existing spec, before
proceeding — get the developer's confirmation before creating a new spec folder.

RULE 19 — When a TODO.md item is being implemented as a spec, remove that item from TODO.md as part of the same
PR — not a separate follow-up cleanup.
