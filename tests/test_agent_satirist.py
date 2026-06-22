import json
import logging
from unittest.mock import patch

import pytest

from agents.agent_satirist import (
    _build_aggregator_prompt,
    _build_satirist_system_prompt,
    run,
)
from core.types import (
    CartoonConcept,
    CartoonLayout,
    ConversationLog,
    CriticHumor,
    EnrichedBrief,
    FramerHumor,
    HumorConfig,
    LoopOutput,
    SatiristHumor,
)

# -- fixtures --

BRIEF = EnrichedBrief(
    target_audience="general public",
    output_language="English",
    tone="dry wit",
    cultural_angle="A cat territorial dispute metaphor for housing policy.",
    culturally_loaded_references=[
        "The 2024 rent control protests",
        "Airbnb landlord memes circulated on social media",
    ],
)
BRIEF_PT = EnrichedBrief(
    target_audience="Portuguese adults",
    output_language="Portuguese",
    tone="sharp satire",
    cultural_angle="A traditional fado metaphor for political betrayal.",
    culturally_loaded_references=[
        "The 1974 Carnation Revolution",
        "SNS healthcare crisis",
    ],
)
TOPIC = "Cats take over the UN Security Council"
_VALID_IMAGE_PROMPT = "A cat sits at the UN table, wielding a gavel made of fish."
_LOOP_OUTPUT = LoopOutput(
    verdict=_VALID_IMAGE_PROMPT,
    log=ConversationLog(loop_name="Satirist/Co-Satirist"),
)


# -- happy path: run() returns CartoonConcept --


def test_run_returns_cartoon_concept():
    # run() first tuple element must be a CartoonConcept, confirming the output type
    # is stable.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT
        concept, *_ = run(TOPIC, BRIEF, [], [])
    assert isinstance(concept, CartoonConcept)


def test_run_image_prompt_field_populated():
    # CartoonConcept.image_prompt must be set from the ParallelPanel verdict content.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT
        concept, *_ = run(TOPIC, BRIEF, [], [])
    assert concept.image_prompt == _VALID_IMAGE_PROMPT


# -- EnrichedBrief acceptance and cultural fields in Satirist system prompt --


def test_run_accepts_enriched_brief():
    # run() must accept EnrichedBrief (not StrategyBrief) after migration.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT
        concept, *_ = run(TOPIC, BRIEF, [], [])
    assert isinstance(concept, CartoonConcept)


def test_cultural_angle_in_satirist_system_prompt():
    # cultural_angle from EnrichedBrief must appear in the Satirist system prompt.
    prompt = _build_satirist_system_prompt(BRIEF)
    assert BRIEF.cultural_angle in prompt


def test_culturally_loaded_references_in_satirist_system_prompt():
    # All culturally_loaded_references must appear in the Satirist system prompt.
    prompt = _build_satirist_system_prompt(BRIEF)
    assert all(ref in prompt for ref in BRIEF.culturally_loaded_references)


# -- CartoonConcept.image_prompt field name preserved --


def test_cartoon_concept_image_prompt_field_name_unchanged():
    # CartoonConcept.image_prompt Python attribute must remain 'image_prompt'.
    concept = CartoonConcept(full_text="text", image_prompt="prompt", iteration=1)
    assert hasattr(concept, "image_prompt")
    assert concept.image_prompt == "prompt"


# -- error propagation from ParallelPanel --


def test_run_propagates_timeout_error():
    # TimeoutError from ParallelPanel must reach the caller so the pipeline exits.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.side_effect = TimeoutError("timeout")
        with pytest.raises(TimeoutError):
            run(TOPIC, BRIEF, [], [])


def test_run_propagates_runtime_error():
    # RuntimeError (all models exhausted) must reach the caller so the pipeline exits.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.side_effect = RuntimeError("all models exhausted")
        with pytest.raises(RuntimeError):
            run(TOPIC, BRIEF, [], [])


# -- logging --


def test_run_logs_at_info(caplog):
    # run() must emit an INFO log so the operator can confirm agent_bc completed.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT
        with caplog.at_level(logging.INFO, logger="agents.agent_satirist"):
            _, *_ = run(TOPIC, BRIEF, [], [])
    assert any(r.levelno == logging.INFO for r in caplog.records)


# -- tuple return with ConversationLog (T006) --


def test_run_returns_tuple_of_cartoon_concept_and_log():
    # run() must return a 4-tuple: concept, log, telemetry, and resolved CartoonLayout.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT
        result = run(TOPIC, BRIEF, [], [])
    assert isinstance(result, tuple)
    assert len(result) == 4


def test_run_first_element_is_cartoon_concept():
    # The first tuple element must be CartoonConcept so callers can do
    # `concept, log = agent_bc.run(...)` without index lookups.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT
        concept, *_ = run(TOPIC, BRIEF, [], [])
    assert isinstance(concept, CartoonConcept)


def test_run_second_element_is_conversation_log():
    # The second tuple element must be ConversationLog so bundle_writer can write
    # it to bc_log.txt without any transformation by the caller.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT
        _, log, *_ = run(TOPIC, BRIEF, [], [])
    assert isinstance(log, ConversationLog)


def test_run_log_has_loop_name_bc():
    # The ConversationLog must carry loop_name="Satirist/Co-Satirist" so bundle_writer
    # labels the log file header correctly without extra context from the caller.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT
        _, log, *_ = run(TOPIC, BRIEF, [], [])
    assert log.loop_name == "Satirist/Co-Satirist"


def test_run_cartoon_concept_image_prompt_with_loop_output_mock():
    # CartoonConcept.image_prompt must equal the verdict from LoopOutput — confirming
    # the agent correctly unpacks LoopOutput.verdict before constructing CartoonConcept.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT
        concept, *_ = run(TOPIC, BRIEF, [], [])
    assert concept.image_prompt == _VALID_IMAGE_PROMPT


# -- humor config injection into system prompts --

_HUMOR = HumorConfig(
    framer=FramerHumor(
        wordplay_scan=True,
        joke_types=["deadpan", "situational"],
        language_register="vernacular",
    ),
    satirist=SatiristHumor(
        preferred_style="deadpan",
        avoid=["obvious_pun", "broad_slapstick"],
        subversion="high",
        joke_explanation=True,
    ),
    critic=CriticHumor(evaluate_joke_mechanics=True, flag_if_no_subversion=True),
)
_BRIEF_WITH_JOKE_TYPE = EnrichedBrief(
    target_audience="general public",
    output_language="English",
    tone="dry wit",
    cultural_angle="A cat territorial dispute metaphor for housing policy.",
    culturally_loaded_references=["The 2024 rent control protests"],
    joke_type="deadpan",
)


def test_satirist_prompt_includes_preferred_style_when_humor_set():
    # preferred_style from humor config must appear in the Satirist system prompt.
    prompt = _build_satirist_system_prompt(_BRIEF_WITH_JOKE_TYPE, _HUMOR)
    assert "deadpan" in prompt


def test_satirist_prompt_includes_avoid_items_when_humor_set():
    # All avoid items from humor config must appear in the Satirist system prompt.
    prompt = _build_satirist_system_prompt(_BRIEF_WITH_JOKE_TYPE, _HUMOR)
    assert "obvious_pun" in prompt


def test_satirist_prompt_includes_joke_type_from_brief():
    # The joke_type set by the Framer must be surfaced in the Satirist prompt.
    prompt = _build_satirist_system_prompt(_BRIEF_WITH_JOKE_TYPE, _HUMOR)
    assert _BRIEF_WITH_JOKE_TYPE.joke_type in prompt


def test_satirist_prompt_includes_joke_explanation_instruction_when_enabled():
    # When joke_explanation is True, the prompt must mention the joke_explanation block.
    prompt = _build_satirist_system_prompt(_BRIEF_WITH_JOKE_TYPE, _HUMOR)
    assert "joke_explanation" in prompt


def test_satirist_prompt_unchanged_without_humor():
    # Without humor config, the Satirist prompt must not contain comedy directives.
    prompt = _build_satirist_system_prompt(BRIEF)
    assert "COMEDY STYLE" not in prompt
    assert "joke_explanation" not in prompt


# -- aggregator prompt --


def test_aggregator_prompt_identifies_as_chief_editor():
    # _build_aggregator_prompt must establish the "chief editor" role so the aggregator
    # LLM frames its task as editorial selection, not generation.
    prompt = _build_aggregator_prompt(BRIEF)
    assert "chief editor" in prompt.lower()


def test_aggregator_prompt_mentions_target_audience():
    # Aggregator must know the target audience to judge which concept lands better
    # for that specific readership.
    prompt = _build_aggregator_prompt(BRIEF)
    assert BRIEF.target_audience in prompt


def test_aggregator_prompt_instructs_pick():
    # Aggregator prompt must contain the PICK instruction so the model knows the
    # expected output format and ParallelPanel can extract the selection.
    prompt = _build_aggregator_prompt(BRIEF)
    assert "PICK:" in prompt


def test_aggregator_prompt_has_verdict_tags():
    # Aggregator must wrap its output in <verdict> tags so _extract_proposer_verdict
    # can parse the final concept without additional format handling.
    prompt = _build_aggregator_prompt(BRIEF)
    assert "<verdict>" in prompt


# ---------------------------------------------------------------------------
# Multi-panel support (Stage 9)
# ---------------------------------------------------------------------------

_LAYOUT_3H = CartoonLayout(panels=3, direction="horizontal")
_LAYOUT_2V = CartoonLayout(panels=2, direction="vertical")

_VALID_3_PANEL_JSON = json.dumps(
    {
        "panels": 3,
        "layout": "horizontal",
        "content": [
            {
                "scene": "Gata reads the headline",
                "caption": "Day one.",
                "beat": "setup",
            },
            {
                "scene": "Gata raises an eyebrow",
                "caption": "Really?",
                "beat": "escalation",
            },
            {"scene": "Gata flips board", "caption": "Done.", "beat": "punchline"},
        ],
    }
)
_LOOP_OUTPUT_MULTI = LoopOutput(
    verdict=_VALID_3_PANEL_JSON,
    log=ConversationLog(loop_name="Satirist/Co-Satirist"),
)


def test_satirist_prompt_mentions_comic_strip_when_multi_panel():
    # When layout.panels > 1 the TASK section must describe a comic strip, not
    # a single-panel cartoon, so the model knows to produce multi-panel output.
    prompt = _build_satirist_system_prompt(BRIEF, layout_override=_LAYOUT_3H)
    assert "comic strip" in prompt.lower() or "3-panel" in prompt.lower()


def test_satirist_prompt_mentions_json_when_multi_panel():
    # When layout.panels > 1 the TASK section must instruct the model to return JSON
    # so the verdict can be parsed deterministically.
    prompt = _build_satirist_system_prompt(BRIEF, layout_override=_LAYOUT_3H)
    assert "JSON" in prompt


def test_satirist_prompt_single_panel_unchanged_without_layout():
    # Without a layout argument the single-panel TASK text must remain unchanged
    # so all existing invocations continue to produce single-panel output.
    prompt = _build_satirist_system_prompt(BRIEF)
    assert "single-panel" in prompt


def test_run_multi_panel_populates_concept_panels():
    # When layout.panels > 1 and the verdict is valid JSON, run() must return a
    # CartoonConcept.panels populated so the image generator can assemble the strip.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT_MULTI
        concept, *_ = run(TOPIC, BRIEF, [], [], layout_override=_LAYOUT_3H)
    assert concept.panels is not None
    assert len(concept.panels) == 3
    assert concept.panels[0].beat == "setup"
    assert concept.panels[2].beat == "punchline"


def test_run_multi_panel_concept_has_empty_image_prompt():
    # When panels are populated the image_prompt field must be empty — the image
    # generator builds the full prompt from the panels list, not this field.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT_MULTI
        concept, *_ = run(TOPIC, BRIEF, [], [], layout_override=_LAYOUT_3H)
    assert concept.image_prompt == ""


def test_run_multi_panel_fallback_on_malformed_json(caplog):
    # When the verdict is not valid JSON, run() must log WARNING and fall back to
    # a single-panel CartoonConcept so the pipeline always produces some output.
    bad_output = LoopOutput(
        verdict="not valid JSON at all",
        log=ConversationLog(loop_name="Satirist/Co-Satirist"),
    )
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = bad_output
        with caplog.at_level(logging.WARNING, logger="agents.agent_satirist"):
            concept, *_ = run(TOPIC, BRIEF, [], [], layout_override=_LAYOUT_3H)
    assert concept.panels is None
    assert concept.image_prompt == "not valid JSON at all"
    assert any("fall" in r.message.lower() for r in caplog.records)


def test_run_multi_panel_fallback_on_wrong_panel_count(caplog):
    # When verdict JSON has fewer panels than requested, run() must log WARNING and
    # fall back to single-panel — an incomplete strip must not reach the image model.
    two_panels = json.dumps(
        {
            "panels": [
                {"scene": "s1", "caption": "c1", "beat": "setup"},
                {"scene": "s2", "caption": "c2", "beat": "punchline"},
            ]
        }
    )
    short_output = LoopOutput(
        verdict=two_panels, log=ConversationLog(loop_name="Satirist/Co-Satirist")
    )
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = short_output
        with caplog.at_level(logging.WARNING, logger="agents.agent_satirist"):
            concept, *_ = run(TOPIC, BRIEF, [], [], layout_override=_LAYOUT_3H)
    assert concept.panels is None


def test_run_single_panel_unchanged_with_default_layout():
    # run() called without a layout argument must behave exactly as before Stage 9 —
    # returning a CartoonConcept with image_prompt populated and panels=None.
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = _LOOP_OUTPUT
        concept, *_ = run(TOPIC, BRIEF, [], [])
    assert concept.panels is None
    assert concept.image_prompt == _VALID_IMAGE_PROMPT


# ---------------------------------------------------------------------------
# Agent inconvenience level (Stage 10)
# ---------------------------------------------------------------------------

_HUMOR_HIGH_INCONVENIENCE = HumorConfig(
    framer=FramerHumor(),
    satirist=SatiristHumor(inconvenience=80),
    critic=CriticHumor(inconvenience=50),
)

_HUMOR_ZERO_INCONVENIENCE = HumorConfig(
    framer=FramerHumor(),
    satirist=SatiristHumor(inconvenience=0),
    critic=CriticHumor(inconvenience=0),
)


def test_satirist_prompt_includes_inconvenience_when_nonzero():
    # When satirist.inconvenience > 0 the Satirist system prompt must contain
    # the INCONVENIENCE directive so the LLM is pushed toward uncomfortable truths.
    prompt = _build_satirist_system_prompt(BRIEF, _HUMOR_HIGH_INCONVENIENCE)
    assert "INCONVENIENCE" in prompt


def test_satirist_prompt_no_inconvenience_when_zero():
    # When satirist.inconvenience == 0 no INCONVENIENCE directive must appear
    # so existing behavior is fully preserved.
    prompt = _build_satirist_system_prompt(BRIEF, _HUMOR_ZERO_INCONVENIENCE)
    assert "INCONVENIENCE" not in prompt


def test_satirist_prompt_high_inconvenience_mentions_squirm():
    # At inconvenience=80 (high tier) the directive must contain the word "squirm"
    # so the LLM receives the maximum discomfort instruction.
    prompt = _build_satirist_system_prompt(BRIEF, _HUMOR_HIGH_INCONVENIENCE)
    assert "squirm" in prompt.lower()


# ---------------------------------------------------------------------------
# Cartoon title (Stage 27)
# ---------------------------------------------------------------------------

_VERDICT_WITH_TITLE = json.dumps(
    {
        "panels": 1,
        "layout": "horizontal",
        "title": "G7 Nods, AI Thanks Them",
        "content": [{"scene": _VALID_IMAGE_PROMPT, "caption": "Noted.", "beat": ""}],
    }
)
_VERDICT_WITHOUT_TITLE = json.dumps(
    {
        "panels": 1,
        "layout": "horizontal",
        "content": [{"scene": _VALID_IMAGE_PROMPT, "caption": "Noted.", "beat": ""}],
    }
)


def test_parse_verdict_extracts_title_field():
    # When the Satirist JSON includes "title", CartoonConcept.title must be populated
    # so the image generator can overlay it without extra string manipulation.
    loop_out = LoopOutput(
        verdict=_VERDICT_WITH_TITLE,
        log=ConversationLog(loop_name="Satirist/Co-Satirist"),
    )
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = loop_out
        concept, *_ = run(TOPIC, BRIEF, [], [])
    assert concept.title == "G7 Nods, AI Thanks Them"


def test_parse_verdict_title_empty_when_missing_from_json():
    # When the Satirist JSON omits "title", CartoonConcept.title must be "" before the
    # fallback in run() applies — confirming _parse_verdict does not invent a title.
    import agents.agent_satirist as sat
    concept, _ = sat._parse_verdict(_VERDICT_WITHOUT_TITLE, None)
    assert concept.title == ""


def test_run_falls_back_to_topic_when_title_missing():
    # run() must set concept.title = topic when the Satirist omits the title field
    # so the image always has a title even if JSON parsing is partial.
    loop_out = LoopOutput(
        verdict=_VERDICT_WITHOUT_TITLE,
        log=ConversationLog(loop_name="Satirist/Co-Satirist"),
    )
    with patch("agents.agent_satirist.ParallelPanel") as MockPanel:
        MockPanel.return_value.run.return_value = loop_out
        concept, *_ = run(TOPIC, BRIEF, [], [])
    assert concept.title == TOPIC


def test_satirist_prompt_includes_title_instruction():
    # The output format rules must mention "title" so the Satirist knows to include it
    # in the JSON — without this the field would never be generated.
    prompt = _build_satirist_system_prompt(BRIEF)
    assert '"title"' in prompt
