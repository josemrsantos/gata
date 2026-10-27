# Quickstart: validating Spec 058

Prerequisites: `source set_gata.sh` (RULE 16) for the live step only; unit tests need no keys.

1. **Unit tests** (mocked providers): `python -m pytest tests/ -q` — must pass with zero failures.
   Focused: `python -m pytest tests -k "reply_parsing or tag_free or satirist_labels or domain_classification or parse_failure_log" -q`.
2. **Lint**: `ruff check . && ruff format --check .`
3. **Fixtures replay** (SC-001): the tests feed the 2026-10-27 unclosed-`<verdict>` reply and the bare
   fenced Satirist JSON reply through `FairParallelPanel` and assert a usable result with no retry call.
4. **Live run** (SC-005, spends real API money — about one normal single-audience edition; the cost is not
   yet estimated — read the latest `run.log` TOTAL line before running):
   `python gata "<topic>"` then check `<bundle>/run.log`: no "missing closing </verdict> tag" lines, and any
   WARNING that does appear names the agent, round, model, field and excerpt.
5. **Stop reason per provider** (R2): in the live `run.log`, confirm `stop_reason=` appears for Claude,
   Gemini and Grok replies when a parse WARNING is forced (a tiny unit-level forced failure is also covered
   by mocked tests).
