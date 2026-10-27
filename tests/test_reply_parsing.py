import logging

import pytest

from llm.reply_parsing import (
    ParseContext,
    log_parse_issue,
    parse_labelled,
    split_pick,
    unwrap_reply,
)

# Shapes reconstructed from the 2026-10-27 run.log evidence in TODO.md (the raw log
# is not kept in the repo): an unclosed <verdict> and a bare fenced Satirist JSON.
UNCLOSED_REPLY = "Here you go.\n<verdict>\nCULTURAL ANGLE: The pager rota as folklore"
BARE_FENCED_JSON = (
    '```json\n{"panels": 3, "layout": "vertical", "title": "Pager Duty",'
    ' "content": [{"scene": "s", "caption": "c", "beat": "b"}]}\n```'
)


def _ctx(**overrides):
    base = {
        "agent": "Satirist/Co-Satirist",
        "role": "gemini-2.5-flash",
        "round": 2,
        "model": "gemini-2.5-flash",
    }
    base.update(overrides)
    return ParseContext(**base)


# -- unwrap_reply --


def test_unwrap_closed_tag_returns_content():
    # A legacy closed <verdict> wrapper must still be unwrapped (old replies work).
    assert unwrap_reply("Intro <verdict>the answer</verdict> outro") == "the answer"


def test_unwrap_unclosed_tag_recovers_content_and_warns(caplog):
    # The 2026-10-27 unclosed-tag reply must be used, not dropped, with a WARNING.
    with caplog.at_level(logging.WARNING):
        result = unwrap_reply(UNCLOSED_REPLY, _ctx())
    assert result == "CULTURAL ANGLE: The pager rota as folklore"
    assert any("verdict" in r.getMessage() for r in caplog.records)


def test_unwrap_bare_fenced_json_returns_json_and_warns(caplog):
    # The 2026-10-27 bare fenced JSON reply must be accepted as a legacy shape.
    with caplog.at_level(logging.WARNING):
        result = unwrap_reply(BARE_FENCED_JSON, _ctx())
    assert result.startswith('{"panels": 3')
    assert not result.startswith("```")
    assert any("JSON" in r.getMessage() for r in caplog.records)


def test_unwrap_plain_text_is_the_whole_reply(caplog):
    # A tag-free reply is the answer itself and must not log any warning.
    with caplog.at_level(logging.WARNING):
        result = unwrap_reply("  Just the concept, no wrapper.\n")
    assert result == "Just the concept, no wrapper."
    assert caplog.records == []


def test_unwrap_removes_one_surrounding_code_fence():
    # Models wrap HTML or text in a fence; the fence is formatting, not content.
    assert unwrap_reply("```html\n<p>hi</p>\n```") == "<p>hi</p>"


def test_unwrap_empty_reply_raises():
    # An empty or whitespace-only reply carries no work, so it is unusable.
    with pytest.raises(ValueError):
        unwrap_reply("   \n ")


def test_unwrap_verdict_wrapper_around_labelled_lines():
    # A wrapper around labelled lines is unwrapped first so labels can be parsed.
    text = "<verdict>PANELS: 2\nLAYOUT: vertical</verdict>"
    assert unwrap_reply(text) == "PANELS: 2\nLAYOUT: vertical"


# -- split_pick --


@pytest.mark.parametrize(
    "line",
    ["PICK: 2", "**PICK: 2**", "- PICK: 2", "pick:2", "PICK: **2**"],
)
def test_split_pick_accepts_drifted_pick_lines(line):
    # The aggregator's PICK line must be found despite bold, bullets or case drift.
    number, rest = split_pick(f"{line}\nthe chosen answer")
    assert number == 2
    assert rest == "the chosen answer"


def test_split_pick_missing_line_returns_none_and_whole_reply():
    # With no PICK line the pick is unknown and the whole reply remains the verdict.
    assert split_pick("just an answer") == (None, "just an answer")


def test_split_pick_keeps_text_when_pick_has_trailing_words():
    # A PICK with trailing prose still yields the number but must not delete the prose.
    number, rest = split_pick("PICK: 3 because it is sharpest\nanswer")
    assert number == 3
    assert "because it is sharpest" in rest


# -- parse_labelled --

SATIRIST_LABELS = ["PANELS", "LAYOUT", "TITLE", "PANEL", "SCENE", "CAPTION", "BEAT"]
CANONICAL = (
    "PANELS: 2\nLAYOUT: vertical\nTITLE: Pager Duty\n"
    "PANEL 1\nSCENE: Gata at a desk\nCAPTION: Quiet night\nBEAT: setup\n"
    "PANEL 2\nSCENE: The pager rings\nCAPTION: Not quiet\nBEAT: punchline\n"
)


def test_parse_labelled_canonical_reply():
    # The canonical labelled reply must split into ordered label/value pairs.
    pairs = parse_labelled(CANONICAL, SATIRIST_LABELS)
    assert [p[0] for p in pairs] == [
        "PANELS",
        "LAYOUT",
        "TITLE",
        "PANEL",
        "SCENE",
        "CAPTION",
        "BEAT",
        "PANEL",
        "SCENE",
        "CAPTION",
        "BEAT",
    ]
    assert dict(pairs[:3]) == {
        "PANELS": "2",
        "LAYOUT": "vertical",
        "TITLE": "Pager Duty",
    }


@pytest.mark.parametrize(
    "drifted",
    [
        CANONICAL.replace("SCENE:", "Scene 1:"),
        CANONICAL.replace("CAPTION:", "**CAPTION**:"),
        CANONICAL.replace("PANEL 1", "## Panel 1").replace("PANEL 2", "## Panel 2"),
        f"```\n{CANONICAL}```",
        CANONICAL.replace("SCENE:", "scene:"),
    ],
)
def test_parse_labelled_tolerates_label_drift(drifted):
    # Label drift, emphasis, headings and a fence must parse like the canonical form.
    assert parse_labelled(drifted, SATIRIST_LABELS) == parse_labelled(
        CANONICAL, SATIRIST_LABELS
    )


def test_parse_labelled_multiline_value_runs_to_next_label():
    # A value spanning several lines must keep running until the next known label.
    pairs = parse_labelled("SCENE: line one\nline two\nCAPTION: c", SATIRIST_LABELS)
    assert pairs == [("SCENE", "line one\nline two"), ("CAPTION", "c")]


def test_parse_labelled_ignores_prose_that_starts_with_a_label_word():
    # A sentence beginning "Scene of..." is value text, not a label line.
    pairs = parse_labelled(
        "SCENE: a\nScene of the crime is dark\nBEAT: b", SATIRIST_LABELS
    )
    assert pairs[0] == ("SCENE", "a\nScene of the crime is dark")


def test_parse_labelled_ignores_preamble_before_first_label():
    # Chatty text before the first label is not part of any field.
    pairs = parse_labelled("Sure, here it is:\nTITLE: T", SATIRIST_LABELS)
    assert pairs == [("TITLE", "T")]


# -- log_parse_issue --


def test_log_parse_issue_names_every_required_field(caplog):
    # A parse-failure WARNING must carry agent, role, round, model, field, default.
    with caplog.at_level(logging.WARNING):
        log_parse_issue(
            _ctx(stop_reason="max_tokens", output_tokens=900, max_tokens=900),
            "BEAT",
            "retry once",
            "x" * 1000,
        )
    message = caplog.records[0].getMessage()
    assert caplog.records[0].levelno == logging.WARNING
    for expected in [
        "Satirist/Co-Satirist",
        "gemini-2.5-flash",
        "round 2",
        "BEAT",
        "retry once",
        "stop_reason=max_tokens",
        "900/900",
    ]:
        assert expected in message


def test_log_parse_issue_excerpt_is_exactly_400_characters(caplog):
    # The log excerpt must be the first 400 characters of the reply, never more.
    with caplog.at_level(logging.WARNING):
        log_parse_issue(_ctx(), "TITLE", "topic used", "a" * 400 + "b" * 50)
    message = caplog.records[0].getMessage()
    assert "a" * 400 in message
    assert "b" not in message.split("reply starts:")[1]


def test_log_parse_issue_omits_unknown_stop_reason(caplog):
    # With no stop reason from the provider the line is still written without it.
    with caplog.at_level(logging.WARNING):
        log_parse_issue(_ctx(), "TITLE", "topic used", "reply")
    assert "stop_reason" not in caplog.records[0].getMessage()
