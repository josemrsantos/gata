import logging
import re

import yaml
from unidecode import unidecode

from core.types import (
    _VALID_PROVIDER_NAMES,
    Community,
    CriticHumor,
    FramerHumor,
    HumorConfig,
    ModelSpec,
    NewsSource,
    ProvidersConfig,
    SatiristHumor,
)

logger = logging.getLogger(__name__)

_REQUIRED_STRING_FIELDS = ("target_audience", "output_language", "tone")


def sanitize_path_segment(text: str) -> str:
    text = unidecode(text).lower()
    text = text.replace(" ", "_")
    text = re.sub(r"[^a-z0-9_-]", "", text)
    return text[:50]


def load_communities(path: str) -> list[Community]:
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        raise ValueError(f"Config file not found: {path}")
    except yaml.YAMLError as exc:
        raise ValueError(f"{path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict) or "communities" not in raw:
        raise ValueError("Config file is missing required top-level 'communities' key")

    entries = raw["communities"]
    if not isinstance(entries, list):
        raise ValueError("'communities' must be a list of entries")

    if not entries:
        raise ValueError("'communities' list is empty — at least one entry is required")

    communities: list[Community] = []
    seen_names: set[str] = set()

    for i, entry in enumerate(entries):
        if "name" not in entry or not isinstance(entry["name"], str):
            raise ValueError(
                f"Community entry #{i + 1} is missing required 'name' field"
            )
        if not entry["name"].strip():
            raise ValueError(f"Community entry #{i + 1} has a blank 'name' field")
        name = entry["name"]

        for field in _REQUIRED_STRING_FIELDS:
            if field not in entry:
                raise ValueError(
                    f"Community '{name}' is missing required field '{field}'"
                )
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise ValueError(f"Community '{name}' has a blank '{field}' field")

        if name in seen_names:
            raise ValueError(f"Duplicate community name: '{name}'")
        seen_names.add(name)

        topics = entry.get("topics")
        if topics is None:
            raise ValueError(f"Community '{name}' is missing required field 'topics'")
        if not isinstance(topics, list) or not topics:
            raise ValueError(f"Community '{name}' has an empty 'topics' list")
        for topic in topics:
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError(
                    f"Community '{name}' has a blank item in its 'topics' list"
                )

        raw_sources = entry.get("news_sources")
        news_sources: list[NewsSource] = []
        if raw_sources is not None:
            if not isinstance(raw_sources, list):
                raise ValueError(
                    f"Community '{name}' field 'news_sources' must be a list"
                )
            for j, src in enumerate(raw_sources):
                if not isinstance(src, dict):
                    raise ValueError(
                        f"Community '{name}' news_sources[{j}] must be a mapping"
                    )
                country = src.get("country", "")
                sources = src.get("sources", "")
                if not country and not sources:
                    raise ValueError(
                        f"Community '{name}' news_sources[{j}]"
                        " must have 'country' or 'sources'"
                    )
                if country and sources:
                    raise ValueError(
                        f"Community '{name}' news_sources[{j}]"
                        " cannot set both 'country' and 'sources'"
                    )
                category = src.get("category", "general")
                if not isinstance(category, str) or not category.strip():
                    raise ValueError(
                        f"Community '{name}' news_sources[{j}]"
                        " 'category' must be a non-blank string"
                    )
                count = src.get("count", 10)
                if not isinstance(count, int) or count < 1:
                    raise ValueError(
                        f"Community '{name}' news_sources[{j}]"
                        " 'count' must be a positive integer"
                    )
                news_sources.append(
                    NewsSource(
                        country=country,
                        sources=sources,
                        category=category,
                        count=count,
                    )
                )

        panels = int(entry.get("panels", 1))
        layout = str(entry.get("layout", "horizontal"))
        communities.append(
            Community(
                name=name,
                target_audience=entry["target_audience"],
                output_language=entry["output_language"],
                tone=entry["tone"],
                topics=list(topics),
                news_sources=news_sources,
                panels=panels,
                layout=layout,
            )
        )

    return communities


def load_providers_config(path: str) -> ProvidersConfig | None:
    """Load optional providers.yaml; returns None if absent, ValueError if invalid."""
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        return None
    except yaml.YAMLError as exc:
        raise ValueError(f"{path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: must be a YAML mapping")

    def _parse_spec(item: object, context: str) -> ModelSpec:
        if not isinstance(item, dict):
            raise ValueError(f"{path}: {context} entry must be a mapping")
        provider = item.get("provider", "")
        model = item.get("model", "")
        if not isinstance(provider, str) or provider not in _VALID_PROVIDER_NAMES:
            raise ValueError(
                f"{path}: {context} provider {provider!r} must be one of"
                f" {sorted(_VALID_PROVIDER_NAMES)}"
            )
        if not isinstance(model, str) or not model.strip():
            raise ValueError(f"{path}: {context} model must be a non-blank string")
        return ModelSpec(provider=provider, model=model)

    raw_panelists = raw.get("panelists")
    if not isinstance(raw_panelists, list) or not raw_panelists:
        raise ValueError(f"{path}: 'panelists' must be a non-empty list")
    panelists: list[list[ModelSpec]] = []
    for i, slot in enumerate(raw_panelists):
        if not isinstance(slot, list) or not slot:
            raise ValueError(f"{path}: panelists[{i}] must be a non-empty list")
        panelists.append([_parse_spec(m, f"panelists[{i}]") for m in slot])

    raw_aggregator = raw.get("aggregator")
    if not isinstance(raw_aggregator, list) or not raw_aggregator:
        raise ValueError(f"{path}: 'aggregator' must be a non-empty list")
    aggregator = [_parse_spec(m, "aggregator") for m in raw_aggregator]

    return ProvidersConfig(panelists=panelists, aggregator=aggregator)


def load_humor_config(path: str) -> HumorConfig | None:
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        return None
    except yaml.YAMLError as exc:
        raise ValueError(f"{path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict) or "agents" not in raw:
        raise ValueError(f"{path} is missing required top-level 'agents' key")

    agents = raw["agents"] or {}
    framer_raw = agents.get("framer") or {}
    satirist_raw = agents.get("satirist") or {}
    critic_raw = agents.get("critic") or {}

    framer = FramerHumor(
        wordplay_scan=bool(framer_raw.get("wordplay_scan", True)),
        joke_types=list(
            framer_raw.get(
                "joke_types", ["situational", "wordplay", "absurdist", "deadpan"]
            )
        ),
        language_register=str(framer_raw.get("language_register", "vernacular")),
        inconvenience=int(framer_raw.get("inconvenience", 0)),
    )
    satirist = SatiristHumor(
        preferred_style=str(satirist_raw.get("preferred_style", "deadpan")),
        avoid=list(satirist_raw.get("avoid", [])),
        subversion=str(satirist_raw.get("subversion", "high")),
        joke_explanation=bool(satirist_raw.get("joke_explanation", True)),
        inconvenience=int(satirist_raw.get("inconvenience", 0)),
    )
    critic = CriticHumor(
        evaluate_joke_mechanics=bool(critic_raw.get("evaluate_joke_mechanics", True)),
        flag_if_no_subversion=bool(critic_raw.get("flag_if_no_subversion", True)),
        inconvenience=int(critic_raw.get("inconvenience", 0)),
        dual_satirist=bool(critic_raw.get("dual_satirist", False)),
    )

    return HumorConfig(framer=framer, satirist=satirist, critic=critic)
