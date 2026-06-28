import concurrent.futures
import threading
from unittest.mock import patch

from core.types import PersonaConfig, TokenUsage

# -- helpers --


def _make_usage(model="test-model", inp=100, out=50, cost=0.001):
    return TokenUsage(model=model, input_tokens=inp, output_tokens=out, cost_usd=cost)


def _verdict(content):
    return f"Response. <verdict>{content}</verdict>"


def _pick(n=1, content="picked"):
    return f"PICK: {n}\n<verdict>{content}</verdict>"


def _make_panelists(names=("pa", "pb")):
    return [
        PersonaConfig(name=n, providers=[], system_prompt="sys", max_tokens=100)
        for n in names
    ]


def _make_aggregator(name="agg"):
    return PersonaConfig(name=name, providers=[], system_prompt="sys", max_tokens=100)


class _CallMock:
    """Thread-safe per-persona response dispenser for _call_persona mocking."""

    def __init__(self, responses: dict[str, list]):
        self._lock = threading.Lock()
        self._queues = {k: list(v) for k, v in responses.items()}
        self.calls: list[tuple[str, list]] = []

    def __call__(self, persona, messages):
        with self._lock:
            self.calls.append((persona.name, messages))
            queue = self._queues.get(persona.name, [])
            if not queue:
                raise RuntimeError(f"no more responses for {persona.name!r}")
            result = queue.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


# -- tests --


def test_single_iteration_single_panelist():
    # With one panelist and iterations=1 the returned verdict must be the panelist's
    # response content (via aggregator selection), proving the basic flow works.
    from llm.fair_parallel_panel import FairParallelPanel

    mock = _CallMock(
        {
            "pa": [(_verdict("concept-a"), _make_usage())],
            "agg": [(_pick(1, "concept-a"), _make_usage())],
        }
    )
    panel = FairParallelPanel(
        _make_panelists(["pa"]), _make_aggregator(), "P", iterations=1
    )
    with patch.object(FairParallelPanel, "_call_persona", mock):
        result = panel.run("topic")
    assert "concept-a" in result.verdict


def test_single_iteration_three_panelists():
    # With three panelists and iterations=1 the aggregator must receive all three
    # concepts so it can pick the best one, not just a subset.
    from llm.fair_parallel_panel import FairParallelPanel

    mock = _CallMock(
        {
            "pa": [(_verdict("concept-a"), _make_usage("m1"))],
            "pb": [(_verdict("concept-b"), _make_usage("m2"))],
            "pc": [(_verdict("concept-c"), _make_usage("m3"))],
            "agg": [(_pick(2, "concept-b"), _make_usage("m4"))],
        }
    )
    panel = FairParallelPanel(
        _make_panelists(["pa", "pb", "pc"]), _make_aggregator(), "P", iterations=1
    )
    with patch.object(FairParallelPanel, "_call_persona", mock):
        panel.run("topic")
    agg_calls = [c for c in mock.calls if c[0] == "agg"]
    assert len(agg_calls) == 1
    agg_prompt = agg_calls[0][1][0]["content"]
    assert "concept-a" in agg_prompt
    assert "concept-b" in agg_prompt
    assert "concept-c" in agg_prompt


def test_second_round_uses_peer_responses():
    # In round 2 each panelist's prompt must contain the other panelists' round-1
    # verdict content so the collaborative exchange actually happens.
    from llm.fair_parallel_panel import FairParallelPanel

    mock = _CallMock(
        {
            "pa": [
                (_verdict("a-r1-unique"), _make_usage()),
                (_verdict("a-r2"), _make_usage()),
            ],
            "pb": [
                (_verdict("b-r1-unique"), _make_usage()),
                (_verdict("b-r2"), _make_usage()),
            ],
            "agg": [(_pick(1, "picked"), _make_usage())],
        }
    )
    panel = FairParallelPanel(
        _make_panelists(["pa", "pb"]), _make_aggregator(), "P", iterations=2
    )
    with patch.object(FairParallelPanel, "_call_persona", mock):
        panel.run("topic")
    pa_round2_calls = [c for c in mock.calls if c[0] == "pa"]
    assert len(pa_round2_calls) == 2
    r2_prompt = pa_round2_calls[1][1][0]["content"]
    assert "b-r1-unique" in r2_prompt
    pb_round2_calls = [c for c in mock.calls if c[0] == "pb"]
    r2_prompt_pb = pb_round2_calls[1][1][0]["content"]
    assert "a-r1-unique" in r2_prompt_pb


def test_timed_out_panelist_skipped():
    # A panelist whose future raises TimeoutError must be skipped and the run must
    # still complete with the remaining panelists, satisfying the fault-tolerance goal.
    from llm.fair_parallel_panel import FairParallelPanel

    mock = _CallMock(
        {
            "pa": [concurrent.futures.TimeoutError()],
            "pb": [
                (_verdict("concept-b"), _make_usage()),
                (_verdict("b-r2"), _make_usage()),
            ],
            "agg": [(_pick(1, "concept-b"), _make_usage())],
        }
    )
    panel = FairParallelPanel(
        _make_panelists(["pa", "pb"]),
        _make_aggregator(),
        "P",
        iterations=2,
        panelist_timeout=60.0,
    )
    with patch.object(FairParallelPanel, "_call_persona", mock):
        result = panel.run("topic")
    assert "concept-b" in result.verdict


def test_failed_panelist_skipped():
    # A panelist that raises a RuntimeError (all providers exhausted) must be skipped
    # and the run must still complete so a single bad provider does not halt the panel.
    from llm.fair_parallel_panel import FairParallelPanel

    mock = _CallMock(
        {
            "pa": [RuntimeError("all providers exhausted")],
            "pb": [
                (_verdict("concept-b"), _make_usage()),
                (_verdict("b-r2"), _make_usage()),
            ],
            "agg": [(_pick(1, "b-r2"), _make_usage())],
        }
    )
    panel = FairParallelPanel(
        _make_panelists(["pa", "pb"]),
        _make_aggregator(),
        "P",
        iterations=2,
        panelist_timeout=60.0,
    )
    with patch.object(FairParallelPanel, "_call_persona", mock):
        result = panel.run("topic")
    assert result.verdict


def test_all_panelists_fail_raises():
    # When every panelist fails in round 1 a RuntimeError must be raised because
    # there is no content to aggregate and the run cannot produce a valid result.
    import pytest

    from llm.fair_parallel_panel import FairParallelPanel

    mock = _CallMock(
        {
            "pa": [RuntimeError("fail")],
            "pb": [RuntimeError("fail")],
            "agg": [],
        }
    )
    panel = FairParallelPanel(
        _make_panelists(["pa", "pb"]),
        _make_aggregator(),
        "P",
        iterations=1,
    )
    with patch.object(FairParallelPanel, "_call_persona", mock):
        with pytest.raises(RuntimeError):
            panel.run("topic")


def test_single_survivor_skips_peer_sharing():
    # When only one panelist survives round 1 its round-2 prompt must NOT contain a
    # peer section — sharing is meaningless with no peers and would confuse the model.
    from llm.fair_parallel_panel import FairParallelPanel

    mock = _CallMock(
        {
            "pa": [RuntimeError("fail")],
            "pb": [
                (_verdict("b-r1"), _make_usage()),
                (_verdict("b-r2"), _make_usage()),
            ],
            "agg": [(_pick(1, "b-r2"), _make_usage())],
        }
    )
    panel = FairParallelPanel(
        _make_panelists(["pa", "pb"]),
        _make_aggregator(),
        "P",
        iterations=2,
    )
    with patch.object(FairParallelPanel, "_call_persona", mock):
        panel.run("topic")
    pb_calls = [c for c in mock.calls if c[0] == "pb"]
    assert len(pb_calls) == 2
    r2_prompt = pb_calls[1][1][0]["content"]
    assert "Other panelists proposed" not in r2_prompt


def test_telemetry_aggregates_all_rounds():
    # The AgentTelemetry must include token-usage records from every round and the
    # aggregator call so cost reporting reflects the full run, not just one round.
    from llm.fair_parallel_panel import FairParallelPanel

    mock = _CallMock(
        {
            "pa": [
                (_verdict("a-r1"), _make_usage("m-pa-r1")),
                (_verdict("a-r2"), _make_usage("m-pa-r2")),
            ],
            "pb": [
                (_verdict("b-r1"), _make_usage("m-pb-r1")),
                (_verdict("b-r2"), _make_usage("m-pb-r2")),
            ],
            "agg": [(_pick(1, "picked"), _make_usage("m-agg"))],
        }
    )
    panel = FairParallelPanel(
        _make_panelists(["pa", "pb"]),
        _make_aggregator(),
        "P",
        iterations=2,
    )
    with patch.object(FairParallelPanel, "_call_persona", mock):
        result = panel.run("topic")
    assert result.telemetry is not None
    models = [c.model for c in result.telemetry.calls]
    assert "m-pa-r1" in models
    assert "m-pa-r2" in models
    assert "m-pb-r1" in models
    assert "m-pb-r2" in models
    assert "m-agg" in models
    assert len(result.telemetry.calls) == 5


def test_panelist_timeout_default():
    # The default panelist_timeout must be 60.0 seconds — large enough to let a
    # primary provider fail (~20s) and a Spec 032 fallback still complete.
    from llm.fair_parallel_panel import FairParallelPanel

    panel = FairParallelPanel(_make_panelists(), _make_aggregator())
    assert panel._panelist_timeout == 60.0


def test_iterations_default():
    # The default number of exchange rounds must be 2 to enable at least one round
    # of peer sharing before the aggregator decides.
    from llm.fair_parallel_panel import FairParallelPanel

    panel = FairParallelPanel(_make_panelists(), _make_aggregator())
    assert panel._iterations == 2


def test_log_contains_round_markers():
    # ConversationLog turns must record iteration numbers matching actual rounds so
    # the audit trail shows which exchange produced which response.
    from llm.fair_parallel_panel import FairParallelPanel

    mock = _CallMock(
        {
            "pa": [
                (_verdict("a-r1"), _make_usage()),
                (_verdict("a-r2"), _make_usage()),
            ],
            "pb": [
                (_verdict("b-r1"), _make_usage()),
                (_verdict("b-r2"), _make_usage()),
            ],
            "agg": [(_pick(1, "picked"), _make_usage())],
        }
    )
    panel = FairParallelPanel(
        _make_panelists(["pa", "pb"]),
        _make_aggregator(),
        "P",
        iterations=2,
    )
    with patch.object(FairParallelPanel, "_call_persona", mock):
        result = panel.run("topic")
    iterations_in_log = {t.iteration for t in result.log.turns}
    assert 1 in iterations_in_log
    assert 2 in iterations_in_log


def test_aggregator_receives_final_round_responses():
    # The aggregator must receive each panelist's final-round verdict, not the
    # round-1 verdict, so it is selecting from the most refined proposals.
    from llm.fair_parallel_panel import FairParallelPanel

    mock = _CallMock(
        {
            "pa": [
                (_verdict("a-stale-r1"), _make_usage()),
                (_verdict("a-final-r2"), _make_usage()),
            ],
            "pb": [
                (_verdict("b-stale-r1"), _make_usage()),
                (_verdict("b-final-r2"), _make_usage()),
            ],
            "agg": [(_pick(1, "a-final-r2"), _make_usage())],
        }
    )
    panel = FairParallelPanel(
        _make_panelists(["pa", "pb"]),
        _make_aggregator(),
        "P",
        iterations=2,
    )
    with patch.object(FairParallelPanel, "_call_persona", mock):
        panel.run("topic")
    agg_calls = [c for c in mock.calls if c[0] == "agg"]
    agg_prompt = agg_calls[0][1][0]["content"]
    assert "a-final-r2" in agg_prompt
    assert "b-final-r2" in agg_prompt
    assert "a-stale-r1" not in agg_prompt
    assert "b-stale-r1" not in agg_prompt
