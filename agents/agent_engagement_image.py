import logging

from core.types import AgentTelemetry, OrderedStory, PersonaConfig
from llm.base import LLMProvider
from llm.fair_parallel_panel import FairParallelPanel

logger = logging.getLogger(__name__)

# Verbatim from constitution.md Section 4 — duplicated here to avoid a circular
# import, consistent with the existing duplication in agents/agent_image_generator.py.
_GATA_CHARACTER = (
    "Gata is a domestic shorthair calico-tabby mix: white chest, muzzle, and paws; "
    "dark grey/black tabby stripes; orange/ginger patches on back. "
    "She has a small dark spot on the bridge of her pink nose. "
    "She wears a simple dark leather collar with a gold/brass nameplate"
    ' engraved "GATA". '
    "Her demeanour is serious, investigative, slightly tired, and highly intelligent. "
    "She never wears human clothes or accessories"
    " — no hats, glasses, pens, or clothing of any kind."
)

# Verbatim from constitution.md Section 5 — every image prompt in this project must
# enforce this aesthetic, with no carve-out for a cover/engagement image.
_VISUAL_STYLE = (
    "--- VISUAL STYLE (mandatory, identical to every other Gata cartoon) ---\n"
    "- Colour palette: greyscale background; Gata in full colour (Selective Color"
    " style)\n"
    "- Setting: 1970s newspaper newsroom — fluorescent lights, heavy metal desks,"
    " background figures\n"
    "- The board: dark chalkboard, hand-drawn white sketches; heading reads 'ON THE"
    " SPOT' (or the target-language equivalent)\n"
    "- Attachments on the board use masking tape — never pins\n"
    "- Minimalist charcoal-on-chalkboard style; high-contrast editorial cartoon"
    " aesthetic; no gradients; hard ink lines\n"
    "- Never reference copyrighted artists or characters — describe visual"
    " characteristics only"
)

_PANELIST_SYSTEM = (
    "You are a visual-concept panelist for Gata Newsroom's newsletter edition"
    " cover.\n"
    "You are given the full text of every story in this newsletter edition, in"
    " order. Propose ONE complete image-generation prompt for a single image that"
    " visually represents the whole edition as a unifying concept — not a literal"
    " collage of the individual stories.\n\n"
    f"{_GATA_CHARACTER}\n\n"
    f"{_VISUAL_STYLE}\n\n"
    "Wrap your entire output in <verdict>...</verdict> tags. The verdict content"
    " must be nothing but the complete image-generation prompt itself — vivid"
    " visual description, no labels, no preamble, ready to hand directly to an"
    " image-generation model. Your prompt text must itself restate the visual style"
    " constraints above so the image model receives them directly."
)

_AGGREGATOR_SYSTEM = (
    "You are the Art Director for Gata Newsroom's newsletter edition cover.\n"
    "Several panelists have each independently proposed an image-generation prompt"
    " for this edition's cover. Evaluate each for how well it unifies the"
    " edition's stories into one coherent visual concept, then pick the single"
    " strongest proposal or synthesise the best elements of several into one"
    " superior prompt.\n\n"
    f"{_VISUAL_STYLE}\n\n"
    "Every candidate proposal was instructed to follow this visual style — if any"
    " proposal drifted from it, correct that in your final synthesis rather than"
    " carrying the drift forward.\n"
    "Output a PICK: N line (N = the proposal number you selected as primary), then"
    " the final image-generation prompt wrapped in <verdict>...</verdict> — the"
    " verdict content must be nothing but the final prompt text, ready to hand"
    " directly to an image-generation model.\n"
    "Do not add any preamble outside the PICK line and the verdict block."
)


def _build_initial_input(stories: list[OrderedStory]) -> str:
    story_blocks = "\n\n".join(
        f"=== STORY {story.order} ===\n{story.text}" for story in stories
    )
    return f"Newsletter edition stories, in reading order:\n\n{story_blocks}"


def run(
    stories: list[OrderedStory],
    panelist_providers: list[list[LLMProvider]],
    aggregator_providers: list[LLMProvider],
) -> tuple[str, AgentTelemetry]:
    """Run the FairParallelPanel deliberation and return the final image prompt.

    Raises ValueError if the panel produces an empty prompt.
    """
    # Each slot is an ordered fallback chain; primary provider name labels the panelist.
    panelists = [
        PersonaConfig(
            name=slot[0].model_id, providers=slot, system_prompt=_PANELIST_SYSTEM
        )
        for slot in panelist_providers
    ]
    aggregator = PersonaConfig(
        name="Art Director",
        providers=aggregator_providers,
        system_prompt=_AGGREGATOR_SYSTEM,
    )
    panel = FairParallelPanel(
        panelists=panelists,
        aggregator=aggregator,
        panel_name="Engagement Image Concept",
    )
    loop_output = panel.run(_build_initial_input(stories))
    prompt = loop_output.verdict.strip()
    if not prompt:
        raise ValueError("Engagement Image Concept: panel produced an empty prompt")
    telemetry = loop_output.telemetry or AgentTelemetry(
        agent_name="Engagement Image Concept", duration_seconds=0.0, iterations=0
    )
    logger.info("engagement_image_concept: final prompt length=%d chars", len(prompt))
    return prompt, telemetry
