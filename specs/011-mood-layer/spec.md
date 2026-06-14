# Feature Specification: Mood Layer — current cultural temperature for the Framer

**Feature Branch**: `012-mood-layer`
**Created**: 2026-06-14
**Status**: Draft

## Summary

Before the Cultural Strategist loop runs, a new `infer_mood()` function makes a single
Gemini call **with Google Search grounding** to establish the current emotional posture of
the target audience toward the topic. The result — a `MoodBrief` — is injected into the
Framer's initial input so its cultural angle is grounded in how people actually feel right
now, not just generic cultural knowledge. Falls back silently if the call fails.

## User Scenarios

### User Story 1 — Mood context enriches the cartoon (Priority: P1)

Running `gata "England vs France World Cup quarter-final"` for a UK audience produces a
cartoon whose cultural angle reflects the *current* English mood (e.g. defensive optimism,
terror disguised as irony) rather than a generic "British humour" angle.

**Acceptance Scenarios**:

1. **Given** a topic with a clear current mood, **When** the pipeline runs, **Then**
   `agent0_log.txt` shows mood context in the Framer's initial input.
2. **Given** the Gemini grounding call fails, **When** the pipeline runs, **Then** it
   continues without mood context and no error is raised.

### User Story 2 — Mood is audience-specific (Priority: P1)

The same topic produces different mood contexts for different audiences — the English mood
toward a World Cup match differs from the French mood.

**Acceptance Scenarios**:

1. **Given** two runs for the same topic with different audiences, **When** both complete,
   **Then** their `agent0_log.txt` files show different mood summaries.

## Technical Design

### New type (`agents/types.py`)

```python
@dataclass
class MoodBrief:
    mood_summary: str        # one paragraph — what the audience feels right now
    emotional_posture: str   # short label e.g. "defensive optimism"
    key_triggers: list[str]  # current references that sharpen the satire
```

### New function (`agents/agent_cultural_strategist.py`)

```python
def infer_mood(topic: str, audience: str, language: str) -> MoodBrief | None
```

- Single Gemini call (`gemini-2.5-flash`) with
  `Tool(google_search=GoogleSearch())` for real-time web grounding
- Returns `MoodBrief` on success, `None` on any failure (parse error, API error)
- Temperature 0.2; JSON output parsed defensively with markdown-fence stripping

### Integration into `agent_cultural_strategist.run()`

`infer_mood()` is called before `DualPersonaLoop.run()`. If it returns a `MoodBrief`,
a `CURRENT MOOD` section is appended to `initial_input`:

```
CURRENT MOOD (use this to sharpen the cultural angle):
[mood_summary]
Emotional posture: [emotional_posture]
Key cultural triggers:
- [trigger 1]
- [trigger 2]
```

No changes to the Framer's system prompt — the mood arrives as richer user-turn context.

### Modified files

| File | Change |
|------|--------|
| `agents/types.py` | Add `MoodBrief` dataclass |
| `agents/agent_cultural_strategist.py` | Add `infer_mood()`; inject into `run()` initial input |
| `pyproject.toml` | Bump version to `1.3.0` |
| `agents/__version__.py` | Bump to `1.3.0` |
