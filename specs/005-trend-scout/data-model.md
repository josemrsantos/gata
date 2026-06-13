# Data Model: Trend Scout

## New entities

### Headline

The atomic unit returned by any source adapter.

```python
@dataclass
class Headline:
    title: str           # headline text
    abstract: str        # short summary (may be empty string)
    source: str          # adapter name, e.g. "newsapi"
    published_at: str    # ISO 8601 date string, e.g. "2026-05-29"
    social_score: float  # engagement score from source; 0.0 if unavailable
```

Stored in `agents/types.py` alongside existing dataclasses.

---

## Modified entities

### Community (agents/types.py)

Add optional `news_sources` field. Existing fields unchanged.

```python
@dataclass
class NewsSource:
    location_uri: str    # Wikipedia URI for country/region filter
    count: int = 10      # max headlines to fetch from this source

@dataclass
class Community:
    name: str
    target_audience: str
    output_language: str
    tone: str
    topics: list[str] = field(default_factory=list)
    news_sources: list[NewsSource] = field(default_factory=list)  # NEW
```

`news_sources` is optional — communities without it use only the seed topic fallback.

---

## communities.yaml schema extension

```yaml
communities:
  - name: uk-tech-engineers
    target_audience: British software engineers and developers
    output_language: English
    tone: dry British wit
    topics:
      - Agile ceremonies that could have been an email
    news_sources:                                              # NEW (optional)
      - location_uri: "http://en.wikipedia.org/wiki/United_Kingdom"
        count: 10
```

Communities without `news_sources` continue to work unchanged.

---

## Source adapter interface (agents/sources/base.py)

```python
from abc import ABC, abstractmethod
from agents.types import Community, Headline

class SourceAdapter(ABC):
    @abstractmethod
    def fetch(self, community: Community) -> list[Headline]:
        """Return headlines for the community. Return [] on any failure."""
```

---

## State transitions

```
pipeline invoked
    │
    ├─ --topic supplied ──────────────────────────────► topic (manual override)
    │
    └─ no --topic
           │
           ├─ community.news_sources non-empty
           │       │
           │       ├─ fetch + rank succeeds ──────────► topic (from Trend Scout)
           │       │
           │       └─ fetch/rank fails or empty ───────► topic (from seed fallback)
           │
           └─ community.news_sources empty ────────────► topic (from seed fallback)
```