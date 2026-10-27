"""The constitution states model *policy*, not model names (constitution v1.4)."""

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_CONSTITUTION = _REPO / ".specify/memory/constitution.md"
_MODEL_ID = re.compile(
    r"\b(?:claude-(?:sonnet|opus|haiku|fable|mythos)-[\w.\-]+|(?:gemini|grok)-\d[\w.\-]*)"
)


def _section(start: str, end: str) -> str:
    text = _CONSTITUTION.read_text()
    first = text.index(start)
    return text[first : text.index(end, first)]


def test_section_1_names_no_specific_model():
    # §1 states rules, not model names, so a routine provider release can never
    # make the constitution stale or force an amendment.
    assert not _MODEL_ID.findall(_section("### §1", "### §2"))


def test_section_6_names_no_specific_model():
    # §6 describes the Grok aggregator and panelist by role for the same reason.
    assert not _MODEL_ID.findall(_section("### §6", "### §7"))


def test_section_1_points_only_at_files_that_exist():
    # §1 tells readers where the defaults live, so every file it names must exist.
    paths = re.findall(r"`([\w/]+\.(?:py|yaml))`", _section("### §1", "### §2"))
    assert paths, "§1 should point at the code that holds the defaults"
    missing = [p for p in paths if not (_REPO / p).exists()]
    assert not missing, missing


def test_section_1_states_the_default_model_rules():
    # The rules every default must follow are the substance of §1 now: verified
    # current, newest stable same tier, priced, stable image models.
    text = _section("### §1", "### §2")
    for phrase in ("currently serves", "same tier", "priced", "stable models"):
        assert phrase in text, phrase


def test_constitution_version_and_amendment_record_are_1_6():
    # An amendment is only valid with a version bump and an amendment-record row,
    # per the constitution's own Amendment Procedure.
    text = _CONSTITUTION.read_text()
    assert "**Version**: 1.6" in text
    assert "- v1.6 (" in text
    assert re.search(r"^\| 1\.6 \|", text, re.M)


def test_section_3_and_6_no_longer_require_verdict_tags_or_json():
    # Spec 058 (constitution v1.6): the Satirist contract is plain LABEL: value text,
    # so §3 and §6 must not demand <verdict> tags or a JSON schema any more.
    contract = _section("### §3", "### §4") + _section("### §6", "### §7")
    assert "LABEL: value" in contract
    assert "PICK: N" in contract
    assert "```json" not in contract
    assert "re.search(r'<verdict>" not in contract
