from unittest.mock import patch

from core.types import (
    AgentTelemetry,
    ConversationLog,
    ConversationTurn,
    RunTelemetry,
    TokenUsage,
)


def _make_log(loop_name: str, n_iterations: int = 2) -> ConversationLog:
    log = ConversationLog(loop_name=loop_name)
    for i in range(1, n_iterations + 1):
        verdict = "APPROVED" if i == n_iterations else "NEEDS REVISION"
        log.turns.append(
            ConversationTurn(
                iteration=i, role="Proposer", text=f"Proposal {i}", verdict=""
            )
        )
        log.turns.append(
            ConversationTurn(
                iteration=i, role="Reviewer", text=f"Review {i}", verdict=verdict
            )
        )
    return log


# -- format_log: section headers (T010) --


def test_format_log_contains_iteration_header():
    # Each iteration must have a clearly labelled header so the operator can jump to
    # any iteration without reading the entire log.
    from core.bundle_writer import format_log

    log = _make_log("Cultural Strategist", n_iterations=2)
    text = format_log(log)
    assert "=== Iteration 1 ===" in text
    assert "=== Iteration 2 ===" in text


def test_format_log_contains_proposer_role_name():
    # The proposer's persona name must appear before their text so the reader knows
    # which side is speaking in each iteration.
    from core.bundle_writer import format_log

    log = _make_log("Cultural Strategist", n_iterations=1)
    text = format_log(log)
    assert "Proposer" in text


def test_format_log_approved_verdict_label():
    # An APPROVED reviewer turn must be labelled "Verdict: APPROVED" so the operator
    # can grep for approvals without parsing the full text.
    from core.bundle_writer import format_log

    log = _make_log("Cultural Strategist", n_iterations=1)
    text = format_log(log)
    assert "Verdict: APPROVED" in text


def test_format_log_needs_revision_verdict_label():
    # A NEEDS REVISION reviewer turn must be labelled accordingly so the operator can
    # distinguish rejections from approvals at a glance.
    from core.bundle_writer import format_log

    log = _make_log("Cultural Strategist", n_iterations=2)
    text = format_log(log)
    assert "Verdict: NEEDS REVISION" in text


def test_format_log_final_say_verdict_label():
    # A FINAL_SAY reviewer turn must be labelled "FINAL SAY" so the operator knows
    # the Final Say Protocol was triggered rather than consensus being reached.
    from core.bundle_writer import format_log

    log = ConversationLog(loop_name="Satirist/Critic")
    log.turns.append(
        ConversationTurn(
            iteration=5, role="Satirist", text="Final proposal", verdict=""
        )
    )
    log.turns.append(
        ConversationTurn(
            iteration=5, role="Critic", text="Last feedback", verdict="FINAL_SAY"
        )
    )
    text = format_log(log)
    assert "FINAL SAY" in text


def test_format_log_iterations_separated_by_dashes():
    # Iterations must be separated by "---" on its own line so the reader can visually
    # scan between iterations without relying on indentation alone.
    from core.bundle_writer import format_log

    log = _make_log("Satirist/Critic", n_iterations=2)
    text = format_log(log)
    assert "---" in text


def test_format_log_proposer_text_in_output():
    # The full proposer text must appear in the formatted log — truncation would make
    # the log useless for auditing what was actually proposed.
    from core.bundle_writer import format_log

    log = _make_log("Cultural Strategist", n_iterations=1)
    text = format_log(log)
    assert "Proposal 1" in text


def test_format_log_reviewer_text_in_output():
    # The full reviewer text must appear in the formatted log — truncation would make
    # it impossible to see what feedback caused a revision.
    from core.bundle_writer import format_log

    log = _make_log("Cultural Strategist", n_iterations=1)
    text = format_log(log)
    assert "Review 1" in text


# -- write_bundle: log file creation (T011) --


def test_write_bundle_creates_bundle_dir(tmp_path):
    # write_bundle must create the bundle folder derived from the output_path stem —
    # its absence would prevent any files from being written.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
    )
    assert (tmp_path / "cartoon").is_dir()


def test_write_bundle_creates_agent0_log(tmp_path):
    # agent0_log.txt must be created so the operator can read the Agent 0 negotiation
    # history; its absence means cultural enrichment cannot be audited.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
    )
    assert (tmp_path / "cartoon" / "agent0_log.txt").exists()


def test_write_bundle_creates_bc_log(tmp_path):
    # bc_log.txt must be created so the operator can read the B/C creative loop history;
    # its absence means the satirical negotiation cannot be audited.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
    )
    assert (tmp_path / "cartoon" / "bc_log.txt").exists()


def test_write_bundle_agent0_log_content(tmp_path):
    # agent0_log.txt must contain the formatted log text — an empty or wrong file
    # defeats the purpose of the audit trail.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
    )
    content = (tmp_path / "cartoon" / "agent0_log.txt").read_text()
    assert "=== Iteration 1 ===" in content
    assert "Proposal 1" in content


def test_write_bundle_bc_log_content(tmp_path):
    # bc_log.txt must contain the formatted B/C loop text — callers must be able to
    # read the satirist and critic exchange without any extra processing.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
    )
    content = (tmp_path / "cartoon" / "bc_log.txt").read_text()
    assert "=== Iteration 1 ===" in content


def test_write_bundle_skips_none_agent0_log(tmp_path):
    # When agent0_log is None (Agent 0 failed before completing), write_bundle must not
    # create agent0_log.txt — partial logs must not appear as if they are complete.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    write_bundle(output_path, None, _make_log("Satirist/Critic"), None, None)
    assert not (tmp_path / "cartoon" / "agent0_log.txt").exists()


def test_write_bundle_skips_none_bc_log(tmp_path):
    # When bc_log is None (B/C loop never ran), write_bundle must not create bc_log.txt
    # so there is no ambiguity about whether the log is complete or missing.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    write_bundle(output_path, _make_log("Cultural Strategist"), None, None, None)
    assert not (tmp_path / "cartoon" / "bc_log.txt").exists()


def test_write_bundle_overwrites_existing_files(tmp_path):
    # Re-running write_bundle over an existing bundle must overwrite files without
    # raising FileExistsError, satisfying FR-013.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    bundle_dir = tmp_path / "cartoon"
    bundle_dir.mkdir()
    (bundle_dir / "agent0_log.txt").write_text("old content")
    write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
    )
    content = (bundle_dir / "agent0_log.txt").read_text()
    assert content != "old content"


def test_write_bundle_returns_bundle_path(tmp_path):
    # write_bundle must return the absolute path to the bundle folder so callers
    # can log or display it without recomputing the path.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    result = write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
    )
    assert result == str(tmp_path / "cartoon")


# -- write_bundle: agent_explainer error handling (T019) --


def test_write_bundle_survives_explainer_failure(tmp_path):
    # When agent_explainer.generate_html() raises, write_bundle must catch the error
    # and return normally so the cartoon image and logs are preserved (FR-011).
    from core.bundle_writer import write_bundle
    from core.types import EnrichedBrief

    brief = EnrichedBrief(
        target_audience="test",
        output_language="English",
        tone="dry",
        cultural_angle="angle",
        culturally_loaded_references=["ref"],
    )
    output_path = str(tmp_path / "cartoon.png")
    with patch(
        "core.bundle_writer.agent_explainer.generate_html",
        side_effect=RuntimeError("explainer failed"),
    ):
        # must not raise
        write_bundle(
            output_path,
            _make_log("Cultural Strategist"),
            _make_log("Satirist/Critic"),
            brief,
            "prompt",
            include_html=True,
        )


def test_write_bundle_logs_are_present_after_explainer_failure(tmp_path):
    # Even when agent_explainer fails, agent0_log.txt and bc_log.txt must still be
    # written — the logs are the primary audit trail and must survive HTML failures.
    from core.bundle_writer import write_bundle
    from core.types import EnrichedBrief

    brief = EnrichedBrief(
        target_audience="test",
        output_language="English",
        tone="dry",
        cultural_angle="angle",
        culturally_loaded_references=["ref"],
    )
    output_path = str(tmp_path / "cartoon.png")
    with patch(
        "core.bundle_writer.agent_explainer.generate_html",
        side_effect=RuntimeError("explainer failed"),
    ):
        write_bundle(
            output_path,
            _make_log("Cultural Strategist"),
            _make_log("Satirist/Critic"),
            brief,
            "prompt",
            include_html=True,
        )
    assert (tmp_path / "cartoon" / "agent0_log.txt").exists()
    assert (tmp_path / "cartoon" / "bc_log.txt").exists()


# -- write_bundle: prompt card (T022) --


def test_write_bundle_creates_prompt_card(tmp_path):
    # prompt_card.txt must exist after a successful run so the operator can reuse
    # the image prompt without re-running the full pipeline.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    with patch(
        "core.bundle_writer.agent_explainer.generate_html",
        return_value=("", ""),
    ):
        write_bundle(
            output_path,
            _make_log("Cultural Strategist"),
            _make_log("Satirist/Critic"),
            None,
            "the exact image prompt",
        )
    assert (tmp_path / "cartoon" / "prompt_card.txt").exists()


def test_write_bundle_prompt_card_verbatim_content(tmp_path):
    # prompt_card.txt must contain exactly the image_prompt string — nothing more,
    # nothing less — so it can be pasted directly into an image generation tool.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    image_prompt = "A cat sits at the UN table, wielding a gavel made of fish."
    with patch(
        "core.bundle_writer.agent_explainer.generate_html",
        return_value=("", ""),
    ):
        write_bundle(
            output_path,
            _make_log("Cultural Strategist"),
            _make_log("Satirist/Critic"),
            None,
            image_prompt,
        )
    content = (tmp_path / "cartoon" / "prompt_card.txt").read_text()
    assert content == image_prompt


def test_write_bundle_skips_prompt_card_when_none(tmp_path):
    # When image_prompt is None, prompt_card.txt must not be created — omission is
    # better than an empty or placeholder file.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
    )
    assert not (tmp_path / "cartoon" / "prompt_card.txt").exists()


# -- format_summary: human-readable telemetry rollup --


def _make_telemetry() -> RunTelemetry:
    agent0 = AgentTelemetry(
        agent_name="Cultural Strategist",
        duration_seconds=18.3,
        iterations=2,
        calls=[
            TokenUsage(
                model="claude-sonnet-4-6",
                input_tokens=900,
                output_tokens=350,
                cost_usd=0.008,
            )
        ],
    )
    image_gen = AgentTelemetry(
        agent_name="Image Generator", duration_seconds=5.0, iterations=1
    )
    return RunTelemetry(agents=[agent0, image_gen])


def test_format_summary_lists_each_agent_by_name():
    # Every agent that ran must appear by name so the operator can see where the
    # time and cost went without opening telemetry.json.
    from core.bundle_writer import format_summary

    text = format_summary(_make_telemetry())
    assert "Cultural Strategist" in text
    assert "Image Generator" in text


def test_format_summary_includes_per_agent_duration_and_iterations():
    # The per-agent line must show duration and iteration count, the two numbers an
    # operator needs to spot a slow or looping agent.
    from core.bundle_writer import format_summary

    text = format_summary(_make_telemetry())
    assert "18.3s" in text
    assert "2 iteration(s)" in text


def test_format_summary_includes_per_agent_cost():
    # The per-agent line must show its cost so the operator can see which agent is
    # driving the bill, not just the total.
    from core.bundle_writer import format_summary

    text = format_summary(_make_telemetry())
    assert "$0.0080" in text


def test_format_summary_includes_total_line():
    # A TOTAL line summing duration and cost across all agents is the headline number
    # for an announcement post — it must be present and correct.
    from core.bundle_writer import format_summary

    text = format_summary(_make_telemetry())
    assert "TOTAL: 23.3s" in text
    assert "$0.0080" in text


# -- write_bundle: summary.txt --


def test_write_bundle_creates_summary_txt_when_telemetry_given(tmp_path):
    # summary.txt must be written alongside telemetry.json so the human-readable
    # rollup is available without parsing JSON.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
        telemetry=_make_telemetry(),
    )
    assert (tmp_path / "cartoon" / "summary.txt").exists()


def test_write_bundle_skips_summary_txt_when_telemetry_none(tmp_path):
    # When no telemetry was collected, summary.txt must not be created — an empty or
    # placeholder file would be misleading.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
    )
    assert not (tmp_path / "cartoon" / "summary.txt").exists()


def _make_brief():
    from core.types import EnrichedBrief

    return EnrichedBrief(
        target_audience="test",
        output_language="English",
        tone="dry",
        cultural_angle="angle",
        culturally_loaded_references=["ref"],
    )


def test_write_bundle_skips_html_by_default(tmp_path):
    # HTML generation costs an extra Claude + Gemini round trip on every run; it must
    # stay off unless the caller explicitly opts in via include_html.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    with patch(
        "core.bundle_writer.agent_explainer.generate_html",
        return_value=("in-lang", "english"),
    ) as mock_generate:
        write_bundle(
            output_path,
            _make_log("Cultural Strategist"),
            _make_log("Satirist/Critic"),
            _make_brief(),
            "prompt",
        )
    mock_generate.assert_not_called()
    assert not (tmp_path / "cartoon" / "explanation.html").exists()
    assert not (tmp_path / "cartoon" / "deep_dive_en.html").exists()


def test_write_bundle_generates_html_when_requested(tmp_path):
    # Passing include_html=True must restore the original behavior so operators who
    # want the explanation pages can still get them on demand.
    from core.bundle_writer import write_bundle

    output_path = str(tmp_path / "cartoon.png")
    with patch(
        "core.bundle_writer.agent_explainer.generate_html",
        return_value=("in-lang", "english"),
    ) as mock_generate:
        write_bundle(
            output_path,
            _make_log("Cultural Strategist"),
            _make_log("Satirist/Critic"),
            _make_brief(),
            "prompt",
            include_html=True,
        )
    mock_generate.assert_called_once()
    assert (tmp_path / "cartoon" / "explanation.html").read_text() == "in-lang"
    assert (tmp_path / "cartoon" / "deep_dive_en.html").read_text() == "english"


def test_write_bundle_summary_txt_matches_format_summary(tmp_path):
    # summary.txt content must be exactly what format_summary produces — no separate,
    # potentially diverging formatting logic for the file vs. the log line.
    from core.bundle_writer import format_summary, write_bundle

    output_path = str(tmp_path / "cartoon.png")
    telemetry = _make_telemetry()
    write_bundle(
        output_path,
        _make_log("Cultural Strategist"),
        _make_log("Satirist/Critic"),
        None,
        None,
        telemetry=telemetry,
    )
    content = (tmp_path / "cartoon" / "summary.txt").read_text()
    assert content == format_summary(telemetry)
