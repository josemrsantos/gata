# Feature Specification: Clean Logging Output

**Feature Branch**: `017-clean-logging`
**Created**: 2026-06-18
**Status**: Draft

## Problem

Running `gata <topic>` produces hundreds of lines of HTTP-level noise from `httpx`,
`google.genai`, and `anthropic` internals. The cost and time data that operators actually
want (per-image and grand total) is buried inside this noise and effectively invisible.

Additionally, `DualPersonaLoop` logs a line per iteration at INFO, and
`agent_image_generator` logs the full image prompt (sometimes thousands of chars) at
INFO. Both amplify the noise significantly.

## Goal

After this stage, `gata <topic>` must produce clean, scannable output:

1. One INFO line when each agent **starts** (stating its purpose)
2. One INFO line when each agent **completes** (with iteration count and cost)
3. Per-audience time+cost visible after each image
4. Grand total time+cost clearly visible at the end
5. HTTP/SDK internals silenced to WARNING

## Technical Design

### Third-party logger silencing — `agents/cli.py` and `pipeline.py`

After `logging.basicConfig(...)` in both entry points, silence the four noisy SDK
loggers to WARNING:

```python
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google.genai").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)  # underscore variant
logging.getLogger("anthropic").setLevel(logging.WARNING)
```

### `agents/dual_loop.py`

- Add `logger.info("%s: starting", self._loop_name)` at the top of `run()`.
- Move per-iteration verdict log from INFO to DEBUG (line 208).
- On approval path: add `logger.info("%s: complete — approved after %d iteration(s)", ...)` before the return.
- On final-say path: change the INFO to `logger.info("%s: complete — max iterations reached", ...)`.

### `agents/agent_image_generator.py`

- Move the full-prompt log (`image_prompt:\n%s`) from INFO to DEBUG.
- Move the multi-panel start log from INFO to DEBUG.
- Move the per-model "trying model=X" log from INFO to DEBUG.
- Add `logger.info("Image Generator: rendering (%d chars)", len(prompt))` after both prompt-build branches.
- After successful `os.replace`, add `logger.info("Image Generator: saved — model=%s cost=$%.4f", model, cost_usd)`.

### `agents/runner.py`

- Add `logger.info("Cultural Strategist: analyzing topic...")` before the Cultural Strategist call.
- Add `logger.info("Satirist/Critic: creating concept...")` before the Satirist call.
- Remove the now-redundant `"creative loop complete — calling image generator"` log.
- Remove the `"done: cartoon saved to %s"` log (Image Generator now logs its own save).

### `agents/cli.py` — audience header improvement

- Switch the per-audience loop to `enumerate(audiences, 1)` and log `[i/N] name — language`.
- Change `"run summary (all audiences):\n%s"` to `"\n=== run summary ===\n%s"` for prominence.

## Modified files

| File | Change |
|------|--------|
| `agents/cli.py` | Silence third-party loggers; cleaner audience header; prominent grand total |
| `pipeline.py` | Silence third-party loggers |
| `agents/dual_loop.py` | Per-iteration INFO → DEBUG; add start + completion INFO |
| `agents/agent_image_generator.py` | Verbose logs → DEBUG; add concise start + saved INFO |
| `agents/runner.py` | Add agent start logs; remove redundant logs |
| `tests/test_dual_loop.py` | Update FR-010 test to match new INFO structure |
| `tests/test_agent_image_generator.py` | Update log-level test to match new INFO structure |

## Expected output shape (gata "some topic")

```
2026-06-18 12:01:00 [agents.cli] INFO credentials loaded from .env file
2026-06-18 12:01:02 [agents.cli] INFO audiences: portuguese(Portuguese), uk(English)
2026-06-18 12:01:02 [agents.cli] INFO [1/2] portuguese — Portuguese
2026-06-18 12:01:02 [agents.runner] INFO Cultural Strategist: analyzing topic...
2026-06-18 12:03:18 [agents.dual_loop] INFO Agent 0: complete — approved after 2 iteration(s)
2026-06-18 12:03:18 [agents.runner] INFO Satirist/Critic: creating concept...
2026-06-18 12:03:49 [agents.dual_loop] INFO B/C: complete — approved after 1 iteration(s)
2026-06-18 12:03:49 [agents.agent_image_generator] INFO Image Generator: rendering (842 chars)
2026-06-18 12:03:58 [agents.agent_image_generator] INFO Image Generator: saved — model=gemini-3.1-flash-image-preview cost=$0.1119
2026-06-18 12:03:58 [agents.runner] INFO run summary:
Cultural Strategist    143.3s   2 iter   $0.0744
Satirist/Critic         31.6s   1 iter   $0.0251
Image Generator          9.3s   1 iter   $0.1119

TOTAL: 184.2s — $0.2114
2026-06-18 12:04:01 [agents.cli] INFO [2/2] uk — English
...
2026-06-18 12:06:24 [agents.cli] INFO
=== run summary ===
portuguese: 184.2s — $0.2114
uk: 132.1s — $0.1843

TOTAL: 316.3s — $0.3957
2026-06-18 12:06:24 [agents.cli] INFO all 2 images saved to /path/to/output
```
