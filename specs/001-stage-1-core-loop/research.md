# Research: Stage 1 Core Loop

**Branch**: `001-stage-1-core-loop` | **Date**: 2026-04-25

All technical decisions for Stage 1 are resolved — the constitution (`.specify/memory/constitution.md`) is prescriptive
on every key choice. This document records each decision, its rationale, and any alternatives considered.

---

## Decision 1: Claude SDK and model

**Decision**: Use `import anthropic`; model string `claude-sonnet-4-6`; `client.messages.create()`

**Rationale**: Mandated by Constitution Principle 1. The `anthropic` package is the only acceptable client for Claude
calls. `claude-sonnet-4-6` is the project-wide locked model string.

**Alternatives considered**: None permitted — any deviation is a blocking constitution violation.

**Temperature**: `temperature=0.8` — deliberately high to encourage creative leaps, unexpected satirical angles, and
risk-taking with wordplay. The Satirist is meant to surprise; variance is a feature, not a bug.

**Implementation note**: Agent B calls `messages.create` with `temperature=0.8`, a system prompt containing Gata's
character rules, visual style rules, and the strategy brief, and a user message containing the current news topic and (
on iterations > 1) the previous critique.

---

## Decision 2: Google Gemini SDK and models

**Decision**: Use `from google import genai`; `gemini-3.1-flash-image-preview` for image generation (Agent D);
`gemini-2.5-flash` for text-only critique (Agent C)

**Rationale**: Mandated by Constitution Principle 1. The legacy `google-generativeai` library is explicitly forbidden.

**Alternatives considered**: None permitted.

**Temperature — image generation**: Temperature is not applicable to `gemini-3.1-flash-image-preview` image-generation
calls; the model does not expose a configurable temperature parameter for this modality.

**Temperature — text critique**: `temperature=0.2` — deliberately low to keep the Critic's quality assessments
consistent and analytical across all iterations. The Critic must apply the same standard on iteration 4 as on iteration
1; creative drift in the Critic undermines the negotiation dynamic.

**Implementation note — image generation**:
`client.models.generate_content(model="gemini-3.1-flash-image-preview", ...)`. Response is binary; extraction pattern is
fixed by Constitution Principle 2 (see Decision 4).

**Implementation note — text critique**:
`client.models.generate_content(model="gemini-2.5-flash", contents=..., config=GenerateContentConfig(temperature=0.2))`.
Returns plain text feedback and an approval verdict.

---

## Decision 3: XML contract for image prompt handoff

**Decision**: Agent B (Satirist) wraps the image prompt in `<image_prompt>…</image_prompt>`. Orchestrator extracts it
via `re.search(r'<image_prompt>(.*?)</image_prompt>', text, re.DOTALL)`. Missing or malformed tag → retry the Satirist
call (not skip).

**Rationale**: Mandated by Constitution Principle 3. Deterministic regex extraction decouples the prose response from
the image-generation input, preventing prompt bleed-through.

**Alternatives considered**: None — the constitution explicitly mandates XML tags (Principle 3).

**Retry scope**: The up-to-3-attempt retry when XML tags are missing or malformed does NOT increment the iteration counter. The iteration counter only advances after a valid `CartoonConcept` has been produced and evaluated by the Critic. The retry is a technical recovery mechanism, invisible to the loop logic.

**Retry exhaustion**: When all 3 attempts are exhausted without a valid XML response, the pipeline exits with a clear error message and exit code 1. No partial output is written. Using the last malformed response as a fallback concept is explicitly deferred to Stage 4 (error handling); in Stage 1 a developer is always present and a clean failure is preferable to silent degradation.

**Planned extension (Stage 4)**: The Satirist will also be instructed to produce a
`<joke_explanation>` block in its final response. The orchestrator will parse this with the
same regex pattern and save it to `output/logs/{timestamp}_explanation.md`. No additional API
call is required — the explanation emerges from the negotiation already completed. This tag is
defined in the constitution but not implemented until Stage 4.

---

## Decision 4: Image binary extraction

**Decision**: Iterate `response.candidates[0].content.parts`; write `part.inline_data.data` to
`output/cartoon_output.png` in binary mode. Write only after all bytes are received — never stream partial writes to the
final filename.

**Rationale**: Mandated by Constitution Principle 2. Gemini returns binary data, never a URL.

**Alternatives considered**: None — URL-based extraction is an explicit constitution violation.

**Safe write pattern**: Write to a temp file first, then `os.replace(tmp, final)` to ensure the output file is either
complete or absent.

---

## Decision 5: Dual-persona iteration loop

**Decision**: B/C loop runs in `agent_bc.py`. Loop counter starts at 1 and caps at 5. Each iteration: (1) Satirist
generates concept + XML-wrapped image prompt; (2) Critic returns structured feedback + `approved: bool`. If
`approved=True` before iteration 5, exit immediately. At iteration 5, always exit and pass the latest concept downstream
regardless of Critic verdict (Claude has final say per Principle 6).

**Rationale**: Constitution Principle 6 — max 5 iterations, measurable progress, Claude final say, cartoon always
generated.

**Measurable progress rule**: The Critic MUST reference a specific change between the previous and current concept. A
critique that merely restates general standards without acknowledging iteration delta is invalid and the loop MUST
request a new critique.

**Final Say Protocol (iteration 5)**: When the loop reaches iteration 5, the Satirist prompt MUST include all three of
the following explicit instructions:

1. **Acknowledge the objection** — Summarise Gemini's last critique in one sentence, directly quoting the core concern (
   e.g., "Gemini flagged that the punchline relies on untranslatable English wordplay").
2. **State the override rationale** — Explain in one sentence why the satirical payoff justifies overruling that
   objection (e.g., "The visual gag works without the wordplay and lands harder in the target language").
3. **Produce a synthesis** — Generate a concept that demonstrably incorporates the iterative feedback accumulated across
   all previous rounds; the output MUST NOT be a copy or near-copy of the iteration 1 proposal. If the Satirist's final
   concept is found to be substantially identical to the first proposal, the pipeline MUST log a warning (but still
   proceed — a cartoon is always generated).

This ensures the Final Say is a reasoned creative decision, not a silent revert to the original idea.

---

## Decision 6: Strategy brief structure

**Decision**: `StrategyBrief` is a simple Python dataclass with three string fields: `target_audience`,
`output_language`, `tone`. Validated at pipeline entry — any blank field raises `ValueError` before agents are invoked.

**Rationale**: Spec FR-002 and FR-003. The brief frames both the Satirist's system prompt and the Critic's evaluation
rubric.

**Language enforcement**: Agent C explicitly checks that no English text appears in the image prompt when
`output_language` is not English (Constitution Principle 7).

---

## Decision 7: Secrets loading

**Decision**: `python-dotenv` loads `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` from `.env` at process start in
`pipeline.py`. Both keys are validated before any agent is instantiated.

**Rationale**: Constitution Principle 10 — no hardcoded keys; `.env` gitignored.

---

## Decision 8: Testing approach

**Decision**: All Anthropic and Gemini SDK calls are mocked using `unittest.mock.patch`. Tests are written before
implementation code. Three test files: `test_agent_bc.py`, `test_agent_d.py`, `test_pipeline.py`. XML parse logic and
`inline_data` extraction each have explicit unit tests.

**Rationale**: Constitution Principle 9 — test-first, no real API calls in tests.

**Key test cases to write before any implementation**:

- XML tag present → concept extracted correctly
- XML tag missing → retry triggered (not silent skip)
- `inline_data` present → binary written to temp then renamed
- `inline_data` absent → error raised, no partial file written
- Loop exits at iteration < 5 when `approved=True`
- Loop exits at iteration 5 regardless of approval
- Blank strategy brief field → `ValueError` before loop starts
- Language: non-English brief → English text in concept triggers Critic rejection
- All 3 XML retries exhausted → `RuntimeError` raised, pipeline exits code 1, no `output/cartoon_output.png` written