import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google.genai.errors import APIError as GeminiAPIError

from agents.agent_cultural_strategist import infer_audiences
from core.config_loader import load_humor_config, sanitize_path_segment
from core.runner import run_pipeline
from core.types import AudienceProfile, RunTelemetry, StrategyBrief

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


def _research_output_path(topic: str) -> str:
    # FR-008: a bundle-directory-naming key only — no image is ever written
    # at this path in research-only mode.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"output/research/{sanitize_path_segment(topic)}_{timestamp}.md"


def _format_grand_total(audience_telemetry: list[tuple[str, RunTelemetry]]) -> str:
    """One line per audience (time, cost), then a TOTAL line across all of them."""
    lines = [
        f"{name}: {tel.total_duration_seconds:.1f}s — ${tel.total_cost_usd:.4f}"
        for name, tel in audience_telemetry
    ]
    total_duration = sum(tel.total_duration_seconds for _, tel in audience_telemetry)
    total_cost = sum(tel.total_cost_usd for _, tel in audience_telemetry)
    lines.append("")
    lines.append(f"TOTAL: {total_duration:.1f}s — ${total_cost:.4f}")
    return "\n".join(lines)


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
    parser.add_argument(
        "--direct",
        action="store_true",
        help="skip the Cultural Strategist and feed the topic straight to the Satirist",
    )
    parser.add_argument(
        "--linkedin-post",
        action="store_true",
        default=False,
        help=(
            "generate a LinkedIn article (linkedin_post.md) and notification snippet"
            " (linkedin_notification.txt) in the output bundle"
        ),
    )
    parser.add_argument(
        "--angle",
        action="append",
        metavar="TEXT",
        help=(
            "an angle the --linkedin-post article should explore; repeatable"
            " (e.g. --angle 'X' --angle 'Y'). Has no effect without"
            " --linkedin-post."
        ),
    )
    parser.add_argument(
        "--research-only",
        action="store_true",
        help=(
            "skip the entire satirical pipeline (Cultural Strategist, Satirist,"
            " Image Generator, Image Evaluator) and produce only a researched"
            " report — research_report.md by default, or the branded"
            " linkedin_post.md when combined with --linkedin-post. Runs once,"
            " not once per inferred audience."
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help=(
            "show the full per-agent/per-model cost breakdown and INFO-level"
            " logs on screen (default: a single TOTAL line and WARNING+ only"
            " — full detail is always saved to the bundle's summary.txt"
            " regardless of this flag)"
        ),
    )
    args = parser.parse_args()
    if not args.topic.strip():
        print("error: topic must not be empty", file=sys.stderr)
        sys.exit(1)
    found_dotenv = load_dotenv()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    if found_dotenv:
        print("credentials loaded from .env file")
    else:
        print("no .env file found — reading credentials from environment variables")
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY is not set")
        sys.exit(1)
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY is not set")
        sys.exit(1)
    if args.angle and not args.linkedin_post:
        logger.info("--angle has no effect without --linkedin-post")
    if args.direct and args.research_only:
        logger.info(
            "--direct has no additional effect under --research-only"
            " (Cultural Strategist is already skipped)"
        )
    humor = None
    if os.path.exists("humor.yaml"):
        try:
            humor = load_humor_config("humor.yaml")
            if humor:
                print("humor config loaded from humor.yaml")
        except ValueError as exc:
            logger.error("humor config error: %s", exc)
            sys.exit(1)
    if args.research_only:
        # US3: a single neutral/branded report has no per-audience image
        # variants — run once, using only the most relevant inferred audience
        # (no _ensure_uk, no loop).
        audience = infer_audiences(args.topic)[0]
        seed_brief = StrategyBrief(
            target_audience=audience.audience,
            output_language=audience.language,
            tone=audience.tone,
        )
        output_path = _research_output_path(args.topic)
        try:
            run_pipeline(
                args.topic,
                seed_brief,
                output_path,
                humor=humor,
                research_only=True,
                generate_linkedin_post=args.linkedin_post,
                angles=args.angle,
                verbose=args.verbose,
            )
        except (TimeoutError, ValueError, RuntimeError, OSError, GeminiAPIError) as exc:
            logger.error("research-only run failed: %s", exc)
            sys.exit(1)
        bundle_dir = Path(output_path).parent / Path(output_path).stem
        print(f"\nReport saved to {bundle_dir}")
        return
    audiences = _ensure_uk(infer_audiences(args.topic))
    topic_slug = sanitize_path_segment(args.topic)
    output_dir = os.path.join(os.getcwd(), topic_slug)
    os.makedirs(output_dir, exist_ok=True)
    failures = 0
    audience_telemetry: list[tuple[str, RunTelemetry]] = []
    for i, audience in enumerate(audiences, 1):
        seed_brief = StrategyBrief(
            target_audience=audience.audience,
            output_language=audience.language,
            tone=audience.tone,
        )
        output_path = os.path.join(output_dir, f"{audience.name}.png")
        print(f"\n[{i}/{len(audiences)}] {audience.name} — {audience.language}")
        try:
            telemetry = run_pipeline(
                args.topic,
                seed_brief,
                output_path,
                humor=humor,
                include_html=args.html,
                show_title=not args.no_title,
                skip_cultural_strategist=args.direct,
                generate_linkedin_post=args.linkedin_post,
                angles=args.angle,
                verbose=args.verbose,
            )
            audience_telemetry.append((audience.name, telemetry))
        except (TimeoutError, ValueError, RuntimeError, OSError, GeminiAPIError) as exc:
            logger.error("failed for audience %r: %s", audience.name, exc)
            failures += 1
    if audience_telemetry:
        summary = _format_grand_total(audience_telemetry)
        if len(audience_telemetry) > 1:
            print(f"\n{summary}")
        try:
            Path(output_dir, "summary.txt").write_text(summary, encoding="utf-8")
        except OSError as exc:
            logger.error("could not write summary.txt: %s", exc)
    if failures == 0:
        print(f"\nAll {len(audiences)} image(s) saved to {output_dir}")
    elif failures < len(audiences):
        n = len(audiences)
        print(
            f"\n{failures}/{n} audiences failed — partial output in {output_dir}",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print("all audiences failed — no output produced", file=sys.stderr)
        sys.exit(1)
