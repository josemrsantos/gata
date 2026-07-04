import logging
import time

from core.types import AgentTelemetry, EnrichedBrief, RunTelemetry, TokenUsage
from llm.base import LLMProvider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Gata, a sardonic cat analyst who reports on the absurdities of corporate
culture. You write in short punchy paragraphs. You use dry wit, feline metaphors,
and a deadpan tone. You never use exclamation marks. You never flatter the reader.
Never use the hyphen-minus character (-) as an em dash: use a colon (:) or a comma
(,) instead. Bold full sentences only, never isolated words.

You will produce five pieces of text. Each piece is preceded by its marker on its
own line. Output the markers exactly as shown, then the content on the next line(s).

===TITLE===
One punchy article title. Satirical, relatable to a broad LinkedIn audience.
No leading # symbol. No trailing punctuation.

===MESSAGE===
The body of "A Message from Gata". Rules:
- Opening line: one short punchy sentence. Stands alone as its own paragraph.
- Body: maximum 4 paragraphs. Group related ideas; do not put every sentence on
  its own line. Leave one blank line between paragraphs.
- Exactly one bold sentence (the core satirical insight). Wrap it in **double
  asterisks**. Bold the full sentence, never isolated words.
Do NOT include the subscribe link, email, repost line, or comment question here.
Stop after the bold sentence (or after the last body paragraph if the bold sentence
is inside the body).

===COMMENT===
One question inviting readers to comment, tied directly to the article topic.
Ask about the reader's own experience. One sentence ending with a question mark.

===PUNCHLINE===
One closing line for the tech stack section. Dry, deadpan, related to the article
topic or image. No leading/trailing asterisks — the caller adds italic formatting.

===NOTIFICATION===
2-3 sentence push notification for LinkedIn followers. Must make someone stop
scrolling and click. Tied to the topic and Gata's sardonic angle. Subtly reflects
that Jose is open to new opportunities, without being blunt. End with \U0001f43e.
Minimum 20 characters.
"""

# Static closing block appended to the Gata message section (Section 3).
_CLOSING_BLOCK = (
    "If you enjoyed this kind of corporate absurdity served with a side of"
    " sardines, repost to spread the word of the gata.\n\n"
    "{comment}\n\n"
    "If you have a story you think Gata should investigate, send it to"
    " gata.the.reporter@gmail.com.\n\n"
    "If you enjoy this kind of corporate absurdity served with a side of"
    " sardines, subscribe to the Gata Newsletter here:\n"
    "https://www.linkedin.com/build-relation/newsletter-follow"
    "?entityUrn=7476681937277980672\n\n"
    "And if you want to talk shop, reach Gata at gata.the.reporter@gmail.com."
)

# Static Section 4 body (without the closing punchline, which is LLM-generated).
_SECTION_4_BODY = """\
# Behind the Scenes: The Tech Stack

Curious about how this report was built? Gata isn't just a character; she is an \
automated data project.

- **The Birthplace:** You can explore the code, the multi-agent orchestration, and \
the logic behind the curtain over at the \
[GitHub Repository](https://github.com/josemrsantos/gata/) - built and engineered \
by The Creator (visit [Jose Santos on LinkedIn](https://www.linkedin.com/in/josemrsantos/)).

- **Open Source & Contributions:** The codebase is fully open-source under the MIT \
License. Anyone is welcome to clone it, use it, or actively contribute to the \
project's evolution. https://github.com/josemrsantos/gata/

- **The Engineering Behind It:** This project is a real-world playground for \
Spec-Driven Development (SDD) using spec-kit and Claude Code. The engine runs on a \
multi-agent framework where Claude, Gemini, and Grok exchange and refine prompts \
autonomously to maximise the quality and irony of the final output.
"""


def _parse_sections(raw: str) -> dict[str, str]:
    # Split on section markers; each marker starts a new keyed block.
    markers = [
        "===TITLE===",
        "===MESSAGE===",
        "===COMMENT===",
        "===PUNCHLINE===",
        "===NOTIFICATION===",
    ]
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped in markers:
            # Save whatever was accumulated for the previous key before switching.
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = stripped.replace("===", "").strip()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)
    # Flush the last section after the loop ends.
    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


def _assemble_article(sections: dict[str, str], telemetry: RunTelemetry) -> str:
    title = sections.get("TITLE", "A Message from Gata")
    message = sections.get("MESSAGE", "")
    comment = sections.get("COMMENT", "")
    punchline = sections.get("PUNCHLINE", "")
    # Section 1: article title as H1.
    s1 = f"# {title}"
    # Section 2: image caption from telemetry — no LLM involvement.
    duration = telemetry.total_duration_seconds
    cost = telemetry.total_cost_usd
    s2 = (
        f"*Pipeline Execution Metrics - Total Time: {duration:.1f}s"
        f" | Total Cost: ${cost:.4f}*"
    )
    # Section 3: Gata message — body from LLM, closing block from template.
    closing = _CLOSING_BLOCK.format(comment=comment) if comment else ""
    gata_body = f"{message}\n\n{closing}".strip() if closing else message
    s3 = f"# A Message from Gata \U0001f43e\n\n{gata_body}"
    # Section 4: static body + LLM-generated italic punchline.
    s4 = _SECTION_4_BODY.rstrip()
    if punchline:
        s4 = f"{s4}\n\n*{punchline}*"
    return f"{s1}\n\n{s2}\n\n{s3}\n\n{s4}"


def generate_linkedin_post(
    brief: EnrichedBrief,
    image_prompt: str,
    topic: str,
    telemetry: RunTelemetry,
    providers: list[LLMProvider],
) -> tuple[str, str]:
    """Generate the LinkedIn article markdown and notification text.

    Returns (article_md, notification_txt). Never raises — on total failure
    returns empty strings so the caller can skip writing files.
    """
    # Build the user message with all context the model needs.
    refs = "\n".join(f"- {r}" for r in brief.culturally_loaded_references)
    user_msg = (
        f"Story topic: {topic}\n\n"
        f"Cultural angle: {brief.cultural_angle}\n\n"
        f"Key references:\n{refs}\n\n"
        f"Image concept: {image_prompt}"
    )
    messages = [{"role": "user", "content": user_msg}]
    start = time.monotonic()
    token_calls: list[TokenUsage] = []
    last_exc: Exception | None = None
    # Try each provider in order; stop on the first successful response.
    for provider in providers:
        try:
            raw, usage = provider.generate(_SYSTEM_PROMPT, messages, max_tokens=1500)
            token_calls.append(usage)
            break
        except Exception as exc:
            logger.warning(
                "linkedin_post: provider %s failed — %s", provider.model_id, exc
            )
            last_exc = exc
    else:
        logger.error("linkedin_post: all providers exhausted — %s", last_exc)
        return "", ""
    # Record agent telemetry onto the run telemetry object.
    duration = time.monotonic() - start
    agent_tel = AgentTelemetry(
        agent_name="LinkedIn Post",
        duration_seconds=duration,
        iterations=1,
        calls=token_calls,
    )
    telemetry.agents.append(agent_tel)
    # Parse the structured response into named sections.
    sections = _parse_sections(raw)
    if not sections:
        logger.warning("linkedin_post: response contained no recognised markers")
        return "", ""
    # Assemble the final markdown article and extract the notification snippet.
    article_md = _assemble_article(sections, telemetry)
    notification_txt = sections.get("NOTIFICATION", "")
    return article_md, notification_txt
