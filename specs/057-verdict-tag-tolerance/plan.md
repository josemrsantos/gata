# Plan — Spec 057

Changes: `llm/dual_loop.py` (`_extract_proposer_verdict` bare-JSON fallback + `_strip_json_fence`);
`llm/fair_parallel_panel.py` (`_FORMAT_REMINDER`, one retry on `ValueError`, retry cost counted);
tests in `tests/test_dual_loop.py` and `tests/test_fair_parallel_panel.py`; CHANGELOG v1.32.1, README
status row 57, docs/architecture.md note, CLAUDE.md row, version 1.32.0 → 1.32.1.

Constitution check: §3 documents the `<verdict>` regex as the parser; it stays the primary path, the
JSON fallback is additive (no amendment needed). §9 TDD (tests first), §12 ruff, §13 logging (WARNING
via `logger`) all satisfied. The retry runs sequentially in the collecting thread, once, only after an
extraction failure, so normal runs have identical timing and cost.
Risk: a non-JSON-schema agent receiving bare JSON by accident — mitigated by requiring the whole reply
to parse as JSON. Version note: spec 056 (on hold) bumps to 1.33.0; whichever merges second re-bumps.
