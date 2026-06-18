import logging

from google.genai.errors import APIError as GeminiAPIError

from agents import (
    agent_cultural_strategist,
    agent_image_generator,
    agent_satirist,
    bundle_writer,
)
from agents.types import (
    CartoonLayout,
    ConversationLog,
    Headline,
    HumorConfig,
    RunTelemetry,
    StrategyBrief,
)

logger = logging.getLogger(__name__)


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
            topic, seed_brief, news_brief=news_headline, humor=humor
        )
        telemetry.agents.append(agent0_tel)
        print("  Satirist/Critic...", flush=True)
        concept, bc_log, bc_tel = agent_satirist.run(
            topic, enriched_brief, humor=humor, layout=layout
        )
        telemetry.agents.append(bc_tel)
        print("  Image Generator...", flush=True)
        _image_path, image_tel = agent_image_generator.generate(
            concept, enriched_brief, output_path, layout=layout
        )
        telemetry.agents.append(image_tel)
    except (TimeoutError, ValueError, RuntimeError, OSError, GeminiAPIError) as exc:
        logger.error("pipeline failed: %s", exc)
        raise
    finally:
        # multi-panel: full_text is the JSON verdict
        # single-panel: full_text equals image_prompt
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
