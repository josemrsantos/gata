# Quickstart: Stage 1 Core Loop

**Branch**: `001-stage-1-core-loop` | **Date**: 2026-04-25

## Prerequisites

- Python 3.10+
- `uv` (`pip install uv`)
- An Anthropic API key
- A Google AI (Gemini) API key

## Setup

```bash
# 1. Create and activate virtual environment
uv venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# 2. Install dependencies
uv pip install -e ".[dev]"

# 3. Create .env in the project root
cat > .env <<EOF
ANTHROPIC_API_KEY=your_anthropic_key_here
GEMINI_API_KEY=your_gemini_key_here
EOF

# 4. Ensure output directory exists
mkdir -p output
```

## Run the pipeline

```bash
python pipeline.py
```

The pipeline will:

1. Validate the hardcoded topic and strategy brief
2. Run the Satirist + Critic loop (up to 5 iterations)
3. Generate and save the cartoon image

On success, output is saved to `output/cartoon_output.png`.

## Run the tests

```bash
pytest tests/
```

All tests run without real API calls — no `.env` required for testing.

## Check code quality

```bash
ruff check .
ruff format .
```

## Changing the hardcoded inputs

Open `pipeline.py` and edit the `TOPIC` string and `BRIEF` dataclass at the top of the file:

```python
TOPIC = "Your news topic here"
BRIEF = StrategyBrief(
    target_audience="Your target audience",
    output_language="English",
    tone="dry wit",
)
```

Then re-run `python pipeline.py`.
