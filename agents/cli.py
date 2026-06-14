import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from google.genai.errors import APIError as GeminiAPIError

from agents.agent_cultural_strategist import infer_audiences
from agents.config_loader import load_humor_config, sanitize_path_segment
from agents.runner import run_pipeline
from agents.types import AudienceProfile, StrategyBrief

logger = logging.getLogger(__name__)

_UK_AUDIENCE = AudienceProfile(
    name="uk",
    audience="UK public",
    language="English",
    tone="dry British wit",
)


def _ensure_uk(profiles: list[AudienceProfile]) -> list[AudienceProfile]:
    # UK is always included — check name and audience description case-insensitively
    _uk_terms = {"uk", "british", "united kingdom"}
    for p in profiles:
        combined = (p.name + " " + p.audience).lower()
        if any(term in combined for term in _uk_terms):
            return profiles
    return profiles + [_UK_AUDIENCE]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate satirical cartoons for topic-relevant audiences"
            " from a single topic."
        )
    )
    parser.add_argument(
        "topic",
        help="topic to satirise, e.g. 'World Cup Qatar vs Swiss'",
    )
    args = parser.parse_args()
    # Reject blank topics immediately before any setup
    if not args.topic.strip():
        print("error: topic must not be empty", file=sys.stderr)
        sys.exit(1)
    # Load .env from the caller's cwd if present, then configure logging
    found_dotenv = load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    if found_dotenv:
        logger.info("credentials loaded from .env file")
    else:
        logger.info(
            "no .env file found — reading credentials from environment variables"
        )
    # Verify API keys before any network call
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY is not set")
        sys.exit(1)
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY is not set")
        sys.exit(1)
    # humor.yaml is optional — look in the caller's cwd
    humor = None
    if os.path.exists("humor.yaml"):
        try:
            humor = load_humor_config("humor.yaml")
            if humor:
                logger.info("humor config loaded from humor.yaml")
        except ValueError as exc:
            logger.error("humor config error: %s", exc)
            sys.exit(1)
    # Infer audiences from the topic, then guarantee UK is always present
    audiences = _ensure_uk(infer_audiences(args.topic))
    logger.info(
        "audiences: %s",
        ", ".join(f"{a.name}({a.language})" for a in audiences),
    )
    # Output folder: subdirectory of cwd named after the sanitized topic
    topic_slug = sanitize_path_segment(args.topic)
    output_dir = os.path.join(os.getcwd(), topic_slug)
    os.makedirs(output_dir, exist_ok=True)
    # Run the pipeline once per audience; log each failure and continue
    failures = 0
    for audience in audiences:
        seed_brief = StrategyBrief(
            target_audience=audience.audience,
            output_language=audience.language,
            tone=audience.tone,
        )
        output_path = os.path.join(output_dir, f"{audience.name}.png")
        logger.info(
            "generating for audience=%r language=%r output=%r",
            audience.audience,
            audience.language,
            output_path,
        )
        try:
            run_pipeline(args.topic, seed_brief, output_path, humor=humor)
        except (TimeoutError, ValueError, RuntimeError, OSError, GeminiAPIError) as exc:
            logger.error("failed for audience %r: %s", audience.name, exc)
            failures += 1
    # Report overall result; partial success still produces useful output
    if failures == 0:
        logger.info("all %d images saved to %s", len(audiences), output_dir)
    elif failures < len(audiences):
        logger.warning(
            "%d/%d audiences failed — partial output in %s",
            failures,
            len(audiences),
            output_dir,
        )
        sys.exit(1)
    else:
        logger.error("all audiences failed — no output produced")
        sys.exit(1)
