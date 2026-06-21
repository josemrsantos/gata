from unittest.mock import MagicMock, patch

import httpx

from agents.sources.newsapi import NewsApiAdapter
from core.types import Community, Headline, NewsSource

_COMMUNITY_SOURCES = Community(
    name="test-community",
    target_audience="Test audience",
    output_language="English",
    tone="dry",
    topics=["fallback topic"],
    news_sources=[NewsSource(sources="bbc-news,the-verge", count=10)],
)

_COMMUNITY_COUNTRY = Community(
    name="us-community",
    target_audience="US audience",
    output_language="English",
    tone="dry",
    topics=["fallback"],
    news_sources=[NewsSource(country="us", count=10)],
)

_SAMPLE_RESPONSE = {
    "status": "ok",
    "totalResults": 2,
    "articles": [
        {
            "source": {"id": "bbc-news", "name": "BBC News"},
            "title": "Tech firm cuts jobs amid AI boom",
            "description": "A major tech company announced layoffs.",
            "publishedAt": "2026-05-29T10:00:00Z",
        },
        {
            "source": {"id": "the-verge", "name": "The Verge"},
            "title": "Government mandates open source",
            "description": "New legislation requires open-source software.",
            "publishedAt": "2026-05-29T09:00:00Z",
        },
    ],
}


def test_fetch_returns_headlines_on_success():
    # Happy path: a valid NewsAPI.org response must be parsed into Headline objects.
    adapter = NewsApiAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = _SAMPLE_RESPONSE
    mock_response.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_response):
        result = adapter.fetch(_COMMUNITY_SOURCES)

    assert len(result) == 2
    assert all(isinstance(h, Headline) for h in result)
    assert result[0].title == "Tech firm cuts jobs amid AI boom"
    assert result[0].source == "BBC News"
    assert result[0].social_score == 0.0


def test_fetch_deduplicates_headlines_across_sources():
    # Duplicate headlines from multiple news_sources must appear only once.
    community = Community(
        name="dup-community",
        target_audience="Test",
        output_language="English",
        tone="dry",
        topics=["fallback"],
        news_sources=[
            NewsSource(sources="bbc-news"),
            NewsSource(country="us"),
        ],
    )
    adapter = NewsApiAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = _SAMPLE_RESPONSE
    mock_response.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_response):
        result = adapter.fetch(community)

    titles = [h.title for h in result]
    assert len(titles) == len(set(titles))


def test_fetch_filters_removed_articles():
    # NewsAPI.org returns "[Removed]" for deleted articles — these must be excluded.
    adapter = NewsApiAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "ok",
        "articles": [
            {
                "source": {"name": "BBC"},
                "title": "[Removed]",
                "description": "",
                "publishedAt": "2026-05-29T10:00:00Z",
            },
            {
                "source": {"name": "The Verge"},
                "title": "Real headline",
                "description": "Real description.",
                "publishedAt": "2026-05-29T09:00:00Z",
            },
        ],
    }
    mock_response.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_response):
        result = adapter.fetch(_COMMUNITY_SOURCES)

    assert len(result) == 1
    assert result[0].title == "Real headline"


def test_fetch_returns_empty_on_request_error():
    # A network error must return [] without raising so the pipeline can fall back.
    adapter = NewsApiAdapter(api_key="test-key")

    with patch("httpx.get", side_effect=httpx.RequestError("timeout")):
        result = adapter.fetch(_COMMUNITY_SOURCES)

    assert result == []


def test_fetch_returns_empty_on_http_error():
    # An HTTP error must return [] without raising so the pipeline keeps running.
    adapter = NewsApiAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401", request=MagicMock(), response=MagicMock(status_code=401)
    )

    with patch("httpx.get", return_value=mock_response):
        result = adapter.fetch(_COMMUNITY_SOURCES)

    assert result == []


def test_fetch_returns_empty_when_no_api_key():
    # A missing API key must skip any HTTP call — no key, no valid request.
    adapter = NewsApiAdapter(api_key="")

    with patch("httpx.get") as mock_get:
        result = adapter.fetch(_COMMUNITY_SOURCES)

    mock_get.assert_not_called()
    assert result == []


def test_fetch_returns_empty_when_no_news_sources():
    # A community with no news_sources must return [] without any HTTP call.
    community = Community(
        name="no-sources",
        target_audience="Test",
        output_language="English",
        tone="dry",
        topics=["fallback"],
        news_sources=[],
    )
    adapter = NewsApiAdapter(api_key="test-key")

    with patch("httpx.get") as mock_get:
        result = adapter.fetch(community)

    mock_get.assert_not_called()
    assert result == []


def test_fetch_sends_sources_param_when_sources_set():
    # When news_source.sources is set, the adapter must send 'sources' not 'country'.
    adapter = NewsApiAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok", "articles": []}
    mock_response.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_response) as mock_get:
        adapter.fetch(_COMMUNITY_SOURCES)

    params = mock_get.call_args.kwargs["params"]
    assert params["sources"] == "bbc-news,the-verge"
    assert params["pageSize"] == 10
    assert "country" not in params
    assert "category" not in params


def test_fetch_sends_country_and_category_when_country_set():
    # When news_source.country is set (not sources), country and category are sent.
    community = Community(
        name="tech-community",
        target_audience="Test",
        output_language="English",
        tone="dry",
        topics=["fallback"],
        news_sources=[NewsSource(country="us", category="technology", count=5)],
    )
    adapter = NewsApiAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok", "articles": []}
    mock_response.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_response) as mock_get:
        adapter.fetch(community)

    params = mock_get.call_args.kwargs["params"]
    assert params["country"] == "us"
    assert params["category"] == "technology"
    assert params["pageSize"] == 5
    assert "sources" not in params


def test_fetch_omits_category_for_general_country():
    # category must NOT be sent when it is "general" — keep the request minimal.
    adapter = NewsApiAdapter(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok", "articles": []}
    mock_response.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_response) as mock_get:
        adapter.fetch(_COMMUNITY_COUNTRY)

    params = mock_get.call_args.kwargs["params"]
    assert "category" not in params
