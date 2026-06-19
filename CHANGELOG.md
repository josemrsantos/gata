# CHANGELOG


## v1.10.0 (2026-06-19)

### Features

* feat: Stage 023 — concept fidelity check in Image Evaluator

Extend the evaluator prompt with an explicit fidelity check that
distinguishes between thematically plausible and actually correct
images. The model is now instructed that thematic similarity is not
sufficient, given a concrete counter-example (British weather cycle
instead of the approved chicken-joke spider diagram), and told to
prefix wrong-concept rejections as "Fidelity failure: intended [X],
image shows [Y]" so failures are diagnosable in logs.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`646e926`](https://github.com/josemrsantos/gata/commit/646e92690dc6e604272be8550f63779c8a0c3c9d))


## v1.9.0 (2026-06-19)

### Features

* feat: Stage 022 — Image Evaluator agent

After image generation, a Gemini vision model checks for LLM rendering
artifacts (duplicate text, garbled text, character failures) and rates
whether the cartoon is genuinely funny for the target audience. Rejects
trigger regeneration up to 2 times before accepting the last image.
Fails open on parse error or model exhaustion so the pipeline is never
blocked.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`8a58038`](https://github.com/josemrsantos/gata/commit/8a58038c84a2983e7ab76988b862b12d7bf76092))


## v1.8.0 (2026-06-18)

### Features

* feat: Stage 021 — Gemini-only Satirist/Co-Satirist loop

Replace Claude with Gemini in the Satirist role. Both agents are now
Gemini-based co-collaborators chasing the funniest possible concept
rather than creator vs. gatekeeper. The Co-Satirist can propose an
improved JSON concept in NEEDS REVISION; APPROVED terminates the loop.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`b3936f4`](https://github.com/josemrsantos/gata/commit/b3936f4b9c40aa71f8db5007c6b8be72e3da22cb))


## v1.7.0 (2026-06-18)

### Features

* feat: auto-layout — Satirist/Critic decides panel count and direction

The Satirist now always outputs structured JSON that includes panels (1–4)
and layout (horizontal/vertical) alongside the cartoon concept. When no
explicit --panels override is given, the agent chooses the format that best
fits the narrative: 1-panel for punch-at-a-glance, 2 for setup/punchline,
3 for escalation, etc. Callers can still force a specific layout by passing
layout_override.

  - agent_satirist: unified JSON output format, auto-layout prompt, new
    _parse_verdict(), run() returns 4-tuple including CartoonLayout
  - runner: unpacks chosen_layout from Satirist and passes it to image gen
  - pipeline: _resolve_layout() returns None (auto) when no --panels flag
    and community panels ≤ 1 (the default); _panel_filename_prefix handles None

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`cdddb26`](https://github.com/josemrsantos/gata/commit/cdddb267f3f5d0fc59716108232693b76f9bf360))


## v1.6.2 (2026-06-18)

### Bug Fixes

* fix: rename Agent 0 → Cultural Strategist, B/C → Satirist/Critic (RULE 9)

Single-char and numeric agent names violate RULE 9. All occurrences of
"Agent 0" and "B/C" replaced with their human-readable names across
source files, test fixtures, and log assertions.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`97ed51a`](https://github.com/josemrsantos/gata/commit/97ed51a5baccc58bcabf4393d3b8cb03ad24d21c))

* fix: add model fallback chain to infer_audiences and infer_mood

Both functions previously used a single gemini-2.5-flash call and gave up
immediately on any failure (including transient 503 overloads). They now
try gemini-2.5-flash → gemini-2.5-pro → gemini-2.0-flash in order, logging
each per-model failure at DEBUG and only surfacing a WARNING when all
models are exhausted — matching the retry pattern used by every other agent.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`2b56b3d`](https://github.com/josemrsantos/gata/commit/2b56b3dbb30f884d5edf625d4614c8b1217cf1b8))


## v1.6.1 (2026-06-18)

### Bug Fixes

* fix: replace logger.info with print() in CLI output for human-friendly display

Timestamps and [module] prefixes made gata output read like server logs.
Fix: basicConfig raised to WARNING (silences all agent INFO); user-visible
lines converted to print() so there are no prefixes or timestamps.

- cli.py: basicConfig to WARNING; all logger.info → print(); remove redundant
  audiences summary line; grand total only shown for 2+ audiences
- runner.py: agent start messages and run summary → print()
- agent_image_generator: "rendering" and "saved" demoted to DEBUG (info is
  already in the run summary printed by runner.py)
- test: update log-level assertion to DEBUG to match new image generator level

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`4649f4f`](https://github.com/josemrsantos/gata/commit/4649f4f275ee33ff3a470d10542ac70cc83780e6))


## v1.6.0 (2026-06-18)

### Documentation

* docs: update README with stages 12-15, richer gata examples, and synced TODO list

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`7a8932c`](https://github.com/josemrsantos/gata/commit/7a8932c307ca319c9a65dc10c8493b76f36b5584))

### Features

* feat: clean logging output — silence SDK noise, add agent start/done INFO

Operators can now see per-agent start, completion, cost, and grand total
without HTTP-level SDK chatter obscuring the output.

- Silence httpx, httpcore, google.genai, google_genai, anthropic to WARNING
  in both cli.py and pipeline.py entry points
- dual_loop: per-iteration verdict demoted to DEBUG; add start + completion
  INFO (e.g. "Agent 0: complete — approved after 2 iteration(s)")
- agent_image_generator: full prompt and per-model logs demoted to DEBUG;
  add concise "rendering (N chars)" start and "saved — model=X cost=$Y" done
- runner: add "Cultural Strategist: analyzing topic..." and
  "Satirist/Critic: creating concept..." start logs; remove now-redundant
  "creative loop complete" and "done: cartoon saved" lines
- cli: cleaner [1/2] audience header; grand total now shown as === run summary ===
- Update FR-010 test to match new completion-at-INFO contract

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`8b1c511`](https://github.com/josemrsantos/gata/commit/8b1c51153d3d26c86946979e33571c8e08a3cf26))


## v1.5.0 (2026-06-16)

### Features

* feat: reduce default audience inference to single main audience + UK

Previously generated 2–4 images per topic run; now generates one image
for the most relevant inferred audience plus one for the UK public.
Cuts API cost and run time roughly in half for the typical single-post use case.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`40dbbbe`](https://github.com/josemrsantos/gata/commit/40dbbbede53662a818cdc4b47cca0c20bfd2f2b8))


## v1.4.0 (2026-06-16)


## v1.5.1 (2026-06-16)

### Bug Fixes

* fix: record real image token counts and non-zero cost in telemetry (v1.5.1)

Image generation cost was always $0.00 because output_tokens was hardcoded to 0
and all image models had (0.0, 0.0) rates. Now reads candidates_token_count from
usage_metadata (same guard as dual_loop.py) and prices the five image models
against verified Gemini API rates.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`cef49c4`](https://github.com/josemrsantos/gata/commit/cef49c46112882c827b24d485ce881251465fada))

### Features

* feat: make HTML explanation output opt-in via --html (v1.5.0)

explanation.html and deep_dive_en.html cost an extra Claude + Gemini
round trip on every run regardless of whether anyone reads them. Add
a --html flag (default off) to gata and pipeline.py; bundle_writer
only calls agent_explainer when explicitly requested. ([`5d29f35`](https://github.com/josemrsantos/gata/commit/5d29f352d50102fc84793e5dddbdc48484ab06ae))

* feat: add human-readable run summary — per-agent time/iterations/cost rollup (v1.4.0)

telemetry.json already captured this data but was machine-readable only.
write_bundle() now also writes summary.txt, and the multi-audience gata
CLI writes a grand-total summary.txt across all audiences — the numbers
needed for an announcement post without parsing JSON by hand. ([`1ef7d8d`](https://github.com/josemrsantos/gata/commit/1ef7d8dffcc24c1d1dc1496bee98bfe4348d5ffe))


## v1.3.0 (2026-06-14)

### Documentation

* docs: recommend pipx for CLI install; keep pip for library/venv use

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`8e80995`](https://github.com/josemrsantos/gata/commit/8e80995d632bc967139843012f8cfe4d15e99ba7))

### Features

* feat: add mood layer — Gemini web-grounded cultural temperature for Framer (v1.3.0)

- agents/types.py: add MoodBrief dataclass
- agents/agent_cultural_strategist.py: add infer_mood() using Gemini with
  Google Search grounding; inject MoodBrief into Framer initial input in run()
- pyproject.toml + agents/__version__.py: bump to 1.3.0
- specs/011-mood-layer/spec.md: feature specification

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`e1e21b0`](https://github.com/josemrsantos/gata/commit/e1e21b02008d64dd2d2a0d276087d85fa4cbea84))


## v1.2.0 (2026-06-14)

### Features

* feat: infer audiences dynamically from topic via Gemini (v1.2.0)

- agents/types.py: add AudienceProfile dataclass
- agents/agent_cultural_strategist.py: add infer_audiences(topic) — single
  Gemini call to identify relevant audiences, languages, and comedy norms;
  falls back to swiss/qatar/global on parse failure
- agents/cli.py: replace hardcoded _AUDIENCES with infer_audiences() call;
  _ensure_uk() guarantees UK audience is always in the final list
- pyproject.toml + agents/__version__.py: bump to 1.2.0
- specs/010-dynamic-audiences/spec.md: feature specification

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`f96a316`](https://github.com/josemrsantos/gata/commit/f96a31634eca9872deea1bba27c603de9f724109))


## v1.1.0 (2026-06-14)

### Features

* feat: add run telemetry — per-agent timing, token counts, cost estimate (v1.1.0)

- agents/types.py: add TokenUsage, AgentTelemetry, RunTelemetry, compute_cost()
  and pricing table; extend LoopOutput with telemetry field
- agents/dual_loop.py: _call_model/_call_persona return (text, TokenUsage);
  DualPersonaLoop.run() accumulates calls and attaches AgentTelemetry to LoopOutput
- agents/agent_cultural_strategist.py: run() returns AgentTelemetry as third element
- agents/agent_satirist.py: run() returns AgentTelemetry as third element
- agents/agent_image_generator.py: track timing; generate() returns (path, AgentTelemetry)
- agents/runner.py: collect RunTelemetry from all agents, pass to bundle_writer
- agents/bundle_writer.py: accept RunTelemetry, write telemetry.json to bundle
- pyproject.toml + agents/__version__.py: bump to 1.1.0

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`0b2090e`](https://github.com/josemrsantos/gata/commit/0b2090ef60205762b7d050c0abd21a9c88b6c9e9))


## v1.0.0 (2026-06-14)

### Bug Fixes

* fix: bump version to 0.1.1 to avoid PyPI filename reuse error

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`1c472e8`](https://github.com/josemrsantos/gata/commit/1c472e8eb52ecf760023965d4a3c9af2d24b7b67))

* fix: add build-system config and agents/__init__.py to fix PyPI build

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`a94cac1`](https://github.com/josemrsantos/gata/commit/a94cac13b0dc54e93d9a74d7d52e6961947acced))

* fix: add missing PEP 621 fields (license, authors, readme) for PyPI publishing

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`1bed314`](https://github.com/josemrsantos/gata/commit/1bed314978f693d1321edfa6c6d4941ad1978430))

### Documentation

* docs: add PyPI badge and pip install instructions to README

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`c932d16`](https://github.com/josemrsantos/gata/commit/c932d168d1b44ca79b804c79ae48dc95d31a37a2))

### Features

* feat: add gata CLI entry point — generates 3 audience-adapted cartoons from a topic

- agents/runner.py: extract run_pipeline() from pipeline._run_pipeline
- agents/cli.py: new gata console-script (Swiss German, Arabic, English audiences)
- pipeline.py: import run_pipeline from agents.runner; remove duplicate definition
- pyproject.toml: add [project.scripts] gata entry point, bump version to 1.0.0
- agents/__version__.py: bump to 1.0.0
- README.md: document gata command and quick-start section
- TODO.md: add multi-audience CLI item
- specs/008-multi-audience-cli/spec.md: full feature specification

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`54a67fe`](https://github.com/josemrsantos/gata/commit/54a67fe49fbe077a1133ac184c254bba4ad10701))

### Unknown

* Initial commit - Rename repo to just gata ([`54ea7be`](https://github.com/josemrsantos/gata/commit/54ea7bea785f6c7bb4bdf82309d4fb1800792d31))
