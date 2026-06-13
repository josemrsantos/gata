import logging
from unittest.mock import patch

import pytest

from agents.dual_loop import DualPersonaLoop
from agents.types import ConversationLog, ConversationTurn, LoopOutput, PersonaConfig

_PROPOSER = PersonaConfig(
    name="TestProposer",
    models=["claude-sonnet-4-6", "claude-opus-4-7"],
    system_prompt="You are the proposer.",
)
_REVIEWER = PersonaConfig(
    name="TestReviewer",
    models=["gemini-2.5-pro", "gemini-2.5-flash"],
    system_prompt="You are the reviewer.",
)
_VERDICT_CONTENT = "Cultural angle: housing crisis as a cat territorial dispute."
_PROPOSER_OK = f"<verdict>{_VERDICT_CONTENT}</verdict>"
_REVIEWER_APPROVED = "<verdict>APPROVED</verdict>"
_REVIEWER_REJECTED = "<verdict>NEEDS REVISION\nToo obvious.</verdict>"


def _make_loop(max_iterations=5, timeout_seconds=900):
    return DualPersonaLoop(_PROPOSER, _REVIEWER, max_iterations, timeout_seconds)


# -- happy path: approval on first iteration --


def test_approval_on_first_iteration_returns_verdict_content():
    # Verifies that when the reviewer approves on iteration 1, run() returns
    # the exact text inside the proposer's <verdict> tag and exits after one round.
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ) as mock:
        result = loop.run("initial input")
    assert result.verdict == _VERDICT_CONTENT
    assert mock.call_count == 2


# -- US2: early consensus before max_iterations --


def test_early_exit_on_approval_at_iteration_2():
    # US2: when the reviewer approves at iteration 2 (not 1, not 5), the loop exits
    # immediately and does not call _call_model for iterations 3-5.
    proposer_iter2 = "<verdict>Refined proposal after feedback.</verdict>"
    responses = [
        _PROPOSER_OK,
        _REVIEWER_REJECTED,
        proposer_iter2,
        _REVIEWER_APPROVED,
    ]
    loop = _make_loop()
    with patch("agents.dual_loop._call_model", side_effect=responses) as mock:
        result = loop.run("input")
    assert result.verdict == "Refined proposal after feedback."
    assert mock.call_count == 4


def test_early_exit_does_not_run_extra_iterations():
    # US2: loop must not run any iteration after the first APPROVED, confirming API
    # quota is not wasted on unnecessary calls once consensus is reached.
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ) as mock:
        loop.run("input")
    assert mock.call_count == 2


# -- US3: Final Say Protocol at iteration 5 --


def test_final_say_returns_iteration_5_proposer_content():
    # US3: when no consensus after 5 iterations, the loop must return the proposer's
    # iteration-5 <verdict> content regardless of the reviewer's final verdict.
    final_content = "My definitive final-say proposal."
    responses = []
    for i in range(1, 5):
        responses.extend(
            [f"<verdict>Proposal iteration {i}</verdict>", _REVIEWER_REJECTED]
        )
    responses.extend([f"<verdict>{final_content}</verdict>", _REVIEWER_REJECTED])
    loop = _make_loop()
    with patch("agents.dual_loop._call_model", side_effect=responses):
        result = loop.run("input")
    assert result.verdict == final_content


def test_final_say_runs_exactly_five_iterations():
    # US3: the loop must invoke each persona exactly 5 times when no approval is reached
    # — confirming the max_iterations cap is respected and never exceeded.
    responses = []
    for i in range(1, 6):
        responses.extend([f"<verdict>Proposal {i}</verdict>", _REVIEWER_REJECTED])
    loop = _make_loop()
    with patch("agents.dual_loop._call_model", side_effect=responses) as mock:
        loop.run("input")
    assert mock.call_count == 10


def test_final_say_prompt_includes_final_say_keywords():
    # US3: at iteration 5, the proposer must receive a system prompt that contains
    # Final Say Protocol language — enforcing genuine consideration of feedback.
    all_calls: list[tuple[str, str]] = []

    def capture(model, system_prompt, messages, max_tokens=2048):
        all_calls.append((model, system_prompt))
        if model.startswith("claude"):
            return "<verdict>proposal</verdict>"
        return _REVIEWER_REJECTED

    loop = _make_loop()
    with patch("agents.dual_loop._call_model", side_effect=capture):
        loop.run("input")
    proposer_calls = [(m, sp) for m, sp in all_calls if m.startswith("claude")]
    assert len(proposer_calls) == 5
    assert "FINAL SAY" in proposer_calls[4][1].upper()


# -- US4: timeout --


def test_timeout_raises_timeout_error():
    # US4: if elapsed time exceeds the budget at an iteration boundary, TimeoutError
    # is raised — the pipeline must exit before producing a result.
    loop = _make_loop(timeout_seconds=1)
    with patch("agents.dual_loop.time") as mock_time:
        mock_time.monotonic.side_effect = [0.0, 2.0]
        with patch("agents.dual_loop._call_model", return_value=_PROPOSER_OK):
            with pytest.raises(TimeoutError):
                loop.run("input")


def test_timeout_fires_before_proposer_call():
    # US4: timeout must be checked before the proposer call so a timed-out run
    # makes zero additional API calls, wasting no quota.
    loop = _make_loop(timeout_seconds=1)
    with patch("agents.dual_loop.time") as mock_time:
        mock_time.monotonic.side_effect = [0.0, 2.0]
        with patch("agents.dual_loop._call_model") as mock_call:
            with pytest.raises(TimeoutError):
                loop.run("input")
    mock_call.assert_not_called()


# -- US4: model fail-over chain --


def test_fallback_to_second_model_when_first_fails():
    # US4: when the first model in a persona's chain raises an error, the next model
    # is tried automatically and the loop continues without raising to the caller.
    proposer = PersonaConfig(
        name="Proposer",
        models=["claude-sonnet-4-6", "claude-opus-4-7"],
        system_prompt="propose",
    )
    reviewer = PersonaConfig(
        name="Reviewer", models=["gemini-2.5-pro"], system_prompt="review"
    )
    loop = DualPersonaLoop(proposer, reviewer)
    tried_models: list[str] = []

    def dispatch(model, system_prompt, messages, max_tokens=2048):
        tried_models.append(model)
        if model == "claude-sonnet-4-6":
            raise RuntimeError("primary model unavailable")
        if model == "claude-opus-4-7":
            return _PROPOSER_OK
        return _REVIEWER_APPROVED

    with patch("agents.dual_loop._call_model", side_effect=dispatch):
        result = loop.run("input")
    assert "claude-sonnet-4-6" in tried_models
    assert "claude-opus-4-7" in tried_models
    assert result.verdict == _VERDICT_CONTENT


def test_fallback_logs_warning_on_model_failure(caplog):
    # US4: when a model in the chain fails and a fallback is used, a WARNING must be
    # logged so the operator can see which model was skipped and why.
    proposer = PersonaConfig(
        name="Proposer",
        models=["claude-sonnet-4-6", "claude-opus-4-7"],
        system_prompt="propose",
    )
    reviewer = PersonaConfig(
        name="Reviewer", models=["gemini-2.5-pro"], system_prompt="review"
    )
    loop = DualPersonaLoop(proposer, reviewer)

    def dispatch(model, system_prompt, messages, max_tokens=2048):
        if model == "claude-sonnet-4-6":
            raise RuntimeError("unavailable")
        if model == "claude-opus-4-7":
            return _PROPOSER_OK
        return _REVIEWER_APPROVED

    with caplog.at_level(logging.WARNING, logger="agents.dual_loop"):
        with patch("agents.dual_loop._call_model", side_effect=dispatch):
            loop.run("input")
    assert any(
        "claude-sonnet-4-6" in r.message
        for r in caplog.records
        if r.levelno == logging.WARNING
    )


def test_all_models_exhausted_raises_runtime_error():
    # US4: when every model in a persona's chain fails, RuntimeError must be raised —
    # the pipeline must exit cleanly before producing any partial output.
    proposer = PersonaConfig(
        name="Proposer", models=["claude-sonnet-4-6"], system_prompt="propose"
    )
    reviewer = PersonaConfig(
        name="Reviewer", models=["gemini-2.5-pro"], system_prompt="review"
    )
    loop = DualPersonaLoop(proposer, reviewer)
    with patch("agents.dual_loop._call_model", side_effect=RuntimeError("all down")):
        with pytest.raises(RuntimeError):
            loop.run("input")


# -- tag parsing: proposer --


def test_missing_proposer_verdict_tag_raises_value_error():
    # The contract requires the proposer to wrap output in <verdict> tags; a missing
    # tag is a protocol violation and must raise ValueError, not be silently ignored.
    loop = _make_loop()
    with patch("agents.dual_loop._call_model", return_value="No tags here at all."):
        with pytest.raises(ValueError):
            loop.run("input")


def test_verdict_tag_content_extracted_with_dotall():
    # The <verdict> tag content may span multiple lines; re.DOTALL must be used so
    # newlines inside the tag are preserved in the returned string.
    multi_line_content = "Line one.\nLine two.\nLine three."
    proposer_response = f"<verdict>{multi_line_content}</verdict>"
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model",
        side_effect=[proposer_response, _REVIEWER_APPROVED],
    ):
        result = loop.run("input")
    assert result.verdict == multi_line_content


# -- tag parsing: reviewer --


def test_reviewer_approved_case_insensitive():
    # The contract says APPROVED detection is case-insensitive; 'approved' (lowercase)
    # must be treated the same as 'APPROVED' to avoid fragile string matching.
    loop = _make_loop()
    reviewer_lowercase = "<verdict>approved</verdict>"
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, reviewer_lowercase]
    ):
        result = loop.run("input")
    assert result.verdict == _VERDICT_CONTENT


def test_reviewer_missing_verdict_tag_treated_as_needs_revision():
    # Per contract, a missing or malformed reviewer <verdict> tag is treated as
    # NEEDS REVISION — the loop must not raise but must continue iterating.
    responses = [
        _PROPOSER_OK,
        "No verdict tag — malformed reviewer response.",
        _PROPOSER_OK,
        _REVIEWER_APPROVED,
    ]
    loop = _make_loop()
    with patch("agents.dual_loop._call_model", side_effect=responses):
        result = loop.run("input")
    assert result.verdict == _VERDICT_CONTENT


# -- logging: FR-010 --


def test_run_logs_iteration_outcome_at_info(caplog):
    # FR-010: every iteration must produce an INFO log with the iteration number and
    # verdict so the operator can trace the negotiation without inspecting code.
    loop = _make_loop()
    with caplog.at_level(logging.INFO, logger="agents.dual_loop"):
        with patch(
            "agents.dual_loop._call_model",
            side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED],
        ):
            loop.run("input")
    info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert any("1" in m for m in info_messages)
    assert any("APPROVED" in m.upper() for m in info_messages)


# -- LoopOutput return type (T003) --


def test_run_returns_loop_output_instance():
    # run() must return a LoopOutput, not a bare string — callers depend on
    # .verdict and .log.
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ):
        result = loop.run("input")
    assert isinstance(result, LoopOutput)


def test_loop_output_verdict_equals_proposer_content():
    # LoopOutput.verdict must equal the content inside the proposer's <verdict> tag,
    # preserving the existing contract for downstream callers.
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ):
        result = loop.run("input")
    assert result.verdict == _VERDICT_CONTENT


def test_loop_output_log_is_conversation_log():
    # LoopOutput.log must be a ConversationLog so callers can write structured
    # turn records.
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ):
        result = loop.run("input")
    assert isinstance(result.log, ConversationLog)


def test_loop_output_log_has_correct_loop_name():
    # ConversationLog.loop_name must match the loop_name argument passed to
    # DualPersonaLoop so bundle_writer can label each log file correctly.
    loop = DualPersonaLoop(_PROPOSER, _REVIEWER, loop_name="Agent 0")
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ):
        result = loop.run("input")
    assert result.log.loop_name == "Agent 0"


def test_loop_output_log_has_two_turns_per_iteration():
    # Each iteration produces exactly 2 ConversationTurn entries (proposer + reviewer);
    # a 1-iteration approved run must have exactly 2 turns.
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ):
        result = loop.run("input")
    assert len(result.log.turns) == 2


def test_loop_output_log_has_four_turns_for_two_iterations():
    # A 2-iteration run (rejected then approved) must produce exactly 4 turns —
    # confirming all turns from all iterations are collected, not just the last.
    loop = _make_loop()
    responses = [_PROPOSER_OK, _REVIEWER_REJECTED, _PROPOSER_OK, _REVIEWER_APPROVED]
    with patch("agents.dual_loop._call_model", side_effect=responses):
        result = loop.run("input")
    assert len(result.log.turns) == 4


def test_turns_are_conversation_turn_instances():
    # Every entry in log.turns must be a ConversationTurn dataclass — callers rely on
    # .iteration, .role, .text, and .verdict fields being present.
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ):
        result = loop.run("input")
    assert all(isinstance(t, ConversationTurn) for t in result.log.turns)


def test_proposer_turn_has_empty_verdict():
    # Proposer turns carry no verdict value — .verdict must be "" so format_log can
    # distinguish proposer rows from reviewer rows without a separate role check.
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ):
        result = loop.run("input")
    proposer_turn = result.log.turns[0]
    assert proposer_turn.verdict == ""


def test_reviewer_approved_turn_has_approved_verdict():
    # A reviewer turn where the loop approved must carry verdict="APPROVED" so
    # format_log can display the correct status marker.
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ):
        result = loop.run("input")
    reviewer_turn = result.log.turns[1]
    assert reviewer_turn.verdict == "APPROVED"


def test_reviewer_rejected_turn_has_needs_revision_verdict():
    # A reviewer turn that rejected the proposal must carry verdict="NEEDS REVISION"
    # so format_log labels the turn correctly and operators see why revision happened.
    loop = _make_loop()
    responses = [_PROPOSER_OK, _REVIEWER_REJECTED, _PROPOSER_OK, _REVIEWER_APPROVED]
    with patch("agents.dual_loop._call_model", side_effect=responses):
        result = loop.run("input")
    first_reviewer_turn = result.log.turns[1]
    assert first_reviewer_turn.verdict == "NEEDS REVISION"


def test_final_say_reviewer_turn_has_final_say_verdict():
    # When the Final Say Protocol fires (last iteration, no consensus), the last
    # reviewer turn must carry verdict="FINAL_SAY" so format_log can mark it distinctly.
    responses = [
        f"<verdict>Proposal {i}</verdict>" if i % 2 == 1 else _REVIEWER_REJECTED
        for i in range(1, 11)
    ]
    loop = _make_loop(max_iterations=5)
    with patch("agents.dual_loop._call_model", side_effect=responses):
        result = loop.run("input")
    last_reviewer_turn = result.log.turns[-1]
    assert last_reviewer_turn.verdict == "FINAL_SAY"


def test_turn_iteration_numbers_are_correct():
    # Each ConversationTurn.iteration must match the 1-based loop counter so the
    # formatted log shows "Iteration 1", "Iteration 2", etc. in order.
    loop = _make_loop()
    responses = [_PROPOSER_OK, _REVIEWER_REJECTED, _PROPOSER_OK, _REVIEWER_APPROVED]
    with patch("agents.dual_loop._call_model", side_effect=responses):
        result = loop.run("input")
    assert result.log.turns[0].iteration == 1
    assert result.log.turns[1].iteration == 1
    assert result.log.turns[2].iteration == 2
    assert result.log.turns[3].iteration == 2


def test_turn_roles_match_persona_names():
    # ConversationTurn.role must equal the persona's .name field so the log header
    # reads "TestProposer" / "TestReviewer" rather than generic "proposer" / "reviewer".
    loop = _make_loop()
    with patch(
        "agents.dual_loop._call_model", side_effect=[_PROPOSER_OK, _REVIEWER_APPROVED]
    ):
        result = loop.run("input")
    assert result.log.turns[0].role == _PROPOSER.name
    assert result.log.turns[1].role == _REVIEWER.name
