# Data Model: Stage 2 Community Configuration

**Branch**: `002-stage-2-community-config` | **Date**: 2026-05-03

---

## Entities

### Community

Represents a named audience configuration loaded from `communities.yaml`.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `name` | `str` | Yes | Non-blank |
| `target_audience` | `str` | Yes | Non-blank |
| `output_language` | `str` | Yes | Non-blank |
| `tone` | `str` | Yes | Non-blank |
| `topics` | `list[str]` | Yes | Non-empty; each item non-blank |

**Uniqueness**: `name` must be unique across all community entries in the config file. Duplicate names are
a validation error (FR-008).

**Python representation** (`agents/types.py`):

```python
@dataclass
class Community:
    name: str
    target_audience: str
    output_language: str
    tone: str
    topics: list[str]

    def to_brief(self) -> StrategyBrief:
        return StrategyBrief(
            target_audience=self.target_audience,
            output_language=self.output_language,
            tone=self.tone,
        )
```

---

### CommunityConfig

The parsed contents of `communities.yaml`. Not a persistent object — created in memory at startup,
used only for community selection, then discarded.

**YAML schema**:

```yaml
communities:
  - name: <str>
    target_audience: <str>
    output_language: <str>
    tone: <str>
    topics:
      - <str>
      - <str>
```

**Top-level key**: `communities` (list of community entries). The file MUST have this key; a bare list
is not valid.

**Python representation**: `list[Community]` returned by `load_communities()`.

---

### OperatingMode

Determined at invocation from CLI arguments. Not a persistent object.

| Mode | Detection condition | Source of topic & brief |
|------|---------------------|------------------------|
| Community (named) | `--community <name>` provided | Loaded from `communities.yaml`; topic selected at random from community's list |
| Community (random) | No arguments | Loaded from `communities.yaml`; community and topic both selected at random |
| Manual | `--topic`, `--audience`, `--language`, `--tone` all provided | Supplied directly via CLI flags |
| Conflict (error) | `--community` + any manual flag | Pipeline exits with error before any API call |

---

## Relationships

```
communities.yaml
    └── [1..*] Community
                  ├── name             → sanitized → output/{community_name}/
                  ├── target_audience  ─┐
                  ├── output_language   ├─→ StrategyBrief → agent_bc.run()
                  ├── tone             ─┘
                  └── topics [1..*]
                               └── selected topic → sanitized → output/{community_name}/{topic}.png
```

---

## Sanitization Rules

Applied to both `community.name` and the selected `topic` before constructing the output path.

Function: `sanitize_path_segment(text: str) -> str`

1. Lowercase the entire string
2. Replace all spaces with underscores
3. Strip all characters that are not `[a-z0-9_-]` (alphanumeric, underscores, hyphens)
4. Truncate to 50 characters

| Input | Output |
|-------|--------|
| `"UK Tech Engineers"` | `"uk_tech_engineers"` |
| `"uk-tech-engineers"` | `"uk-tech-engineers"` |
| `"Portuguese Adults (18-35)"` | `"portuguese_adults_18-35"` |
| `"Is Scrum really Agile?"` | `"is_scrum_really_agile"` |
| `"Crise habitacional em Lisboa"` | `"crise_habitacional_em_lisboa"` |
| `"AI hype"` | `"ai_hype"` |

---

## Validation Rules (enforced by `config_loader.py` before any API call)

1. File exists at project root (`communities.yaml`)
2. File parses as valid YAML
3. Top-level `communities` key is present and is a list
4. List has at least one entry
5. Each entry has all five required fields present and non-blank
6. Each entry's `topics` list is non-empty and all items are non-blank strings
7. No two entries share the same `name` value (case-sensitive comparison)

Any violation → `ValueError` with a message identifying the problem precisely (file path, community name,
field name as applicable).
