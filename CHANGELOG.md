# CHANGELOG


## v1.15.0 (2026-06-27)

### Documentation

* docs: fix gata CLI — topic is mandatory, Trend Scout only used by pipeline.py

gata always requires a positional topic argument; running it without one is an
error. Auto-topic mode (Trend Scout) is a pipeline.py-only feature. The
architecture entry-points diagram and README incorrectly implied gata could
run without a topic and would delegate to Trend Scout.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`ed066ed`](https://github.com/josemrsantos/gata/commit/ed066ed68c69eb9c9bb2213bc1db368b155057f5))

* docs: correct all input/output examples against real pipeline output

- Gata CLI: remove cartoon.png from audience subfolders (PNG is at topic level)
- Cultural Strategist: output format corrected to CULTURAL ANGLE:/REFERENCES:/JOKE TYPE:
- Image Generator: input is a single continuous scene string, not separate labelled sections
- Image Generator: output path corrected to gata CLI format
- Explainer HTML: remove accidental Portuguese phrase from English explanation
- Bundle Writer: diagram removes cartoon.png (written by Image Generator, not BW);
  input clarified as output_path pointer; summary uses Satirist/Co-Satirist agent name;
  Trend Scout absent from summary note added (bypassed in --topic mode)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`8ec065b`](https://github.com/josemrsantos/gata/commit/8ec065b66765bdc4a5dfe5845e5773b42bbc68b3))

* docs: add input/output examples to all agents and Gata CLI

Each section in docs/architecture.md now has a concrete Example block using
the same scenario (UK PM resignation) end-to-end so the data flow across
agents is coherent. Bundle Writer example corrected to show PNG at output_path
and bundle folder as its sibling directory.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`d134269`](https://github.com/josemrsantos/gata/commit/d1342692972f9549a5cb2688429c6d51f687cedb))

* docs: add Gata CLI entry-point section to architecture doc

Adds an 'Entry points' section between the HLD and Agents, with a decision
diagram showing the --topic (direct) vs auto-topic (Trend Scout) paths and
audience inference. Matches the GT node the user added to the HLD.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`876e091`](https://github.com/josemrsantos/gata/commit/876e091e1f775405d15251158db56577c954eee5))

* docs: Stage 030 — documentation overhaul (README + architecture)

README restructured: install-first, three required API keys with links
immediately after, then usage and reference. docs/architecture.md rewritten
with HLD agent graph, per-agent detailed diagrams, ParallelPanel and
DualPersonaLoop protocol explanations, and a guide for adding new protocols.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`063cd1f`](https://github.com/josemrsantos/gata/commit/063cd1f6cd0f500a127d6baf431c45ba7d2a5cba))

### Features

* feat: spec 032 — LLM provider configurability + cross-provider fallback

- New providers.yaml config declares panelist/aggregator LLM chains per role
- Each panelist slot is an ordered fallback list; if the primary provider fails,
  the next provider in the slot is tried automatically (cross-provider fallback)
- Auto-discovery: ./providers.yaml loaded first, then ~/.gata/providers.yaml,
  then hardcoded defaults — no flag needed for the common case
- --providers PATH flag for explicit override
- Agent signatures updated: panelist_providers is now list[list[LLMProvider]]
- New ModelSpec / ProvidersConfig dataclasses in core/types.py
- load_providers_config() added to core/config_loader.py
- _build_provider() factory added to core/runner.py
- bundle_writer.write_bundle() forwards provider config to agent_explainer
- 19 new tests in tests/test_providers_config.py
- Version bumped to 1.15.0

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`855dce9`](https://github.com/josemrsantos/gata/commit/855dce9d0dd18dd121a91d5ccf36abc4507f01fe))


## v1.14.0 (2026-06-22)

### Features

* feat: Stage 029 — Grok-3 as primary decider across all ParallelPanel agents

Cultural Strategist and Explainer converted from DualPersonaLoop to
ParallelPanel. Grok-3 is now the aggregator/decider in all three panel
agents (Satirist, Cultural Strategist, Explainer); Grok-3-mini participates
as panelist alongside Claude and Gemini, keeping judge and proposer distinct.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`d7d7bb7`](https://github.com/josemrsantos/gata/commit/d7d7bb783c58447f4e8d1d73a7e3fee19a30ddcf))


## v1.13.0 (2026-06-22)

### Documentation

* docs: update README for Stage 027 — cartoon title banner + --no-title flag

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`a133c29`](https://github.com/josemrsantos/gata/commit/a133c29b735e8fb2b3a90418e0d488399a6b7b31))

### Features

* feat: Stage 027 — Satirist-authored title overlaid as dark banner on generated images

Adds a punchy 3-8 word title to every cartoon: the Satirist includes a
"title" field in its JSON output; agent_image_generator overlays it as a
dark banner at the top of the saved image using Pillow. Falls back to the
raw topic string if the Satirist omits the title. --no-title flag in both
pipeline.py and core/cli.py suppresses the banner. 351 tests passing.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`b570b38`](https://github.com/josemrsantos/gata/commit/b570b38bd8e5ecc334e96acbde779d32a63fd3dc))


## v1.12.0 (2026-06-21)

### Features

* feat: Stage 026 — LLM Communication Protocol Framework + Parallel Panel

feat: Stage 026 — LLM Communication Protocol Framework + Parallel Panel ([`26e3ca1`](https://github.com/josemrsantos/gata/commit/26e3ca16fbe7f48a6743460a466f8c96ef3a68ab))

* feat: Stage 026 — LLM Communication Protocol Framework + Parallel Panel

Introduces ConversationProtocol ABC as the shared interface for all
conversation topologies. DualPersonaLoop now inherits it (no behaviour
change). New ParallelPanel topology runs Claude, Grok, and Gemini as
independent satirists; an Aggregator (Claude) picks the strongest concept.
Replaces the DualPersonaLoop in agent_satirist.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`1febdf8`](https://github.com/josemrsantos/gata/commit/1febdf89dc3bfa68c70f3259cb0278159d2683d6))


## v1.11.0 (2026-06-21)

### Documentation

* docs: add spec 024 — LLM provider abstraction + project restructure

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`cc91f39`](https://github.com/josemrsantos/gata/commit/cc91f391d9e093b5bee734bdaa2dd8ec7b0bdfaf))

* docs: remove "ad-hoc" from RULE 5

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`6ab736a`](https://github.com/josemrsantos/gata/commit/6ab736a32cf411976e4cb2b9503e139049d7cfa8))

* docs: remove implemented items from TODO.md

Remove 5 completed stages (multi-audience CLI, post-generation image
review, Gemini co-satirist, image evaluator, fidelity check). Also
update the fact-check gate description to reflect the current
Satirist/Co-Satirist architecture (no longer references B/C or Claude).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`2eda305`](https://github.com/josemrsantos/gata/commit/2eda3050949353d8112609dd2757685d45ed6678))

* docs: backfill specs for stages 019–023

Add spec.md files for all stages completed since spec 016:
- 019: inference model fallback + agent rename
- 020: auto-layout (Satirist chooses panel count/direction)
- 021: Gemini-only Satirist/Co-Satirist loop
- 022: Image Evaluator agent
- 023: Image Evaluator concept fidelity check

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`32023ed`](https://github.com/josemrsantos/gata/commit/32023ed5c0a888f48b709db31921370bbf5a423d))

### Features

* feat: Stage 025 — Grok integration as Co-Satirist primary

Adds GrokProvider (llm/grok.py) using the xAI OpenAI-compatible API.
Grok-3 becomes the Co-Satirist primary; Gemini Flash / 2.0-Flash are
fallbacks. Cost table covers grok-3, grok-3-mini, grok-3-fast,
grok-3-mini-fast. 10 new unit tests added (test_grok_provider.py).

Also fixes two bugs surfaced by live testing:
- GeminiProvider.generate() now raises RuntimeError on empty response.text
  (Gemini 2.5-pro returns None for thinking-only turns) so the fallback
  chain can try the next provider instead of passing "" downstream.
- GrokProvider.generate() applies the same guard for empty message.content.

README updated: Co-Satirist LLM, XAI_API_KEY added to env-vars table.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`531278e`](https://github.com/josemrsantos/gata/commit/531278ec62069aef41a8782d773c1640c13a17b3))

### Refactoring

* refactor: Stage 024 — LLM provider abstraction + project restructure

Introduces llm/ package (LLMProvider ABC, ClaudeProvider, GeminiProvider,
DualPersonaLoop) and core/ package (types, config_loader, runner, bundle_writer,
humor_utils, cli, __version__). agents/ now contains only Gata agents.

Post-review fixes applied:
- DualPersonaLoop final-say suffix uses .replace() not .format() to prevent
  KeyError when reviewer LLM output contains curly braces
- GeminiProvider.generate() now forwards max_output_tokens to GenerateContentConfig
  so PersonaConfig.max_tokens=8192 (Explainer Writer) is honoured
- ClaudeProvider.generate() guards against empty content list (IndexError)
- GeminiProvider.generate() uses self.compute_cost() instead of inline formula
- Expose get_gemini_client() publicly; infer_audiences/infer_mood/trend_scout
  call it directly instead of creating throwaway GeminiProvider wrappers
- _GEMINI_EVAL_CHAIN aliased to _GEMINI_PRO_CHAIN (identical model lists)
- README agent table updated: Satirist now uses Claude (was Gemini)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`4cfbe0e`](https://github.com/josemrsantos/gata/commit/4cfbe0e535c46749c5d036f03c112c7ff343db6f))

* refactor: simplify _resolve_layout using explicit argparse defaults

Set --panels default to 1 and --layout default to 'horizontal' so args
always carry real values; remove the now-dead community config fallback
and the None-sentinel checks from _resolve_layout.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`39d9b19`](https://github.com/josemrsantos/gata/commit/39d9b19c0be6f6fdc3e57cddae47b28511c64ee9))

### Unknown

* 2.1.1

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`eb8fc9f`](https://github.com/josemrsantos/gata/commit/eb8fc9f8f6c7e687063a32f1d024efcb2d1c680c))

* docs+test: Stage 025 code review — fix stale README and add missing guard test

- Fix 8 stale "Critic" references in README (Tech Stack, narrative, stage table,
  bundle docs, .env/.export/Actions setup examples)
- Add XAI_API_KEY to all three setup examples (.env, Option B export, GitHub Actions)
- Add test_generate_raises_runtime_error_on_none_content covering the if-not-text
  guard (non-empty choices, None message.content path)
- Fix RULE 14: replace bare blank line inside test function body with inline comment

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`988c3ef`](https://github.com/josemrsantos/gata/commit/988c3ef13303c9a25bab350f1d50bc91e17e12d2))

* 2.1.0

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`70fe61b`](https://github.com/josemrsantos/gata/commit/70fe61b9984828877c21bb809b738e930a008c61))

* 2.0.0

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`e583624`](https://github.com/josemrsantos/gata/commit/e5836245f7970d014fc2ab473bd4f6b341a2d5f7))

* 1.10.1

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> ([`92643dc`](https://github.com/josemrsantos/gata/commit/92643dc63d6e569d55c46a18476c049f7327c06a))


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
