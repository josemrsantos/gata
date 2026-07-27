from unittest.mock import MagicMock, patch

import pytest

from llm.grok import _COST_PER_M, GrokProvider

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_response(text: str, in_tok: int = 10, out_tok: int = 5) -> MagicMock:
    """Build a mock openai ChatCompletion response."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    usage = MagicMock()
    usage.prompt_tokens = in_tok
    usage.completion_tokens = out_tok
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


def _make_empty_response() -> MagicMock:
    """Build a mock response with no choices (empty content list)."""
    resp = MagicMock()
    resp.choices = []
    return resp


@pytest.fixture(autouse=True)
def _reset_grok_singleton():
    # Reset the module-level client singleton between tests so patches don't leak.
    import llm.grok as grok_mod

    original = grok_mod._client
    yield
    grok_mod._client = original


# ---------------------------------------------------------------------------
# model_id
# ---------------------------------------------------------------------------


def test_model_id_returns_constructor_argument():
    # GrokProvider.model_id must return exactly the model string passed at construction.
    provider = GrokProvider("grok-3")
    assert provider.model_id == "grok-3"


# ---------------------------------------------------------------------------
# generate() — happy path
# ---------------------------------------------------------------------------


def test_generate_returns_text_and_token_usage():
    # generate() must return the response text and a populated TokenUsage on success.
    provider = GrokProvider("grok-3")
    fake_resp = _make_response("Gata proposes a spider diagram.", in_tok=20, out_tok=8)
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.return_value = fake_resp
        text, usage = provider.generate("system", [{"role": "user", "content": "go"}])
    assert text == "Gata proposes a spider diagram."
    assert usage.model == "grok-3"
    assert usage.input_tokens == 20
    assert usage.output_tokens == 8


def test_generate_prepends_system_message():
    # generate() must inject the system prompt as the first message so Grok receives it.
    provider = GrokProvider("grok-3")
    fake_resp = _make_response("ok")
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.return_value = fake_resp
        provider.generate("be satirical", [{"role": "user", "content": "topic"}])
    call_args = mock_client_fn.return_value.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "be satirical"}
    assert messages[1] == {"role": "user", "content": "topic"}


def test_generate_passes_max_tokens_to_api():
    # generate() must forward max_tokens to the API so long outputs are not truncated.
    provider = GrokProvider("grok-3")
    fake_resp = _make_response("ok")
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.return_value = fake_resp
        provider.generate("sys", [{"role": "user", "content": "q"}], max_tokens=4096)
    call_args = mock_client_fn.return_value.chat.completions.create.call_args
    assert call_args.kwargs["max_tokens"] == 4096


# ---------------------------------------------------------------------------
# generate() — empty choices guard
# ---------------------------------------------------------------------------


def test_generate_raises_runtime_error_on_empty_choices():
    # generate() must raise RuntimeError when the API returns no choices so the
    # DualPersonaLoop fallback chain can try the next provider.
    provider = GrokProvider("grok-3")
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.return_value = (
            _make_empty_response()
        )
        with pytest.raises(RuntimeError, match="empty choices"):
            provider.generate("sys", [{"role": "user", "content": "q"}])


def test_generate_raises_runtime_error_on_none_content():
    # generate() must raise RuntimeError when choices are non-empty but message.content
    # is None (tool-use-only response), so the fallback chain tries the next provider.
    provider = GrokProvider("grok-3")
    resp = MagicMock()
    choice = MagicMock()
    choice.message.content = None
    resp.choices = [choice]
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.return_value = resp
        with pytest.raises(RuntimeError, match="empty response content"):
            provider.generate("sys", [{"role": "user", "content": "q"}])


# ---------------------------------------------------------------------------
# cost calculation
# ---------------------------------------------------------------------------


def test_generate_computes_correct_cost_for_grok3():
    # grok-3 is retired and confirmed (live API check, spec 039) to silently redirect
    # to and bill as grok-4.3 ($1.25/$2.50 per million) — cost_usd must reflect that
    # real billed rate, not the old standalone grok-3 rate.
    provider = GrokProvider("grok-3")
    fake_resp = _make_response("x", in_tok=1_000_000, out_tok=1_000_000)
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.return_value = fake_resp
        _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert abs(usage.cost_usd - 3.75) < 0.001  # $1.25 input + $2.50 output


def test_generate_computes_correct_cost_for_grok3_mini():
    # grok-3-mini is also confirmed (live API check, spec 039) to silently redirect
    # to and bill as grok-4.3 — same rate and same reasoning as grok-3 above.
    provider = GrokProvider("grok-3-mini")
    fake_resp = _make_response("x", in_tok=1_000_000, out_tok=1_000_000)
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.return_value = fake_resp
        _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert abs(usage.cost_usd - 3.75) < 0.001  # $1.25 input + $2.50 output


def test_generate_computes_correct_cost_for_grok4_3():
    # grok-4.3 is a genuinely live model (confirmed, does not redirect) — its own
    # entry in _COST_PER_M must carry its real rate ($1.25/$2.50 per million).
    provider = GrokProvider("grok-4.3")
    fake_resp = _make_response("x", in_tok=1_000_000, out_tok=1_000_000)
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.return_value = fake_resp
        _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert abs(usage.cost_usd - 3.75) < 0.001  # $1.25 input + $2.50 output


def test_generate_computes_correct_cost_for_grok_build_0_1():
    # grok-build-0.1 is the cheapest genuinely-live Grok model (confirmed, does not
    # redirect) — used as the new default panelist; rate is $1.00/$2.00 per million.
    provider = GrokProvider("grok-build-0.1")
    fake_resp = _make_response("x", in_tok=1_000_000, out_tok=1_000_000)
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.return_value = fake_resp
        _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert abs(usage.cost_usd - 3.00) < 0.001  # $1.00 input + $2.00 output


def test_generate_cost_defaults_to_zero_for_unknown_model():
    # generate() must return cost_usd=0.0 for unrecognised model IDs rather than crash.
    provider = GrokProvider("grok-99-mystery")
    fake_resp = _make_response("x", in_tok=100, out_tok=50)
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.return_value = fake_resp
        _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert usage.cost_usd == 0.0


# ---------------------------------------------------------------------------
# cost table coverage
# ---------------------------------------------------------------------------


def test_cost_table_covers_all_expected_models():
    # _COST_PER_M must include the three genuinely-live models (spec 039) plus the
    # four retired grok-3 variants, kept as priced aliases at the grok-4.3 rate they
    # now actually bill, so a leftover custom providers.yaml still gets a real cost.
    expected = {
        "grok-4.5",
        "grok-4.3",
        "grok-build-0.1",
        "grok-3",
        "grok-3-mini",
        "grok-3-fast",
        "grok-3-mini-fast",
    }
    assert expected.issubset(_COST_PER_M.keys())


def test_cost_table_retired_grok3_variants_priced_at_grok4_3_rate():
    # All four retired grok-3-family slugs are confirmed (live API check, spec 039)
    # to redirect to and bill as grok-4.3 — their table entries must match that rate
    # exactly, not their old individual (and now wrong) standalone rates.
    for model in ("grok-3", "grok-3-mini", "grok-3-fast", "grok-3-mini-fast"):
        assert _COST_PER_M[model] == (1.25, 2.50)


# ---------------------------------------------------------------------------
# provider fallback via DualPersonaLoop
# ---------------------------------------------------------------------------


def test_grok_provider_failure_falls_through_to_next_provider():
    # When GrokProvider.generate() raises, DualPersonaLoop must try the next provider
    # rather than propagating the exception — ensuring Gemini fallback works.
    from core.types import PersonaConfig, TokenUsage
    from llm.dual_loop import DualPersonaLoop

    # real GrokProvider wired to fail; mocks simulate fallback and reviewer
    grok = GrokProvider("grok-3")
    fallback = MagicMock()
    fallback.model_id = "gemini-2.5-flash"
    _fallback_usage = TokenUsage(
        model="gemini-2.5-flash", input_tokens=5, output_tokens=3, cost_usd=0.0
    )
    fallback.generate.return_value = (
        "<verdict>approved concept</verdict>",
        _fallback_usage,
    )
    reviewer = MagicMock()
    reviewer.model_id = "claude-sonnet-4-6"
    _reviewer_usage = TokenUsage(
        model="claude-sonnet-4-6", input_tokens=5, output_tokens=3, cost_usd=0.0
    )
    reviewer.generate.return_value = ("<verdict>APPROVED</verdict>", _reviewer_usage)
    proposer_cfg = PersonaConfig(
        name="Co-Satirist",
        providers=[grok, fallback],
        system_prompt="propose",
    )
    reviewer_cfg = PersonaConfig(
        name="Satirist",
        providers=[reviewer],
        system_prompt="review",
    )
    with patch("llm.grok._get_client") as mock_client_fn:
        mock_client_fn.return_value.chat.completions.create.side_effect = RuntimeError(
            "network error"
        )
        loop = DualPersonaLoop(proposer_cfg, reviewer_cfg, max_iterations=1)
        result = loop.run("initial brief")
    assert result.verdict == "approved concept"
    assert fallback.generate.call_count == 1
