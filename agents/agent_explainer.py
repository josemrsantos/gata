import logging

from core.types import ConversationLog, EnrichedBrief, PersonaConfig
from llm import LLMProvider
from llm.parallel_panel import ParallelPanel

logger = logging.getLogger(__name__)


_WRITER_SYSTEM = (
    "You are an HTML content writer for Gata Newsroom.\n"
    "You receive a brief describing a satirical cartoon and must produce a complete, "
    "self-contained HTML5 explanation page.\n\n"
    "REQUIREMENTS:\n"
    "- Start with <!DOCTYPE html>\n"
    '- Include <meta charset="UTF-8"> in the <head>\n'
    "- Set the lang attribute on the <html> tag to the target language code\n"
    "- Use semantic structure: one <h1> heading and body paragraphs in <p> tags\n"
    "- No external resources: no CDN links, no <script src>, no <link rel=stylesheet>\n"
    "- No inline style attributes\n\n"
    "Wrap your complete HTML output in <verdict>...</verdict> tags."
)

_EXPLAINER_AGGREGATOR_SYSTEM = (
    "You are The Editor — an HTML quality judge for Gata Newsroom.\n"
    "Three writers have independently produced an HTML explanation page.\n"
    "Your job is to:\n"
    "1. Evaluate each page against ALL of these criteria:\n"
    "   a. Contains <!DOCTYPE html>\n"
    '   b. Contains <meta charset="UTF-8"> in the <head>\n'
    "   c. The lang attribute on <html> matches the target language\n"
    "   d. All body text is in the correct language (no leakage)\n"
    "   e. Content clearly explains the satirical angle and cultural references\n"
    "   f. No external resource links\n"
    "2. Pick the page that best satisfies all criteria. If multiple pages pass,"
    " prefer the most thorough explanation.\n"
    "3. Output a PICK: N line (N = the chosen page number), then the complete chosen"
    " HTML page wrapped in <verdict>...</verdict> tags.\n\n"
    "Do not add preamble. Do not modify the chosen HTML. Output only PICK: N and the"
    " <verdict> block containing the verbatim HTML."
)


def _build_context(
    enriched_brief: EnrichedBrief,
    agent0_log: ConversationLog | None,
    bc_log: ConversationLog | None,
    image_prompt: str,
) -> str:
    refs = "\n".join(f"- {r}" for r in enriched_brief.culturally_loaded_references)
    parts = [
        f"TARGET AUDIENCE: {enriched_brief.target_audience}",
        f"TARGET LANGUAGE: {enriched_brief.output_language}",
        f"TONE: {enriched_brief.tone}",
        f"CULTURAL ANGLE: {enriched_brief.cultural_angle}",
        f"KEY CULTURAL REFERENCES:\n{refs}",
        f"IMAGE PROMPT (what the cartoon shows):\n{image_prompt}",
    ]
    if agent0_log and agent0_log.turns:
        parts.append(f"AGENT 0 LOOP: {len(agent0_log.turns)} turns captured")
    if bc_log and bc_log.turns:
        parts.append(f"B/C LOOP: {len(bc_log.turns)} turns captured")
    return "\n\n".join(parts)


def generate_html(
    enriched_brief: EnrichedBrief,
    agent0_log: ConversationLog | None,
    bc_log: ConversationLog | None,
    image_prompt: str,
    panelist_providers: list[LLMProvider],
    aggregator_providers: list[LLMProvider],
) -> tuple[str, str]:
    """Generate in-language and English HTML explanation files via ParallelPanel."""
    # one PersonaConfig per panelist provider, all using the Writer system prompt
    panelists = [
        PersonaConfig(
            name="Writer", providers=[p], system_prompt=_WRITER_SYSTEM, max_tokens=8192
        )
        for p in panelist_providers
    ]
    # aggregator PersonaConfig constructed once and shared across both panel runs
    aggregator = PersonaConfig(
        name="Editor",
        providers=aggregator_providers,
        system_prompt=_EXPLAINER_AGGREGATOR_SYSTEM,
    )
    context = _build_context(enriched_brief, agent0_log, bc_log, image_prompt)

    # generate in-language explanation
    in_lang_prompt = (
        f"{context}\n\n"
        f"TASK: Write a complete HTML5 explanation page in"
        f" {enriched_brief.output_language}. "
        f"The page is for an end user who does not understand the joke. "
        f"Explain the satirical angle, the cultural references, and why it is funny. "
        f"The lang attribute must be set to the appropriate ISO language code for "
        f"{enriched_brief.output_language}."
    )
    in_lang_panel = ParallelPanel(
        panelists=panelists,
        aggregator=aggregator,
        panel_name="explainer-lang",
    )
    in_lang_output = in_lang_panel.run(in_lang_prompt)
    logger.info("agent_explainer: in-language HTML generated")

    # generate English deep-dive for operator
    english_prompt = (
        f"{context}\n\n"
        "TASK: Write a complete HTML5 explanation page in English. "
        "The page is for an operator who may have no prior knowledge of the"
        " target culture. "
        "Explain the news background, what cultural references were used and why"
        " they resonate "
        "with the target audience, and what makes the satirical angle effective. "
        "The lang attribute must be 'en'."
    )
    english_panel = ParallelPanel(
        panelists=panelists,
        aggregator=aggregator,
        panel_name="explainer-en",
    )
    english_output = english_panel.run(english_prompt)
    logger.info("agent_explainer: English deep-dive HTML generated")

    return in_lang_output.verdict, english_output.verdict
