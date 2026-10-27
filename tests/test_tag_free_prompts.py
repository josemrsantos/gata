from agents import agent_cultural_strategist as cs
from agents import agent_engagement_image as ei
from agents import agent_explainer as ex
from agents import agent_linkedin_post as li
from llm.reply_parsing import unwrap_reply

_CS_BODY = (
    "CULTURAL ANGLE: Pager rota as folklore\n"
    "REFERENCES:\n- Friday deploys\n- Stack Overflow\n"
    "JOKE TYPE: irony"
)
_LI_SECTIONS = (
    "===TITLE===\nA title\n===EXECUTIVE_SUMMARY===\nSummary\n"
    "===BODY===\nBody [1]\n===COMMENT===\nWhat do you think?\n"
    "===NOTIFICATION===\nA teaser that is long enough."
)


def test_cultural_strategist_prompts_have_no_verdict_tags_tag_free():
    # Spec 058 FR-001: neither the Framer nor the Resonator prompt may ask for tags.
    assert "<verdict>" not in cs._build_framer_system_prompt(None)
    assert "<verdict>" not in cs._CS_AGGREGATOR_SYSTEM


def test_cultural_strategist_aggregator_asks_for_pick_then_fields_tag_free():
    # Spec 058 FR-002: the Resonator must be told to write PICK: N then the fields.
    assert "PICK: N" in cs._CS_AGGREGATOR_SYSTEM
    assert "CULTURAL ANGLE:" in cs._CS_AGGREGATOR_SYSTEM


def test_cultural_strategist_parse_is_the_same_tagged_or_untagged_tag_free():
    # Spec 058 FR-010: an untagged reply must parse to exactly what a tagged one does.
    tagged = unwrap_reply(f"<verdict>\n{_CS_BODY}\n</verdict>")
    untagged = unwrap_reply(_CS_BODY)
    assert cs._parse_verdict(untagged) == cs._parse_verdict(tagged)
    assert cs._parse_verdict(untagged)[2] == "irony"


def test_explainer_prompts_have_no_verdict_tags_tag_free():
    # Spec 058 FR-001: neither the HTML writer nor the Editor may be asked for tags.
    assert "<verdict>" not in ex._WRITER_SYSTEM
    assert "<verdict>" not in ex._EXPLAINER_AGGREGATOR_SYSTEM


def test_explainer_html_in_a_code_fence_loses_only_the_fence_tag_free():
    # Spec 058 FR-010: HTML returned in a fence must reach the caller unchanged inside.
    html = "<!DOCTYPE html>\n<html><body><p>x</p></body></html>"
    assert unwrap_reply(f"```html\n{html}\n```") == html
    assert unwrap_reply(html) == html


def test_engagement_image_prompts_have_no_verdict_tags_tag_free():
    # Spec 058 FR-001: neither the panelist nor the Art Director may be asked for tags.
    assert "<verdict>" not in ei._PANELIST_SYSTEM
    assert "<verdict>" not in ei._AGGREGATOR_SYSTEM


def test_engagement_image_aggregator_asks_for_pick_tag_free():
    # Spec 058 FR-002: the Art Director must still be told to write a PICK: N line.
    assert "PICK: N" in ei._AGGREGATOR_SYSTEM


def test_linkedin_angle_and_writing_prompts_have_no_verdict_tags_tag_free():
    # Spec 058 FR-001: planning and writing prompts must not mention verdict tags.
    for prompt in (
        li._PLANNER_SYSTEM,
        li._PLANNER_AGGREGATOR_SYSTEM,
        li._WRITER_SYSTEM,
        li._WRITER_AGGREGATOR_SYSTEM,
    ):
        assert "<verdict>" not in prompt


def test_linkedin_prompts_keep_their_section_formats_tag_free():
    # Spec 058: dropping the tags must not drop the ANGLE:/FOCUS: or ===MARKER=== text.
    assert "ANGLE:" in li._PLANNER_SYSTEM and "FOCUS:" in li._PLANNER_SYSTEM
    assert "===TITLE===" in li._WRITER_SYSTEM
    assert "===NOTIFICATION===" in li._WRITER_AGGREGATOR_SYSTEM


def test_linkedin_sections_parse_the_same_tagged_or_untagged_tag_free():
    # Spec 058 FR-010: the article sections must parse identically with or without tags.
    tagged = unwrap_reply(f"<verdict>\n{_LI_SECTIONS}\n</verdict>")
    untagged = unwrap_reply(_LI_SECTIONS)
    assert li._parse_sections(untagged) == li._parse_sections(tagged)
    assert li._parse_sections(untagged)["TITLE"] == "A title"
