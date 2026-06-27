from core.types import AgentTelemetry, RunTelemetry, TokenUsage


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
