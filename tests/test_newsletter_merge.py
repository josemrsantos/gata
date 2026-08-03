import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import newsletter_merge
from core.newsletter_merge import (
    NewsletterMergeError,
    build_fallback_chain,
    discover_and_order_stories,
    estimate_merge_call_cost,
    merge_edition,
    sum_image_generator_cost,
    write_output,
)
from core.types import TokenUsage

# -- fixtures / helpers --


def _make_story(
    edition_dir: Path,
    folder_name: str,
    audience: str = "uk",
    *,
    post_text: str = "post body",
    image_costs: list[float] | None = None,
    write_telemetry: bool = True,
) -> Path:
    story_dir = edition_dir / folder_name
    audience_dir = story_dir / audience
    audience_dir.mkdir(parents=True)
    (audience_dir / "linkedin_post.md").write_text(post_text, encoding="utf-8")
    if write_telemetry:
        agents = [{"agent": "Satirist/Co-Satirist", "total_cost_usd": 0.05}]
        for cost in image_costs or [0.10]:
            agents.append({"agent": "Image Generator", "total_cost_usd": cost})
        telemetry = {"agents": agents}
        (audience_dir / "telemetry.json").write_text(
            json.dumps(telemetry), encoding="utf-8"
        )
    return story_dir


# -- discover_and_order_stories: ordering (User Story 2) --


def test_orders_by_numeric_prefix_not_directory_listing_order(tmp_path):
    # Folder names are chosen so lexicographic order ("10_" < "1_" < "2_") would
    # give the wrong answer — only numeric-prefix order must win.
    _make_story(tmp_path, "10_last")
    _make_story(tmp_path, "1_first")
    _make_story(tmp_path, "2_middle")
    stories = discover_and_order_stories(tmp_path, "uk")
    assert [s.path.name for s in stories] == ["1_first", "2_middle", "10_last"]


def test_missing_numeric_prefix_raises_naming_folder(tmp_path):
    # A story folder with no leading number must fail loudly, not sort last/first
    # by accident — the operator needs to know exactly which folder to rename.
    _make_story(tmp_path, "01_ok")
    _make_story(tmp_path, "no_prefix_here")
    with pytest.raises(NewsletterMergeError, match="no_prefix_here"):
        discover_and_order_stories(tmp_path, "uk")


def test_duplicate_numeric_prefix_raises_naming_both_folders(tmp_path):
    # Two folders claiming the same position is ambiguous and must never be
    # silently resolved by directory-listing order.
    _make_story(tmp_path, "01_alpha")
    _make_story(tmp_path, "01_beta")
    with pytest.raises(NewsletterMergeError) as exc_info:
        discover_and_order_stories(tmp_path, "uk")
    assert "01_alpha" in str(exc_info.value)
    assert "01_beta" in str(exc_info.value)


def test_fewer_than_two_candidates_raises(tmp_path):
    # Merging a single story is meaningless per FR-003 — must fail before any
    # Gemini call rather than emit a degenerate one-section document.
    _make_story(tmp_path, "01_only")
    with pytest.raises(NewsletterMergeError):
        discover_and_order_stories(tmp_path, "uk")


def test_missing_linkedin_post_raises_naming_folder_and_path(tmp_path):
    # A numbered folder that never got --linkedin-post at generation time must
    # fail loudly (FR-006), not be silently dropped from the edition.
    _make_story(tmp_path, "01_ok")
    incomplete = tmp_path / "02_incomplete"
    (incomplete / "uk").mkdir(parents=True)
    with pytest.raises(NewsletterMergeError) as exc_info:
        discover_and_order_stories(tmp_path, "uk")
    assert "02_incomplete" in str(exc_info.value)
    assert "linkedin_post.md" in str(exc_info.value)


def test_discover_returns_text_and_summed_image_cost(tmp_path):
    # Downstream cost totals (FR-010a) depend on each OrderedStory carrying the
    # right text and the right summed image-generation cost.
    _make_story(tmp_path, "01_a", post_text="hello from story a", image_costs=[0.10])
    _make_story(
        tmp_path, "02_b", post_text="hello from story b", image_costs=[0.09, 0.10]
    )
    stories = discover_and_order_stories(tmp_path, "uk")
    assert stories[0].text == "hello from story a"
    assert stories[0].image_generator_cost_usd == pytest.approx(0.10)
    assert stories[1].image_generator_cost_usd == pytest.approx(0.19)


def test_respects_custom_audience_argument(tmp_path):
    # --audience must actually change which sub-folder is read, not just uk.
    _make_story(tmp_path, "01_a", audience="portuguese")
    _make_story(tmp_path, "02_b", audience="portuguese")
    stories = discover_and_order_stories(tmp_path, "portuguese")
    assert len(stories) == 2


def test_edition_folder_not_found_raises(tmp_path):
    # Pointing at a path that doesn't exist must fail clearly, not crash with a
    # raw filesystem traceback.
    with pytest.raises(NewsletterMergeError):
        discover_and_order_stories(tmp_path / "does-not-exist", "uk")


# -- sum_image_generator_cost --


def test_sums_multiple_image_generator_entries(tmp_path):
    # A story that needed several image-generation iterations paid for every one
    # of them — the total must include all attempts, not just the last.
    telemetry_path = tmp_path / "telemetry.json"
    telemetry_path.write_text(
        json.dumps(
            {
                "agents": [
                    {"agent": "Image Generator", "total_cost_usd": 0.0958},
                    {"agent": "Image Evaluator", "total_cost_usd": 0.0031},
                    {"agent": "Image Generator", "total_cost_usd": 0.0995},
                    {"agent": "Image Generator", "total_cost_usd": 0.1013},
                ]
            }
        ),
        encoding="utf-8",
    )
    total = sum_image_generator_cost(telemetry_path, "some-story")
    assert total == pytest.approx(0.0958 + 0.0995 + 0.1013)


def test_missing_telemetry_file_raises(tmp_path):
    # An incomplete/wrong total is worse than no merge — a missing telemetry.json
    # must hard-fail (FR-012), not silently contribute $0.00.
    with pytest.raises(NewsletterMergeError, match="some-story"):
        sum_image_generator_cost(tmp_path / "telemetry.json", "some-story")


def test_telemetry_with_no_image_generator_entries_raises(tmp_path):
    # A telemetry.json that exists but never recorded an Image Generator agent
    # (e.g. a bundle generated by a future pipeline variant) must also hard-fail.
    telemetry_path = tmp_path / "telemetry.json"
    telemetry_path.write_text(
        json.dumps(
            {"agents": [{"agent": "Satirist/Co-Satirist", "total_cost_usd": 1.0}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(NewsletterMergeError, match="some-story"):
        sum_image_generator_cost(telemetry_path, "some-story")


def test_telemetry_malformed_json_raises(tmp_path):
    # Corrupt JSON must fail clearly rather than propagate a raw JSONDecodeError.
    telemetry_path = tmp_path / "telemetry.json"
    telemetry_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(NewsletterMergeError, match="some-story"):
        sum_image_generator_cost(telemetry_path, "some-story")


# -- estimate_merge_call_cost --


def test_estimate_uses_max_tokens_as_output_ceiling():
    # FR-010b: the estimate must use max_tokens (not an assumed shorter real
    # output) so the published total never understates the call's actual cost.
    rate = (1.0, 2.0)  # $1/M input, $2/M output
    text = "a" * 4000  # ~1000 estimated tokens at 4 chars/token
    cost = estimate_merge_call_cost(rate, text, max_tokens=5000)
    expected = (1000 * 1.0 + 5000 * 2.0) / 1_000_000
    assert cost == pytest.approx(expected)


def test_estimate_scales_with_higher_rate():
    # A pricier candidate model must produce a strictly higher estimate for the
    # same input, so callers can safely use "the priciest model in the chain" as
    # a conservative upper bound regardless of which model actually succeeds.
    text = "some prompt text"
    cheap = estimate_merge_call_cost((0.10, 0.40), text, max_tokens=1000)
    pricey = estimate_merge_call_cost((2.00, 12.00), text, max_tokens=1000)
    assert pricey > cheap


# -- build_fallback_chain --


def test_gemini_models_come_before_other_providers():
    # FR-013: every Gemini text model must be exhausted before any other
    # provider is attempted.
    chain = build_fallback_chain()
    model_ids = [p.model_id for p, _ in chain]
    gemini_ids = {
        "gemini-2.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.1-pro-preview",
    }
    gemini_positions = [i for i, m in enumerate(model_ids) if m in gemini_ids]
    other_positions = [i for i, m in enumerate(model_ids) if m not in gemini_ids]
    assert gemini_positions
    assert other_positions
    assert max(gemini_positions) < min(other_positions)


def test_each_tier_is_ranked_ascending_by_combined_rate():
    # Per FR-013, Gemini must be *fully exhausted* before any other provider is
    # tried, even if a cheaper non-Gemini model exists — so only each tier on its
    # own must be non-decreasing, not the chain as a whole (a priciest Gemini
    # model can legitimately precede the cheapest Grok model).
    chain = build_fallback_chain()
    gemini_ids = {
        "gemini-2.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.1-pro-preview",
    }
    gemini_rates = [sum(rate) for p, rate in chain if p.model_id in gemini_ids]
    other_rates = [sum(rate) for p, rate in chain if p.model_id not in gemini_ids]
    assert gemini_rates == sorted(gemini_rates)
    assert other_rates == sorted(other_rates)


def test_no_retired_gemini_model_in_chain():
    # gemini-2.0-flash was shut down 2026-06-01 (Spec 039) — it must never be a
    # candidate, cheap or not.
    chain = build_fallback_chain()
    model_ids = [p.model_id for p, _ in chain]
    assert "gemini-2.0-flash" not in model_ids
    assert "gemini-2.0-flash-lite" not in model_ids


# -- write_output --


def test_write_output_writes_text(tmp_path):
    # The CLI's only file-writing behaviour must actually land the exact text on
    # disk at the requested path.
    output_path = tmp_path / "merged_linkedin_post.md"
    write_output("merged content", output_path)
    assert output_path.read_text(encoding="utf-8") == "merged content"


def test_write_output_raises_on_unwritable_path(tmp_path):
    # An unwritable target (e.g. parent directory doesn't exist) must raise our
    # own clear error type, not a bare OSError the CLI has to guess about.
    with pytest.raises(NewsletterMergeError):
        write_output("content", tmp_path / "does" / "not" / "exist.md")


# -- merge_edition (orchestration) --


def test_merge_edition_passes_summed_total_to_agent_and_returns_its_text(tmp_path):
    # merge_edition's whole job is arithmetic + wiring: it must hand the agent the
    # correct total (image costs + merge-call estimate) and return exactly what
    # the agent produced.
    _make_story(tmp_path, "01_a", image_costs=[0.10])
    _make_story(tmp_path, "02_b", image_costs=[0.20])
    fake_provider = MagicMock()
    fake_provider.model_id = "fake-model"
    fake_chain = [(fake_provider, (1.0, 2.0))]
    fake_usage = TokenUsage(
        model="fake-model", input_tokens=100, output_tokens=200, cost_usd=0.01
    )
    with (
        patch("core.newsletter_merge.build_fallback_chain", return_value=fake_chain),
        patch(
            "core.newsletter_merge.generate_merged_post",
            return_value=("the merged document", fake_usage),
        ) as mock_generate,
    ):
        result = merge_edition(tmp_path, audience="uk")
    assert result == "the merged document"
    total_arg = mock_generate.call_args.kwargs["estimated_total_cost_usd"]
    assert total_arg > 0.30  # at least the 0.10 + 0.20 image costs, plus the estimate


def test_merge_edition_propagates_discovery_error_before_any_call(tmp_path):
    # A single-story or malformed edition must fail before the (expensive) agent
    # call is ever attempted.
    _make_story(tmp_path, "01_only")
    with patch("core.newsletter_merge.generate_merged_post") as mock_generate:
        with pytest.raises(NewsletterMergeError):
            merge_edition(tmp_path, audience="uk")
    mock_generate.assert_not_called()


def test_merge_edition_uses_the_priciest_rate_in_the_whole_chain_not_just_last(
    tmp_path,
):
    # Regression: the estimate must scan every entry in the chain for the true
    # maximum rate — the chain is only cheapest-first *within* each tier, so the
    # most expensive model is not guaranteed to be the last element overall.
    _make_story(tmp_path, "01_a", image_costs=[0.0])
    _make_story(tmp_path, "02_b", image_costs=[0.0])
    cheap, mid, pricey, last = (MagicMock() for _ in range(4))
    cheap.model_id, mid.model_id, pricey.model_id, last.model_id = (
        "cheap",
        "mid",
        "pricey",
        "last",
    )
    # "pricey" sits in the middle and is the most expensive; "last" (final chain
    # position) is deliberately cheaper than it, mirroring how a real chain's
    # tiers aren't globally sorted.
    fake_chain = [
        (cheap, (0.1, 0.1)),
        (mid, (1.0, 1.0)),
        (pricey, (100.0, 100.0)),
        (last, (2.0, 2.0)),
    ]
    fake_usage = TokenUsage(model="last", input_tokens=1, output_tokens=1, cost_usd=0.0)
    with (
        patch("core.newsletter_merge.build_fallback_chain", return_value=fake_chain),
        patch(
            "core.newsletter_merge.generate_merged_post",
            return_value=("merged", fake_usage),
        ) as mock_generate,
    ):
        merge_edition(tmp_path, audience="uk")
    total_arg = mock_generate.call_args.kwargs["estimated_total_cost_usd"]
    # If the bug were present ("last"'s rate (2.0, 2.0) used instead), the
    # estimate would be roughly 0.0082; with the fix, "pricey"'s (100.0, 100.0)
    # rate must be used instead, giving a much larger figure.
    assert total_arg > 0.1


# -- CLI (newsletter_merge.py) --

ENV = {
    "GEMINI_API_KEY": "fake-gemini",
    "ANTHROPIC_API_KEY": "fake-anthropic",
    "XAI_API_KEY": "fake-grok",
}


def test_cli_exits_when_a_required_key_is_missing(caplog):
    # FR-017: the full fallback chain's credentials must be verified before any
    # call is attempted, not discovered mid-run as a confusing provider failure.
    caplog.set_level(logging.ERROR, logger="newsletter_merge")
    with (
        patch.dict(
            "os.environ",
            {"GEMINI_API_KEY": "", "ANTHROPIC_API_KEY": "k", "XAI_API_KEY": "k"},
        ),
        patch("newsletter_merge.load_dotenv"),
        patch("sys.argv", ["newsletter_merge.py", "some-edition"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        newsletter_merge.main()
    assert exc_info.value.code == 1
    assert any("GEMINI_API_KEY" in r.message for r in caplog.records)


def test_cli_writes_default_output_path(tmp_path):
    # With no -o/--output, the merged document must land at
    # <edition_folder>/merged_linkedin_post.md (FR-016).
    edition_dir = tmp_path / "edition"
    edition_dir.mkdir()
    with (
        patch.dict("os.environ", ENV),
        patch("newsletter_merge.load_dotenv"),
        patch("newsletter_merge.merge_edition", return_value="merged text"),
        patch("sys.argv", ["newsletter_merge.py", str(edition_dir)]),
    ):
        newsletter_merge.main()
    output_path = edition_dir / "merged_linkedin_post.md"
    assert output_path.read_text(encoding="utf-8") == "merged text"


def test_cli_respects_output_override(tmp_path):
    # -o/--output must actually change where the file lands.
    edition_dir = tmp_path / "edition"
    edition_dir.mkdir()
    custom_output = tmp_path / "custom.md"
    with (
        patch.dict("os.environ", ENV),
        patch("newsletter_merge.load_dotenv"),
        patch("newsletter_merge.merge_edition", return_value="merged text"),
        patch(
            "sys.argv",
            ["newsletter_merge.py", str(edition_dir), "-o", str(custom_output)],
        ),
    ):
        newsletter_merge.main()
    assert custom_output.read_text(encoding="utf-8") == "merged text"


def test_cli_exits_nonzero_and_writes_nothing_on_merge_error(tmp_path, caplog):
    # FR-015: total fallback-chain exhaustion (or any NewsletterMergeError) must
    # exit non-zero and must not write a partial/empty output file.
    caplog.set_level(logging.ERROR, logger="newsletter_merge")
    edition_dir = tmp_path / "edition"
    edition_dir.mkdir()
    with (
        patch.dict("os.environ", ENV),
        patch("newsletter_merge.load_dotenv"),
        patch(
            "newsletter_merge.merge_edition",
            side_effect=NewsletterMergeError("all providers exhausted"),
        ),
        patch("sys.argv", ["newsletter_merge.py", str(edition_dir)]),
        pytest.raises(SystemExit) as exc_info,
    ):
        newsletter_merge.main()
    assert exc_info.value.code == 1
    assert not (edition_dir / "merged_linkedin_post.md").exists()


def test_cli_exits_nonzero_on_fallback_chain_exhaustion(tmp_path, caplog):
    # FR-015: the RuntimeError raised when every provider in the fallback chain
    # fails (a distinct case from a NewsletterMergeError) must also be caught by
    # the CLI, exit non-zero, and write no output file.
    caplog.set_level(logging.ERROR, logger="newsletter_merge")
    edition_dir = tmp_path / "edition"
    edition_dir.mkdir()
    with (
        patch.dict("os.environ", ENV),
        patch("newsletter_merge.load_dotenv"),
        patch(
            "newsletter_merge.merge_edition",
            side_effect=RuntimeError("newsletter_editor: all providers exhausted"),
        ),
        patch("sys.argv", ["newsletter_merge.py", str(edition_dir)]),
        pytest.raises(SystemExit) as exc_info,
    ):
        newsletter_merge.main()
    assert exc_info.value.code == 1
    assert not (edition_dir / "merged_linkedin_post.md").exists()


# -- User Story 3: no template-shape validation, no auto-publish implication --


def test_arbitrary_linkedin_post_content_is_accepted(tmp_path):
    # FR-008: hand-edited or drifted text must still be accepted — there is no
    # parse step that can reject a story for not matching the agent_linkedin_post
    # template markers.
    _make_story(tmp_path, "01_a", post_text="### totally different shape\nno markers")
    _make_story(tmp_path, "02_b", post_text="just plain prose, nothing structured")
    stories = discover_and_order_stories(tmp_path, "uk")
    assert len(stories) == 2


def test_cli_help_never_implies_auto_publish(capsys):
    # FR-018: nothing about the CLI's own description should read as "this tool
    # posts for you" — only that a human reviews a draft before publishing.
    with patch("sys.argv", ["newsletter_merge.py", "--help"]):
        with pytest.raises(SystemExit):
            newsletter_merge.main()
    help_text = capsys.readouterr().out.lower()
    assert "draft" in help_text
    for phrase in ("posts to linkedin", "automatically publishes", "auto-publish"):
        assert phrase not in help_text
