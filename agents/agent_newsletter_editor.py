from __future__ import annotations

import logging

from core.types import OrderedStory, TokenUsage
from llm.base import LLMProvider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are Gata's newsletter editor. You are given several already-written"
    " LinkedIn articles from Gata's satirical newsroom, each already reviewed and"
    " polished on its own. Your job is to merge them into a single newsletter"
    " edition, in the exact order given, without softening the satire or"
    " rewriting each story's voice.\n\n"
    "Follow every instruction in the user message exactly, especially the fixed"
    " story order and the final cost line — do not reorder stories, and do not"
    " omit, alter, or recompute the cost figure you are given."
)


def build_merge_prompt(
    ordered_stories: list[OrderedStory], estimated_total_cost_usd: float
) -> str:
    """Build the single user-message prompt for the merge call (FR-009, FR-011)."""
    story_blocks = "\n\n".join(
        f"=== STORY {story.order} (folder: {story.path.name}) ===\n{story.text}"
        for story in ordered_stories
    )
    return (
        "Merge the following stories, in the exact order given below, into one"
        " LinkedIn newsletter edition. Do not reorder them.\n\n"
        f"{story_blocks}\n\n"
        "Instructions:\n"
        "- Present each story as its own numbered section, in the order given"
        " above.\n"
        "- Any content repeated across more than one story (a repost-and-share"
        " line, contact/subscribe links, a 'Behind the Scenes' or tech-stack"
        " section) must appear exactly once, consolidated at the end — not once"
        " per story.\n"
        "- Fold each story's own closing question into one shared 'Join the"
        " Conversation' section at the end, in story order.\n"
        "- You may merge and phrase content in whatever way reads best; you are"
        " not required to reproduce any story's wording verbatim.\n"
        "- As the very last line(s) of the document, write exactly this total"
        f" cost figure: ${estimated_total_cost_usd:.4f}, together with a"
        " sentence noting that the human time spent reviewing and editing this"
        " edition was not included in that total."
    )


def generate_merged_post(
    fallback_chain: list[LLMProvider],
    ordered_stories: list[OrderedStory],
    estimated_total_cost_usd: float,
    max_tokens: int = 4096,
) -> tuple[str, TokenUsage]:
    """Call each provider in fallback_chain in turn; return the first success.

    Raises RuntimeError if every provider in the chain fails (FR-015).
    """
    prompt = build_merge_prompt(ordered_stories, estimated_total_cost_usd)
    messages = [{"role": "user", "content": prompt}]
    last_exc: Exception | None = None
    # Cheapest-first order is the caller's responsibility (core.newsletter_merge's
    # build_fallback_chain) — this loop just tries them in the order given.
    for provider in fallback_chain:
        try:
            text, usage = provider.generate(
                _SYSTEM_PROMPT, messages, max_tokens=max_tokens
            )
        except Exception as exc:
            logger.warning(
                "newsletter_editor: provider %s failed — %s", provider.model_id, exc
            )
            last_exc = exc
            continue
        logger.info(
            "newsletter_editor: %s served the merge — %d in / %d out — $%.4f",
            provider.model_id,
            usage.input_tokens,
            usage.output_tokens,
            usage.cost_usd,
        )
        return text, usage
    raise RuntimeError(f"newsletter_editor: all providers exhausted — {last_exc}")
