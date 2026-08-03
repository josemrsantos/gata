import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agents.agent_newsletter_editor import build_merge_prompt, generate_merged_post
from core.newsletter_merge import OrderedStory
from core.types import TokenUsage

# -- fixtures / helpers --


def _story(order: int, folder: str, text: str) -> OrderedStory:
    return OrderedStory(
        path=Path(folder),
        order=order,
        text=text,
        image_generator_cost_usd=0.10,
    )


def _provider(
    model_id: str, response: str | None = None, exc: Exception | None = None
) -> MagicMock:
    provider = MagicMock()
    provider.model_id = model_id
    if exc is not None:
        provider.generate.side_effect = exc
    else:
        usage = TokenUsage(
            model=model_id, input_tokens=500, output_tokens=800, cost_usd=0.0123
        )
        provider.generate.return_value = (response, usage)
    return provider


_STORIES = [
    _story(1, "01_first", "First story body about scene-setting."),
    _story(2, "02_second", "Second story body about the punchline."),
]


# -- build_merge_prompt --


def test_prompt_states_story_order_explicitly():
    # FR-009: the prompt must state the given order explicitly so the model isn't
    # left to infer it, and must not be told to reorder anything.
    prompt = build_merge_prompt(_STORIES, estimated_total_cost_usd=0.55)
    first_pos = prompt.index("First story body")
    second_pos = prompt.index("Second story body")
    assert first_pos < second_pos


def test_prompt_includes_full_text_of_every_story():
    # Dropping a story's text would silently produce an incomplete edition.
    prompt = build_merge_prompt(_STORIES, estimated_total_cost_usd=0.55)
    assert "First story body about scene-setting." in prompt
    assert "Second story body about the punchline." in prompt


def test_prompt_instructs_consolidation_of_repeated_content():
    # FR-009: the model must be told to collapse repeated boilerplate into one
    # shared section rather than repeating it per story.
    prompt = build_merge_prompt(_STORIES, estimated_total_cost_usd=0.55)
    assert "once" in prompt.lower()


def test_prompt_includes_total_cost_and_human_time_disclaimer():
    # FR-011: the exact total and the human-time disclaimer must both be present
    # so the model has no room to omit or recompute either.
    prompt = build_merge_prompt(_STORIES, estimated_total_cost_usd=1.2345)
    assert "1.2345" in prompt
    assert "human" in prompt.lower()


def test_prompt_does_not_impose_any_template_shape_on_input():
    # FR-008: build_merge_prompt must not validate or reject unusual story text —
    # it only has to include it.
    odd_story = [_story(1, "01_a", "###???not a normal post at all")]
    prompt = build_merge_prompt(odd_story, estimated_total_cost_usd=0.10)
    assert "###???not a normal post at all" in prompt


# -- generate_merged_post: happy path --


def test_generate_merged_post_returns_first_success_verbatim():
    # FR-016: the merged text returned must be exactly what the model produced,
    # with no further post-processing by this function.
    provider = _provider("cheap-model", response="THE MERGED DOCUMENT")
    text, usage = generate_merged_post(
        [provider], _STORIES, estimated_total_cost_usd=0.50
    )
    assert text == "THE MERGED DOCUMENT"
    assert usage.model == "cheap-model"


# -- generate_merged_post: fallback chain (User Story 4) --


def test_fallback_tries_next_provider_on_failure():
    # FR-013/014: a failure on the cheapest model must not abort the run — the
    # next model in the chain must be tried.
    failing = _provider("cheap-model", exc=RuntimeError("boom"))
    working = _provider("next-model", response="MERGED")
    text, usage = generate_merged_post(
        [failing, working], _STORIES, estimated_total_cost_usd=0.50
    )
    assert text == "MERGED"
    assert usage.model == "next-model"
    failing.generate.assert_called_once()
    working.generate.assert_called_once()


def test_fallback_logs_each_failure_and_the_eventual_success(caplog):
    # FR-014: every attempt's outcome must be visible in the log, not just the
    # final result — this is how an operator would notice a provider degrading.
    caplog.set_level(logging.INFO, logger="agents.agent_newsletter_editor")
    failing_a = _provider("model-a", exc=RuntimeError("model-a down"))
    failing_b = _provider("model-b", exc=RuntimeError("model-b down"))
    working = _provider("model-c", response="MERGED")
    generate_merged_post(
        [failing_a, failing_b, working], _STORIES, estimated_total_cost_usd=0.50
    )
    messages = "\n".join(r.message for r in caplog.records)
    assert "model-a" in messages
    assert "model-b" in messages
    assert "model-c" in messages


def test_exhausting_every_provider_raises_and_makes_no_partial_output():
    # FR-015: total exhaustion must raise, not return a partial/empty document
    # that the CLI might accidentally write to disk.
    failing_a = _provider("model-a", exc=RuntimeError("model-a down"))
    failing_b = _provider("model-b", exc=RuntimeError("model-b down"))
    with pytest.raises(RuntimeError):
        generate_merged_post(
            [failing_a, failing_b], _STORIES, estimated_total_cost_usd=0.50
        )
