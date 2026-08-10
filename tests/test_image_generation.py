import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.genai.errors import ServerError
from PIL import Image

from core.image_generation import ImageGeneration, _overlay_title
from llm.gemini import compute_cost

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
PROMPT = "A cat at the UN table."


def _make_gemini_response(binary_data=None, usage_metadata=None):
    part = MagicMock()
    if binary_data is not None:
        part.inline_data = MagicMock(data=binary_data)
    else:
        part.inline_data = None
    response = MagicMock()
    response.candidates = [MagicMock(content=MagicMock(parts=[part]))]
    response.usage_metadata = usage_metadata
    return response


class _UsageMetadata:
    # Plain object (not MagicMock) so getattr() with a default behaves like the real
    # SDK type when an attribute is genuinely absent, instead of auto-vivifying one.
    def __init__(self, prompt_token_count=0, candidates_token_count=None):
        self.prompt_token_count = prompt_token_count
        if candidates_token_count is not None:
            self.candidates_token_count = candidates_token_count


# ---------------------------------------------------------------------------
# First model succeeds — no fallback needed
# ---------------------------------------------------------------------------


def test_generate_first_model_succeeds(tmp_path):
    # generate() writes the image and stops when the first model returns data.
    out_file = tmp_path / "cartoon_output.png"
    response = _make_gemini_response(FAKE_PNG)

    with patch("core.image_generation._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = response
        path, _tel = ImageGeneration().generate(PROMPT, output_path=str(out_file))

    assert Path(path).exists()
    assert Path(path).read_bytes() == FAKE_PNG
    assert mock_client.models.generate_content.call_count == 1


# ---------------------------------------------------------------------------
# Fallback when a model returns no binary data
# ---------------------------------------------------------------------------


def test_generate_falls_back_when_no_data(tmp_path):
    # generate() tries the next model when the current one returns no binary data.
    out_file = tmp_path / "cartoon_output.png"
    no_data = _make_gemini_response(binary_data=None)
    with_data = _make_gemini_response(FAKE_PNG)

    with patch("core.image_generation._gemini_client") as mock_client:
        mock_client.models.generate_content.side_effect = [no_data, with_data]
        path, _tel = ImageGeneration().generate(PROMPT, output_path=str(out_file))

    assert Path(path).exists()
    assert mock_client.models.generate_content.call_count == 2


# ---------------------------------------------------------------------------
# Fallback when a model raises an API exception
# ---------------------------------------------------------------------------


def test_generate_falls_back_on_api_exception(tmp_path):
    # generate() tries the next model when the current one raises an exception.
    out_file = tmp_path / "cartoon_output.png"
    with_data = _make_gemini_response(FAKE_PNG)

    with patch("core.image_generation._gemini_client") as mock_client:
        mock_client.models.generate_content.side_effect = [
            ServerError(503, {"error": {"message": "Model temporarily unavailable"}}),
            with_data,
        ]
        path, _tel = ImageGeneration().generate(PROMPT, output_path=str(out_file))

    assert Path(path).exists()
    assert mock_client.models.generate_content.call_count == 2


# ---------------------------------------------------------------------------
# All models fail → RuntimeError, no file written
# ---------------------------------------------------------------------------


def test_generate_all_models_fail_raises(tmp_path):
    # generate() raises RuntimeError when every model in the chain returns no data.
    out_file = tmp_path / "cartoon_output.png"
    no_data = _make_gemini_response(binary_data=None)

    with patch("core.image_generation._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = no_data
        with pytest.raises(RuntimeError, match="no binary data"):
            ImageGeneration().generate(PROMPT, output_path=str(out_file))

    assert not out_file.exists()


# ---------------------------------------------------------------------------
# Failure preserves existing file at output path
# ---------------------------------------------------------------------------


def test_generate_failure_preserves_existing_file(tmp_path):
    # A failed generate() call must not corrupt a pre-existing file at the output path.
    out_file = tmp_path / "cartoon_output.png"
    original_content = b"original PNG content"
    out_file.write_bytes(original_content)
    no_data = _make_gemini_response(binary_data=None)

    with patch("core.image_generation._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = no_data
        with pytest.raises(RuntimeError):
            ImageGeneration().generate(PROMPT, output_path=str(out_file))

    assert out_file.read_bytes() == original_content


# ---------------------------------------------------------------------------
# Logging compliance — Principle 13
# ---------------------------------------------------------------------------


def test_generate_logs_model_and_prompt_length(caplog, tmp_path):
    # generate() logs model name and prompt length at DEBUG so they are accessible
    # when troubleshooting without polluting normal CLI output.
    out_file = tmp_path / "cartoon_output.png"
    response = _make_gemini_response(FAKE_PNG)

    with patch("core.image_generation._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = response
        caplog.set_level(logging.DEBUG, logger="core.image_generation")
        ImageGeneration().generate(PROMPT, output_path=str(out_file))

    assert any(
        r.levelno == logging.DEBUG and "gemini-3.1-flash-image-preview" in r.message
        for r in caplog.records
    )
    prompt_len = str(len(PROMPT))
    assert any(
        prompt_len in r.message for r in caplog.records if r.levelno == logging.DEBUG
    )


# ---------------------------------------------------------------------------
# Cost telemetry reflects real Gemini usage (Stage 015)
# ---------------------------------------------------------------------------


def test_generate_records_real_output_tokens_and_nonzero_cost(tmp_path):
    # Image generation must record the actual billed output token count and a
    # non-zero cost, instead of the previous hardcoded output_tokens=0 / $0.00 bug.
    out_file = tmp_path / "cartoon_output.png"
    usage = _UsageMetadata(prompt_token_count=500, candidates_token_count=1120)
    response = _make_gemini_response(FAKE_PNG, usage_metadata=usage)

    with patch("core.image_generation._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = response
        _, telemetry = ImageGeneration().generate(PROMPT, output_path=str(out_file))

    call = telemetry.calls[0]
    assert call.model == "gemini-3.1-flash-image-preview"
    assert call.input_tokens == 500
    assert call.output_tokens == 1120
    assert call.cost_usd == pytest.approx(compute_cost(call.model, 500, 1120))
    assert call.cost_usd > 0


def test_generate_defaults_tokens_to_zero_when_usage_metadata_absent(tmp_path):
    # When the SDK response carries no usage_metadata, token counts and cost must
    # default to 0 rather than raising — mirrors the existing dual_loop.py guard.
    out_file = tmp_path / "cartoon_output.png"
    response = _make_gemini_response(FAKE_PNG, usage_metadata=None)

    with patch("core.image_generation._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = response
        _, telemetry = ImageGeneration().generate(PROMPT, output_path=str(out_file))

    call = telemetry.calls[0]
    assert call.input_tokens == 0
    assert call.output_tokens == 0
    assert call.cost_usd == 0.0


def test_generate_telemetry_named_image_generator(tmp_path):
    # Spec 040's sum_image_generator_cost() sums telemetry entries named exactly
    # "Image Generator" — the shared class must keep emitting that exact name.
    out_file = tmp_path / "cartoon_output.png"
    response = _make_gemini_response(FAKE_PNG)

    with patch("core.image_generation._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = response
        _, telemetry = ImageGeneration().generate(PROMPT, output_path=str(out_file))

    assert telemetry.agent_name == "Image Generator"


# ---------------------------------------------------------------------------
# Title overlay — Spec 027
# ---------------------------------------------------------------------------


def _make_real_png(path: str, width: int = 512, height: int = 384) -> None:
    # PIL Image.new is the only reliable way to produce a file _overlay_title can load.
    img = Image.new("RGB", (width, height), (180, 180, 180))
    img.save(path)


def test_overlay_title_expands_image_height(tmp_path):
    # _overlay_title must add a banner above the image, expanding canvas height —
    # if height is unchanged, the overlay did nothing and the title is invisible.
    img_path = str(tmp_path / "test.png")
    _make_real_png(img_path, width=512, height=384)
    _overlay_title(img_path, "G7 Lets AI Self-Regulate")
    with Image.open(img_path) as result:
        assert result.height > 384


def test_overlay_title_preserves_image_width(tmp_path):
    # _overlay_title must not alter image width — the banner spans the same horizontal
    # extent as the original so the overall composition does not shift or crop.
    img_path = str(tmp_path / "test.png")
    _make_real_png(img_path, width=512, height=384)
    _overlay_title(img_path, "G7 Lets AI Self-Regulate")
    with Image.open(img_path) as result:
        assert result.width == 512


def test_generate_calls_overlay_when_show_title_true_and_title_set(tmp_path):
    # generate() must invoke _overlay_title when show_title=True and a title is
    # supplied — the title banner must physically reach the saved image file.
    out_file = tmp_path / "cartoon_output.png"
    response = _make_gemini_response(FAKE_PNG)
    with (
        patch("core.image_generation._gemini_client") as mock_client,
        patch("core.image_generation._overlay_title") as mock_overlay,
    ):
        mock_client.models.generate_content.return_value = response
        ImageGeneration().generate(
            PROMPT,
            output_path=str(out_file),
            title="AI Circus Comes to Town",
            show_title=True,
        )
    mock_overlay.assert_called_once_with(str(out_file), "AI Circus Comes to Town")


def test_generate_skips_overlay_when_show_title_false(tmp_path):
    # generate() must NOT call _overlay_title when show_title=False — the --no-title
    # flag must suppress the banner so the raw image is delivered without modification.
    out_file = tmp_path / "cartoon_output.png"
    response = _make_gemini_response(FAKE_PNG)
    with (
        patch("core.image_generation._gemini_client") as mock_client,
        patch("core.image_generation._overlay_title") as mock_overlay,
    ):
        mock_client.models.generate_content.return_value = response
        ImageGeneration().generate(
            PROMPT,
            output_path=str(out_file),
            title="AI Circus Comes to Town",
            show_title=False,
        )
    mock_overlay.assert_not_called()


def test_generate_skips_overlay_when_title_is_none(tmp_path):
    # generate() must NOT call _overlay_title when title=None — the newsletter
    # engagement-image caller (FR-011) never supplies a title, and must not get a
    # blank banner.
    out_file = tmp_path / "cartoon_output.png"
    response = _make_gemini_response(FAKE_PNG)
    with (
        patch("core.image_generation._gemini_client") as mock_client,
        patch("core.image_generation._overlay_title") as mock_overlay,
    ):
        mock_client.models.generate_content.return_value = response
        ImageGeneration().generate(
            PROMPT,
            output_path=str(out_file),
            title=None,
            show_title=True,
        )
    mock_overlay.assert_not_called()
