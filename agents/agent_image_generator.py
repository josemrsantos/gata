import logging

from core.image_generation import ImageGeneration, _closest_gemini_aspect_ratio
from core.types import (
    AgentTelemetry,
    CartoonConcept,
    CartoonLayout,
    PanelConcept,
)

logger = logging.getLogger(__name__)

# Verbatim from constitution.md Section 4 — duplicated here to avoid a circular import
# with agent_satirist.py.
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


def _panel_position_labels(n: int, direction: str) -> list[str]:
    # Returns positional labels matching the layout so the image model knows the
    # physical reading order for each panel.
    if direction == "horizontal":
        if n == 2:
            return ["LEFT", "RIGHT"]
        if n == 3:
            return ["LEFT", "CENTER", "RIGHT"]
        return [f"PANEL {i + 1}" for i in range(n)]
    # vertical direction
    if n == 2:
        return ["TOP", "BOTTOM"]
    if n == 3:
        return ["TOP", "MIDDLE", "BOTTOM"]
    return [f"PANEL {i + 1}" for i in range(n)]


def _build_multi_panel_prompt(
    panels: list[PanelConcept],
    layout: CartoonLayout,
) -> str:
    n = layout.panels
    direction = layout.direction
    orientation = "landscape" if direction == "horizontal" else "portrait"
    arrangement = "left-to-right" if direction == "horizontal" else "top-to-bottom"
    labels = _panel_position_labels(n, direction)
    # Header describes the overall composition so the model renders the correct format
    header = (
        f"Multi-panel satirical comic strip: {n} panels arranged "
        f"{arrangement}, {orientation} orientation. "
        "Visible black rectangular borders between each panel. "
        "Each panel has the same visual style: minimalist charcoal-on-chalkboard, "
        "1970s newspaper newsroom setting, greyscale background with Gata in full "
        "colour (Selective Color style).\n"
    )
    # Per-panel blocks give the model the scene content and caption for each panel
    panel_blocks = []
    for i, panel in enumerate(panels):
        block = (
            f"\n--- PANEL {i + 1} ({labels[i]}) ---\n"
            f"Scene: {panel.scene}\n"
            f'Caption below panel: "{panel.caption}"'
        )
        panel_blocks.append(block)
    # Gata appended once — consistent rendering across all panels
    character_section = (
        "\n\n--- GATA CHARACTER (render consistently across ALL panels) ---\n"
        + _GATA_CHARACTER
    )
    style_section = (
        "\n\n--- VISUAL STYLE (apply to ALL panels equally) ---\n"
        "- Colour palette: greyscale background;"
        " Gata in full colour (Selective Color)\n"
        "- Setting: 1970s newspaper newsroom — fluorescent lights, heavy metal desks\n"
        "- Chalkboard heading in each panel: 'ON THE SPOT'"
        " or target-language equivalent\n"
        "- Attachments on the board use masking tape — never pins\n"
        "- High-contrast, editorial cartoon aesthetic. No gradients. Hard ink lines.\n"
        "- Each panel has a visible rectangular border.\n"
        "- Captions appear beneath each panel, outside the panel border.\n"
        "- Never reference copyrighted artists or characters."
    )
    return header + "".join(panel_blocks) + character_section + style_section


def build_image_request(concept: CartoonConcept, layout: CartoonLayout | None) -> str:
    """The exact text sent to the image model: shared by generate() and prompt-only."""
    # Multi-panel composite when panels exist; concept.image_prompt verbatim otherwise
    if concept.panels is not None and layout is not None:
        prompt = _build_multi_panel_prompt(concept.panels, layout)
        logger.debug(
            "build_image_request: multi-panel mode panels=%d direction=%s "
            "prompt_length=%d",
            layout.panels,
            layout.direction,
            len(prompt),
        )
        return prompt
    logger.debug("image_prompt:\n%s", concept.image_prompt)
    return concept.image_prompt


def request_has_gata_description(request: str) -> bool:
    """True when the request carries the verbatim constitution section 4 paragraph."""
    return _GATA_CHARACTER in request


PROMPT_SEPARATOR = "===== PASTE EVERYTHING BELOW THIS LINE INTO GEMINI ====="


def build_manual_header(
    title: str, show_title: bool, target_size: tuple[int, int] | None
) -> str:
    """Operator-facing notes on what a normal run applies outside the request text."""
    if show_title:
        banner = (
            "not part of the request. A normal run adds the title as a banner above"
            " the picture afterwards; add it yourself if you want it."
        )
    else:
        banner = (
            "not part of the request. --no-title was set, so a normal run adds no"
            " banner either."
        )
    if target_size is not None:
        width, height = target_size
        ratio = _closest_gemini_aspect_ratio(target_size)
        size = f"{width}x{height} (aspect ratio {ratio}); ask Gemini for that shape."
        crop = (
            "Final crop/resize: not applied; a normal run crops to the exact size"
            " above after generation."
        )
    else:
        size = "no size pinned."
        crop = "Final crop/resize: none needed (no size pinned)."
    return (
        "IMAGE REQUEST FOR MANUAL USE (generated by --image-prompt-only)\n"
        f"Title: {title or 'none'}\n"
        f"Title banner: {banner}\n"
        f"Picture size: {size}\n"
        f"{crop}"
    )


def build_prompt_file(
    concept: CartoonConcept,
    layout: CartoonLayout | None,
    show_title: bool,
    target_size: tuple[int, int] | None,
) -> str:
    """Header, one separator line, then the exact request (byte-identical)."""
    header = build_manual_header(concept.title, show_title, target_size)
    return f"{header}\n{PROMPT_SEPARATOR}\n{build_image_request(concept, layout)}"


def generate(
    concept: CartoonConcept,
    output_path: str,
    layout: CartoonLayout | None = None,
    show_title: bool = True,
    target_size: tuple[int, int] | None = None,
) -> tuple[str, AgentTelemetry]:
    # The request is built by the same function the prompt-only mode saves to disk
    prompt = build_image_request(concept, layout)
    # Actual rendering is shared with the newsletter engagement-image path.
    return ImageGeneration().generate(
        prompt,
        output_path,
        title=concept.title,
        show_title=show_title,
        target_size=target_size,
    )
