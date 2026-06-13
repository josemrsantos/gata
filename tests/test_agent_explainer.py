from unittest.mock import patch

import pytest

from agents.types import ConversationLog, EnrichedBrief, LoopOutput


def _make_brief(language: str = "Portuguese") -> EnrichedBrief:
    return EnrichedBrief(
        target_audience="Portuguese adults",
        output_language=language,
        tone="sharp satire",
        cultural_angle="Housing crisis as cat territorial dispute.",
        culturally_loaded_references=["Rent control protests", "Airbnb backlash"],
    )


def _make_log(loop_name: str) -> ConversationLog:
    return ConversationLog(loop_name=loop_name)


_IN_LANG_HTML = (
    '<!DOCTYPE html><html lang="pt">'
    '<head><meta charset="UTF-8"></head>'
    "<body>Explicação</body></html>"
)
_EN_HTML = (
    '<!DOCTYPE html><html lang="en">'
    '<head><meta charset="UTF-8"></head>'
    "<body>Explanation</body></html>"
)


# -- T016: generate_html return type and structure (in-language HTML) --


def test_generate_html_returns_tuple():
    # generate_html() must return a 2-tuple so callers can unpack in-language and
    # English HTML without index lookups.
    from agents.agent_explainer import generate_html

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.return_value = LoopOutput(
            verdict=_IN_LANG_HTML, log=ConversationLog(loop_name="explainer-lang")
        )
        result = generate_html(
            _make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt"
        )
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_generate_html_first_element_is_in_language_html():
    # The first tuple element must be the in-language HTML string — callers write it
    # to explanation.html without any transformation.
    from agents.agent_explainer import generate_html

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.side_effect = [
            LoopOutput(verdict=_IN_LANG_HTML, log=ConversationLog(loop_name="lang")),
            LoopOutput(verdict=_EN_HTML, log=ConversationLog(loop_name="en")),
        ]
        in_lang, _ = generate_html(
            _make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt"
        )
    assert in_lang == _IN_LANG_HTML


def test_generate_html_second_element_is_english_html():
    # The second tuple element must be the English HTML string — callers write it
    # to deep_dive_en.html without any transformation.
    from agents.agent_explainer import generate_html

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.side_effect = [
            LoopOutput(verdict=_IN_LANG_HTML, log=ConversationLog(loop_name="lang")),
            LoopOutput(verdict=_EN_HTML, log=ConversationLog(loop_name="en")),
        ]
        _, english = generate_html(
            _make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt"
        )
    assert english == _EN_HTML


def test_generate_html_calls_dual_loop_twice():
    # generate_html() must run two separate DualPersonaLoop iterations — one for
    # in-language HTML and one for English — so each gets its own editorial review.
    from agents.agent_explainer import generate_html

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.side_effect = [
            LoopOutput(verdict=_IN_LANG_HTML, log=ConversationLog(loop_name="lang")),
            LoopOutput(verdict=_EN_HTML, log=ConversationLog(loop_name="en")),
        ]
        generate_html(_make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt")
    assert mock_instance.run.call_count == 2


def test_generate_html_in_lang_contains_doctype():
    # in-language HTML must begin with <!DOCTYPE html> so browsers render it as
    # a proper HTML5 document rather than triggering quirks mode.
    from agents.agent_explainer import generate_html

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.side_effect = [
            LoopOutput(verdict=_IN_LANG_HTML, log=ConversationLog(loop_name="lang")),
            LoopOutput(verdict=_EN_HTML, log=ConversationLog(loop_name="en")),
        ]
        in_lang, _ = generate_html(
            _make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt"
        )
    assert "<!DOCTYPE html>" in in_lang


def test_generate_html_in_lang_contains_utf8_charset():
    # The in-language HTML must declare UTF-8 charset (FR-012) so non-Latin scripts
    # render correctly in any browser without manual encoding configuration.
    from agents.agent_explainer import generate_html

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.side_effect = [
            LoopOutput(verdict=_IN_LANG_HTML, log=ConversationLog(loop_name="lang")),
            LoopOutput(verdict=_EN_HTML, log=ConversationLog(loop_name="en")),
        ]
        in_lang, _ = generate_html(
            _make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt"
        )
    assert 'charset="UTF-8"' in in_lang or "charset='UTF-8'" in in_lang.lower()


def test_generate_html_raises_when_all_models_exhausted():
    # RuntimeError from DualPersonaLoop (all models exhausted) must propagate so
    # bundle_writer can catch it and log the failure per FR-011.
    from agents.agent_explainer import generate_html

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.side_effect = RuntimeError("all models exhausted")
        with pytest.raises(RuntimeError):
            generate_html(
                _make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt"
            )


# -- T020: English deep-dive HTML specifics --


def test_generate_html_english_contains_doctype():
    # English deep-dive HTML must begin with <!DOCTYPE html> for the same reason as
    # in-language HTML — consistent document structure for operator tooling.
    from agents.agent_explainer import generate_html

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.side_effect = [
            LoopOutput(verdict=_IN_LANG_HTML, log=ConversationLog(loop_name="lang")),
            LoopOutput(verdict=_EN_HTML, log=ConversationLog(loop_name="en")),
        ]
        _, english = generate_html(
            _make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt"
        )
    assert "<!DOCTYPE html>" in english


def test_generate_html_english_contains_utf8_charset():
    # English deep-dive must also declare UTF-8 charset so it renders consistently
    # regardless of the operator's browser locale settings.
    from agents.agent_explainer import generate_html

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.side_effect = [
            LoopOutput(verdict=_IN_LANG_HTML, log=ConversationLog(loop_name="lang")),
            LoopOutput(verdict=_EN_HTML, log=ConversationLog(loop_name="en")),
        ]
        _, english = generate_html(
            _make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt"
        )
    assert 'charset="UTF-8"' in english or "charset='utf-8'" in english.lower()


def test_generate_html_english_lang_attribute_is_en():
    # The English HTML must have lang="en" on the <html> tag so screen readers and
    # other assistive tools apply English language rules.
    from agents.agent_explainer import generate_html

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.side_effect = [
            LoopOutput(verdict=_IN_LANG_HTML, log=ConversationLog(loop_name="lang")),
            LoopOutput(verdict=_EN_HTML, log=ConversationLog(loop_name="en")),
        ]
        _, english = generate_html(
            _make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt"
        )
    assert 'lang="en"' in english


def test_generate_html_uses_distinct_prompts_for_each_call():
    # generate_html() must pass different initial_input strings to the two loop runs
    # so each DualPersonaLoop receives a prompt appropriate for its task (in-language
    # vs English).
    from agents.agent_explainer import generate_html

    captured_inputs: list[str] = []

    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value

        def capture_and_return(initial_input: str) -> LoopOutput:
            captured_inputs.append(initial_input)
            if len(captured_inputs) == 1:
                return LoopOutput(
                    verdict=_IN_LANG_HTML, log=ConversationLog(loop_name="lang")
                )
            return LoopOutput(verdict=_EN_HTML, log=ConversationLog(loop_name="en"))

        mock_instance.run.side_effect = capture_and_return
        generate_html(_make_brief(), _make_log("Agent 0"), _make_log("B/C"), "prompt")

    assert len(captured_inputs) == 2
    assert captured_inputs[0] != captured_inputs[1]


# -- T026: UTF-8 charset always present regardless of target language --


def test_generate_html_utf8_present_for_non_latin_language():
    # UTF-8 charset must be declared even for non-Latin scripts (Korean, Arabic, etc.)
    # so the HTML file renders correctly on any system (FR-012).
    from agents.agent_explainer import generate_html

    korean_html = (
        '<!DOCTYPE html><html lang="ko">'
        '<head><meta charset="UTF-8"></head>'
        "<body>설명</body></html>"
    )
    with patch("agents.agent_explainer.DualPersonaLoop") as MockLoop:
        mock_instance = MockLoop.return_value
        mock_instance.run.side_effect = [
            LoopOutput(verdict=korean_html, log=ConversationLog(loop_name="lang")),
            LoopOutput(verdict=_EN_HTML, log=ConversationLog(loop_name="en")),
        ]
        in_lang, _ = generate_html(
            _make_brief("Korean"), _make_log("Agent 0"), _make_log("B/C"), "prompt"
        )
    assert 'charset="UTF-8"' in in_lang or "charset='utf-8'" in in_lang.lower()
