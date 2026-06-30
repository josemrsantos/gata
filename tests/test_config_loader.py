import textwrap

import pytest

from core.config_loader import (
    load_communities,
    load_humor_config,
    load_providers_config,
    sanitize_path_segment,
)
from core.types import Community, HumorConfig

# ---------------------------------------------------------------------------
# sanitize_path_segment
# ---------------------------------------------------------------------------


def test_sanitize_lowercase():
    # Uppercase letters must be lowercased so directory names are consistent.
    assert sanitize_path_segment("UK Tech Engineers") == "uk_tech_engineers"


def test_sanitize_spaces_to_underscores():
    # Spaces become underscores so the path is filesystem-safe without quoting.
    assert sanitize_path_segment("ai hype") == "ai_hype"


def test_sanitize_non_alphanum_stripped():
    # Punctuation and special characters are stripped to avoid path escaping issues.
    assert sanitize_path_segment("Is Scrum really Agile?") == "is_scrum_really_agile"


def test_sanitize_truncates_to_50_chars():
    # Long strings are truncated so directory names don't exceed filesystem limits.
    result = sanitize_path_segment("a" * 60)
    assert len(result) == 50


def test_sanitize_empty_string():
    # Empty input must return an empty string without raising.
    assert sanitize_path_segment("") == ""


def test_sanitize_accented_characters_transliterated():
    # Accented characters are transliterated to ASCII equivalents, not stripped.
    assert sanitize_path_segment("habitação") == "habitacao"


def test_sanitize_parentheses_and_numbers():
    # Parentheses are stripped; digits and hyphens are kept.
    result = sanitize_path_segment("Portuguese Adults (18-35)")
    assert result == "portuguese_adults_18-35"


def test_sanitize_hyphens_preserved():
    # Hyphens are valid in directory names on all OSes and must not be stripped.
    assert sanitize_path_segment("uk-tech-engineers") == "uk-tech-engineers"


def test_sanitize_already_clean():
    # A string that already satisfies the rules is returned unchanged.
    assert sanitize_path_segment("uk_tech_engineers") == "uk_tech_engineers"


# ---------------------------------------------------------------------------
# load_communities — happy path
# ---------------------------------------------------------------------------

VALID_YAML = """
communities:
  - name: test-community
    target_audience: Test audience
    output_language: English
    tone: dry wit
    topics:
      - Topic one
      - Topic two
  - name: other-community
    target_audience: Other audience
    output_language: Portuguese
    tone: sharp satire
    topics:
      - Outro tema
"""


def test_load_communities_returns_community_objects(tmp_path):
    # Valid YAML must return a list of Community dataclass instances.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text(VALID_YAML)

    result = load_communities(str(config_file))

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(c, Community) for c in result)


def test_load_communities_fields_mapped_correctly(tmp_path):
    # Each Community object must have all five fields populated from the YAML.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text(VALID_YAML)

    result = load_communities(str(config_file))
    c = result[0]

    assert c.name == "test-community"
    assert c.target_audience == "Test audience"
    assert c.output_language == "English"
    assert c.tone == "dry wit"
    assert c.topics == ["Topic one", "Topic two"]


def test_load_communities_to_brief(tmp_path):
    # to_brief() must return a StrategyBrief with the community's three brief fields.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text(VALID_YAML)

    community = load_communities(str(config_file))[0]
    brief = community.to_brief()

    assert brief.target_audience == "Test audience"
    assert brief.output_language == "English"
    assert brief.tone == "dry wit"


# ---------------------------------------------------------------------------
# load_communities — file and parse errors
# ---------------------------------------------------------------------------


def test_load_communities_file_not_found():
    # A missing file must raise ValueError naming the path, not FileNotFoundError.
    with pytest.raises(ValueError, match="communities.yaml"):
        load_communities("/nonexistent/path/communities.yaml")


def test_load_communities_invalid_yaml(tmp_path):
    # Malformed YAML must raise ValueError before any community is processed.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text("communities: [unclosed bracket")

    with pytest.raises(ValueError, match="not valid YAML"):
        load_communities(str(config_file))


def test_load_communities_missing_communities_key(tmp_path):
    # A YAML file without a top-level 'communities' key must raise ValueError.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text("entries:\n  - name: x\n")

    with pytest.raises(ValueError, match="communities"):
        load_communities(str(config_file))


def test_load_communities_empty_list(tmp_path):
    # An empty communities list must raise ValueError — needs at least one entry.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text("communities: []\n")

    with pytest.raises(ValueError, match="empty"):
        load_communities(str(config_file))


# ---------------------------------------------------------------------------
# load_communities — community entry validation
# ---------------------------------------------------------------------------

MISSING_FIELD_YAML = """
communities:
  - name: broken-community
    target_audience: Some audience
    output_language: English
    tone: dry
"""


def test_load_communities_missing_required_field(tmp_path):
    # A missing field must raise ValueError naming both the community and the field.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text(MISSING_FIELD_YAML)

    with pytest.raises(ValueError) as exc_info:
        load_communities(str(config_file))

    assert "broken-community" in str(exc_info.value)
    assert "topics" in str(exc_info.value)


def test_load_communities_blank_field(tmp_path):
    # A blank (whitespace-only) field must be treated as missing and raise ValueError.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text(
        "communities:\n"
        "  - name: blank-tone\n"
        "    target_audience: Audience\n"
        "    output_language: English\n"
        '    tone: "   "\n'
        "    topics:\n"
        "      - A topic\n"
    )

    with pytest.raises(ValueError, match="tone"):
        load_communities(str(config_file))


def test_load_communities_empty_topics_list(tmp_path):
    # An empty topics list must raise ValueError naming the community.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text(
        "communities:\n"
        "  - name: no-topics\n"
        "    target_audience: Audience\n"
        "    output_language: English\n"
        "    tone: dry\n"
        "    topics: []\n"
    )

    with pytest.raises(ValueError, match="no-topics"):
        load_communities(str(config_file))


def test_load_communities_blank_topic_item(tmp_path):
    # A blank string inside the topics list must raise ValueError naming the community.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text(
        "communities:\n"
        "  - name: blank-topic\n"
        "    target_audience: Audience\n"
        "    output_language: English\n"
        "    tone: dry\n"
        "    topics:\n"
        "      - Valid topic\n"
        '      - "   "\n'
    )

    with pytest.raises(ValueError, match="blank-topic"):
        load_communities(str(config_file))


def test_load_communities_duplicate_names(tmp_path):
    # Duplicate community names must raise ValueError that includes the offending name.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text(
        "communities:\n"
        "  - name: my-community\n"
        "    target_audience: A\n"
        "    output_language: English\n"
        "    tone: dry\n"
        "    topics:\n"
        "      - Topic one\n"
        "  - name: my-community\n"
        "    target_audience: B\n"
        "    output_language: English\n"
        "    tone: sharp\n"
        "    topics:\n"
        "      - Topic two\n"
    )

    with pytest.raises(ValueError) as exc_info:
        load_communities(str(config_file))

    assert "my-community" in str(exc_info.value)


def test_load_communities_blank_name(tmp_path):
    # A blank name must raise ValueError — name is used for error reporting and paths.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text(
        "communities:\n"
        '  - name: ""\n'
        "    target_audience: Audience\n"
        "    output_language: English\n"
        "    tone: dry\n"
        "    topics:\n"
        "      - A topic\n"
    )

    with pytest.raises(ValueError, match="name"):
        load_communities(str(config_file))


def test_load_communities_communities_not_a_list(tmp_path):
    # If 'communities' exists but is not a list, raise ValueError before processing.
    config_file = tmp_path / "communities.yaml"
    config_file.write_text("communities: not-a-list\n")

    with pytest.raises(ValueError, match="communities"):
        load_communities(str(config_file))


# ---------------------------------------------------------------------------
# load_humor_config — happy path
# ---------------------------------------------------------------------------

_VALID_HUMOR_YAML = """
agents:
  framer:
    wordplay_scan: true
    joke_types:
      - situational
      - wordplay
    language_register: vernacular
  satirist:
    preferred_style: deadpan
    avoid:
      - obvious_pun
    subversion: high
    joke_explanation: true
  critic:
    evaluate_joke_mechanics: true
    flag_if_no_subversion: true
"""


def test_load_humor_config_returns_humor_config(tmp_path):
    # Valid humor.yaml must return a HumorConfig with all three agent blocks populated.
    config_file = tmp_path / "humor.yaml"
    config_file.write_text(_VALID_HUMOR_YAML)
    result = load_humor_config(str(config_file))
    assert isinstance(result, HumorConfig)


def test_load_humor_config_framer_fields(tmp_path):
    # Framer block must have wordplay_scan, joke_types, and language_register loaded.
    config_file = tmp_path / "humor.yaml"
    config_file.write_text(_VALID_HUMOR_YAML)
    result = load_humor_config(str(config_file))
    assert result.framer.wordplay_scan is True
    assert result.framer.joke_types == ["situational", "wordplay"]
    assert result.framer.language_register == "vernacular"


def test_load_humor_config_satirist_fields(tmp_path):
    # Satirist block must have preferred_style, avoid, subversion, and joke_explanation.
    config_file = tmp_path / "humor.yaml"
    config_file.write_text(_VALID_HUMOR_YAML)
    result = load_humor_config(str(config_file))
    assert result.satirist.preferred_style == "deadpan"
    assert "obvious_pun" in result.satirist.avoid
    assert result.satirist.subversion == "high"
    assert result.satirist.joke_explanation is True


def test_load_humor_config_critic_fields(tmp_path):
    # Critic block must have evaluate_joke_mechanics and flag_if_no_subversion.
    config_file = tmp_path / "humor.yaml"
    config_file.write_text(_VALID_HUMOR_YAML)
    result = load_humor_config(str(config_file))
    assert result.critic.evaluate_joke_mechanics is True
    assert result.critic.flag_if_no_subversion is True


# ---------------------------------------------------------------------------
# load_humor_config — missing file and parse errors
# ---------------------------------------------------------------------------


def test_load_humor_config_returns_none_when_file_missing():
    # A missing humor.yaml must return None — humor config is optional.
    result = load_humor_config("/nonexistent/humor.yaml")
    assert result is None


def test_load_humor_config_invalid_yaml(tmp_path):
    # Malformed YAML must raise ValueError before any config is processed.
    config_file = tmp_path / "humor.yaml"
    config_file.write_text("agents: [unclosed bracket")
    with pytest.raises(ValueError, match="not valid YAML"):
        load_humor_config(str(config_file))


def test_load_humor_config_missing_agents_key(tmp_path):
    # A YAML file without a top-level 'agents' key must raise ValueError.
    config_file = tmp_path / "humor.yaml"
    config_file.write_text("style:\n  framer: {}\n")
    with pytest.raises(ValueError, match="agents"):
        load_humor_config(str(config_file))


# ---------------------------------------------------------------------------
# load_communities — panels and layout fields (Stage 9)
# ---------------------------------------------------------------------------

_MINIMAL_COMMUNITY_YAML = """
communities:
  - name: minimal
    target_audience: anyone
    output_language: English
    tone: neutral
    topics:
      - test topic
"""

_MULTI_PANEL_COMMUNITY_YAML = """
communities:
  - name: multi-test
    target_audience: anyone
    output_language: English
    tone: neutral
    panels: 3
    layout: vertical
    topics:
      - test topic
"""


def test_community_panels_defaults_to_1_when_absent(tmp_path):
    # Communities without a 'panels' field must load with panels=1 so existing
    # communities.yaml files are forwards-compatible with no changes required.
    p = tmp_path / "c.yaml"
    p.write_text(_MINIMAL_COMMUNITY_YAML)
    communities = load_communities(str(p))
    assert communities[0].panels == 1


def test_community_layout_defaults_to_horizontal_when_absent(tmp_path):
    # Communities without a 'layout' field must load with layout="horizontal" so
    # the default single-panel behaviour is preserved for all existing configs.
    p = tmp_path / "c.yaml"
    p.write_text(_MINIMAL_COMMUNITY_YAML)
    communities = load_communities(str(p))
    assert communities[0].layout == "horizontal"


def test_community_panels_and_layout_loaded_from_yaml(tmp_path):
    # When 'panels' and 'layout' are present in a community entry, both values must
    # be loaded so the pipeline can apply community-level panel configuration.
    p = tmp_path / "c.yaml"
    p.write_text(_MULTI_PANEL_COMMUNITY_YAML)
    communities = load_communities(str(p))
    assert communities[0].panels == 3
    assert communities[0].layout == "vertical"


# ---------------------------------------------------------------------------
# Inconvenience level and dual satirist loading (Stage 10)
# ---------------------------------------------------------------------------

_HUMOR_WITH_INCONVENIENCE = """
agents:
  framer:
    wordplay_scan: true
    inconvenience: 40
  satirist:
    preferred_style: deadpan
    subversion: high
    inconvenience: 80
  critic:
    evaluate_joke_mechanics: false
    flag_if_no_subversion: true
    inconvenience: 60
    dual_satirist: true
"""

_HUMOR_WITHOUT_INCONVENIENCE = """
agents:
  framer:
    wordplay_scan: true
  satirist:
    preferred_style: deadpan
    subversion: high
  critic:
    evaluate_joke_mechanics: false
    flag_if_no_subversion: true
"""


def test_load_humor_config_reads_satirist_inconvenience(tmp_path):
    # When inconvenience is set in humor.yaml for the satirist, it must be loaded
    # so the Satirist prompt injection can use the configured level.
    p = tmp_path / "h.yaml"
    p.write_text(_HUMOR_WITH_INCONVENIENCE)
    config = load_humor_config(str(p))
    assert config.satirist.inconvenience == 80


def test_load_humor_config_reads_framer_inconvenience(tmp_path):
    # When inconvenience is set for the framer, it must be loaded so the Framer
    # prompt can inject the correct inconvenience directive.
    p = tmp_path / "h.yaml"
    p.write_text(_HUMOR_WITH_INCONVENIENCE)
    config = load_humor_config(str(p))
    assert config.framer.inconvenience == 40


def test_load_humor_config_reads_critic_inconvenience(tmp_path):
    # When inconvenience is set for the critic, it must be loaded so the Critic
    # prompt can inject the correct directive.
    p = tmp_path / "h.yaml"
    p.write_text(_HUMOR_WITH_INCONVENIENCE)
    config = load_humor_config(str(p))
    assert config.critic.inconvenience == 60


def test_load_humor_config_reads_dual_satirist_flag(tmp_path):
    # dual_satirist: true in humor.yaml must be loaded so the Critic prompt switches
    # to collaborative mode when the flag is set.
    p = tmp_path / "h.yaml"
    p.write_text(_HUMOR_WITH_INCONVENIENCE)
    config = load_humor_config(str(p))
    assert config.critic.dual_satirist is True


def test_load_humor_config_inconvenience_defaults_to_zero(tmp_path):
    # When inconvenience is absent from humor.yaml all agents must default to 0
    # so existing configs are fully backwards-compatible.
    p = tmp_path / "h.yaml"
    p.write_text(_HUMOR_WITHOUT_INCONVENIENCE)
    config = load_humor_config(str(p))
    assert config.satirist.inconvenience == 0
    assert config.framer.inconvenience == 0
    assert config.critic.inconvenience == 0


def test_load_humor_config_dual_satirist_defaults_to_false(tmp_path):
    # When dual_satirist is absent from humor.yaml the critic must default to False
    # so the adversarial critic behaviour is unchanged by default.
    p = tmp_path / "h.yaml"
    p.write_text(_HUMOR_WITHOUT_INCONVENIENCE)
    config = load_humor_config(str(p))
    assert config.critic.dual_satirist is False


# ---------------------------------------------------------------------------
# load_providers_config — timeout field (Spec 036)
# ---------------------------------------------------------------------------

_PROVIDERS_WITH_TIMEOUT = textwrap.dedent("""\
    panelists:
      - - provider: claude
          model: claude-sonnet-4-6
          timeout: 25.0
    aggregator:
      - provider: grok
        model: grok-3
    """)

_PROVIDERS_NO_TIMEOUT = textwrap.dedent("""\
    panelists:
      - - provider: claude
          model: claude-sonnet-4-6
    aggregator:
      - provider: grok
        model: grok-3
    """)

_PROVIDERS_NEGATIVE_TIMEOUT = textwrap.dedent("""\
    panelists:
      - - provider: claude
          model: claude-sonnet-4-6
          timeout: -5
    aggregator:
      - provider: grok
        model: grok-3
    """)


def test_providers_timeout_parsed(tmp_path):
    # A numeric timeout field on a provider entry must be parsed into ModelSpec.timeout
    # so FairParallelPanel can enforce a per-provider budget from config alone.
    p = tmp_path / "providers.yaml"
    p.write_text(_PROVIDERS_WITH_TIMEOUT)
    config = load_providers_config(str(p))
    assert config.panelists[0][0].timeout == 25.0


def test_providers_timeout_absent_is_none(tmp_path):
    # A provider entry without a timeout field must yield ModelSpec.timeout of None
    # so omitting the field preserves today's unbounded behaviour with no regression.
    p = tmp_path / "providers.yaml"
    p.write_text(_PROVIDERS_NO_TIMEOUT)
    config = load_providers_config(str(p))
    assert config.panelists[0][0].timeout is None


def test_providers_timeout_invalid_raises(tmp_path):
    # A non-positive timeout must raise ValueError to surface misconfiguration early
    # before any LLM calls are made, giving a clear error rather than silent failure.
    p = tmp_path / "providers.yaml"
    p.write_text(_PROVIDERS_NEGATIVE_TIMEOUT)
    with pytest.raises(ValueError, match="timeout"):
        load_providers_config(str(p))
