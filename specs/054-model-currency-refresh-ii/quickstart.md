# Quickstart: validating Model currency refresh II

Run from the repo root. Real calls need the API keys (RULE 16):

```bash
source set_gata.sh
```

## 1. Offline checks (no API calls, part of the test suite)

```bash
python -m pytest tests/ -q          # must report 0 failures (§9)
ruff check . && ruff format --check .   # must exit 0 (§12)
```

Expected: the new invariant tests (every default model has a price entry; no
retired name in any default; Grok panelist ≠ aggregator; chain provider order
unchanged) pass — see `contracts/model-matrix.md` §4.

## 2. One-off live check — FR-001 / SC-004 / FR-014 (manual, NOT in the test suite)

**Use a realistic prompt, not a trivial one** (Amendment A): a "ping" is answered without thinking and hides problems such as the Claude 5 thinking-block crash. Send each Claude default the real Satirist prompt (`_build_satirist_system_prompt(...)` with a topic as the user message, as in research.md §9) through `ClaudeProvider.generate()` and confirm text comes back.

One short call per **distinct** default model. Before changing code, run it
against the *proposed* new models to confirm they exist; after the change, run
it against whatever the code now treats as default (read from the real chains).
Throwaway command, nothing is committed:

```bash
python - <<'EOF'
from llm import ClaudeProvider, GeminiProvider, GrokProvider
checks = [
    (ClaudeProvider, "claude-sonnet-5-5"), (ClaudeProvider, "claude-opus-5-5"),
    (ClaudeProvider, "claude-haiku-4-5-20251001"),
    (GeminiProvider, "gemini-3.8-flash"), (GeminiProvider, "gemini-3.5-flash-lite"),
    (GeminiProvider, "gemini-2.5-pro"),
    (GrokProvider, "grok-4.3"), (GrokProvider, "grok-build-0.1"),
    (GrokProvider, "grok-3"),  # D-X4 (see the raw check below for what xAI reports)
]
for cls, model in checks:
    try:
        text, usage = cls(model).generate("Reply with OK.", [{"role": "user", "content": "ping"}], max_tokens=1024)  # thinking models need room
        print(f"OK   {model:32} in={usage.input_tokens} out={usage.output_tokens} cost=${usage.cost_usd:.6f}")
    except Exception as exc:
        print(f"FAIL {model:32} {type(exc).__name__}: {str(exc)[:120]}")
EOF
```

For the Grok aliases the response's own `model` field is the evidence, because
`usage.model` only echoes the name we asked for: `GrokProvider("grok-4.3").client.chat.completions.create(model="grok-3", messages=[...], max_tokens=16).model`.
Record each line's result in `research.md` §6 (verification record). Expected
cost: a few cents in total. A FAIL on a planned default stops the swap for that
model until resolved.

### 2b. Image models (required — they are defaults too)

Text calls cannot test image models, so make one real image call per image
model in the chain (about $0.07 and $0.13). Throwaway, outputs go to the
scratch directory:

```bash
python - <<'EOF'
import tempfile, os
import core.image_generation as ig
for model in ("gemini-3.1-flash-image", "gemini-3-pro-image"):
    ig._MODELS = [model]
    out = os.path.join(tempfile.mkdtemp(), "check.png")
    try:
        ig.ImageGeneration().generate("A grey cat sitting on a desk.", out, show_title=False)
        print(f"OK   {model} -> {os.path.getsize(out)} bytes")  # generate() returns (path, AgentTelemetry)
    except Exception as exc:
        print(f"FAIL {model} {type(exc).__name__}: {str(exc)[:120]}")
EOF
```

## 3. Default end-to-end check (optional, a few dollars)

```bash
python pipeline.py --topic "model currency smoke test" --audience "UK engineers" --language English --tone dry
gata "model currency smoke test"
```

Expected: both complete; `run.log` in each bundle has no model-not-found or
retired-model warning, and the image step's first attempt is
`gemini-3.1-flash-image` (not the old `-preview` name). Skip if §2 plus the offline checks are enough.

## 4. Docs and governance gates (RULE 17 / 19)

- `CHANGELOG.md` has the new version entry; `README.md` and `docs/architecture.md`
  show the new model names; no stale name remains: `grep -rnE "claude-sonnet-4-6|gemini-2\.5-flash\b|-image-preview" README.md docs CHANGELOG.md` (only historical
  CHANGELOG lines may match).
- `TODO.md` no longer lists "Model currency refresh II" (RULE 19).
- Constitution is at the approved new version with §1/§6 matching the matrix.
