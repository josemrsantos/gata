import logging
from unittest.mock import MagicMock, patch

import pytest

from agents.agent_cultural_strategist import run
from core.types import ConversationLog, EnrichedBrief, LoopOutput, StrategyBrief


@pytest.fixture(autouse=True)
def _mock_infer_mood():
    # infer_mood() makes live Gemini calls; patch it out so unit tests stay offline.
    with patch("agents.agent_cultural_strategist.infer_mood", return_value=None):
        yield

_SEED = StrategyBrief(
    target_audience="Portuguese adults",
    output_language="Portuguese",
    tone="sarcastic",
)
_TOPIC = "Housing crisis in Lisbon"
_VALID_VERDICT = (
    "CULTURAL ANGLE: Lisbon housing crisis as cat territorial dispute.\n"
    "REFERENCES:\n"
    "- The 2024 rent control protests\n"
    "- Airbnb landlord memes circulated on Portuguese social media"
)
_LOOP_OUTPUT = LoopOutput(
    verdict=_VALID_VERDICT,
    log=ConversationLog(loop_name="Cultural Strategist"),
)
# Empty provider lists are fine since DualPersonaLoop is mocked in all tests below
_MP = []


# -- happy path: EnrichedBrief produced correctly --


def test_run_returns_enriched_brief_type():
    # run() must return an EnrichedBrief as the first tuple element, not the raw string.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        enriched_brief, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert isinstance(enriched_brief, EnrichedBrief)


def test_run_seed_fields_locked_in_enriched_brief():
    # The three seed fields must be carried unchanged — Agent 0 must not overwrite them.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        enriched_brief, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert enriched_brief.target_audience == _SEED.target_audience
    assert enriched_brief.output_language == _SEED.output_language
    assert enriched_brief.tone == _SEED.tone


def test_run_parses_cultural_angle():
    # cultural_angle must contain the text from the CULTURAL ANGLE: section.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        enriched_brief, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert "cat territorial dispute" in enriched_brief.cultural_angle


def test_run_parses_references_as_list():
    # culturally_loaded_references must be a list with one entry per bullet point.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        enriched_brief, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert isinstance(enriched_brief.culturally_loaded_references, list)
    assert len(enriched_brief.culturally_loaded_references) == 2
    assert any(
        "rent control" in ref for ref in enriched_brief.culturally_loaded_references
    )


def test_run_accepts_single_reference():
    # Minimum valid output is one reference; the pipeline must not require more.
    single_ref = "CULTURAL ANGLE: A valid angle.\nREFERENCES:\n- Only one reference"
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = LoopOutput(
            verdict=single_ref, log=ConversationLog(loop_name="Cultural Strategist")
        )
        enriched_brief, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert len(enriched_brief.culturally_loaded_references) == 1


# -- validation: empty fields raise ValueError --


def test_run_raises_value_error_on_empty_cultural_angle():
    # An empty cultural_angle means enrichment failed; the pipeline must not continue.
    empty_angle = "CULTURAL ANGLE: \nREFERENCES:\n- Some reference"
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = LoopOutput(
            verdict=empty_angle, log=ConversationLog(loop_name="Cultural Strategist")
        )
        with pytest.raises(ValueError, match="cultural_angle"):
            run(_TOPIC, _SEED, _MP, _MP)


def test_run_raises_value_error_on_empty_references_list():
    # An empty references list means enrichment failed; the pipeline must not continue.
    no_refs = "CULTURAL ANGLE: A valid angle.\nREFERENCES:\n"
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = LoopOutput(
            verdict=no_refs, log=ConversationLog(loop_name="Cultural Strategist")
        )
        with pytest.raises(ValueError, match="culturally_loaded_references"):
            run(_TOPIC, _SEED, _MP, _MP)


# -- error propagation from DualPersonaLoop --


def test_run_propagates_timeout_error():
    # TimeoutError from DualPersonaLoop must reach the caller so the pipeline exits.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.side_effect = TimeoutError("timeout after 900s")
        with pytest.raises(TimeoutError):
            run(_TOPIC, _SEED, _MP, _MP)


def test_run_propagates_runtime_error():
    # RuntimeError (all models exhausted) must reach the caller so the pipeline exits.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.side_effect = RuntimeError("all models exhausted")
        with pytest.raises(RuntimeError):
            run(_TOPIC, _SEED, _MP, _MP)


# -- logging: FR-011 --


def test_run_logs_enriched_brief_at_info(caplog):
    # FR-011: the enriched brief must be logged at INFO so the operator can inspect
    # the cultural context without running the full pipeline to image output.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        with caplog.at_level(logging.INFO, logger="agents.agent_cultural_strategist"):
            _, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert any("cultural_angle" in m for m in info_messages)


# -- tuple return with ConversationLog (T005) --


def test_run_returns_tuple_of_enriched_brief_log_and_telemetry():
    # run() must return a 3-tuple: (EnrichedBrief, ConversationLog, AgentTelemetry).
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        result = run(_TOPIC, _SEED, _MP, _MP)
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_run_first_element_is_enriched_brief():
    # The first tuple element must be the EnrichedBrief so callers can unpack with
    # `enriched_brief, log, telemetry = agent_0.run(...)` without index lookups.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        enriched_brief, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert isinstance(enriched_brief, EnrichedBrief)


def test_run_second_element_is_conversation_log():
    # The second tuple element must be the ConversationLog from the DualPersonaLoop
    # so bundle_writer can write it to agent0_log.txt.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        _, log, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert isinstance(log, ConversationLog)


def test_run_log_has_loop_name_cultural_strategist():
    # The ConversationLog must carry loop_name="Cultural Strategist" so bundle_writer
    # labels the file header without needing extra context from the caller.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        _, log, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert log.loop_name == "Cultural Strategist"


def test_run_enriched_brief_content_unchanged_with_loop_output_mock():
    # EnrichedBrief content must be correctly parsed even when the mock returns a
    # LoopOutput — confirming the agent unpacks verdict before parsing.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        enriched_brief, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert "cat territorial dispute" in enriched_brief.cultural_angle
    assert enriched_brief.target_audience == _SEED.target_audience


# -- joke_type extraction --


_VERDICT_WITH_JOKE_TYPE = (
    "CULTURAL ANGLE: Lisbon housing crisis as cat territorial dispute.\n"
    "REFERENCES:\n"
    "- The 2024 rent control protests\n"
    "- Airbnb landlord memes circulated on Portuguese social media\n"
    "JOKE TYPE: situational"
)
_LOOP_OUTPUT_WITH_JOKE_TYPE = LoopOutput(
    verdict=_VERDICT_WITH_JOKE_TYPE,
    log=ConversationLog(loop_name="Cultural Strategist"),
)


def test_run_extracts_joke_type_when_present():
    # When the Framer verdict includes a JOKE TYPE field, it must appear in joke_type.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT_WITH_JOKE_TYPE
        enriched_brief, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert enriched_brief.joke_type == "situational"


def test_run_joke_type_defaults_to_empty_when_absent_from_verdict():
    # When the verdict has no JOKE TYPE, joke_type must be empty string — not an error.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT
        enriched_brief, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    assert enriched_brief.joke_type == ""


def test_run_references_not_contaminated_by_joke_type_line():
    # JOKE TYPE must not be parsed as a reference bullet — references must stay clean.
    with patch("agents.agent_cultural_strategist.DualPersonaLoop") as MockLoop:
        MockLoop.return_value.run.return_value = _LOOP_OUTPUT_WITH_JOKE_TYPE
        enriched_brief, _, _ = run(_TOPIC, _SEED, _MP, _MP)
    refs = enriched_brief.culturally_loaded_references
    assert not any("JOKE TYPE" in ref for ref in refs)
    assert len(enriched_brief.culturally_loaded_references) == 2


# ---------------------------------------------------------------------------
# Framer inconvenience level (Stage 10)
# ---------------------------------------------------------------------------


def test_framer_prompt_includes_inconvenience_when_nonzero():
    # When framer.inconvenience > 0 the Framer system prompt must contain the
    # INCONVENIENCE directive so the cultural angle is pushed toward discomfort.
    from agents.agent_cultural_strategist import _build_framer_system_prompt
    from core.types import CriticHumor, FramerHumor, HumorConfig, SatiristHumor

    humor = HumorConfig(
        framer=FramerHumor(inconvenience=70),
        satirist=SatiristHumor(),
        critic=CriticHumor(),
    )
    prompt = _build_framer_system_prompt(humor)
    assert "INCONVENIENCE" in prompt


def test_framer_prompt_no_inconvenience_when_zero():
    # When framer.inconvenience == 0 no INCONVENIENCE directive appears — the
    # framer prompt is unchanged from baseline behavior.
    from agents.agent_cultural_strategist import _build_framer_system_prompt
    from core.types import CriticHumor, FramerHumor, HumorConfig, SatiristHumor

    humor = HumorConfig(
        framer=FramerHumor(inconvenience=0),
        satirist=SatiristHumor(),
        critic=CriticHumor(),
    )
    prompt = _build_framer_system_prompt(humor)
    assert "INCONVENIENCE" not in prompt


# ---------------------------------------------------------------------------
# infer_audiences — single-audience default (Stage 016)
# ---------------------------------------------------------------------------


def test_infer_audiences_returns_exactly_one_profile_on_success():
    # infer_audiences() must return a list with exactly one AudienceProfile when
    # the LLM responds correctly — the prompt now asks for a single audience.
    from agents.agent_cultural_strategist import infer_audiences

    mock_response = MagicMock()
    mock_response.text = (
        '[{"name":"swiss","audience":"Swiss public",'
        '"language":"Swiss German","tone":"dry Swiss wit"}]'
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        profiles = infer_audiences("Swiss election results")
    assert len(profiles) == 1
    assert profiles[0].name == "swiss"


def test_infer_audiences_fallback_returns_one_profile():
    # On LLM failure the fallback list must contain exactly one entry so the
    # "main + UK" shape is preserved even in degraded mode.
    from agents.agent_cultural_strategist import infer_audiences

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("network error")
    with patch("llm.gemini._get_client", return_value=mock_client):
        profiles = infer_audiences("some topic")
    assert len(profiles) == 1


def test_infer_audiences_system_prompt_asks_for_single_audience():
    # The system prompt must ask for the single most relevant audience, not a list
    # of 2-4, so the LLM doesn't return more than one entry.
    from agents.agent_cultural_strategist import _AUDIENCE_INFERENCE_SYSTEM

    assert "single" in _AUDIENCE_INFERENCE_SYSTEM.lower()
    assert "2 to 4" not in _AUDIENCE_INFERENCE_SYSTEM
