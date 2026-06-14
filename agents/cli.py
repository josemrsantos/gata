import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from google.genai.errors import APIError as GeminiAPIError

from agents.config_loader import load_humor_config, sanitize_path_segment
from agents.runner import run_pipeline
from agents.types import StrategyBrief

logger = logging.getLogger(__name__)

# One entry per target audience; each drives an independent pipeline run.
_AUDIENCES = [
    {
        "name": "swiss",
        "audience": "Swiss public",
        "language": "Swiss German",
        "tone": "dry Swiss wit",
    },
    {
        "name": "qatar",
        "audience": "Qatari public",
        "language": "Arabic",
        "tone": "Gulf Arabic satire",
    },
    {
        "name": "global",
        "audience": "global English-speaking public",
        "language": "English",
        "tone": "international wit",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate satirical cartoons for Swiss, Qatari, and global audiences "
            "from a single topic."
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
    # Output folder: subdirectory of cwd named after the sanitized topic
    topic_slug = sanitize_path_segment(args.topic)
    output_dir = os.path.join(os.getcwd(), topic_slug)
    os.makedirs(output_dir, exist_ok=True)
    # Run the pipeline once per audience; log each failure and continue
    failures = 0
    for audience in _AUDIENCES:
        seed_brief = StrategyBrief(
            target_audience=audience["audience"],
            output_language=audience["language"],
            tone=audience["tone"],
        )
        output_path = os.path.join(output_dir, f"{audience['name']}.png")
        logger.info(
            "generating for audience=%r language=%r output=%r",
            audience["audience"],
            audience["language"],
            output_path,
        )
        try:
            run_pipeline(args.topic, seed_brief, output_path, humor=humor)
        except (TimeoutError, ValueError, RuntimeError, OSError, GeminiAPIError) as exc:
            logger.error("failed for audience %r: %s", audience["name"], exc)
            failures += 1
    # Report overall result; partial success still produces useful output
    if failures == 0:
        logger.info("all 3 images saved to %s", output_dir)
    elif failures < len(_AUDIENCES):
        logger.warning(
            "%d/%d audiences failed — partial output in %s",
            failures,
            len(_AUDIENCES),
            output_dir,
        )
        sys.exit(1)
    else:
        logger.error("all audiences failed — no output produced")
        sys.exit(1)
