# Gata Newsroom

[![PyPI version](https://img.shields.io/pypi/v/gata)](https://pypi.org/project/gata/)

An automated multi-agent pipeline that transforms daily topics into a recurring satirical cartoon series starring **Gata**, a serious investigative calico cat who views all geopolitics through the lens of feline priorities.

## Status

| Stage | Name | Status |
|-------|------|--------|
| 1 | Core pipeline (Satirist/Co-Satirist creative loop + image generation) | ✅ Complete |
| 2 | Community config + model fallback chains | ✅ Complete |
| 3 | Cultural Strategist (Framer + Resonator) | ✅ Complete |
| 4 | Text Output Bundle (logs, HTML explanations, prompt card) | ✅ Complete |
| 5 | Housekeeping + rules redefinition | ✅ Complete |
| 6 | Trend Scout — automated topic discovery via NewsAPI.org + Gemini | ✅ Complete |
| 7 | Comedy style configuration via humor.yaml | ✅ Complete |
| 8 | Free-text community mode — --community accepts any description | ✅ Complete |
| 9 | Multi-panel cartoon format — --panels and --layout flags | ✅ Complete |
| 10 | Agent personality — inconvenience level (0–100) + dual satirist mode | ✅ Complete |
| 11 | Dynamic news search — infers country + category from free-text; --community + --topic mode | ✅ Complete |
| 12 | Run summary — per-agent time, iterations, and cost + grand total | ✅ Complete |
| 13 | Optional HTML output — --html flag, off by default | ✅ Complete |
| 14 | Image generation cost tracking — accurate $/image in telemetry and summary | ✅ Complete |
| 15 | Single main audience default — one inferred audience + UK per run | ✅ Complete |

## How it works

1. **Trend Scout** fetches today's top headlines for the community and ranks them by satirical potential. For free-text communities, it infers the appropriate country and news category in a single Gemini call (`infer_community_profile`). In `--community + --topic` mode, Trend Scout is bypassed entirely.
2. **Cultural Strategist** (Framer + Resonator loop) negotiates a cultural angle and audience-specific references for the chosen topic
3. **Satirist + Co-Satirist loop** iterates on a satirical cartoon concept until approved (up to 5 iterations)
4. **Image Generator** renders the approved concept into a PNG via a fallback chain of Gemini image models
5. **Explainer** (opt-in via `--html`) produces two HTML explanation pages: one in the target language, one in English for operators
6. **Bundle writer** saves the full output package: image, conversation logs, prompt card, telemetry, and summary — plus the HTML files when `--html` is set

All agents use prioritised model fallback chains. Both dual-loop pairs (Framer/Resonator and Satirist/Co-Satirist) include a 3-pass self-review injected into both personas.

## Agents

| Agent | Sub-agents | LLMs | What it does |
|---|---|---|---|
| **Trend Scout** | — | Gemini | Fetches today's headlines from NewsAPI.org and picks the top 3 ranked by satirical potential for the community |
| **Cultural Strategist** | Framer, Resonator | Claude (Framer) · Gemini (Resonator) | Framer proposes a cultural angle and audience references; Resonator approves or challenges until the angle is specific and sharp |
| **Creative Loop** | Satirist, Co-Satirist | Claude (Satirist) · Grok (Co-Satirist, Gemini fallback) | Satirist proposes the cartoon concept; Co-Satirist either approves or counters with a sharper version; loops up to 5 iterations |
| **Image Generator** | — | Gemini image models | Renders the approved image prompt into a PNG; tries up to 5 models in order before failing |
| **Image Evaluator** | — | Gemini vision models | After image generation, checks for LLM rendering artifacts (duplicate text, garbled text, character failures) and rates whether the cartoon is genuinely funny for the target audience; triggers regeneration up to 2 times on rejection |
| **Explainer** | Writer, Editor | Claude (Writer) · Gemini (Editor) | Writer drafts two HTML pages (in-language for end users, English for operators); Editor approves or requests revision |

## Quick start

```bash
pipx install gata
export ANTHROPIC_API_KEY=...
export GEMINI_API_KEY=...
gata "World Cup Qatar vs Swiss"
```

This generates two satirical cartoons from a single topic — one for the most culturally relevant audience (inferred by the pipeline) and one for the UK public — saved to a subdirectory of your working directory.

## Setup

**Install from PyPI** (recommended — installs the `gata` command globally):

```bash
pipx install gata
```

If `pipx` is not installed: `sudo apt install pipx && pipx ensurepath`

**Install into a virtual environment** (for use as a library or in scripts):

```bash
pip install gata
```

**Install from source (for development):**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### Required secrets

Three API keys are required:

| Variable | Where to get it | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Cultural Strategist, Satirist, Explainer |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Trend Scout, Image Generator, Resonator, Co-Satirist fallback |
| `XAI_API_KEY` | [console.x.ai](https://console.x.ai) | Co-Satirist (Grok) |
| `NEWSAPI_ORG_KEY` | [newsapi.org](https://newsapi.org) | Trend Scout (headline fetching) |

### Option A — `.env` file (recommended for local development)

Create a `.env` file in the project root. It is git-ignored and never committed.

```
ANTHROPIC_API_KEY=your_anthropic_key_here
GEMINI_API_KEY=your_gemini_key_here
XAI_API_KEY=your_xai_key_here
NEWSAPI_ORG_KEY=your_newsapi_key_here
```

The pipeline loads this file automatically on startup and logs `credentials loaded from .env file` to confirm.

### Option B — environment variables (recommended for CI/CD and servers)

Export the variables in your shell before running the pipeline. The pipeline detects that no `.env` file is present and logs `reading credentials from environment variables`.

```bash
export ANTHROPIC_API_KEY=your_anthropic_key_here
export GEMINI_API_KEY=your_gemini_key_here
export XAI_API_KEY=your_xai_key_here
export NEWSAPI_ORG_KEY=your_newsapi_key_here
python pipeline.py --community uk-politics
```

In GitHub Actions, add the three values as repository secrets (`Settings → Secrets and variables → Actions`) and reference them in your workflow:

```yaml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  XAI_API_KEY: ${{ secrets.XAI_API_KEY }}
  NEWSAPI_ORG_KEY: ${{ secrets.NEWSAPI_ORG_KEY }}
```

## `gata` command

The simplest way to run the pipeline. Give it any topic and it generates two satirical
cartoons: one for the most culturally relevant audience (inferred automatically) and one
for the UK public.

```bash
# Generate cartoons for a news topic
gata "Interest rates stay high despite falling inflation"
# → infers audience (e.g. "german"), adds UK
# → saves german.png + uk.png to ./interest_rates_stay_high.../

# Any topic works — Gata will find the angle
gata "World Cup final: Argentina vs France"
gata "Tech layoffs hit Silicon Valley again"
gata "Portugal wins Eurovision"

# Also generate HTML explanation pages (off by default — adds an extra Claude + Gemini call)
gata "NATO summit in Brussels" --html
```

Output folder: `{cwd}/{topic_slug}/` — one PNG per audience, plus a bundle folder per image containing logs, prompt card, telemetry, and a cost/time summary. Run `gata --help` to see all options.

## `pipeline.py` — advanced usage

```bash
# Named community (exact match in communities.yaml; topic selected by Trend Scout)
python pipeline.py --community uk-politics

# Free-text community (no entry required in communities.yaml; language and tone inferred)
python pipeline.py --community "US community that dislikes Trump"
python pipeline.py --community "Communauté française qui critique Macron"

# Community + topic mode (brief from community, topic supplied directly — no Trend Scout)
python pipeline.py --community uk-politics --topic "Number 10 is becoming available for rent, again."
python pipeline.py --community "Adeptos portugueses de futebol" --topic "O Ronaldo vai levar Portugal ao mundial"

# Random community and topic
python pipeline.py

# Manual mode (bypasses communities.yaml entirely)
python pipeline.py --topic "AI hype" --audience "developers" --language "English" --tone "dry wit"

# Multi-panel cartoon (add --panels N and --layout direction to any mode above)
python pipeline.py --community uk-politics --panels 3 --layout horizontal
python pipeline.py --community portuguese-adults --panels 2 --layout vertical
python pipeline.py --topic "World Cup result" --audience "football fans" --language "English" --tone "excited" --panels 4 --layout horizontal

# Also generate the HTML explanation pages (off by default; add --html to any mode above)
python pipeline.py --community uk-politics --html
```

### Multi-panel flags

| Flag | Values | Default | Description |
|---|---|---|---|
| `--panels` | 1–4 | 1 | Number of panels in the cartoon strip |
| `--layout` | `horizontal`, `vertical` | `horizontal` | Panel arrangement direction |

CLI flags take precedence over `communities.yaml` panel config, which takes precedence over the defaults.
Output filename prefix: `{N}{d}_` for multi-panel (e.g. `3h_english_topic.png`); no prefix for single-panel.

Output is saved to a bundle folder:
- Community mode: `output/{community}/{topic}/`
- Manual mode: `output/manual/{topic}/`

Each bundle contains:
- `cartoon.png` — the generated image
- `agent0_log.txt` — Agent 0 negotiation history (cultural strategy)
- `bc_log.txt` — B/C creative loop history (satirist + co-satirist exchange)
- `prompt_card.txt` — verbatim image prompt for standalone reuse
- `telemetry.json` — per-agent timing, token counts, and cost (machine-readable)
- `summary.txt` — per-agent time, iterations, and cost, plus a run total (human-readable)

With `--html` (off by default), the bundle also contains:
- `explanation.html` — in-language explanation of the joke for end users
- `deep_dive_en.html` — English operator deep-dive (news context, cultural references, satirical logic)

Running `gata <topic>` also writes a top-level `{output_dir}/summary.txt` aggregating time and cost across every audience generated for that topic.

## Communities

Communities are defined in `communities.yaml`. Each community specifies a target audience, output language, tone, a list of seed topics, and optionally a default panel count and layout direction.

| Community | Language | Tone |
|---|---|---|
| `uk-politics` | English | Dry British wit |
| `uk-tech-engineers` | English | Dry British wit |
| `portuguese-adults` | Portuguese | Sátira política afiada |
| `portuguese-politics` | Portuguese | Sátira política afiada |
| `us-startup-crowd` | English | Sarcastic Silicon Valley cynicism |

To add a new community, add an entry to `communities.yaml` — no code changes required.

## Comedy configuration (humor.yaml)

`humor.yaml` controls the comedy style and agent personality for every run. All fields default to off so the file is optional.

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
| `critic` | `evaluate_joke_mechanics` | bool | Critic checks that the chosen joke type is executed correctly |
| `critic` | `flag_if_no_subversion` | bool | Critic rejects straight-play concepts with no twist |
| `critic` | `inconvenience` | 0–100 | How aggressively Critic demands uncomfortable truths |
| `critic` | `dual_satirist` | bool | Replace adversarial Critic with a co-creating Second Satirist |

**Inconvenience levels:** 0 = off; 1–33 = mild nudge ("look beneath the obvious"); 34–66 = medium push ("don't let the target off the hook"); 67–100 = maximum ("if the audience doesn't squirm, it isn't ready").

**Dual satirist mode:** when `critic.dual_satirist: true`, the Critic becomes a Second Satirist who builds on the first Satirist's idea rather than evaluating it against rules. The loop still terminates when the Second Satirist responds with `APPROVED`.

## Tech Stack

- Python 3.x
- **Framer** — Anthropic Claude (`claude-sonnet-4-6` → `claude-opus-4-7` → `claude-haiku-4-5-20251001`)
- **Resonator** — Google Gemini (`gemini-2.5-pro` → `gemini-2.5-flash` → `gemini-2.0-flash`)
- **Satirist** — Anthropic Claude (same fallback chain as Framer)
- **Co-Satirist** — xAI Grok (`grok-3` → `gemini-2.5-flash` → `gemini-2.0-flash` Gemini fallback)
- **Image Generator** — Google Gemini image models (`gemini-3.1-flash-image-preview` → `gemini-3.1-flash-image` → `gemini-3-pro-image-preview` → `gemini-3-pro-image` → `gemini-2.5-flash-image`)
- **Explainer Writer** — Anthropic Claude (`claude-sonnet-4-6`, max 8192 tokens)
- **Explainer Editor** — Google Gemini (`gemini-2.5-flash` → `gemini-2.5-pro` → `gemini-2.0-flash`)
- **Trend Scout** — fetches today's headlines from NewsAPI.org and uses Gemini `gemini-2.5-flash` to rank them by satirical potential for the community

## Upcoming Work

See `TODO.md` for the full backlog. Key items:

- **Post-generation image review** — vision model checks for rendering artifacts (duplicate labels, garbled text, Gata integrity failures) and retries before writing the bundle
- **Voting system** — funny / not funny ratings per cartoon feeding back into the pipeline to improve future output
- **Self-documenting CLI** — `pipeline.py` with no arguments prints all calling modes with ready-to-copy examples
- **Gemini fact-check gate** — Gemini verifies every factual claim in the concept before the image prompt is finalised; returns with a `FACT:` tag if anything is wrong
- **Batch image generation** — use the Gemini Batch API to cut image generation cost by ~50%
