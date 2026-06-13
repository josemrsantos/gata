import logging
import re

from agents.dual_loop import DualPersonaLoop
from agents.humor_utils import inconvenience_directive
from agents.types import (
    ConversationLog,
    EnrichedBrief,
    Headline,
    HumorConfig,
    PersonaConfig,
    StrategyBrief,
)

logger = logging.getLogger(__name__)

_FRAMER_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "claude-haiku-4-5-20251001",
]
_RESONATOR_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

def _build_framer_system_prompt(humor: HumorConfig | None = None) -> str:
    lines = [
        "You are The Framer — a cultural strategist for Gata Newsroom.",
        "Given a news topic and a seed strategy brief, identify the satirical reading "
        "of the topic for the target audience. You must produce two things:",
        "1. A CULTURAL ANGLE: a one-paragraph satirical framing of the topic that will "
        "resonate specifically with the target audience's cultural context.",
        "2. REFERENCES: a bullet list of short observations (one or two sentences each)"
        " that the target audience would recognise — cultural touchstones, shared"
        " memories, or widely known incidents that are NOT in the news topic itself"
        " but deepen the satirical reading.",
    ]
    if humor and humor.framer.wordplay_scan:
        lines += [
            "",
            "WORDPLAY SCAN: actively look for pun or wordplay opportunities in the "
            f"target language ({humor.framer.language_register} register) that could "
            "sharpen the satirical angle.",
        ]
    if humor:
        joke_types_str = " | ".join(humor.framer.joke_types)
        lines += [
            "",
            f"JOKE TYPE: select the most appropriate type from [{joke_types_str}]"
            " based on the cultural angle and include it as a JOKE TYPE field"
            " in your verdict.",
        ]
    lines += [
        "",
        "The target audience, output language, and tone are LOCKED"
        " — you cannot change them.",
        "Each iteration must make measurable progress; repeating a previous position"
        " is not permitted.",
        "",
        "Wrap your entire output in <verdict>...</verdict> tags"
        " using exactly this structure:",
        "<verdict>",
        "CULTURAL ANGLE: [one paragraph]",
        "REFERENCES:",
        "- [reference 1]",
        "- [reference 2]",
    ]
    if humor:
        lines.append(f"JOKE TYPE: [{' | '.join(humor.framer.joke_types)}]")
    lines.append("</verdict>")
    if humor and humor.framer.inconvenience > 0:
        directive = inconvenience_directive(humor.framer.inconvenience)
        if directive:
            lines += ["", directive]
    return "\n".join(lines)

_RESONATOR_SYSTEM = (
    "You are The Resonator — a cultural critic for Gata Newsroom.\n"
    "You receive a proposed cultural angle and references from The Framer and evaluate "
    "whether they will genuinely resonate with the stated target audience.\n\n"
    "If the angle and references are culturally sharp, specific, and genuinely"
    " cannot be improved for this audience:\n"
    "<verdict>APPROVED</verdict>\n\n"
    "If they are too generic, inaccurate, or a material improvement exists:\n"
    "<verdict>NEEDS REVISION</verdict>\n"
    "followed by specific, actionable feedback. You must propose an alternative "
    "angle or flag which references are weak and why. Generic critique is not "
    "acceptable.\n\n"
    "Each iteration of feedback must be different from the previous one — circular "
    "arguments are a protocol violation."
)


def _parse_verdict(verdict_content: str) -> tuple[str, list[str], str]:
    angle_match = re.search(
        r"CULTURAL ANGLE:[ \t]*(.*?)(?=\nREFERENCES:|\Z)", verdict_content, re.DOTALL
    )
    cultural_angle = angle_match.group(1).strip() if angle_match else ""
    refs_match = re.search(
        r"REFERENCES:\s*(.*?)(?:\nJOKE TYPE:|\Z)", verdict_content, re.DOTALL
    )
    references: list[str] = []
    if refs_match:
        for line in refs_match.group(1).splitlines():
            stripped = line.lstrip("-• ").strip()
            if stripped:
                references.append(stripped)
    joke_match = re.search(r"JOKE TYPE:[ \t]*(\S+)", verdict_content)
    joke_type = joke_match.group(1).strip() if joke_match else ""
    return cultural_angle, references, joke_type


def run(
    topic: str,
    seed_brief: StrategyBrief,
    news_brief: Headline | None = None,
    humor: HumorConfig | None = None,
) -> tuple[EnrichedBrief, ConversationLog]:
    framer = PersonaConfig(
        name="Framer",
        models=_FRAMER_MODELS,
        system_prompt=_build_framer_system_prompt(humor),
    )
    resonator = PersonaConfig(
        name="Resonator",
        models=_RESONATOR_MODELS,
        system_prompt=_RESONATOR_SYSTEM,
    )
    loop = DualPersonaLoop(framer, resonator, loop_name="Agent 0", self_review_passes=3)
    news_context = ""
    if news_brief and (news_brief.abstract or news_brief.source):
        parts = []
        if news_brief.source:
            parts.append(f"Source: {news_brief.source}")
        if news_brief.abstract:
            parts.append(f"Summary: {news_brief.abstract}")
        news_context = "\n" + "\n".join(parts)
    initial_input = (
        f"News topic: {topic}{news_context}\n\n"
        f"Target audience: {seed_brief.target_audience}\n"
        f"Output language: {seed_brief.output_language}\n"
        f"Tone: {seed_brief.tone}"
    )
    loop_output = loop.run(initial_input)
    cultural_angle, references, joke_type = _parse_verdict(loop_output.verdict)
    if not cultural_angle:
        raise ValueError("Agent 0: cultural_angle is empty — enrichment failed")
    if not references:
        raise ValueError(
            "Agent 0: culturally_loaded_references is empty — enrichment failed"
        )
    enriched = EnrichedBrief(
        target_audience=seed_brief.target_audience,
        output_language=seed_brief.output_language,
        tone=seed_brief.tone,
        cultural_angle=cultural_angle,
        culturally_loaded_references=references,
        joke_type=joke_type,
    )
    logger.info(
        "cultural_strategist: enriched brief"
        " — cultural_angle=%r references=%d",
        cultural_angle[:80],
        len(references),
    )
    return enriched, loop_output.log
