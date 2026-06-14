import json
import logging
import re
from datetime import date

from agents.dual_loop import DualPersonaLoop
from agents.humor_utils import inconvenience_directive
from agents.types import (
    AgentTelemetry,
    CartoonConcept,
    CartoonLayout,
    ConversationLog,
    EnrichedBrief,
    HumorConfig,
    PanelConcept,
    PersonaConfig,
)

logger = logging.getLogger(__name__)

_CLAUDE_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "claude-sonnet-4-5",
    "claude-haiku-4-5-20251001",
]
_GEMINI_CRITIC_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3.1-pro-preview",
]

# Verbatim from constitution.md Section 4
_GATA_CHARACTER = (
    "Gata is a domestic shorthair calico-tabby mix: white chest, muzzle, and paws; "
    "dark grey/black tabby stripes; orange/ginger patches on back. "
    "She has a small dark spot on the bridge of her pink nose. "
    "She wears a simple dark leather collar with a gold/brass nameplate"
    ' engraved "GATA". '
    "Her demeanour is serious, investigative, slightly tired, and highly intelligent. "
    "She never wears human clothes or accessories"
    " — no hats, glasses, pens, or clothing of any kind."
)

# Verbatim from constitution.md Section 5
_VISUAL_STYLE = (
    "Visual style rules:\n"
    "- Colour palette: greyscale background; Gata in full colour"
    " (Selective Color style)\n"
    "- Setting: 1970s newspaper newsroom — fluorescent lights, heavy metal desks, "
    "background figures\n"
    "- The board: dark chalkboard, hand-drawn white sketches, heading always "
    '"ON THE SPOT" (or target-language equivalent)\n'
    "- Attachments on the board use masking tape — never pins\n"
    "- Style descriptor: single-panel satirical cartoon, minimalist "
    "charcoal-on-chalkboard style, high-contrast, dry caption at the bottom\n"
    "- Never reference copyrighted artists or characters"
    " — describe visual characteristics only"
)


def _build_satirist_system_prompt(
    brief: EnrichedBrief,
    humor: HumorConfig | None = None,
    layout: CartoonLayout | None = None,
) -> str:
    today = date.today().strftime("%d %B %Y")
    lines = [
        "You are a satirical cartoon writer for the Gata Newsroom.",
        f"Today's date is {today}."
        " Use this when referencing current events, years, or dates.",
        "",
        "CHARACTER — always include verbatim in every image prompt:",
        _GATA_CHARACTER,
        "",
        _VISUAL_STYLE,
        "",
        "STRATEGY BRIEF:",
        f"- Target audience: {brief.target_audience}",
        f"- Output language: {brief.output_language}"
        " (ALL text in the cartoon must be in this language)",
        f"- Tone: {brief.tone}",
        "",
        "CULTURAL CONTEXT — use this to sharpen the satirical angle:",
        f"- Angle: {brief.cultural_angle}",
        "- Audience references (weave these in where they deepen the satire):",
    ]
    for ref in brief.culturally_loaded_references:
        lines.append(f"  - {ref}")
    if humor:
        lines += [
            "",
            "COMEDY STYLE:",
            f"- Register: {humor.satirist.preferred_style}"
            " — commit to this tone throughout",
            f"- Subversion: {humor.satirist.subversion}"
            " — actively subvert the obvious first read",
        ]
        if humor.satirist.avoid:
            avoid_str = ", ".join(humor.satirist.avoid)
            lines.append(f"- Avoid: {avoid_str}")
        if brief.joke_type:
            lines.append(
                f"- Joke type: {brief.joke_type}"
                " (selected by The Framer for this topic)"
            )
    if layout is not None and layout.panels > 1:
        n = layout.panels
        direction = layout.direction
        lines += [
            "",
            f"TASK: Given a news topic, generate a satirical {n}-panel {direction}"
            " comic strip concept featuring Gata.",
            f"The joke spans all {n} panels as a progressive narrative arc.",
            "Wrap your concept in <verdict>...</verdict> tags.",
            f"Inside <verdict>, return ONLY a valid JSON object with a 'panels'"
            f" key containing an array of exactly {n} panel objects.",
            "Each panel object MUST have three string keys:",
            '  "scene": visual description of what is happening in this panel'
            " (what Gata is doing, what the chalkboard shows, any labels or text)",
            '  "caption": 1-2 sentence caption in the output language',
            '  "beat": narrative position (e.g. "setup", "escalation", "punchline")',
            "ALL caption text MUST be in the specified output language.",
            "Return ONLY the JSON — no preamble, no explanation, no markdown fences.",
        ]
    else:
        lines += [
            "",
            "TASK: Given a news topic, generate a satirical single-panel"
            " cartoon concept featuring Gata.",
            "Wrap the image generation prompt in <verdict>...</verdict> tags.",
            "The image prompt must include Gata's full character description verbatim,"
            " visual style rules,",
            "and all cartoon text in the specified output language.",
        ]
    if humor and humor.satirist.joke_explanation:
        lines += [
            "After the image prompt, add a"
            " <joke_explanation>...</joke_explanation> block:",
            "one sentence explaining why this joke lands for the target audience.",
        ]
    if humor:
        directive = inconvenience_directive(humor.satirist.inconvenience)
        if directive:
            lines += ["", directive]
    return "\n".join(lines)


def _build_critic_system_prompt(
    brief: EnrichedBrief, humor: HumorConfig | None = None
) -> str:
    # Dual satirist mode: replace the adversarial critic with a co-creating partner
    if humor and humor.critic.dual_satirist:
        return _build_second_satirist_prompt(brief, humor)
    lines = [
        "You are a rigorous cartoon quality critic for the Gata Newsroom.",
        "Evaluate the proposed cartoon concept against these rules:",
        "",
        "1. PUNCHING UP: satire must target systems of power or public figures,"
        " not private individuals.",
        "2. VISUAL-FIRST: the image must carry at least 50% of the humour;"
        " caption-only jokes score below threshold.",
        "3. GATA INTEGRITY: Gata must actively expose or challenge the subject"
        " — not be passive or decorative.",
        "4. ORIGINALITY: if the angle is the obvious first-read of the topic,"
        " reject it and propose an alternative with a one-sentence rationale.",
        f"5. AUDIENCE FIT: concept must be immediately accessible"
        f" to {brief.target_audience}.",
        f"6. LANGUAGE COMPLIANCE: ALL text must be in {brief.output_language}.",
    ]
    rule_num = 7
    if humor and humor.critic.evaluate_joke_mechanics and brief.joke_type:
        lines.append(
            f"{rule_num}. JOKE MECHANICS: the selected joke type is"
            f' "{brief.joke_type}"'
            " — verify the concept executes it correctly, not just gestures at it."
        )
        rule_num += 1
    if humor and humor.critic.flag_if_no_subversion:
        lines.append(
            f"{rule_num}. SUBVERSION CHECK: if the satirical angle plays it straight "
            "with no twist or subverted expectation, reject it."
        )
    lines += [
        "",
        "RESPONSE FORMAT:",
        "If the concept is sharp, specific, and genuinely cannot be improved:",
        "<verdict>APPROVED</verdict>",
        "",
        "If any rule is violated or a material improvement exists:",
        "<verdict>NEEDS REVISION</verdict>",
        "followed by: which rule was violated or what is weak,"
        " and one concrete alternative angle or fix.",
        "Each iteration of feedback must differ from the previous one —"
        " circular arguments are a protocol violation.",
    ]
    if humor:
        directive = inconvenience_directive(humor.critic.inconvenience)
        if directive:
            lines += ["", directive]
    return "\n".join(lines)


def _build_second_satirist_prompt(
    brief: EnrichedBrief, humor: HumorConfig | None = None
) -> str:
    # Replaces the adversarial Critic with a collaborative second Satirist voice.
    lines = [
        "You are the Second Satirist for Gata Newsroom.",
        "Your partner has proposed a cartoon concept. Your job is to build upon it"
        " — sharpen the angle, add the detail they missed, push the joke further.",
        "You are not a critic. Do not evaluate rules. Do not reject.",
        "Instead: contribute. Make the concept more surprising, more specific,"
        " or more inconvenient than your partner dared.",
        f"Target audience: {brief.target_audience}.",
        f"Output language: {brief.output_language}"
        " — ALL text in the cartoon must be in this language.",
        "",
        "When the concept has reached its highest potential and you cannot improve"
        " it further, respond with exactly:",
        "<verdict>APPROVED</verdict>",
        "Otherwise, contribute your improved version directly — no preamble,"
        " no critique, just the sharper concept.",
    ]
    if humor:
        directive = inconvenience_directive(humor.critic.inconvenience)
        if directive:
            lines += ["", directive]
    return "\n".join(lines)


def run(
    topic: str,
    brief: EnrichedBrief,
    humor: HumorConfig | None = None,
    layout: CartoonLayout | None = None,
) -> tuple[CartoonConcept, ConversationLog, AgentTelemetry]:
    satirist = PersonaConfig(
        name="Satirist",
        models=_CLAUDE_MODELS,
        system_prompt=_build_satirist_system_prompt(brief, humor, layout),
    )
    critic = PersonaConfig(
        name="Critic",
        models=_GEMINI_CRITIC_MODELS,
        system_prompt=_build_critic_system_prompt(brief, humor),
    )
    loop = DualPersonaLoop(satirist, critic, loop_name="B/C", self_review_passes=3)
    loop_output = loop.run(topic)
    verdict_content = loop_output.verdict
    # Multi-panel path: parse JSON verdict into a list of PanelConcept objects
    if layout is not None and layout.panels > 1:
        concept = _parse_multi_panel_verdict(verdict_content, layout)
    else:
        # Single-panel path: verdict content is the image prompt verbatim
        concept = CartoonConcept(
            full_text=verdict_content,
            image_prompt=verdict_content,
            iteration=0,
        )
    logger.info(
        "satirist: concept produced — panels=%s cultural_angle=%r",
        len(concept.panels) if concept.panels else "single",
        brief.cultural_angle[:60],
    )
    # telemetry is always populated by DualPersonaLoop; guard for safety
    telemetry = loop_output.telemetry or AgentTelemetry(
        agent_name="B/C", duration_seconds=0.0, iterations=0
    )
    return concept, loop_output.log, telemetry


def _parse_multi_panel_verdict(
    verdict_content: str,
    layout: CartoonLayout,
) -> CartoonConcept:
    # Strip markdown fences defensively — same pattern as trend_scout ranking
    clean = verdict_content.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean)
    clean = re.sub(r"\s*```$", "", clean)
    try:
        parsed = json.loads(clean)
        panels_data = parsed.get("panels", [])
        if not isinstance(panels_data, list) or len(panels_data) != layout.panels:
            raise ValueError(
                f"expected {layout.panels} panels, got {len(panels_data)}"
            )
        panel_concepts = [
            PanelConcept(
                scene=str(p["scene"]),
                caption=str(p["caption"]),
                beat=str(p.get("beat", "")),
            )
            for p in panels_data
        ]
        return CartoonConcept(
            full_text=verdict_content,
            image_prompt="",
            iteration=0,
            panels=panel_concepts,
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        logger.warning(
            "satirist: multi-panel verdict parse failed (%s)"
            " — falling back to single-panel",
            exc,
        )
        # Use raw verdict as single-panel prompt — ensures output is always produced
        return CartoonConcept(
            full_text=verdict_content,
            image_prompt=verdict_content,
            iteration=0,
        )
