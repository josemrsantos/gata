from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.agent_engagement_image import _GATA_CHARACTER, _VISUAL_STYLE, run
from core.types import AgentTelemetry, ConversationLog, LoopOutput, OrderedStory


def _story(order: int, text: str) -> OrderedStory:
    return OrderedStory(
        path=Path(f"{order:02d}_story"),
        order=order,
        text=text,
        image_generator_cost_usd=0.0,
    )


def _provider(model_id: str) -> MagicMock:
    provider = MagicMock()
    provider.model_id = model_id
    return provider


_STORIES = [_story(1, "Story one body text."), _story(2, "Story two body text.")]
_PANELIST_PROVIDERS = [
    [_provider("model-a")],
    [_provider("model-b")],
    [_provider("model-c")],
]
_AGGREGATOR_PROVIDERS = [_provider("aggregator-model")]


def _fake_loop_output(verdict: str) -> LoopOutput:
    return LoopOutput(
        verdict=verdict,
        log=ConversationLog(loop_name="Engagement Image Concept"),
        telemetry=AgentTelemetry(
            agent_name="Engagement Image Concept", duration_seconds=1.0, iterations=2
        ),
    )


def test_run_returns_aggregator_verdict_as_final_prompt():
    # The whole point of the deliberation is that the aggregator's pick becomes the
    # final image prompt, not any single panelist's independent guess.
    with patch("agents.agent_engagement_image.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output(
            "  A vivid cover scene.  "
        )
        prompt, telemetry = run(_STORIES, _PANELIST_PROVIDERS, _AGGREGATOR_PROVIDERS)
    assert prompt == "A vivid cover scene."
    assert telemetry.agent_name == "Engagement Image Concept"


def test_panelist_system_prompt_includes_verbatim_gata_character():
    # Constitution §4: any prompt referencing Gata's appearance must copy the
    # character paragraph character-for-character, not a paraphrase.
    with patch("agents.agent_engagement_image.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output("prompt")
        run(_STORIES, _PANELIST_PROVIDERS, _AGGREGATOR_PROVIDERS)
    _, kwargs = mock_cls.call_args
    panelists = kwargs["panelists"]
    assert panelists
    assert all(_GATA_CHARACTER in p.system_prompt for p in panelists)


def test_panelist_and_aggregator_prompts_enforce_mandatory_visual_style():
    # Constitution §5: every image prompt in this project must enforce the
    # greyscale/Selective-Color 1970s-newsroom aesthetic — a cover image is not an
    # exception, and this regression (a photorealistic office scene) shipped once
    # already when this constraint was omitted.
    with patch("agents.agent_engagement_image.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output("prompt")
        run(_STORIES, _PANELIST_PROVIDERS, _AGGREGATOR_PROVIDERS)
    _, kwargs = mock_cls.call_args
    for panelist in kwargs["panelists"]:
        assert _VISUAL_STYLE in panelist.system_prompt
    assert _VISUAL_STYLE in kwargs["aggregator"].system_prompt


def test_panelists_named_by_model_id_aggregator_named_art_director():
    # RULE 9: agent names must be human-readable; this mirrors the existing
    # Cultural Strategist convention of naming panelists by their model_id.
    with patch("agents.agent_engagement_image.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output("prompt")
        run(_STORIES, _PANELIST_PROVIDERS, _AGGREGATOR_PROVIDERS)
    _, kwargs = mock_cls.call_args
    panelist_names = [p.name for p in kwargs["panelists"]]
    assert panelist_names == ["model-a", "model-b", "model-c"]
    assert kwargs["aggregator"].name == "Art Director"


def test_initial_input_includes_every_story_text_in_order():
    # FR-003: every story's full text must reach the panel, in edition order.
    with patch("agents.agent_engagement_image.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output("prompt")
        run(_STORIES, _PANELIST_PROVIDERS, _AGGREGATOR_PROVIDERS)
    initial_input = mock_cls.return_value.run.call_args.args[0]
    first_pos = initial_input.index("Story one body text.")
    second_pos = initial_input.index("Story two body text.")
    assert first_pos < second_pos


def test_initial_input_never_references_a_story_image_path():
    # FR-003: the concept panel must never receive any story's rendered image —
    # not even as a file path reference — only story text.
    with patch("agents.agent_engagement_image.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output("prompt")
        run(_STORIES, _PANELIST_PROVIDERS, _AGGREGATOR_PROVIDERS)
    initial_input = mock_cls.return_value.run.call_args.args[0]
    assert "01_story" not in initial_input
    assert ".png" not in initial_input


def test_empty_verdict_raises_value_error():
    # An empty aggregator verdict means the deliberation failed to produce a usable
    # prompt — this must surface as an explicit error, not an empty image prompt
    # silently reaching image generation.
    with patch("agents.agent_engagement_image.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output("   ")
        with pytest.raises(ValueError):
            run(_STORIES, _PANELIST_PROVIDERS, _AGGREGATOR_PROVIDERS)
