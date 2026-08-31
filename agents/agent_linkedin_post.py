import concurrent.futures
import html
import json
import logging
import re
import time
from urllib.parse import urlparse

import duckdb
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

# Domain classification panel (Spec 042 amendment 2): a full FairParallelPanel
# deliberation, not a single model call, per the operator's explicit request
# for cross-checked judgment. iterations=3 (one more than the class default)
# since early runs with a small/empty cache are expected to disagree more
# before converging.
_DOMAIN_CLASSIFICATION_TIMEOUT_SECONDS = 90.0
_DOMAIN_CLASSIFICATION_ITERATIONS = 3

# Local, gitignored, regenerating cache — not a hand-edited config (Spec 042
# amendment 2 FR-025). A domain already present is trusted indefinitely.
_DOMAIN_CACHE_PATH = "source_domains.duckdb"

# Citation enforcement (Spec 042 amendment 2 FR-027/FR-029/FR-030): a
# mid-round nudge targets ~2 citations per body section; the hard code-level
# backstop caps the final published article at 15 distinct citations total.
_MAX_CITATIONS_PER_SECTION = 2
_MAX_TOTAL_CITATIONS = 15
_CITATION_RE = re.compile(r" ?\[(\d+)\]")

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

# Spec 044: matches any <meta ...> tag so its attributes can be inspected
# regardless of order (og:title/twitter:title put `content` before or after
# `property`/`name` depending on the site).
_META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_META_ATTR_RE = re.compile(r"""([a-zA-Z0-9:_-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")

# Spec 044 FR-002: a candidate title is non-descriptive once it normalises to
# nothing beyond the source's own domain label (e.g. "Reddit" for
# reddit.com) — only alphanumerics are compared, case-insensitively.
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Spec 044 FR-003/FR-004: a URL-path segment needs at least this many real
# (2+ letter) words to count as a descriptive slug — pinned here per the
# spec's Assumptions (the spec's acceptance criteria are the contract, not
# this literal value).
_MIN_SLUG_WORDS = 3
_SLUG_WORD_RE = re.compile(r"[A-Za-z]{2,}")

# Spec 044 FR-007: every research call is asked to append a title for each
# URL it cites after this marker, in its own same-call response — no second
# call. FR-010: everything from this marker onward is stripped from the
# stored digest summary.
_SOURCE_TITLES_MARKER = "===SOURCE_TITLES==="

_RESEARCH_SYSTEM = (
    "You are a research assistant preparing background for a professional"
    " article. Use web search to find current, factual, credible information"
    " about the given topic. Summarise your findings in clear, neutral prose (2-4"
    " paragraphs) — report what the sources say, do not editorialise or joke."
    "\n\nAfter your findings, on their own line, write the exact marker"
    f" {_SOURCE_TITLES_MARKER} followed by one line per URL you cited above,"
    " each formatted exactly as:\n<url> | <short descriptive title of that"
    " specific page, 6-14 words, based on what you actually found there —"
    " never just the site's own name>"
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
    " no feline metaphors, no dry wit, no satire. Organise the body as one"
    " section per agreed angle (a short markdown heading per section) — the"
    " introduction is its own separate section (see ===EXECUTIVE_SUMMARY==="
    " below), not part of the body. Target roughly 500-800 words total across"
    " the summary and body combined.\n\n"
    "You may reference facts from your own research findings in your prose. You"
    " will also be given a numbered list of sources you may cite — when a"
    " specific claim comes from one of them, cite it inline immediately as"
    " [N] matching its number in that list. Never invent a number not in the"
    " list, never write a URL yourself, and never fabricate a source outside"
    " it — a Sources list is appended separately, built only from your cited"
    " numbers; do not write one yourself. Aim for roughly 2 citations per body"
    " section; do not exceed 15 distinct citations in the whole article. If"
    " you had no research findings available, do not present any specific"
    " claim as researched fact — rely only on general knowledge and say so if"
    " that matters to your angle.\n\n"
    "Wrap your entire output in <verdict>...</verdict> tags. Inside, produce five"
    " marked sections, in this exact order, with no text before, between, or"
    " after them other than the markers themselves:\n\n"
    "===TITLE===\n"
    "One punchy, professional article title. No leading # symbol.\n\n"
    "===EXECUTIVE_SUMMARY===\n"
    "A 3-5 sentence summary of the article's core finding or argument, for a"
    " reader who won't read further. No heading — just the paragraph.\n\n"
    "===BODY===\n"
    "The article body: one section per agreed angle, no separate introduction.\n\n"
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
    " same ===TITLE===/===EXECUTIVE_SUMMARY===/===BODY===/===COMMENT===/"
    "===NOTIFICATION=== marker format as the proposals. Do not add preamble"
    " outside PICK/verdict."
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
    # Best-effort steer toward citable domains (Spec 042 amendment 2 FR-024) —
    # the actual enforcement is the post-research classification/filter step,
    # not this instruction alone.
    query += (
        "\nWhen searching, prefer academic, government, or otherwise"
        " highly-reputable and established sources over minor outlets, blogs,"
        " or content farms."
    )
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


# Gemini's own grounding-redirect host (Spec 043) — its path is an opaque
# tracking token, never real page content. Confirmed live (Spec 044): when a
# fetch through this host fails before any redirect resolves, slug
# humanisation would otherwise run on that opaque token and publish
# base64-noise as a "title" — _resolve_sources skips the slug step in
# exactly that situation (see _is_unresolved_redirect_wrapper).
_GROUNDING_REDIRECT_HOST = "vertexaisearch.cloud.google.com"


def _is_unresolved_redirect_wrapper(original_url: str, slug_url: str) -> bool:
    return slug_url == original_url and _domain_from_url(original_url) == (
        _GROUNDING_REDIRECT_HOST
    )


def _extract_title_tag(html_text: str) -> str | None:
    match = _TITLE_TAG_RE.search(html_text)
    if not match:
        return None
    title = " ".join(html.unescape(match.group(1)).split())
    return title or None


def _extract_meta_content(
    html_text: str, attr_name: str, attr_value: str
) -> str | None:
    """Finds a <meta {attr_name}="{attr_value}" content="..."> tag regardless
    of attribute order (Spec 044 FR-001 — og:title/twitter:title) and returns
    its cleaned content, or None if the tag or its content is absent.
    """
    for tag in _META_TAG_RE.findall(html_text):
        attrs: dict[str, str] = {}
        for match in _META_ATTR_RE.finditer(tag):
            key = match.group(1).lower()
            attrs[key] = (
                match.group(2) if match.group(2) is not None else match.group(3)
            )
        if attrs.get(attr_name, "").lower() != attr_value:
            continue
        content = attrs.get("content")
        if content is None:
            continue
        cleaned = " ".join(html.unescape(content).split())
        return cleaned or None
    return None


def _fetch_page_title(url: str) -> tuple[str | None, str]:
    """Best-effort fetch of a page's real title, trying <title>, then
    og:title, then twitter:title (Spec 044 FR-001), plus the final resolved
    URL after redirects. The resolved URL is captured even when the
    destination request itself then fails (Spec 044 FR-014) — a 403 after a
    successful redirect must not fall back to the original redirect-wrapper
    URL for slug humanisation. Returns (None, url) on any failure — timeout,
    connection error, no usable tag/meta anywhere — never raises.
    """
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=_TITLE_FETCH_TIMEOUT_SECONDS,
            headers=_TITLE_FETCH_HEADERS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return None, str(exc.response.url)
    except Exception:
        return None, url
    text = response.text
    title = (
        _extract_title_tag(text)
        or _extract_meta_content(text, "property", "og:title")
        or _extract_meta_content(text, "name", "twitter:title")
    )
    return title, str(response.url)


def _normalize_for_comparison(text: str) -> str:
    return _NON_ALNUM_RE.sub("", text.lower())


def _is_descriptive_title(title: str | None, domain: str) -> bool:
    """Spec 044 FR-002: a candidate title is non-descriptive when, once
    normalised (case-folded, punctuation/whitespace stripped), it is empty,
    or it equals either the source's own domain label (e.g. "Reddit" for
    reddit.com) or the full domain restated (e.g. "reddit.com" itself — the
    raw seed title Gemini/Grok extraction starts every source from).
    Containing that label within a longer, real title is not disqualifying,
    only being *only* the label or the domain is.
    """
    if not title:
        return False
    normalized_title = _normalize_for_comparison(title)
    if not normalized_title:
        return False
    label = domain.split(".")[0] if domain else domain
    non_descriptive = {
        _normalize_for_comparison(label),
        _normalize_for_comparison(domain),
    }
    return normalized_title not in non_descriptive


def _humanize_slug(url: str) -> str | None:
    """Spec 044 FR-003/FR-004: derives a title from the most specific
    hyphen/underscore-delimited URL-path segment with at least
    _MIN_SLUG_WORDS real (2+ letter) words, converting separators to spaces
    and dropping purely-numeric tokens (e.g. a trailing ID). Segments below
    the threshold — purely numeric/hex-like IDs included — are skipped in
    favour of an earlier, more descriptive segment. Returns None when no
    path segment qualifies.
    """
    path = urlparse(url).path
    segments = [seg for seg in path.split("/") if seg]
    for segment in reversed(segments):
        words = [w for w in re.split(r"[-_]+", segment) if w]
        real_words = [w for w in words if _SLUG_WORD_RE.search(w)]
        if len(real_words) < _MIN_SLUG_WORDS:
            continue
        prose = " ".join(w for w in words if not w.isdigit())
        if prose:
            return prose[0].upper() + prose[1:]
    return None


def _split_source_titles_block(text: str) -> tuple[str, dict[str, str]]:
    """Splits a provider's raw response into (summary_without_block,
    url_to_title) — everything from _SOURCE_TITLES_MARKER onward is the
    appended block (Spec 044 FR-007/FR-010) and is never part of the stored
    summary. A missing or malformed block yields an empty mapping and the
    summary is simply the whole (stripped) text — never raises.
    """
    idx = text.find(_SOURCE_TITLES_MARKER)
    if idx == -1:
        return text.strip(), {}
    summary = text[:idx].strip()
    block = text[idx + len(_SOURCE_TITLES_MARKER) :]
    titles: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        url, _, title = line.partition("|")
        url = url.strip()
        title = title.strip()
        if url and title:
            titles[url] = title
    return summary, titles


def _resolve_sources(
    candidates: list[tuple[str, str, str]],
    provider_titles: dict[str, str],
    *,
    do_fetch: bool,
) -> list[ResearchSource]:
    """Resolves every (raw_title, url, domain) candidate's published title
    through the Spec 044 chain: its own raw candidate title, then (if
    do_fetch) a live fetch's <title>/og:title/twitter:title, then a
    humanised URL-path slug, then a title the source's own provider supplied
    in the same research call — dropping any source for which nothing along
    that chain is descriptive (FR-011), logged at DEBUG (FR-012), never
    raising. Live fetches run in parallel so total added latency stays low
    regardless of source count (unchanged from Spec 043 FR-003).
    """
    if not candidates:
        return []
    fetch_results: dict[str, tuple[str | None, str]] = {}
    if do_fetch:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(candidates)
        ) as executor:
            futures = {
                url: executor.submit(_fetch_page_title, url) for _, url, _ in candidates
            }
            for url, future in futures.items():
                try:
                    fetch_results[url] = future.result(
                        timeout=_TITLE_FETCH_TIMEOUT_SECONDS + 2
                    )
                except Exception as exc:
                    logger.debug(
                        "linkedin_research: title fetch failed for %s — %s", url, exc
                    )
                    fetch_results[url] = (None, url)
    resolved: list[ResearchSource] = []
    for raw_title, url, domain in candidates:
        # Step 1: the candidate's own raw title (Claude's real citation title,
        # or a provider's bare-domain seed which never passes this check).
        if _is_descriptive_title(raw_title, domain):
            resolved.append(ResearchSource(title=f"{domain} - {raw_title}", url=url))
            continue
        # Step 2: a live fetch's <title>/og:title/twitter:title, if this
        # provider gets one (Claude already has a real citation title, so it
        # never fetches — Spec 043 FR-006).
        slug_url = url
        if do_fetch:
            fetched_title, slug_url = fetch_results.get(url, (None, url))
            if _is_descriptive_title(fetched_title, domain):
                resolved.append(
                    ResearchSource(title=f"{domain} - {fetched_title}", url=url)
                )
                continue
        # Step 3: a humanised URL-path slug, on the fetch-resolved
        # destination URL when one was reached (FR-014), else the original —
        # skipped entirely when neither happened and the URL is still
        # Gemini's own opaque redirect-wrapper path (never real content).
        slug_title = (
            None
            if _is_unresolved_redirect_wrapper(url, slug_url)
            else _humanize_slug(slug_url)
        )
        if _is_descriptive_title(slug_title, domain):
            resolved.append(ResearchSource(title=f"{domain} - {slug_title}", url=url))
            continue
        # Step 4: the source's own originating provider's same-call title,
        # matched strictly by URL (FR-008) — never introduces a new source.
        provider_title = provider_titles.get(url)
        if _is_descriptive_title(provider_title, domain):
            resolved.append(
                ResearchSource(title=f"{domain} - {provider_title}", url=url)
            )
            continue
        # Step 5: nothing descriptive anywhere — drop the source (FR-011).
        logger.debug(
            "linkedin_research: dropping source with no descriptive title — %s", url
        )
    return resolved


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
    raw_text = (response.text or "").strip()
    summary, provider_titles = _split_source_titles_block(raw_text)
    if not summary:
        logger.warning(
            "linkedin_research: gemini (%s) returned no text", provider.model_id
        )
        return None, None
    raw_sources = _extract_gemini_sources(response)
    candidates = [
        (s.title, s.url, s.title or _domain_from_url(s.url)) for s in raw_sources
    ]
    sources = _resolve_sources(candidates, provider_titles, do_fetch=True)
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
    # Anthropic's citation API already gives a real title (unlike Gemini/Grok)
    # — the raw title is returned as-is, un-prefixed; the shared resolver
    # (Spec 044 _resolve_sources) applies the domain prefix and the
    # non-descriptive check uniformly across all three providers.
    sources: list[ResearchSource] = []
    seen: set[str] = set()
    for block in getattr(response, "content", None) or []:
        citations = getattr(block, "citations", None) or []
        for citation in citations:
            url = getattr(citation, "url", None)
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(
                ResearchSource(title=getattr(citation, "title", None) or "", url=url)
            )
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
    raw_text = "\n".join(t for t in text_blocks if t).strip()
    summary, provider_titles = _split_source_titles_block(raw_text)
    if not summary:
        logger.warning(
            "linkedin_research: claude (%s) returned no text", provider.model_id
        )
        return None, None
    raw_sources = _extract_claude_sources(response)
    candidates = [(s.title, s.url, _domain_from_url(s.url)) for s in raw_sources]
    # Claude never fetches (do_fetch=False) — its citation title is already
    # real when present (Spec 043 FR-006); the resolver still walks the rest
    # of the chain (slug, provider-supplied title) when it isn't.
    sources = _resolve_sources(candidates, provider_titles, do_fetch=False)
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
    raw_text = (getattr(response, "output_text", None) or "").strip()
    summary, provider_titles = _split_source_titles_block(raw_text)
    if not summary:
        logger.warning(
            "linkedin_research: grok (%s) returned no text", provider.model_id
        )
        return None, None
    raw_sources = _extract_grok_sources(response)
    candidates = [(s.title, s.url, _domain_from_url(s.url)) for s in raw_sources]
    sources = _resolve_sources(candidates, provider_titles, do_fetch=True)
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


def _open_domain_cache() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(_DOMAIN_CACHE_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS domains ("
        "domain TEXT PRIMARY KEY, paywalled BOOLEAN, reliability TEXT,"
        " classified_at TIMESTAMP)"
    )
    return con


def _load_cached_domains(domains: set[str]) -> dict[str, dict]:
    """Domains already classified — trusted indefinitely (Spec 042 amendment 2
    FR-025); an empty result for any domain not yet seen, never an error.
    """
    if not domains:
        return {}
    con = _open_domain_cache()
    try:
        placeholders = ",".join("?" for _ in domains)
        rows = con.execute(
            f"SELECT domain, paywalled, reliability FROM domains"
            f" WHERE domain IN ({placeholders})",
            list(domains),
        ).fetchall()
    finally:
        con.close()
    return {
        domain: {"paywalled": bool(paywalled), "reliability": reliability}
        for domain, paywalled, reliability in rows
    }


def _save_classified_domains(classifications: dict[str, dict]) -> None:
    if not classifications:
        return
    con = _open_domain_cache()
    try:
        for domain, verdict in classifications.items():
            con.execute(
                "INSERT OR REPLACE INTO domains (domain, paywalled, reliability,"
                " classified_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                [domain, verdict["paywalled"], verdict["reliability"]],
            )
    finally:
        con.close()


_DOMAIN_CLASSIFIER_SYSTEM = (
    "You are assessing web domains for use as citations in a professional,"
    " researched LinkedIn article.\n"
    "For each domain listed, judge: (1) is it typically paywalled for readers"
    " (a paid subscription is required to read full articles)? (2) is it a"
    " highly reliable source — academic, government, or a well-established,"
    " editorially rigorous outlet — versus a minor/low-quality outlet, blog,"
    " or content farm?\n"
    "Wrap your entire output in <verdict>...</verdict> tags containing ONLY a"
    " JSON object, no other text, mapping each domain to its verdict, e.g.:\n"
    '{"nytimes.com": {"paywalled": true, "reliability": "high"},'
    ' "some-blog.com": {"paywalled": false, "reliability": "low"}}\n'
    'reliability must be exactly "high" or "low". Include every domain you'
    " were given, and no others."
)

_DOMAIN_CLASSIFIER_AGGREGATOR_SYSTEM = (
    "You are the Managing Editor reconciling several panelists' domain"
    " classifications.\n"
    "Synthesise the most accurate final verdict per domain (majority view, or"
    " your own best judgment on disagreement).\n"
    "Output a PICK: N line (N = the proposal number you selected as primary),"
    " then the final JSON wrapped in <verdict>...</verdict>, using the exact"
    " same format as the proposals. Do not add preamble outside PICK/verdict."
)


def _classify_domains_panel(
    domains: list[str],
    panelist_providers: list[list[LLMProvider]],
    aggregator_providers: list[LLMProvider],
) -> tuple[dict[str, dict], AgentTelemetry]:
    """Classify each domain's paywall/reliability status via a FairParallelPanel
    deliberation (Spec 042 amendment 2 FR-026.2) — a panel decision, not a
    single model's call, since this is a judgment call worth cross-checking.
    Fails open: returns ({}, telemetry) on total panel failure or unparseable
    output, so callers treat every domain as unclassified rather than aborting
    the run — the telemetry (and its real cost) is still returned either way,
    so this panel's spend is never silently missing from the run's totals.
    """
    fallback_tel = AgentTelemetry(
        agent_name="Domain Classification", duration_seconds=0.0, iterations=0
    )
    if not domains:
        return {}, fallback_tel
    panelists = [
        PersonaConfig(
            name=slot[0].model_id,
            providers=slot,
            system_prompt=_DOMAIN_CLASSIFIER_SYSTEM,
            max_tokens=1000,
        )
        for slot in panelist_providers
    ]
    aggregator = PersonaConfig(
        name="Source Classifier",
        providers=aggregator_providers,
        system_prompt=_DOMAIN_CLASSIFIER_AGGREGATOR_SYSTEM,
        max_tokens=1000,
    )
    panel = FairParallelPanel(
        panelists=panelists,
        aggregator=aggregator,
        panel_name="Domain Classification",
        iterations=_DOMAIN_CLASSIFICATION_ITERATIONS,
        panelist_timeout=_DOMAIN_CLASSIFICATION_TIMEOUT_SECONDS,
    )
    domain_list = "\n".join(f"- {d}" for d in domains)
    try:
        loop_output = panel.run(f"Domains to classify:\n{domain_list}")
    except Exception as exc:
        logger.warning("source_classification: panel failed — %s", exc)
        return {}, fallback_tel
    telemetry = loop_output.telemetry or fallback_tel
    raw = loop_output.verdict.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("source_classification: panel returned invalid JSON")
        return {}, telemetry
    if not isinstance(parsed, dict):
        logger.warning("source_classification: panel JSON was not an object")
        return {}, telemetry
    result: dict[str, dict] = {}
    for domain, verdict in parsed.items():
        if not isinstance(verdict, dict):
            continue
        reliability = str(verdict.get("reliability", "")).lower()
        if reliability not in ("high", "low"):
            continue
        result[domain] = {
            "paywalled": bool(verdict.get("paywalled", False)),
            "reliability": reliability,
        }
    return result, telemetry


def research_all_panelists(
    panelist_providers: list[list[LLMProvider]],
    topic: str,
    angles: list[str] | None,
    aggregator_providers: list[LLMProvider],
) -> tuple[list[ResearchDigest | None], list[AgentTelemetry]]:
    """Run every panelist's own research call in parallel, each bounded by
    _RESEARCH_TIMEOUT_SECONDS (Spec 042 FR-001). A single provider's failure or
    timeout yields None for that slot (FR-005) rather than raising. Before
    returning, classifies and filters out any paywalled/low-reliability
    domain from every digest (Spec 042 amendment 2 FR-026) — the earliest
    point this pipeline can act, since each provider's own search tool is a
    server-side black box we can't gate before its own fetch.
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
    # Every research call is in; classify and filter before anyone downstream
    # (angle-planning, writing) ever sees a bad domain's sources.
    all_domains = {
        _domain_from_url(source.url)
        for digest in digests
        if digest is not None
        for source in digest.sources
    }
    cache = _load_cached_domains(all_domains)
    unclassified = sorted(all_domains - cache.keys())
    if unclassified:
        new_verdicts, classification_tel = _classify_domains_panel(
            unclassified, panelist_providers, aggregator_providers
        )
        telemetries.append(classification_tel)
        _save_classified_domains(new_verdicts)
        cache.update(new_verdicts)
    for digest in digests:
        if digest is None:
            continue
        kept: list[ResearchSource] = []
        for source in digest.sources:
            domain = _domain_from_url(source.url)
            verdict = cache.get(domain)
            if verdict is not None and (
                verdict["paywalled"] or verdict["reliability"] == "low"
            ):
                logger.warning(
                    "source_classification: excluding %s (%s) —"
                    " paywalled=%s reliability=%s",
                    source.url,
                    domain,
                    verdict["paywalled"],
                    verdict["reliability"],
                )
                continue
            kept.append(source)
        digest.sources = kept
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
            max_tokens=2500,
        )
        for slot, digest in zip(panelist_providers, digests)
    ]
    aggregator = PersonaConfig(
        name="Managing Editor",
        providers=aggregator_providers,
        system_prompt=_PLANNER_AGGREGATOR_SYSTEM,
        max_tokens=2500,
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


def _build_citable_sources_block(candidates: list[ResearchSource]) -> str:
    if not candidates:
        return ""
    lines = [
        "\n\nSOURCES YOU MAY CITE (cite inline as [N] against this exact"
        " numbering; never invent a number not listed; do not fabricate a"
        " source outside it):",
        "",
    ]
    lines.extend(
        f"[{i}] {source.title} ({source.url})" for i, source in enumerate(candidates, 1)
    )
    return "\n".join(lines)


def _count_citations_per_section(text: str) -> list[int]:
    """Splits on markdown H2 headings; returns a citation count per resulting
    chunk (the text before the first heading counts as its own chunk).
    """
    sections = re.split(r"(?m)^##\s+.*$", text)
    return [len(_CITATION_RE.findall(section)) for section in sections]


def _citation_round_validator(verdicts: dict[str, str]) -> dict[str, str]:
    """FairParallelPanel round_validator (Spec 042 amendment 2 FR-028): flags
    any panelist whose BODY has a section citing more than
    _MAX_CITATIONS_PER_SECTION sources, so it gets a chance to trim before the
    next round. Best-effort only — _extract_and_renumber_citations is the
    actual hard backstop regardless of whether a panelist complies.
    """
    feedback: dict[str, str] = {}
    for name, raw_verdict in verdicts.items():
        body = _parse_sections(raw_verdict).get("BODY", "")
        if any(
            count > _MAX_CITATIONS_PER_SECTION
            for count in _count_citations_per_section(body)
        ):
            feedback[name] = (
                "VALIDATION WARNING: one or more of your body sections cites"
                f" more than {_MAX_CITATIONS_PER_SECTION} sources. Please"
                f" revise so each section cites at most"
                f" {_MAX_CITATIONS_PER_SECTION} sources."
            )
    return feedback


def _rewrite_citations(text: str, renumber_map: dict[int, int]) -> str:
    def _sub(match: re.Match) -> str:
        old_index = int(match.group(1))
        new_index = renumber_map.get(old_index)
        if new_index is None:
            return ""
        prefix = " " if match.group(0).startswith(" ") else ""
        return f"{prefix}[{new_index}]"

    return _CITATION_RE.sub(_sub, text)


def _extract_and_renumber_citations(
    summary: str, body: str, candidates: list[ResearchSource]
) -> tuple[str, str, list[ResearchSource]]:
    """Spec 042 amendment 2 FR-029: determines which candidates were actually
    cited (first-appearance order across summary+body), drops invalid/out-of-
    range indices, caps at _MAX_TOTAL_CITATIONS distinct sources, renumbers
    the survivors sequentially, and rewrites every [N] marker to match.
    """
    combined = summary + "\n\n" + body
    order: list[int] = []
    for match in _CITATION_RE.finditer(combined):
        old_index = int(match.group(1))
        if 1 <= old_index <= len(candidates) and old_index not in order:
            order.append(old_index)
    kept = order[:_MAX_TOTAL_CITATIONS]
    renumber_map = {old: new for new, old in enumerate(kept, 1)}
    new_summary = _rewrite_citations(summary, renumber_map)
    new_body = _rewrite_citations(body, renumber_map)
    final_sources = [candidates[old_index - 1] for old_index in kept]
    return new_summary, new_body, final_sources


def _write_article(
    topic: str,
    digests: list[ResearchDigest | None],
    angles: str,
    brief: EnrichedBrief,
    panelist_providers: list[list[LLMProvider]],
    aggregator_providers: list[LLMProvider],
    candidates: list[ResearchSource],
) -> tuple[dict[str, str] | None, AgentTelemetry]:
    citable_block = _build_citable_sources_block(candidates)
    panelists = [
        PersonaConfig(
            name=slot[0].model_id,
            providers=slot,
            system_prompt=(
                _WRITER_SYSTEM + _panelist_research_context(digest) + citable_block
            ),
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
        round_validator=_citation_round_validator,
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
    markers = [
        "===TITLE===",
        "===EXECUTIVE_SUMMARY===",
        "===BODY===",
        "===COMMENT===",
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


def _merge_sources(digests: list[ResearchDigest | None]) -> list[ResearchSource]:
    # Deduplicated union across every panelist's own real, already-filtered
    # sources (Spec 042 FR-011; paywalled/low-reliability domains already
    # removed by research_all_panelists, amendment 2 FR-026) — the only path
    # citable candidates ever come from.
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
    lines.extend(
        f"{i}. [{source.title}]({source.url})" for i, source in enumerate(sources, 1)
    )
    return "\n".join(lines)


def _assemble_report(
    sections: dict[str, str],
    sources: list[ResearchSource],
    telemetry: RunTelemetry,
    topic: str,
) -> str:
    """Neutral, unbranded assembly for research_only mode (Spec 046 FR-005).

    Same section data as _assemble_article, but the title falls back to a
    neutral default and the Gata-specific closing block / tech-stack promo
    (_CLOSING_BLOCK, _SECTION_4_BODY) are omitted entirely — only the factual
    Pipeline Metrics line and AI-authorship disclosure remain.
    """
    title = sections.get("TITLE", "").strip() or f"Research Report: {topic}"
    summary = sections.get("EXECUTIVE_SUMMARY", "").strip()
    body = sections.get("BODY", "")
    s1 = f"# {title}"
    summary_section = f"## Executive Summary\n\n{summary}" if summary else ""
    sources_section = _build_sources_section(sources)
    duration = telemetry.total_duration_seconds
    cost = telemetry.total_cost_usd
    metrics_line = (
        f"*Pipeline Execution Metrics - Total Time: {duration:.1f}s"
        f" | Total Cost: ${cost:.4f}*"
    )
    parts = [s1]
    if summary_section:
        parts.append(summary_section)
    if body.strip():
        parts.append(body.strip())
    if sources_section:
        parts.append(sources_section)
    parts.append(f"{metrics_line}\n\n{_DISCLOSURE}")
    return "\n\n".join(parts)


def _assemble_article(
    sections: dict[str, str], sources: list[ResearchSource], telemetry: RunTelemetry
) -> str:
    title = sections.get("TITLE", "Gata's Panel Weighs In")
    summary = sections.get("EXECUTIVE_SUMMARY", "").strip()
    body = sections.get("BODY", "")
    comment = sections.get("COMMENT", "")
    # Title as H1.
    s1 = f"# {title}"
    # Executive Summary, code-inserted heading around the writer panel's own
    # summary text — omitted entirely when absent so nothing blank is published.
    summary_section = f"## Executive Summary\n\n{summary}" if summary else ""
    # Article body + static closing block (no disclosure/metrics prepended here
    # anymore — both moved to the bottom, inside Behind the Scenes, below).
    closing = _CLOSING_BLOCK.format(comment=comment) if comment else ""
    s3 = f"{body}\n\n{closing}".strip() if closing else body.strip()
    # Sources (optional): code-built list, omitted entirely when empty.
    sources_section = _build_sources_section(sources)
    # Behind the Scenes: static tech-stack body, plus the telemetry caption (real
    # run metrics, no LLM involvement) and the mandatory disclosure, both moved
    # here from the top so they read as closing/meta information, not a lead-in.
    duration = telemetry.total_duration_seconds
    cost = telemetry.total_cost_usd
    metrics_line = (
        f"*Pipeline Execution Metrics - Total Time: {duration:.1f}s"
        f" | Total Cost: ${cost:.4f}*"
    )
    s5 = f"{_SECTION_4_BODY.rstrip()}\n\n{metrics_line}\n\n{_DISCLOSURE}"
    parts = [s1]
    if summary_section:
        parts.append(summary_section)
    if s3:
        parts.append(s3)
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
    branded: bool = True,
) -> tuple[str, str]:
    """Generate the researched article markdown and notification text.

    Returns (article_md, notification_txt). Never raises — a total failure at
    the research, angle-planning, or writing stage returns empty strings so the
    caller can skip writing files (FR-008); every stage still appends its own
    AgentTelemetry entry (or entries) to `telemetry` before returning.

    `branded` (Spec 046) controls only the final assembly step: `True` (the
    default, unchanged behaviour) produces today's Gata-branded article via
    `_assemble_article`; `False` produces a neutral, unbranded report via
    `_assemble_report` — every stage before assembly is identical either way.
    """
    clean_angles = [a.strip() for a in (angles or []) if a and a.strip()] or None

    digests, research_tels = research_all_panelists(
        panelist_providers, topic, clean_angles, aggregator_providers
    )
    telemetry.agents.extend(research_tels)
    if all(digest is None for digest in digests):
        logger.warning("linkedin_post: every provider's research failed — no article")
        return "", ""

    # Merged here (not after writing, as before Spec 042 amendment 2) — the
    # writing panel needs a stable, numbered candidate list to cite from.
    # Filtering already happened inside research_all_panelists.
    candidates = _merge_sources(digests)

    angle_text, planning_tel = _plan_angles(
        topic, digests, clean_angles, panelist_providers, aggregator_providers
    )
    telemetry.agents.append(planning_tel)
    if angle_text is None:
        return "", ""

    sections, writing_tel = _write_article(
        topic,
        digests,
        angle_text,
        brief,
        panelist_providers,
        aggregator_providers,
        candidates,
    )
    telemetry.agents.append(writing_tel)
    if sections is None:
        return "", ""

    new_summary, new_body, final_sources = _extract_and_renumber_citations(
        sections.get("EXECUTIVE_SUMMARY", ""), sections.get("BODY", ""), candidates
    )
    sections["EXECUTIVE_SUMMARY"] = new_summary
    sections["BODY"] = new_body
    article_md = (
        _assemble_article(sections, final_sources, telemetry)
        if branded
        else _assemble_report(sections, final_sources, telemetry, topic)
    )
    notification_txt = sections.get("NOTIFICATION", "")
    return article_md, notification_txt
