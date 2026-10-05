"""Invariants for the built-in default models, fallback chains and price tables.

Spec 054 (model currency refresh II): every default must be a model the
provider still serves, chains keep their provider order, and every default has
a price entry so cost reports never silently show $0.00.
"""

from pathlib import Path

import yaml

import core.image_generation as image_generation
from agents import agent_cultural_strategist, trend_scout
from core import newsletter_merge, runner
from core.types import ModelSpec, ProvidersConfig
from llm import claude as claude_prices
from llm import gemini as gemini_prices
from llm import grok as grok_prices
from llm.claude import ClaudeProvider

_REPO = Path(__file__).resolve().parent.parent

# Names that must never again be a built-in default: superseded by a same-tier
# successor, or already failing for our key (Spec 054 research.md §6).
_NOT_DEFAULTS = {
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-lite",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
}


def _ids(providers) -> list[str]:
    return [p.model_id for p in providers]


def _yaml_defaults() -> dict:
    return yaml.safe_load((_REPO / "providers.yaml").read_text())


def _all_default_ids() -> set[str]:
    cfg = _yaml_defaults()
    yaml_ids = {m["model"] for slot in cfg["panelists"] for m in slot}
    yaml_ids |= {m["model"] for m in cfg["aggregator"]}
    return (
        set(_ids(runner._CLAUDE_CHAIN))
        | set(_ids(runner._GEMINI_PRO_CHAIN))
        | set(_ids(runner._GEMINI_EVAL_CHAIN))
        | set(_ids(runner._PARALLEL_PANELISTS))
        | set(_ids(runner._AGGREGATOR_CHAIN))
        | set(image_generation._MODELS)
        | set(newsletter_merge._GEMINI_TEXT_MODELS)
        | set(newsletter_merge._CLAUDE_MODELS)
        | set(newsletter_merge._GROK_MODELS)
        | set(_ids(newsletter_merge._DEFAULT_PANELIST_PROVIDERS))
        | set(_ids(newsletter_merge._DEFAULT_AGGREGATOR_PROVIDERS))
        | set(agent_cultural_strategist._INFERENCE_MODELS)
        | {trend_scout._GEMINI_MODEL}
        | yaml_ids
    )


def test_no_superseded_or_dead_model_is_a_default():
    # A superseded or already-failing model must not remain a built-in default,
    # otherwise every run would hit it first (or fall through a dead entry).
    leaked = _all_default_ids() & _NOT_DEFAULTS
    assert not leaked, f"superseded/dead models still default: {sorted(leaked)}"


def test_bundle_writer_fallback_defaults_use_current_models():
    # core/bundle_writer.py hard-codes fallback providers inside a function, so
    # this checks its source text for the same superseded names.
    text = (_REPO / "core" / "bundle_writer.py").read_text()
    leaked = {name for name in _NOT_DEFAULTS if name in text}
    assert not leaked, f"bundle_writer still names: {sorted(leaked)}"
    assert "claude-sonnet-5-5" in text


def test_image_chain_is_stable_models_only_in_existing_order():
    # The image chain must start on the stable GA model, not the preview name
    # Google documents as shut down; flash before pro keeps the old order.
    assert image_generation._MODELS == [
        "gemini-3.1-flash-image",
        "gemini-3-pro-image",
    ]


def test_claude_chain_uses_same_tier_successors_in_order():
    # Sonnet and Opus move to their 5.5 successors in place; Haiku 4.5 has no
    # newer model so it stays — the chain order must not change (FR-003).
    assert _ids(runner._CLAUDE_CHAIN) == [
        "claude-sonnet-5-5",
        "claude-opus-5-5",
        "claude-haiku-4-5-20251001",
    ]


def test_gemini_chain_moves_only_flash_lite():
    # Live check 2026-10-04: gemini-2.5-flash still works (HOLD) while
    # gemini-2.5-flash-lite returns 404, so only Flash-Lite is replaced.
    assert _ids(runner._GEMINI_PRO_CHAIN) == [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-3.5-flash-lite",
    ]
    assert _ids(runner._GEMINI_EVAL_CHAIN) == _ids(runner._GEMINI_PRO_CHAIN)


def test_parallel_panelists_and_aggregator_defaults():
    # The panel keeps one model per provider; only the Claude panelist changes,
    # and the Grok aggregator is intentionally unchanged (lead decision).
    assert _ids(runner._PARALLEL_PANELISTS) == [
        "claude-sonnet-5-5",
        "grok-build-0.1",
        "gemini-2.5-flash",
    ]
    assert _ids(runner._AGGREGATOR_CHAIN) == [
        "grok-4.3",
        "claude-sonnet-5-5",
        "gemini-2.5-pro",
    ]


def test_grok_panelist_and_aggregator_stay_distinct_models():
    # Constitution §6 keeps the Grok panelist and the Grok aggregator as
    # different models so the aggregator is never judging its own output.
    panel_grok = {
        p.model_id for p in runner._PARALLEL_PANELISTS if p.model_id.startswith("grok-")
    }
    agg_grok = {m for m in _ids(runner._AGGREGATOR_CHAIN) if m.startswith("grok-")}
    assert panel_grok and agg_grok
    assert panel_grok.isdisjoint(agg_grok)
    cfg = _yaml_defaults()
    yaml_panel = {
        m["model"] for slot in cfg["panelists"] for m in slot if m["provider"] == "grok"
    }
    yaml_agg = {m["model"] for m in cfg["aggregator"] if m["provider"] == "grok"}
    assert yaml_panel.isdisjoint(yaml_agg)


def test_cultural_strategist_and_trend_scout_defaults():
    # The audience-inference chain replaces only its dead Flash-Lite entry, and
    # the trend scout stays on gemini-2.5-flash (still served).
    assert agent_cultural_strategist._INFERENCE_MODELS == [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.5-flash-lite",
    ]
    assert trend_scout._GEMINI_MODEL == "gemini-2.5-flash"


def test_newsletter_merge_lists_use_current_models():
    # The newsletter merge fallback ladders must follow the same successors,
    # with the Grok list untouched.
    assert newsletter_merge._GEMINI_TEXT_MODELS == [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.1-pro-preview",
    ]
    assert newsletter_merge._CLAUDE_MODELS == [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-5-5",
        "claude-opus-5-5",
    ]
    assert newsletter_merge._GROK_MODELS == ["grok-build-0.1", "grok-4.3", "grok-4.5"]
    assert _ids(newsletter_merge._DEFAULT_PANELIST_PROVIDERS) == [
        "claude-sonnet-5-5",
        "grok-build-0.1",
        "gemini-2.5-flash",
    ]
    assert _ids(newsletter_merge._DEFAULT_AGGREGATOR_PROVIDERS) == _ids(
        runner._AGGREGATOR_CHAIN
    )


def test_providers_yaml_defaults_keep_order_and_use_current_models():
    # providers.yaml is the operator-facing copy of the defaults: its provider
    # order per slot must be unchanged (FR-003) and its models current.
    cfg = _yaml_defaults()
    order = [[m["provider"] for m in slot] for slot in cfg["panelists"]]
    assert order == [
        ["claude", "gemini", "grok"],
        ["grok", "gemini", "claude"],
        ["gemini", "grok", "claude"],
    ]
    assert [m["provider"] for m in cfg["aggregator"]] == ["grok", "claude", "gemini"]
    assert [[m["model"] for m in slot] for slot in cfg["panelists"]] == [
        ["claude-sonnet-5-5", "gemini-2.5-flash", "grok-build-0.1"],
        ["grok-build-0.1", "gemini-2.5-flash", "claude-haiku-4-5-20251001"],
        ["gemini-2.5-flash", "grok-build-0.1", "claude-haiku-4-5-20251001"],
    ]
    assert [m["model"] for m in cfg["aggregator"]] == [
        "grok-4.3",
        "claude-sonnet-5-5",
        "gemini-2.5-pro",
    ]


def test_every_default_model_has_a_price_entry():
    # An unpriced model silently costs $0.00 in the run summary, so every
    # built-in default must have a row in its provider's price table.
    tables = {
        "claude-": claude_prices._COST_PER_M,
        "gemini-": gemini_prices._COST_PER_M,
        "grok-": grok_prices._COST_PER_M,
    }
    missing = []
    for model in sorted(_all_default_ids()):
        table = next(t for prefix, t in tables.items() if model.startswith(prefix))
        if model not in table:
            missing.append(model)
    assert not missing, f"defaults without a price entry: {missing}"


# ---------------------------------------------------------------------------
# Claude panelists run at low effort (spec 054 amendment A)
# ---------------------------------------------------------------------------


def _claude_only(providers):
    return [p for p in providers if isinstance(p, ClaudeProvider)]


def test_default_claude_panelists_run_at_low_effort():
    # The default Claude panelist must request low effort so Sonnet 5.5 does not
    # spend hundreds of thinking tokens on every panel round.
    claude = _claude_only(runner._PARALLEL_PANELISTS)
    assert claude
    assert all(p.effort == "low" for p in claude)


def test_claude_models_outside_the_panel_keep_their_default_effort():
    # Only panelists are tuned: the Claude fallback chain and the aggregator slots
    # must not silently change behaviour.
    assert all(p.effort is None for p in _claude_only(runner._CLAUDE_CHAIN))


def test_runner_build_provider_sets_effort_only_for_panelists():
    # providers.yaml entries become panelists or aggregators; only a panelist
    # Claude entry on a model that supports effort gets low effort.
    spec = ModelSpec(provider="claude", model="claude-sonnet-5-5")
    assert runner._build_provider(spec, panelist=True).effort == "low"
    assert runner._build_provider(spec).effort is None
    haiku = ModelSpec(provider="claude", model="claude-haiku-4-5-20251001")
    assert runner._build_provider(haiku, panelist=True).effort is None


def test_newsletter_engagement_panelists_run_at_low_effort_aggregator_does_not():
    # The newsletter's engagement-image panel is a panel too: its Claude panelists
    # use low effort and its aggregator is left alone.
    assert all(
        p.effort == "low"
        for p in _claude_only(newsletter_merge._DEFAULT_PANELIST_PROVIDERS)
    )
    claude = ModelSpec(provider="claude", model="claude-sonnet-5-5")
    config = ProvidersConfig(panelists=[[claude]], aggregator=[claude])
    panelists, aggregator = newsletter_merge._build_engagement_providers(config)
    assert panelists[0][0].effort == "low"
    assert aggregator[0].effort is None


def test_bundle_writer_fallback_panelists_use_the_shared_effort_constant():
    # bundle_writer builds its own fallback panel; its Claude panelist must use the
    # same shared low-effort setting (checked in the source because the defaults are
    # created inside a function).
    text = (_REPO / "core" / "bundle_writer.py").read_text()
    assert "PANELIST_CLAUDE_EFFORT" in text


def test_default_aggregator_falls_back_across_providers_in_providers_yaml_order():
    # A Grok outage or exhausted credit once took down every panel's aggregation
    # step, because gata's built-in aggregator had no fallback. The built-in chain
    # must match providers.yaml's aggregator chain: grok, then claude, then gemini.
    providers = [p.__class__.__name__ for p in runner._AGGREGATOR_CHAIN]
    assert providers == ["GrokProvider", "ClaudeProvider", "GeminiProvider"]
    cfg = _yaml_defaults()
    assert [m["model"] for m in cfg["aggregator"]] == _ids(runner._AGGREGATOR_CHAIN)


def test_the_claude_aggregator_fallback_keeps_the_default_effort():
    # Only panelists run at low effort; the aggregator decides the final answer and
    # keeps the model's default behaviour even when it is only a fallback.
    assert all(p.effort is None for p in _claude_only(runner._AGGREGATOR_CHAIN))
