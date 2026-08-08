import logging
import os
import tempfile
import time

from google import genai
from google.genai.errors import APIError
from PIL import Image, ImageDraw, ImageFont

from core.types import AgentTelemetry, TokenUsage
from llm.gemini import compute_cost

logger = logging.getLogger(__name__)

_gemini_client: genai.Client | None = None

_MODELS = [
    "gemini-3.1-flash-image-preview",
    "gemini-3.1-flash-image",
    "gemini-3-pro-image-preview",
    "gemini-3-pro-image",
    "gemini-2.5-flash-image",
]


def _overlay_title(image_path: str, title: str) -> None:
    with Image.open(image_path) as img:
        # normalize to RGB so any source mode (RGBA, P, etc.) is handled uniformly
        rgb = img.convert("RGB")
    width, height = rgb.size
    # banner height proportional to image; minimum 50 px so text stays legible
    banner_h = max(50, int(height * 0.08))
    font_size = max(18, int(banner_h * 0.52))
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:
        # Pillow < 10 does not accept a size argument to load_default
        font = ImageFont.load_default()
    # new canvas: dark banner (#1a1a1a) at top, original image shifted below
    canvas = Image.new("RGB", (width, height + banner_h), (26, 26, 26))
    canvas.paste(rgb, (0, banner_h))
    draw = ImageDraw.Draw(canvas)
    # center title text horizontally and vertically within the banner
    bbox = draw.textbbox((0, 0), title, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = max(0, (width - text_w) // 2)
    y = max(0, (banner_h - text_h) // 2)
    draw.text((x, y), title, fill=(255, 255, 255), font=font)
    canvas.save(image_path)
    logger.debug("image_generation: title overlay added — %r", title)


class ImageGeneration:
    """Shared Gemini image-rendering core.

    Given a finished prompt string, tries each model in _MODELS in priority order,
    writes the first successful result atomically to output_path, and optionally
    overlays a title banner. Used by both the per-story pipeline
    (agents/agent_image_generator.py) and the newsletter engagement-image step
    (core/newsletter_merge.py) so both render through identical code.
    """

    def generate(
        self,
        prompt: str,
        output_path: str,
        title: str | None = None,
        show_title: bool = True,
    ) -> tuple[str, AgentTelemetry]:
        start = time.monotonic()
        token_calls: list[TokenUsage] = []
        logger.debug("ImageGeneration: rendering (%d chars)", len(prompt))
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
            # Call succeeded; now check it actually returned usable content.
            content = response.candidates[0].content if response.candidates else None
            if content is None or content.parts is None:
                logger.warning("Model %s returned no content parts", model)
                continue
            # Content exists; search its parts for the actual image bytes.
            image_data: bytes | None = None
            for part in content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    break
            if image_data is None:
                logger.warning("Model %s returned no binary data", model)
                continue
            # Image bytes found — write them atomically before recording any telemetry.
            output_dir = os.path.dirname(output_path) or "."
            with tempfile.NamedTemporaryFile(
                dir=output_dir, delete=False, suffix=".tmp"
            ) as tmp:
                tmp_name = tmp.name
                tmp.write(image_data)
            # Temp file written; publish it atomically to the real output path.
            try:
                os.replace(tmp_name, output_path)
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
            # File is on disk; usage_metadata may be absent on some Gemini models.
            meta = getattr(response, "usage_metadata", None)
            in_tok = getattr(meta, "prompt_token_count", 0) or 0
            out_tok = getattr(meta, "candidates_token_count", 0) or 0
            cost_usd = compute_cost(model, in_tok, out_tok)
            token_calls.append(
                TokenUsage(
                    model=model,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cost_usd=cost_usd,
                )
            )
            logger.debug(
                "ImageGeneration: saved — model=%s cost=$%.4f", model, cost_usd
            )
            # overlay title banner only when requested and a title was supplied
            if show_title and title:
                _overlay_title(output_path, title)
            telemetry = AgentTelemetry(
                agent_name="Image Generator",
                duration_seconds=time.monotonic() - start,
                iterations=1,
                calls=token_calls,
            )
            return os.path.abspath(output_path), telemetry
        # Every model in the fallback list was tried and none produced usable data.
        raise RuntimeError("Image generation failed: no binary data from any model")
