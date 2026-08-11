from unittest.mock import MagicMock

import pytest

from llm.claude import _COST_PER_M, ClaudeProvider

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_response(text: str, in_tok: int = 10, out_tok: int = 5) -> MagicMock:
    """Build a mock anthropic Message response."""
    block = MagicMock()
    block.text = text
    usage = MagicMock()
    usage.input_tokens = in_tok
    usage.output_tokens = out_tok
    resp = MagicMock()
    resp.content = [block]
    resp.usage = usage
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
    # doesn't silently report $0.00 if providers.yaml is pointed at them.
    assert _COST_PER_M["claude-sonnet-5"] == (3.00, 15.00)
    assert _COST_PER_M["claude-opus-5"] == (5.00, 25.00)


def test_cost_table_opus_4_7_and_4_8_match_current_pricing():
    # Regression guard: Opus 4.7/4.8 must not silently revert to the stale
    # ($15.00, $75.00) rate that predates the repricing this spec fixes.
    assert _COST_PER_M["claude-opus-4-7"] == (5.00, 25.00)
    assert _COST_PER_M["claude-opus-4-8"] == (5.00, 25.00)


def test_cost_table_haiku_4_5_matches_current_pricing():
    # Regression guard: Haiku 4.5 must not silently revert to the stale Haiku 3.5 rate.
    assert _COST_PER_M["claude-haiku-4-5-20251001"] == (1.00, 5.00)
