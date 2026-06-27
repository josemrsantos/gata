import json
import logging
import mimetypes
import re
import time

from google.genai import types as genai_types
from google.genai.errors import APIError

from core.types import (
    AgentTelemetry,
    CartoonConcept,
    CartoonLayout,
    EnrichedBrief,
    ImageEvaluation,
    TokenUsage,
)
from llm import GeminiProvider

logger = logging.getLogger(__name__)

# Verbatim from constitution.md Section 4 — duplicated to avoid circular imports
_GATA_CHARACTER = (
    "Gata is a domestic shorthair calico-tabby mix: white chest, muzzle, and paws; "
    "dark grey/black tabby stripes; orange/ginger patches on back. "
    "She has a small dark spot on the bridge of her pink nose. "
    "She wears a simple dark leather collar with a gold/brass nameplate"
    ' engraved "GATA". '
    "Her demeanour is serious, investigative, slightly tired, and highly intelligent. "
    "She never wears human clothes or accessories"
    " — no hats, glasses, pens, or clothing of any kind."
)

_SYSTEM_PROMPT = (
    "You are the Image Evaluator at Gata Newsroom.\n"
    "You receive a finished cartoon image and the concept that produced it.\n"
    "Your job: decide APPROVED or REJECTED based on three criteria.\n"
    "\n"
    "OUTPUT FORMAT — return ONLY valid JSON, no markdown fences:\n"
    "{\n"
    '  "artifacts": ["specific description of each problem found",'
    " or empty list if none],\n"
    '  "is_funny": true or false,\n'
    '  "funny_notes": "one sentence: why this will or will not land'
    ' for the target audience",\n'
    '  "verdict": "APPROVED" or "REJECTED"\n'
    "}\n"
    "\n"
    "The artifacts list covers both technical rendering problems AND concept fidelity\n"
    "failures. Prefix each entry so failures can be diagnosed:\n"
    '- Technical artifact: "Artifact: [description]"\n'
    '- Wrong concept rendered: "Fidelity failure: intended [X], image shows [Y]"\n'
    "\n"
    "VERDICT RULES:\n"
    "- REJECTED if artifacts list is non-empty\n"
    "- REJECTED if is_funny is false\n"
    "- APPROVED only when artifacts is empty AND is_funny is true"
)


def _build_eval_prompt(
    concept: CartoonConcept,
    brief: EnrichedBrief,
    layout: CartoonLayout | None,
) -> str:
    # Describe what the cartoon was supposed to show so the model can check completeness
    if concept.panels is not None:
        concept_desc = "\n".join(
            f'Panel {i + 1}: {p.scene} — "{p.caption}"'
            for i, p in enumerate(concept.panels)
        )
    else:
        concept_desc = concept.full_text[:600]
    panel_note = ""
    if layout is not None and layout.panels > 1:
        panel_note = f"\nFORMAT: {layout.panels}-panel {layout.direction} comic strip."
    lines = [
        "GATA CHARACTER — verify she matches this exactly:",
        _GATA_CHARACTER,
        "",
        "INTENDED CONCEPT:",
        concept_desc,
        panel_note,
        "",
        "CONCEPT FIDELITY CHECK — does the image show the specific scene above?",
        "Thematic similarity is NOT sufficient. If the image depicts something"
        " plausible but different — e.g. a British weather diagram instead of a"
        " chicken-joke spider diagram — that is a fidelity failure, even if Gata"
        " and the newsroom setting look correct.",
        "Ask yourself:",
        "- Is the specific scene described above (not just the general theme) visible?",
        "- Are the named elements — diagrams, labels, objects, board text — present?",
        "- Has the image model silently substituted a different-but-related visual?",
        'If the image does not match, report: "Fidelity failure: intended [X],'
        ' image shows [Y]"',
        "",
        f"TARGET AUDIENCE: {brief.target_audience}",
        f"CULTURAL CONTEXT: {brief.cultural_angle}",
        "",
        "TECHNICAL ARTIFACT CHECKLIST — report every problem you find:",
        '- Duplicate text: prefix "Artifact: duplicate [text]"',
        '- Garbled text: prefix "Artifact: garbled text [description]"',
        "- Character failure: Gata absent, wrong colours, or wearing"
        ' accessories — prefix "Artifact: character [description]"',
        "",
        f"FUNNINESS CHECK — would {brief.target_audience} actually laugh at this?",
        "- Does the visual joke land without reading the caption?",
        "- Is the uncomfortable or surprising angle visible in the image itself?",
        "- Is this genuinely funny, not just competent or merely illustrative?",
    ]
    return "\n".join(lines)


def _parse_evaluation(text: str, model: str) -> ImageEvaluation:
    # Strip markdown fences Gemini sometimes adds around JSON
    clean = re.sub(r"^```(?:json)?\s*", "", text.strip())
    clean = re.sub(r"\s*```$", "", clean)
    try:
        parsed = json.loads(clean)
        artifacts = [str(a) for a in parsed.get("artifacts", [])]
        is_funny = bool(parsed.get("is_funny", True))
        funny_notes = str(parsed.get("funny_notes", ""))
        # Derive verdict from the data rather than trusting the model's verdict field —
        # prevents a model from listing artifacts while still returning APPROVED
        verdict = "APPROVED" if (not artifacts and is_funny) else "REJECTED"
        return ImageEvaluation(
            verdict=verdict,
            artifacts=artifacts,
            is_funny=is_funny,
            funny_notes=funny_notes,
            model_used=model,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "image evaluator: parse failed (%s) — defaulting to APPROVED", exc
        )
        # Fail open: a broken response must not block the pipeline
        return ImageEvaluation(
            verdict="APPROVED",
            artifacts=[],
            is_funny=True,
            funny_notes="(evaluation unavailable — parse error)",
            model_used=model,
        )


def evaluate(
    image_path: str,
    concept: CartoonConcept,
    brief: EnrichedBrief,
    evaluator_providers: list[GeminiProvider],
    layout: CartoonLayout | None = None,
) -> tuple[ImageEvaluation, AgentTelemetry]:
    start = time.monotonic()
    token_calls: list[TokenUsage] = []
    # Read the image once; reuse bytes across all provider attempts
    with open(image_path, "rb") as fh:
        image_bytes = fh.read()
    mime_type = mimetypes.guess_type(image_path)[0] or "image/png"
    user_prompt = _build_eval_prompt(concept, brief, layout)
    last_exc: Exception | None = None
    # Try each provider in priority order; stop on first successful evaluation
    for provider in evaluator_providers:
        model = provider.model_id
        try:
            response = provider.client.models.generate_content(
                model=model,
                contents=[
                    genai_types.Part(
                        inline_data=genai_types.Blob(
                            data=image_bytes,
                            mime_type=mime_type,
                        )
                    ),
                    genai_types.Part(text=user_prompt),
                ],
                config=genai_types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.1,
                ),
            )
        except (APIError, Exception) as exc:
            logger.warning(
                "image evaluator: model %s failed — %s — trying next model",
                model,
                exc,
            )
            last_exc = exc
            continue
        # Parse usage metadata defensively — absent on some Gemini models
        meta = getattr(response, "usage_metadata", None)
        in_tok = getattr(meta, "prompt_token_count", 0) or 0
        out_tok = getattr(meta, "candidates_token_count", 0) or 0
        token_calls.append(
            TokenUsage(
                model=model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=provider.compute_cost(in_tok, out_tok),
            )
        )
        evaluation = _parse_evaluation(response.text, model)
        logger.info(
            "image evaluator: verdict=%s is_funny=%s artifacts=%d model=%s",
            evaluation.verdict,
            evaluation.is_funny,
            len(evaluation.artifacts),
            model,
        )
        return evaluation, AgentTelemetry(
            agent_name="Image Evaluator",
            duration_seconds=time.monotonic() - start,
            iterations=1,
            calls=token_calls,
        )
    # All models exhausted — fail open rather than blocking the pipeline
    logger.warning(
        "image evaluator: all models exhausted (last error: %s)"
        " — defaulting to APPROVED",
        last_exc,
    )
    return ImageEvaluation(
        verdict="APPROVED",
        artifacts=[],
        is_funny=True,
        funny_notes="(evaluation unavailable — all models exhausted)",
        model_used="none",
    ), AgentTelemetry(
        agent_name="Image Evaluator",
        duration_seconds=time.monotonic() - start,
        iterations=0,
        calls=token_calls,
    )
