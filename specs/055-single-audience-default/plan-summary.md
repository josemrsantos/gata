# Plan Summary: Single-audience default for gata

**Spec**: `055-single-audience-default` · **Date**: 2026-10-04 · **For**: human approval at gate G2
*One page, plain English, no file-by-file detail. The plan and tasks are the source of
truth; if they disagree with this page, the plan wins and this page is regenerated.*

## 1. What and why
`gata "<topic>"` will produce one cartoon, for UK software engineers, instead of guessing
about two audiences. Each extra audience is a full paid run, so the default stops paying
for a cartoon you usually don't need. Other audiences stay available on request.

## 2. What changes for you
- **Cost and time**: a run drops from about two audiences to one — roughly $0.20 and about
  5 minutes saved per run (an older one-audience run in the repo cost $0.20 and took 320 s;
  today's prices differ a little).
- **Behaviour you'll notice**: the output folder now has `uk-tech-engineers.png` instead of
  a guessed audience plus `uk.png`. `--audience NAME` (repeatable) picks audiences from
  `communities.yaml`; `--infer-audiences` brings back exactly today's behaviour.
- **Breaking, on purpose**: anything that relied on the guessed audiences or on the folder
  `uk/` must change (see decision 1, the newsletter merge).
- **Risk and undo**: low. The change is one file (`gata`'s entry point) plus tests and docs;
  `--infer-audiences` is the undo, and the pipeline itself is untouched.

## 3. Decisions I need from you
| # | Decision | My recommendation | Why |
|---|----------|-------------------|-----|
| 1 | `newsletter_merge.py` reads `<story>/uk/…` by default and will fail on new default runs (they write `uk-tech-engineers/`). Change its default to `uk-tech-engineers`, leave it, or make it accept both? | Change the default (A) | One small change plus a test and doc line; the error today says exactly what is missing. Accepting both (C) is friendlier to old editions but adds logic. If you pick A or C I add it to the spec and tasks. |
| 2 | Run one optional paid smoke test (a single `gata` run) before the PR? | Yes | About $0.20 and 5 minutes; it is the only check with real models. |
| 3 | Make file names safe for named audiences (strip odd characters from community names before using them as file names)? | Yes | Cheap, and names like `uk-tech-engineers` are unchanged; today inferred names are not sanitized either. |
| 4 | Version bump `1.30.0` → `1.31.0` (new flag, changed default)? | Yes | Matches how earlier specs did it. |

## 4. Decisions already made
Your five answers in the spec (community names only; `--audience` replaces the default and
`--infer-audiences` restores the old behaviour; the default is built into `gata`; layout stays
automatic; `--research-only` uses the first selected audience), recorded in the spec's
Clarifications. Three assumptions of mine still need your OK: the built-in default also answers
to its own name when `communities.yaml` is absent; when the file exists it is the only source of
names (even for `uk-tech-engineers`); `--infer-audiences` together with `--audience` is rejected.

## 5. Scope
**In**: the `gata` command's audience selection, its tests, README, architecture doc,
CHANGELOG, version, CLAUDE.md row, TODO item removal.
**Out**: `pipeline.py`, models, layout, `communities.yaml` contents, the agents.

## 6. Cost and time
No real API calls in the test suite. Optional smoke test ≈ $0.20, ≈ 5 minutes. Work is 41
tasks, all in `core/cli.py` and `tests/test_cli.py` plus docs; nothing here can exceed the
estimate except decision 1 if you choose the "accept both" option.

## 7. Verified vs assumed
**Verified**: I read the current `gata` code, `communities.yaml`, the loader and specs 008/010/015;
the newsletter-merge default and its failure message; the per-run cost from a real `summary.txt`;
10 of the 13 CLI tests run `gata` and some will need `--infer-audiences`.
**Only assumed**: nothing else in this repo depends on `gata`'s audience folders (a search found
none; scripts outside the repo are unknown).

## 8. What would surprise you
- The newsletter merge breaks on new default runs (decision 1).
- This spec **supersedes** two earlier rules for default runs: spec 010's "a UK audience is always
  present" and spec 015's "main audience plus UK". They still hold under `--infer-audiences`.
- About 10 existing CLI tests are rewritten, and the suite is red between two tasks while that
  happens (nothing is pushed in that window).
- `/speckit-analyze` found 1 HIGH (decision 1), 2 MEDIUM and 3 LOW. I fixed the 2 MEDIUM and 1 LOW
  in the task text; the other 2 LOW are decisions 2 and 3 above. None unfixed besides the decisions.

## 9. Detail, if you want it
[spec.md](spec.md) · [plan.md](plan.md) · [tasks.md](tasks.md) · [research.md](research.md) ·
[contracts/cli-contract.md](contracts/cli-contract.md) · [quickstart.md](quickstart.md)
