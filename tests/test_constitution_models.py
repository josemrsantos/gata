"""The constitution's §1 must name the same models the code defaults to (Spec 054)."""

import re
from pathlib import Path

_CONSTITUTION = (
    Path(__file__).resolve().parent.parent / ".specify/memory/constitution.md"
)

# Current defaults named in §1 (Gemini Flash stays 2.5: it still works, Spec 054).
_CURRENT_DEFAULTS = {
    "claude-sonnet-5-5",
    "gemini-3.1-flash-image",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "grok-4.3",
}


def _section_1() -> str:
    text = _CONSTITUTION.read_text()
    start = text.index("### §1")
    return text[start : text.index("### §2", start)]


def test_section_1_names_only_current_default_models():
    # A stale model name in §1 would make every later plan's Constitution Check
    # wrong, so §1 may only name models that are current defaults.
    named = set(re.findall(r"`((?:claude|gemini|grok)-[\w.\-]+)`", _section_1()))
    assert named, "§1 should name at least one model"
    assert named <= _CURRENT_DEFAULTS, sorted(named - _CURRENT_DEFAULTS)
    assert "claude-sonnet-5-5" in named
    assert "gemini-3.1-flash-image" in named


def test_section_1_points_at_the_real_image_chain_location():
    # §1 must point at core/image_generation.py, where the image fallback chain
    # actually lives, not at the agent module it used to be defined in.
    section = _section_1()
    assert "core/image_generation.py" in section
    assert "agents/agent_image_generator.py" not in section


def test_constitution_version_and_amendment_record_are_1_3():
    # An amendment is only valid with a version bump and an amendment-record row,
    # per the constitution's own Amendment Procedure.
    text = _CONSTITUTION.read_text()
    assert "**Version**: 1.3" in text
    assert "- v1.3 (" in text
    assert re.search(r"^\| 1\.3 \|.*Spec 054", text, re.M)
