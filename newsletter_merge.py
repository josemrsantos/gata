import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from core.config_loader import load_providers_config
from core.newsletter_merge import NewsletterMergeError, merge_edition, write_output

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY")
_NOTIFICATION_FILENAME = "edition_notification.txt"


def _find_providers_config() -> str | None:
    """Return path to providers.yaml using the same lookup order as pipeline.py.

    Order: ./providers.yaml (project/dev) → ~/.gata/providers.yaml (user install).
    """
    local = Path("providers.yaml")
    if local.exists():
        return str(local.resolve())
    user = Path.home() / ".gata" / "providers.yaml"
    if user.exists():
        return str(user)
    return None


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
    parser.add_argument(
        "--no-image",
        action="store_true",
        help=(
            "skip the automatic engagement-image and its deliberation step"
            " (no engagement_image.png is generated, no extra cost)"
        ),
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
    providers_config = None
    providers_path = _find_providers_config()
    if providers_path:
        try:
            providers_config = load_providers_config(providers_path)
        except ValueError as exc:
            logger.error("providers config error: %s", exc)
            sys.exit(1)
    edition_dir = Path(args.edition_folder)
    output_path = (
        Path(args.output) if args.output else edition_dir / "merged_linkedin_post.md"
    )
    try:
        result = merge_edition(
            edition_dir,
            audience=args.audience,
            generate_image=not args.no_image,
            providers_config=providers_config,
        )
    except (NewsletterMergeError, RuntimeError) as exc:
        logger.error("%s", exc)
        sys.exit(1)
    try:
        write_output(result.article_text, output_path)
    except NewsletterMergeError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    print(f"\nMerged edition draft written to {output_path}")
    if result.engagement_image_path:
        print(f"Engagement image written to {result.engagement_image_path}")
    elif not args.no_image:
        print("No engagement image was generated — see the log for why.")
    if result.notification_text:
        notification_path = edition_dir / _NOTIFICATION_FILENAME
        try:
            write_output(result.notification_text, notification_path)
        except NewsletterMergeError as exc:
            logger.error("%s", exc)
            sys.exit(1)
        print(f"Network notification teaser written to {notification_path}")
    else:
        print("No notification teaser was generated — see the log for why.")
    print("This is a draft — review and edit before publishing.")


if __name__ == "__main__":
    main()
