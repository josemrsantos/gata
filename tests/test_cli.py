import logging
import re
from unittest.mock import patch

from core.types import AgentTelemetry, AudienceProfile, RunTelemetry, TokenUsage

ENV = {"ANTHROPIC_API_KEY": "fake-anthropic", "GEMINI_API_KEY": "fake-gemini"}

_AUDIENCES = [
    AudienceProfile(name="devs", audience="developers", language="English", tone="dry"),
    AudienceProfile(
        name="pt", audience="Portuguese public", language="Portuguese", tone="sharp"
    ),
    AudienceProfile(
        name="uk", audience="UK public", language="English", tone="dry British wit"
    ),
]


def _tel(duration: float, cost: float) -> RunTelemetry:
    return RunTelemetry(
        agents=[
            AgentTelemetry(
                agent_name="Cultural Strategist",
                duration_seconds=duration,
                iterations=1,
                calls=[
                    TokenUsage(
                        model="claude-sonnet-4-6",
                        input_tokens=0,
                        output_tokens=0,
                        cost_usd=cost,
                    )
                ],
            )
        ]
    )


def test_format_grand_total_lists_each_audience_by_name():
    # Every audience that completed must appear by name so the operator can see
    # which audience cost the most without opening individual bundles.
    from core.cli import _format_grand_total

    audiences = [("swiss", _tel(10.0, 0.01)), ("qatar", _tel(5.0, 0.02))]
    text = _format_grand_total(audiences)
    assert "swiss" in text
    assert "qatar" in text


def test_format_grand_total_sums_duration_and_cost():
    # The TOTAL line is the headline number for an announcement post — it must sum
    # correctly across every audience, not just repeat the last one.
    from core.cli import _format_grand_total

    audiences = [("swiss", _tel(10.0, 0.01)), ("qatar", _tel(5.0, 0.02))]
    text = _format_grand_total(audiences)
    assert "TOTAL: 15.0s" in text
    assert "$0.0300" in text


def test_format_grand_total_omits_failed_audiences():
    # A failed audience contributes no telemetry, so it must not appear in the
    # output or be counted as a zero-cost, zero-time entry.
    from core.cli import _format_grand_total

    text = _format_grand_total([("swiss", _tel(10.0, 0.01))])
    assert "qatar" not in text
    assert "TOTAL: 10.0s" in text


# ---------------------------------------------------------------------------
# Spec 046 — --research-only flag (gata CLI)
# ---------------------------------------------------------------------------


def test_research_only_flag_calls_run_pipeline_once_not_per_audience():
    # FR-010: --research-only must bypass the per-audience loop — run_pipeline
    # is invoked exactly once, not once per inferred audience.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", "AI regulation", "--research-only"]),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES),
        patch("core.cli.run_pipeline", return_value=RunTelemetry()) as mock_run,
        patch("os.makedirs"),
    ):
        cli.main()
    mock_run.assert_called_once()


def test_research_only_flag_uses_first_inferred_audience():
    # US3: the single report's context comes from the first inferred audience
    # (before _ensure_uk) — not a UK-ensured or looped-over list.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", "AI regulation", "--research-only"]),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES),
        patch("core.cli.run_pipeline", return_value=RunTelemetry()) as mock_run,
        patch("os.makedirs"),
    ):
        cli.main()
    seed_brief = mock_run.call_args.args[1]
    assert seed_brief.target_audience == _AUDIENCES[0].audience
    assert seed_brief.output_language == _AUDIENCES[0].language
    assert seed_brief.tone == _AUDIENCES[0].tone


def test_research_only_flag_passes_research_only_and_linkedin_post():
    # US2: --research-only --linkedin-post must reach run_pipeline as
    # research_only=True, generate_linkedin_post=True.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch(
            "sys.argv",
            ["gata", "AI regulation", "--research-only", "--linkedin-post"],
        ),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES),
        patch("core.cli.run_pipeline", return_value=RunTelemetry()) as mock_run,
        patch("os.makedirs"),
    ):
        cli.main()
    assert mock_run.call_args.kwargs["research_only"] is True
    assert mock_run.call_args.kwargs["generate_linkedin_post"] is True


def test_research_only_flag_output_path_under_output_research():
    # FR-008: output_path must live under output/research/, named from the
    # topic slug plus a timestamp — never a per-audience image path.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", "AI regulation", "--research-only"]),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES),
        patch("core.cli.run_pipeline", return_value=RunTelemetry()) as mock_run,
        patch("os.makedirs"),
    ):
        cli.main()
    output_path = mock_run.call_args.args[2]
    assert re.match(r"output/research/ai_regulation_\d{8}_\d{6}\.md", output_path)


def test_direct_with_research_only_logs_info_not_error(caplog):
    # FR-011: --direct is redundant under --research-only (Cultural Strategist
    # is already skipped) — this must be an INFO log, never an error/exit.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch(
            "sys.argv",
            ["gata", "AI regulation", "--research-only", "--direct"],
        ),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES),
        patch("core.cli.run_pipeline", return_value=RunTelemetry()),
        patch("os.makedirs"),
        caplog.at_level(logging.INFO),
    ):
        cli.main()
    assert any(
        "--direct" in rec.message and "research-only" in rec.message.lower()
        for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# Spec 050 — gata --verbose/-v CLI flag
# ---------------------------------------------------------------------------


def test_gata_verbose_flag_sets_info_level():
    # FR-006: --verbose must raise gata's logging level to INFO.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", "AI regulation", "--research-only", "--verbose"]),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES),
        patch("core.cli.run_pipeline", return_value=RunTelemetry()),
        patch("os.makedirs"),
        patch("core.cli.logging.basicConfig") as mock_basic_config,
    ):
        cli.main()
    assert mock_basic_config.call_args.kwargs["level"] == logging.INFO


def test_gata_default_sets_warning_level():
    # FR-006: without --verbose, gata's default stays WARNING (unchanged).
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", "AI regulation", "--research-only"]),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES),
        patch("core.cli.run_pipeline", return_value=RunTelemetry()),
        patch("os.makedirs"),
        patch("core.cli.logging.basicConfig") as mock_basic_config,
    ):
        cli.main()
    assert mock_basic_config.call_args.kwargs["level"] == logging.WARNING


def test_gata_verbose_passed_to_run_pipeline_research_only():
    # FR-005: --verbose must reach run_pipeline(verbose=True) on the
    # research-only branch.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", "AI regulation", "--research-only", "--verbose"]),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES),
        patch("core.cli.run_pipeline", return_value=RunTelemetry()) as mock_run,
        patch("os.makedirs"),
    ):
        cli.main()
    assert mock_run.call_args.kwargs["verbose"] is True


def test_gata_verbose_passed_to_run_pipeline_each_audience():
    # FR-005: --verbose must reach every run_pipeline() call in the
    # per-audience loop, not just the first.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", "AI regulation", "--verbose"]),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES),
        patch("core.cli.run_pipeline", return_value=RunTelemetry()) as mock_run,
        patch("os.makedirs"),
    ):
        cli.main()
    # _AUDIENCES already includes a UK entry, so _ensure_uk adds nothing.
    assert mock_run.call_count == len(_AUDIENCES)
    assert all(c.kwargs["verbose"] is True for c in mock_run.call_args_list)


def test_gata_no_verbose_flag_passes_false_to_run_pipeline():
    # Regression guard: default (no --verbose) must explicitly pass False.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", "AI regulation"]),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES),
        patch("core.cli.run_pipeline", return_value=RunTelemetry()) as mock_run,
        patch("os.makedirs"),
    ):
        cli.main()
    assert all(c.kwargs["verbose"] is False for c in mock_run.call_args_list)
