# Data Model: Multi-Panel Cartoon Format

**Feature**: specs/007-multi-panel-cartoon/
**Phase**: 1 — Design
**Date**: 2026-06-11

## New Entities

### PanelConcept — `agents/types.py`

Represents one panel in a multi-panel cartoon strip. Contains everything the image generator needs to render that panel's scene.

```python
@dataclass
class PanelConcept:
    scene: str    # Full scene description for this panel (passed verbatim to image model)
    caption: str  # Caption text beneath this panel (1–2 sentences, in output_language)
    beat: str     # Narrative position: "setup" | "escalation" | "punchline" | free text
```

**Validation rules**:
- `scene` must be non-empty
- `caption` must be non-empty; 1–2 sentence limit enforced by satirist prompt instruction
- `beat` must be non-empty; the pipeline treats it as informational and does not validate its value
- `PanelConcept` is never written to disk; it is consumed by the image generator within a single pipeline run

**JSON schema** (as returned by satirist inside `<verdict>`):
```json
{"scene": "<string>", "caption": "<string>", "beat": "<string>"}
```

---

### CartoonLayout — `agents/types.py`

Configuration for a multi-panel run. Created in `pipeline.py` and passed to both the satirist and image generator agents.

```python
@dataclass
class CartoonLayout:
    panels: int = 1               # Number of panels: 1, 2, 3, or 4
    direction: str = "horizontal" # "horizontal" | "vertical"
```

**Validation rules** (enforced in `pipeline.py` before any API call, per FR-010):
- `panels` must be an integer in [1, 4]; values outside this range → `sys.exit(1)` with descriptive error
- `direction` must be `"horizontal"` or `"vertical"`; any other value → `sys.exit(1)` with descriptive error
- When `panels == 1`, `direction` is ignored and the single-panel code path runs unchanged (FR-009)

**Source precedence** (FR-004):
```
CLI --panels / --layout       (highest priority)
         ↓
Community config panels / layout
         ↓
Defaults: panels=1, direction="horizontal"
```

---

## Modified Entities

### CartoonConcept — `agents/types.py`

Extended with an optional `panels` field. The single-panel path never sets `panels` and is entirely unaffected.

```python
@dataclass
class CartoonConcept:
    full_text: str
    image_prompt: str                          # Empty string for multi-panel; populated for single-panel
    iteration: int
    panels: list[PanelConcept] | None = None  # None = single-panel path; list = multi-panel path
```

**Invariant**: For a given instance, exactly one of `image_prompt` (non-empty) or `panels` (non-None) is set. The image generator checks `concept.panels is not None` to select the multi-panel path.

---

### Community — `agents/types.py`

Extended with optional panel layout configuration (FR-003). Both new fields have defaults, preserving backwards compatibility with existing `communities.yaml` files.

```python
@dataclass
class Community:
    name: str
    target_audience: str
    output_language: str
    tone: str
    topics: list[str] = field(default_factory=list)
    news_sources: list[NewsSource] = field(default_factory=list)
    panels: int = 1               # NEW — optional; default 1 (single-panel)
    layout: str = "horizontal"    # NEW — optional; default "horizontal"
```

**config_loader.py loading**:
```python
panels = int(community_data.get("panels", 1))
layout = community_data.get("layout", "horizontal")
```

---

## Entity Relationships

```
pipeline.py
    │
    ├─ resolves CLI + community config ──→ CartoonLayout
    │                                           │
    │                                     ┌────┴────┐
    │                                     ↓         ↓
    ├─ agent_satirist.run(layout=layout)  agent_image_generator.generate(layout=layout)
    │          │                                     ↑
    │          └──→ CartoonConcept ─────────────────┘
    │                   │
    │                   ├── image_prompt  (single-panel: non-empty)
    │                   └── panels        (multi-panel: list[PanelConcept])
    │                              └── PanelConcept × N
```

## YAML Schema Extension (`communities.yaml`)

```yaml
# Existing fields unchanged; new fields are optional
- name: uk-politics
  target_audience: "UK politically engaged adults"
  output_language: "English"
  tone: "dry wit"
  topics: [...]
  news_sources: [...]
  panels: 3           # NEW optional — default 1 if absent
  layout: horizontal  # NEW optional — default "horizontal" if absent
```
