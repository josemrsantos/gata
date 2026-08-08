from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from agents import agent_engagement_image
from agents.agent_newsletter_editor import generate_merged_post, parse_merge_response
from core.image_generation import ImageGeneration
from core.types import EditionMergeResult, ModelSpec, OrderedStory, ProvidersConfig
from llm.base import LLMProvider
from llm.claude import _COST_PER_M as _CLAUDE_COST_PER_M
from llm.claude import ClaudeProvider
from llm.gemini import _COST_PER_M as _GEMINI_COST_PER_M
from llm.gemini import GeminiProvider
from llm.grok import _COST_PER_M as _GROK_COST_PER_M
from llm.grok import GrokProvider

logger = logging.getLogger(__name__)

_PREFIX_RE = re.compile(r"^(\d+)[-_]")
_IMAGE_GENERATOR_AGENT_NAME = "Image Generator"
_DEFAULT_MAX_TOKENS = 4096
_CHARS_PER_TOKEN_ESTIMATE = 4
_ENGAGEMENT_IMAGE_FILENAME = "engagement_image.png"

# Active Gemini text models considered for the merge call — image models are
# excluded, this call never generates or evaluates an image (Spec 040 FR-007).
_GEMINI_TEXT_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3.1-pro-preview",
]
# Claude/Grok models tried once every Gemini option has failed (FR-013).
_CLAUDE_MODELS = ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"]
_GROK_MODELS = ["grok-build-0.1", "grok-4.3", "grok-4.5"]

# Default engagement-image deliberation providers, mirroring core/runner.py's
# _PARALLEL_PANELISTS / _GROK_AGGREGATOR defaults — used when no providers.yaml
# override is supplied (Spec 041 FR-002).
_DEFAULT_PANELIST_PROVIDERS: list[LLMProvider] = [
    ClaudeProvider("claude-sonnet-4-6"),
    GrokProvider("grok-build-0.1"),
    GeminiProvider("gemini-2.5-flash"),
]
_DEFAULT_AGGREGATOR_PROVIDERS: list[LLMProvider] = [GrokProvider("grok-4.3")]


class NewsletterMergeError(Exception):
    """Any FR-0xx hard-error condition raised by this module."""


def discover_and_order_stories(edition_dir: Path, audience: str) -> list[OrderedStory]:
    """Find, validate, and order every story folder under edition_dir (FR-002-006)."""
    if not edition_dir.is_dir():
        raise NewsletterMergeError(f"edition folder not found: {edition_dir}")
    candidates = sorted(
        p for p in edition_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    if len(candidates) < 2:
        raise NewsletterMergeError(
            f"need at least 2 story folders under {edition_dir} — found"
            f" {len(candidates)}; merging a single story is meaningless, use its"
            " own linkedin_post.md directly"
        )
    # Every candidate must carry a leading number fixing its position (FR-004).
    missing_prefix = [p.name for p in candidates if not _PREFIX_RE.match(p.name)]
    if missing_prefix:
        raise NewsletterMergeError(
            "every story folder needs a leading number to fix its order (e.g."
            f" 01_story-name) — missing on: {', '.join(sorted(missing_prefix))}"
        )
    # Two folders cannot claim the same position (FR-005).
    numbered = [(int(_PREFIX_RE.match(p.name).group(1)), p) for p in candidates]
    seen: dict[int, Path] = {}
    collisions: list[str] = []
    for number, path in numbered:
        if number in seen:
            collisions.append(
                f"{seen[number].name!r} and {path.name!r} both use {number}"
            )
        else:
            seen[number] = path
    if collisions:
        raise NewsletterMergeError(
            f"story folders have colliding numeric prefixes: {'; '.join(collisions)}"
        )
    numbered.sort(key=lambda item: (item[0], item[1].name))
    # Only now read each story's content — every folder is confirmed unambiguous.
    stories: list[OrderedStory] = []
    for order, path in numbered:
        post_path = path / audience / "linkedin_post.md"
        if not post_path.is_file():
            raise NewsletterMergeError(
                f"{path.name}: missing expected file {post_path}"
            )
        text = post_path.read_text(encoding="utf-8")
        cost = sum_image_generator_cost(path / audience / "telemetry.json", path.name)
        stories.append(
            OrderedStory(
                path=path, order=order, text=text, image_generator_cost_usd=cost
            )
        )
    return stories


def sum_image_generator_cost(telemetry_path: Path, story_name: str) -> float:
    """Sum every "Image Generator" agent's cost in telemetry_path (FR-010a, FR-012)."""
    try:
        data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NewsletterMergeError(
            f"{story_name}: could not read {telemetry_path} — {exc}"
        ) from exc
    costs = [
        agent.get("total_cost_usd", 0.0)
        for agent in data.get("agents", [])
        if agent.get("agent") == _IMAGE_GENERATOR_AGENT_NAME
    ]
    if not costs:
        raise NewsletterMergeError(
            f"{story_name}: {telemetry_path} has no {_IMAGE_GENERATOR_AGENT_NAME!r}"
            " entries"
        )
    return sum(costs)


def estimate_merge_call_cost(
    rate: tuple[float, float], input_text: str, max_tokens: int
) -> float:
    """Conservative cost estimate: real input size, capped output (FR-010b)."""
    input_rate, output_rate = rate
    estimated_input_tokens = max(1, len(input_text) // _CHARS_PER_TOKEN_ESTIMATE)
    return (estimated_input_tokens * input_rate + max_tokens * output_rate) / 1_000_000


def build_fallback_chain() -> list[tuple[LLMProvider, tuple[float, float]]]:
    """Every candidate model paired with its rate, cheapest tier-first (FR-013)."""
    gemini_tier = [
        (GeminiProvider(model), _GEMINI_COST_PER_M[model])
        for model in _GEMINI_TEXT_MODELS
    ]
    other_tier = [
        (GrokProvider(model), _GROK_COST_PER_M[model]) for model in _GROK_MODELS
    ] + [(ClaudeProvider(model), _CLAUDE_COST_PER_M[model]) for model in _CLAUDE_MODELS]
    gemini_tier.sort(key=lambda item: sum(item[1]))
    other_tier.sort(key=lambda item: sum(item[1]))
    return gemini_tier + other_tier


def _build_provider(spec: ModelSpec) -> LLMProvider:
    """Instantiate the correct LLMProvider from a ModelSpec (mirrors core/runner.py)."""
    if spec.provider == "claude":
        return ClaudeProvider(spec.model, timeout=spec.timeout)
    if spec.provider == "gemini":
        return GeminiProvider(spec.model, timeout=spec.timeout)
    if spec.provider == "grok":
        return GrokProvider(spec.model, timeout=spec.timeout)
    raise ValueError(f"unknown provider: {spec.provider!r}")


def _build_engagement_providers(
    providers_config: ProvidersConfig | None,
) -> tuple[list[list[LLMProvider]], list[LLMProvider]]:
    """Build the FairParallelPanel provider lists for the engagement-image concept.

    Reuses providers.yaml's existing panelists/aggregator schema (Spec 041 FR-002)
    when supplied; otherwise falls back to the same hardcoded defaults
    core/runner.py uses for every other FairParallelPanel agent.
    """
    if providers_config is not None:
        panelist_providers = [
            [_build_provider(s) for s in slot] for slot in providers_config.panelists
        ]
        aggregator_providers = [_build_provider(s) for s in providers_config.aggregator]
        return panelist_providers, aggregator_providers
    return [[p] for p in _DEFAULT_PANELIST_PROVIDERS], list(
        _DEFAULT_AGGREGATOR_PROVIDERS
    )


def generate_engagement_image(
    stories: list[OrderedStory],
    edition_dir: Path,
    providers_config: ProvidersConfig | None = None,
) -> tuple[str | None, float]:
    """Run the concept deliberation and render the engagement image.

    Returns (image_path, total_cost). On any failure this is a soft failure per
    Spec 041 FR-008: logs a warning and returns (None, 0.0) rather than raising —
    the caller must still be able to write the merged article.
    """
    panelist_providers, aggregator_providers = _build_engagement_providers(
        providers_config
    )
    try:
        prompt, concept_tel = agent_engagement_image.run(
            stories, panelist_providers, aggregator_providers
        )
        output_path = str(edition_dir / _ENGAGEMENT_IMAGE_FILENAME)
        image_path, image_tel = ImageGeneration().generate(
            prompt, output_path, show_title=False
        )
    except Exception as exc:
        logger.warning("newsletter_merge: engagement image step failed — %s", exc)
        return None, 0.0
    total_cost = concept_tel.total_cost_usd + image_tel.total_cost_usd
    logger.info(
        "newsletter_merge: engagement image written to %s (cost=$%.4f)",
        image_path,
        total_cost,
    )
    return image_path, total_cost


def write_output(text: str, output_path: Path) -> None:
    """Write text verbatim to output_path (FR-016)."""
    try:
        output_path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise NewsletterMergeError(f"could not write {output_path} — {exc}") from exc


def merge_edition(
    edition_dir: Path,
    audience: str = "uk",
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    generate_image: bool = True,
    providers_config: ProvidersConfig | None = None,
) -> EditionMergeResult:
    """Discover, cost, and merge one edition folder into a single draft document.

    When generate_image is True (default), also runs the engagement-image
    deliberation and rendering before the merge-text call, so the resulting exact
    cost can be folded into the published total (Spec 041 FR-010). A failure in
    that step is soft (FR-008): the merge still proceeds and still succeeds.
    """
    stories = discover_and_order_stories(edition_dir, audience)
    engagement_image_path: str | None = None
    engagement_cost = 0.0
    if generate_image:
        engagement_image_path, engagement_cost = generate_engagement_image(
            stories, edition_dir, providers_config
        )
    chain = build_fallback_chain()
    # The priciest candidate in the *whole* chain sets the estimate's rate, so the
    # published total is a true upper bound no matter which model actually
    # succeeds — chain order is cheapest-first per tier, not globally, so this
    # must scan every entry rather than assume the last one is the most expensive.
    priciest_rate = max((rate for _, rate in chain), key=lambda r: r[0] + r[1])
    combined_text = "\n\n".join(story.text for story in stories)
    merge_estimate = estimate_merge_call_cost(priciest_rate, combined_text, max_tokens)
    image_costs_total = sum(story.image_generator_cost_usd for story in stories)
    total_estimate = image_costs_total + merge_estimate + engagement_cost
    providers = [provider for provider, _ in chain]
    merged_text, usage = generate_merged_post(
        providers,
        stories,
        estimated_total_cost_usd=total_estimate,
        max_tokens=max_tokens,
    )
    article_text, notification_text = parse_merge_response(merged_text)
    if notification_text is None:
        logger.warning(
            "newsletter_merge: merge response had no ===NOTIFICATION=== section —"
            " edition_notification.txt will not be written"
        )
    logger.info(
        "newsletter_merge: published total=$%.4f (images=$%.4f + merge"
        " estimate=$%.4f + engagement=$%.4f) — actual merge-call cost=$%.4f (model=%s)",
        total_estimate,
        image_costs_total,
        merge_estimate,
        engagement_cost,
        usage.cost_usd,
        usage.model,
    )
    return EditionMergeResult(
        article_text=article_text,
        notification_text=notification_text,
        engagement_image_path=engagement_image_path,
    )
