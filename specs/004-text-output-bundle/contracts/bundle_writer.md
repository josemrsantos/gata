# Contract: bundle_writer

**Module**: `agents/bundle_writer.py`
**Role**: Creates the output bundle folder and writes all bundle files after a pipeline run.

---

## Public Interface

```python
def write_bundle(
    output_path: str,
    agent0_log: ConversationLog,
    bc_log: ConversationLog,
    enriched_brief: EnrichedBrief,
    image_prompt: str,
) -> str:
    ...
```

**Returns**: Absolute path to the bundle folder that was created.

**Never raises**: All exceptions are caught internally. Failures are logged at `ERROR` level.
The function always returns the bundle folder path (even if some files could not be written).

---

## Bundle Folder Derivation

```python
from pathlib import Path

bundle_dir = Path(output_path).parent / Path(output_path).stem
```

Examples:
- `output/portuguese_adults/pt_sporting.png` →
  `output/portuguese_adults/pt_sporting/`
- `output/manual/pt_housing_crisis_in_lisbon.png` →
  `output/manual/pt_housing_crisis_in_lisbon/`

The folder is created with `Path.mkdir(parents=True, exist_ok=True)` — overwrites silently.

---

## Files Written

| File | Content | Failure behaviour |
|------|---------|-------------------|
| `agent0_log.txt` | Formatted Agent 0 turns | Logs error; continues |
| `bc_log.txt` | Formatted B/C turns | Logs error; continues |
| `explanation.html` | In-language HTML from agent_explainer | Logs error; skips prompt card too |
| `deep_dive_en.html` | English HTML from agent_explainer | Logs error; written independently |
| `prompt_card.txt` | Verbatim `image_prompt` string | Logs error; continues |

---

## Log Formatting (format_log)

```python
def format_log(log: ConversationLog) -> str:
    ...
```

Internal helper that produces the plain-text log body. Format per iteration:

```
=== Iteration N ===

[PROPOSER ROLE]
{full proposer text}

[REVIEWER ROLE]
Verdict: APPROVED / NEEDS REVISION / FINAL SAY
{full reviewer text}

---
```

- Iterations are separated by `---` on its own line.
- The header shows total iterations only on the last one: `=== Iteration N / N ===` when N
  equals the maximum.
- `"FINAL_SAY"` verdict is displayed as `FINAL SAY (approved)`.

---

## Partial Bundle on Failure (FR-010)

`write_bundle()` is designed to be called after any failure point. When called with only
one log (e.g. the B/C loop never ran because Agent 0 failed), the missing log argument
should be `None`. The function writes only non-None logs and skips HTML generation.

Updated signature to support partial write:

```python
def write_bundle(
    output_path: str,
    agent0_log: ConversationLog | None,
    bc_log: ConversationLog | None,
    enriched_brief: EnrichedBrief | None,
    image_prompt: str | None,
) -> str:
    ...
```

HTML and prompt card are only generated when `enriched_brief` and `image_prompt` are
both non-None.
