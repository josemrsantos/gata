import inspect
from unittest.mock import MagicMock, patch

from agents import agent_image_generator
from core.types import AgentTelemetry, CartoonConcept, CartoonLayout, PanelConcept

CONCEPT = CartoonConcept(
    full_text="<image_prompt>A cat at the UN table.</image_prompt>",
    image_prompt="A cat at the UN table.",
    iteration=1,
)

_FAKE_TELEMETRY = AgentTelemetry(
    agent_name="Image Generator", duration_seconds=0.01, iterations=1
)


def _capture_generate(out_path: str) -> tuple[MagicMock, dict]:
    """Patch ImageGeneration so calls are captured instead of hitting Gemini."""
    captured: dict = {}

    def _fake_generate(
        prompt, output_path, title=None, show_title=True, target_size=None
    ):
        captured["prompt"] = prompt
        captured["output_path"] = output_path
        captured["title"] = title
        captured["show_title"] = show_title
        captured["target_size"] = target_size
        return out_path, _FAKE_TELEMETRY

    mock_cls = MagicMock()
    mock_cls.return_value.generate.side_effect = _fake_generate
    return mock_cls, captured


# ---------------------------------------------------------------------------
# Delegation to core.image_generation.ImageGeneration (Spec 041 FR-006/FR-007)
# ---------------------------------------------------------------------------


def test_generate_does_not_accept_brief_parameter():
    # FR-007: the unused `brief` parameter must be dropped from the public
    # signature, not just ignored internally.
    params = inspect.signature(agent_image_generator.generate).parameters
    assert "brief" not in params


def test_generate_delegates_single_panel_prompt_verbatim(tmp_path):
    # generate() must hand ImageGeneration exactly concept.image_prompt when there
    # are no panels — the single-panel path must be unaffected by the extraction.
    out_file = tmp_path / "single.png"
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        path, tel = agent_image_generator.generate(CONCEPT, output_path=str(out_file))
    assert captured["prompt"] == CONCEPT.image_prompt
    assert captured["output_path"] == str(out_file)
    assert path == str(out_file)
    assert tel is _FAKE_TELEMETRY


def test_generate_passes_empty_title_when_concept_has_none(tmp_path):
    # A concept with no title (the default "") must still delegate that empty
    # string through unchanged — ImageGeneration, not this module, decides that an
    # empty title means no overlay.
    out_file = tmp_path / "single.png"
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        agent_image_generator.generate(CONCEPT, output_path=str(out_file))
    assert captured["title"] == ""


def test_generate_passes_concept_title_and_show_title_through(tmp_path):
    # generate() must forward concept.title and the caller's show_title flag
    # unchanged — the actual overlay decision now lives in ImageGeneration.
    out_file = tmp_path / "single.png"
    titled_concept = CartoonConcept(
        full_text="", image_prompt="prompt text", iteration=1, title="Big Headline"
    )
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        agent_image_generator.generate(
            titled_concept, output_path=str(out_file), show_title=False
        )
    assert captured["title"] == "Big Headline"
    assert captured["show_title"] is False


# ---------------------------------------------------------------------------
# Multi-panel prompt building (Stage 9) — still agent_image_generator's job
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
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        agent_image_generator.generate(
            _MULTI_CONCEPT_3H, output_path=str(out_file), layout=_LAYOUT_3H
        )
    prompt = captured["prompt"]
    assert "Gata reads the headline" in prompt
    assert "Gata raises an eyebrow" in prompt
    assert "Gata flips board" in prompt


def test_generate_multi_panel_horizontal_uses_left_right_labels(tmp_path):
    # A 3-panel horizontal strip must use LEFT/CENTER/RIGHT positional labels so the
    # image model knows the reading order and physical arrangement of the panels.
    out_file = tmp_path / "multi.png"
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        agent_image_generator.generate(
            _MULTI_CONCEPT_3H, output_path=str(out_file), layout=_LAYOUT_3H
        )
    prompt = captured["prompt"]
    assert "LEFT" in prompt
    assert "CENTER" in prompt
    assert "RIGHT" in prompt


def test_generate_multi_panel_vertical_uses_top_bottom_labels(tmp_path):
    # A 2-panel vertical strip must use TOP/BOTTOM positional labels so the image model
    # renders panels stacked vertically in reading order.
    out_file = tmp_path / "multi.png"
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        agent_image_generator.generate(
            _MULTI_CONCEPT_2V, output_path=str(out_file), layout=_LAYOUT_2V
        )
    prompt = captured["prompt"]
    assert "TOP" in prompt
    assert "BOTTOM" in prompt


def test_generate_multi_panel_includes_gata_description(tmp_path):
    # The Gata character description must appear in the multi-panel prompt so the
    # image model renders Gata consistently across all panels.
    out_file = tmp_path / "multi.png"
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        agent_image_generator.generate(
            _MULTI_CONCEPT_3H, output_path=str(out_file), layout=_LAYOUT_3H
        )
    prompt = captured["prompt"]
    assert "GATA" in prompt or "calico" in prompt.lower()


def test_generate_single_panel_unchanged_when_panels_is_none(tmp_path):
    # When concept.panels is None, generate() must use concept.image_prompt verbatim
    # so the existing single-panel path is unaffected by Stage 9 changes.
    out_file = tmp_path / "single.png"
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        agent_image_generator.generate(CONCEPT, output_path=str(out_file))
    assert captured["prompt"] == CONCEPT.image_prompt


def test_generate_multi_panel_beat_not_in_prompt(tmp_path):
    # Beat labels (setup/escalation/punchline) are internal narrative markers for the
    # Satirist — they must never appear in the image prompt or the image model renders
    # them as visible text in the output image.
    out_file = tmp_path / "multi.png"
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        agent_image_generator.generate(
            _MULTI_CONCEPT_3H, output_path=str(out_file), layout=_LAYOUT_3H
        )
    prompt = captured["prompt"].upper()
    assert "BEAT:" not in prompt


# ---------------------------------------------------------------------------
# target_size pass-through — Spec 045 LinkedIn feature image size correction
# ---------------------------------------------------------------------------


def test_generate_passes_target_size_through_to_image_generation(tmp_path):
    # FR-005: a caller-supplied target_size must reach ImageGeneration.generate()
    # unchanged — core/runner.py relies on this to pin --linkedin-post cartoons
    # to LinkedIn's cover size.
    out_file = tmp_path / "single.png"
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        agent_image_generator.generate(
            CONCEPT, output_path=str(out_file), target_size=(1200, 644)
        )
    assert captured["target_size"] == (1200, 644)


def test_generate_defaults_target_size_to_none(tmp_path):
    # FR-007 regression guard: omitting target_size must keep the default
    # behaviour of every existing caller unchanged.
    out_file = tmp_path / "single.png"
    mock_cls, captured = _capture_generate(str(out_file))
    with patch("agents.agent_image_generator.ImageGeneration", mock_cls):
        agent_image_generator.generate(CONCEPT, output_path=str(out_file))
    assert captured["target_size"] is None
