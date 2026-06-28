# Plan: Spec 035 — Direct Satirist Mode

## Constitution Check

| Principle | Rule | Status | Notes |
|-----------|------|--------|-------|
| §1 | SDK and model rules | ✅ Pass | No new SDKs or models |
| §2 | Image output rule | ✅ Pass | Image output unchanged |
| §3 | XML and output contract | ✅ Pass | `<verdict>` tags unchanged |
| §4 | Character rules | ✅ Pass | No prompt template changes |
| §5 | Visual style rules | ✅ Pass | No image prompt changes |
| §6 | Verdict JSON schema | ✅ Pass | Schema unchanged |
| §7 | Language rule | ✅ Pass | `output_language` still flows from seed_brief |
| §8 | Project structure | ✅ Pass | No new directories |
| §9 | Testing rules | ✅ Pass | Tests written before implementation (TDD) |
| §10 | Secrets and security | ✅ Pass | No credentials involved |
| §11 | Development stages | ✅ Pass | New branch `035-direct-satirist-mode` |
| §12 | Code quality | ✅ Pass | ruff check + format before commit |
| §13 | Logging | ✅ Pass | Direct mode logged at INFO level |

---

## Architecture

### `core/runner.py`

Add `skip_cultural_strategist: bool = False` to `run_pipeline()`.

When `True`, replace the Cultural Strategist call with a minimal `EnrichedBrief`:

```python
if skip_cultural_strategist:
    print("  Direct mode — skipping Cultural Strategist", flush=True)
    logger.info("run_pipeline: direct mode — Cultural Strategist skipped")
    enriched_brief = EnrichedBrief(
        target_audience=seed_brief.target_audience,
        output_language=seed_brief.output_language,
        tone=seed_brief.tone,
        cultural_angle=topic,
        culturally_loaded_references=[],
    )
else:
    print("  Cultural Strategist...", flush=True)
    enriched_brief, agent0_log, agent0_tel = agent_cultural_strategist.run(...)
    telemetry.agents.append(agent0_tel)
```

No other changes to `run_pipeline()`. The Satirist, Image Generator, and Evaluator
are unaffected and receive the same types as before.

### `pipeline.py`

Add one argument to the argparse setup:

```python
parser.add_argument(
    "--direct",
    action="store_true",
    help="Skip the Cultural Strategist; feed topic directly to the Satirist.",
)
```

Pass it through to `run_pipeline()`:

```python
run_pipeline(
    ...,
    skip_cultural_strategist=args.direct,
)
```

---

## Implementation sequence (TDD)

### Phase 1 — Tests (`tests/test_pipeline.py`)

Extend the existing test file with these new tests before any implementation:

| # | Test | What it checks |
|---|------|----------------|
| 1 | `test_direct_flag_skips_cultural_strategist` | `run_pipeline(..., skip_cultural_strategist=True)` does NOT call `agent_cultural_strategist.run` |
| 2 | `test_direct_flag_builds_minimal_enriched_brief` | minimal `EnrichedBrief` has `cultural_angle == topic`, empty references, audience/language/tone from seed_brief |
| 3 | `test_direct_flag_passes_brief_to_satirist` | Satirist receives the minimal brief (not None, not a Cultural Strategist brief) |
| 4 | `test_direct_flag_absent_cultural_strategist_in_telemetry` | `RunTelemetry.agents` has no entry named "Cultural Strategist" when `--direct` is used |
| 5 | `test_normal_mode_unchanged` | Without `skip_cultural_strategist`, `agent_cultural_strategist.run` IS called (regression guard) |

### Phase 2 — Implementation

1. `tests/test_pipeline.py` — add 5 tests (Phase 1)
2. `core/runner.py` — add `skip_cultural_strategist` parameter and branch
3. `pipeline.py` — add `--direct` flag
4. `core/cli.py` — add `--direct` flag (same wiring as `pipeline.py`)
5. `core/__version__.py` — bump to `1.18.0`

### Phase 3 — Verification

- `python -m pytest tests/` — zero failures
- `ruff check . && ruff format .` — exit 0
- Live run: `python pipeline.py --topic "..." --community uk --direct`
  - confirm `"Direct mode"` log line
  - confirm Cultural Strategist absent from cost summary
  - confirm image is produced

---

## Complexity Notes

- Minimal change: 2 files changed in core logic (`runner.py`, `pipeline.py`), 1 version bump
- `EnrichedBrief` does not need a new constructor or factory — direct field assignment is fine
- `agent0_log` stays `None` in direct mode; `core/bundle_writer.py` already handles `None` logs
- RULE 14: no blank lines between phases inside `run_pipeline()` — use inline comments
