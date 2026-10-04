# Quickstart: validating the single-audience default

Run from the repo root. Real calls need the keys (RULE 16): `source set_gata.sh`.

## 1. Offline checks (the test suite — no API calls)

```bash
python -m pytest tests/test_cli.py -v
python -m pytest tests/ -q
ruff check . && ruff format --check .
```

Expected: the new tests pass — default run is one audience with no guessing call;
`--audience` selects, orders and de-duplicates; invalid input exits 1 before any call;
`--infer-audiences` keeps today's behaviour; `--research-only` takes the first
selected audience; the built-in default equals `communities.yaml`'s `uk-tech-engineers`.

## 2. Free manual checks (no paid call — validation happens first)

```bash
gata "test topic" --audience not-a-real-audience     # ERROR naming the value + valid choices, exit 1
gata "test topic" --audience ""                      # ERROR, exit 1
gata "test topic" --infer-audiences --audience uk-politics   # ERROR: cannot be used together, exit 1
gata --help                                          # documents the default, --audience, --infer-audiences
cd /tmp && gata "test topic" --audience uk-politics  # ERROR: communities.yaml not found ... (exit 1)
```

These exit before any model call, so they cost nothing.

## 3. Optional paid smoke test (one pipeline run — a few dollars at most)

```bash
gata "model currency smoke test"
```

Expected: one `[1/1] uk-tech-engineers — English` progress line, one image
`model_currency_smoke_test/uk-tech-engineers.png`, no audience-guessing step, and a
single total in `summary.txt`. Add `--audience uk-politics --audience portuguese-adults`
to see two runs (`[1/2]`, `[2/2]`) — costs two pipeline runs.

## 4. Docs and governance gates (RULE 6 / 15 / 17 / 19)

- README `gata` section and `docs/architecture.md` describe the new default,
  `--audience` and `--infer-audiences`; no remaining "UK always added" claim for the
  default path: `grep -rniE "always (added|present|included)|UK public" README.md docs`.
- CHANGELOG has v1.31.0; version files say 1.31.0; `TODO.md` no longer lists this item.
