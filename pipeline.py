import argparse
import logging
import os
import random
import sys

from dotenv import load_dotenv
from google.genai.errors import APIError as GeminiAPIError

from agents import trend_scout
from core.config_loader import (
    load_communities,
    load_humor_config,
    sanitize_path_segment,
)
from core.runner import run_pipeline
from core.types import CartoonLayout, StrategyBrief

logger = logging.getLogger(__name__)


def _panel_filename_prefix(layout: CartoonLayout | None) -> str:
    # Returns e.g. "3h_" for explicit 3-panel horizontal, "" otherwise (auto or 1).
    if layout is None or layout.panels <= 1:
        return ""
    direction_char = "h" if layout.direction == "horizontal" else "v"
    return f"{layout.panels}{direction_char}_"


def _resolve_layout(args, community=None) -> CartoonLayout | None:
    # CLI flag takes precedence; fall back to community config if present
    if args.panels <= 1:
        if community is not None and community.panels > 1:
            return CartoonLayout(panels=community.panels, direction=community.layout)
        return None
    return CartoonLayout(panels=args.panels, direction=args.layout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gata Newsroom cartoon pipeline")
    parser.add_argument("--community", metavar="NAME", help="community name to run for")
    parser.add_argument("--topic", help="topic for manual mode")
    parser.add_argument("--audience", help="target audience for manual mode")
    parser.add_argument("--language", help="output language for manual mode")
    parser.add_argument("--tone", help="tone for manual mode")
    parser.add_argument(
        "--panels", type=int, default=1, metavar="N",
        help="number of panels 1-4 (default 1)"
    )
    parser.add_argument(
        "--layout", default='horizontal', metavar="DIR",
        help="panel direction: horizontal or vertical (default horizontal)"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="also generate explanation.html and deep_dive_en.html (default off)",
    )
    parser.add_argument(
        "--no-title",
        action="store_true",
        help="suppress title banner on generated images (default: title shown)",
    )
    args = parser.parse_args()
    # Reject an empty --community immediately — blank string is not a valid description
    if args.community is not None and not args.community.strip():
        logger.error("--community must not be empty")
        sys.exit(1)
    # Validate panel count and layout direction before any API call (FR-010)
    if args.panels is not None and not (1 <= args.panels <= 4):
        logger.error("--panels must be between 1 and 4")
        sys.exit(1)
    if args.layout is not None and args.layout not in ("horizontal", "vertical"):
        logger.error("--layout must be 'horizontal' or 'vertical'")
        sys.exit(1)
    # Logging and env vars must be initialised before any config load can emit errors
    found_dotenv = load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    # Silence SDK HTTP noise — operators want agent-level output, not socket events
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("google.genai").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    # Explicit source log lets operators know which credential path is active
    if found_dotenv:
        logger.info("credentials loaded from .env file")
    else:
        logger.info(
            "no .env file found — reading credentials from environment variables"
        )
    # humor.yaml is optional — absent means no comedy directives are injected
    try:
        humor = load_humor_config("humor.yaml")
    except ValueError as exc:
        logger.error("humor config error: %s", exc)
        sys.exit(1)
    if humor:
        logger.info("humor config loaded from humor.yaml")
    # Determine which mode the caller intended before applying constraints
    has_topic = args.topic is not None
    ctx_flags = (args.audience, args.language, args.tone)
    has_context = any(v is not None for v in ctx_flags)
    has_all_context = all(v is not None for v in ctx_flags)
    # --community+topic is new; audience/language/tone always conflict with --community
    community_topic_mode = bool(args.community and has_topic and not has_context)
    # --community + explicit context flags: community infers the brief, flags conflict
    if args.community and has_context:
        logger.error(
            "--community and context flags "
            "(--audience, --language, --tone) are mutually exclusive"
        )
        sys.exit(1)
    # Context flags without topic leave StrategyBrief incomplete
    if has_context and not has_topic:
        logger.error(
            "--audience, --language, --tone require --topic to form a complete brief"
        )
        sys.exit(1)
    # --topic alone (no community) requires all context flags to build a full brief
    if has_topic and not args.community and not has_all_context:
        logger.error(
            "manual mode requires all four flags: "
            "--topic, --audience, --language, --tone"
        )
        sys.exit(1)
    # Both LLM providers required; verify credentials before any network call
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not anthropic_key:
        logger.error("ANTHROPIC_API_KEY is not set — cannot start pipeline")
        sys.exit(1)
    if not gemini_key:
        logger.error("GEMINI_API_KEY is not set — cannot start pipeline")
        sys.exit(1)
    # All preflight checks passed — branch into the appropriate mode
    if has_topic and not args.community:
        # Full manual mode: all four context flags supplied by the caller
        topic = args.topic
        seed_brief = StrategyBrief(
            target_audience=args.audience,
            output_language=args.language,
            tone=args.tone,
        )
        layout = _resolve_layout(args)
        prefix = _panel_filename_prefix(layout)
        output_path = (
            f"output/manual/{prefix}{sanitize_path_segment(args.language)}"
            f"_{sanitize_path_segment(topic)}.png"
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        logger.info("manual mode: topic=%r, output=%r", topic, output_path)
        try:
            run_pipeline(
                topic, seed_brief, output_path, humor=humor, layout=layout,
                include_html=args.html, show_title=not args.no_title,
            )
        except (TimeoutError, ValueError, RuntimeError, OSError, GeminiAPIError) as exc:
            logger.error("pipeline failed: %s", exc)
            sys.exit(1)
    elif community_topic_mode:
        # Community + topic mode: brief inferred from community, topic supplied directly
        communities = []
        if os.path.exists("communities.yaml"):
            try:
                communities = load_communities("communities.yaml")
            except ValueError as exc:
                logger.error("config error: %s", exc)
                sys.exit(1)
        community = next((c for c in communities if c.name == args.community), None)
        topic = args.topic
        if community is not None:
            # Named community: use its pre-configured brief without inference
            seed_brief = community.to_brief()
            folder = sanitize_path_segment(community.name)
        else:
            # Free-text community: infer brief from description, skip Trend Scout
            seed_brief = trend_scout.infer_brief_from_description(args.community)
            folder = sanitize_path_segment(args.community)
        layout = _resolve_layout(args)
        prefix = _panel_filename_prefix(layout)
        output_path = (
            f"output/{folder}"
            f"/{prefix}{sanitize_path_segment(seed_brief.output_language)}"
            f"_{sanitize_path_segment(topic)}.png"
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        logger.info(
            "community-topic mode: community=%r topic=%r output=%r",
            args.community,
            topic,
            output_path,
        )
        try:
            run_pipeline(
                topic, seed_brief, output_path, humor=humor, layout=layout,
                include_html=args.html, show_title=not args.no_title,
            )
        except (TimeoutError, ValueError, RuntimeError, OSError, GeminiAPIError) as exc:
            logger.error("pipeline failed: %s", exc)
            sys.exit(1)
    elif args.community:
        # communities.yaml may not exist — treat absence as valid (no named communities)
        # and fall through to free-text inference if no exact name match is found
        communities = []
        if os.path.exists("communities.yaml"):
            try:
                communities = load_communities("communities.yaml")
            except ValueError as exc:
                logger.error("config error: %s", exc)
                sys.exit(1)
        # Exact name match → use configured brief and Trend Scout for this community
        community = next((c for c in communities if c.name == args.community), None)
        if community is not None:
            logger.info(
                "pipeline: %r matched in communities.yaml — using named-community path",
                args.community,
            )
            headlines, topic_source = trend_scout.get_topics(community)
            if not headlines:
                logger.error(
                    "no topics available for %r — add seed topics or news_sources",
                    community.name,
                )
                sys.exit(1)
            headline = headlines[0]
            topic = headline.title
            logger.info(
                "community=%r topic source=%s topic=%r",
                community.name,
                topic_source,
                topic,
            )
            seed_brief = community.to_brief()
            layout = _resolve_layout(args, community=community)
            prefix = _panel_filename_prefix(layout)
            output_path = (
                f"output/{sanitize_path_segment(community.name)}"
                f"/{prefix}{sanitize_path_segment(community.output_language)}"
                f"_{sanitize_path_segment(topic)}.png"
            )
        else:
            # No exact match → treat description as free-text; infer brief via Gemini
            logger.info(
                "pipeline: %r not found in communities.yaml"
                " — using free-text inference",
                args.community,
            )
            free_text = trend_scout.get_topics_for_description(args.community)
            headlines, seed_brief, topic_source = free_text
            if not headlines:
                logger.error(
                    "no topics available for community: %r", args.community
                )
                sys.exit(1)
            headline = headlines[0]
            topic = headline.title
            logger.info(
                "community=%r topic source=%s topic=%r",
                args.community,
                topic_source,
                topic,
            )
            # Free-text has no community object — CLI flags or global defaults only
            layout = _resolve_layout(args)
            prefix = _panel_filename_prefix(layout)
            output_path = (
                f"output/{sanitize_path_segment(args.community)}"
                f"/{prefix}{sanitize_path_segment(seed_brief.output_language)}"
                f"_{sanitize_path_segment(topic)}.png"
            )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        logger.info(
            "community=%r, topic=%r, output=%r", args.community, topic, output_path
        )
        try:
            run_pipeline(
                topic, seed_brief, output_path, news_headline=headline, humor=humor,
                layout=layout, include_html=args.html, show_title=not args.no_title,
            )
        except (TimeoutError, ValueError, RuntimeError, OSError, GeminiAPIError) as exc:
            logger.error("pipeline failed: %s", exc)
            sys.exit(1)
    else:
        try:
            communities = load_communities("communities.yaml")
        except ValueError as exc:
            logger.error("config error: %s", exc)
            sys.exit(1)
        # Full community list loaded; pick one at random for the unattended daily run
        community = random.choice(communities)
        headlines, topic_source = trend_scout.get_topics(community)
        if not headlines:
            logger.error(
                "no topics available for %r — add seed topics or news_sources",
                community.name,
            )
            sys.exit(1)
        headline = headlines[0]
        topic = headline.title
        logger.info(
            "community=%r topic source=%s topic=%r", community.name, topic_source, topic
        )
        seed_brief = community.to_brief()
        layout = _resolve_layout(args, community=community)
        prefix = _panel_filename_prefix(layout)
        output_path = (
            f"output/{sanitize_path_segment(community.name)}"
            f"/{prefix}{sanitize_path_segment(community.output_language)}"
            f"_{sanitize_path_segment(topic)}.png"
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        logger.info(
            "community=%r, topic=%r, output=%r",
            community.name,
            topic,
            output_path,
        )
        try:
            run_pipeline(
                topic, seed_brief, output_path, news_headline=headline, humor=humor,
                layout=layout, include_html=args.html, show_title=not args.no_title,
            )
        except (TimeoutError, ValueError, RuntimeError, OSError, GeminiAPIError) as exc:
            logger.error("pipeline failed: %s", exc)
            sys.exit(1)


if __name__ == "__main__":
    main()
