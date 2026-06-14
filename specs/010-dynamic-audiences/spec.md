# Feature Specification: Dynamic audience inference for the gata CLI

**Feature Branch**: `011-dynamic-audiences`
**Created**: 2026-06-14
**Status**: Draft

## Summary

Replace the hardcoded `_AUDIENCES` list in `agents/cli.py` with a call to a new
`infer_audiences(topic)` function in `agent_cultural_strategist.py`. The function makes a
single Gemini call asking it to identify the 2–4 most relevant audiences for the topic,
their languages, and their comedy norms. A UK audience is always guaranteed — if the
inferred list does not include one, a hardcoded UK entry is appended.

## User Scenarios

### User Story 1 — Audiences are inferred from the topic (Priority: P1)

Running `gata "World Cup Qatar vs Swiss"` produces images for audiences that are actually
relevant to that topic (e.g. Swiss, Qatari, global) rather than a fixed set that may be
irrelevant for other topics.

**Acceptance Scenarios**:

1. **Given** a topic about a Swiss/Qatari event, **When** `gata` runs, **Then** the inferred
   audiences include Swiss and Qatari entries.
2. **Given** a topic about US tech layoffs, **When** `gata` runs, **Then** the inferred
   audiences reflect US and tech-adjacent audiences rather than Swiss/Qatari.
3. **Given** any topic, **When** `gata` runs, **Then** a UK audience is always present in
   the final list.

### User Story 2 — UK audience is always present (Priority: P1)

Even if the Framer does not infer a UK-relevant audience, the UK entry is appended.

**Acceptance Scenarios**:

1. **Given** inferred audiences contain no UK entry, **When** `cli.py` builds the final
   list, **Then** a UK entry (`language: English`, `tone: dry British wit`) is appended.
2. **Given** inferred audiences already contain a UK entry, **When** `cli.py` checks,
   **Then** no duplicate is added.

### Edge Cases

- If inference fails (JSON parse error, API error), fall back to the hardcoded
  `_AUDIENCES` default list (Swiss, Qatar, Global English) plus the UK guarantee, so the
  run still produces output.

## Technical Design

### New type (`agents/types.py`)

```python
@dataclass
class AudienceProfile:
    name: str      # slug used as output filename, e.g. "swiss"
    audience: str  # human description, e.g. "Swiss German-speaking public"
    language: str
    tone: str
```

### New function (`agents/agent_cultural_strategist.py`)

```python
def infer_audiences(topic: str) -> list[AudienceProfile]
```

- Single Gemini call (`gemini-2.5-flash`), temperature 0.2
- System prompt instructs the model to identify 2–4 audiences, infer language, and reason
  about comedy norms from cultural knowledge
- Returns parsed `list[AudienceProfile]`; on any parse failure returns the fallback list

### UK guarantee (`agents/cli.py`)

After `infer_audiences()` returns, check whether any profile contains "uk", "british", or
"united kingdom" (case-insensitive) in its `name` or `audience` fields. If not, append:

```python
AudienceProfile(name="uk", audience="UK public", language="English", tone="dry British wit")
```

### Modified files

| File | Change |
|------|--------|
| `agents/types.py` | Add `AudienceProfile` dataclass |
| `agents/agent_cultural_strategist.py` | Add `infer_audiences(topic)` function |
| `agents/cli.py` | Replace `_AUDIENCES` constant with `infer_audiences()` call + UK guarantee |
| `pyproject.toml` | Bump version to `1.2.0` |
| `agents/__version__.py` | Bump to `1.2.0` |
