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
) -> None:
    """Run the full pipeline for a single topic and write the output image."""
    agent0_log: ConversationLog | None = None
    bc_log: ConversationLog | None = None
    enriched_brief = None
    concept = None
    try:
        enriched_brief, agent0_log = agent_cultural_strategist.run(
            topic, seed_brief, news_brief=news_headline, humor=humor
        )
        concept, bc_log = agent_satirist.run(
            topic, enriched_brief, humor=humor, layout=layout
        )
        logger.info("creative loop complete — calling image generator")
        agent_image_generator.generate(
            concept, enriched_brief, output_path, layout=layout
        )
        logger.info("done: cartoon saved to %s", output_path)
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
        )
