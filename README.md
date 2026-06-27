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
2. **Cultural Strategist** — three Framers (Claude, Grok-mini, Gemini) independently
   propose a cultural angle; Grok-3 (Resonator) aggregates and picks the sharpest one
3. **Satirist** — three Panelists (Claude, Grok-mini, Gemini) independently generate a
   cartoon concept; Grok-3 (Aggregator) picks the strongest concept
4. **Image Generator** renders the approved concept into a PNG via a fallback chain of
   Gemini image models; overlays the Satirist-authored title as a dark banner at the top
   (suppressed with `--no-title`)
5. **Explainer** (opt-in via `--html`) — three Writers (Claude, Grok-mini, Gemini)
   independently draft an HTML explanation page; Grok-3 (Editor) picks the best one;
   runs twice — once in the target language, once in English
6. **Bundle Writer** saves the full output package: image, conversation logs, prompt
   card, telemetry, and summary

## Agents

| Agent | Sub-agents | LLMs | What it does |
|---|---|---|---|
| **Trend Scout** | — | Gemini | Fetches today's headlines from NewsAPI.org and picks the top 3 ranked by satirical potential for the community |
| **Cultural Strategist** | Framer ×3, Resonator | Claude · Grok-mini · Gemini (Framers) · Grok-3 (Resonator/aggregator) | Three Framers independently propose a cultural angle and audience references; Resonator picks the sharpest one |
| **Satirist** | Panelist ×3, Aggregator | Claude · Grok-mini · Gemini (panelists) · Grok-3 (aggregator) | Three panelists independently generate a cartoon concept; Aggregator picks the strongest |
| **Image Generator** | — | Gemini image models | Renders the approved image prompt into a PNG; tries up to 5 models in order before failing |
| **Image Evaluator** | — | Gemini vision models | Checks for LLM rendering artifacts and rates comedy; triggers regeneration up to 2 times on rejection |
| **Explainer** | Writer ×3, Editor | Claude · Grok-mini · Gemini (writers) · Grok-3 (editor/aggregator) | Three Writers independently draft HTML explanation pages (in-language + English); Editor picks the best per run |

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

# Also generate HTML explanation pages
gata "NATO summit in Brussels" --html
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
```

### Multi-panel flags

| Flag | Values | Default | Description |
|---|---|---|---|
| `--panels` | 1–4 | 1 | Number of panels in the cartoon strip |
| `--layout` | `horizontal`, `vertical` | `horizontal` | Panel arrangement direction |
| `--no-title` | — | off | Suppress the title banner overlaid at the top of the image |

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
