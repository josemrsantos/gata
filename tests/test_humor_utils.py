from core.humor_utils import inconvenience_directive


def test_inconvenience_directive_zero_returns_empty():
    # At level 0 no directive is injected so the prompt is unchanged.
    assert inconvenience_directive(0) == ""


def test_inconvenience_directive_negative_returns_empty():
    # Negative values are treated as 0 — no directive injected.
    assert inconvenience_directive(-10) == ""


def test_inconvenience_directive_low_level_is_gentle():
    # Levels 1–33 produce a mild nudge, not a hard demand.
    result = inconvenience_directive(20)
    assert result != ""
    assert "INCONVENIENCE" in result
    assert "uncomfortable" in result.lower()


def test_inconvenience_directive_medium_level_escalates():
    # Levels 34–66 push harder — "don't let them off the hook".
    result = inconvenience_directive(50)
    assert "INCONVENIENCE" in result
    assert "hide" in result.lower() or "hook" in result.lower()


def test_inconvenience_directive_high_level_is_maximum():
    # Levels 67–100 force maximum discomfort — the audience must squirm.
    result = inconvenience_directive(100)
    assert "INCONVENIENCE" in result
    assert "squirm" in result.lower()


def test_inconvenience_directive_boundary_33_is_low():
    # Exactly 33 is still the low tier — boundary must not bleed into medium.
    result = inconvenience_directive(33)
    assert "squirm" not in result.lower()
    assert "hide" not in result.lower()


def test_inconvenience_directive_boundary_34_is_medium():
    # 34 crosses into medium tier.
    result = inconvenience_directive(34)
    assert "hide" in result.lower() or "hook" in result.lower()


def test_inconvenience_directive_boundary_67_is_high():
    # 67 crosses into maximum tier.
    result = inconvenience_directive(67)
    assert "squirm" in result.lower()
