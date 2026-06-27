import logging
from unittest.mock import MagicMock, patch

import pytest

from core.types import (
    ConversationLog,
    ConversationTurn,
    LoopOutput,
    PersonaConfig,
    TokenUsage,
)
from llm.dual_loop import DualPersonaLoop

_DUMMY_USAGE = TokenUsage(model="test", input_tokens=0, output_tokens=0, cost_usd=0.0)
_VERDICT_CONTENT = "Cultural angle: housing crisis as a cat territorial dispute."
_PROPOSER_OK = f"<verdict>{_VERDICT_CONTENT}</verdict>"
_REVIEWER_APPROVED = "<verdict>APPROVED</verdict>"
_REVIEWER_REJECTED = "<verdict>NEEDS REVISION\nToo obvious.</verdict>"


def _make_provider(model_id: str, responses=None, *, raises=None):
    """Return a mock LLMProvider whose generate() side-effects through responses."""
    provider = MagicMock()
    provider.model_id = model_id
    if raises is not None:
        provider.generate.side_effect = raises
    elif isinstance(responses, list):
        provider.generate.side_effect = [(r, _DUMMY_USAGE) for r in responses]
    else:
        provider.generate.return_value = (responses, _DUMMY_USAGE)
    return provider


def _make_loop_with_providers(
    proposer_responses,
    reviewer_responses,
    max_iterations=5,
    timeout_seconds=900,
):
    """Build a DualPersonaLoop and return it together with the mock provider objects."""
    p_provider = _make_provider("claude-sonnet-4-6", proposer_responses)
    r_provider = _make_provider("gemini-2.5-pro", reviewer_responses)
    proposer = PersonaConfig(
        name="TestProposer",
        providers=[p_provider],
        system_prompt="You are the proposer.",
    )
    reviewer = PersonaConfig(
        name="TestReviewer",
        providers=[r_provider],
        system_prompt="You are the reviewer.",
    )
    loop = DualPersonaLoop(proposer, reviewer, max_iterations, timeout_seconds)
    return loop, p_provider, r_provider


def _make_loop(
    proposer_responses, reviewer_responses, max_iterations=5, timeout_seconds=900
):  # noqa: E501
    """Build a DualPersonaLoop without exposing the provider mocks."""
    loop, _, _ = _make_loop_with_providers(
        proposer_responses, reviewer_responses, max_iterations, timeout_seconds
    )
    return loop


# -- happy path: approval on first iteration --


def test_approval_on_first_iteration_returns_verdict_content():
    # Verifies that when the reviewer approves on iteration 1, run() returns
    # the exact text inside the proposer's <verdict> tag and exits after one round.
    loop, p_provider, r_provider = _make_loop_with_providers(
        [_PROPOSER_OK], [_REVIEWER_APPROVED]
    )
    result = loop.run("initial input")
    assert result.verdict == _VERDICT_CONTENT
    assert p_provider.generate.call_count == 1
    assert r_provider.generate.call_count == 1


# -- US2: early consensus before max_iterations --


def test_early_exit_on_approval_at_iteration_2():
    # US2: when the reviewer approves at iteration 2 (not 1, not 5), the loop exits
    # immediately and does not call generate() for iterations 3-5.
    proposer_iter2 = "<verdict>Refined proposal after feedback.</verdict>"
    loop, p_provider, r_provider = _make_loop_with_providers(
        [_PROPOSER_OK, proposer_iter2],
        [_REVIEWER_REJECTED, _REVIEWER_APPROVED],
    )
    result = loop.run("input")
    assert result.verdict == "Refined proposal after feedback."
    assert p_provider.generate.call_count == 2
    assert r_provider.generate.call_count == 2


def test_early_exit_does_not_run_extra_iterations():
    # US2: loop must not run any iteration after the first APPROVED, confirming API
    # quota is not wasted on unnecessary calls once consensus is reached.
    loop, p_provider, r_provider = _make_loop_with_providers(
        [_PROPOSER_OK], [_REVIEWER_APPROVED]
    )
    loop.run("input")
    assert p_provider.generate.call_count == 1
    assert r_provider.generate.call_count == 1


# -- US3: Final Say Protocol at iteration 5 --


def test_final_say_returns_iteration_5_proposer_content():
    # US3: when no consensus after 5 iterations, the loop must return the proposer's
    # iteration-5 <verdict> content regardless of the reviewer's final verdict.
    final_content = "My definitive final-say proposal."
    proposer_responses = [
        f"<verdict>Proposal iteration {i}</verdict>" for i in range(1, 5)
    ] + [f"<verdict>{final_content}</verdict>"]
    reviewer_responses = [_REVIEWER_REJECTED] * 5
    loop = _make_loop(proposer_responses, reviewer_responses)
    result = loop.run("input")
    assert result.verdict == final_content


def test_final_say_runs_exactly_five_iterations():
    # US3: the loop must invoke each persona exactly 5 times when no approval is reached
    # — confirming the max_iterations cap is respected and never exceeded.
    proposer_responses = [f"<verdict>Proposal {i}</verdict>" for i in range(1, 6)]
    reviewer_responses = [_REVIEWER_REJECTED] * 5
    loop, p_provider, r_provider = _make_loop_with_providers(
        proposer_responses, reviewer_responses
    )
    loop.run("input")
    assert p_provider.generate.call_count == 5
    assert r_provider.generate.call_count == 5


def test_final_say_prompt_includes_final_say_keywords():
    # US3: at iteration 5, the proposer must receive a system prompt containing
    # Final Say Protocol language — enforcing genuine consideration of feedback.
    proposer_responses = [f"<verdict>Proposal {i}</verdict>" for i in range(1, 6)]
    reviewer_responses = [_REVIEWER_REJECTED] * 5
    loop, p_provider, _ = _make_loop_with_providers(
        proposer_responses, reviewer_responses
    )
    loop.run("input")
    # generate() is called as generate(system_prompt, messages, max_tokens=...)
    last_call = p_provider.generate.call_args_list[-1]
    system_prompt_used = last_call.args[0]
    assert "FINAL SAY" in system_prompt_used.upper()


# -- US4: timeout --


def test_timeout_raises_timeout_error():
    # US4: if elapsed time exceeds the budget at an iteration boundary, TimeoutError
    # is raised — the pipeline must exit before producing a result.
    loop, p_provider, _ = _make_loop_with_providers(
        [_PROPOSER_OK], [_REVIEWER_APPROVED], timeout_seconds=1
    )
    with patch("llm.dual_loop.time") as mock_time:
        mock_time.monotonic.side_effect = [0.0, 2.0]
        with pytest.raises(TimeoutError):
            loop.run("input")


def test_timeout_fires_before_proposer_call():
    # US4: timeout must be checked before the proposer call so a timed-out run
    # makes zero additional API calls, wasting no quota.
    loop, p_provider, _ = _make_loop_with_providers(
        [_PROPOSER_OK], [_REVIEWER_APPROVED], timeout_seconds=1
    )
    with patch("llm.dual_loop.time") as mock_time:
        mock_time.monotonic.side_effect = [0.0, 2.0]
        with pytest.raises(TimeoutError):
            loop.run("input")
    p_provider.generate.assert_not_called()


# -- US4: provider fail-over chain --


def test_fallback_to_second_provider_when_first_fails():
    # US4: when the first provider in a persona's chain raises an error, the next
    # provider is tried automatically and the loop continues without raising.
    p1 = _make_provider("claude-sonnet-4-6", raises=RuntimeError("primary unavailable"))
    p2 = _make_provider("claude-opus-4-7", [_PROPOSER_OK])
    r_prov = _make_provider("gemini-2.5-pro", [_REVIEWER_APPROVED])
    proposer = PersonaConfig(
        name="Proposer", providers=[p1, p2], system_prompt="propose"
    )
    reviewer = PersonaConfig(
        name="Reviewer", providers=[r_prov], system_prompt="review"
    )
    loop = DualPersonaLoop(proposer, reviewer)
    result = loop.run("input")
    assert p1.generate.called
    assert p2.generate.called
    assert result.verdict == _VERDICT_CONTENT


def test_fallback_logs_warning_on_provider_failure(caplog):
    # US4: when a provider in the chain fails and a fallback is used, a WARNING must
    # be logged so the operator can see which provider was skipped and why.
    p1 = _make_provider("claude-sonnet-4-6", raises=RuntimeError("unavailable"))
    p2 = _make_provider("claude-opus-4-7", [_PROPOSER_OK])
    r_prov = _make_provider("gemini-2.5-pro", [_REVIEWER_APPROVED])
    proposer = PersonaConfig(
        name="Proposer", providers=[p1, p2], system_prompt="propose"
    )
    reviewer = PersonaConfig(
        name="Reviewer", providers=[r_prov], system_prompt="review"
    )
    loop = DualPersonaLoop(proposer, reviewer)
    with caplog.at_level(logging.WARNING, logger="llm.dual_loop"):
        loop.run("input")
    assert any(
        "claude-sonnet-4-6" in r.message
        for r in caplog.records
        if r.levelno == logging.WARNING
    )


def test_all_providers_exhausted_raises_runtime_error():
    # US4: when every provider in a persona's chain fails, RuntimeError must be raised
    # — the pipeline must exit cleanly before producing any partial output.
    p = _make_provider("claude-sonnet-4-6", raises=RuntimeError("all down"))
    r = _make_provider("gemini-2.5-pro", [_REVIEWER_APPROVED])
    proposer = PersonaConfig(name="Proposer", providers=[p], system_prompt="propose")
    reviewer = PersonaConfig(name="Reviewer", providers=[r], system_prompt="review")
    loop = DualPersonaLoop(proposer, reviewer)
    with pytest.raises(RuntimeError):
        loop.run("input")


# -- tag parsing: proposer --


def test_missing_proposer_verdict_tag_raises_value_error():
    # The contract requires the proposer to wrap output in <verdict> tags; a missing
    # tag is a protocol violation and must raise ValueError, not be silently ignored.
    loop = _make_loop(["No tags here at all."], [_REVIEWER_APPROVED])
    with pytest.raises(ValueError):
        loop.run("input")


def test_verdict_tag_content_extracted_with_dotall():
    # The <verdict> tag content may span multiple lines; re.DOTALL must be used so
    # newlines inside the tag are preserved in the returned string.
    multi_line_content = "Line one.\nLine two.\nLine three."
    proposer_response = f"<verdict>{multi_line_content}</verdict>"
    loop = _make_loop([proposer_response], [_REVIEWER_APPROVED])
    result = loop.run("input")
    assert result.verdict == multi_line_content


# -- tag parsing: reviewer --


def test_reviewer_approved_case_insensitive():
    # The contract says APPROVED detection is case-insensitive; 'approved' (lowercase)
    # must be treated the same as 'APPROVED' to avoid fragile string matching.
    reviewer_lowercase = "<verdict>approved</verdict>"
    loop = _make_loop([_PROPOSER_OK], [reviewer_lowercase])
    result = loop.run("input")
    assert result.verdict == _VERDICT_CONTENT


def test_reviewer_missing_verdict_tag_treated_as_needs_revision():
    # Per contract, a missing or malformed reviewer <verdict> tag is treated as
    # NEEDS REVISION — the loop must not raise but must continue iterating.
    loop = _make_loop(
        [_PROPOSER_OK, _PROPOSER_OK],
        ["No verdict tag — malformed reviewer response.", _REVIEWER_APPROVED],
    )
    result = loop.run("input")
    assert result.verdict == _VERDICT_CONTENT


# -- logging: FR-010 --


def test_run_logs_completion_outcome_at_info(caplog):
    # FR-010: the loop must log start and completion at INFO so operators can see
    # agent progress without wading through per-iteration debug output.
    loop = _make_loop([_PROPOSER_OK], [_REVIEWER_APPROVED])
    with caplog.at_level(logging.INFO, logger="llm.dual_loop"):
        loop.run("input")
    info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert any("1" in m for m in info_messages)
    assert any("approved" in m.lower() for m in info_messages)


# -- LoopOutput return type (T003) --


def test_run_returns_loop_output_instance():
    # run() must return a LoopOutput, not a bare string — callers depend on
    # .verdict and .log.
    loop = _make_loop([_PROPOSER_OK], [_REVIEWER_APPROVED])
    result = loop.run("input")
    assert isinstance(result, LoopOutput)


def test_loop_output_verdict_equals_proposer_content():
    # LoopOutput.verdict must equal the content inside the proposer's <verdict> tag,
    # preserving the existing contract for downstream callers.
    loop = _make_loop([_PROPOSER_OK], [_REVIEWER_APPROVED])
    result = loop.run("input")
    assert result.verdict == _VERDICT_CONTENT


def test_loop_output_log_is_conversation_log():
    # LoopOutput.log must be a ConversationLog so callers can write structured
    # turn records.
    loop = _make_loop([_PROPOSER_OK], [_REVIEWER_APPROVED])
    result = loop.run("input")
    assert isinstance(result.log, ConversationLog)


def test_loop_output_log_has_correct_loop_name():
    # ConversationLog.loop_name must match the loop_name argument passed to
    # DualPersonaLoop so bundle_writer can label each log file correctly.
    p_prov = _make_provider("claude-sonnet-4-6", [_PROPOSER_OK])
    r_prov = _make_provider("gemini-2.5-pro", [_REVIEWER_APPROVED])
    proposer = PersonaConfig(name="TestProposer", providers=[p_prov], system_prompt="p")
    reviewer = PersonaConfig(name="TestReviewer", providers=[r_prov], system_prompt="r")
    loop = DualPersonaLoop(proposer, reviewer, loop_name="TestLoop")
    result = loop.run("input")
    assert result.log.loop_name == "TestLoop"


def test_loop_output_log_has_two_turns_per_iteration():
    # Each iteration produces exactly 2 ConversationTurn entries (proposer + reviewer);
    # a 1-iteration approved run must have exactly 2 turns.
    loop = _make_loop([_PROPOSER_OK], [_REVIEWER_APPROVED])
    result = loop.run("input")
    assert len(result.log.turns) == 2


def test_loop_output_log_has_four_turns_for_two_iterations():
    # A 2-iteration run (rejected then approved) must produce exactly 4 turns —
    # confirming all turns from all iterations are collected, not just the last.
    loop = _make_loop(
        [_PROPOSER_OK, _PROPOSER_OK], [_REVIEWER_REJECTED, _REVIEWER_APPROVED]
    )
    result = loop.run("input")
    assert len(result.log.turns) == 4


def test_turns_are_conversation_turn_instances():
    # Every entry in log.turns must be a ConversationTurn dataclass — callers rely on
    # .iteration, .role, .text, and .verdict fields being present.
    loop = _make_loop([_PROPOSER_OK], [_REVIEWER_APPROVED])
    result = loop.run("input")
    assert all(isinstance(t, ConversationTurn) for t in result.log.turns)


def test_proposer_turn_has_empty_verdict():
    # Proposer turns carry no verdict value — .verdict must be "" so format_log can
    # distinguish proposer rows from reviewer rows without a separate role check.
    loop = _make_loop([_PROPOSER_OK], [_REVIEWER_APPROVED])
    result = loop.run("input")
    proposer_turn = result.log.turns[0]
    assert proposer_turn.verdict == ""


def test_reviewer_approved_turn_has_approved_verdict():
    # A reviewer turn where the loop approved must carry verdict="APPROVED" so
    # format_log can display the correct status marker.
    loop = _make_loop([_PROPOSER_OK], [_REVIEWER_APPROVED])
    result = loop.run("input")
    reviewer_turn = result.log.turns[1]
    assert reviewer_turn.verdict == "APPROVED"


def test_reviewer_rejected_turn_has_needs_revision_verdict():
    # A reviewer turn that rejected the proposal must carry verdict="NEEDS REVISION"
    # so format_log labels the turn correctly and operators see why revision happened.
    loop = _make_loop(
        [_PROPOSER_OK, _PROPOSER_OK], [_REVIEWER_REJECTED, _REVIEWER_APPROVED]
    )
    result = loop.run("input")
    first_reviewer_turn = result.log.turns[1]
    assert first_reviewer_turn.verdict == "NEEDS REVISION"


def test_final_say_reviewer_turn_has_final_say_verdict():
    # When the Final Say Protocol fires (last iteration, no consensus), the last
    # reviewer turn must carry verdict="FINAL_SAY" so format_log can mark it distinctly.
    proposer_responses = [f"<verdict>Proposal {i}</verdict>" for i in range(1, 6)]
    reviewer_responses = [_REVIEWER_REJECTED] * 5
    loop = _make_loop(proposer_responses, reviewer_responses, max_iterations=5)
    result = loop.run("input")
    last_reviewer_turn = result.log.turns[-1]
    assert last_reviewer_turn.verdict == "FINAL_SAY"


def test_turn_iteration_numbers_are_correct():
    # Each ConversationTurn.iteration must match the 1-based loop counter so the
    # formatted log shows "Iteration 1", "Iteration 2", etc. in order.
    loop = _make_loop(
        [_PROPOSER_OK, _PROPOSER_OK], [_REVIEWER_REJECTED, _REVIEWER_APPROVED]
    )
    result = loop.run("input")
    assert result.log.turns[0].iteration == 1
    assert result.log.turns[1].iteration == 1
    assert result.log.turns[2].iteration == 2
    assert result.log.turns[3].iteration == 2


def test_turn_roles_match_persona_names():
    # ConversationTurn.role must equal the persona's .name field so the log header
    # reads "TestProposer" / "TestReviewer" rather than generic "proposer" / "reviewer".
    loop, _, _ = _make_loop_with_providers([_PROPOSER_OK], [_REVIEWER_APPROVED])
    result = loop.run("input")
    assert result.log.turns[0].role == "TestProposer"
    assert result.log.turns[1].role == "TestReviewer"
