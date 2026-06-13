# Quickstart: Text Output Bundle

## Manual Test Scenarios

### Scenario 1 — Full bundle from a community run

```bash
python pipeline.py --community portuguese_adults
```

**Expected outcome**:
1. `output/portuguese_adults/{lang}_{topic}/` folder exists.
2. `agent0_log.txt` — contains Framer and Resonator turns with iteration headers.
3. `bc_log.txt` — contains Satirist and Critic turns with iteration headers.
4. `explanation.html` — opens in browser; text is in Portuguese; explains the joke.
5. `deep_dive_en.html` — opens in browser; text is in English; explains cultural context.
6. `prompt_card.txt` — contains only the image prompt (no extra text).

### Scenario 2 — Full bundle from manual mode

```bash
python pipeline.py \
  --topic "Housing crisis in Lisbon" \
  --audience "Portuguese adults" \
  --language "Portuguese" \
  --tone "sarcastic"
```

**Expected outcome**: Same as Scenario 1. Bundle folder under `output/manual/`.

### Scenario 3 — Non-Latin script (Korean community, if configured)

```bash
python pipeline.py --community korean_news_readers
```

**Expected outcome**: `explanation.html` has `<meta charset="UTF-8">` and renders Korean
characters without corruption in Chrome/Firefox.

### Scenario 4 — Verify prompt card is verbatim

```bash
# After a run, compare prompt_card.txt with the image prompt logged by the pipeline
grep "image_prompt" output/portuguese_adults/*.png 2>/dev/null || \
  diff <(cat output/portuguese_adults/*/prompt_card.txt) \
       <(grep -A1 "image_prompt" /tmp/pipeline.log | tail -1)
```

### Scenario 5 — Partial bundle on early failure (manual test)

Temporarily add `raise RuntimeError("forced fail")` after `agent_0.run()` in pipeline.py,
then run:

```bash
python pipeline.py --community portuguese_adults
```

**Expected outcome**:
- Pipeline exits with non-zero code.
- Bundle folder exists containing `agent0_log.txt` (Agent 0 completed).
- `bc_log.txt`, `explanation.html`, `deep_dive_en.html`, `prompt_card.txt` are **absent**.

### Scenario 6 — Rerun over existing bundle

Run the pipeline twice with the same topic. The second run should overwrite all bundle files
without error (no `FileExistsError`).

---

## Unit Test Smoke Check

```bash
pytest tests/test_agent_explainer.py tests/test_bundle_writer.py -v
```

All tests should pass with mocked API calls. No real API calls should be made.

---

## Ruff Check

```bash
ruff check agents/agent_explainer.py agents/bundle_writer.py agents/types.py agents/dual_loop.py pipeline.py
ruff format --check agents/agent_explainer.py agents/bundle_writer.py agents/types.py agents/dual_loop.py pipeline.py
```
