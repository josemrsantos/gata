# Research: Single-audience default for gata

**Date**: 2026-10-04. All findings below come from reading the current code
(`core/cli.py`, `core/config_loader.py`, `core/types.py`, `tests/test_cli.py`,
`communities.yaml`) and the earlier specs 008, 010, 015. No external research was
needed: this feature changes which audiences the existing pipeline is called for.

## Findings about today's behaviour

- `gata` builds audiences as `_ensure_uk(infer_audiences(topic))` and loops
  `run_pipeline()` once per audience (`core/cli.py`), writing
  `<topic-folder>/<audience.name>.png`.
- `AudienceProfile(name, audience, language, tone)` is all `gata` uses. The
  `Community` type has the same three fields (`target_audience`, `output_language`,
  `tone`) plus `panels`/`layout`/`topics`/`news_sources`, which `gata` never passes on.
- `load_communities(path)` raises `ValueError` for a missing file, bad YAML or an
  invalid entry. `pipeline.py` treats an absent `communities.yaml` as normal; the file
  is read from the **current folder**.
- `--research-only` today calls `infer_audiences(topic)[0]` once and does not use
  `_ensure_uk` or the loop.
- Spec 010 requires "a UK audience is always present"; spec 015 made the default
  "main audience plus UK". Both are superseded for default runs by this spec.
- About 10 of the 13 tests in `tests/test_cli.py` patch `core.cli.infer_audiences` and run
  `gata` with no audience option, so they assume the guessing default.

## Decisions

- **D1 — Where the default lives.** A module constant `_DEFAULT_AUDIENCE` in
  `core/cli.py`, next to the existing `_UK_AUDIENCE`: name `uk-tech-engineers`,
  audience "British software engineers and developers", language English, tone
  "dry British wit". *Why*: spec FR-006 (built-in, works from any folder). *Rejected*:
  reading it from `communities.yaml` (fails from other folders); a new
  `core/audiences.py` module (more structure than one constant and two helpers need).
- **D2 — Drift guard.** One test loads the repo's `communities.yaml` and asserts the
  `uk-tech-engineers` entry's three fields equal `_DEFAULT_AUDIENCE` (FR-006).
- **D3 — Resolving `--audience` names.** A helper `_resolve_audience_names(names)`
  that (a) strips and rejects empty values, (b) removes duplicates keeping first
  position, (c) loads `communities.yaml` from the current folder only if it exists,
  (d) maps each name to an `AudienceProfile` from the community's three fields, and
  (e) if the file is absent, accepts only the built-in default's own name. Names
  match **exactly** (case-sensitive), as community names do in `pipeline.py`.
  *Rejected*: case-insensitive matching (not how `pipeline.py` behaves; two ways to
  spell one audience would complicate dedupe).
- **D4 — Error messages and timing.** Validation runs right after logging is set up,
  before the API-key check and before any call, and exits with status 1 using
  `logger.error` like the API-key errors (constitution §13: no bare `print` in `core/`),
  so they show as `ERROR: ...`. Messages: unknown name → names
  the value and lists valid choices; file missing → says `communities.yaml` was not
  found in the current folder and that only `uk-tech-engineers` is available;
  `--infer-audiences` with `--audience` → "cannot be used together".
- **D5 — `--infer-audiences`.** A `store_true` flag that selects the existing code
  path unchanged: `_ensure_uk(infer_audiences(topic))`. `_UK_AUDIENCE`, `_ensure_uk`
  and `infer_audiences` stay (spec 010/015 behaviour preserved behind the flag).
- **D6 — `--research-only`.** Takes the first selected audience: with
  `--infer-audiences` that is `infer_audiences(topic)[0]` (today's behaviour);
  otherwise it is the first resolved audience (default or first `--audience`). If
  more than one `--audience` value was resolved, a `logger.warning` says the rest
  are ignored (WARNING is visible in the quiet default mode).
- **D7 — Progress and cost output.** Unchanged code: the `[i/N]` line and
  `_format_grand_total` already handle N=1 (the grand total is only printed to the
  screen when more than one audience ran; `summary.txt` is always written).
- **D8 — Version.** Behaviour change with a new flag: bump `1.30.0` → `1.31.0`
  (hand-edited in the PR, as in spec 054).

## What is deliberately not changed

`pipeline.py` and its `--community` mode; layout (stays automatic — the community's
`panels`/`layout` are not read); `communities.yaml` contents; model choices.

## Risks

- **Existing tests** that assume guessing must be updated (about 10 in
  `tests/test_cli.py`); they are mock-only, so the work is mechanical but wide.
- **Drift** between the built-in default and `communities.yaml` is guarded by D2
  only for the three fields; the file's other fields are irrelevant to `gata`.
- **Name collisions**: a community named like an inferred audience (for example
  `uk`) is unaffected, since the two selection modes never mix (D4).
