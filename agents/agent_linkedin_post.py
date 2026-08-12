import concurrent.futures
import html
import logging
import re
import time
from urllib.parse import urlparse

import httpx
from google.genai import types as genai_types

from core.types import (
    AgentTelemetry,
    EnrichedBrief,
    PersonaConfig,
    ResearchDigest,
    ResearchSource,
    RunTelemetry,
    TokenUsage,
)
from llm.base import LLMProvider
from llm.claude import _COST_PER_M as _CLAUDE_COST_PER_M
from llm.claude import ClaudeProvider
from llm.fair_parallel_panel import FairParallelPanel
from llm.gemini import GeminiProvider
from llm.gemini import compute_cost as _gemini_compute_cost
from llm.grok import _COST_PER_M as _GROK_COST_PER_M
from llm.grok import GrokProvider

logger = logging.getLogger(__name__)

# Bounds each panelist provider's own research call (Spec 042 FR-001) and the
# writing FairParallelPanel's per-round budget (FR-009) — both set to 120s.
_RESEARCH_TIMEOUT_SECONDS = 120.0
_WRITING_PANEL_TIMEOUT_SECONDS = 120.0

# Per-URL budget for the source-title enrichment fetch, shared by Gemini and
# Grok (Spec 043 FR-002/FR-003) — short enough that even a full set of
# slow/hanging fetches can't meaningfully threaten either provider's 120s
# research budget above.
_TITLE_FETCH_TIMEOUT_SECONDS = 5.0
_TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
# Confirmed live: Wikipedia (and likely other sites) return HTTP 403 for
# requests with no User-Agent header, which _fetch_page_title would otherwise
# silently treat as "no title found" — a real browser-like UA fixes this for
# the sites that gate on it, without changing behaviour for sites that don't.
_TITLE_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

_RESEARCH_SYSTEM = (
    "You are a research assistant preparing background for a professional"
    " article. Use web search to find current, factual, credible information"
    " about the given topic. Summarise your findings in clear, neutral prose (2-4"
    " paragraphs) — report what the sources say, do not editorialise or joke."
)

_PLANNER_SYSTEM = (
    "You are an editorial panelist scoping a professional LinkedIn article.\n"
    "You are given a topic and your own web research findings on it. Propose 2-4"
    " distinct angles the article could explore — substantively different from"
    " each other (e.g. contrasting when something is the right approach vs. the"
    " wrong one), not just rephrasings of the same point.\n\n"
    "Wrap your entire output in <verdict>...</verdict> tags. Inside, list each"
    " angle exactly as:\nANGLE: <short title>\nFOCUS: <one-sentence description>\n"
    "(repeat for each angle proposed, 2-4 total, no other text)."
)

_PLANNER_MANDATORY_ANGLES = (
    "\n\nThe operator has specifically requested these angles be explored — they"
    " MUST all appear among your proposed angles (you may still add others"
    " alongside them):\n{angles}"
)

_PLANNER_AGGREGATOR_SYSTEM = (
    "You are the Managing Editor for a professional LinkedIn article.\n"
    "Several panelists have each independently researched the same topic and"
    " proposed a set of angles from their own findings. Pick the strongest set,"
    " or synthesise the best angles from several proposals into one final set of"
    " 2-4 (or more, if many operator angles were supplied) substantively"
    " distinct angles. If the operator specified mandatory angles, every one of"
    " them MUST appear in your final set.\n"
    "Output a PICK: N line (N = the proposal number you selected as primary),"
    " then the final angle set wrapped in <verdict>...</verdict>, in the same"
    " ANGLE:/FOCUS: format as the proposals. Do not add preamble outside"
    " PICK/verdict."
)

_WRITER_SYSTEM = (
    "You are an editorial panelist writing a professional LinkedIn article.\n"
    "You are given a topic, your own web research findings, and an agreed set of"
    " angles. Write the article: professional, analytical register — no jokes,"
    " no feline metaphors, no dry wit, no satire. Organise it as one section per"
    " agreed angle (a short markdown heading per section), with a brief"
    " introduction before the sections. Target roughly 500-800 words total.\n\n"
    "You may reference facts from your own research findings in your prose, but"
    " you MUST NOT cite, link, or invent any URL or source — a Sources list is"
    " appended separately from verified data; do not write one yourself. If you"
    " had no research findings available, do not present any specific claim as"
    " researched fact — rely only on general knowledge and say so if it matters"
    " to your angle.\n\n"
    "Wrap your entire output in <verdict>...</verdict> tags. Inside, produce four"
    " marked sections, in this exact order, with no text before, between, or"
    " after them other than the markers themselves:\n\n"
    "===TITLE===\n"
    "One punchy, professional article title. No leading # symbol.\n\n"
    "===BODY===\n"
    "The article body: introduction plus one section per agreed angle.\n\n"
    "===COMMENT===\n"
    "One serious, substantive question inviting readers to share their own"
    " experience or view on the topic. One sentence, ending with a question"
    " mark.\n\n"
    "===NOTIFICATION===\n"
    "2-3 sentence LinkedIn network-notification teaser for this article —"
    " serious and compelling, not a joke hook. Minimum 20 characters."
)

_WRITER_AGGREGATOR_SYSTEM = (
    "You are the Managing Editor for a professional LinkedIn article.\n"
    "Several panelists have each independently drafted the same article from"
    " their own research and the same agreed angles. Pick the strongest draft,"
    " or synthesise the best material from several into one final version —"
    " professional register, no jokes, no satire, covering every agreed angle,"
    " targeting roughly 500-800 words.\n"
    "Output a PICK: N line (N = the proposal number you selected as primary),"
    " then the final article wrapped in <verdict>...</verdict>, using the exact"
    " same ===TITLE===/===BODY===/===COMMENT===/===NOTIFICATION=== marker format"
    " as the proposals. Do not add preamble outside PICK/verdict."
)

# Code-inserted, never LLM-authored — guarantees the disclosure is always present
# and always worded consistently (Spec 042 FR-013).
_DISCLOSURE = (
    "*This article was independently researched by three AI models (Claude,"
    " Gemini, and Grok), each performing its own web search, then drafted by the"
    " same panel and synthesized by an editorial AI. No human wrote this"
    " article's text.*"
)

# Static closing block appended after the article body.
_CLOSING_BLOCK = (
    "If this was a useful read, repost to help it reach more people.\n\n"
    "{comment}\n\n"
    "If you have a topic you'd like Gata's panel to research next, send it to"
    " gata.the.reporter@gmail.com.\n\n"
    "Subscribe to the Gata Newsletter here:\n"
    "https://www.linkedin.com/build-relation/newsletter-follow"
    "?entityUrn=7476681937277980672\n\n"
    "And if you want to talk shop, reach Gata at gata.the.reporter@gmail.com."
)

# Static Section body — describes the pipeline itself; unaffected by whether this
# particular article is satirical or researched.
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


def _build_research_query(topic: str, angles: list[str] | None) -> str:
    query = f"Topic: {topic}"
    if angles:
        bullet_list = "\n".join(f"- {a}" for a in angles)
        query += f"\nPay particular attention to these angles:\n{bullet_list}"
    return query


def _extract_gemini_sources(response) -> list[ResearchSource]:
    candidate = response.candidates[0] if response.candidates else None
    metadata = getattr(candidate, "grounding_metadata", None) if candidate else None
    chunks = getattr(metadata, "grounding_chunks", None) or []
    sources: list[ResearchSource] = []
    seen: set[str] = set()
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if web is None or not web.uri or web.uri in seen:
            continue
        seen.add(web.uri)
        sources.append(ResearchSource(title=web.title or web.uri, url=web.uri))
    return sources


def _domain_from_url(url: str) -> str:
    """Clean display domain for a URL — www. stripped, falls back to the raw
    URL itself if it can't be parsed into a usable domain (Spec 043 FR-001).
    """
    netloc = urlparse(url).netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or url


def _fetch_page_title(url: str) -> str | None:
    """Best-effort fetch of a page's real <title>. Returns None on any failure —
    timeout, connection error, non-2xx status, or a missing/empty tag (Spec 043
    FR-002) — never raises. Shared by both Gemini (redirect URLs) and Grok
    (direct URLs) — neither provider gives a usable title on its own.
    """
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=_TITLE_FETCH_TIMEOUT_SECONDS,
            headers=_TITLE_FETCH_HEADERS,
        )
        response.raise_for_status()
    except Exception:
        return None
    match = _TITLE_TAG_RE.search(response.text)
    if not match:
        return None
    title = " ".join(html.unescape(match.group(1)).split())
    return title or None


def _enrich_source_titles_via_fetch(
    sources: list[ResearchSource],
) -> list[ResearchSource]:
    """Rewrite each source's title to "{bare domain} - {page title}" when its
    URL resolves to a page with a real <title> (Spec 043 FR-004, FR-005); any
    source whose fetch fails is returned unchanged (already a bare domain).
    Fetches run in parallel so total added latency stays low regardless of
    source count (FR-003).
    """
    if not sources:
        return sources
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = [executor.submit(_fetch_page_title, source.url) for source in sources]
        enriched: list[ResearchSource] = []
        for source, future in zip(sources, futures):
            try:
                page_title = future.result(timeout=_TITLE_FETCH_TIMEOUT_SECONDS + 2)
            except Exception as exc:
                logger.debug(
                    "linkedin_research: title fetch failed for %s — %s",
                    source.url,
                    exc,
                )
                page_title = None
            if page_title:
                enriched.append(
                    ResearchSource(
                        title=f"{source.title} - {page_title}", url=source.url
                    )
                )
            else:
                enriched.append(source)
    return enriched


def _research_gemini(
    provider: GeminiProvider, query: str
) -> tuple[ResearchDigest | None, TokenUsage | None]:
    try:
        response = provider.client.models.generate_content(
            model=provider.model_id,
            contents=query,
            config=genai_types.GenerateContentConfig(
                system_instruction=_RESEARCH_SYSTEM,
                tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                temperature=0.2,
            ),
        )
    except Exception as exc:
        logger.warning(
            "linkedin_research: gemini (%s) failed — %s", provider.model_id, exc
        )
        return None, None
    summary = (response.text or "").strip()
    if not summary:
        logger.warning(
            "linkedin_research: gemini (%s) returned no text", provider.model_id
        )
        return None, None
    sources = _enrich_source_titles_via_fetch(_extract_gemini_sources(response))
    meta = getattr(response, "usage_metadata", None)
    in_tok = getattr(meta, "prompt_token_count", 0) or 0
    out_tok = getattr(meta, "candidates_token_count", 0) or 0
    usage = TokenUsage(
        model=provider.model_id,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=_gemini_compute_cost(provider.model_id, in_tok, out_tok),
    )
    logger.info(
        "linkedin_research: gemini (%s) succeeded — %d source(s), cost=$%.4f",
        provider.model_id,
        len(sources),
        usage.cost_usd,
    )
    return ResearchDigest(summary=summary, sources=sources), usage


def _extract_claude_sources(response) -> list[ResearchSource]:
    # Anthropic's citation API already gives a real title (unlike Gemini/Grok) —
    # only a domain prefix is added, no fetch needed (Spec 043 FR-006).
    sources: list[ResearchSource] = []
    seen: set[str] = set()
    for block in getattr(response, "content", None) or []:
        citations = getattr(block, "citations", None) or []
        for citation in citations:
            url = getattr(citation, "url", None)
            if not url or url in seen:
                continue
            seen.add(url)
            domain = _domain_from_url(url)
            page_title = getattr(citation, "title", None)
            title = f"{domain} - {page_title}" if page_title else domain
            sources.append(ResearchSource(title=title, url=url))
    return sources


def _research_claude(
    provider: ClaudeProvider, query: str
) -> tuple[ResearchDigest | None, TokenUsage | None]:
    try:
        response = provider.client.messages.create(
            model=provider.model_id,
            max_tokens=1200,
            system=_RESEARCH_SYSTEM,
            messages=[{"role": "user", "content": query}],
            tools=[
                {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
            ],
        )
    except Exception as exc:
        logger.warning(
            "linkedin_research: claude (%s) failed — %s", provider.model_id, exc
        )
        return None, None
    text_blocks = [
        getattr(block, "text", "")
        for block in (response.content or [])
        if getattr(block, "type", "") == "text"
    ]
    summary = "\n".join(t for t in text_blocks if t).strip()
    if not summary:
        logger.warning(
            "linkedin_research: claude (%s) returned no text", provider.model_id
        )
        return None, None
    sources = _extract_claude_sources(response)
    in_tok = getattr(response.usage, "input_tokens", 0) or 0
    out_tok = getattr(response.usage, "output_tokens", 0) or 0
    rates = _CLAUDE_COST_PER_M.get(provider.model_id, (0.0, 0.0))
    cost = (in_tok * rates[0] + out_tok * rates[1]) / 1_000_000
    usage = TokenUsage(
        model=provider.model_id,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=cost,
    )
    logger.info(
        "linkedin_research: claude (%s) succeeded — %d source(s), cost=$%.4f",
        provider.model_id,
        len(sources),
        cost,
    )
    return ResearchDigest(summary=summary, sources=sources), usage


def _extract_grok_sources(response) -> list[ResearchSource]:
    # xAI deprecated Live Search (search_parameters via chat.completions) with an
    # HTTP 410 confirmed live during this feature's own end-to-end test — the
    # current mechanism is the Agent Tools / Responses API's web_search tool,
    # confirmed live to return `AnnotationURLCitation` objects on the final
    # message's content. Its `title` field is the in-text footnote number (e.g.
    # "1"), not a page title — confirmed by inspecting a real response — so the
    # bare domain is used as the pre-fetch baseline title (Spec 043 FR-005),
    # the same starting point Gemini's own API already gives us for free; a
    # real title is then resolved the same way as Gemini's, since Grok's URLs
    # are real, direct destination URLs rather than redirects.
    sources: list[ResearchSource] = []
    seen: set[str] = set()
    for item in getattr(response, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            for annotation in getattr(content, "annotations", None) or []:
                url = getattr(annotation, "url", None)
                if not url or url in seen:
                    continue
                seen.add(url)
                sources.append(ResearchSource(title=_domain_from_url(url), url=url))
    return sources


def _research_grok(
    provider: GrokProvider, query: str
) -> tuple[ResearchDigest | None, TokenUsage | None]:
    try:
        response = provider.client.responses.create(
            model=provider.model_id,
            instructions=_RESEARCH_SYSTEM,
            input=query,
            tools=[{"type": "web_search"}],
        )
    except Exception as exc:
        logger.warning(
            "linkedin_research: grok (%s) failed — %s", provider.model_id, exc
        )
        return None, None
    summary = (getattr(response, "output_text", None) or "").strip()
    if not summary:
        logger.warning(
            "linkedin_research: grok (%s) returned no text", provider.model_id
        )
        return None, None
    sources = _enrich_source_titles_via_fetch(_extract_grok_sources(response))
    usage_obj = getattr(response, "usage", None)
    in_tok = getattr(usage_obj, "input_tokens", 0) or 0
    out_tok = getattr(usage_obj, "output_tokens", 0) or 0
    rates = _GROK_COST_PER_M.get(provider.model_id, (0.0, 0.0))
    cost = (in_tok * rates[0] + out_tok * rates[1]) / 1_000_000
    usage = TokenUsage(
        model=provider.model_id,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=cost,
    )
    logger.info(
        "linkedin_research: grok (%s) succeeded — %d source(s), cost=$%.4f",
        provider.model_id,
        len(sources),
        cost,
    )
    return ResearchDigest(summary=summary, sources=sources), usage


def _research_for_provider(
    provider: LLMProvider, topic: str, angles: list[str] | None
) -> tuple[ResearchDigest | None, TokenUsage | None, float]:
    # Timed here, inside the submitted call itself, so the measured duration is
    # this call's own real wall time — not however long the orchestrator (which
    # collects results from parallel futures in a fixed order, not completion
    # order) happened to take to get around to checking it.
    start = time.monotonic()
    query = _build_research_query(topic, angles)
    if isinstance(provider, GeminiProvider):
        digest, usage = _research_gemini(provider, query)
    elif isinstance(provider, ClaudeProvider):
        digest, usage = _research_claude(provider, query)
    elif isinstance(provider, GrokProvider):
        digest, usage = _research_grok(provider, query)
    else:
        logger.warning(
            "linkedin_research: unrecognised provider type %s — skipping",
            type(provider).__name__,
        )
        digest, usage = None, None
    return digest, usage, time.monotonic() - start


def research_all_panelists(
    panelist_providers: list[list[LLMProvider]],
    topic: str,
    angles: list[str] | None,
) -> tuple[list[ResearchDigest | None], list[AgentTelemetry]]:
    """Run every panelist's own research call in parallel, each bounded by
    _RESEARCH_TIMEOUT_SECONDS (Spec 042 FR-001). A single provider's failure or
    timeout yields None for that slot (FR-005) rather than raising.
    """
    primaries = [slot[0] for slot in panelist_providers]
    digests: list[ResearchDigest | None] = [None] * len(primaries)
    telemetries: list[AgentTelemetry] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(primaries)) as executor:
        futures = [
            executor.submit(_research_for_provider, provider, topic, angles)
            for provider in primaries
        ]
        for i, (provider, future) in enumerate(zip(primaries, futures)):
            try:
                digest, usage, duration = future.result(
                    timeout=_RESEARCH_TIMEOUT_SECONDS
                )
            except concurrent.futures.TimeoutError:
                logger.warning(
                    "linkedin_research: %s exceeded %ss — treating as failed",
                    provider.model_id,
                    _RESEARCH_TIMEOUT_SECONDS,
                )
                digest, usage, duration = None, None, _RESEARCH_TIMEOUT_SECONDS
            digests[i] = digest
            telemetries.append(
                AgentTelemetry(
                    agent_name=f"LinkedIn Research ({provider.model_id})",
                    duration_seconds=duration,
                    iterations=1 if digest is not None else 0,
                    calls=[usage] if usage else [],
                )
            )
    return digests, telemetries


def _panelist_research_context(digest: ResearchDigest | None) -> str:
    if digest is None:
        return (
            "\n\nNo web search results were available to you for this topic. Do"
            " not present any specific claim as researched fact — rely only on"
            " general knowledge, and be explicit in your own text if that"
            " matters to your angle."
        )
    sources_lines = (
        "\n".join(f"- {s.title} ({s.url})" for s in digest.sources)
        or "(no sources returned)"
    )
    return (
        f"\n\nYour own web search findings:\n{digest.summary}\n\n"
        f"Your own sources:\n{sources_lines}"
    )


def _plan_angles(
    topic: str,
    digests: list[ResearchDigest | None],
    angles: list[str] | None,
    panelist_providers: list[list[LLMProvider]],
    aggregator_providers: list[LLMProvider],
) -> tuple[str | None, AgentTelemetry]:
    panelists = [
        PersonaConfig(
            name=slot[0].model_id,
            providers=slot,
            system_prompt=_PLANNER_SYSTEM + _panelist_research_context(digest),
            max_tokens=1200,
        )
        for slot, digest in zip(panelist_providers, digests)
    ]
    aggregator = PersonaConfig(
        name="Managing Editor",
        providers=aggregator_providers,
        system_prompt=_PLANNER_AGGREGATOR_SYSTEM,
        max_tokens=1200,
    )
    panel = FairParallelPanel(
        panelists=panelists, aggregator=aggregator, panel_name="LinkedIn Angle Planning"
    )
    initial_input = f"Topic: {topic}"
    if angles:
        bullet_list = "\n".join(f"- {a}" for a in angles)
        initial_input += _PLANNER_MANDATORY_ANGLES.format(angles=bullet_list)
    fallback_tel = AgentTelemetry(
        agent_name="LinkedIn Angle Planning", duration_seconds=0.0, iterations=0
    )
    try:
        loop_output = panel.run(initial_input)
    except Exception as exc:
        logger.warning("linkedin_angle_planning: panel failed — %s", exc)
        return None, fallback_tel
    telemetry = loop_output.telemetry or fallback_tel
    result = loop_output.verdict.strip()
    if not result:
        logger.warning("linkedin_angle_planning: panel produced an empty angle set")
        return None, telemetry
    return result, telemetry


def _write_article(
    topic: str,
    digests: list[ResearchDigest | None],
    angles: str,
    brief: EnrichedBrief,
    panelist_providers: list[list[LLMProvider]],
    aggregator_providers: list[LLMProvider],
) -> tuple[dict[str, str] | None, AgentTelemetry]:
    panelists = [
        PersonaConfig(
            name=slot[0].model_id,
            providers=slot,
            system_prompt=_WRITER_SYSTEM + _panelist_research_context(digest),
            max_tokens=3000,
        )
        for slot, digest in zip(panelist_providers, digests)
    ]
    aggregator = PersonaConfig(
        name="Managing Editor",
        providers=aggregator_providers,
        system_prompt=_WRITER_AGGREGATOR_SYSTEM,
        max_tokens=3000,
    )
    panel = FairParallelPanel(
        panelists=panelists,
        aggregator=aggregator,
        panel_name="LinkedIn Article Writing",
        panelist_timeout=_WRITING_PANEL_TIMEOUT_SECONDS,
    )
    initial_input = (
        f"Topic: {topic}\nOutput language: {brief.output_language}\n\n"
        f"Agreed angles:\n{angles}"
    )
    fallback_tel = AgentTelemetry(
        agent_name="LinkedIn Article Writing", duration_seconds=0.0, iterations=0
    )
    try:
        loop_output = panel.run(initial_input)
    except Exception as exc:
        logger.warning("linkedin_writing: panel failed — %s", exc)
        return None, fallback_tel
    telemetry = loop_output.telemetry or fallback_tel
    sections = _parse_sections(loop_output.verdict)
    if not sections:
        logger.warning("linkedin_writing: response contained no recognised markers")
        return None, telemetry
    return sections, telemetry


def _parse_sections(raw: str) -> dict[str, str]:
    # Split on section markers; each marker starts a new keyed block.
    markers = ["===TITLE===", "===BODY===", "===COMMENT===", "===NOTIFICATION==="]
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


def _merge_sources(digests: list[ResearchDigest | None]) -> list[ResearchSource]:
    # Deduplicated union across every panelist's own real sources (Spec 042
    # FR-011) — the only path published sources ever come from.
    merged: list[ResearchSource] = []
    seen: set[str] = set()
    for digest in digests:
        if digest is None:
            continue
        for source in digest.sources:
            if source.url in seen:
                continue
            seen.add(source.url)
            merged.append(source)
    return merged


def _build_sources_section(sources: list[ResearchSource]) -> str:
    if not sources:
        return ""
    lines = ["## Sources", ""]
    lines.extend(f"- [{source.title}]({source.url})" for source in sources)
    return "\n".join(lines)


def _assemble_article(
    sections: dict[str, str], sources: list[ResearchSource], telemetry: RunTelemetry
) -> str:
    title = sections.get("TITLE", "Gata's Panel Weighs In")
    body = sections.get("BODY", "")
    comment = sections.get("COMMENT", "")
    # Section 1: article title as H1.
    s1 = f"# {title}"
    # Section 2: telemetry caption from real run metrics — no LLM involvement.
    duration = telemetry.total_duration_seconds
    cost = telemetry.total_cost_usd
    s2 = (
        f"*Pipeline Execution Metrics - Total Time: {duration:.1f}s"
        f" | Total Cost: ${cost:.4f}*"
    )
    # Section 3: mandatory disclosure + article body + static closing block.
    disclosed_body = f"{_DISCLOSURE}\n\n{body}".strip()
    closing = _CLOSING_BLOCK.format(comment=comment) if comment else ""
    s3 = f"{disclosed_body}\n\n{closing}".strip() if closing else disclosed_body
    # Section 4 (optional): code-built Sources list, omitted entirely when empty.
    sources_section = _build_sources_section(sources)
    # Section 5: static tech-stack body, unaffected by this article's tone.
    s5 = _SECTION_4_BODY.rstrip()
    parts = [s1, s2, s3]
    if sources_section:
        parts.append(sources_section)
    parts.append(s5)
    return "\n\n".join(parts)


def generate_linkedin_post(
    brief: EnrichedBrief,
    topic: str,
    telemetry: RunTelemetry,
    panelist_providers: list[list[LLMProvider]],
    aggregator_providers: list[LLMProvider],
    angles: list[str] | None = None,
) -> tuple[str, str]:
    """Generate the researched LinkedIn article markdown and notification text.

    Returns (article_md, notification_txt). Never raises — a total failure at
    the research, angle-planning, or writing stage returns empty strings so the
    caller can skip writing files (FR-008); every stage still appends its own
    AgentTelemetry entry (or entries) to `telemetry` before returning.
    """
    clean_angles = [a.strip() for a in (angles or []) if a and a.strip()] or None

    digests, research_tels = research_all_panelists(
        panelist_providers, topic, clean_angles
    )
    telemetry.agents.extend(research_tels)
    if all(digest is None for digest in digests):
        logger.warning("linkedin_post: every provider's research failed — no article")
        return "", ""

    angle_text, planning_tel = _plan_angles(
        topic, digests, clean_angles, panelist_providers, aggregator_providers
    )
    telemetry.agents.append(planning_tel)
    if angle_text is None:
        return "", ""

    sections, writing_tel = _write_article(
        topic, digests, angle_text, brief, panelist_providers, aggregator_providers
    )
    telemetry.agents.append(writing_tel)
    if sections is None:
        return "", ""

    merged_sources = _merge_sources(digests)
    article_md = _assemble_article(sections, merged_sources, telemetry)
    notification_txt = sections.get("NOTIFICATION", "")
    return article_md, notification_txt
