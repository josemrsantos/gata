# CHANGELOG


## v1.4.0 (2026-06-16)

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
