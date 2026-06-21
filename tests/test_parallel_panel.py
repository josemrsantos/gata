from unittest.mock import MagicMock

import pytest

from core.types import (
    PersonaConfig,
    TokenUsage,
)
from llm.base import ConversationProtocol
from llm.dual_loop import DualPersonaLoop
from llm.parallel_panel import ParallelPanel

# -- helpers --


def _make_provider(
    model_id: str, response: str, raise_exc: Exception | None = None
) -> MagicMock:
    provider = MagicMock()
    provider.model_id = model_id
    usage = TokenUsage(
        model=model_id, input_tokens=10, output_tokens=20, cost_usd=0.001
    )
    if raise_exc:
        provider.generate.side_effect = raise_exc
    else:
        provider.generate.return_value = (response, usage)
    return provider


def _make_panelist(name: str, response: str) -> PersonaConfig:
    return PersonaConfig(
        name=name, providers=[_make_provider(name, response)], system_prompt="sys"
    )


def _make_failing_panelist(name: str) -> PersonaConfig:
    return PersonaConfig(
        name=name,
        providers=[_make_provider(name, "", raise_exc=RuntimeError("provider failed"))],
        system_prompt="sys",
    )


def _make_aggregator(response: str) -> PersonaConfig:
    return PersonaConfig(
        name="Aggregator",
        providers=[_make_provider("claude-sonnet", response)],
        system_prompt="sys",
    )


def _std_panel(panelists: list[PersonaConfig], name: str = "Test") -> ParallelPanel:
    return ParallelPanel(
        panelists=panelists, aggregator=_make_aggregator(_AGG), panel_name=name
    )


# -- test data --

_P1 = "Concept A text.\n<verdict>Concept A: cat diplomacy</verdict>"
_P2 = "Concept B text.\n<verdict>Concept B: cat veto</verdict>"
_P3 = "Concept C text.\n<verdict>Concept C: cat walkout</verdict>"
_AGG = "Best concept is B.\nPICK: 2\n<verdict>Concept B: cat veto</verdict>"


# -- happy path --


def test_happy_path_verdict_equals_aggregator_pick():
    # ParallelPanel.run() must return the verdict chosen by the aggregator, not a
    # random or first-panelist choice — this is the core contract of the protocol.
    panelists = [
        _make_panelist("claude", _P1),
        _make_panelist("grok", _P2),
        _make_panelist("gemini", _P3),
    ]
    result = _std_panel(panelists).run("cats at the UN")
    assert result.verdict == "Concept B: cat veto"


def test_happy_path_log_has_one_turn_per_panelist():
    # ConversationLog must contain one turn per successful panelist so bundle_writer
    # can attribute each concept to its model in the output.
    panelists = [
        _make_panelist("claude", _P1),
        _make_panelist("grok", _P2),
        _make_panelist("gemini", _P3),
    ]
    result = _std_panel(panelists).run("cats at the UN")
    panelist_roles = [t.role for t in result.log.turns if t.role != "Aggregator"]
    assert panelist_roles == ["claude", "grok", "gemini"]


def test_happy_path_log_ends_with_aggregator_turn():
    # ConversationLog must end with exactly one Aggregator turn carrying a PICK label
    # so bundle_writer can display which concept was selected.
    panelists = [_make_panelist("claude", _P1), _make_panelist("grok", _P2)]
    result = _std_panel(panelists).run("cats at the UN")
    agg_turns = [t for t in result.log.turns if t.role == "Aggregator"]
    assert len(agg_turns) == 1
    assert agg_turns[0].verdict.startswith("PICK:")


def test_happy_path_all_turns_have_iteration_one():
    # All turns must have iteration=1 — unlike DualPersonaLoop there are no
    # multi-round iterations; mismatched values break the HTML log rendering.
    panelists = [_make_panelist("claude", _P1), _make_panelist("grok", _P2)]
    result = _std_panel(panelists).run("cats at the UN")
    assert all(t.iteration == 1 for t in result.log.turns)


def test_happy_path_telemetry_accumulates_all_calls():
    # AgentTelemetry.calls must include one TokenUsage per panelist plus one for the
    # aggregator — callers use this to report total token spend for the agent.
    panelists = [
        _make_panelist("claude", _P1),
        _make_panelist("grok", _P2),
        _make_panelist("gemini", _P3),
    ]
    result = _std_panel(panelists).run("cats at the UN")
    assert result.telemetry is not None
    assert len(result.telemetry.calls) == 4  # 3 panelists + 1 aggregator


def test_happy_path_panelist_verdict_is_empty_string():
    # Panelist turns must have verdict="" — they are generators not evaluators; a
    # non-empty string would imply approval/rejection semantics that don't exist here.
    panelists = [_make_panelist("claude", _P1), _make_panelist("grok", _P2)]
    result = _std_panel(panelists).run("cats at the UN")
    panelist_turns = [t for t in result.log.turns if t.role != "Aggregator"]
    assert all(t.verdict == "" for t in panelist_turns)


# -- panelist failure handling --


def test_one_panelist_failure_is_skipped():
    # When one panelist's provider raises, run() must skip it and still call the
    # aggregator with the remaining successful concepts — one bad provider must not
    # abort the whole panel.
    panelists = [
        _make_panelist("claude", _P1),
        _make_failing_panelist("grok"),
        _make_panelist("gemini", _P3),
    ]
    result = _std_panel(panelists).run("cats at the UN")
    # 2 successful panelist turns + 1 aggregator turn = 3
    assert len(result.log.turns) == 3


def test_failing_panelist_excluded_from_log():
    # A failed panelist must not appear in ConversationLog — including it would imply
    # a concept was generated when none was, corrupting the bundle output.
    panelists = [
        _make_panelist("claude", _P1),
        _make_failing_panelist("grok"),
        _make_panelist("gemini", _P3),
    ]
    result = _std_panel(panelists).run("cats at the UN")
    assert "grok" not in [t.role for t in result.log.turns]


def test_failing_panelist_not_counted_in_telemetry():
    # A failed panelist must not contribute a TokenUsage entry — it made no successful
    # API call and should not inflate token cost reporting.
    panelists = [
        _make_panelist("claude", _P1),
        _make_failing_panelist("grok"),
        _make_panelist("gemini", _P3),
    ]
    result = _std_panel(panelists).run("cats at the UN")
    assert result.telemetry is not None
    assert len(result.telemetry.calls) == 3  # 2 successful + 1 aggregator


def test_all_panelists_fail_raises_runtime_error():
    # When every panelist fails, run() must raise RuntimeError so the pipeline
    # caller can handle the error rather than silently returning an empty result.
    panelists = [_make_failing_panelist("claude"), _make_failing_panelist("grok")]
    with pytest.raises(RuntimeError, match="all panelists failed"):
        _std_panel(panelists).run("cats at the UN")


def test_aggregator_failure_raises_runtime_error():
    # When the aggregator exhausts all its providers, run() must propagate RuntimeError
    # so the pipeline caller knows the final verdict could not be produced.
    panelists = [_make_panelist("claude", _P1)]
    failing_agg = PersonaConfig(
        name="Aggregator",
        providers=[_make_provider("claude", "", raise_exc=RuntimeError("agg failed"))],
        system_prompt="sys",
    )
    panel = ParallelPanel(
        panelists=panelists, aggregator=failing_agg, panel_name="Test"
    )
    with pytest.raises(RuntimeError):
        panel.run("cats at the UN")


# -- log and telemetry identity --


def test_log_loop_name_equals_panel_name():
    # ConversationLog.loop_name must equal the panel_name constructor argument so
    # bundle_writer labels the log section with the correct agent name.
    panelists = [_make_panelist("claude", _P1)]
    result = _std_panel(panelists, name="MyPanel").run("topic")
    assert result.log.loop_name == "MyPanel"


def test_telemetry_agent_name_equals_panel_name():
    # AgentTelemetry.agent_name must match panel_name so RunTelemetry.agents correctly
    # attributes this agent's cost and duration in the pipeline summary.
    panelists = [_make_panelist("claude", _P1)]
    result = _std_panel(panelists, name="MyPanel").run("topic")
    assert result.telemetry is not None
    assert result.telemetry.agent_name == "MyPanel"


def test_telemetry_iterations_is_one():
    # ParallelPanel always runs exactly one round — telemetry.iterations must be 1
    # so the pipeline summary does not report misleading multi-iteration counts.
    panelists = [_make_panelist("claude", _P1), _make_panelist("grok", _P2)]
    result = _std_panel(panelists).run("topic")
    assert result.telemetry is not None
    assert result.telemetry.iterations == 1


# -- ConversationProtocol ABC conformance --


def test_parallel_panel_satisfies_conversation_protocol():
    # ParallelPanel must be a subclass of ConversationProtocol so any caller that
    # holds a protocol reference can accept either topology interchangeably.
    assert issubclass(ParallelPanel, ConversationProtocol)


def test_dual_persona_loop_satisfies_conversation_protocol():
    # DualPersonaLoop must also satisfy ConversationProtocol — confirming that both
    # topologies share the same interface and can be swapped without changing callers.
    assert issubclass(DualPersonaLoop, ConversationProtocol)
