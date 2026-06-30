import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.config_loader import load_providers_config
from core.runner import _build_provider
from core.types import ModelSpec, ProvidersConfig

# ---------------------------------------------------------------------------
# load_providers_config — file loading
# ---------------------------------------------------------------------------


def test_load_providers_config_returns_none_when_absent(tmp_path):
    # Missing file is not an error; the pipeline falls back to hardcoded defaults.
    result = load_providers_config(str(tmp_path / "no_such_file.yaml"))
    assert result is None


def test_load_providers_config_valid(tmp_path):
    # A well-formed providers.yaml must parse into a ProvidersConfig with the
    # correct number of panelist slots and aggregator entries.
    cfg = tmp_path / "providers.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            panelists:
              - - provider: claude
                  model: claude-sonnet-4-6
                - provider: gemini
                  model: gemini-2.5-flash
              - - provider: grok
                  model: grok-3-mini
            aggregator:
              - provider: grok
                model: grok-3
              - provider: claude
                model: claude-sonnet-4-6
        """)
    )
    result = load_providers_config(str(cfg))
    assert isinstance(result, ProvidersConfig)
    assert len(result.panelists) == 2
    assert len(result.panelists[0]) == 2
    assert result.panelists[0][0] == ModelSpec(
        provider="claude", model="claude-sonnet-4-6"
    )
    assert result.panelists[0][1] == ModelSpec(
        provider="gemini", model="gemini-2.5-flash"
    )
    assert len(result.panelists[1]) == 1
    assert result.panelists[1][0] == ModelSpec(provider="grok", model="grok-3-mini")
    assert len(result.aggregator) == 2
    assert result.aggregator[0] == ModelSpec(provider="grok", model="grok-3")


def test_load_providers_config_invalid_yaml(tmp_path):
    # Malformed YAML must raise ValueError before any provider is instantiated.
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("panelists: [unclosed")
    with pytest.raises(ValueError, match="not valid YAML"):
        load_providers_config(str(cfg))


def test_load_providers_config_missing_panelists_key(tmp_path):
    # YAML without a 'panelists' key is invalid and must raise immediately.
    cfg = tmp_path / "p.yaml"
    cfg.write_text("aggregator:\n  - provider: grok\n    model: grok-3\n")
    with pytest.raises(ValueError, match="panelists"):
        load_providers_config(str(cfg))


def test_load_providers_config_empty_panelists(tmp_path):
    # An empty panelists list gives no panelists to assign — must raise.
    cfg = tmp_path / "p.yaml"
    cfg.write_text(
        "panelists: []\naggregator:\n  - provider: grok\n    model: grok-3\n"
    )
    with pytest.raises(ValueError, match="panelists"):
        load_providers_config(str(cfg))


def test_load_providers_config_missing_aggregator_key(tmp_path):
    # YAML without an 'aggregator' key is invalid and must raise immediately.
    cfg = tmp_path / "p.yaml"
    cfg.write_text(
        "panelists:\n  - - provider: claude\n      model: claude-sonnet-4-6\n"
    )
    with pytest.raises(ValueError, match="aggregator"):
        load_providers_config(str(cfg))


def test_load_providers_config_empty_aggregator(tmp_path):
    # An empty aggregator list leaves no model to finalise — must raise.
    cfg = tmp_path / "p.yaml"
    cfg.write_text(
        "panelists:\n  - - provider: claude\n      model: claude-sonnet-4-6\n"
        "aggregator: []\n"
    )
    with pytest.raises(ValueError, match="aggregator"):
        load_providers_config(str(cfg))


def test_load_providers_config_unknown_provider(tmp_path):
    # An unrecognised provider name must fail at load time, not at API call time.
    cfg = tmp_path / "p.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            panelists:
              - - provider: openai
                  model: gpt-4o
            aggregator:
              - provider: grok
                model: grok-3
        """)
    )
    with pytest.raises(ValueError, match="openai"):
        load_providers_config(str(cfg))


def test_load_providers_config_blank_model(tmp_path):
    # A blank model string must raise before any provider object is built.
    cfg = tmp_path / "p.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            panelists:
              - - provider: claude
                  model: ""
            aggregator:
              - provider: grok
                model: grok-3
        """)
    )
    with pytest.raises(ValueError, match="model"):
        load_providers_config(str(cfg))


def test_load_providers_config_empty_slot(tmp_path):
    # A panelist slot that is an empty list must raise — no model to call.
    cfg = tmp_path / "p.yaml"
    cfg.write_text(
        textwrap.dedent("""\
            panelists:
              - []
            aggregator:
              - provider: grok
                model: grok-3
        """)
    )
    with pytest.raises(ValueError, match="panelists"):
        load_providers_config(str(cfg))


# ---------------------------------------------------------------------------
# _build_provider — factory
# ---------------------------------------------------------------------------


def test_build_provider_claude():
    # Factory must return a ClaudeProvider for provider='claude'.
    with patch("core.runner.ClaudeProvider") as MockClaude:
        instance = MagicMock()
        MockClaude.return_value = instance
        result = _build_provider(
            ModelSpec(provider="claude", model="claude-sonnet-4-6")
        )
        MockClaude.assert_called_once_with("claude-sonnet-4-6", timeout=None)
        assert result is instance


def test_build_provider_gemini():
    # Factory must return a GeminiProvider for provider='gemini'.
    with patch("core.runner.GeminiProvider") as MockGemini:
        instance = MagicMock()
        MockGemini.return_value = instance
        result = _build_provider(ModelSpec(provider="gemini", model="gemini-2.5-flash"))
        MockGemini.assert_called_once_with("gemini-2.5-flash", timeout=None)
        assert result is instance


def test_build_provider_grok():
    # Factory must return a GrokProvider for provider='grok'.
    with patch("core.runner.GrokProvider") as MockGrok:
        instance = MagicMock()
        MockGrok.return_value = instance
        result = _build_provider(ModelSpec(provider="grok", model="grok-3"))
        MockGrok.assert_called_once_with("grok-3", timeout=None)
        assert result is instance


def test_build_provider_unknown_raises():
    # An unknown provider name must raise ValueError immediately.
    with pytest.raises(ValueError, match="unknown provider"):
        _build_provider(ModelSpec(provider="openai", model="gpt-4o"))


# ---------------------------------------------------------------------------
# cross-provider fallback integration
# ---------------------------------------------------------------------------


def test_panelist_slot_uses_fallback_when_primary_fails():
    # When the primary provider in a slot raises RuntimeError, the next provider
    # in the slot must be called and its result returned — this is the core
    # cross-provider fallback guarantee.
    from core.types import PersonaConfig
    from llm.parallel_panel import ParallelPanel

    primary = MagicMock()
    primary.model_id = "primary-model"
    primary.generate.side_effect = RuntimeError("primary API down")

    fallback = MagicMock()
    fallback.model_id = "fallback-model"
    mock_usage = MagicMock()
    fallback.generate.return_value = (
        "<verdict>fallback answer</verdict>",
        mock_usage,
    )

    aggregator_provider = MagicMock()
    aggregator_provider.model_id = "agg-model"
    agg_usage = MagicMock()
    aggregator_provider.generate.return_value = (
        "PICK: 1\n<verdict>fallback answer</verdict>",
        agg_usage,
    )

    panelist = PersonaConfig(
        name="test-panelist",
        providers=[primary, fallback],
        system_prompt="system",
    )
    aggregator = PersonaConfig(
        name="Aggregator",
        providers=[aggregator_provider],
        system_prompt="aggregate",
    )

    panel = ParallelPanel(
        panelists=[panelist], aggregator=aggregator, panel_name="test"
    )
    output = panel.run("test topic")

    primary.generate.assert_called_once()
    fallback.generate.assert_called_once()
    assert output.verdict is not None


def test_all_providers_in_slot_fail_raises():
    # When every provider in a slot fails, ParallelPanel must still proceed
    # (failed panelists are skipped) and the aggregator handles remaining output.
    from core.types import PersonaConfig
    from llm.parallel_panel import ParallelPanel

    bad1 = MagicMock()
    bad1.model_id = "bad1"
    bad1.generate.side_effect = RuntimeError("fail 1")

    bad2 = MagicMock()
    bad2.model_id = "bad2"
    bad2.generate.side_effect = RuntimeError("fail 2")

    good_panelist = MagicMock()
    good_panelist.model_id = "good"
    good_usage = MagicMock()
    good_panelist.generate.return_value = ("<verdict>good answer</verdict>", good_usage)

    agg_provider = MagicMock()
    agg_provider.model_id = "agg"
    agg_usage = MagicMock()
    agg_provider.generate.return_value = (
        "PICK: 1\n<verdict>good answer</verdict>",
        agg_usage,
    )

    failing_panelist = PersonaConfig(
        name="failing",
        providers=[bad1, bad2],
        system_prompt="system",
    )
    good_panelist_cfg = PersonaConfig(
        name="good",
        providers=[good_panelist],
        system_prompt="system",
    )
    aggregator = PersonaConfig(
        name="Aggregator",
        providers=[agg_provider],
        system_prompt="aggregate",
    )

    panel = ParallelPanel(
        panelists=[failing_panelist, good_panelist_cfg],
        aggregator=aggregator,
        panel_name="test",
    )
    output = panel.run("test topic")
    assert output.verdict is not None


# ---------------------------------------------------------------------------
# _find_providers_config — auto-discovery
# ---------------------------------------------------------------------------


def test_find_providers_config_prefers_local_over_home(tmp_path, monkeypatch):
    # ./providers.yaml takes priority over ~/.gata/providers.yaml so project-level
    # config always wins for developers running from the project root.
    from pipeline import _find_providers_config

    monkeypatch.chdir(tmp_path)
    local = tmp_path / "providers.yaml"
    local.write_text("x: 1")
    home_gata = tmp_path / ".gata"
    home_gata.mkdir()
    (home_gata / "providers.yaml").write_text("x: 2")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    assert _find_providers_config() == str(local)


def test_find_providers_config_falls_back_to_home(tmp_path, monkeypatch):
    # When no local providers.yaml exists, ~/.gata/providers.yaml is used so
    # pipx-installed users get their config picked up automatically.
    from pipeline import _find_providers_config

    monkeypatch.chdir(tmp_path)
    home_gata = tmp_path / ".gata"
    home_gata.mkdir()
    user_cfg = home_gata / "providers.yaml"
    user_cfg.write_text("x: 1")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    assert _find_providers_config() == str(user_cfg)


def test_find_providers_config_returns_none_when_neither_exists(tmp_path, monkeypatch):
    # When neither location has a providers.yaml, None is returned and the
    # pipeline falls back to hardcoded defaults without error.
    from pipeline import _find_providers_config

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    assert _find_providers_config() is None
