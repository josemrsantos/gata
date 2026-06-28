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
    EnrichedBrief,
    Headline,
    HumorConfig,
    ModelSpec,
    ProvidersConfig,
    RunTelemetry,
    StrategyBrief,
)
from llm import ClaudeProvider, GeminiProvider, GrokProvider
from llm.base import LLMProvider

logger = logging.getLogger(__name__)


def _build_provider(spec: ModelSpec) -> LLMProvider:
    """Instantiate the correct LLMProvider from a ModelSpec."""
    if spec.provider == "claude":
        return ClaudeProvider(spec.model)
    if spec.provider == "gemini":
        return GeminiProvider(spec.model)
    if spec.provider == "grok":
        return GrokProvider(spec.model)
    raise ValueError(f"unknown provider: {spec.provider!r}")


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
_PARALLEL_PANELISTS = [
    ClaudeProvider("claude-sonnet-4-6"),
    GrokProvider("grok-3-mini"),
    GeminiProvider("gemini-2.5-flash"),
]
_GROK_AGGREGATOR = [GrokProvider("grok-3")]
_GEMINI_EVAL_CHAIN = _GEMINI_PRO_CHAIN  # same model priority as evaluator chain


def run_pipeline(
    topic: str,
    seed_brief: StrategyBrief,
    output_path: str,
    news_headline: Headline | None = None,
    humor: HumorConfig | None = None,
    layout: CartoonLayout | None = None,
    include_html: bool = False,
    show_title: bool = True,
    providers_config: ProvidersConfig | None = None,
    skip_cultural_strategist: bool = False,
) -> RunTelemetry:
    """Run the full pipeline for a single topic and write the output image."""
    # Build provider lists from config when supplied; otherwise wrap hardcoded defaults
    # in single-element lists so each slot has the same list[list[LLMProvider]] shape.
    if providers_config is not None:
        panelist_providers: list[list[LLMProvider]] = [
            [_build_provider(s) for s in slot] for slot in providers_config.panelists
        ]
        aggregator_providers: list[LLMProvider] = [
            _build_provider(s) for s in providers_config.aggregator
        ]
    else:
        panelist_providers = [[p] for p in _PARALLEL_PANELISTS]
        aggregator_providers = _GROK_AGGREGATOR

    agent0_log: ConversationLog | None = None
    bc_log: ConversationLog | None = None
    enriched_brief = None
    concept = None
    telemetry = RunTelemetry()
    try:
        if skip_cultural_strategist:
            # Direct mode: build a minimal brief from the seed so the Satirist has
            # audience/language/tone context without paying Cultural Strategist cost.
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
            enriched_brief, agent0_log, agent0_tel = agent_cultural_strategist.run(
                topic,
                seed_brief,
                panelist_providers=panelist_providers,
                aggregator_providers=aggregator_providers,
                news_brief=news_headline,
                humor=humor,
            )
            telemetry.agents.append(agent0_tel)
        print("  Satirist/Co-Satirist...", flush=True)
        concept, bc_log, bc_tel, chosen_layout = agent_satirist.run(
            topic,
            enriched_brief,
            panelist_providers=panelist_providers,
            aggregator_providers=aggregator_providers,
            humor=humor,
            layout_override=layout,
        )
        telemetry.agents.append(bc_tel)
        print("  Image Generator...", flush=True)
        _MAX_IMAGE_RETRIES = 2
        for _attempt in range(_MAX_IMAGE_RETRIES + 1):
            _image_path, image_tel = agent_image_generator.generate(
                concept,
                enriched_brief,
                output_path,
                layout=chosen_layout,
                show_title=show_title,
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
                    "image evaluator: REJECTED after %d attempt(s) — using last image",
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
            panelist_providers=panelist_providers,
            aggregator_providers=aggregator_providers,
        )
        print(bundle_writer.format_summary(telemetry))
    return telemetry
