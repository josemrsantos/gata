import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from core.newsletter_merge import NewsletterMergeError, merge_edition, write_output

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge a newsletter edition folder's numbered story sub-folders into"
            " one draft LinkedIn document for a human to review before"
            " publishing. Story order comes from each folder's leading number"
            " (e.g. 01_story-name) — not from timestamps or a guess."
        )
    )
    parser.add_argument(
        "edition_folder",
        help="edition folder containing numbered story sub-folders",
    )
    parser.add_argument(
        "--audience",
        default="uk",
        help="audience sub-folder name to read from each story (default: uk)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="output path (default: <edition_folder>/merged_linkedin_post.md)",
    )
    args = parser.parse_args()
    found_dotenv = load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    if found_dotenv:
        print("credentials loaded from .env file")
    else:
        print("no .env file found — reading credentials from environment variables")
    # FR-017: verify every credential the fallback chain might need before any
    # call is attempted, so a failure is never discovered mid-run.
    missing = [key for key in _REQUIRED_KEYS if not os.getenv(key)]
    if missing:
        logger.error("missing required credentials: %s", ", ".join(missing))
        sys.exit(1)
    edition_dir = Path(args.edition_folder)
    output_path = (
        Path(args.output) if args.output else edition_dir / "merged_linkedin_post.md"
    )
    try:
        merged_text = merge_edition(edition_dir, audience=args.audience)
    except (NewsletterMergeError, RuntimeError) as exc:
        logger.error("%s", exc)
        sys.exit(1)
    try:
        write_output(merged_text, output_path)
    except NewsletterMergeError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    print(f"\nMerged edition draft written to {output_path}")
    print("This is a draft — review and edit before publishing.")


if __name__ == "__main__":
    main()
