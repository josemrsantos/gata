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

_OUTPUT_FORMAT_RULES = (
    'OUTPUT FORMAT — wrap in <verdict>...</verdict> tags, return ONLY valid JSON:\n'
    "{\n"
    '  "panels": <integer 1–4>,\n'
    '  "layout": "horizontal" or "vertical",\n'
    '  "content": [\n'
    '    {"scene": "...", "caption": "...", "beat": "..."},\n'
    "    ...\n"
    "  ]\n"
    "}\n"
    "\n"
    "CONTENT RULES:\n"
    '- panels = 1: "scene" MUST include Gata\'s full character description verbatim'
    " and all visual style rules — it feeds directly into the image generator.\n"
    '- panels ≥ 2: "scene" describes only the panel\'s action; character and style'
    " are added automatically. Each panel MUST have a non-empty \"beat\".\n"
    '- "caption" must always be in the specified output language.\n'
    "- No preamble, no explanation, no markdown fences."
)


def _build_satirist_system_prompt(
    brief: EnrichedBrief,
    humor: HumorConfig | None = None,
    layout_override: CartoonLayout | None = None,
) -> str:
    today = date.today().strftime("%d %B %Y")
    lines = [
        "You are a satirical cartoon writer for the Gata Newsroom.",
        f"Today's date is {today}."
        " Use this when referencing current events, years, or dates.",
        "",
        "CHARACTER — always include verbatim in every single-panel image prompt:",
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
    if layout_override is not None:
        # Caller has specified an exact format — constrain the Satirist to it
        n = layout_override.panels
        direction = layout_override.direction
        lines += [
            "",
            f"TASK: Generate a {n}-panel {direction} cartoon concept featuring Gata.",
            f"The joke spans all {n} panels as a progressive narrative arc.",
        ]
    else:
        # Auto-layout: the Satirist chooses the format that best fits the joke
        lines += [
            "",
            "TASK: Choose the ideal panel count and direction, then generate the"
            " concept.",
            "",
            "PANEL COUNT — choose based on narrative needs:",
            "- 1 panel: single strong visual, punch-at-a-glance, no buildup needed",
            "- 2 panels: setup → punchline, or before/after contrast",
            "- 3 panels: escalation with three beats (most expressive choice)",
            "- 4 panels: four-beat arc (use sparingly — only when all four beats"
            " are essential)",
            "",
            "LAYOUT — choose based on how the panels relate:",
            "- horizontal: left-to-right time progression or side-by-side comparison",
            "- vertical: top-to-bottom cause → effect or power-relationship sequence",
        ]
    lines += ["", _OUTPUT_FORMAT_RULES]
    if humor and humor.satirist.joke_explanation:
        lines += [
            "After the JSON, add a <joke_explanation>...</joke_explanation> block:",
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


def _parse_verdict(
    verdict_content: str,
    layout_override: CartoonLayout | None,
) -> tuple[CartoonConcept, CartoonLayout]:
    clean = verdict_content.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean)
    clean = re.sub(r"\s*```$", "", clean)
    try:
        parsed = json.loads(clean)
        panels_chosen = int(parsed.get("panels", 1))
        direction_chosen = str(parsed.get("layout", "horizontal"))
        content = parsed.get("content", [])
        # Caller-specified override wins over Satirist's choice
        if layout_override is not None:
            panels_chosen = layout_override.panels
            direction_chosen = layout_override.direction
        layout = CartoonLayout(panels=panels_chosen, direction=direction_chosen)
        if panels_chosen == 1:
            # Single-panel: scene already contains full char description and style
            scene = str(content[0].get("scene", "")) if content else verdict_content
            return CartoonConcept(
                full_text=verdict_content,
                image_prompt=scene,
                iteration=0,
            ), layout
        # Multi-panel: validate content length matches chosen panel count
        if len(content) != panels_chosen:
            raise ValueError(
                f"expected {panels_chosen} items in content, got {len(content)}"
            )
        panel_concepts = [
            PanelConcept(
                scene=str(p["scene"]),
                caption=str(p["caption"]),
                beat=str(p.get("beat", "")),
            )
            for p in content
        ]
        return CartoonConcept(
            full_text=verdict_content,
            image_prompt="",
            iteration=0,
            panels=panel_concepts,
        ), layout
    except (json.JSONDecodeError, KeyError, ValueError, TypeError, IndexError) as exc:
        logger.warning(
            "satirist: verdict parse failed (%s) — falling back to single-panel", exc
        )
        # Fallback always produces something; uses raw verdict as the image prompt
        return CartoonConcept(
            full_text=verdict_content,
            image_prompt=verdict_content,
            iteration=0,
        ), CartoonLayout(panels=1, direction="horizontal")


def run(
    topic: str,
    brief: EnrichedBrief,
    humor: HumorConfig | None = None,
    layout_override: CartoonLayout | None = None,
) -> tuple[CartoonConcept, ConversationLog, AgentTelemetry, CartoonLayout]:
    satirist = PersonaConfig(
        name="Satirist",
        models=_CLAUDE_MODELS,
        system_prompt=_build_satirist_system_prompt(brief, humor, layout_override),
    )
    critic = PersonaConfig(
        name="Critic",
        models=_GEMINI_CRITIC_MODELS,
        system_prompt=_build_critic_system_prompt(brief, humor),
    )
    loop = DualPersonaLoop(
        satirist, critic, loop_name="Satirist/Critic", self_review_passes=3
    )
    loop_output = loop.run(topic)
    concept, layout = _parse_verdict(loop_output.verdict, layout_override)
    logger.info(
        "satirist: concept produced — panels=%d layout=%s cultural_angle=%r",
        layout.panels,
        layout.direction,
        brief.cultural_angle[:60],
    )
    # telemetry is always populated by DualPersonaLoop; guard for safety
    telemetry = loop_output.telemetry or AgentTelemetry(
        agent_name="Satirist/Critic", duration_seconds=0.0, iterations=0
    )
    return concept, loop_output.log, telemetry, layout
