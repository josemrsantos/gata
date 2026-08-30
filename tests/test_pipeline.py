import logging
import re
from unittest.mock import MagicMock, patch

import pytest

import pipeline
from core.types import (
    AgentTelemetry,
    CartoonConcept,
    CartoonLayout,
    Community,
    ConversationLog,
    EnrichedBrief,
    Headline,
    StrategyBrief,
)

FAKE_CONCEPT = CartoonConcept(
    full_text="A cat at the UN.",
    image_prompt="A cat at the UN.",
    iteration=1,
)
FAKE_AGENT0_LOG = ConversationLog(loop_name="Cultural Strategist")
FAKE_BC_LOG = ConversationLog(loop_name="Satirist/Critic")

# Single-topic communities keep topic selection deterministic without patching
# random.choice.
COMMUNITY_UK = Community(
    name="uk-tech-engineers",
    target_audience="UK tech workers",
    output_language="English",
    tone="dry wit",
    topics=["AI hype"],
)

COMMUNITY_PT = Community(
    name="portuguese-adults",
    target_audience="Portuguese adults",
    output_language="Portuguese",
    tone="sharp satire",
    topics=["Housing crisis"],
)

FAKE_COMMUNITIES = [COMMUNITY_UK, COMMUNITY_PT]

FAKE_HEADLINE = Headline(
    title="AI hype reaches peak",
    abstract="",
    source="newsapi",
    published_at="2026-06-11",
    social_score=0.0,
)

FAKE_ENRICHED_BRIEF = EnrichedBrief(
    target_audience="UK tech workers",
    output_language="English",
    tone="dry wit",
    cultural_angle="A satirical angle about AI hype in the UK tech scene.",
    culturally_loaded_references=["ChatGPT moment", "Tech layoffs 2023"],
)

FAKE_AGENT0_TEL = AgentTelemetry(
    agent_name="Cultural Strategist", duration_seconds=0.0, iterations=1
)
FAKE_BC_TEL = AgentTelemetry(
    agent_name="Satirist/Co-Satirist", duration_seconds=0.0, iterations=1
)
FAKE_IMAGE_TEL = AgentTelemetry(
    agent_name="Image Generator", duration_seconds=0.0, iterations=1
)
FAKE_EVAL_TEL = AgentTelemetry(
    agent_name="Image Evaluator", duration_seconds=0.0, iterations=1
)
_FAKE_EVAL_RESULT = MagicMock()
_FAKE_EVAL_RESULT.verdict = "APPROVED"

# Minimal env vars so the API-key guard in main() does not exit early.
ENV = {"ANTHROPIC_API_KEY": "fake-anthropic", "GEMINI_API_KEY": "fake-gemini"}


# -- API-key guard --


def test_pipeline_exits_when_anthropic_key_missing(caplog, tmp_path):
    # main() must log ERROR and exit 1 when ANTHROPIC_API_KEY is not set.
    caplog.set_level(logging.ERROR, logger="pipeline")
    with (
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": "k"}),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        pipeline.main()
    assert exc_info.value.code == 1
    assert any("ANTHROPIC_API_KEY" in r.message for r in caplog.records)


def test_pipeline_exits_when_gemini_key_missing(caplog, tmp_path):
    # main() must log ERROR and exit 1 when GEMINI_API_KEY is not set.
    caplog.set_level(logging.ERROR, logger="pipeline")
    with (
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k", "GEMINI_API_KEY": ""}),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        pipeline.main()
    assert exc_info.value.code == 1
    assert any("GEMINI_API_KEY" in r.message for r in caplog.records)


# -- --community: named community mode --


def test_community_mode_selects_correct_brief():
    # --community passes the named community's seed brief to agent_0, not another's.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ) as mock_agent_0,
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()

    topic, seed_brief = mock_agent_0.call_args.args
    assert topic in COMMUNITY_UK.topics
    assert seed_brief == COMMUNITY_UK.to_brief()


def test_community_mode_agent_bc_receives_enriched_brief():
    # agent_bc.run() must receive the EnrichedBrief returned by agent_0.run().
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ) as mock_bc,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()

    _, brief = mock_bc.call_args.args
    assert brief is FAKE_ENRICHED_BRIEF


def test_community_mode_output_path():
    # --community builds the path as output/{name}/{language}/{topic}.png.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()

    output_path = mock_gen.call_args.args[1]
    assert output_path == "output/uk-tech-engineers/english_ai_hype.png"


# ---------------------------------------------------------------------------
# T012 — Named community backwards compat (US3)
# ---------------------------------------------------------------------------


def test_named_community_calls_get_topics_not_free_text():
    # An exact --community name match must call trend_scout.get_topics(), not
    # get_topics_for_description() — the two paths must never be confused.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics",
            return_value=([FAKE_HEADLINE], "seed"),
        ) as mock_get_topics,
        patch(
            "pipeline.trend_scout.get_topics_for_description",
            create=True,
        ) as mock_free,
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    mock_get_topics.assert_called_once()
    mock_free.assert_not_called()


def test_named_community_output_folder_uses_community_name():
    # A named community's bundle must land under the community name folder —
    # not a sanitized description — preserving the pre-Stage-8 output structure.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics",
            return_value=([FAKE_HEADLINE], "seed"),
        ),
        patch("pipeline.trend_scout.get_topics_for_description", create=True),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    output_path = mock_gen.call_args.args[1]
    assert "uk-tech-engineers" in output_path
    assert "us_community" not in output_path


# -- Random community mode (no arguments) --


def test_random_mode_calls_choice_on_communities():
    # No args → random.choice is called on the full communities list to select one.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.random.choice",
            side_effect=[COMMUNITY_PT, "Housing crisis"],
        ) as mock_choice,
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()

    mock_choice.assert_any_call(FAKE_COMMUNITIES)


def test_random_mode_uses_selected_community_topics():
    # The topic is drawn from the selected community's topics, not another community's.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.random.choice",
            side_effect=[COMMUNITY_PT, "Housing crisis"],
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()

    output_path = mock_gen.call_args.args[1]
    assert output_path == "output/portuguese-adults/portuguese_housing_crisis.png"


# -- Manual mode (--topic, --audience, --language, --tone) --

_MANUAL_ARGV = [
    "pipeline.py",
    "--topic",
    "AI hype",
    "--audience",
    "developers",
    "--language",
    "English",
    "--tone",
    "dry",
]


def test_manual_mode_does_not_call_trend_scout():
    # Manual --topic flag must bypass Trend Scout entirely, preserving RULE 12.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", _MANUAL_ARGV),
        patch("pipeline.load_communities"),
        patch("agents.trend_scout.get_topics") as mock_ts,
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()

    mock_ts.assert_not_called()


def test_manual_mode_does_not_load_communities():
    # All four manual flags → pipeline runs without touching communities.yaml.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", _MANUAL_ARGV),
        patch("pipeline.load_communities") as mock_load,
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()

    mock_load.assert_not_called()


def test_manual_mode_output_path():
    # Manual mode saves the image to output/manual/{language}/{sanitized_topic}.png.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", _MANUAL_ARGV),
        patch("pipeline.load_communities"),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()

    output_path = mock_gen.call_args.args[1]
    assert output_path == "output/manual/english_ai_hype.png"


def test_manual_mode_missing_flag_exits_1():
    # Any missing manual flag exits code 1 before any agent call.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            [
                "pipeline.py",
                "--topic",
                "AI hype",
                "--audience",
                "developers",
                "--language",
                "English",
            ],
        ),
        patch("core.runner.agent_cultural_strategist.run") as mock_a0,
        patch("core.runner.agent_satirist.run") as mock_run,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
    ):
        with pytest.raises(SystemExit) as exc_info:
            pipeline.main()

    assert exc_info.value.code == 1
    mock_a0.assert_not_called()
    mock_run.assert_not_called()
    mock_gen.assert_not_called()


def test_community_with_context_flag_exits_1():
    # --community combined with --audience exits code 1 before any agent call —
    # audience/language/tone conflict with community-based brief inference.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            [
                "pipeline.py",
                "--community",
                "uk-tech-engineers",
                "--audience",
                "developers",
            ],
        ),
        patch("core.runner.agent_cultural_strategist.run") as mock_a0,
        patch("core.runner.agent_satirist.run") as mock_run,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
    ):
        with pytest.raises(SystemExit) as exc_info:
            pipeline.main()

    assert exc_info.value.code == 1
    mock_a0.assert_not_called()
    mock_run.assert_not_called()
    mock_gen.assert_not_called()


# -- Config validation — ValueError from load_communities exits 1 --


def test_config_missing_file_exits_1():
    # A missing communities.yaml causes exit 1 before any agent is called.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py"]),
        patch(
            "pipeline.load_communities",
            side_effect=ValueError("Config file not found: communities.yaml"),
        ),
        patch("core.runner.agent_cultural_strategist.run") as mock_a0,
        patch("core.runner.agent_satirist.run") as mock_run,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
    ):
        with pytest.raises(SystemExit) as exc_info:
            pipeline.main()

    assert exc_info.value.code == 1
    mock_a0.assert_not_called()
    mock_run.assert_not_called()
    mock_gen.assert_not_called()


def test_config_invalid_yaml_exits_1():
    # A malformed communities.yaml causes exit 1 before any agent is called.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py"]),
        patch(
            "pipeline.load_communities",
            side_effect=ValueError("communities.yaml is not valid YAML"),
        ),
        patch("core.runner.agent_cultural_strategist.run") as mock_a0,
        patch("core.runner.agent_satirist.run") as mock_run,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
    ):
        with pytest.raises(SystemExit) as exc_info:
            pipeline.main()

    assert exc_info.value.code == 1
    mock_a0.assert_not_called()
    mock_run.assert_not_called()
    mock_gen.assert_not_called()


def test_config_duplicate_name_exits_1():
    # Duplicate community names in communities.yaml cause exit 1 before any agent call.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py"]),
        patch(
            "pipeline.load_communities",
            side_effect=ValueError("Duplicate community name: 'my-community'"),
        ),
        patch("core.runner.agent_cultural_strategist.run") as mock_a0,
        patch("core.runner.agent_satirist.run") as mock_run,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
    ):
        with pytest.raises(SystemExit) as exc_info:
            pipeline.main()

    assert exc_info.value.code == 1
    mock_a0.assert_not_called()
    mock_run.assert_not_called()
    mock_gen.assert_not_called()


# -- Agent 0 call ordering and error propagation (T008) --


def test_agent_0_called_before_agent_bc():
    # agent_0.run() must be called before agent_bc.run() in every pipeline path.
    call_order: list[str] = []
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            side_effect=lambda *a, **kw: (
                call_order.append("agent_cultural_strategist")
                or (FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL)
            ),
        ),
        patch(
            "core.runner.agent_satirist.run",
            side_effect=lambda *a, **kw: (
                call_order.append("agent_satirist")
                or (FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None)
            ),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
        patch("os.makedirs"),
    ):
        pipeline.main()

    assert call_order == ["agent_cultural_strategist", "agent_satirist"]


def test_pipeline_exits_before_agent_bc_on_agent_0_runtime_error():
    # RuntimeError from agent_0.run() must exit the pipeline before agent_bc.run().
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            side_effect=RuntimeError("all models exhausted"),
        ),
        patch("core.runner.agent_satirist.run") as mock_bc,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
        patch("os.makedirs"),
    ):
        with pytest.raises(SystemExit):
            pipeline.main()

    mock_bc.assert_not_called()
    mock_gen.assert_not_called()


def test_pipeline_exits_before_agent_bc_on_agent_0_timeout_error():
    # TimeoutError from agent_0.run() must exit the pipeline before agent_bc.run().
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            side_effect=TimeoutError("timeout after 900s"),
        ),
        patch("core.runner.agent_satirist.run") as mock_bc,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
        patch("os.makedirs"),
    ):
        with pytest.raises(SystemExit):
            pipeline.main()

    mock_bc.assert_not_called()
    mock_gen.assert_not_called()


# -- bundle_writer integration (T013) --


def test_write_bundle_called_after_agent_d(tmp_path):
    # write_bundle must be called after agent_d.generate() completes so the cartoon
    # image is saved before any bundle file is written.
    call_order: list[str] = []
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            side_effect=lambda *a, **kw: (
                call_order.append("agent_image_generator")
                or ("fake.png", FAKE_IMAGE_TEL)
            ),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch(
            "core.bundle_writer.write_bundle",
            side_effect=lambda *a, **kw: call_order.append("write_bundle") or "",
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()

    assert call_order == ["agent_image_generator", "write_bundle"]


def test_write_bundle_receives_correct_output_path(tmp_path):
    # write_bundle must receive the same output_path as agent_d.generate so the
    # bundle folder is co-located with the image file.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_wb,
        patch("os.makedirs"),
    ):
        pipeline.main()

    output_path = mock_wb.call_args.args[0]
    assert output_path == "output/uk-tech-engineers/english_ai_hype.png"


def test_write_bundle_receives_agent0_and_bc_logs(tmp_path):
    # write_bundle must receive both ConversationLog objects from agent_0 and agent_bc
    # so it can write both log files without additional lookups.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_wb,
        patch("os.makedirs"),
    ):
        pipeline.main()

    _, agent0_log, bc_log = mock_wb.call_args.args[:3]
    assert agent0_log is FAKE_AGENT0_LOG
    assert bc_log is FAKE_BC_LOG


def test_write_bundle_receives_image_prompt(tmp_path):
    # write_bundle must receive concept.image_prompt so it can write prompt_card.txt
    # with the exact prompt that was sent to the image generator.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_wb,
        patch("os.makedirs"),
    ):
        pipeline.main()

    image_prompt = mock_wb.call_args.args[4]
    assert image_prompt == FAKE_CONCEPT.image_prompt


def test_write_bundle_called_with_agent0_log_on_bc_failure(tmp_path):
    # When agent_bc.run() raises, write_bundle must still be called with the
    # agent0_log that was collected — partial bundle behaviour per FR-010.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch("core.runner.agent_satirist.run", side_effect=RuntimeError("bc failed")),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_wb,
        patch("os.makedirs"),
    ):
        with pytest.raises(SystemExit):
            pipeline.main()

    assert mock_wb.called
    agent0_log = mock_wb.call_args.args[1]
    assert agent0_log is FAKE_AGENT0_LOG


# ---------------------------------------------------------------------------
# T005 — Free-text community path (pipeline integration)
# ---------------------------------------------------------------------------

_FREE_TEXT_DESC = "US community that dislikes Trump"

_INFERRED_BRIEF = StrategyBrief(
    target_audience="US adults critical of Trump",
    output_language="English",
    tone="sharp political satire",
)

_FREE_TEXT_HEADLINE = Headline(
    title="Trump signs executive order",
    abstract="",
    source="newsapi",
    published_at="2026-06-11",
    social_score=0.0,
)


def test_free_text_community_calls_get_topics_for_description():
    # When --community doesn't match any communities.yaml entry, the pipeline must
    # call trend_scout.get_topics_for_description — not exit 1 as it did before.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", _FREE_TEXT_DESC]),
        patch("os.path.exists", return_value=True),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics_for_description",
            return_value=([_FREE_TEXT_HEADLINE], _INFERRED_BRIEF, "trend_scout"),
            create=True,
        ) as mock_gttfd,
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    mock_gttfd.assert_called_once_with(_FREE_TEXT_DESC)


def test_free_text_community_output_path_uses_sanitized_description():
    # The output folder must be derived from the sanitized description string so
    # bundles land under a recognisable folder rather than a generic "manual/" path.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", _FREE_TEXT_DESC]),
        patch("os.path.exists", return_value=True),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics_for_description",
            return_value=([_FREE_TEXT_HEADLINE], _INFERRED_BRIEF, "trend_scout"),
            create=True,
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    output_path = mock_gen.call_args.args[1]
    assert "us_community_that_dislikes_trump" in output_path
    assert "manual" not in output_path


def test_free_text_community_pipeline_uses_inferred_brief():
    # agent_cultural_strategist.run must receive the StrategyBrief inferred from the
    # description so all downstream agents have the correct audience/language/tone.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", _FREE_TEXT_DESC]),
        patch("os.path.exists", return_value=True),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics_for_description",
            return_value=([_FREE_TEXT_HEADLINE], _INFERRED_BRIEF, "trend_scout"),
            create=True,
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ) as mock_agent0,
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    _, brief_passed = mock_agent0.call_args.args
    assert brief_passed == _INFERRED_BRIEF


# ---------------------------------------------------------------------------
# T014 — Empty --community string validation (US4)
# ---------------------------------------------------------------------------


def test_empty_community_string_exits_1(caplog):
    # --community "" must exit 1 and log an error before any API call is made;
    # an empty description is a user mistake, not a free-text community.
    caplog.set_level(logging.ERROR, logger="pipeline")
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", ""]),
        patch("core.runner.agent_cultural_strategist.run") as mock_a0,
        patch("core.runner.agent_satirist.run") as mock_run,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
    ):
        with pytest.raises(SystemExit) as exc_info:
            pipeline.main()
    assert exc_info.value.code == 1
    mock_a0.assert_not_called()
    mock_run.assert_not_called()
    mock_gen.assert_not_called()
    assert any("empty" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# T015 — Missing communities.yaml is not a crash (US4)
# ---------------------------------------------------------------------------


def test_missing_communities_yaml_triggers_free_text_path():
    # When communities.yaml is absent, free-text inference must proceed without
    # error — the missing file is treated as an empty community list, not a crash.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "tech enthusiasts"]),
        patch("os.path.exists", return_value=False),
        patch("pipeline.load_communities") as mock_load,
        patch(
            "pipeline.trend_scout.get_topics_for_description",
            return_value=([_FREE_TEXT_HEADLINE], _INFERRED_BRIEF, "trend_scout"),
            create=True,
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# T016 — Empty headline list from free-text path exits 1 (US4)
# ---------------------------------------------------------------------------


def test_free_text_empty_headlines_exits_1():
    # When get_topics_for_description returns no headlines, the pipeline must
    # exit 1 and not call any agent — no partial bundle should be started.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", _FREE_TEXT_DESC]),
        patch("os.path.exists", return_value=True),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics_for_description",
            return_value=([], _INFERRED_BRIEF, "none"),
            create=True,
        ),
        patch("core.runner.agent_cultural_strategist.run") as mock_a0,
        patch("core.runner.agent_satirist.run") as mock_run,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
    ):
        with pytest.raises(SystemExit) as exc_info:
            pipeline.main()
    assert exc_info.value.code == 1
    mock_a0.assert_not_called()
    mock_run.assert_not_called()
    mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# Stage 9 — --panels and --layout CLI validation (T006, FR-010)
# ---------------------------------------------------------------------------


def test_panels_zero_exits_1(caplog):
    # --panels 0 must exit 1 before any API call — panel count below 1 is invalid.
    caplog.set_level(logging.ERROR, logger="pipeline")
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--panels", "0"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        pipeline.main()
    assert exc_info.value.code == 1
    assert any("panels" in r.message.lower() for r in caplog.records)


def test_panels_five_exits_1(caplog):
    # --panels 5 must exit 1 before any API call — panel count above 4 is invalid.
    caplog.set_level(logging.ERROR, logger="pipeline")
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--panels", "5"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        pipeline.main()
    assert exc_info.value.code == 1


def test_layout_invalid_string_exits_1(caplog):
    # --layout with an unrecognised string must exit 1 before any API call.
    caplog.set_level(logging.ERROR, logger="pipeline")
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--panels", "3", "--layout", "diagonal"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        pipeline.main()
    assert exc_info.value.code == 1
    assert any("layout" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# Stage 9 — CartoonLayout passed to agent_satirist (T015)
# ---------------------------------------------------------------------------

_COMMUNITY_WITH_PANELS = Community(
    name="uk-tech-engineers",
    target_audience="UK tech workers",
    output_language="English",
    tone="dry wit",
    topics=["AI hype"],
    panels=3,
    layout="horizontal",
)


def test_panels_cli_flag_passed_as_cartoon_layout_to_satirist():
    # CartoonLayout constructed from --panels 3 --layout horizontal must be passed as
    # the layout kwarg to agent_satirist.run() so it uses the multi-panel prompt.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            [
                "pipeline.py",
                "--community",
                "uk-tech-engineers",
                "--panels",
                "3",
                "--layout",
                "horizontal",
            ],
        ),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics",
            return_value=([FAKE_HEADLINE], "seed"),
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ) as mock_satirist,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    layout_arg = mock_satirist.call_args.kwargs.get("layout_override")
    assert isinstance(layout_arg, CartoonLayout)
    assert layout_arg.panels == 3
    assert layout_arg.direction == "horizontal"


def test_community_panels_config_used_when_no_cli_flag():
    # When no --panels CLI flag is given, the community's panels field must be used
    # to build CartoonLayout so community-level panel config works without CLI flags.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch(
            "pipeline.load_communities",
            return_value=[_COMMUNITY_WITH_PANELS, COMMUNITY_PT],
        ),
        patch(
            "pipeline.trend_scout.get_topics",
            return_value=([FAKE_HEADLINE], "seed"),
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ) as mock_satirist,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    layout_arg = mock_satirist.call_args.kwargs.get("layout_override")
    assert isinstance(layout_arg, CartoonLayout)
    assert layout_arg.panels == 3


def test_cli_panels_overrides_community_config():
    # --panels 2 must override a community's panels=3 config so CLI always takes
    # precedence over community-level panel configuration (FR-004).
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            ["pipeline.py", "--community", "uk-tech-engineers", "--panels", "2"],
        ),
        patch(
            "pipeline.load_communities",
            return_value=[_COMMUNITY_WITH_PANELS, COMMUNITY_PT],
        ),
        patch(
            "pipeline.trend_scout.get_topics",
            return_value=([FAKE_HEADLINE], "seed"),
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ) as mock_satirist,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    layout_arg = mock_satirist.call_args.kwargs.get("layout_override")
    assert layout_arg.panels == 2


# ---------------------------------------------------------------------------
# Stage 9 — Filename prefix for multi-panel (T017, FR-008)
# ---------------------------------------------------------------------------


def test_multi_panel_filename_has_nh_prefix():
    # When panels=3 and direction="horizontal", the output filename must begin
    # with "3h_" so multi-panel files are distinguishable from single-panel ones.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            [
                "pipeline.py",
                "--community",
                "uk-tech-engineers",
                "--panels",
                "3",
                "--layout",
                "horizontal",
            ],
        ),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics",
            return_value=([FAKE_HEADLINE], "seed"),
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    output_path = mock_gen.call_args.args[1]
    filename = output_path.split("/")[-1]
    assert filename.startswith("3h_")


def test_single_panel_filename_has_no_prefix():
    # When no --panels flag is given (default panels=1), the filename must NOT
    # have any prefix — backwards-compat requires no change to single-panel filenames.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--community", "uk-tech-engineers"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics",
            return_value=([FAKE_HEADLINE], "seed"),
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    output_path = mock_gen.call_args.args[1]
    filename = output_path.split("/")[-1]
    # Single-panel filenames start with the language slug, not a panel prefix
    assert not filename[0].isdigit()


# ---------------------------------------------------------------------------
# Stage 11 — Community + topic mode (T017)
# ---------------------------------------------------------------------------

_COMMUNITY_TOPIC_BRIEF = StrategyBrief(
    target_audience="UK political observers",
    output_language="English",
    tone="dry British wit",
)


def test_community_topic_mode_skips_trend_scout():
    # --community + --topic must skip Trend Scout entirely; topic comes from --topic
    # and is passed straight to the agents — no get_topics or inference calls.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            [
                "pipeline.py",
                "--community",
                "Some free-text community",
                "--topic",
                "House burns down",
            ],
        ),
        patch("os.path.exists", return_value=False),
        patch(
            "pipeline.trend_scout.infer_brief_from_description",
            return_value=_COMMUNITY_TOPIC_BRIEF,
        ),
        patch("pipeline.trend_scout.get_topics") as mock_get_topics,
        patch("pipeline.trend_scout.get_topics_for_description") as mock_gttfd,
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle"),
        patch("os.makedirs"),
    ):
        pipeline.main()
    mock_get_topics.assert_not_called()
    mock_gttfd.assert_not_called()


def test_community_topic_mode_passes_topic_to_agent():
    # The topic string passed to agent_cultural_strategist must be exactly what
    # was supplied via --topic, not a headline extracted from Trend Scout.
    provided_topic = "Number 10 is becoming available for rent, again."
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            [
                "pipeline.py",
                "--community",
                "uk-tech-engineers",
                "--topic",
                provided_topic,
            ],
        ),
        patch("os.path.exists", return_value=True),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ) as mock_a0,
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle"),
        patch("os.makedirs"),
    ):
        pipeline.main()
    topic_arg = mock_a0.call_args.args[0]
    assert topic_arg == provided_topic


def test_community_topic_mode_named_community_uses_configured_brief():
    # When the community name matches communities.yaml, its configured brief must be
    # used without calling infer_brief_from_description — no unnecessary inference.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            [
                "pipeline.py",
                "--community",
                "uk-tech-engineers",
                "--topic",
                "AI overload",
            ],
        ),
        patch("os.path.exists", return_value=True),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch("pipeline.trend_scout.infer_brief_from_description") as mock_infer,
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ) as mock_a0,
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle"),
        patch("os.makedirs"),
    ):
        pipeline.main()
    # Named community brief comes from community.to_brief(), not inference
    mock_infer.assert_not_called()
    _, brief_arg = mock_a0.call_args.args
    assert brief_arg.target_audience == COMMUNITY_UK.target_audience


def test_community_topic_mode_output_path_uses_community_folder():
    # Output must land under output/{community-name}/ so bundles are organised
    # by community consistently with the standard community mode.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            [
                "pipeline.py",
                "--community",
                "uk-tech-engineers",
                "--topic",
                "AI overload",
            ],
        ),
        patch("os.path.exists", return_value=True),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle"),
        patch("os.makedirs"),
    ):
        pipeline.main()
    output_path = mock_gen.call_args.args[1]
    assert output_path.startswith("output/uk-tech-engineers/")


# ---------------------------------------------------------------------------
# Stage 12 — Env var fallback logging (T018)
# ---------------------------------------------------------------------------


def test_pipeline_logs_when_dotenv_file_found(caplog):
    # When load_dotenv() loads a .env file (returns True), pipeline must emit an INFO
    # message mentioning ".env" so operators know which credential source is active.
    caplog.set_level(logging.INFO, logger="pipeline")
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv", return_value=True),
        patch("sys.argv", ["pipeline.py"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.random.choice",
            side_effect=[COMMUNITY_PT, "Housing crisis"],
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    assert any(".env" in r.message for r in caplog.records)


def test_pipeline_logs_when_no_dotenv_file(caplog):
    # When load_dotenv() finds no .env file (returns False), pipeline must emit an
    # INFO message mentioning "environment" so operators know credentials come from
    # the shell environment rather than a file.
    caplog.set_level(logging.INFO, logger="pipeline")
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv", return_value=False),
        patch("sys.argv", ["pipeline.py"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.random.choice",
            side_effect=[COMMUNITY_PT, "Housing crisis"],
        ),
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("os.makedirs"),
    ):
        pipeline.main()
    assert any("environment" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# Spec 035 — --direct flag (skip Cultural Strategist)
# ---------------------------------------------------------------------------

_DIRECT_SEED = StrategyBrief(
    target_audience="UK workers",
    output_language="English",
    tone="dry wit",
)


def test_direct_flag_skips_cultural_strategist():
    # run_pipeline(skip_cultural_strategist=True) must never call
    # agent_cultural_strategist.run so the Cultural Strategist cost and latency
    # are completely absent from the run.
    from core.runner import run_pipeline

    with (
        patch("core.runner.agent_cultural_strategist.run") as mock_a0,
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline("AI hype", _DIRECT_SEED, "out.png", skip_cultural_strategist=True)
    mock_a0.assert_not_called()


def test_direct_flag_builds_minimal_enriched_brief():
    # The minimal EnrichedBrief built in direct mode must carry the topic verbatim
    # as cultural_angle, empty references, and audience/language/tone from the
    # seed brief — the Satirist gets enough context without Cultural Strategist work.
    from core.runner import run_pipeline

    captured: list = []

    def capture_satirist(topic, brief, **kwargs):
        captured.append(brief)
        return (FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None)

    with (
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run", side_effect=capture_satirist),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline("AI hype", _DIRECT_SEED, "out.png", skip_cultural_strategist=True)
    assert len(captured) == 1
    brief = captured[0]
    assert brief.cultural_angle == "AI hype"
    assert brief.culturally_loaded_references == []
    assert brief.target_audience == _DIRECT_SEED.target_audience
    assert brief.output_language == _DIRECT_SEED.output_language
    assert brief.tone == _DIRECT_SEED.tone


def test_direct_flag_passes_brief_to_satirist():
    # The Satirist must receive the minimal EnrichedBrief (not None) so it has
    # audience and language context even without Cultural Strategist enrichment.
    from core.runner import run_pipeline

    with (
        patch("core.runner.agent_cultural_strategist.run"),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ) as mock_satirist,
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline("AI hype", _DIRECT_SEED, "out.png", skip_cultural_strategist=True)
    _, brief = mock_satirist.call_args.args
    assert brief is not None
    assert isinstance(brief.cultural_angle, str) and brief.cultural_angle


def test_direct_flag_absent_cultural_strategist_in_telemetry():
    # RunTelemetry must contain no entry named "Cultural Strategist" in direct mode
    # so the cost summary is accurate and does not show a zero-cost phantom agent.
    from core.runner import run_pipeline

    with (
        patch("core.runner.agent_cultural_strategist.run"),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        telemetry = run_pipeline(
            "AI hype", _DIRECT_SEED, "out.png", skip_cultural_strategist=True
        )
    agent_names = [a.agent_name for a in telemetry.agents]
    assert "Cultural Strategist" not in agent_names


def test_normal_mode_unchanged():
    # Without skip_cultural_strategist, agent_cultural_strategist.run must be called
    # exactly once — guard against regressions in the standard pipeline path.
    from core.runner import run_pipeline

    with (
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ) as mock_a0,
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, None),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ),
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline("AI hype", _DIRECT_SEED, "out.png")
    mock_a0.assert_called_once()


# ---------------------------------------------------------------------------
# Spec 046 — --research-only flag (core.runner.run_pipeline mechanism)
# ---------------------------------------------------------------------------

_RESEARCH_SEED = StrategyBrief(
    target_audience="policy analysts",
    output_language="English",
    tone="neutral",
)

FAKE_LINKEDIN_TEL = AgentTelemetry(
    agent_name="LinkedIn Post", duration_seconds=0.0, iterations=1
)


def test_research_only_skips_entire_satirical_pipeline():
    # research_only=True must never call Cultural Strategist, Satirist, Image
    # Generator, or Image Evaluator — that cost is exactly what this mode exists
    # to avoid.
    from core.runner import run_pipeline

    with (
        patch("core.runner.agent_cultural_strategist.run") as mock_cs,
        patch("core.runner.agent_satirist.run") as mock_sat,
        patch("core.runner.agent_image_generator.generate") as mock_img,
        patch("core.runner.agent_image_evaluator.evaluate") as mock_eval,
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("article", "notification"),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline("AI regulation", _RESEARCH_SEED, "out.md", research_only=True)
    mock_cs.assert_not_called()
    mock_sat.assert_not_called()
    mock_img.assert_not_called()
    mock_eval.assert_not_called()


def test_research_only_always_calls_generate_linkedin_post():
    # FR-003: generate_linkedin_post must be invoked in research_only mode
    # regardless of the generate_linkedin_post flag's own value — that flag
    # only picks branded vs. neutral output, per this same mode.
    from core.runner import run_pipeline

    with (
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("article", "notification"),
        ) as mock_post,
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline(
            "AI regulation",
            _RESEARCH_SEED,
            "out.md",
            research_only=True,
            generate_linkedin_post=False,
        )
    mock_post.assert_called_once()


def test_research_only_builds_minimal_enriched_brief_for_linkedin_post():
    # The minimal EnrichedBrief passed to generate_linkedin_post must carry the
    # topic verbatim and the seed brief's audience/language/tone — no Cultural
    # Strategist call happened to produce a richer one.
    from core.runner import run_pipeline

    with (
        patch("core.runner.agent_cultural_strategist.run") as mock_cs,
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("article", "notification"),
        ) as mock_post,
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline("AI regulation", _RESEARCH_SEED, "out.md", research_only=True)
    mock_cs.assert_not_called()
    brief = mock_post.call_args.args[0]
    assert brief.cultural_angle == "AI regulation"
    assert brief.culturally_loaded_references == []
    assert brief.target_audience == _RESEARCH_SEED.target_audience
    assert brief.output_language == _RESEARCH_SEED.output_language
    assert brief.tone == _RESEARCH_SEED.tone


def test_research_only_branded_matches_generate_linkedin_post_flag():
    # FR-003: branded passed to generate_linkedin_post must equal the caller's
    # generate_linkedin_post flag — True only when --linkedin-post was set.
    from core.runner import run_pipeline

    with (
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("article", "notification"),
        ) as mock_post,
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline(
            "AI regulation",
            _RESEARCH_SEED,
            "out.md",
            research_only=True,
            generate_linkedin_post=True,
        )
    assert mock_post.call_args.kwargs["branded"] is True


def test_research_only_branded_false_writes_research_report():
    # FR-007: when branded=False, write_bundle must receive research_report
    # (the article text) and linkedin_post=None — never both populated.
    from core.runner import run_pipeline

    with (
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("neutral article", "notification"),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_write,
    ):
        run_pipeline(
            "AI regulation",
            _RESEARCH_SEED,
            "out.md",
            research_only=True,
            generate_linkedin_post=False,
        )
    assert mock_write.call_args.kwargs["research_report"] == "neutral article"
    assert mock_write.call_args.kwargs["linkedin_post"] is None


def test_research_only_branded_true_writes_linkedin_post():
    # FR-003: when branded=True (i.e. --linkedin-post also supplied),
    # write_bundle must receive linkedin_post and research_report=None.
    from core.runner import run_pipeline

    with (
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("branded article", "notification"),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_write,
    ):
        run_pipeline(
            "AI regulation",
            _RESEARCH_SEED,
            "out.md",
            research_only=True,
            generate_linkedin_post=True,
        )
    assert mock_write.call_args.kwargs["linkedin_post"] == (
        "branded article",
        "notification",
    )
    assert mock_write.call_args.kwargs["research_report"] is None


def test_research_only_absent_agents_in_telemetry():
    # RunTelemetry must contain no Cultural Strategist/Satirist/Image
    # Generator/Image Evaluator entries in research_only mode.
    from core.runner import run_pipeline

    with (
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("article", "notification"),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        telemetry = run_pipeline(
            "AI regulation", _RESEARCH_SEED, "out.md", research_only=True
        )
    agent_names = [a.agent_name for a in telemetry.agents]
    assert agent_names == []


# ---------------------------------------------------------------------------
# Spec 046 — --research-only CLI flag (pipeline.py)
# ---------------------------------------------------------------------------

_RESEARCH_ONLY_ARGV = [
    "pipeline.py",
    "--topic",
    "AI hype",
    "--audience",
    "developers",
    "--language",
    "English",
    "--tone",
    "dry",
    "--research-only",
]


def test_research_only_cli_flag_builds_output_research_path():
    # FR-008: output_path in research-only mode must live under
    # output/research/, named from the topic slug plus a timestamp — never
    # derived from an image path.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", _RESEARCH_ONLY_ARGV),
        patch("pipeline.load_communities"),
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("article", "notification"),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_write,
        patch("os.makedirs"),
    ):
        pipeline.main()
    output_path = mock_write.call_args.args[0]
    assert re.match(r"output/research/ai_hype_\d{8}_\d{6}\.md", output_path)


def test_research_only_community_topic_mode_builds_output_research_path():
    # FR-008: the community-topic branch must also override output_path to
    # output/research/, not its normal output/{community}/... image path.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            [
                "pipeline.py",
                "--community",
                "uk-tech-engineers",
                "--topic",
                "AI overload",
                "--research-only",
            ],
        ),
        patch("os.path.exists", return_value=True),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("article", "notification"),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_write,
        patch("os.makedirs"),
    ):
        pipeline.main()
    output_path = mock_write.call_args.args[0]
    assert re.match(r"output/research/ai_overload_\d{8}_\d{6}\.md", output_path)


def test_research_only_named_community_mode_builds_output_research_path():
    # FR-008: the named-community (Trend Scout) branch must also override
    # output_path to output/research/, not its normal image path.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            ["pipeline.py", "--community", "uk-tech-engineers", "--research-only"],
        ),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics",
            return_value=([FAKE_HEADLINE], "seed"),
        ),
        patch("pipeline.trend_scout.get_topics_for_description", create=True),
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("article", "notification"),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_write,
        patch("os.makedirs"),
    ):
        pipeline.main()
    output_path = mock_write.call_args.args[0]
    assert output_path.startswith("output/research/")
    assert re.match(r"output/research/.+_\d{8}_\d{6}\.md", output_path)


def test_research_only_free_text_community_builds_output_research_path():
    # FR-008: the free-text-community (no exact communities.yaml match) branch
    # must also override output_path to output/research/.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch(
            "sys.argv",
            ["pipeline.py", "--community", _FREE_TEXT_DESC, "--research-only"],
        ),
        patch("os.path.exists", return_value=True),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.trend_scout.get_topics_for_description",
            return_value=([_FREE_TEXT_HEADLINE], _INFERRED_BRIEF, "trend_scout"),
            create=True,
        ),
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("article", "notification"),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_write,
        patch("os.makedirs"),
    ):
        pipeline.main()
    output_path = mock_write.call_args.args[0]
    assert output_path.startswith("output/research/")
    assert re.match(r"output/research/.+_\d{8}_\d{6}\.md", output_path)


def test_research_only_random_mode_builds_output_research_path():
    # FR-008: the default random-community branch must also override
    # output_path to output/research/, not its normal image path.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", ["pipeline.py", "--research-only"]),
        patch("pipeline.load_communities", return_value=FAKE_COMMUNITIES),
        patch(
            "pipeline.random.choice",
            side_effect=[COMMUNITY_PT, "Housing crisis"],
        ),
        patch("core.runner.agent_cultural_strategist.run"),
        patch("core.runner.agent_satirist.run"),
        patch("core.runner.agent_image_generator.generate"),
        patch("core.runner.agent_image_evaluator.evaluate"),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=("article", "notification"),
        ),
        patch("core.bundle_writer.write_bundle", return_value="") as mock_write,
        patch("os.makedirs"),
    ):
        pipeline.main()
    output_path = mock_write.call_args.args[0]
    assert output_path.startswith("output/research/")
    assert re.match(r"output/research/.+_\d{8}_\d{6}\.md", output_path)


def test_research_only_cli_flag_passes_research_only_to_run_pipeline():
    # research_only=True must reach run_pipeline so the satirical pipeline is
    # actually skipped, not just the output path renamed.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", _RESEARCH_ONLY_ARGV),
        patch("pipeline.load_communities"),
        patch("pipeline.run_pipeline", return_value=MagicMock()) as mock_run,
        patch("os.makedirs"),
    ):
        pipeline.main()
    assert mock_run.call_args.kwargs["research_only"] is True


def test_research_only_with_direct_logs_info_not_error(caplog):
    # FR-011: --direct is redundant under --research-only (Cultural Strategist
    # is already skipped) — this must be an INFO log, never an error/exit.
    with (
        patch.dict("os.environ", ENV),
        patch("pipeline.load_dotenv"),
        patch("sys.argv", _RESEARCH_ONLY_ARGV + ["--direct"]),
        patch("pipeline.load_communities"),
        patch("pipeline.run_pipeline", return_value=MagicMock()),
        patch("os.makedirs"),
        caplog.at_level(logging.INFO),
    ):
        pipeline.main()
    assert any(
        "--direct" in rec.message and "research-only" in rec.message.lower()
        for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# target_size gating — Spec 045 LinkedIn feature image size correction
# ---------------------------------------------------------------------------

_LAYOUT_HORIZONTAL = CartoonLayout(panels=1, direction="horizontal")
_LAYOUT_VERTICAL = CartoonLayout(panels=2, direction="vertical")


def test_linkedin_post_horizontal_layout_pins_target_size():
    # FR-006: a --linkedin-post run with a horizontal (or single-panel default)
    # layout must pin the cartoon to LinkedIn's exact cover size, since that
    # cartoon is the image actually pasted into LinkedIn today.
    from core.runner import run_pipeline

    with (
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, _LAYOUT_HORIZONTAL),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=(None, ""),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline("AI hype", _DIRECT_SEED, "out.png", generate_linkedin_post=True)
    assert mock_gen.call_args.kwargs["target_size"] == (1200, 644)


def test_linkedin_post_vertical_layout_leaves_target_size_none():
    # A --linkedin-post run with a vertical multi-panel layout must NOT be forced
    # to 1200x644 — cropping a vertical composition to landscape would mutilate it.
    from core.runner import run_pipeline

    with (
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, _LAYOUT_VERTICAL),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch(
            "core.runner.agent_linkedin_post.generate_linkedin_post",
            return_value=(None, ""),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline("AI hype", _DIRECT_SEED, "out.png", generate_linkedin_post=True)
    assert mock_gen.call_args.kwargs["target_size"] is None


def test_no_linkedin_post_leaves_target_size_none():
    # A run without --linkedin-post must never force the cartoon's resolution —
    # this feature only corrects images that are actually headed to LinkedIn.
    from core.runner import run_pipeline

    with (
        patch(
            "core.runner.agent_cultural_strategist.run",
            return_value=(FAKE_ENRICHED_BRIEF, FAKE_AGENT0_LOG, FAKE_AGENT0_TEL),
        ),
        patch(
            "core.runner.agent_satirist.run",
            return_value=(FAKE_CONCEPT, FAKE_BC_LOG, FAKE_BC_TEL, _LAYOUT_HORIZONTAL),
        ),
        patch(
            "core.runner.agent_image_generator.generate",
            return_value=("fake_image.png", FAKE_IMAGE_TEL),
        ) as mock_gen,
        patch(
            "core.runner.agent_image_evaluator.evaluate",
            return_value=(_FAKE_EVAL_RESULT, FAKE_EVAL_TEL),
        ),
        patch("core.bundle_writer.write_bundle", return_value=""),
    ):
        run_pipeline("AI hype", _DIRECT_SEED, "out.png")
    assert mock_gen.call_args.kwargs["target_size"] is None
