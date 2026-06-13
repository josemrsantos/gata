from agents.types import (
    CartoonConcept,
    CartoonLayout,
    CriticHumor,
    FramerHumor,
    PanelConcept,
    SatiristHumor,
)


def test_panel_concept_holds_scene_caption_beat():
    # PanelConcept must store all three fields so the image generator can assemble
    # a complete per-panel description without needing any external context.
    pc = PanelConcept(
        scene="Gata eyes a pie chart", caption="Numbers never lie.", beat="setup"
    )
    assert pc.scene == "Gata eyes a pie chart"
    assert pc.caption == "Numbers never lie."
    assert pc.beat == "setup"


def test_cartoon_layout_defaults_to_single_horizontal():
    # CartoonLayout must default to panels=1 and direction="horizontal" so existing
    # callers that omit the argument get backwards-compatible single-panel behaviour.
    layout = CartoonLayout()
    assert layout.panels == 1
    assert layout.direction == "horizontal"


def test_cartoon_layout_accepts_multi_panel_vertical():
    # CartoonLayout must accept explicit panels and direction for multi-panel runs.
    layout = CartoonLayout(panels=3, direction="vertical")
    assert layout.panels == 3
    assert layout.direction == "vertical"


def test_cartoon_concept_panels_defaults_to_none():
    # CartoonConcept.panels must default to None so all existing single-panel code
    # paths are unaffected without changes to any existing call site.
    concept = CartoonConcept(full_text="text", image_prompt="prompt", iteration=0)
    assert concept.panels is None


def test_cartoon_concept_panels_accepts_list_of_panel_concepts():
    # CartoonConcept.panels must accept a populated list so the satirist's multi-panel
    # output can be carried to the image generator through the same concept object.
    panels = [
        PanelConcept(scene="s1", caption="c1", beat="setup"),
        PanelConcept(scene="s2", caption="c2", beat="punchline"),
    ]
    concept = CartoonConcept(full_text="", image_prompt="", iteration=0, panels=panels)
    assert concept.panels is not None
    assert len(concept.panels) == 2
    assert concept.panels[0].beat == "setup"
    assert concept.panels[1].scene == "s2"


def test_satirist_humor_inconvenience_defaults_to_zero():
    # SatiristHumor.inconvenience must default to 0 so existing configs are unaffected.
    sh = SatiristHumor()
    assert sh.inconvenience == 0


def test_satirist_humor_inconvenience_accepts_value():
    # SatiristHumor.inconvenience must accept a non-zero value for the feature to work.
    sh = SatiristHumor(inconvenience=75)
    assert sh.inconvenience == 75


def test_critic_humor_inconvenience_defaults_to_zero():
    # CriticHumor.inconvenience must default to 0 so existing configs are unaffected.
    ch = CriticHumor()
    assert ch.inconvenience == 0


def test_critic_humor_dual_satirist_defaults_to_false():
    # CriticHumor.dual_satirist must default to False so the Critic role is unchanged
    # unless explicitly opted in via humor.yaml.
    ch = CriticHumor()
    assert ch.dual_satirist is False


def test_critic_humor_dual_satirist_accepts_true():
    # CriticHumor.dual_satirist=True must be storable so the mode can be activated.
    ch = CriticHumor(dual_satirist=True)
    assert ch.dual_satirist is True


def test_framer_humor_inconvenience_defaults_to_zero():
    # FramerHumor.inconvenience must default to 0 so existing configs are unaffected.
    fh = FramerHumor()
    assert fh.inconvenience == 0
