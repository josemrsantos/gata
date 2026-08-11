from unittest.mock import MagicMock, patch

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
    assert query == "Topic: Vibe coding"


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
    # across all blocks, not just the first.
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


# -- _extract_grok_sources --


def test_extract_grok_sources_from_output_annotations():
    # xAI's Agent Tools / Responses API attaches citations as annotations on an
    # output message's content — must produce usable ResearchSource entries.
    # `title` on the real annotation is just the footnote number, not a page
    # title, so the URL itself is used as the display title (confirmed live).
    annotation = MagicMock(url="https://example.com/c", title="1")
    content = MagicMock(annotations=[annotation])
    item = MagicMock(content=[content])
    response = MagicMock(output=[item])
    sources = alp._extract_grok_sources(response)
    assert sources == [
        ResearchSource(title="https://example.com/c", url="https://example.com/c")
    ]


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
    # non-trivial usage record for cost tracking.
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
    digest, usage = alp._research_gemini(provider, "Topic: X")
    assert digest.summary == "Findings here."
    assert digest.sources[0].url == "https://example.com/g"
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
    # citations via output_text / output annotations.
    provider = MagicMock(model_id="grok-4.3")
    annotation = MagicMock(url="https://example.com/e", title="E")
    content = MagicMock(annotations=[annotation])
    item = MagicMock(content=[content])
    response = MagicMock(output=[item], output_text="Grok findings.")
    response.usage = MagicMock(input_tokens=40, output_tokens=60)
    provider.client.responses.create.return_value = response
    digest, usage = alp._research_grok(provider, "Topic: X")
    assert digest.summary == "Grok findings."
    assert digest.sources[0].url == "https://example.com/e"
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
        digests, telemetries = alp.research_all_panelists(providers, "Topic", None)
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
        digests, _ = alp.research_all_panelists(providers, "Topic", None)
    assert digests[0] is not None
    assert digests[1] is None
    assert digests[2] is not None


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
        )
    _, kwargs = mock_cls.call_args
    assert kwargs["panelist_timeout"] == 120


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
        "BODY": "Real body.",
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
