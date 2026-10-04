from unittest.mock import MagicMock

import pytest

import llm.claude as claude_mod
from llm.claude import _COST_PER_M, ClaudeProvider

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_response(text: str, in_tok: int = 10, out_tok: int = 5) -> MagicMock:
    """Build a mock anthropic Message response."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    usage = MagicMock()
    usage.input_tokens = in_tok
    usage.output_tokens = out_tok
    resp = MagicMock()
    resp.content = [block]
    resp.usage = usage
    resp.stop_reason = "end_turn"
    return resp


@pytest.fixture(autouse=True)
def _reset_claude_singleton():
    # Reset the module-level client singleton between tests so mocks don't leak.
    import llm.claude as claude_mod

    original = claude_mod._client
    yield
    claude_mod._client = original


# ---------------------------------------------------------------------------
# model_id
# ---------------------------------------------------------------------------


def test_model_id_returns_constructor_argument():
    # ClaudeProvider.model_id must return exactly the constructor's model string.
    provider = ClaudeProvider("claude-sonnet-4-6")
    assert provider.model_id == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# client property (Spec 042 FR-002)
# ---------------------------------------------------------------------------


def test_client_property_returns_the_singleton_anthropic_client():
    # client must expose the same lazily-created singleton generate() uses, so
    # agents needing raw SDK access (e.g. web search tool use) share one client.
    import llm.claude as claude_mod

    provider = ClaudeProvider("claude-sonnet-4-6")
    claude_mod._client = None
    client = provider.client
    assert client is claude_mod._client
    # A second access must not create a new client.
    assert provider.client is client


# ---------------------------------------------------------------------------
# generate() — happy path
# ---------------------------------------------------------------------------


def test_generate_returns_text_and_token_usage():
    # generate() must return the response text and a populated TokenUsage on success.
    import llm.claude as claude_mod

    provider = ClaudeProvider("claude-sonnet-4-6")
    claude_mod._client = MagicMock()
    claude_mod._client.messages.create.return_value = _make_response(
        "Gata proposes a spider diagram.", in_tok=20, out_tok=8
    )
    text, usage = provider.generate("system", [{"role": "user", "content": "go"}])
    assert text == "Gata proposes a spider diagram."
    assert usage.model == "claude-sonnet-4-6"
    assert usage.input_tokens == 20
    assert usage.output_tokens == 8


def test_generate_raises_runtime_error_on_empty_content():
    # generate() must raise RuntimeError when the API returns an empty content list
    # so the fallback chain can try the next provider.
    import llm.claude as claude_mod

    provider = ClaudeProvider("claude-sonnet-4-6")
    claude_mod._client = MagicMock()
    resp = MagicMock()
    resp.content = []
    claude_mod._client.messages.create.return_value = resp
    with pytest.raises(RuntimeError, match="empty content"):
        provider.generate("sys", [{"role": "user", "content": "q"}])


# ---------------------------------------------------------------------------
# cost calculation — current, correctly priced models
# ---------------------------------------------------------------------------


def test_generate_computes_correct_cost_for_sonnet_4_6():
    # generate() must compute cost_usd using claude-sonnet-4-6's $3.00/$15.00 rate.
    import llm.claude as claude_mod

    provider = ClaudeProvider("claude-sonnet-4-6")
    claude_mod._client = MagicMock()
    claude_mod._client.messages.create.return_value = _make_response(
        "x", in_tok=1_000_000, out_tok=1_000_000
    )
    _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert abs(usage.cost_usd - 18.00) < 0.001  # $3 input + $15 output


def test_generate_computes_correct_cost_for_opus_4_7():
    # generate() must use claude-opus-4-7's current rate ($5.00/$25.00/MTok), not the
    # old pre-repricing rate of $15.00/$75.00 that used to live in _COST_PER_M.
    import llm.claude as claude_mod

    provider = ClaudeProvider("claude-opus-4-7")
    claude_mod._client = MagicMock()
    claude_mod._client.messages.create.return_value = _make_response(
        "x", in_tok=1_000_000, out_tok=1_000_000
    )
    _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert abs(usage.cost_usd - 30.00) < 0.001  # $5 input + $25 output


def test_generate_computes_correct_cost_for_opus_4_8():
    # Same repricing fix as Opus 4.7 — Opus 4.8 shares the $5.00/$25.00/MTok rate.
    import llm.claude as claude_mod

    provider = ClaudeProvider("claude-opus-4-8")
    claude_mod._client = MagicMock()
    claude_mod._client.messages.create.return_value = _make_response(
        "x", in_tok=1_000_000, out_tok=1_000_000
    )
    _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert abs(usage.cost_usd - 30.00) < 0.001  # $5 input + $25 output


def test_generate_computes_correct_cost_for_haiku_4_5():
    # generate() must use claude-haiku-4-5's current rate ($1.00/$5.00/MTok), not the
    # old Haiku 3.5 rate of $0.80/$4.00 that was left over in _COST_PER_M.
    import llm.claude as claude_mod

    provider = ClaudeProvider("claude-haiku-4-5-20251001")
    claude_mod._client = MagicMock()
    claude_mod._client.messages.create.return_value = _make_response(
        "x", in_tok=1_000_000, out_tok=1_000_000
    )
    _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert abs(usage.cost_usd - 6.00) < 0.001  # $1 input + $5 output


def test_generate_cost_defaults_to_zero_for_unknown_model():
    # generate() must return cost_usd=0.0 for unrecognised model IDs rather than crash.
    import llm.claude as claude_mod

    provider = ClaudeProvider("claude-99-mystery")
    claude_mod._client = MagicMock()
    claude_mod._client.messages.create.return_value = _make_response(
        "x", in_tok=100, out_tok=50
    )
    _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert usage.cost_usd == 0.0


# ---------------------------------------------------------------------------
# cost table coverage
# ---------------------------------------------------------------------------


def test_cost_table_includes_new_sonnet_5_and_opus_5():
    # _COST_PER_M must include the newer Sonnet 5 / Opus 5 models so telemetry
    # doesn't silently report $0.00 if providers.yaml is pointed at them. Sonnet 5's
    # introductory $2/$10 became the standard price (Anthropic's pricing page,
    # 2026-10-04): the planned increase to $3/$15 will not occur.
    assert _COST_PER_M["claude-sonnet-5"] == (2.00, 10.00)
    assert _COST_PER_M["claude-opus-5"] == (5.00, 25.00)


def test_cost_table_opus_4_7_and_4_8_match_current_pricing():
    # Regression guard: Opus 4.7/4.8 must not silently revert to the stale
    # ($15.00, $75.00) rate that predates the repricing this spec fixes.
    assert _COST_PER_M["claude-opus-4-7"] == (5.00, 25.00)
    assert _COST_PER_M["claude-opus-4-8"] == (5.00, 25.00)


def test_cost_table_haiku_4_5_matches_current_pricing():
    # Regression guard: Haiku 4.5 must not silently revert to the stale Haiku 3.5 rate.
    assert _COST_PER_M["claude-haiku-4-5-20251001"] == (1.00, 5.00)


# ---------------------------------------------------------------------------
# price table — every non-retired, generally available model (Spec 054)
# ---------------------------------------------------------------------------


def test_cost_table_matches_published_rates_on_2026_10_04():
    # Every non-retired Claude model on Anthropic's pricing page must have its
    # published rate here (data-model: "value equals the provider's published rate
    # on the verification date"); an unpriced model silently reports $0.00.
    expected = {
        "claude-sonnet-5-5": (2.00, 10.00),
        "claude-opus-5-5": (4.00, 20.00),
        "claude-opus-4-6": (5.00, 25.00),
        "claude-opus-4-5-20251101": (5.00, 25.00),
        "claude-opus-4-5": (5.00, 25.00),
        "claude-sonnet-4-5-20250929": (3.00, 15.00),
        "claude-fable-5-1": (10.00, 50.00),
        "claude-fable-5": (10.00, 50.00),
        "claude-sonnet-5": (2.00, 10.00),
        "claude-sonnet-4-6": (3.00, 15.00),
        "claude-sonnet-4-5": (3.00, 15.00),
        "claude-opus-5": (5.00, 25.00),
        "claude-opus-4-8": (5.00, 25.00),
        "claude-opus-4-7": (5.00, 25.00),
        "claude-haiku-4-5-20251001": (1.00, 5.00),
    }
    for model, rate in expected.items():
        assert _COST_PER_M.get(model) == rate, model


def test_cost_table_has_no_invitation_only_mythos_models():
    # Mythos models are invitation-only (not generally available), so they are
    # deliberately not priced in the table.
    assert not [m for m in _COST_PER_M if "mythos" in m]


def test_generate_computes_correct_cost_for_sonnet_5_5():
    # claude-sonnet-5-5 is the new default creative model: generate() must price it
    # at its published $2.00/$10.00 per MTok instead of silently reporting $0.00.
    provider = ClaudeProvider("claude-sonnet-5-5")
    claude_mod._client = MagicMock()
    claude_mod._client.messages.create.return_value = _make_response(
        "x", in_tok=1_000_000, out_tok=1_000_000
    )
    _, usage = provider.generate("s", [{"role": "user", "content": "q"}])
    assert abs(usage.cost_usd - 12.00) < 0.001  # $2 input + $10 output


# ---------------------------------------------------------------------------
# content blocks and effort (spec 054 amendment A)
# ---------------------------------------------------------------------------


def _typed_block(block_type: str, text: str = "") -> MagicMock:
    # A response content block like the SDK's: a thinking block has no .text.
    block = MagicMock(spec=["type"] if block_type == "thinking" else ["type", "text"])
    block.type = block_type
    if block_type != "thinking":
        block.text = text
    return block


def _response_with(blocks, stop_reason="end_turn", out_tok=5) -> MagicMock:
    resp = _make_response("unused", out_tok=out_tok)
    resp.content = blocks
    resp.stop_reason = stop_reason
    return resp


def _generate_with(provider, response):
    claude_mod._client = MagicMock()
    claude_mod._client.messages.create.return_value = response
    return provider.generate("s", [{"role": "user", "content": "q"}])


def test_generate_skips_a_leading_thinking_block():
    # Claude 5.5 models may start a reply with a thinking block; the answer text
    # must still be returned instead of crashing on the missing .text.
    response = _response_with(
        [_typed_block("thinking"), _typed_block("text", "ANSWER")]
    )
    text, _ = _generate_with(ClaudeProvider("claude-sonnet-5-5"), response)
    assert text == "ANSWER"


def test_generate_joins_several_text_blocks_in_order():
    # A reply split into several text blocks must come back as one string, in order.
    response = _response_with([_typed_block("text", "A"), _typed_block("text", "B")])
    text, _ = _generate_with(ClaudeProvider("claude-sonnet-5-5"), response)
    assert text == "AB"


def test_generate_without_any_text_block_raises_a_clear_error():
    # A reply with no text block (for example thinking that ran out of tokens) must
    # raise an error naming the model and stop reason so the fallback chain moves on.
    response = _response_with([_typed_block("thinking")], stop_reason="max_tokens")
    with pytest.raises(RuntimeError) as exc:
        _generate_with(ClaudeProvider("claude-sonnet-5-5"), response)
    assert "claude-sonnet-5-5" in str(exc.value)
    assert "max_tokens" in str(exc.value)


def test_generate_warns_when_the_reply_hit_max_tokens(caplog):
    # A reply cut off at max_tokens must be visible in the log, because thinking
    # tokens share the budget and a truncated answer would otherwise look normal.
    response = _response_with(
        [_typed_block("text", "cut off")], stop_reason="max_tokens"
    )
    with caplog.at_level("WARNING", logger="llm.claude"):
        text, _ = _generate_with(ClaudeProvider("claude-sonnet-5-5"), response)
    assert text == "cut off"
    assert "max_tokens" in caplog.text


def test_generate_passes_low_effort_for_models_that_support_it():
    # A provider created with effort="low" must send output_config.effort=low on
    # Sonnet 5.5, which is how the panelists keep thinking short and cheap.
    provider = ClaudeProvider("claude-sonnet-5-5", effort="low")
    _generate_with(provider, _make_response("x"))
    kwargs = claude_mod._client.messages.create.call_args.kwargs
    assert kwargs["extra_body"] == {"output_config": {"effort": "low"}}
    assert provider.effort == "low"


def test_generate_sends_no_effort_by_default():
    # Without an effort setting the request must be exactly what it was before.
    _generate_with(ClaudeProvider("claude-sonnet-5-5"), _make_response("x"))
    assert "extra_body" not in claude_mod._client.messages.create.call_args.kwargs


def test_effort_is_ignored_for_models_that_do_not_support_it():
    # Haiku 4.5 does not support the effort parameter, so asking for it must not add
    # the field (the API would reject the request).
    provider = ClaudeProvider("claude-haiku-4-5-20251001", effort="low")
    _generate_with(provider, _make_response("x"))
    assert "extra_body" not in claude_mod._client.messages.create.call_args.kwargs
    assert provider.effort is None
