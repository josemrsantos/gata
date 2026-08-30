# Gata Newsroom

[![PyPI version](https://img.shields.io/pypi/v/gata)](https://pypi.org/project/gata/)

An automated multi-agent pipeline that transforms daily topics into a recurring satirical cartoon series starring **Gata**, a serious investigative calico cat who views all geopolitics through the lens of feline priorities.

## Install

```bash
pipx install gata
```

If `pipx` is not installed: `sudo apt install pipx && pipx ensurepath`

## Required API keys

Three LLM provider accounts are required before you can run Gata:

| Provider | Sign up | Environment variable |
|---|---|---|
| **Anthropic** | [console.anthropic.com](https://console.anthropic.com) | `ANTHROPIC_API_KEY` |
| **Google AI Studio** | [aistudio.google.com](https://aistudio.google.com) | `GEMINI_API_KEY` |
| **xAI** | [console.x.ai](https://console.x.ai) | `XAI_API_KEY` |

> **Auto-topic mode** (`pipeline.py` without `--topic`) also requires a
> [NewsAPI.org](https://newsapi.org) key in `NEWSAPI_ORG_KEY`.
> The `gata` command always requires a topic — Trend Scout is never used by it.

Export the keys in your shell, or place them in a `.env` file in the project root (it is
gitignored and never committed):

```bash
# Option A — shell environment
export ANTHROPIC_API_KEY=...
export GEMINI_API_KEY=...
export XAI_API_KEY=...
export NEWSAPI_ORG_KEY=...   # only needed for auto-topic mode

# Option B — .env file (loaded automatically on startup)
ANTHROPIC_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
XAI_API_KEY=your_key_here
NEWSAPI_ORG_KEY=your_key_here
```

## Quick start

```bash
gata "World Cup final: Argentina vs France"
```

This infers the most culturally relevant audience, negotiates a cultural angle, generates
three independent cartoon concepts, picks the strongest one, and saves two PNGs to your
working directory — one for the inferred audience and one for the UK public.

## How it works

1. **Trend Scout** fetches today's top headlines for the community and ranks them by
   satirical potential; only used by `pipeline.py` when `--topic` is not supplied —
   the `gata` command always requires a topic and never invokes Trend Scout
2. **Cultural Strategist** — three Framers (Claude, Grok-build, Gemini) independently
   propose a cultural angle; Grok-4.3 (Resonator) aggregates and picks the sharpest one
3. **Satirist** — three Panelists (Claude, Grok-build, Gemini) independently generate a
   cartoon concept; Grok-4.3 (Aggregator) picks the strongest concept
4. **Image Generator** renders the approved concept into a PNG via a fallback chain of
   Gemini image models; overlays the Satirist-authored title as a dark banner at the top
   (suppressed with `--no-title`). When `--linkedin-post` is set and the layout is
   single-panel or horizontal, the saved file is corrected to exactly LinkedIn's
   1200x644 Article-cover size — cropped/resized before the title banner, then
   re-fitted afterward so the banner never pushes it off-size; a vertical multi-panel
   cartoon is left untouched
5. **Explainer** (opt-in via `--html`) — three Writers (Claude, Grok-build, Gemini)
   independently draft an HTML explanation page; Grok-4.3 (Editor) picks the best one;
   runs twice — once in the target language, once in English
6. **Bundle Writer** saves the full output package: image, conversation logs, prompt
   card, telemetry, and summary

## Agents

| Agent | Sub-agents | LLMs | What it does |
|---|---|---|---|
| **Trend Scout** | — | Gemini | Fetches today's headlines from NewsAPI.org and picks the top 3 ranked by satirical potential for the community |
| **Cultural Strategist** | Framer ×3, Resonator | Claude · Grok-build (grok-build-0.1) · Gemini (Framers) · Grok-4.3 (Resonator/aggregator) | Three Framers independently propose a cultural angle and audience references; Resonator picks the sharpest one |
| **Satirist** | Panelist ×3, Aggregator | Claude · Grok-build (grok-build-0.1) · Gemini (panelists) · Grok-4.3 (aggregator) | Three panelists independently generate a cartoon concept; Aggregator picks the strongest |
| **Image Generator** | — | Gemini image models | Renders the approved image prompt into a PNG; tries up to 5 models in order before failing; with `--linkedin-post` and a single-panel/horizontal layout, corrects the saved file to LinkedIn's exact 1200x644 cover size |
| **Image Evaluator** | — | Gemini vision models | Checks for LLM rendering artifacts and rates comedy; triggers regeneration up to 2 times on rejection |
| **Explainer** | Writer ×3, Editor | Claude · Grok-build (grok-build-0.1) · Gemini (writers) · Grok-4.3 (editor/aggregator) | Three Writers independently draft HTML explanation pages (in-language + English); Editor picks the best per run |
| **LinkedIn Post** | Research (Gemini/Claude/Grok, independent) → Domain Classifier ×3 + Source Classifier → Angle Planner ×3 + Managing Editor → Writer ×3 + Managing Editor | Same panelist/aggregator chains as Satirist | Each panelist researches the topic with its own real web search; every newly-seen source domain is then classified for paywall/reliability by a dedicated panel (cached in a local `source_domains.duckdb`, so a domain is only ever judged once), and any paywalled or low-reliability domain is stripped before angle-planning or writing ever sees it. Three panelists independently propose article angles (an optional `--angle` steers this), then three panelists draft a serious, non-satirical article — its own labelled Executive Summary leading the piece, citing sources inline as numbered footnotes (`[1]`, `[2]`, ...) against a shared candidate list, up to 15 total. A code-built, numbered Sources list (every source URL always code-verified — never LLM-authored — with a genuinely descriptive title resolved from fetched page data, its own URL, or, as a last resort, that source's own provider; anything with nothing descriptive is dropped, never published bare) matches those footnotes exactly. Everything through here runs identically regardless of `--research-only`; only final assembly differs: `--linkedin-post` produces the Gata-branded `linkedin_post.md` (disclosure + pipeline metrics inside "Behind the Scenes"), while `--research-only` alone produces a neutral `research_report.md` with no Gata branding, closing block, or tech-stack promo |
| **Engagement Image Concept** | Panelist ×N, Art Director | Same provider chains as Satirist panelists/aggregator (or `providers.yaml`) | Deliberates one image-generation prompt that visually unifies an entire newsletter edition from its stories' text only (never their rendered images); rendered via the shared `ImageGeneration` class and pinned to LinkedIn's exact 1200x644 Article/Newsletter cover size. Runs before the Newsletter Editor call, on by default, skippable with `--no-image` |
| **Newsletter Editor** | — | Gemini text models (primary) · Grok · Claude (fallback only, cheapest-first) | Merges several stories' `linkedin_post.md` files into one newsletter-edition draft plus a network-facing notification teaser (`edition_notification.txt`), invoked via the standalone `newsletter_merge.py` script — not part of the `gata`/`pipeline.py` flow |

## `gata` command

The simplest way to run the pipeline. Give it any topic and it generates two satirical
cartoons: one for the most culturally relevant audience (inferred automatically) and one
for the UK public.

```bash
# Generate cartoons for a news topic
gata "Interest rates stay high despite falling inflation"

# Any topic works — Gata will find the angle
gata "World Cup final: Argentina vs France"
gata "Tech layoffs hit Silicon Valley again"
gata "Portugal wins Eurovision"

# Skip the Cultural Strategist — feed the topic straight to the Satirist
gata "AI is replacing junior developers" --direct

# Also generate HTML explanation pages
gata "NATO summit in Brussels" --html

# Generate a researched (non-satirical) companion article alongside the cartoon
gata "Vibe coding in production" --linkedin-post
gata "Vibe coding in production" --linkedin-post --angle "where it should not be used" --angle "where it's fine as long as..."

# Research-only mode: skip the entire satirical pipeline (no cartoon, no image
# cost) and produce only a researched report — runs once, not once per audience
gata "AI regulation in the EU" --research-only
gata "AI regulation in the EU" --research-only --linkedin-post
```

Output folder: `{cwd}/{topic_slug}/` — one PNG per audience, plus a bundle folder per
image. Run `gata --help` to see all options.

## `pipeline.py` — advanced usage

```bash
# Named community (exact match in communities.yaml; topic selected by Trend Scout)
python pipeline.py --community uk-politics

# Free-text community (no entry required in communities.yaml)
python pipeline.py --community "US community that dislikes Trump"
python pipeline.py --community "Communauté française qui critique Macron"

# Community + topic mode (topic supplied directly — no Trend Scout)
python pipeline.py --community uk-politics --topic "Number 10 is becoming available for rent, again."
python pipeline.py --community "Adeptos portugueses de futebol" --topic "O Ronaldo vai levar Portugal ao mundial"

# Random community and topic
python pipeline.py

# Manual mode (bypasses communities.yaml entirely)
python pipeline.py --topic "AI hype" --audience "developers" --language "English" --tone "dry wit"

# Multi-panel cartoon
python pipeline.py --community uk-politics --panels 3 --layout horizontal
python pipeline.py --community portuguese-adults --panels 2 --layout vertical

# HTML explanation pages + suppress title banner
python pipeline.py --community uk-politics --html --no-title

# Skip the Cultural Strategist (direct mode)
python pipeline.py --topic "AI hype" --audience "developers" --language "English" --direct

# Custom LLM provider chains via providers.yaml
python pipeline.py --community uk-politics --providers providers.yaml

# Researched (non-satirical) companion article, with operator-supplied angles
python pipeline.py --topic "Vibe coding in production" --audience "engineering leaders" --language English --tone neutral --direct --linkedin-post --angle "where it should not be used" --angle "where it's fine as long as..."

# Research-only mode: skip the entire satirical pipeline (no cartoon, no image
# cost) — produces research_report.md by default, or the branded
# linkedin_post.md when combined with --linkedin-post
python pipeline.py --topic "AI regulation in the EU" --audience "policy analysts" --language English --tone neutral --research-only
python pipeline.py --community uk-politics --research-only --linkedin-post
```

### Multi-panel flags

| Flag | Values | Default | Description |
|---|---|---|---|
| `--panels` | 1–4 | 1 | Number of panels in the cartoon strip |
| `--layout` | `horizontal`, `vertical` | `horizontal` | Panel arrangement direction |
| `--no-title` | — | off | Suppress the title banner overlaid at the top of the image |
| `--direct` | — | off | Skip the Cultural Strategist; feed topic straight to the Satirist |
| `--providers` | path | built-in defaults | Path to `providers.yaml` — overrides built-in LLM assignments |
| `--linkedin-post` | — | off | Generate a researched LinkedIn article (`linkedin_post.md`) and notification snippet (`linkedin_notification.txt`) in the output bundle |
| `--angle` | text, repeatable | none | An angle the `--linkedin-post` article should explore (e.g. `--angle "X" --angle "Y"`); has no effect without `--linkedin-post` |
| `--research-only` | — | off | Skip the entire satirical pipeline (Cultural Strategist, Satirist, Image Generator, Image Evaluator) and produce only a researched report — neutral `research_report.md` by default, or the branded `linkedin_post.md` when combined with `--linkedin-post`. On the `gata` CLI, runs once using the first inferred audience instead of looping per audience |

### Output bundle

Each run writes a bundle folder containing:

| File | Description |
|---|---|
| `cartoon.png` | The generated image |
| `agent0_log.txt` | Cultural Strategist negotiation history |
| `bc_log.txt` | Satirist panel exchange log |
| `prompt_card.txt` | Verbatim image prompt for standalone reuse |
| `telemetry.json` | Per-agent timing, token counts, and cost (machine-readable) |
| `summary.txt` | Per-agent time, iterations, and cost (human-readable) |
| `explanation.html` | In-language explanation of the joke (`--html` only) |
| `deep_dive_en.html` | English operator deep-dive (`--html` only) |
| `linkedin_post.md` | Researched, non-satirical companion article — independently researched by Claude/Gemini/Grok (paywalled/low-reliability domains filtered before drafting), opening with a labelled Executive Summary and organised by agreed angles, citing sources inline as numbered footnotes against a code-built, matching Sources list (up to 15); the AI-authorship disclosure and pipeline metrics sit at the bottom, inside "Behind the Scenes" (`--linkedin-post` only) |
| `linkedin_notification.txt` | Serious push-notification teaser for LinkedIn followers (`--linkedin-post` only) |
| `research_report.md` | Neutral, unbranded researched report — same research/angle-planning/writing engine as `linkedin_post.md`, but no Gata branding, no closing/subscribe block, no "Behind the Scenes" tech-stack promo (`--research-only` without `--linkedin-post` only) |

In `--research-only` mode, `cartoon.png`, `agent0_log.txt`, `bc_log.txt`, and `prompt_card.txt` are never created — no cartoon is generated — and the bundle lives under `output/research/{topic_slug}_{timestamp}/` instead of an image-derived path.

## Communities

Communities are defined in `communities.yaml`. Each community specifies a target
audience, output language, tone, seed topics, and optionally a default panel count.

| Community | Language | Tone |
|---|---|---|
| `uk-politics` | English | Dry British wit |
| `uk-tech-engineers` | English | Dry British wit |
| `portuguese-adults` | Portuguese | Sátira política afiada |
| `portuguese-politics` | Portuguese | Sátira política afiada |
| `us-startup-crowd` | English | Sarcastic Silicon Valley cynicism |

To add a new community, add an entry to `communities.yaml` — no code changes required.

## LLM provider configuration (`providers.yaml`)

`providers.yaml` controls which LLM models handle each agent role and in what fallback order. It is optional — if absent, Gata uses its built-in defaults (Claude Sonnet, Grok grok-build-0.1, and Gemini Flash as panelists; Grok grok-4.3 as aggregator).

Each panelist slot is an ordered fallback chain. If the primary model fails, the next model in the slot is tried — including across provider boundaries (cross-provider fallback). The aggregator entry works the same way.

```yaml
panelists:
  - - provider: claude
      model: claude-sonnet-4-6
      timeout: 25.0        # optional: per-call limit in seconds
    - provider: gemini
      model: gemini-2.5-flash
      timeout: 15.0
  - - provider: grok
      model: grok-build-0.1
    - provider: gemini
      model: gemini-2.5-flash

aggregator:
  - provider: grok
    model: grok-4.3
  - provider: claude
    model: claude-sonnet-4-6
```

The optional `timeout` field (Spec 036) gives each provider its own per-call budget. If a provider stalls beyond that limit it is abandoned and the next provider in the chain starts with a fresh budget. Omit `timeout` (the default) to keep unbounded calls.

Load a custom file with `--providers providers.yaml` or place it in `./providers.yaml` (auto-discovered).

## Comedy configuration (`humor.yaml`)

`humor.yaml` controls comedy style and agent personality. All fields default to off.

| Section | Field | Type | What it does |
|---|---|---|---|
| `framer` | `wordplay_scan` | bool | Framer actively looks for pun/wordplay opportunities |
| `framer` | `joke_types` | list | Menu of joke types the Framer chooses from |
| `framer` | `language_register` | string | Register for wordplay (`vernacular`, `formal`, …) |
| `framer` | `inconvenience` | 0–100 | How aggressively Framer surfaces uncomfortable truths |
| `satirist` | `preferred_style` | string | Tone commitment (`deadpan`, `absurdist`, …) |
| `satirist` | `avoid` | list | Joke types/styles to avoid |
| `satirist` | `subversion` | string | Subversion intensity (`high`, `medium`, `low`) |
| `satirist` | `joke_explanation` | bool | Add a `<joke_explanation>` block after each concept |
| `satirist` | `inconvenience` | 0–100 | How aggressively Satirist forces uncomfortable truths |

**Inconvenience levels:** 0 = off; 1–33 = mild nudge; 34–66 = medium push; 67–100 = maximum.

## Install from source (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for agent diagrams and the
communication protocol framework.

## Status

| Stage | Name | Status |
|-------|------|--------|
| 1 | Core pipeline — Satirist/Co-Satirist creative loop + image generation | ✅ |
| 2 | Community config + model fallback chains | ✅ |
| 3 | Cultural Strategist (Framer + Resonator) | ✅ |
| 4 | Text Output Bundle (logs, HTML explanations, prompt card) | ✅ |
| 5 | Trend Scout — automated topic discovery via NewsAPI.org + Gemini | ✅ |
| 6 | Free-text community mode | ✅ |
| 7 | Multi-panel cartoon format — --panels and --layout | ✅ |
| 8 | Multi-audience CLI | ✅ |
| 9 | Run telemetry — per-agent timing, token counts, cost | ✅ |
| 10 | Dynamic audiences | ✅ |
| 11 | Mood layer | ✅ |
| 12 | Run summary | ✅ |
| 13 | Optional HTML output | ✅ |
| 14 | Image cost pricing | ✅ |
| 15 | Single main audience | ✅ |
| 16 | Clean logging | ✅ |
| 19 | Inference model fallback | ✅ |
| 20 | Auto layout | ✅ |
| 21 | Gemini Satirist | ✅ |
| 22 | Image Evaluator | ✅ |
| 23 | Evaluator fidelity | ✅ |
| 24 | LLM provider abstraction | ✅ |
| 25 | Grok integration | ✅ |
| 26 | Protocol framework + Parallel Panel | ✅ |
| 27 | Cartoon title banner + --no-title flag | ✅ |
| 29 | Grok as primary decider — Grok-3 aggregator across all ParallelPanel agents | ✅ |
| 30 | Documentation overhaul — README + architecture doc | ✅ |
| 32 | LLM provider configurability + cross-provider fallback via `providers.yaml` | ✅ |
| 33 | Enhanced cost reporting — per-model breakdown in telemetry summary | ✅ |
| 34 | FairParallelPanel — multi-round parallel protocol with peer sharing | ✅ |
| 35 | Direct Satirist mode — `--direct` flag bypasses Cultural Strategist | ✅ |
| 36 | Per-provider call timeout — optional `timeout` field in `providers.yaml` | ✅ |
| 38 | LinkedIn Newsletter companion post — `--linkedin-post` generates `linkedin_post.md` + `linkedin_notification.txt` | ✅ |
| 41 | Newsletter engagement image & notification — `newsletter_merge.py` auto-generates `engagement_image.png` (FairParallelPanel concept panel + shared `core/image_generation.py` renderer) and `edition_notification.txt` | ✅ |
| 42 | Researched LinkedIn article — `--linkedin-post` article is independently researched by Claude/Gemini/Grok (each with its own real web search), angle-planned and written via two `FairParallelPanel` stages, with a repeatable `--angle` flag and a code-built Sources list. *Amended 2026-08-29*: the article now opens with a labelled Executive Summary section, and the AI-authorship disclosure + pipeline metrics moved from right after the title to the bottom of the article, inside "Behind the Scenes". *Amended again 2026-08-29*: every source domain is now classified for paywall/reliability by a dedicated `FairParallelPanel` (cached in `source_domains.duckdb`, gitignored) before angle-planning or writing ever sees it; the article cites sources inline as numbered footnotes against a matching, capped (≤15) Sources list | ✅ |
| 43 | Uniform source titles — every Sources-list entry reads as `domain - page title` regardless of provider; Gemini/Grok resolve it via a direct `httpx` fetch of the cited URL, Claude gets a domain prefix added to its own already-good title | ✅ |
| 44 | Descriptive source titles — a 4-step chain (fetched `<title>`/`og:title`/`twitter:title` → humanised URL-path slug → the source's own provider's same-call title → drop) replaces the single-tier fetch, so no source is ever published as a bare domain or the site's own name restated | ✅ |
| 45 | LinkedIn feature image size correction — `engagement_image.png` and, with `--linkedin-post` on a single-panel/horizontal cartoon, `cartoon.png` are corrected in Python (Gemini aspect-ratio hint + Pillow centre-crop/resize) to exactly LinkedIn's 1200x644 Article-cover size, so LinkedIn's own auto-crop never clips the image | ✅ |
| 46 | Research-only mode — `--research-only` skips the entire satirical pipeline (Cultural Strategist, Satirist, Image Generator, Image Evaluator) and runs only the research/angle-planning/writing engine, producing a neutral `research_report.md` by default or the branded `linkedin_post.md` when combined with `--linkedin-post`; on the `gata` CLI it runs once (first inferred audience) instead of once per audience | ✅ |
