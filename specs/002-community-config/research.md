# Research: Stage 2 Community Configuration

**Branch**: `002-stage-2-community-config` | **Date**: 2026-05-03

All technical decisions for Stage 2 are resolved. This document records each decision, its rationale,
and alternatives considered.

---

## Decision 1: YAML library

**Decision**: `pyyaml` (`import yaml`)

**Rationale**: De facto standard for YAML in Python. The config schema is flat and simple — a list of
community objects with five string/list fields. No schema validation library (Pydantic, cerberus,
strictyaml) is justified. Validation is hand-written in `config_loader.py` and is more directly testable
than declarative schema definitions. `pyyaml` is also already a transitive dependency of several common
packages, so it adds minimal footprint.

**Alternatives considered**:
- `ruamel.yaml` — preserves YAML comments on round-trip; not needed since we never write back to the file.
- `strictyaml` — enforces schema at parse time; the custom validation in `config_loader.py` provides the
  same guarantees with clearer error messages.
- `tomllib` (stdlib, Python 3.11+) — TOML not YAML; different format, project has already settled on YAML.

---

## Decision 2: CLI argument parsing library

**Decision**: `argparse` (stdlib)

**Rationale**: Four flags for manual mode, one flag for community mode. `argparse` handles mutual exclusion
via `add_mutually_exclusive_group()` or argument presence checks. No additional dependency needed. For a
developer-facing CLI tool at this stage, the standard library is sufficient.

**Alternatives considered**:
- `click` — more ergonomic decorator-based API; adds a dependency not justified by the complexity of four flags.
- `typer` — type-annotated, auto-generates help text; same dependency overhead objection as `click`.

**Mutual exclusion implementation**: `argparse` does not natively support "all of group A OR all of group B"
semantics. The check is implemented post-parse in `pipeline.py`: if any manual flag is provided, all four
must be present; if `--community` is also present alongside any manual flag, exit with a conflict error.
This keeps the validation explicit and readable.

---

## Decision 3: Logging configuration pattern

**Decision**: `logging.basicConfig()` called once in `pipeline.py:main()`. Each module calls
`logging.getLogger(__name__)`.

**Format**: `%(asctime)s [%(name)s] %(levelname)s %(message)s`

**Rationale**: Centralised configuration in the entry point is the standard Python logging pattern. Agent
modules obtain a logger but never configure one — this prevents handler duplication and respects the
library/application boundary. `__name__` as the logger name makes the source module visible in every log
line without extra effort.

**Log levels applied**:
- `INFO` — normal flow: community selected, topic selected, iteration progress, image saved
- `WARNING` — recoverable issues: near-duplicate detected, language leakage, generic critique re-call
- `ERROR` — failures: XML retry exhaustion, image extraction failure, config validation failure

**Alternatives considered**:
- `structlog` — structured JSON logging; useful for production log aggregation but premature for Stage 2.
- Per-module `basicConfig` calls — causes handler duplication; rejected.

---

## Decision 4: `Community` dataclass location

**Decision**: Add `Community` dataclass to `agents/types.py` alongside existing dataclasses.

**Rationale**: Consistent with `StrategyBrief`, `CartoonConcept`, `Critique`. Keeps all shared data types
in one place. `Community.to_brief()` convenience method converts a `Community` to a `StrategyBrief` — the
translation lives with the type, not scattered across caller code.

**Alternatives considered**:
- Define inside `config_loader.py` — makes the type harder to import independently and breaks the
  established pattern.
- Use a `TypedDict` — less ergonomic; no method attachment; rejected.

---

## Decision 5: `agent_d.generate()` output path parameter

**Decision**: Remove module-level `OUTPUT_PATH` constant. Add `output_path: str` as a required parameter
to `generate(concept, brief, output_path)`.

**Rationale**: Stage 2 requires a runtime-computed path (`output/{community}/{topic}.png`). A module-level
constant cannot hold a runtime value. Passing the path explicitly makes the function pure with respect to
file I/O location — easier to test and reason about. Existing tests that patched `OUTPUT_PATH` are updated
to pass the path directly.

**Alternatives considered**:
- Keep `OUTPUT_PATH` as a module global, set it in `pipeline.py` before calling `generate()` — mutable
  global state; rejected as fragile and untestable.
- Accept an optional parameter with the old constant as default — backwards compatibility not needed since
  all callers are in-repo and updated atomically.

---

## Decision 6: Sanitization function

**Decision**: `sanitize_path_segment(text: str) -> str` in `agents/config_loader.py`.

**Rules** (same for both community name and topic):
1. Lowercase the entire string
2. Replace spaces with underscores
3. Strip all characters that are not `[a-z0-9_-]` (alphanumeric, underscores, hyphens)
4. Truncate to 50 characters

**Rationale**: Single function, called twice (community name and topic). Defined in `config_loader.py`
because that module is responsible for turning raw YAML values into filesystem-safe strings.
Exported so `pipeline.py` and tests can call it directly.

**Unicode/non-ASCII**: Characters outside `[a-z0-9_]` are stripped after lowercasing. Portuguese characters
(`ã`, `ç`, `é`, etc.) will be stripped. This means `"habitação"` becomes `"habitao"`. This is acceptable
for Stage 2: the output path is an internal artefact, not a user-visible label. A transliteration step
(e.g., `unidecode`) is deferred to Stage 4 if needed.

**Alternatives considered**:
- Apply transliteration before stripping (e.g., `unidecode`) — better human-readable paths for non-ASCII;
  deferred to Stage 4 as an enhancement, not a correctness issue.
- Use hyphens instead of underscores — minor style preference; underscores chosen for consistency with the
  existing topic sanitization example in the spec (`is_scrum_really_agile.png`).
