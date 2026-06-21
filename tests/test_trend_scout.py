import json
import logging
from unittest.mock import MagicMock, patch

import pytest

import agents.trend_scout as _ts_module
from agents.sources.base import SourceAdapter
from agents.trend_scout import get_topics
from core.types import Community, Headline, NewsSource, StrategyBrief

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SAMPLE_HEADLINES = [
    Headline(
        title="AI replaces junior devs",
        abstract="Firms cut junior roles.",
        source="newsapi",
        published_at="2026-05-29",
        social_score=1500.0,
    ),
    Headline(
        title="Rust rewrite season begins",
        abstract="Another startup rewrites in Rust.",
        source="newsapi",
        published_at="2026-05-29",
        social_score=900.0,
    ),
    Headline(
        title="Scrum meeting productivity questioned",
        abstract="Study finds standups wasteful.",
        source="newsapi",
        published_at="2026-05-29",
        social_score=700.0,
    ),
]

_COMMUNITY_WITH_SOURCES = Community(
    name="uk-tech-engineers",
    target_audience="British software engineers",
    output_language="English",
    tone="dry British wit",
    topics=["Fallback topic A", "Fallback topic B"],
    news_sources=[NewsSource(sources="bbc-news")],
)

_COMMUNITY_NO_SOURCES = Community(
    name="no-sources-community",
    target_audience="Test audience",
    output_language="English",
    tone="dry",
    topics=["Seed topic 1", "Seed topic 2"],
    news_sources=[],
)


def _mock_gemini(titles: list[str]) -> MagicMock:
    mock_response = MagicMock()
    mock_response.text = json.dumps(titles)
    return mock_response


# ---------------------------------------------------------------------------
# US1 — Automated Topic Discovery
# ---------------------------------------------------------------------------


def test_get_topics_returns_ranked_list_from_gemini():
    # Core happy path: adapter returns headlines, Gemini ranks them as topic strings.
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_gemini(
        [
            "AI replaces junior devs",
            "Rust rewrite season begins",
            "Scrum meeting productivity questioned",
        ]
    )

    with patch("llm.gemini._get_client", return_value=mock_client):
        result, source = get_topics(_COMMUNITY_WITH_SOURCES, n=3, adapter=stub_adapter)

    assert [h.title for h in result] == [
        "AI replaces junior devs",
        "Rust rewrite season begins",
        "Scrum meeting productivity questioned",
    ]
    assert all(h.abstract for h in result)
    assert source == "trend_scout"


def test_get_topics_respects_n_parameter():
    # get_topics() must return at most n items even when Gemini returns a longer list.
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_gemini(
        [
            "AI replaces junior devs",
            "Rust rewrite season begins",
            "Scrum meeting productivity questioned",
        ]
    )

    with patch("llm.gemini._get_client", return_value=mock_client):
        result, source = get_topics(_COMMUNITY_WITH_SOURCES, n=1, adapter=stub_adapter)

    assert len(result) == 1
    assert result[0].title == "AI replaces junior devs"
    assert source == "trend_scout"


def test_get_topics_calls_gemini_with_community_profile():
    # Gemini must receive audience and tone so ranking is community-specific.
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_gemini(
        ["AI replaces junior devs"]
    )

    with patch("llm.gemini._get_client", return_value=mock_client):
        get_topics(_COMMUNITY_WITH_SOURCES, n=1, adapter=stub_adapter)

    contents = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "British software engineers" in contents
    assert "dry British wit" in contents


# ---------------------------------------------------------------------------
# US2 — Graceful Fallback
# ---------------------------------------------------------------------------


def test_get_topics_falls_back_to_seed_on_empty_fetch():
    # When fetch returns no headlines, seed topics must be returned instead.
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = []

    result, source = get_topics(_COMMUNITY_WITH_SOURCES, n=3, adapter=stub_adapter)

    assert [h.title for h in result] == ["Fallback topic A", "Fallback topic B"]
    assert source == "seed"


def test_get_topics_falls_back_to_seed_on_gemini_failure():
    # A Gemini exception must not crash get_topics — seed topics are the safety net.
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Gemini unavailable")

    with patch("llm.gemini._get_client", return_value=mock_client):
        result, source = get_topics(_COMMUNITY_WITH_SOURCES, n=3, adapter=stub_adapter)

    assert [h.title for h in result] == ["Fallback topic A", "Fallback topic B"]
    assert source == "seed"


def test_get_topics_returns_seed_when_no_news_sources():
    # A community with no news_sources must skip fetch and return seed topics directly.
    result, source = get_topics(_COMMUNITY_NO_SOURCES, n=3)

    assert [h.title for h in result] == ["Seed topic 1", "Seed topic 2"]
    assert source == "seed"


def test_get_topics_returns_empty_when_no_sources_and_no_seeds():
    # If both news_sources and seed topics are absent, [] is returned without raising.
    community = Community(
        name="empty-community",
        target_audience="Test",
        output_language="English",
        tone="dry",
        topics=[],
        news_sources=[],
    )

    result, source = get_topics(community, n=3)

    assert result == []
    assert source == "seed"


# ---------------------------------------------------------------------------
# T001 — Ranking helper regression tests
# ---------------------------------------------------------------------------


def test_ranking_passes_language_to_gemini_prompt():
    # The ranking call must include output_language in the prompt so Gemini can
    # score stories for language-appropriate satirical potential.
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_gemini(
        ["AI replaces junior devs"]
    )
    with patch("llm.gemini._get_client", return_value=mock_client):
        get_topics(_COMMUNITY_WITH_SOURCES, n=1, adapter=stub_adapter)
    contents = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert "English" in contents


def test_ranking_strips_markdown_fences_from_gemini_response():
    # Gemini sometimes wraps JSON in ```json fences; the ranking helper must
    # strip them before parsing, otherwise json.loads raises and ranking is lost.
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES
    fenced_response = MagicMock()
    fenced_response.text = "```json\n[\"AI replaces junior devs\"]\n```"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = fenced_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        result, source = get_topics(_COMMUNITY_WITH_SOURCES, n=1, adapter=stub_adapter)
    assert result[0].title == "AI replaces junior devs"
    assert source == "trend_scout"


def test_ranking_falls_back_to_seed_when_gemini_returns_non_list():
    # If Gemini returns a non-list JSON value (object, string, number), the
    # ranking helper raises ValueError; get_topics must catch it and use seeds.
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES
    bad_response = MagicMock()
    bad_response.text = '{"error": "malformed"}'
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = bad_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        result, source = get_topics(_COMMUNITY_WITH_SOURCES, n=3, adapter=stub_adapter)
    assert [h.title for h in result] == ["Fallback topic A", "Fallback topic B"]
    assert source == "seed"


# ---------------------------------------------------------------------------
# T003 — infer_brief_from_description unit tests
# ---------------------------------------------------------------------------


def test_infer_brief_returns_correct_fields_from_valid_json():
    # infer_brief_from_description must parse all three fields from a well-formed
    # Gemini response — verifies the happy-path contract before any edge cases.
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "target_audience": "US adults critical of Trump",
        "output_language": "English",
        "tone": "sharp political satire",
    })
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        brief = _ts_module.infer_brief_from_description(
            "US community that dislikes Trump"
        )
    assert isinstance(brief, StrategyBrief)
    assert brief.target_audience == "US adults critical of Trump"
    assert brief.output_language == "English"
    assert brief.tone == "sharp political satire"


def test_infer_brief_applies_all_defaults_on_malformed_json():
    # When Gemini returns unparseable text, the function must use all defaults
    # rather than raise — keeps the pipeline alive on inference failure.
    mock_response = MagicMock()
    mock_response.text = "not json at all"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        brief = _ts_module.infer_brief_from_description("some community")
    assert brief.target_audience == "general public"
    assert brief.output_language == "English"
    assert brief.tone == "dry wit"


def test_infer_brief_applies_default_only_for_missing_key():
    # A partial response with two of three keys must default only the absent
    # field — not replace values the model did return.
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "target_audience": "French-speaking satire fans",
        "output_language": "French",
    })
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        brief = _ts_module.infer_brief_from_description("Communauté française")
    assert brief.target_audience == "French-speaking satire fans"
    assert brief.output_language == "French"
    assert brief.tone == "dry wit"


def test_infer_brief_treats_blank_value_as_absent():
    # A blank string in the JSON is semantically absent — passing an empty
    # audience to downstream agents would produce a broken brief.
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "target_audience": "",
        "output_language": "English",
        "tone": "sarcastic",
    })
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        brief = _ts_module.infer_brief_from_description("some community")
    assert brief.target_audience == "general public"
    assert brief.output_language == "English"
    assert brief.tone == "sarcastic"


def test_infer_brief_passes_description_in_gemini_prompt():
    # The community description must appear in the prompt contents so the model
    # infers from actual text rather than receiving a generic blank request.
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "target_audience": "x", "output_language": "English", "tone": "x",
    })
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    description = "US community that dislikes Trump"
    with patch("llm.gemini._get_client", return_value=mock_client):
        _ts_module.infer_brief_from_description(description)
    contents = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert description in contents


# ---------------------------------------------------------------------------
# T010 — Language inference via infer_brief_from_description (parametrised)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "description,expected_language",
    [
        ("Communauté française qui critique Macron", "French"),
        ("Comunidade portuguesa que critica o governo", "Portuguese"),
        ("US tech professionals who follow AI news", "English"),
    ],
)
def test_infer_brief_infers_language_from_description(description, expected_language):
    # Language returned by Gemini must propagate unchanged to StrategyBrief so
    # downstream agents generate content in the correct language.
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "target_audience": "adults",
        "output_language": expected_language,
        "tone": "dry wit",
    })
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        brief = _ts_module.infer_brief_from_description(description)
    assert brief.output_language == expected_language


def test_infer_brief_defaults_language_to_english_on_blank_output_language(caplog):
    # A blank output_language from Gemini must default to "English" and emit a
    # WARNING so operators can identify when inference was incomplete.
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "target_audience": "adults",
        "output_language": "",
        "tone": "dry wit",
    })
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with (
        patch("llm.gemini._get_client", return_value=mock_client),
        caplog.at_level(logging.WARNING, logger="agents.trend_scout"),
    ):
        brief = _ts_module.infer_brief_from_description("vague community")
    assert brief.output_language == "English"
    assert any("output_language" in r.message for r in caplog.records)


def test_inference_system_prompt_explicitly_instructs_language_inference():
    # _INFERENCE_SYSTEM must tell Gemini to infer the community's primary language
    # from the description; without this instruction the model defaults to English
    # for non-English communities.
    assert "primary language" in _ts_module._INFERENCE_SYSTEM


# ---------------------------------------------------------------------------
# T004 — get_topics_for_description unit tests
# ---------------------------------------------------------------------------


def test_get_topics_for_description_returns_ranked_headlines_and_brief():
    # Happy path: inferred profile + fetched headlines + ranking all succeed and
    # the function returns the ranked list, the brief, and source="trend_scout".
    inferred_brief = StrategyBrief(
        target_audience="US adults critical of Trump",
        output_language="English",
        tone="sharp political satire",
    )
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES
    with patch(
        "agents.trend_scout.infer_community_profile", return_value=(inferred_brief, [])
    ):
        with patch(
            "agents.trend_scout._rank_headlines",
            return_value=["AI replaces junior devs", "Rust rewrite season begins"],
        ):
            headlines, brief, source = _ts_module.get_topics_for_description(
                "US community that dislikes Trump", n=2, adapter=stub_adapter
            )
    assert source == "trend_scout"
    assert brief is inferred_brief
    assert [h.title for h in headlines] == [
        "AI replaces junior devs",
        "Rust rewrite season begins",
    ]


def test_get_topics_for_description_returns_empty_when_adapter_returns_nothing():
    # When the adapter finds no headlines, the function must return an empty list
    # and source="none" rather than calling the ranker or raising.
    inferred_brief = StrategyBrief(
        target_audience="some audience",
        output_language="English",
        tone="dry wit",
    )
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = []
    with patch(
        "agents.trend_scout.infer_community_profile", return_value=(inferred_brief, [])
    ):
        with patch("agents.trend_scout._rank_headlines") as mock_rank:
            headlines, brief, source = _ts_module.get_topics_for_description(
                "unknown community", n=3, adapter=stub_adapter
            )
    assert headlines == []
    assert source == "none"
    assert brief is inferred_brief
    mock_rank.assert_not_called()


def test_get_topics_for_description_passes_description_as_hint_to_ranker():
    # The raw description string must be forwarded to _rank_headlines as
    # description_hint so the ranker has richer context than inferred fields alone.
    description = "US community that dislikes Trump"
    inferred_brief = StrategyBrief(
        target_audience="US adults",
        output_language="English",
        tone="sharp",
    )
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES
    with patch(
        "agents.trend_scout.infer_community_profile", return_value=(inferred_brief, [])
    ):
        with patch(
            "agents.trend_scout._rank_headlines",
            return_value=["AI replaces junior devs"],
        ) as mock_rank:
            _ts_module.get_topics_for_description(
                description, n=1, adapter=stub_adapter
            )
    call_args = mock_rank.call_args.args
    assert call_args[4] == description


def test_get_topics_for_description_uses_inferred_brief_fields_for_ranking():
    # The audience, language, and tone passed to _rank_headlines must come from
    # the inferred profile — not hardcoded values — so ranking is community-specific.
    inferred_brief = StrategyBrief(
        target_audience="French-speaking political observers",
        output_language="French",
        tone="mordant",
    )
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES
    with patch(
        "agents.trend_scout.infer_community_profile", return_value=(inferred_brief, [])
    ):
        with patch(
            "agents.trend_scout._rank_headlines",
            return_value=["AI replaces junior devs"],
        ) as mock_rank:
            _ts_module.get_topics_for_description(
                "Communauté française", n=1, adapter=stub_adapter
            )
    call_args = mock_rank.call_args.args
    assert call_args[1] == "French-speaking political observers"
    assert call_args[2] == "French"
    assert call_args[3] == "mordant"


# ---------------------------------------------------------------------------
# T013 — get_topics() output unchanged after _rank_headlines refactor
# ---------------------------------------------------------------------------


def test_get_topics_unchanged_output_after_rank_headlines_refactor():
    # get_topics() must return the same ranked Headline objects after the
    # _rank_with_gemini → _rank_headlines refactor — end-to-end regression guard.
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES
    expected_titles = ["Rust rewrite season begins", "AI replaces junior devs"]
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_gemini(expected_titles)
    with patch("llm.gemini._get_client", return_value=mock_client):
        result, source = get_topics(_COMMUNITY_WITH_SOURCES, n=2, adapter=stub_adapter)
    assert [h.title for h in result] == expected_titles
    assert source == "trend_scout"
    assert all(isinstance(h, Headline) for h in result)


# ---------------------------------------------------------------------------
# US4 — Source adapter injection
# ---------------------------------------------------------------------------


def test_get_topics_uses_injected_stub_adapter():
    # An injected stub adapter must replace NewsApiAdapter — sources are pluggable.
    class StubAdapter(SourceAdapter):
        def fetch(self, community: Community) -> list[Headline]:
            return [
                Headline(
                    title="Stub headline",
                    abstract="Stub abstract",
                    source="stub",
                    published_at="2026-05-29",
                    social_score=999.0,
                )
            ]

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_gemini(["Stub headline"])

    with patch("llm.gemini._get_client", return_value=mock_client):
        result, source = get_topics(_COMMUNITY_WITH_SOURCES, n=1, adapter=StubAdapter())

    assert result[0].title == "Stub headline"
    assert source == "trend_scout"


# ---------------------------------------------------------------------------
# T014 — infer_community_profile unit tests (Stage 11)
# ---------------------------------------------------------------------------


def test_infer_community_profile_returns_brief_and_sources():
    # Happy path: Gemini returns all five fields, both a StrategyBrief and one
    # NewsSource are returned with the inferred values — not the defaults.
    payload = json.dumps({
        "target_audience": "Portuguese football fans",
        "output_language": "Portuguese",
        "tone": "passionate",
        "news_country": "pt",
        "news_category": "sports",
    })
    mock_response = MagicMock()
    mock_response.text = payload
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        brief, sources = _ts_module.infer_community_profile("Portuguese football fans")
    assert brief.output_language == "Portuguese"
    assert brief.target_audience == "Portuguese football fans"
    assert brief.tone == "passionate"
    assert len(sources) == 1
    assert sources[0].country == "pt"
    assert sources[0].category == "sports"


def test_infer_community_profile_defaults_missing_source_fields():
    # When news_country and news_category are absent, the _SOURCE_DEFAULTS
    # ("us"/"general") are applied so the fetch never silently sends no-op params.
    payload = json.dumps({
        "target_audience": "UK adults",
        "output_language": "English",
        "tone": "dry",
    })
    mock_response = MagicMock()
    mock_response.text = payload
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        brief, sources = _ts_module.infer_community_profile("UK adults")
    assert sources[0].country == "us"
    assert sources[0].category == "general"
    assert brief.output_language == "English"


def test_infer_community_profile_applies_all_defaults_on_bad_json():
    # When Gemini returns unparseable JSON, all brief fields and source fields
    # fall back to their defaults so the caller can always proceed.
    mock_response = MagicMock()
    mock_response.text = "not json at all"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with patch("llm.gemini._get_client", return_value=mock_client):
        brief, sources = _ts_module.infer_community_profile("some community")
    assert brief.target_audience == "general public"
    assert brief.output_language == "English"
    assert brief.tone == "dry wit"
    assert sources[0].country == "us"
    assert sources[0].category == "general"


def test_get_topics_for_description_uses_inferred_sources_not_defaults():
    # get_topics_for_description must pass the sources returned by
    # infer_community_profile to the adapter, not the hardcoded _DEFAULT_NEWS_SOURCES.
    inferred_brief = StrategyBrief(
        target_audience="Portuguese football fans",
        output_language="Portuguese",
        tone="passionate",
    )
    inferred_sources = [NewsSource(country="pt", category="sports", count=15)]
    stub_adapter = MagicMock(spec=SourceAdapter)
    stub_adapter.fetch.return_value = _SAMPLE_HEADLINES
    with patch(
        "agents.trend_scout.infer_community_profile",
        return_value=(inferred_brief, inferred_sources),
    ):
        with patch(
            "agents.trend_scout._rank_headlines",
            return_value=["AI replaces junior devs"],
        ):
            _ts_module.get_topics_for_description(
                "Portuguese football fans", n=1, adapter=stub_adapter
            )
    call_community = stub_adapter.fetch.call_args.args[0]
    assert call_community.news_sources == inferred_sources
