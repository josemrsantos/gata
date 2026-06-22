# Gata Newsroom — Project Constitution

**Version**: 1.0
**Ratified**: 2026-06-22
**Ratified by**: Jose Santos (project lead)
**Status**: Active

---

## Preamble

This constitution governs all development decisions, implementation plans, and code
changes in the gata project. Every `plan.md` file must include a Constitution Check
table that gates implementation. A principle may be violated only when justified in
the plan's Complexity Tracking table and explicitly accepted by the project lead.

---

## Amendment Procedure

1. Propose the amendment in a GitHub issue or discussion.
2. Document the rationale and affected principles.
3. Obtain explicit approval from the project lead.
4. Update this file with the new version number, date, and amendment record.
5. Update any active `plan.md` files that reference the amended principle.

---

## Principles

### §1 — SDK and Model Rules

- Claude SDK: `import anthropic`; primary creative model `claude-sonnet-4-6`
- Gemini SDK: `from google import genai` (google-genai package); never use the
  deprecated `google-generativeai` package
- Gemini image generation: `gemini-3.1-flash-image-preview` (primary); fallback
  chain defined in `agents/agent_image_generator.py`
- Gemini text models: `gemini-2.5-flash` (primary for most agents);
  `gemini-2.5-pro` for evaluator tasks
- Grok SDK: `from openai import OpenAI` with `base_url="https://api.x.ai/v1"`;
  primary model `grok-3`
- No other LLM providers or SDKs without a constitution amendment

### §2 — Image Output Rule

- Image binary is extracted from `response.candidates[0].content.parts` by
  checking `part.inline_data`
- The raw binary from `inline_data.data` is written atomically to disk using
  `tempfile.NamedTemporaryFile` + `os.replace()`
- The image prompt text is NEVER written to disk; only the final PNG is persisted
- A partial or corrupt image file MUST NOT be left on disk if generation fails

### §3 — XML and Output Contract

- The Satirist wraps its cartoon concept in `<verdict>…</verdict>` tags containing
  valid JSON (see §6 for the JSON schema)
- No other XML tags are used for inter-agent communication
- Parsers use `re.search(r'<verdict>(.*?)</verdict>', text, re.DOTALL)` to extract
  the verdict block

### §4 — Character Rules

The following description of Gata MUST appear verbatim (never paraphrased, never
abbreviated) in every single-panel image prompt. For multi-panel runs it is appended
once to the composite prompt:

> Gata is a domestic shorthair calico-tabby mix: white chest, muzzle, and paws;
> dark grey/black tabby stripes; orange/ginger patches on back. She has a small
> dark spot on the bridge of her pink nose. She wears a simple dark leather collar
> with a gold/brass nameplate engraved "GATA". Her demeanour is serious,
> investigative, slightly tired, and highly intelligent. She never wears human
> clothes or accessories — no hats, glasses, pens, or clothing of any kind.

Any code or prompt that references Gata's appearance MUST copy this paragraph
character-for-character. Test coverage MUST assert the verbatim string is present.

### §5 — Visual Style Rules

Every image prompt MUST enforce the following aesthetic:

- **Colour palette**: greyscale background; Gata in full colour (Selective Color
  style)
- **Setting**: 1970s newspaper newsroom — fluorescent lights, heavy metal desks,
  background figures
- **The board**: dark chalkboard, hand-drawn white sketches; heading ALWAYS reads
  "ON THE SPOT" translated into the output language; never in English when the
  output language is not English
- **Attachments**: masking tape only — never pins
- **Style descriptor**: "single-panel satirical cartoon" for one panel; "N-panel
  comic strip" for multi-panel; minimalist charcoal-on-chalkboard style;
  high-contrast; dry one-line caption at the bottom
- **Never reference**: copyrighted artists or characters; describe visual
  characteristics only

### §6 — Verdict JSON Schema and Iteration Rules

The Satirist's `<verdict>` block contains valid JSON with this schema:

```json
{
  "panels": "<integer 1–4>",
  "layout": "horizontal | vertical",
  "title": "<punchy 3–8 word editorial headline in the output language>",
  "content": [
    {"scene": "...", "caption": "...", "beat": "..."}
  ]
}
```

Iteration rules:

- Maximum 5 iterations per Satirist/Co-Satirist exchange
- Claude (as panelist or aggregator) has final say via the three-part Final Say
  Protocol: (1) acknowledge the objection, (2) state override rationale, (3)
  produce a synthesis incorporating all feedback
- Gemini (as Co-Satirist or critic) cannot force rejection past iteration 5
- The ParallelPanel topology (Claude + Grok + Gemini as independent panelists;
  Claude as aggregator) is the current Satirist implementation

### §7 — Language Rule

- The output language is specified in the strategy brief (`output_language` field)
- ALL text visible in the generated cartoon — captions, chalkboard heading, board
  text, title overlay — MUST be in the output language
- No English leakage when the output language is not English
- The Co-Satirist (Gemini) performs a language check on every iteration; English
  leakage causes `approved = False` regardless of other feedback

### §8 — Project Structure

Approved source directories (additive changes only within these):

```
agents/        — agent implementations and data types
core/          — runner, CLI, config loader, bundle writer, utilities
llm/           — LLM provider abstraction, conversation protocols
tests/         — pytest test suite (mirrors source structure)
specs/         — per-stage Speckit artifacts (committed to git)
.specify/      — Speckit governance (constitution, templates)
```

Rules:

- No new top-level directories without a constitution amendment
- No new packages inside `agents/`, `core/`, or `llm/` without a plan.md entry
  in the Project Structure section
- All changes must be additive; existing public interfaces are not broken without
  explicit deprecation and approval

### §9 — Testing Rules

- Test framework: `pytest` with `unittest.mock`
- ALL SDK and API calls must be mocked in tests; zero real API calls during test
  runs
- Tests are written BEFORE the corresponding implementation (TDD); test tasks
  appear before implementation tasks in every `tasks.md`
- Every test function MUST have a plain-English comment at its top (one sentence)
  explaining what the test checks and why it matters (RULE 3 in CLAUDE.md)
- `python -m pytest tests/` must pass with zero failures before any stage is
  considered complete

### §10 — Secrets and Security

- API keys are loaded exclusively from environment variables:
  `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROK_API_KEY`, `NEWSAPI_KEY`
- Load via `source set_gata.sh` (RULE 16 in CLAUDE.md)
- API keys are NEVER hardcoded in source files, test files, or configuration files
- `set_gata.sh` and any `.env` files are gitignored
- `output/` directory (generated images) is gitignored

### §11 — Development Stages

- Stages are numbered with a 3-digit prefix: `001`, `002`, … `027`, `028`, …
- Each stage lives on its own git branch named `NNN-feature-slug`
- No stage work on `main`; all stage work merges via pull request
- Stages are sequential; work on stage N+1 does not begin until stage N is merged
  to `main`
- Completed stages (001–027) are fully merged into `main` as of 2026-06-22
- Next stage: `028-*` (name agreed at start of stage)

### §12 — Code Quality

- `ruff check .` must exit 0 before any task is marked complete
- `ruff format .` must be run on all modified files before commit
- `ruff` configuration: `line-length = 88`, `target-version = "py310"` (defined
  in `pyproject.toml`)
- No bare `print()` calls in `agents/`, `core/`, or `llm/`; use the `logging`
  module

### §13 — Logging

- `logger = logging.getLogger(__name__)` at the top of every agent module
- Log severity levels: `DEBUG` for per-call detail, `INFO` for phase transitions,
  `WARNING` for recoverable failures, `ERROR` for unrecoverable failures
- Log messages include structured context: model name, iteration number, agent
  name as appropriate
- No bare `print()` in `agents/`, `core/`, or `llm/`; `print()` is permitted
  only in `pipeline.py` for user-facing progress output

---

## Amendment Record

| Version | Date | Principle | Change | Approved by |
|---------|------|-----------|--------|-------------|
| 1.0 | 2026-06-22 | All | Initial ratification | Jose Santos |
