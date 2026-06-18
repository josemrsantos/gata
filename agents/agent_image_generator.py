import logging
import os
import tempfile
import time

from google import genai
from google.genai.errors import APIError

from agents.types import (
    AgentTelemetry,
    CartoonConcept,
    CartoonLayout,
    PanelConcept,
    StrategyBrief,
    TokenUsage,
    compute_cost,
)

logger = logging.getLogger(__name__)

_gemini_client: genai.Client | None = None

_MODELS = [
    "gemini-3.1-flash-image-preview",
    "gemini-3.1-flash-image",
    "gemini-3-pro-image-preview",
    "gemini-3-pro-image",
    "gemini-2.5-flash-image",
]

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


def generate(
    concept: CartoonConcept,
    brief: StrategyBrief,
    output_path: str,
    layout: CartoonLayout | None = None,
) -> tuple[str, AgentTelemetry]:
    start = time.monotonic()
    token_calls: list[TokenUsage] = []
    # Build the prompt: multi-panel composite when panels present, verbatim otherwise
    if concept.panels is not None and layout is not None:
        prompt = _build_multi_panel_prompt(concept.panels, layout)
        logger.debug(
            "generate: multi-panel mode panels=%d direction=%s prompt_length=%d",
            layout.panels,
            layout.direction,
            len(prompt),
        )
    else:
        prompt = concept.image_prompt
        logger.debug("image_prompt:\n%s", prompt)
    logger.debug("Image Generator: rendering (%d chars)", len(prompt))
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client()
    # try each model in priority order; stop on first successful image write
    for model in _MODELS:
        logger.debug(
            "generate: trying model=%s, prompt_length=%d chars", model, len(prompt)
        )
        try:
            response = _gemini_client.models.generate_content(
                model=model,
                contents=prompt,
            )
        except APIError as exc:
            logger.warning("Model %s raised an exception: %s", model, exc)
            continue

        content = response.candidates[0].content if response.candidates else None
        if content is None or content.parts is None:
            logger.warning("Model %s returned no content parts", model)
            continue

        image_data: bytes | None = None
        for part in content.parts:
            if part.inline_data is not None:
                image_data = part.inline_data.data
                break

        if image_data is None:
            logger.warning("Model %s returned no binary data", model)
            continue

        output_dir = os.path.dirname(output_path) or "."
        with tempfile.NamedTemporaryFile(
            dir=output_dir, delete=False, suffix=".tmp"
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(image_data)

        try:
            os.replace(tmp_name, output_path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

        # usage_metadata may be absent on some Gemini models — guard defensively
        meta = getattr(response, "usage_metadata", None)
        in_tok = getattr(meta, "prompt_token_count", 0) or 0
        out_tok = getattr(meta, "candidates_token_count", 0) or 0
        cost_usd = compute_cost(model, in_tok, out_tok)
        token_calls.append(TokenUsage(
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost_usd,
        ))
        logger.debug("Image Generator: saved — model=%s cost=$%.4f", model, cost_usd)
        telemetry = AgentTelemetry(
            agent_name="Image Generator",
            duration_seconds=time.monotonic() - start,
            iterations=1,
            calls=token_calls,
        )
        return os.path.abspath(output_path), telemetry

    raise RuntimeError("Image generation failed: no binary data from any model")
