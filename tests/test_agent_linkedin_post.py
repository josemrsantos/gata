from unittest.mock import MagicMock, patch

import httpx

from agents import agent_linkedin_post as alp
from core.types import (
    AgentTelemetry,
    ConversationLog,
    EnrichedBrief,
    LoopOutput,
    ResearchDigest,
    ResearchSource,
    RunTelemetry,
)
from llm.claude import ClaudeProvider
from llm.gemini import GeminiProvider
from llm.grok import GrokProvider

BRIEF = EnrichedBrief(
    target_audience="engineers",
    output_language="English",
    tone="neutral",
    cultural_angle="",
    culturally_loaded_references=[],
)


def _provider(model_id: str) -> MagicMock:
    provider = MagicMock()
    provider.model_id = model_id
    return provider


def _panelist_providers() -> list[list[MagicMock]]:
    return [[_provider("model-a")], [_provider("model-b")], [_provider("model-c")]]


# -- _build_research_query --


def test_build_research_query_includes_angles_as_bullets():
    # FR-007: supplied angles must reach the research query so search terms
    # reflect what the operator actually wants investigated.
    query = alp._build_research_query("Vibe coding", ["angle one", "angle two"])
    assert "angle one" in query
    assert "angle two" in query
    assert "Vibe coding" in query


def test_build_research_query_without_angles_is_just_the_topic():
    # No angle supplied must not inject an empty/garbled angles section.
    query = alp._build_research_query("Vibe coding", None)
    assert query.startswith("Topic: Vibe coding")
    assert "angles" not in query.lower()


def test_build_research_query_steers_toward_reputable_sources():
    # Spec 042 amendment 2 FR-024: every research query nudges toward
    # academic/reputable sources, regardless of whether angles were supplied.
    query = alp._build_research_query("Vibe coding", None)
    assert "academic" in query.lower() or "reputable" in query.lower()


# -- _extract_gemini_sources --


def test_extract_gemini_sources_reads_grounding_chunks():
    # FR-003: sources must come from real grounding metadata, not model prose.
    web = MagicMock(title="Example", uri="https://example.com/a")
    chunk = MagicMock(web=web)
    response = MagicMock()
    response.candidates = [
        MagicMock(grounding_metadata=MagicMock(grounding_chunks=[chunk]))
    ]
    sources = alp._extract_gemini_sources(response)
    assert sources == [ResearchSource(title="Example", url="https://example.com/a")]


def test_extract_gemini_sources_dedupes_by_url():
    # The same URL appearing twice in grounding metadata must not be published twice.
    web = MagicMock(title="Example", uri="https://example.com/a")
    chunk1, chunk2 = MagicMock(web=web), MagicMock(web=web)
    response = MagicMock()
    response.candidates = [
        MagicMock(grounding_metadata=MagicMock(grounding_chunks=[chunk1, chunk2]))
    ]
    assert len(alp._extract_gemini_sources(response)) == 1


def test_extract_gemini_sources_handles_no_candidates():
    # A response with no candidates must not raise — treated as zero sources.
    response = MagicMock(candidates=[])
    assert alp._extract_gemini_sources(response) == []


# -- _extract_claude_sources --


def test_extract_claude_sources_reads_citations_from_content_blocks():
    # Claude's citations are attached per content block — must be collected
    # across all blocks, not just the first. Spec 044: the raw citation title
    # is returned un-prefixed; the shared resolver (_resolve_sources) applies
    # the domain prefix uniformly across all three providers.
    citation = MagicMock(url="https://example.com/b", title="B Source")
    block = MagicMock(citations=[citation])
    response = MagicMock(content=[block])
    sources = alp._extract_claude_sources(response)
    assert sources == [ResearchSource(title="B Source", url="https://example.com/b")]


def test_extract_claude_sources_handles_no_citations():
    # A block with no citations attribute (or an empty one) must not raise.
    block = MagicMock(citations=[])
    response = MagicMock(content=[block])
    assert alp._extract_claude_sources(response) == []


def test_extract_claude_sources_yields_empty_title_when_none():
    # Spec 044: a citation with no title at all must yield an empty raw
    # title (not a "None" string) — the shared resolver treats an empty
    # title as non-descriptive and falls through to its other signals.
    citation = MagicMock(url="https://example.com/b", title=None)
    block = MagicMock(citations=[citation])
    response = MagicMock(content=[block])
    sources = alp._extract_claude_sources(response)
    assert sources == [ResearchSource(title="", url="https://example.com/b")]


# -- _extract_grok_sources --


def test_extract_grok_sources_from_output_annotations():
    # xAI's Agent Tools / Responses API attaches citations as annotations on an
    # output message's content — must produce usable ResearchSource entries.
    # `title` on the real annotation is just the footnote number, not a page
    # title, so the bare domain is used as the pre-fetch baseline (Spec 043
    # FR-005) — the same starting point Gemini's own API gives for free.
    annotation = MagicMock(url="https://example.com/c", title="1")
    content = MagicMock(annotations=[annotation])
    item = MagicMock(content=[content])
    response = MagicMock(output=[item])
    sources = alp._extract_grok_sources(response)
    assert sources == [ResearchSource(title="example.com", url="https://example.com/c")]


def test_extract_grok_sources_dedupes_by_url():
    # The same URL annotated on two different content items must not be
    # published twice.
    annotation = MagicMock(url="https://example.com/c", title="C")
    content = MagicMock(annotations=[annotation, annotation])
    item = MagicMock(content=[content])
    response = MagicMock(output=[item])
    assert len(alp._extract_grok_sources(response)) == 1


def test_extract_grok_sources_degrades_to_empty_on_unrecognised_shape():
    # An unexpected response shape must degrade to zero sources, never raise —
    # this is the graceful-degradation path called out in the spec's Assumptions
    # (xAI's exact Responses API citation shape isn't independently verified).
    response = MagicMock(output=None)
    assert alp._extract_grok_sources(response) == []


# -- _research_gemini / _research_claude / _research_grok --


def test_research_gemini_success_returns_digest_and_usage():
    # A successful grounded call must produce a digest with real sources and a
    # non-trivial usage record for cost tracking. The fetch is mocked to
    # return a descriptive title directly so this test makes no real network
    # call — the full resolution chain is covered separately below.
    provider = MagicMock(model_id="gemini-2.5-flash")
    web = MagicMock(title="G", uri="https://example.com/g")
    response = MagicMock(text="Findings here.")
    response.candidates = [
        MagicMock(grounding_metadata=MagicMock(grounding_chunks=[MagicMock(web=web)]))
    ]
    response.usage_metadata = MagicMock(
        prompt_token_count=100, candidates_token_count=200
    )
    provider.client.models.generate_content.return_value = response
    with patch(
        "agents.agent_linkedin_post._fetch_page_title",
        return_value=("Real Page Title", "https://example.com/g"),
    ):
        digest, usage = alp._research_gemini(provider, "Topic: X")
    assert digest.summary == "Findings here."
    assert digest.sources[0].url == "https://example.com/g"
    assert digest.sources[0].title == "G - Real Page Title"
    assert usage.model == "gemini-2.5-flash"


def test_research_gemini_exception_returns_none():
    # An API exception must soft-fail to (None, None), not propagate.
    provider = MagicMock(model_id="gemini-2.5-flash")
    provider.client.models.generate_content.side_effect = RuntimeError("boom")
    digest, usage = alp._research_gemini(provider, "Topic: X")
    assert digest is None
    assert usage is None


def test_research_gemini_empty_text_returns_none():
    # A response with no text must be treated as a failed research attempt.
    provider = MagicMock(model_id="gemini-2.5-flash")
    response = MagicMock(text="")
    provider.client.models.generate_content.return_value = response
    digest, usage = alp._research_gemini(provider, "Topic: X")
    assert digest is None


# -- _fetch_page_title (Spec 043, extended by Spec 044 FR-001/FR-014) --


def test_fetch_page_title_extracts_and_decodes_title():
    # SC-001: a real <title> tag must be extracted, HTML-entity-decoded, and
    # whitespace-collapsed, alongside the resolved URL.
    html_body = (
        "<html><head><title>What is Vibe coding  &amp; Why</title></head></html>"
    )
    with patch("agents.agent_linkedin_post.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(text=html_body, url="https://example.com/r")
        title, resolved_url = alp._fetch_page_title("https://example.com/redirect")
    assert title == "What is Vibe coding & Why"
    assert resolved_url == "https://example.com/r"


def test_fetch_page_title_sends_a_user_agent_header():
    # Regression: confirmed live that Wikipedia (and likely other sites) return
    # HTTP 403 for requests with no User-Agent, which looked identical to "no
    # title found" until traced back to the real cause — a browser-like UA
    # must be sent on every request.
    with patch("agents.agent_linkedin_post.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(text="<title>T</title>", url="https://x")
        alp._fetch_page_title("https://example.com/redirect")
    assert "User-Agent" in mock_get.call_args.kwargs["headers"]


def test_fetch_page_title_returns_none_and_original_url_on_request_exception():
    # SC-002: a timeout/connection error must degrade to (None, url), never
    # raise — no redirect could have completed, so the original URL is all
    # that's known.
    with patch(
        "agents.agent_linkedin_post.httpx.get", side_effect=httpx.TimeoutException("t")
    ):
        title, resolved_url = alp._fetch_page_title("https://example.com/redirect")
    assert title is None
    assert resolved_url == "https://example.com/redirect"


def test_fetch_page_title_returns_resolved_destination_url_on_non_2xx_status():
    # Spec 044 FR-014/SC-013: a non-2xx status after a successful redirect
    # must still surface the resolved destination URL (not the original
    # redirect-wrapper URL) so slug humanisation can use it.
    request = MagicMock()
    bad_response = MagicMock(url="https://real-destination.com/article")
    response = MagicMock(url="https://real-destination.com/article")
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=request, response=bad_response
    )
    with patch("agents.agent_linkedin_post.httpx.get", return_value=response):
        title, resolved_url = alp._fetch_page_title("https://redirect.example/r")
    assert title is None
    assert resolved_url == "https://real-destination.com/article"


def test_fetch_page_title_returns_none_when_no_title_tag_or_meta():
    # SC-003: HTML with no <title> tag and no og:title/twitter:title meta
    # must degrade to None, not raise or return a garbage value.
    with patch("agents.agent_linkedin_post.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            text="<html><body>no title here</body></html>", url="https://x"
        )
        title, _ = alp._fetch_page_title("https://example.com/redirect")
    assert title is None


def test_fetch_page_title_returns_none_for_empty_title_tag():
    # An empty <title></title> must not publish an empty string as a title.
    with patch("agents.agent_linkedin_post.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            text="<html><head><title>   </title></head></html>", url="https://x"
        )
        title, _ = alp._fetch_page_title("https://example.com/redirect")
    assert title is None


def test_fetch_page_title_falls_back_to_og_title_when_title_tag_missing():
    # Spec 044 FR-001: a site that renders og:title for link previews but has
    # no <title> tag (common on bot-gated pages) must still yield a title.
    html_body = (
        '<html><head><meta property="og:title" content="Real Page Title"></head></html>'
    )
    with patch("agents.agent_linkedin_post.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(text=html_body, url="https://x")
        title, _ = alp._fetch_page_title("https://example.com/gated")
    assert title == "Real Page Title"


def test_fetch_page_title_falls_back_to_twitter_title_when_others_missing():
    # Spec 044 FR-001: twitter:title is the last fetched-metadata signal
    # tried, after <title> and og:title both come up empty.
    html_body = (
        '<html><head><meta name="twitter:title" content="Twitter Title Here">'
        "</head></html>"
    )
    with patch("agents.agent_linkedin_post.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(text=html_body, url="https://x")
        title, _ = alp._fetch_page_title("https://example.com/gated")
    assert title == "Twitter Title Here"


def test_fetch_page_title_prefers_title_tag_over_og_title():
    # <title> is tried first — a real og:title present alongside it must not
    # override the page's own <title> tag.
    html_body = (
        "<title>Real Title</title>"
        '<meta property="og:title" content="Different OG Title">'
    )
    with patch("agents.agent_linkedin_post.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(text=html_body, url="https://x")
        title, _ = alp._fetch_page_title("https://example.com/a")
    assert title == "Real Title"


def test_fetch_page_title_reads_og_title_regardless_of_attribute_order():
    # Real-world meta tags don't always put `content` last — parsing must not
    # depend on attribute order.
    html_body = '<meta content="Order Independent Title" property="og:title">'
    with patch("agents.agent_linkedin_post.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(text=html_body, url="https://x")
        title, _ = alp._fetch_page_title("https://example.com/a")
    assert title == "Order Independent Title"


# -- _domain_from_url (Spec 043 FR-001) --


def test_domain_from_url_strips_www_prefix():
    assert (
        alp._domain_from_url("https://www.ibm.com/think/topics/vibe-coding")
        == "ibm.com"
    )


def test_domain_from_url_leaves_bare_domain_unchanged():
    assert alp._domain_from_url("https://example.com/a") == "example.com"


def test_domain_from_url_falls_back_to_raw_url_when_unparseable():
    # An input with no parseable network location must not produce an empty
    # string — fall back to the raw URL itself.
    assert alp._domain_from_url("not-a-url") == "not-a-url"


# -- _is_descriptive_title (Spec 044 FR-002) --


def test_is_descriptive_title_rejects_bare_domain_label():
    # "Reddit" for reddit.com is exactly the pattern this spec eliminates.
    assert alp._is_descriptive_title("Reddit", "reddit.com") is False


def test_is_descriptive_title_rejects_full_domain_restated():
    # Gemini/Grok's raw seed titles are the full domain itself (e.g.
    # "reddit.com") — this must be rejected too, not just the bare label.
    assert alp._is_descriptive_title("reddit.com", "reddit.com") is False


def test_is_descriptive_title_rejects_empty_or_none():
    # An empty, None, or whitespace-only title must never be treated as a
    # real candidate, regardless of the domain it's checked against.
    assert alp._is_descriptive_title("", "reddit.com") is False
    assert alp._is_descriptive_title(None, "reddit.com") is False
    assert alp._is_descriptive_title("   ", "reddit.com") is False


def test_is_descriptive_title_accepts_label_within_a_longer_title():
    # Containing the domain label is not disqualifying — only the title
    # being *only* the label is.
    assert (
        alp._is_descriptive_title("TechCrunch: AI slop is everywhere", "techcrunch.com")
        is True
    )


def test_is_descriptive_title_accepts_short_substantive_title():
    # Brevity alone must not be disqualifying.
    assert alp._is_descriptive_title("AI Bubble", "fidelity.com") is True


# -- _humanize_slug (Spec 044 FR-003/FR-004) --


def test_humanize_slug_converts_descriptive_path_segment():
    # A real Facebook-style slug (from the spec's own failing example) must
    # turn into readable prose once separators become spaces.
    url = "https://www.facebook.com/newshour/posts/slop-defined-as-digital-content-of-low-quality/1326081292720447/"
    humanized = alp._humanize_slug(url)
    assert humanized == "Slop defined as digital content of low quality"


def test_humanize_slug_skips_trailing_numeric_id_for_earlier_segment():
    # A trailing numeric ID segment (e.g. a Facebook post ID) must be
    # skipped in favour of the earlier, descriptive segment.
    url = "https://x.com/a/gen-z-workers-sabotage-ai-rollout-backlash/1234567890/"
    humanized = alp._humanize_slug(url)
    assert humanized is not None
    assert "1234567890" not in humanized


def test_humanize_slug_rejects_pure_numeric_or_hex_like_segment():
    # SC: a ScienceDirect-style PII code has no real words at all.
    assert (
        alp._humanize_slug(
            "https://sciencedirect.com/science/article/abs/pii/S2666799123000436"
        )
        is None
    )


def test_humanize_slug_rejects_segment_below_minimum_word_count():
    # A short segment like "ai-bubble" (2 words) must not qualify on its own
    # when nothing else in the path does either.
    assert alp._humanize_slug("https://fidelity.com/ai-bubble") is None


def test_humanize_slug_returns_none_for_path_with_no_segments():
    # A bare-root URL (no path at all) has nothing to derive a slug from.
    assert alp._humanize_slug("https://reddit.com") is None
    assert alp._humanize_slug("https://reddit.com/") is None


# -- _split_source_titles_block (Spec 044 FR-007/FR-008/FR-010) --


def test_split_source_titles_block_extracts_url_title_pairs():
    # The marker must cleanly separate real summary prose from the
    # code-parseable url|title lines appended after it.
    text = (
        "Some real findings here.\n"
        "===SOURCE_TITLES===\n"
        "https://a.com/1 | A descriptive title for the first source\n"
        "https://b.com/2 | Another descriptive title\n"
    )
    summary, titles = alp._split_source_titles_block(text)
    assert summary == "Some real findings here."
    assert titles == {
        "https://a.com/1": "A descriptive title for the first source",
        "https://b.com/2": "Another descriptive title",
    }


def test_split_source_titles_block_missing_marker_returns_whole_text_and_empty_map():
    # FR: a missing block must not raise, and must leave the summary intact.
    summary, titles = alp._split_source_titles_block("Just findings, no block.")
    assert summary == "Just findings, no block."
    assert titles == {}


def test_split_source_titles_block_ignores_malformed_lines():
    # A line with no "|" delimiter must be skipped, not raise or corrupt
    # the parse of the well-formed lines around it.
    text = (
        "Findings.\n===SOURCE_TITLES===\nnot a valid line\n\n"
        "https://a.com/1 | Good title"
    )
    summary, titles = alp._split_source_titles_block(text)
    assert summary == "Findings."
    assert titles == {"https://a.com/1": "Good title"}


# -- _is_unresolved_redirect_wrapper (Spec 044 — live-confirmed fix) --


def test_is_unresolved_redirect_wrapper_true_when_fetch_never_left_the_wrapper():
    # Regression: confirmed live that when a fetch through Gemini's grounding
    # redirect host fails before any redirect resolves, _fetch_page_title
    # correctly returns the original wrapper URL unchanged (FR-014's "best
    # effort" case) — this must be recognised so slug humanisation never
    # runs on that URL's own opaque base64 path.
    wrapper_url = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AB12"
    assert alp._is_unresolved_redirect_wrapper(wrapper_url, wrapper_url) is True


def test_is_unresolved_redirect_wrapper_false_once_a_redirect_resolved():
    # Once the fetch actually followed the redirect to a real destination
    # (even if that destination then failed), slug humanisation should run
    # on the real destination — not be blocked by this check.
    wrapper_url = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AB12"
    real_destination = "https://real-site.com/a-real-article-title"
    assert alp._is_unresolved_redirect_wrapper(wrapper_url, real_destination) is False


def test_is_unresolved_redirect_wrapper_false_for_ordinary_direct_urls():
    # Grok's URLs are direct, not redirects — an unresolved fetch on a
    # direct URL must still be eligible for slug humanisation on that URL.
    direct_url = "https://example.com/a-real-article-title"
    assert alp._is_unresolved_redirect_wrapper(direct_url, direct_url) is False


# -- _resolve_sources (Spec 044 — the shared title-resolution chain) --


def test_resolve_sources_skips_slug_on_unresolved_redirect_wrapper():
    # Regression (live-confirmed): a fetch failure that never escapes
    # Gemini's grounding-redirect host must not publish that host's own
    # opaque path as a "humanised" title — it must fall through to the
    # provider-supplied title instead.
    wrapper_url = (
        "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"
        "AUZIYQGt-oxwjHMrxbxvz3sRpHLSjVkRPc1C5cuFhWBlpdPey6-real-long-token"
    )
    candidates = [("real-site.com", wrapper_url, "real-site.com")]
    provider_titles = {wrapper_url: "A real descriptive title from the provider"}
    with patch(
        "agents.agent_linkedin_post._fetch_page_title",
        return_value=(None, wrapper_url),
    ):
        resolved = alp._resolve_sources(candidates, provider_titles, do_fetch=True)
    assert resolved == [
        ResearchSource(
            title="real-site.com - A real descriptive title from the provider",
            url=wrapper_url,
        )
    ]


def test_resolve_sources_uses_descriptive_raw_candidate_without_fetching():
    # Claude's already-good citation title must be used as-is, with no fetch.
    candidates = [("A Real Title", "https://x.com/a", "x.com")]
    with patch("agents.agent_linkedin_post._fetch_page_title") as mock_fetch:
        resolved = alp._resolve_sources(candidates, {}, do_fetch=False)
    mock_fetch.assert_not_called()
    assert resolved == [
        ResearchSource(title="x.com - A Real Title", url="https://x.com/a")
    ]


def test_resolve_sources_falls_through_to_fetch_when_raw_candidate_is_domain_only():
    # A raw candidate that's just the bare domain (Gemini/Grok's seed) must
    # be rejected at step 1 and rescued by a descriptive live fetch.
    candidates = [("x.com", "https://x.com/a", "x.com")]
    with patch(
        "agents.agent_linkedin_post._fetch_page_title",
        return_value=("Fetched Title", "https://x.com/a"),
    ):
        resolved = alp._resolve_sources(candidates, {}, do_fetch=True)
    assert resolved == [
        ResearchSource(title="x.com - Fetched Title", url="https://x.com/a")
    ]


def test_resolve_sources_falls_through_to_slug_when_fetch_fails():
    # When the live fetch yields nothing, the chain must still recover a
    # descriptive title from the URL's own path before giving up.
    url = "https://x.com/a/gen-z-workers-sabotage-ai-rollout-backlash/"
    candidates = [("x.com", url, "x.com")]
    with patch(
        "agents.agent_linkedin_post._fetch_page_title", return_value=(None, url)
    ):
        resolved = alp._resolve_sources(candidates, {}, do_fetch=True)
    assert len(resolved) == 1
    assert resolved[0].title.startswith("x.com - Gen z workers sabotage")


def test_resolve_sources_falls_through_to_provider_title_when_slug_fails():
    # A ScienceDirect-style PII-code URL has no rescuing slug — the
    # provider's own same-call title must be the last real signal tried.
    url = "https://sciencedirect.com/science/article/abs/pii/S2666799123000436"
    candidates = [("sciencedirect.com", url, "sciencedirect.com")]
    provider_titles = {url: "A peer-reviewed study on AI content detection"}
    with patch(
        "agents.agent_linkedin_post._fetch_page_title", return_value=(None, url)
    ):
        resolved = alp._resolve_sources(candidates, provider_titles, do_fetch=True)
    assert resolved == [
        ResearchSource(
            title="sciencedirect.com - A peer-reviewed study on AI content detection",
            url=url,
        )
    ]


def test_resolve_sources_ignores_provider_title_for_unverified_url():
    # Spec 044 FR-008: a provider-titles entry for a URL that isn't one of
    # the candidates must never rescue a different source.
    url = "https://sciencedirect.com/science/article/abs/pii/S2666799123000436"
    candidates = [("sciencedirect.com", url, "sciencedirect.com")]
    provider_titles = {"https://not-this-one.com/x": "Some title"}
    with patch(
        "agents.agent_linkedin_post._fetch_page_title", return_value=(None, url)
    ):
        resolved = alp._resolve_sources(candidates, provider_titles, do_fetch=True)
    assert resolved == []


def test_resolve_sources_drops_source_with_nothing_descriptive_anywhere():
    # Spec 044 FR-011: a bare-root URL with no rescuing signal must be
    # dropped, not published as a bare domain.
    candidates = [("reddit.com", "https://reddit.com", "reddit.com")]
    with patch(
        "agents.agent_linkedin_post._fetch_page_title",
        return_value=(None, "https://reddit.com"),
    ):
        resolved = alp._resolve_sources(candidates, {}, do_fetch=True)
    assert resolved == []


def test_resolve_sources_one_source_dropping_does_not_affect_others():
    # Sources are resolved independently — one source having nothing
    # descriptive must not affect another source's own resolution.
    good_url = "https://x.com/a"
    bad_url = "https://reddit.com"
    candidates = [
        ("Good Real Title", good_url, "x.com"),
        ("reddit.com", bad_url, "reddit.com"),
    ]
    with patch(
        "agents.agent_linkedin_post._fetch_page_title", return_value=(None, bad_url)
    ):
        resolved = alp._resolve_sources(candidates, {}, do_fetch=True)
    assert resolved == [ResearchSource(title="x.com - Good Real Title", url=good_url)]


def test_resolve_sources_empty_list_returns_empty_list():
    # No candidates must not raise or spin up a thread pool for nothing.
    assert alp._resolve_sources([], {}, do_fetch=True) == []


def test_research_claude_success_returns_digest_and_usage():
    # A successful Claude web-search call must extract text and citations.
    provider = MagicMock(model_id="claude-sonnet-4-6")
    citation = MagicMock(url="https://example.com/c", title="C")
    text_block = MagicMock(type="text", text="Claude findings.", citations=[citation])
    response = MagicMock(content=[text_block])
    response.usage = MagicMock(input_tokens=50, output_tokens=75)
    provider.client.messages.create.return_value = response
    digest, usage = alp._research_claude(provider, "Topic: X")
    assert digest.summary == "Claude findings."
    assert digest.sources[0].url == "https://example.com/c"
    assert usage.model == "claude-sonnet-4-6"


def test_research_claude_exception_returns_none():
    # An API exception must soft-fail rather than propagate.
    provider = MagicMock(model_id="claude-sonnet-4-6")
    provider.client.messages.create.side_effect = RuntimeError("boom")
    digest, usage = alp._research_claude(provider, "Topic: X")
    assert digest is None
    assert usage is None


def test_research_grok_success_returns_digest_and_usage():
    # A successful Grok Responses-API web_search call must extract text and
    # citations via output_text / output annotations. The fetch is mocked to
    # return a descriptive title directly so this test makes no real network
    # call — the full resolution chain is covered separately above.
    provider = MagicMock(model_id="grok-4.3")
    annotation = MagicMock(url="https://example.com/e", title="E")
    content = MagicMock(annotations=[annotation])
    item = MagicMock(content=[content])
    response = MagicMock(output=[item], output_text="Grok findings.")
    response.usage = MagicMock(input_tokens=40, output_tokens=60)
    provider.client.responses.create.return_value = response
    with patch(
        "agents.agent_linkedin_post._fetch_page_title",
        return_value=("Real Page Title", "https://example.com/e"),
    ):
        digest, usage = alp._research_grok(provider, "Topic: X")
    assert digest.summary == "Grok findings."
    assert digest.sources[0].url == "https://example.com/e"
    assert digest.sources[0].title == "example.com - Real Page Title"
    assert usage.model == "grok-4.3"


def test_research_grok_empty_output_text_returns_none():
    # No output_text must be treated as a failed research attempt.
    provider = MagicMock(model_id="grok-4.3")
    provider.client.responses.create.return_value = MagicMock(output_text="")
    digest, usage = alp._research_grok(provider, "Topic: X")
    assert digest is None


def test_research_grok_exception_returns_none():
    # An API exception (e.g. the confirmed-live HTTP 410 on the deprecated Live
    # Search path) must soft-fail rather than propagate.
    provider = MagicMock(model_id="grok-4.3")
    provider.client.responses.create.side_effect = RuntimeError("410 deprecated")
    digest, usage = alp._research_grok(provider, "Topic: X")
    assert digest is None
    assert usage is None


# -- _research_for_provider dispatch --


def test_research_for_provider_dispatches_by_type():
    # Each concrete provider type must route to its own research implementation
    # regardless of position in the panelist list.
    gemini = GeminiProvider("gemini-2.5-flash")
    claude = ClaudeProvider("claude-sonnet-4-6")
    grok = GrokProvider("grok-4.3")
    with (
        patch(
            "agents.agent_linkedin_post._research_gemini", return_value=(None, None)
        ) as m_gemini,
        patch(
            "agents.agent_linkedin_post._research_claude", return_value=(None, None)
        ) as m_claude,
        patch(
            "agents.agent_linkedin_post._research_grok", return_value=(None, None)
        ) as m_grok,
    ):
        alp._research_for_provider(gemini, "T", None)
        alp._research_for_provider(claude, "T", None)
        alp._research_for_provider(grok, "T", None)
    m_gemini.assert_called_once()
    m_claude.assert_called_once()
    m_grok.assert_called_once()


def test_research_for_provider_unknown_type_returns_none():
    # A provider type this feature doesn't recognise must degrade cleanly.
    digest, usage, duration = alp._research_for_provider(object(), "T", None)
    assert digest is None
    assert usage is None
    assert duration >= 0.0


def test_research_for_provider_reports_its_own_wall_time():
    # Regression: the duration must be measured inside this call, not by the
    # caller's fixed-order result-collection loop (which could see 0.0s for a
    # provider that finished before the caller got around to checking it).
    with patch(
        "agents.agent_linkedin_post._research_gemini", return_value=(None, None)
    ):
        _, _, duration = alp._research_for_provider(
            GeminiProvider("gemini-2.5-flash"), "T", None
        )
    assert duration >= 0.0


# -- research_all_panelists --


def test_research_all_panelists_runs_every_slot():
    # Every panelist slot's primary provider must get its own research attempt.
    providers = _panelist_providers()
    with patch(
        "agents.agent_linkedin_post._research_for_provider",
        return_value=(ResearchDigest(summary="s", sources=[]), None, 1.5),
    ) as mock_research:
        digests, telemetries = alp.research_all_panelists(
            providers, "Topic", None, [_provider("agg")]
        )
    assert mock_research.call_count == 3
    assert len(digests) == 3
    assert all(d is not None for d in digests)
    assert len(telemetries) == 3
    assert all(t.duration_seconds == 1.5 for t in telemetries)


def test_research_all_panelists_one_failure_yields_none_for_that_slot():
    # One provider failing must not affect the others' results.
    providers = _panelist_providers()

    def _side_effect(provider, topic, angles):
        if provider.model_id == "model-b":
            return None, None, 0.5
        return ResearchDigest(summary="ok", sources=[]), None, 1.0

    with patch(
        "agents.agent_linkedin_post._research_for_provider", side_effect=_side_effect
    ):
        digests, _ = alp.research_all_panelists(
            providers, "Topic", None, [_provider("agg")]
        )
    assert digests[0] is not None
    assert digests[1] is None
    assert digests[2] is not None


def test_research_all_panelists_filters_paywalled_source():
    # Spec 042 amendment 2 FR-026: a source whose domain is already cached as
    # paywalled must be stripped from its digest before the function returns.
    providers = _panelist_providers()
    digest = ResearchDigest(
        summary="s", sources=[ResearchSource(title="T", url="https://paywalled.com/a")]
    )
    with (
        patch(
            "agents.agent_linkedin_post._research_for_provider",
            return_value=(digest, None, 1.0),
        ),
        patch(
            "agents.agent_linkedin_post._load_cached_domains",
            return_value={"paywalled.com": {"paywalled": True, "reliability": "high"}},
        ),
        patch("agents.agent_linkedin_post._classify_domains_panel") as mock_classify,
    ):
        digests, _ = alp.research_all_panelists(
            providers, "Topic", None, [_provider("agg")]
        )
    mock_classify.assert_not_called()
    assert all(d.sources == [] for d in digests)


def test_research_all_panelists_classifies_and_caches_unknown_domain():
    # An unclassified domain must go through the classification panel, get
    # saved to the cache, and be excluded this run if classified low-quality.
    providers = _panelist_providers()
    digest = ResearchDigest(
        summary="s",
        sources=[ResearchSource(title="T", url="https://sketchy.example/a")],
    )
    with (
        patch(
            "agents.agent_linkedin_post._research_for_provider",
            return_value=(digest, None, 1.0),
        ),
        patch("agents.agent_linkedin_post._load_cached_domains", return_value={}),
        patch(
            "agents.agent_linkedin_post._classify_domains_panel",
            return_value=(
                {"sketchy.example": {"paywalled": False, "reliability": "low"}},
                AgentTelemetry(
                    agent_name="Domain Classification",
                    duration_seconds=1.0,
                    iterations=1,
                ),
            ),
        ) as mock_classify,
        patch("agents.agent_linkedin_post._save_classified_domains") as mock_save,
    ):
        digests, _ = alp.research_all_panelists(
            providers, "Topic", None, [_provider("agg")]
        )
    mock_classify.assert_called_once()
    assert mock_classify.call_args.args[0] == ["sketchy.example"]
    mock_save.assert_called_once_with(
        {"sketchy.example": {"paywalled": False, "reliability": "low"}}
    )
    assert all(d.sources == [] for d in digests)


def test_research_all_panelists_includes_classification_cost_in_telemetry():
    # Regression: the domain-classification panel's own real cost was being
    # silently dropped — confirmed live, where a genuine ~90s/$0.02 panel run
    # never appeared in the run's cost summary. Its telemetry must be
    # included in the returned list, not just the per-provider research ones.
    providers = _panelist_providers()
    digest = ResearchDigest(
        summary="s",
        sources=[ResearchSource(title="T", url="https://sketchy.example/a")],
    )
    classification_tel = AgentTelemetry(
        agent_name="Domain Classification", duration_seconds=42.0, iterations=3
    )
    with (
        patch(
            "agents.agent_linkedin_post._research_for_provider",
            return_value=(digest, None, 1.0),
        ),
        patch("agents.agent_linkedin_post._load_cached_domains", return_value={}),
        patch(
            "agents.agent_linkedin_post._classify_domains_panel",
            return_value=(
                {"sketchy.example": {"paywalled": False, "reliability": "low"}},
                classification_tel,
            ),
        ),
        patch("agents.agent_linkedin_post._save_classified_domains"),
    ):
        _, telemetries = alp.research_all_panelists(
            providers, "Topic", None, [_provider("agg")]
        )
    assert classification_tel in telemetries


def test_research_all_panelists_keeps_eligible_source():
    # A domain classified as neither paywalled nor low-reliability must survive.
    providers = _panelist_providers()
    source = ResearchSource(title="T", url="https://good.example/a")
    digest = ResearchDigest(summary="s", sources=[source])
    with (
        patch(
            "agents.agent_linkedin_post._research_for_provider",
            return_value=(digest, None, 1.0),
        ),
        patch(
            "agents.agent_linkedin_post._load_cached_domains",
            return_value={"good.example": {"paywalled": False, "reliability": "high"}},
        ),
        patch("agents.agent_linkedin_post._classify_domains_panel") as mock_classify,
    ):
        digests, _ = alp.research_all_panelists(
            providers, "Topic", None, [_provider("agg")]
        )
    mock_classify.assert_not_called()
    assert digests[0].sources == [source]


# -- _panelist_research_context --


def test_panelist_research_context_with_digest_includes_findings_and_sources():
    digest = ResearchDigest(
        summary="Some findings.",
        sources=[ResearchSource(title="T", url="https://x.com")],
    )
    context = alp._panelist_research_context(digest)
    assert "Some findings." in context
    assert "https://x.com" in context


def test_panelist_research_context_without_digest_forbids_fabricated_facts():
    # FR-005: an ungrounded panelist must be told plainly not to present
    # unverified claims as researched fact.
    context = alp._panelist_research_context(None)
    assert "No web search results were available" in context


# -- _plan_angles --


def _fake_loop_output(verdict: str) -> LoopOutput:
    return LoopOutput(
        verdict=verdict,
        log=ConversationLog(loop_name="x"),
        telemetry=AgentTelemetry(
            agent_name="LinkedIn Angle Planning", duration_seconds=1.0, iterations=2
        ),
    )


def test_plan_angles_includes_mandatory_operator_angles():
    # FR-007: operator-supplied angles must be marked mandatory in the shared
    # initial_input seen by every panelist.
    providers = _panelist_providers()
    digests = [None, None, None]
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output("ANGLE: A\nFOCUS: b")
        alp._plan_angles("Topic", digests, ["angle one"], providers, [_provider("agg")])
    initial_input = mock_cls.return_value.run.call_args.args[0]
    assert "angle one" in initial_input
    assert "MUST" in initial_input


def test_plan_angles_embeds_each_panelists_own_digest_in_its_own_prompt():
    # Each panelist's system prompt must carry its own research, not a shared one.
    providers = _panelist_providers()
    digests = [
        ResearchDigest(summary="Findings for A", sources=[]),
        None,
        ResearchDigest(summary="Findings for C", sources=[]),
    ]
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output("ANGLE: A\nFOCUS: b")
        alp._plan_angles("Topic", digests, None, providers, [_provider("agg")])
    _, kwargs = mock_cls.call_args
    prompts = [p.system_prompt for p in kwargs["panelists"]]
    assert "Findings for A" in prompts[0]
    assert "No web search results were available" in prompts[1]
    assert "Findings for C" in prompts[2]


def test_plan_angles_panel_failure_returns_none():
    # FR-008: total panel failure must soft-fail, not raise.
    providers = _panelist_providers()
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.side_effect = RuntimeError("all panelists failed")
        result, telemetry = alp._plan_angles(
            "Topic", [None, None, None], None, providers, [_provider("agg")]
        )
    assert result is None
    assert telemetry.agent_name == "LinkedIn Angle Planning"


# -- _write_article --


def test_write_article_uses_120s_panelist_timeout():
    # FR-009: the writing panel must override the 60s class default to 120s.
    providers = _panelist_providers()
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output(
            "===TITLE===\nT\n===BODY===\nB\n===COMMENT===\nC?\n===NOTIFICATION===\nN"
        )
        alp._write_article(
            "Topic",
            [None, None, None],
            "ANGLE: A",
            BRIEF,
            providers,
            [_provider("agg")],
            [],
        )
    _, kwargs = mock_cls.call_args
    assert kwargs["panelist_timeout"] == 120


def test_write_article_passes_round_validator():
    # Spec 042 amendment 2 FR-028: the writing panel must be constructed with
    # the citation round_validator, not left to enforce nothing mid-round.
    providers = _panelist_providers()
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output(
            "===TITLE===\nT\n===BODY===\nB\n===COMMENT===\nC?\n===NOTIFICATION===\nN"
        )
        alp._write_article(
            "Topic",
            [None, None, None],
            "ANGLE: A",
            BRIEF,
            providers,
            [_provider("agg")],
            [],
        )
    _, kwargs = mock_cls.call_args
    assert kwargs["round_validator"] is alp._citation_round_validator


def test_write_article_panel_failure_returns_none():
    providers = _panelist_providers()
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.side_effect = RuntimeError("all panelists failed")
        sections, telemetry = alp._write_article(
            "Topic",
            [None, None, None],
            "ANGLE: A",
            BRIEF,
            providers,
            [_provider("agg")],
            [],
        )
    assert sections is None
    assert telemetry.agent_name == "LinkedIn Article Writing"


# -- _merge_sources / _build_sources_section --


def test_merge_sources_dedupes_across_digests_and_skips_none():
    d1 = ResearchDigest(
        summary="", sources=[ResearchSource(title="A", url="https://x.com/1")]
    )
    d2 = None
    d3 = ResearchDigest(
        summary="",
        sources=[
            ResearchSource(title="A dup", url="https://x.com/1"),
            ResearchSource(title="B", url="https://x.com/2"),
        ],
    )
    merged = alp._merge_sources([d1, d2, d3])
    urls = [s.url for s in merged]
    assert urls == ["https://x.com/1", "https://x.com/2"]


def test_build_sources_section_empty_list_returns_empty_string():
    assert alp._build_sources_section([]) == ""


def test_build_sources_section_lists_every_source_as_markdown_link():
    sources = [ResearchSource(title="A", url="https://x.com/1")]
    section = alp._build_sources_section(sources)
    assert "[A](https://x.com/1)" in section


def test_build_sources_section_numbers_match_list_order():
    # Spec 042 amendment 2 FR-029.4: the visible numbering must match the
    # candidates' order exactly, so it lines up with in-text [N] markers.
    sources = [
        ResearchSource(title="First", url="https://x.com/1"),
        ResearchSource(title="Second", url="https://x.com/2"),
    ]
    section = alp._build_sources_section(sources)
    assert section.splitlines()[2].startswith("1. ")
    assert section.splitlines()[3].startswith("2. ")


# -- _build_citable_sources_block / _count_citations_per_section --


def test_build_citable_sources_block_empty_list_returns_empty_string():
    # No candidates at all must produce no block — nothing for the writer to
    # cite, so the prompt shouldn't imply otherwise.
    assert alp._build_citable_sources_block([]) == ""


def test_build_citable_sources_block_numbers_from_one():
    # FR-027: the citable list must be 1-based and stable, matching the
    # numbering the writer is told to cite against.
    sources = [
        ResearchSource(title="First", url="https://x.com/1"),
        ResearchSource(title="Second", url="https://x.com/2"),
    ]
    block = alp._build_citable_sources_block(sources)
    assert "[1] First (https://x.com/1)" in block
    assert "[2] Second (https://x.com/2)" in block


def test_count_citations_per_section_splits_on_h2_headings():
    # Each markdown H2 section is counted independently, so a validator can
    # tell a compliant section from one that over-cites.
    text = "## First\nCites [1] and [2] here.\n\n## Second\nCites [3] only."
    assert alp._count_citations_per_section(text) == [0, 2, 1]


# -- _citation_round_validator (Spec 042 amendment 2 FR-028) --


def test_citation_round_validator_flags_section_over_limit():
    # FR-028: a body section citing more than the per-section limit must
    # produce feedback for that panelist, naming the limit so it can comply.
    verdict = (
        "===TITLE===\nT\n===EXECUTIVE_SUMMARY===\nS\n===BODY===\n"
        "## Angle One\nCites [1], [2], and [3] — too many.\n"
        "===COMMENT===\nC?\n===NOTIFICATION===\nN"
    )
    feedback = alp._citation_round_validator({"pa": verdict})
    assert "pa" in feedback
    assert "2" in feedback["pa"]


def test_citation_round_validator_silent_when_within_limit():
    # A compliant panelist must get no feedback at all — the validator should
    # never nag a panelist that's already within the per-section limit.
    verdict = (
        "===TITLE===\nT\n===EXECUTIVE_SUMMARY===\nS\n===BODY===\n"
        "## Angle One\nCites [1] and [2] only.\n"
        "===COMMENT===\nC?\n===NOTIFICATION===\nN"
    )
    assert alp._citation_round_validator({"pa": verdict}) == {}


# -- _extract_and_renumber_citations (Spec 042 amendment 2 FR-029) --

_FIVE_CANDIDATES = [
    ResearchSource(title=f"S{i}", url=f"https://x.com/{i}") for i in range(1, 6)
]


def test_extract_and_renumber_citations_basic_renumbering():
    # SC-014: citing [2] then [5] (skipping [1]) must renumber to [1] then [2]
    # in the final text, matching the Sources list built from the same order.
    body = "First claim [2]. Second claim [5]."
    new_summary, new_body, sources = alp._extract_and_renumber_citations(
        "", body, _FIVE_CANDIDATES
    )
    assert "[1]" in new_body and "[2]" in new_body
    assert "[5]" not in new_body
    assert [s.url for s in sources] == ["https://x.com/2", "https://x.com/5"]


def test_extract_and_renumber_citations_strips_invalid_index():
    # SC-014: a citation number outside the candidate range must be stripped
    # entirely from the text, not left dangling or crash the pipeline.
    body = "Valid claim [2]. Bogus claim [99]."
    _, new_body, sources = alp._extract_and_renumber_citations(
        "", body, _FIVE_CANDIDATES
    )
    assert "[99]" not in new_body
    assert "[1]" in new_body
    assert len(sources) == 1


def test_extract_and_renumber_citations_caps_at_max_total():
    # SC-015: more than _MAX_TOTAL_CITATIONS distinct valid citations must be
    # truncated to the first N by first-appearance order.
    many_candidates = [
        ResearchSource(title=f"S{i}", url=f"https://x.com/{i}") for i in range(1, 20)
    ]
    body = " ".join(f"Claim [{i}]." for i in range(1, 18))
    _, new_body, sources = alp._extract_and_renumber_citations(
        "", body, many_candidates
    )
    assert len(sources) == alp._MAX_TOTAL_CITATIONS
    assert f"[{alp._MAX_TOTAL_CITATIONS}]" in new_body
    assert f"[{alp._MAX_TOTAL_CITATIONS + 1}]" not in new_body


def test_extract_and_renumber_citations_considers_summary_before_body():
    # A citation appearing first in the summary must be numbered [1], even if
    # the same source is cited again later in the body.
    summary = "Overview references [3] directly."
    body = "Body also cites [3] and introduces [1]."
    new_summary, new_body, sources = alp._extract_and_renumber_citations(
        summary, body, _FIVE_CANDIDATES
    )
    assert "[1]" in new_summary
    assert sources[0].url == "https://x.com/3"


def test_extract_and_renumber_citations_no_citations_yields_empty_sources():
    # No [N] markers anywhere must produce an empty Sources list, not an
    # error or a spurious entry.
    _, _, sources = alp._extract_and_renumber_citations("", "No citations here.", [])
    assert sources == []


# -- DuckDB domain cache (Spec 042 amendment 2 FR-025) --


def test_domain_cache_round_trip(tmp_path, monkeypatch):
    # A saved classification must be loadable afterward, from a fresh
    # connection, exactly as written.
    monkeypatch.setattr(alp, "_DOMAIN_CACHE_PATH", str(tmp_path / "cache.duckdb"))
    alp._save_classified_domains(
        {"nytimes.com": {"paywalled": True, "reliability": "high"}}
    )
    loaded = alp._load_cached_domains({"nytimes.com", "unknown.com"})
    assert loaded == {"nytimes.com": {"paywalled": True, "reliability": "high"}}


def test_load_cached_domains_empty_set_returns_empty_dict():
    # An empty query set must short-circuit rather than open a DB connection.
    assert alp._load_cached_domains(set()) == {}


def test_save_classified_domains_empty_dict_is_a_noop(tmp_path, monkeypatch):
    # Saving nothing must not even create the cache file — avoids an empty
    # DuckDB file appearing on disk for runs with no new domains to classify.
    monkeypatch.setattr(alp, "_DOMAIN_CACHE_PATH", str(tmp_path / "cache.duckdb"))
    alp._save_classified_domains({})
    assert not (tmp_path / "cache.duckdb").exists()


# -- _classify_domains_panel (Spec 042 amendment 2 FR-026.2) --


def test_classify_domains_panel_empty_list_returns_empty_dict():
    # No domains to classify must skip the panel entirely, not run an empty
    # deliberation.
    result, telemetry = alp._classify_domains_panel(
        [], _panelist_providers(), [_provider("agg")]
    )
    assert result == {}
    assert telemetry.agent_name == "Domain Classification"


def test_classify_domains_panel_uses_panel_timeout_and_iterations():
    # FR-026.2: the classification panel must use its own dedicated timeout
    # and iteration count, not whatever FairParallelPanel defaults to.
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output(
            '{"a.com": {"paywalled": false, "reliability": "high"}}'
        )
        alp._classify_domains_panel(
            ["a.com"], _panelist_providers(), [_provider("agg")]
        )
    _, kwargs = mock_cls.call_args
    assert kwargs["panelist_timeout"] == 90
    assert kwargs["iterations"] == 3


def test_classify_domains_panel_parses_verdict_json():
    # A well-formed verdict must translate directly into the classification
    # dict callers rely on for filtering.
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output(
            '{"a.com": {"paywalled": true, "reliability": "low"}}'
        )
        result, _ = alp._classify_domains_panel(
            ["a.com"], _panelist_providers(), [_provider("agg")]
        )
    assert result == {"a.com": {"paywalled": True, "reliability": "low"}}


def test_classify_domains_panel_returns_real_telemetry_on_success():
    # Regression: the panel's own AgentTelemetry (and its real cost) must be
    # returned, not discarded — this was silently dropped before being caught
    # live (a real ~90s/$0.02 panel run never appeared in the cost summary).
    real_tel = AgentTelemetry(
        agent_name="Domain Classification", duration_seconds=42.0, iterations=3
    )
    loop_output = LoopOutput(
        verdict='{"a.com": {"paywalled": true, "reliability": "low"}}',
        log=ConversationLog(loop_name="x"),
        telemetry=real_tel,
    )
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = loop_output
        _, telemetry = alp._classify_domains_panel(
            ["a.com"], _panelist_providers(), [_provider("agg")]
        )
    assert telemetry is real_tel


def test_classify_domains_panel_fails_open_on_panel_exception():
    # SC-013: total panel failure must return {} (fail open), never raise —
    # the run must still be able to proceed with unclassified domains.
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.side_effect = RuntimeError("all panelists failed")
        result, telemetry = alp._classify_domains_panel(
            ["a.com"], _panelist_providers(), [_provider("agg")]
        )
    assert result == {}
    assert telemetry.agent_name == "Domain Classification"


def test_classify_domains_panel_fails_open_on_invalid_json():
    # A verdict that isn't valid JSON must also fail open, not crash the run.
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output("not json at all")
        result, _ = alp._classify_domains_panel(
            ["a.com"], _panelist_providers(), [_provider("agg")]
        )
    assert result == {}


def test_classify_domains_panel_skips_entries_with_bad_reliability_value():
    # A reliability value other than "high"/"low" must be rejected per-domain
    # rather than silently accepted or crashing the whole parse.
    with patch("agents.agent_linkedin_post.FairParallelPanel") as mock_cls:
        mock_cls.return_value.run.return_value = _fake_loop_output(
            '{"a.com": {"paywalled": false, "reliability": "medium"}}'
        )
        result, _ = alp._classify_domains_panel(
            ["a.com"], _panelist_providers(), [_provider("agg")]
        )
    assert result == {}


# -- _assemble_article --


def test_assemble_article_includes_disclosure_and_omits_empty_sources():
    sections = {"TITLE": "T", "BODY": "Body text.", "COMMENT": "Question?"}
    article = alp._assemble_article(sections, [], RunTelemetry())
    assert "independently researched" in article
    assert "## Sources" not in article


def test_assemble_article_includes_sources_section_when_present():
    sections = {"TITLE": "T", "BODY": "Body text.", "COMMENT": "Question?"}
    sources = [ResearchSource(title="A", url="https://x.com/1")]
    article = alp._assemble_article(sections, sources, RunTelemetry())
    assert "## Sources" in article
    assert "https://x.com/1" in article


def test_assemble_article_places_executive_summary_after_title_before_body():
    # FR-020/SC-008: when the writer panel supplies EXECUTIVE_SUMMARY, it must
    # appear as its own heading right after the title and before the body.
    sections = {
        "TITLE": "T",
        "EXECUTIVE_SUMMARY": "The short version of the whole argument.",
        "BODY": "Body text.",
        "COMMENT": "Question?",
    }
    article = alp._assemble_article(sections, [], RunTelemetry())
    assert article.index("## Executive Summary") > article.index("# T")
    assert article.index("The short version") > article.index("## Executive Summary")
    assert article.index("Body text.") > article.index("The short version")


def test_assemble_article_omits_executive_summary_heading_when_absent():
    # SC-009: no EXECUTIVE_SUMMARY key at all must not publish a blank heading.
    sections = {"TITLE": "T", "BODY": "Body text.", "COMMENT": "Question?"}
    article = alp._assemble_article(sections, [], RunTelemetry())
    assert "## Executive Summary" not in article


def test_assemble_article_omits_executive_summary_heading_when_blank():
    # SC-009: a present-but-empty/whitespace EXECUTIVE_SUMMARY is treated the
    # same as absent — never publish a heading with nothing under it.
    sections = {
        "TITLE": "T",
        "EXECUTIVE_SUMMARY": "   ",
        "BODY": "Body text.",
        "COMMENT": "Question?",
    }
    article = alp._assemble_article(sections, [], RunTelemetry())
    assert "## Executive Summary" not in article


def test_assemble_article_moves_metrics_and_disclosure_to_behind_the_scenes():
    # FR-022/SC-010: Pipeline Metrics and the disclosure must land inside the
    # Behind the Scenes section, at the bottom, not near the top of the article.
    sections = {"TITLE": "T", "BODY": "Body text.", "COMMENT": "Question?"}
    telemetry = RunTelemetry()
    article = alp._assemble_article(sections, [], telemetry)
    behind_scenes_index = article.index("Behind the Scenes")
    assert article.index("Pipeline Execution Metrics") > behind_scenes_index
    assert article.index("independently researched") > behind_scenes_index


def test_assemble_article_metrics_and_disclosure_no_longer_lead_the_article():
    # Regression guard for the specific bug being fixed: these two lines used to
    # sit immediately after the title — confirm they no longer come before the
    # body/Executive Summary content.
    sections = {
        "TITLE": "T",
        "EXECUTIVE_SUMMARY": "Summary text.",
        "BODY": "Body text.",
        "COMMENT": "Question?",
    }
    article = alp._assemble_article(sections, [], RunTelemetry())
    assert article.index("Summary text.") < article.index("Pipeline Execution Metrics")
    assert article.index("Body text.") < article.index("independently researched")


def test_assemble_article_full_section_order():
    # FR-023: end-to-end ordering — title, summary, body/closing, sources,
    # behind-the-scenes (metrics + disclosure last) — exactly in that order.
    sections = {
        "TITLE": "T",
        "EXECUTIVE_SUMMARY": "Summary text.",
        "BODY": "Body text.",
        "COMMENT": "Question?",
    }
    sources = [ResearchSource(title="A", url="https://x.com/1")]
    article = alp._assemble_article(sections, sources, RunTelemetry())
    indices = [
        article.index("# T"),
        article.index("## Executive Summary"),
        article.index("Body text."),
        article.index("## Sources"),
        article.index("Behind the Scenes"),
        article.index("Pipeline Execution Metrics"),
        article.index("independently researched"),
    ]
    assert indices == sorted(indices)


# -- generate_linkedin_post: end-to-end soft-failure chaining --


def test_generate_linkedin_post_all_research_failure_returns_empty_and_skips_panels():
    # FR-008: total research failure must skip both panels entirely.
    providers = _panelist_providers()
    telemetry = RunTelemetry()
    with (
        patch(
            "agents.agent_linkedin_post.research_all_panelists",
            return_value=(
                [None, None, None],
                [AgentTelemetry(agent_name="r", duration_seconds=0, iterations=0)] * 3,
            ),
        ),
        patch("agents.agent_linkedin_post._plan_angles") as mock_plan,
        patch("agents.agent_linkedin_post._write_article") as mock_write,
    ):
        article, notification = alp.generate_linkedin_post(
            BRIEF, "Topic", telemetry, providers, [_provider("agg")]
        )
    assert article == ""
    assert notification == ""
    mock_plan.assert_not_called()
    mock_write.assert_not_called()


def test_generate_linkedin_post_angle_planning_failure_skips_writing():
    providers = _panelist_providers()
    telemetry = RunTelemetry()
    digest = ResearchDigest(summary="s", sources=[])
    with (
        patch(
            "agents.agent_linkedin_post.research_all_panelists",
            return_value=([digest, None, None], []),
        ),
        patch(
            "agents.agent_linkedin_post._plan_angles",
            return_value=(
                None,
                AgentTelemetry(agent_name="p", duration_seconds=0, iterations=0),
            ),
        ),
        patch("agents.agent_linkedin_post._write_article") as mock_write,
    ):
        article, notification = alp.generate_linkedin_post(
            BRIEF, "Topic", telemetry, providers, [_provider("agg")]
        )
    assert article == ""
    mock_write.assert_not_called()


def test_generate_linkedin_post_full_success_assembles_article():
    providers = _panelist_providers()
    telemetry = RunTelemetry()
    digest = ResearchDigest(
        summary="s", sources=[ResearchSource(title="A", url="https://x.com/1")]
    )
    sections = {
        "TITLE": "A Real Title",
        "BODY": "Real body citing [1] a source.",
        "COMMENT": "Question?",
        "NOTIFICATION": "Read this.",
    }
    with (
        patch(
            "agents.agent_linkedin_post.research_all_panelists",
            return_value=([digest, digest, digest], []),
        ),
        patch(
            "agents.agent_linkedin_post._plan_angles",
            return_value=(
                "ANGLE: A\nFOCUS: b",
                AgentTelemetry(agent_name="p", duration_seconds=0, iterations=1),
            ),
        ),
        patch(
            "agents.agent_linkedin_post._write_article",
            return_value=(
                sections,
                AgentTelemetry(agent_name="w", duration_seconds=0, iterations=1),
            ),
        ),
    ):
        article, notification = alp.generate_linkedin_post(
            BRIEF, "Topic", telemetry, providers, [_provider("agg")]
        )
    assert "A Real Title" in article
    assert "https://x.com/1" in article
    assert notification == "Read this."


def test_generate_linkedin_post_strips_empty_angle_strings():
    # Edge case: empty/whitespace-only --angle entries must be dropped, not
    # passed through to the panels as if they were real angles.
    providers = _panelist_providers()
    telemetry = RunTelemetry()
    with patch(
        "agents.agent_linkedin_post.research_all_panelists",
        return_value=([None, None, None], []),
    ) as mock_research:
        alp.generate_linkedin_post(
            BRIEF, "Topic", telemetry, providers, [_provider("agg")], angles=["  ", ""]
        )
    call_angles = mock_research.call_args.args[2]
    assert call_angles is None
