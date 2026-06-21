import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.genai.errors import ServerError

from agents import agent_image_generator
from core.types import (
    CartoonConcept,
    CartoonLayout,
    PanelConcept,
    StrategyBrief,
)
from llm.gemini import compute_cost

BRIEF = StrategyBrief(
    target_audience="general public",
    output_language="English",
    tone="dry wit",
)

CONCEPT = CartoonConcept(
    full_text="<image_prompt>A cat at the UN table.</image_prompt>",
    image_prompt="A cat at the UN table.",
    iteration=1,
)

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


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

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = response
        path, _tel = agent_image_generator.generate(
            CONCEPT, BRIEF, output_path=str(out_file)
        )

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

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.side_effect = [no_data, with_data]
        path, _tel = agent_image_generator.generate(
            CONCEPT, BRIEF, output_path=str(out_file)
        )

    assert Path(path).exists()
    assert mock_client.models.generate_content.call_count == 2


# ---------------------------------------------------------------------------
# Fallback when a model raises an API exception
# ---------------------------------------------------------------------------


def test_generate_falls_back_on_api_exception(tmp_path):
    # generate() tries the next model when the current one raises an exception.
    out_file = tmp_path / "cartoon_output.png"
    with_data = _make_gemini_response(FAKE_PNG)

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.side_effect = [
            ServerError(503, {"error": {"message": "Model temporarily unavailable"}}),
            with_data,
        ]
        path, _tel = agent_image_generator.generate(
            CONCEPT, BRIEF, output_path=str(out_file)
        )

    assert Path(path).exists()
    assert mock_client.models.generate_content.call_count == 2


# ---------------------------------------------------------------------------
# All models fail → RuntimeError, no file written
# ---------------------------------------------------------------------------


def test_generate_all_models_fail_raises(tmp_path):
    # generate() raises RuntimeError when every model in the chain returns no data.
    out_file = tmp_path / "cartoon_output.png"
    no_data = _make_gemini_response(binary_data=None)

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = no_data
        with pytest.raises(RuntimeError, match="no binary data"):
            agent_image_generator.generate(CONCEPT, BRIEF, output_path=str(out_file))

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

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = no_data
        with pytest.raises(RuntimeError):
            agent_image_generator.generate(CONCEPT, BRIEF, output_path=str(out_file))

    assert out_file.read_bytes() == original_content


# ---------------------------------------------------------------------------
# Logging compliance — Principle 13
# ---------------------------------------------------------------------------


def test_generate_logs_model_and_prompt_length(caplog, tmp_path):
    # generate() logs model name and prompt length at DEBUG so they are accessible
    # when troubleshooting without polluting normal CLI output.
    out_file = tmp_path / "cartoon_output.png"
    response = _make_gemini_response(FAKE_PNG)

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = response
        caplog.set_level(logging.DEBUG, logger="agents.agent_image_generator")
        agent_image_generator.generate(CONCEPT, BRIEF, output_path=str(out_file))

    assert any(
        r.levelno == logging.DEBUG and "gemini-3.1-flash-image-preview" in r.message
        for r in caplog.records
    )
    prompt_len = str(len(CONCEPT.image_prompt))
    assert any(
        prompt_len in r.message for r in caplog.records if r.levelno == logging.DEBUG
    )


# ---------------------------------------------------------------------------
# Multi-panel support (Stage 9)
# ---------------------------------------------------------------------------

_3_PANELS = [
    PanelConcept(scene="Gata reads the headline", caption="Day one.", beat="setup"),
    PanelConcept(scene="Gata raises an eyebrow", caption="Really?", beat="escalation"),
    PanelConcept(scene="Gata flips board", caption="Same.", beat="punchline"),
]
_2_PANELS = [
    PanelConcept(scene="Gata spots the pattern", caption="Here we go.", beat="setup"),
    PanelConcept(scene="Gata walks away", caption="As expected.", beat="punchline"),
]

_MULTI_CONCEPT_3H = CartoonConcept(
    full_text="", image_prompt="", iteration=0, panels=_3_PANELS
)
_MULTI_CONCEPT_2V = CartoonConcept(
    full_text="", image_prompt="", iteration=0, panels=_2_PANELS
)

_LAYOUT_3H = CartoonLayout(panels=3, direction="horizontal")
_LAYOUT_2V = CartoonLayout(panels=2, direction="vertical")


def test_generate_multi_panel_uses_composite_prompt(tmp_path):
    # When concept.panels is non-None, generate() must build a composite prompt
    # containing all panel scenes rather than using the empty image_prompt field.
    out_file = tmp_path / "multi.png"
    response = _make_gemini_response(FAKE_PNG)
    captured = {}

    def _capture(*args, **kwargs):
        captured["prompt"] = kwargs.get("contents") or (args[0] if args else "")
        return response

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.side_effect = _capture
        agent_image_generator.generate(
            _MULTI_CONCEPT_3H, BRIEF, output_path=str(out_file), layout=_LAYOUT_3H
        )

    prompt = captured.get("prompt", "")
    assert "Gata reads the headline" in prompt
    assert "Gata raises an eyebrow" in prompt
    assert "Gata flips board" in prompt


def test_generate_multi_panel_horizontal_uses_left_right_labels(tmp_path):
    # A 3-panel horizontal strip must use LEFT/CENTER/RIGHT positional labels so the
    # image model knows the reading order and physical arrangement of the panels.
    out_file = tmp_path / "multi.png"
    response = _make_gemini_response(FAKE_PNG)
    captured = {}

    def _capture(*args, **kwargs):
        captured["prompt"] = kwargs.get("contents") or (args[0] if args else "")
        return response

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.side_effect = _capture
        agent_image_generator.generate(
            _MULTI_CONCEPT_3H, BRIEF, output_path=str(out_file), layout=_LAYOUT_3H
        )

    prompt = captured.get("prompt", "")
    assert "LEFT" in prompt
    assert "CENTER" in prompt
    assert "RIGHT" in prompt


def test_generate_multi_panel_vertical_uses_top_bottom_labels(tmp_path):
    # A 2-panel vertical strip must use TOP/BOTTOM positional labels so the image model
    # renders panels stacked vertically in reading order.
    out_file = tmp_path / "multi.png"
    response = _make_gemini_response(FAKE_PNG)
    captured = {}

    def _capture(*args, **kwargs):
        captured["prompt"] = kwargs.get("contents") or (args[0] if args else "")
        return response

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.side_effect = _capture
        agent_image_generator.generate(
            _MULTI_CONCEPT_2V, BRIEF, output_path=str(out_file), layout=_LAYOUT_2V
        )

    prompt = captured.get("prompt", "")
    assert "TOP" in prompt
    assert "BOTTOM" in prompt


def test_generate_multi_panel_includes_gata_description(tmp_path):
    # The Gata character description must appear in the multi-panel prompt so the
    # image model renders Gata consistently across all panels.
    out_file = tmp_path / "multi.png"
    response = _make_gemini_response(FAKE_PNG)
    captured = {}

    def _capture(*args, **kwargs):
        captured["prompt"] = kwargs.get("contents") or (args[0] if args else "")
        return response

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.side_effect = _capture
        agent_image_generator.generate(
            _MULTI_CONCEPT_3H, BRIEF, output_path=str(out_file), layout=_LAYOUT_3H
        )

    prompt = captured.get("prompt", "")
    assert "GATA" in prompt or "calico" in prompt.lower()


def test_generate_single_panel_unchanged_when_panels_is_none(tmp_path):
    # When concept.panels is None, generate() must use concept.image_prompt verbatim
    # so the existing single-panel path is unaffected by Stage 9 changes.
    out_file = tmp_path / "single.png"
    response = _make_gemini_response(FAKE_PNG)
    captured = {}

    def _capture(*args, **kwargs):
        captured["prompt"] = kwargs.get("contents") or (args[0] if args else "")
        return response

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.side_effect = _capture
        agent_image_generator.generate(CONCEPT, BRIEF, output_path=str(out_file))

    assert captured.get("prompt") == CONCEPT.image_prompt


def test_generate_multi_panel_beat_not_in_prompt(tmp_path):
    # Beat labels (setup/escalation/punchline) are internal narrative markers for the
    # Satirist — they must never appear in the image prompt or the image model renders
    # them as visible text in the output image.
    out_file = tmp_path / "multi.png"
    response = _make_gemini_response(FAKE_PNG)
    captured = {}

    def _capture(*args, **kwargs):
        captured["prompt"] = kwargs.get("contents") or (args[0] if args else "")
        return response

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.side_effect = _capture
        agent_image_generator.generate(
            _MULTI_CONCEPT_3H, BRIEF, output_path=str(out_file), layout=_LAYOUT_3H
        )

    prompt = captured.get("prompt", "").upper()
    assert "BEAT:" not in prompt


# ---------------------------------------------------------------------------
# Cost telemetry reflects real Gemini usage (Stage 015)
# ---------------------------------------------------------------------------


def test_generate_records_real_output_tokens_and_nonzero_cost(tmp_path):
    # Image generation must record the actual billed output token count and a
    # non-zero cost, instead of the previous hardcoded output_tokens=0 / $0.00 bug.
    out_file = tmp_path / "cartoon_output.png"
    usage = _UsageMetadata(prompt_token_count=500, candidates_token_count=1120)
    response = _make_gemini_response(FAKE_PNG, usage_metadata=usage)

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = response
        _, telemetry = agent_image_generator.generate(
            CONCEPT, BRIEF, output_path=str(out_file)
        )

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

    with patch("agents.agent_image_generator._gemini_client") as mock_client:
        mock_client.models.generate_content.return_value = response
        _, telemetry = agent_image_generator.generate(
            CONCEPT, BRIEF, output_path=str(out_file)
        )

    call = telemetry.calls[0]
    assert call.input_tokens == 0
    assert call.output_tokens == 0
    assert call.cost_usd == 0.0
