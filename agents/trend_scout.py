import argparse
import json
import logging
import os
import re
import sys

from dotenv import load_dotenv
from google.genai import types as genai_types

from agents.sources.base import SourceAdapter
from agents.sources.newsapi import NewsApiAdapter
from core.config_loader import load_communities
from core.types import Community, Headline, NewsSource, StrategyBrief
from llm.gemini import get_gemini_client

logger = logging.getLogger(__name__)

_GEMINI_MODEL = "gemini-2.5-flash"
_RANKING_SYSTEM = (
    "You are a satirical content strategist. "
    "Rank news headlines by their satirical potential for a given community profile. "
    "Return only a JSON array of headline titles — no explanation, no markdown."
)
_INFERENCE_SYSTEM = (
    "You are a community analyst. "
    "Given a plain-language description of a community or audience, "
    "infer three attributes. "
    'Set "output_language" to the primary language implied by the description '
    "(e.g. French for a French-speaking community, English if unspecified). "
    "Respond with ONLY a JSON object — no explanation, no markdown — "
    'using exactly these keys: "target_audience", "output_language", "tone".'
)
_INFERENCE_DEFAULTS: dict[str, str] = {
    "target_audience": "general public",
    "output_language": "English",
    "tone": "dry wit",
}
# US and UK general headlines cover the broadest English-language satirical
# territory and power the existing named communities, so they serve as a
# sensible default fetch scope when no community config is available.
_DEFAULT_NEWS_SOURCES: list[NewsSource] = [
    NewsSource(country="us", category="general", count=10),
    NewsSource(country="gb", category="general", count=10),
]
# Extended inference prompt that adds news_country / news_category so both brief
# and source selection can be resolved in a single Gemini call.
_COMBINED_INFERENCE_SYSTEM = (
    "You are a community analyst. "
    "Given a plain-language description of a community or audience, "
    "infer five attributes. "
    'Set "output_language" to the primary language implied by the description '
    "(e.g. French for a French-speaking community, English if unspecified). "
    'Set "news_country" to the ISO 3166-1 alpha-2 code most relevant '
    'to this community (e.g. "pt" for Portuguese, "gb" for UK, "us" for US). '
    'Set "news_category" to the NewsAPI category that best fits: '
    "business, entertainment, general, health, science, sports, or technology. "
    "Respond with ONLY a JSON object — no explanation, no markdown — "
    'using exactly these keys: '
    '"target_audience", "output_language", "tone", "news_country", "news_category".'
)
_SOURCE_DEFAULTS: dict[str, str] = {
    "news_country": "us",
    "news_category": "general",
}
def _rank_headlines(
    headlines: list[Headline],
    audience: str,
    language: str,
    tone: str,
    description_hint: str,
    n: int,
) -> list[str]:
    client = get_gemini_client()
    # Community profile block: append raw description when provided so the
    # model has richer context than structured fields alone can convey.
    profile = (
        f"Community profile:\n"
        f"- Audience: {audience}\n"
        f"- Tone: {tone}\n"
        f"- Language: {language}\n"
    )
    if description_hint:
        profile += f"- Description: {description_hint}\n"
    lines = "\n".join(
        f"{i + 1}. {h.title}" + (f" — {h.abstract}" if h.abstract else "")
        for i, h in enumerate(headlines)
    )
    contents = (
        f"{profile}\n"
        f"Headlines:\n{lines}\n\n"
        f"Return a JSON array of the top {n} headline titles "
        f"ranked by satirical potential for this community. "
        f"Return only the JSON array."
    )
    response = client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=contents,
        config=genai_types.GenerateContentConfig(
            system_instruction=_RANKING_SYSTEM,
            temperature=0.1,
        ),
    )
    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    ranked = json.loads(raw)
    if not isinstance(ranked, list):
        raise ValueError(f"Gemini ranking returned non-list: {raw!r}")
    return [str(t) for t in ranked[:n]]


def _bare(title: str) -> Headline:
    return Headline(
        title=title, abstract="", source="", published_at="", social_score=0.0
    )


def _seed_headlines(community: Community, n: int) -> list[Headline]:
    return [_bare(t) for t in community.topics[:n]]


def get_topics(
    community: Community,
    n: int = 3,
    *,
    adapter: SourceAdapter | None = None,
) -> tuple[list[Headline], str]:
    """Fetch and rank top-N headlines; fall back to seed topics on failure.

    Returns (headlines, source) where source is "trend_scout" or "seed".
    """
    if not community.news_sources:
        logger.info(
            "trend_scout: community=%r has no news_sources — using seed topics",
            community.name,
        )
        return _seed_headlines(community, n), "seed"

    _adapter = adapter if adapter is not None else NewsApiAdapter()
    fetched = _adapter.fetch(community)

    if not fetched:
        logger.warning(
            "trend_scout: community=%r fetch returned no headlines"
            " — falling back to seed topics",
            community.name,
        )
        return _seed_headlines(community, n), "seed"

    try:
        ranked_titles = _rank_headlines(
            fetched, community.target_audience, community.output_language,
            community.tone, "", n
        )
        if not ranked_titles:
            raise ValueError("empty ranked list")
        title_to_headline = {h.title: h for h in fetched}
        ranked = [title_to_headline.get(t, _bare(t)) for t in ranked_titles]
        logger.info(
            "trend_scout: community=%r ranked %d topics from %d headlines via Gemini",
            community.name,
            len(ranked),
            len(fetched),
        )
        return ranked, "trend_scout"
    except Exception as exc:
        logger.warning(
            "trend_scout: community=%r Gemini ranking failed (%s)"
            " — falling back to seed topics",
            community.name,
            exc,
        )
        return _seed_headlines(community, n), "seed"


def infer_brief_from_description(description: str) -> StrategyBrief:
    client = get_gemini_client()
    # Ask Gemini to interpret the free-text description and return structured fields
    response = client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=f"Community description: {description}",
        config=genai_types.GenerateContentConfig(
            system_instruction=_INFERENCE_SYSTEM,
            temperature=0.1,
        ),
    )
    # Strip markdown fences before parsing — same defensive pattern as _rank_headlines
    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    parsed: dict = {}
    try:
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError(f"inference returned non-dict: {raw!r}")
        parsed = result
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "trend_scout: infer_brief_from_description parse failed (%s)"
            " — applying all defaults",
            exc,
        )
    # Build the brief applying _INFERENCE_DEFAULTS for any absent or blank field
    fields: dict[str, str] = {}
    for key, default in _INFERENCE_DEFAULTS.items():
        value = parsed.get(key, "")
        if not isinstance(value, str) or not value.strip():
            logger.warning(
                "trend_scout: inferred %r is absent or blank — using default %r",
                key,
                default,
            )
            fields[key] = default
        else:
            fields[key] = value.strip()
    logger.info(
        "trend_scout: inferred brief: audience=%r language=%r tone=%r",
        fields["target_audience"],
        fields["output_language"],
        fields["tone"],
    )
    return StrategyBrief(
        target_audience=fields["target_audience"],
        output_language=fields["output_language"],
        tone=fields["tone"],
    )


def infer_community_profile(
    description: str,
) -> tuple[StrategyBrief, list[NewsSource]]:
    """Infer brief and news sources from a description in one Gemini call."""
    client = get_gemini_client()
    # Single call covers both brief inference and source selection to reduce latency
    response = client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=f"Community description: {description}",
        config=genai_types.GenerateContentConfig(
            system_instruction=_COMBINED_INFERENCE_SYSTEM,
            temperature=0.1,
        ),
    )
    # Strip markdown fences — same defensive pattern as _rank_headlines
    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    parsed: dict = {}
    try:
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError(f"inference returned non-dict: {raw!r}")
        parsed = result
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "trend_scout: infer_community_profile parse failed (%s)"
            " — applying all defaults",
            exc,
        )
    # Build brief fields applying _INFERENCE_DEFAULTS for absent or blank values
    fields: dict[str, str] = {}
    for key, default in _INFERENCE_DEFAULTS.items():
        value = parsed.get(key, "")
        if not isinstance(value, str) or not value.strip():
            logger.warning(
                "trend_scout: inferred %r is absent or blank — using default %r",
                key,
                default,
            )
            fields[key] = default
        else:
            fields[key] = value.strip()
    brief = StrategyBrief(
        target_audience=fields["target_audience"],
        output_language=fields["output_language"],
        tone=fields["tone"],
    )
    # Extract source fields; fall back to _SOURCE_DEFAULTS so a fetch always runs
    news_country = parsed.get("news_country", "")
    news_category = parsed.get("news_category", "")
    if not isinstance(news_country, str) or not news_country.strip():
        logger.warning(
            "trend_scout: news_country absent or blank — using default %r",
            _SOURCE_DEFAULTS["news_country"],
        )
        news_country = _SOURCE_DEFAULTS["news_country"]
    if not isinstance(news_category, str) or not news_category.strip():
        logger.warning(
            "trend_scout: news_category absent or blank — using default %r",
            _SOURCE_DEFAULTS["news_category"],
        )
        news_category = _SOURCE_DEFAULTS["news_category"]
    sources = [
        NewsSource(
            country=news_country.strip().lower(),
            category=news_category.strip().lower(),
            count=15,
        )
    ]
    logger.info(
        "trend_scout: inferred profile: audience=%r language=%r tone=%r"
        " news_country=%r news_category=%r",
        fields["target_audience"],
        fields["output_language"],
        fields["tone"],
        news_country,
        news_category,
    )
    return brief, sources


def get_topics_for_description(
    description: str,
    n: int = 3,
    *,
    adapter: SourceAdapter | None = None,
) -> tuple[list[Headline], StrategyBrief, str]:
    # Infer brief and sources together before fetching so ranking uses the right profile
    brief, sources = infer_community_profile(description)
    # Build a synthetic Community to satisfy the adapter's fetch interface; only
    # news_sources matters to NewsApiAdapter — the other fields carry the inferred brief
    _adapter = adapter if adapter is not None else NewsApiAdapter()
    synthetic = Community(
        name="_free_text",
        target_audience=brief.target_audience,
        output_language=brief.output_language,
        tone=brief.tone,
        topics=[],
        news_sources=sources,
    )
    fetched = _adapter.fetch(synthetic)
    # Nothing to rank — signal the caller to handle the empty case gracefully
    if not fetched:
        logger.warning(
            "trend_scout: free-text mode fetch returned no headlines"
            " for description=%r",
            description,
        )
        return [], brief, "none"
    # Rank by relevance to the community description, passing the raw text as a hint
    try:
        ranked_titles = _rank_headlines(
            fetched, brief.target_audience, brief.output_language,
            brief.tone, description, n,
        )
        if not ranked_titles:
            raise ValueError("empty ranked list")
        title_to_headline = {h.title: h for h in fetched}
        ranked = [title_to_headline.get(t, _bare(t)) for t in ranked_titles]
        logger.info(
            "trend_scout: free-text mode ranked %d topics from %d headlines"
            " for description=%r",
            len(ranked),
            len(fetched),
            description,
        )
        return ranked, brief, "trend_scout"
    except Exception as exc:
        logger.warning(
            "trend_scout: free-text mode ranking failed (%s)"
            " — returning empty for description=%r",
            exc,
            description,
        )
        return [], brief, "none"


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Trend Scout — fetch and rank trending topics for a community"
    )
    parser.add_argument(
        "--community",
        required=True,
        metavar="NAME",
        help="community name from communities.yaml",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=3,
        metavar="N",
        help="number of topics to return (default: 3)",
    )
    args = parser.parse_args()

    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set", file=sys.stderr)
        sys.exit(2)
    if not os.getenv("NEWSAPI_ORG_KEY"):
        print("ERROR: NEWSAPI_ORG_KEY is not set", file=sys.stderr)
        sys.exit(2)

    try:
        communities = load_communities("communities.yaml")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    community = next((c for c in communities if c.name == args.community), None)
    if community is None:
        print(f"ERROR: unknown community {args.community!r}", file=sys.stderr)
        sys.exit(1)

    headlines, source = get_topics(community, n=args.top)
    if not headlines:
        print("No topics returned.", file=sys.stderr)
        sys.exit(1)

    print(f"(source: {source})\n")
    for i, h in enumerate(headlines, 1):
        print(f"{i}. {h.title}")
        if h.abstract:
            prefix = f"{h.source} — " if h.source else ""
            print(f"   {prefix}{h.abstract}")
        print()
