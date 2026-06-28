import json
import logging
import re

from google.genai import types as genai_types

from core.humor_utils import inconvenience_directive
from core.types import (
    AgentTelemetry,
    AudienceProfile,
    ConversationLog,
    EnrichedBrief,
    Headline,
    HumorConfig,
    MoodBrief,
    PersonaConfig,
    StrategyBrief,
)
from llm import LLMProvider
from llm.fair_parallel_panel import FairParallelPanel
from llm.gemini import get_gemini_client

logger = logging.getLogger(__name__)

_INFERENCE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
]

_AUDIENCE_INFERENCE_SYSTEM = (
    "Given a news topic, identify the single most relevant audience for satirical"
    " cartoon coverage. Consider: who would find this topic most meaningful or funny,"
    " what language they speak, and what comedy style resonates with their culture."
    " If you are uncertain about comedy norms for a culture, reason from what you know"
    " about that culture's satire traditions, popular media, and sense of humour.\n\n"
    "Return ONLY a valid JSON array containing exactly one element, with no preamble"
    " or markdown fences. The element must have exactly these string keys:\n"
    '  "name": short lowercase slug used as a filename (e.g. "swiss", "qatar")\n'
    '  "audience": human description (e.g. "Swiss German-speaking public")\n'
    '  "language": the language to write the cartoon in'
    ' (be specific, e.g. "Brazilian Portuguese")\n'
    '  "tone": comedy style that works for this audience'
    ' (e.g. "dry Swiss wit", "Gulf Arabic satire")\n\n'
    "Example output:\n"
    '[{"name":"swiss","audience":"Swiss German-speaking public",'
    '"language":"Swiss German","tone":"dry Swiss wit"}]'
)

_AUDIENCE_FALLBACK: list[AudienceProfile] = [
    # Single entry — _ensure_uk in cli.py appends UK, giving the same "main + UK" shape
    AudienceProfile(
        name="global",
        audience="global English-speaking public",
        language="English",
        tone="international wit",
    ),
]


def infer_audiences(topic: str) -> list[AudienceProfile]:
    """Infer relevant audiences for a topic, trying each model in turn.

    Returns a parsed list of AudienceProfile objects. Falls back to
    _AUDIENCE_FALLBACK only when all models are exhausted.
    """
    client = get_gemini_client()
    for model in _INFERENCE_MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=f"News topic: {topic}",
                config=genai_types.GenerateContentConfig(
                    system_instruction=_AUDIENCE_INFERENCE_SYSTEM,
                    temperature=0.2,
                ),
            )
            # Strip markdown fences defensively before JSON parse
            raw = response.text.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)
            if not isinstance(parsed, list) or not parsed:
                raise ValueError(f"inference returned non-list: {raw!r}")
            profiles = [
                AudienceProfile(
                    name=str(item.get("name", "audience")).lower().replace(" ", "_"),
                    audience=str(item.get("audience", "")),
                    language=str(item.get("language", "English")),
                    tone=str(item.get("tone", "wit")),
                )
                for item in parsed
            ]
            logger.info(
                "infer_audiences: inferred %d audiences for topic %r",
                len(profiles),
                topic[:60],
            )
            return profiles
        except Exception as exc:
            logger.debug(
                "infer_audiences: model %s failed (%s) — trying next", model, exc
            )
    logger.warning("infer_audiences: all models failed — using fallback audience")
    return list(_AUDIENCE_FALLBACK)


_MOOD_INFERENCE_SYSTEM = (
    "You are a cultural analyst with real-time web access.\n"
    "Given a news topic and a target audience, describe the current emotional mood of"
    " that audience toward the topic. Search the web for recent reactions, commentary,"
    " and public sentiment if needed.\n\n"
    "Return ONLY a valid JSON object with no preamble or markdown fences:\n"
    '  "mood_summary": one paragraph describing the current mood\n'
    '  "emotional_posture": a short label (e.g. "defensive optimism",'
    ' "anxious pride", "resigned cynicism")\n'
    '  "key_triggers": array of 3-5 short strings — current cultural references,'
    " recent events, or shared experiences that would sharpen a satirical cartoon"
    " for this audience right now"
)


def infer_mood(topic: str, audience: str, language: str) -> MoodBrief | None:
    """Return the current emotional mood of an audience toward a topic.

    Uses Gemini with Google Search grounding for real-time accuracy.
    Tries each model in turn; returns None only when all are exhausted so
    callers can proceed without mood context.
    """
    client = get_gemini_client()
    for model in _INFERENCE_MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=(
                    f"Topic: {topic}\nAudience: {audience}\nLanguage: {language}"
                ),
                config=genai_types.GenerateContentConfig(
                    system_instruction=_MOOD_INFERENCE_SYSTEM,
                    tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                    temperature=0.2,
                ),
            )
            # Strip markdown fences defensively before JSON parse
            raw = response.text.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)
            triggers = parsed.get("key_triggers", [])
            if not isinstance(triggers, list):
                triggers = []
            mood = MoodBrief(
                mood_summary=str(parsed.get("mood_summary", "")),
                emotional_posture=str(parsed.get("emotional_posture", "")),
                key_triggers=[str(t) for t in triggers],
            )
            logger.info(
                "infer_mood: posture=%r triggers=%d for audience=%r",
                mood.emotional_posture,
                len(mood.key_triggers),
                audience,
            )
            return mood
        except Exception as exc:
            logger.debug("infer_mood: model %s failed (%s) — trying next", model, exc)
    logger.warning("infer_mood: all models failed — proceeding without mood context")
    return None


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


_CS_AGGREGATOR_SYSTEM = (
    "You are The Resonator — a cultural critic and chief editor for Gata Newsroom.\n"
    "Three Framers have independently proposed a cultural angle and reference list for"
    " the topic below. Your job is to:\n"
    "1. Evaluate each proposal for genuine cultural resonance with the stated target"
    " audience — specificity, accuracy, and satirical sharpness matter most.\n"
    "2. Pick the single strongest proposal, or synthesise the best elements from"
    " multiple proposals into one superior angle.\n"
    "3. Output a PICK: N line (N = the proposal number you selected as primary), then"
    " your final cultural angle in the exact format below, wrapped in"
    " <verdict>...</verdict>:\n\n"
    "<verdict>\n"
    "CULTURAL ANGLE: [one paragraph]\n"
    "REFERENCES:\n"
    "- [reference 1]\n"
    "- [reference 2]\n"
    "JOKE TYPE: [type]\n"
    "</verdict>\n\n"
    "If a JOKE TYPE field was present in the proposals, carry the best one forward.\n"
    "If none was present, omit the field.\n"
    "Do not add preamble. Output only PICK: N and the <verdict> block."
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
    panelist_providers: list[list[LLMProvider]],
    aggregator_providers: list[LLMProvider],
    news_brief: Headline | None = None,
    humor: HumorConfig | None = None,
) -> tuple[EnrichedBrief, ConversationLog, AgentTelemetry]:
    framer_prompt = _build_framer_system_prompt(humor)
    # Each slot is an ordered fallback chain; primary provider name labels the panelist.
    panelists = [
        PersonaConfig(
            name=slot[0].model_id, providers=slot, system_prompt=framer_prompt
        )
        for slot in panelist_providers
    ]
    aggregator = PersonaConfig(
        name="Resonator",
        providers=aggregator_providers,
        system_prompt=_CS_AGGREGATOR_SYSTEM,
    )
    panel = FairParallelPanel(
        panelists=panelists,
        aggregator=aggregator,
        panel_name="Cultural Strategist",
    )
    news_context = ""
    if news_brief and (news_brief.abstract or news_brief.source):
        parts = []
        if news_brief.source:
            parts.append(f"Source: {news_brief.source}")
        if news_brief.abstract:
            parts.append(f"Summary: {news_brief.abstract}")
        news_context = "\n" + "\n".join(parts)
    # infer current mood before building the initial input — failure is non-fatal
    mood = infer_mood(topic, seed_brief.target_audience, seed_brief.output_language)
    mood_context = ""
    if mood:
        trigger_lines = "\n".join(f"- {t}" for t in mood.key_triggers)
        mood_context = (
            f"\n\nCURRENT MOOD (use this to sharpen the cultural angle):\n"
            f"{mood.mood_summary}\n"
            f"Emotional posture: {mood.emotional_posture}\n"
            f"Key cultural triggers:\n{trigger_lines}"
        )
    initial_input = (
        f"News topic: {topic}{news_context}{mood_context}\n\n"
        f"Target audience: {seed_brief.target_audience}\n"
        f"Output language: {seed_brief.output_language}\n"
        f"Tone: {seed_brief.tone}"
    )
    loop_output = panel.run(initial_input)
    cultural_angle, references, joke_type = _parse_verdict(loop_output.verdict)
    if not cultural_angle:
        raise ValueError(
            "Cultural Strategist: cultural_angle is empty — enrichment failed"
        )
    if not references:
        raise ValueError(
            "Cultural Strategist: culturally_loaded_references is empty"
            " — enrichment failed"
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
        "cultural_strategist: enriched brief — cultural_angle=%r references=%d",
        cultural_angle[:80],
        len(references),
    )
    # telemetry is always populated by FairParallelPanel; guard for safety
    telemetry = loop_output.telemetry or AgentTelemetry(
        agent_name="Cultural Strategist", duration_seconds=0.0, iterations=0
    )
    return enriched, loop_output.log, telemetry
