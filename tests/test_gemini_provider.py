from unittest.mock import MagicMock, patch

from llm.gemini import _COST_PER_M, GeminiProvider, compute_cost

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_response(text: str, in_tok: int = 10, out_tok: int = 5) -> MagicMock:
    """Build a mock genai GenerateContentResponse."""
    resp = MagicMock()
    resp.text = text
    meta = MagicMock()
    meta.prompt_token_count = in_tok
    meta.candidates_token_count = out_tok
    resp.usage_metadata = meta
    return resp


# ---------------------------------------------------------------------------
# model_id
# ---------------------------------------------------------------------------


def test_model_id_returns_constructor_argument():
    # GeminiProvider.model_id must return exactly the constructor's model string.
    provider = GeminiProvider("gemini-2.5-flash")
    assert provider.model_id == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# generate() — happy path
# ---------------------------------------------------------------------------


def test_generate_returns_text_and_token_usage():
    # generate() must return the response text and a populated TokenUsage on success.
    provider = GeminiProvider("gemini-2.5-flash")
    fake_resp = _make_response("Gata proposes a spider diagram.", in_tok=20, out_tok=8)
    with patch("llm.gemini._get_client") as mock_client_fn:
        mock_client_fn.return_value.models.generate_content.return_value = fake_resp
        text, usage = provider.generate("system", [{"role": "user", "content": "go"}])
    assert text == "Gata proposes a spider diagram."
    assert usage.model == "gemini-2.5-flash"
    assert usage.input_tokens == 20
    assert usage.output_tokens == 8


def test_generate_raises_runtime_error_on_empty_text():
    # generate() must raise RuntimeError when the response text is empty/None (all
    # thinking tokens), so the fallback chain tries the next provider.
    provider = GeminiProvider("gemini-2.5-flash")
    fake_resp = _make_response(None)
    with patch("llm.gemini._get_client") as mock_client_fn:
        mock_client_fn.return_value.models.generate_content.return_value = fake_resp
        try:
            provider.generate("sys", [{"role": "user", "content": "q"}])
            raise AssertionError("expected RuntimeError")
        except RuntimeError as exc:
            assert "empty response text" in str(exc)


# ---------------------------------------------------------------------------
# cost calculation
# ---------------------------------------------------------------------------


def test_compute_cost_for_gemini_2_5_flash():
    # compute_cost() must use gemini-2.5-flash's current rate ($0.30/$2.50/MTok).
    cost = compute_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
    assert abs(cost - 2.80) < 0.001  # $0.30 input + $2.50 output


def test_compute_cost_defaults_to_zero_for_unknown_model():
    # compute_cost() must return 0.0 for unrecognised model IDs rather than crash.
    assert compute_cost("gemini-99-mystery", 100, 50) == 0.0


# ---------------------------------------------------------------------------
# cost table coverage / currency
# ---------------------------------------------------------------------------


def test_cost_table_flash_lite_matches_current_pricing():
    # Regression guard: gemini-3.1-flash-lite must not silently revert to the stale
    # (0.10, 0.40) launch-promo rate this spec corrects to the real (0.25, 1.50) rate.
    assert _COST_PER_M["gemini-3.1-flash-lite"] == (0.25, 1.50)


def test_cost_table_pro_preview_matches_current_pricing():
    # Regression guard: gemini-3.1-pro-preview must not silently revert to the stale
    # rate copied from gemini-2.5-pro; it has its own, higher tiered rate.
    assert _COST_PER_M["gemini-3.1-pro-preview"] == (2.00, 12.00)


def test_cost_table_excludes_dead_gemini_2_0_flash():
    # gemini-2.0-flash was shut down by Google on 2026-06-01 (confirmed via official
    # deprecation docs) — it must not remain in the cost table as if still billable.
    assert "gemini-2.0-flash" not in _COST_PER_M
