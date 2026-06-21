import logging

from google.genai.errors import APIError as GeminiAPIError

from agents import (
    agent_cultural_strategist,
    agent_image_evaluator,
    agent_image_generator,
    agent_satirist,
)
from core import bundle_writer
from core.types import (
    CartoonLayout,
    ConversationLog,
    Headline,
    HumorConfig,
    RunTelemetry,
    StrategyBrief,
)
from llm import ClaudeProvider, GeminiProvider, GrokProvider

logger = logging.getLogger(__name__)

# Provider chains created once; each chain tries models in priority order on failure.
_CLAUDE_CHAIN = [
    ClaudeProvider("claude-sonnet-4-6"),
    ClaudeProvider("claude-opus-4-7"),
    ClaudeProvider("claude-haiku-4-5-20251001"),
]
_GEMINI_PRO_CHAIN = [
    GeminiProvider("gemini-2.5-pro"),
    GeminiProvider("gemini-2.5-flash"),
    GeminiProvider("gemini-2.0-flash"),
]
_GROK_CO_SATIRIST_CHAIN = [
    GrokProvider("grok-3"),
    GeminiProvider("gemini-2.5-flash"),
    GeminiProvider("gemini-2.0-flash"),
]
_GEMINI_EVAL_CHAIN = _GEMINI_PRO_CHAIN  # same model priority as resonator chain


def run_pipeline(
    topic: str,
    seed_brief: StrategyBrief,
    output_path: str,
    news_headline: Headline | None = None,
    humor: HumorConfig | None = None,
    layout: CartoonLayout | None = None,
    include_html: bool = False,
) -> RunTelemetry:
    """Run the full pipeline for a single topic and write the output image."""
    agent0_log: ConversationLog | None = None
    bc_log: ConversationLog | None = None
    enriched_brief = None
    concept = None
    telemetry = RunTelemetry()
    try:
        print("  Cultural Strategist...", flush=True)
        enriched_brief, agent0_log, agent0_tel = agent_cultural_strategist.run(
            topic,
            seed_brief,
            framer_providers=_CLAUDE_CHAIN,
            resonator_providers=_GEMINI_PRO_CHAIN,
            news_brief=news_headline,
            humor=humor,
        )
        telemetry.agents.append(agent0_tel)
        print("  Satirist/Co-Satirist...", flush=True)
        concept, bc_log, bc_tel, chosen_layout = agent_satirist.run(
            topic,
            enriched_brief,
            satirist_providers=_CLAUDE_CHAIN,
            co_satirist_providers=_GROK_CO_SATIRIST_CHAIN,
            humor=humor,
            layout_override=layout,
        )
        telemetry.agents.append(bc_tel)
        print("  Image Generator...", flush=True)
        _MAX_IMAGE_RETRIES = 2
        for _attempt in range(_MAX_IMAGE_RETRIES + 1):
            _image_path, image_tel = agent_image_generator.generate(
                concept, enriched_brief, output_path, layout=chosen_layout
            )
            telemetry.agents.append(image_tel)
            print("  Image Evaluator...", flush=True)
            _eval_result, eval_tel = agent_image_evaluator.evaluate(
                _image_path,
                concept,
                enriched_brief,
                evaluator_providers=_GEMINI_EVAL_CHAIN,
                layout=chosen_layout,
            )
            telemetry.agents.append(eval_tel)
            if _eval_result.verdict == "APPROVED":
                break
            if _attempt < _MAX_IMAGE_RETRIES:
                logger.warning(
                    "image evaluator: REJECTED (attempt %d/%d)"
                    " artifacts=%r funny=%s — regenerating",
                    _attempt + 1,
                    _MAX_IMAGE_RETRIES + 1,
                    _eval_result.artifacts,
                    _eval_result.is_funny,
                )
            else:
                logger.warning(
                    "image evaluator: REJECTED after %d attempt(s)"
                    " — using last image",
                    _MAX_IMAGE_RETRIES + 1,
                )
    except (TimeoutError, ValueError, RuntimeError, OSError, GeminiAPIError) as exc:
        logger.error("pipeline failed: %s", exc)
        raise
    finally:
        if concept is not None:
            has_panels = concept.panels is not None
            image_prompt = concept.full_text if has_panels else concept.image_prompt
        else:
            image_prompt = None
        bundle_writer.write_bundle(
            output_path,
            agent0_log,
            bc_log,
            enriched_brief,
            image_prompt,
            telemetry=telemetry,
            include_html=include_html,
        )
        print(bundle_writer.format_summary(telemetry))
    return telemetry
