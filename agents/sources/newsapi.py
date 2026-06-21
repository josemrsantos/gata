import logging
import os
from datetime import date

import httpx

from agents.sources.base import SourceAdapter
from core.types import Community, Headline

logger = logging.getLogger(__name__)

_ENDPOINT = "https://newsapi.org/v2/top-headlines"
_TIMEOUT = 30.0


class NewsApiAdapter(SourceAdapter):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = (
            api_key if api_key is not None else os.getenv("NEWSAPI_ORG_KEY", "")
        )

    def fetch(self, community: Community) -> list[Headline]:
        if not self._api_key:
            logger.warning(
                "NewsApiAdapter: NEWSAPI_ORG_KEY not set — returning empty list"
            )
            return []
        if not community.news_sources:
            return []

        today = date.today().isoformat()
        headlines: list[Headline] = []
        seen: set[str] = set()

        for source in community.news_sources:
            if source.sources:
                params: dict = {
                    "sources": source.sources,
                    "pageSize": min(source.count, 100),
                    "apiKey": self._api_key,
                }
                label = f"sources={source.sources}"
            else:
                params = {
                    "country": source.country,
                    "pageSize": min(source.count, 100),
                    "apiKey": self._api_key,
                }
                if source.category != "general":
                    params["category"] = source.category
                label = f"country={source.country}"

            try:
                response = httpx.get(_ENDPOINT, params=params, timeout=_TIMEOUT)
                response.raise_for_status()
                data = response.json()
            except httpx.RequestError as exc:
                logger.warning("NewsApiAdapter: request error for %s — %s", label, exc)
                continue
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "NewsApiAdapter: HTTP %s for %s",
                    exc.response.status_code,
                    label,
                )
                continue

            for article in data.get("articles", []):
                title = article.get("title", "") or ""
                if not title or title == "[Removed]" or title in seen:
                    continue
                seen.add(title)
                published = (article.get("publishedAt", today) or today)[:10]
                headlines.append(
                    Headline(
                        title=title,
                        abstract=article.get("description", "") or "",
                        source=article.get("source", {}).get("name", "newsapi.org"),
                        published_at=published,
                        social_score=0.0,
                    )
                )

        return headlines
