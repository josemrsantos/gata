import logging
import re
from pathlib import Path
from unittest.mock import patch

import pytest

import core.cli as cli
from core.config_loader import load_communities
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
    # (before _ensure_uk) — not a UK-ensured or looped-over list. Spec 055: guessed
    # audiences are now opt-in, so this test passes --infer-audiences.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch(
            "sys.argv",
            ["gata", "AI regulation", "--infer-audiences", "--research-only"],
        ),
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
    # per-audience loop, not just the first. Spec 055: several audiences now need
    # --infer-audiences, so this test passes it.
    import core.cli as cli

    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", "AI regulation", "--infer-audiences", "--verbose"]),
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


# ---------------------------------------------------------------------------
# Spec 055 — single-audience default
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent


def test_builtin_default_audience_matches_communities_yaml():
    # The built-in default must equal the uk-tech-engineers entry in
    # communities.yaml, otherwise the two copies drift apart silently (FR-006).
    community = {c.name: c for c in load_communities(str(_REPO / "communities.yaml"))}[
        "uk-tech-engineers"
    ]
    default = cli._DEFAULT_AUDIENCE
    assert default.name == "uk-tech-engineers"
    assert default.audience == community.target_audience
    assert default.language == community.output_language
    assert default.tone == community.tone


def test_help_states_default_audience_and_new_options(capsys):
    # --help must tell the operator the default audience and the two audience
    # options, since the default behaviour changed (FR-011, SC-006).
    with patch("sys.argv", ["gata", "--help"]), pytest.raises(SystemExit) as exc:
        cli.main()
    out = capsys.readouterr().out
    assert exc.value.code == 0
    assert "uk-tech-engineers" in out
    assert "--audience" in out
    assert "--infer-audiences" in out


def _run_gata(argv, *, infer_return=None):
    # Runs gata's main() with every external call mocked; returns the run_pipeline
    # and infer_audiences mocks so tests can inspect how they were called.
    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", *argv]),
        patch(
            "core.cli.infer_audiences", return_value=infer_return or _AUDIENCES
        ) as mock_infer,
        patch("core.cli.run_pipeline", return_value=_tel(5.0, 0.01)) as mock_run,
    ):
        cli.main()
    return mock_run, mock_infer


def test_default_run_is_one_pipeline_run_for_the_builtin_audience(
    tmp_path, monkeypatch
):
    # A plain `gata "topic"` must run the pipeline once, for uk-tech-engineers, and
    # never ask Gemini to guess audiences (FR-001, FR-002, SC-001, SC-002).
    monkeypatch.chdir(tmp_path)
    (tmp_path / "communities.yaml").write_text((_REPO / "communities.yaml").read_text())
    mock_run, mock_infer = _run_gata(["AI regulation"])
    mock_infer.assert_not_called()
    mock_run.assert_called_once()
    seed_brief = mock_run.call_args.args[1]
    assert seed_brief.target_audience == "British software engineers and developers"
    assert seed_brief.output_language == "English"
    assert seed_brief.tone == "dry British wit"
    assert mock_run.call_args.args[2].endswith("uk-tech-engineers.png")


def test_default_run_shows_one_progress_line_and_one_total(
    tmp_path, monkeypatch, capsys
):
    # The default run must look like a single-audience run: a [1/1] line, no
    # "UK public" audience, and a summary.txt with one audience line plus TOTAL
    # (FR-002, FR-010, US1 scenario 3).
    monkeypatch.chdir(tmp_path)
    _run_gata(["AI regulation"])
    out = capsys.readouterr().out
    assert "[1/1] uk-tech-engineers — English" in out
    assert "UK public" not in out
    lines = (tmp_path / "ai_regulation" / "summary.txt").read_text().splitlines()
    audience_lines = [x for x in lines if x and not x.startswith("TOTAL:")]
    assert len(audience_lines) == 1
    assert audience_lines[0].startswith("uk-tech-engineers:")
    assert any(x.startswith("TOTAL:") for x in lines)


def test_default_run_works_without_a_communities_file(tmp_path, monkeypatch):
    # The default is built in, so it must work from a folder that has no
    # communities.yaml at all (FR-006).
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / "communities.yaml").exists()
    mock_run, mock_infer = _run_gata(["AI regulation"])
    mock_infer.assert_not_called()
    mock_run.assert_called_once()


def _run_gata_expect_exit(argv):
    # Like _run_gata, but for runs that must stop with SystemExit; returns the exit
    # code plus the mocks so tests can prove no paid call was made.
    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch("sys.argv", ["gata", *argv]),
        patch("core.cli.infer_audiences", return_value=_AUDIENCES) as mock_infer,
        patch("core.cli.run_pipeline", return_value=_tel(5.0, 0.01)) as mock_run,
        pytest.raises(SystemExit) as exc,
    ):
        cli.main()
    return exc.value.code, mock_run, mock_infer


_NO_UK = [
    AudienceProfile(name="devs", audience="developers", language="English", tone="dry"),
    AudienceProfile(
        name="pt", audience="Portuguese public", language="Portuguese", tone="sharp"
    ),
]


def test_infer_audiences_flag_restores_guessed_audiences_plus_uk(tmp_path, monkeypatch):
    # --infer-audiences must reproduce the old behaviour exactly: one run per
    # guessed audience, with the UK public added when none of them is UK (FR-005,
    # SC-007).
    monkeypatch.chdir(tmp_path)
    mock_run, mock_infer = _run_gata(["AI regulation", "--infer-audiences"])
    mock_infer.assert_called_once()
    assert mock_run.call_count == len(_AUDIENCES)
    mock_run, _ = _run_gata(["AI regulation", "--infer-audiences"], infer_return=_NO_UK)
    names = [Path(c.args[2]).name for c in mock_run.call_args_list]
    assert names == ["devs.png", "pt.png", "uk.png"]


def test_infer_audiences_with_research_only_uses_first_guessed_audience(
    tmp_path, monkeypatch
):
    # Under --infer-audiences, --research-only keeps today's behaviour: one run,
    # using the first guessed audience.
    monkeypatch.chdir(tmp_path)
    mock_run, mock_infer = _run_gata(
        ["AI regulation", "--infer-audiences", "--research-only"]
    )
    mock_infer.assert_called_once()
    mock_run.assert_called_once()
    seed_brief = mock_run.call_args.args[1]
    assert seed_brief.target_audience == _AUDIENCES[0].audience


def test_infer_audiences_together_with_audience_is_rejected(caplog):
    # The two options are different ways of choosing audiences, so using both
    # must stop the command before any paid call (FR-005, contract).
    code, mock_run, mock_infer = _run_gata_expect_exit(
        ["AI regulation", "--infer-audiences", "--audience", "uk-politics"]
    )
    assert code == 1
    assert "--infer-audiences and --audience cannot be used together" in caplog.text
    mock_run.assert_not_called()
    mock_infer.assert_not_called()


_COMMUNITY_TEMPLATE = """  - name: {name}
    target_audience: {name} audience
    output_language: {lang}
    tone: {name} tone
    panels: 3
    layout: vertical
    topics:
      - a sample topic
"""


def _write_communities(folder, names=("uk-politics", "portuguese-adults")):
    # Writes a small communities.yaml (with panels/layout set, which gata must
    # ignore) into `folder` and returns the file path.
    body = "communities:\n" + "".join(
        _COMMUNITY_TEMPLATE.format(
            name=n, lang="Portuguese" if "pt" in n else "English"
        )
        for n in names
    )
    path = folder / "communities.yaml"
    path.write_text(body)
    return path


def test_audience_option_runs_the_named_community(tmp_path, monkeypatch):
    # --audience NAME must run once for that community, using its description,
    # language and tone, with no audience guessing (FR-003, FR-004).
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path)
    mock_run, mock_infer = _run_gata(["AI regulation", "--audience", "uk-politics"])
    mock_infer.assert_not_called()
    mock_run.assert_called_once()
    seed_brief = mock_run.call_args.args[1]
    assert seed_brief.target_audience == "uk-politics audience"
    assert seed_brief.output_language == "English"
    assert seed_brief.tone == "uk-politics tone"
    assert mock_run.call_args.args[2].endswith("uk-politics.png")


def test_two_audiences_run_in_order_in_the_same_folder(tmp_path, monkeypatch, capsys):
    # Several --audience values must give one run each, in the order given, into
    # the same output folder, with [i/N] progress lines (SC-003, FR-010).
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path)
    mock_run, _ = _run_gata(
        [
            "AI regulation",
            "--audience",
            "portuguese-adults",
            "--audience",
            "uk-politics",
        ]
    )
    paths = [Path(c.args[2]) for c in mock_run.call_args_list]
    assert [p.name for p in paths] == ["portuguese-adults.png", "uk-politics.png"]
    assert paths[0].parent == paths[1].parent
    out = capsys.readouterr().out
    assert "[1/2] portuguese-adults" in out
    assert "[2/2] uk-politics" in out


def test_the_same_audience_given_twice_runs_once(tmp_path, monkeypatch):
    # A repeated --audience value must not pay for the same audience twice.
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path)
    mock_run, _ = _run_gata(
        ["AI regulation", "--audience", "uk-politics", "--audience", "uk-politics"]
    )
    mock_run.assert_called_once()
    assert mock_run.call_args.args[2].endswith("uk-politics.png")


@pytest.mark.parametrize("value", ["nope", ""])
def test_unknown_or_empty_audience_stops_before_any_call(
    tmp_path, monkeypatch, caplog, value
):
    # An unknown or empty --audience must stop the command naming the value and the
    # valid choices, before any paid call (FR-007, SC-004).
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path)
    code, mock_run, mock_infer = _run_gata_expect_exit(
        ["AI regulation", "--audience", value]
    )
    assert code == 1
    assert f"unknown audience '{value}' — valid audiences:" in caplog.text
    assert "uk-politics" in caplog.text
    assert "portuguese-adults" in caplog.text
    mock_run.assert_not_called()
    mock_infer.assert_not_called()


def test_builtin_default_name_works_when_the_file_is_absent(tmp_path, monkeypatch):
    # Without communities.yaml the built-in default still answers to its own
    # name, so `--audience uk-tech-engineers` works from any folder (FR-007).
    monkeypatch.chdir(tmp_path)
    mock_run, _ = _run_gata(["AI regulation", "--audience", "uk-tech-engineers"])
    mock_run.assert_called_once()
    assert mock_run.call_args.args[2].endswith("uk-tech-engineers.png")


def test_other_names_say_the_file_is_missing_when_it_is_absent(
    tmp_path, monkeypatch, caplog
):
    # Naming any other audience with no communities.yaml must say the file was not
    # found and that only the built-in audience is available (FR-007).
    monkeypatch.chdir(tmp_path)
    code, mock_run, _ = _run_gata_expect_exit(
        ["AI regulation", "--audience", "uk-politics"]
    )
    assert code == 1
    assert "communities.yaml not found in the current folder" in caplog.text
    assert "only the built-in audience 'uk-tech-engineers'" in caplog.text
    mock_run.assert_not_called()


def test_an_existing_file_is_the_only_source_of_names(tmp_path, monkeypatch, caplog):
    # When communities.yaml exists but has no uk-tech-engineers entry, that name is
    # unknown: the file wins and the built-in copy only serves the file-absent case.
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path)
    code, mock_run, _ = _run_gata_expect_exit(
        ["AI regulation", "--audience", "uk-tech-engineers"]
    )
    assert code == 1
    assert "unknown audience 'uk-tech-engineers'" in caplog.text
    mock_run.assert_not_called()


def test_community_panels_and_layout_are_not_passed_to_the_pipeline(
    tmp_path, monkeypatch
):
    # A community's panels/layout settings must stay unused by gata: layout remains
    # chosen automatically for every audience (FR-003a).
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path)
    mock_run, _ = _run_gata(["AI regulation", "--audience", "uk-politics"])
    assert "panels" not in mock_run.call_args.kwargs
    assert "layout" not in mock_run.call_args.kwargs
    assert len(mock_run.call_args.args) == 3
    assert mock_run.call_args.args[2].endswith("uk-politics.png")


def test_invalid_communities_file_reports_the_loader_error(
    tmp_path, monkeypatch, caplog
):
    # A broken communities.yaml must stop the command with the loader's own
    # message, before any paid call.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "communities.yaml").write_text("not_communities: []\n")
    code, mock_run, _ = _run_gata_expect_exit(["AI regulation", "--audience", "x"])
    assert code == 1
    assert "missing required top-level 'communities' key" in caplog.text
    mock_run.assert_not_called()


def test_named_audience_file_names_are_made_safe(tmp_path, monkeypatch):
    # A community name with path characters must become a safe file name that stays
    # inside the topic folder, while already-safe names are unchanged (FR-014).
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path, names=("Odd Name/../x",))
    mock_run, _ = _run_gata(["AI regulation", "--audience", "Odd Name/../x"])
    out_path = Path(mock_run.call_args.args[2])
    assert out_path.name == "odd_namex.png"
    assert out_path.parent == tmp_path / "ai_regulation"


def test_research_only_uses_the_first_named_audience_and_warns(
    tmp_path, monkeypatch, caplog
):
    # --research-only runs once for the first selected audience; any further
    # --audience values are ignored with a visible warning (FR-008, SC-008).
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path)
    mock_run, mock_infer = _run_gata(
        [
            "AI regulation",
            "--research-only",
            "--audience",
            "uk-politics",
            "--audience",
            "portuguese-adults",
        ]
    )
    mock_infer.assert_not_called()
    mock_run.assert_called_once()
    assert mock_run.call_args.args[1].target_audience == "uk-politics audience"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("ignoring portuguese-adults" in r.getMessage() for r in warnings)


def test_research_only_without_audience_uses_the_default(tmp_path, monkeypatch):
    # With no --audience, --research-only must use the built-in default audience.
    monkeypatch.chdir(tmp_path)
    mock_run, mock_infer = _run_gata(["AI regulation", "--research-only"])
    mock_infer.assert_not_called()
    mock_run.assert_called_once()
    assert mock_run.call_args.args[1].target_audience == (
        "British software engineers and developers"
    )


def test_existing_options_apply_to_every_selected_audience(tmp_path, monkeypatch):
    # Regression guard: the other options must reach every audience's run exactly
    # as they did before (FR-009).
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path)
    mock_run, _ = _run_gata(
        [
            "AI regulation",
            "--audience",
            "uk-politics",
            "--audience",
            "portuguese-adults",
            "--no-title",
            "--html",
            "--direct",
            "--linkedin-post",
            "--angle",
            "X",
            "--verbose",
        ]
    )
    assert mock_run.call_count == 2
    for call in mock_run.call_args_list:
        assert call.kwargs["show_title"] is False
        assert call.kwargs["include_html"] is True
        assert call.kwargs["skip_cultural_strategist"] is True
        assert call.kwargs["generate_linkedin_post"] is True
        assert call.kwargs["angles"] == ["X"]
        assert call.kwargs["verbose"] is True


def test_one_failing_audience_does_not_stop_the_others(tmp_path, monkeypatch, capsys):
    # Regression guard: when one audience fails the others still run and the command
    # exits 1 reporting the partial result, as before.
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path)
    with (
        patch.dict("os.environ", ENV),
        patch("core.cli.load_dotenv"),
        patch(
            "sys.argv",
            ["gata", "AI regulation", "--audience", "uk-politics"]
            + ["--audience", "portuguese-adults"],
        ),
        patch(
            "core.cli.run_pipeline",
            side_effect=[RuntimeError("boom"), _tel(5.0, 0.01)],
        ) as mock_run,
        pytest.raises(SystemExit) as exc,
    ):
        cli.main()
    assert exc.value.code == 1
    assert mock_run.call_count == 2
    assert "1/2 audiences failed" in capsys.readouterr().err


def test_audience_whose_name_has_no_safe_characters_is_rejected(
    tmp_path, monkeypatch, caplog
):
    # A community name that is all unsafe characters would make an empty file name,
    # so it must be rejected before any paid call instead of writing ".png".
    monkeypatch.chdir(tmp_path)
    _write_communities(tmp_path, names=("///",))
    code, mock_run, _ = _run_gata_expect_exit(["AI regulation", "--audience", "///"])
    assert code == 1
    assert "cannot be used as a file name" in caplog.text
    mock_run.assert_not_called()
