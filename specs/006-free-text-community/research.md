# Research: Free-Text Community Mode

## Decision 1: Where inference lives

**Decision**: New functions in `agents/trend_scout.py` — `infer_brief_from_description(description)` and `get_topics_for_description(description, n, adapter)`.

**Rationale**: Trend Scout already owns the full responsibility for "given a community, return ranked headlines". Free-text mode is the same contract with the community described in prose rather than config. Keeping it in the same module avoids a new import chain and keeps the pipeline call sites clean. No new module is needed.

**Alternatives considered**:
- New `agents/community_inferrer.py` module: adds a file and import chain for what is effectively two functions. Rejected — not enough substance to justify a new module.
- Inference in `pipeline.py` directly: mixes orchestration with LLM call logic. Rejected — pipeline.py should stay thin.

---

## Decision 2: Inference prompt shape

**Decision**: Single Gemini call with a structured JSON output prompt asking for `{target_audience, output_language, tone}`. System prompt instructs the model to respond with only a JSON object — no markdown, no explanation.

**Rationale**: One round-trip is sufficient; the three fields are short and unambiguous to extract. JSON output is deterministic and already used elsewhere in the codebase (headline ranking). Using the same Gemini model (`gemini-2.5-flash`) as headline ranking keeps the fallback chain consistent.

**Defaults when inference is ambiguous**: audience = `"general public"`, language = `"English"`, tone = `"dry wit"`. A log WARNING is emitted when defaults are applied.

**Alternatives considered**:
- Returning a full `Community` object with a synthetic name: unnecessary — only `StrategyBrief` fields are needed downstream.
- Using Claude for inference: adds Anthropic cost for a short structural task that Gemini already handles well. Rejected.

---

## Decision 3: Default news sources for free-text fetch

**Decision**: Add a module-level constant `_DEFAULT_NEWS_SOURCES` in `trend_scout.py`:

```python
_DEFAULT_NEWS_SOURCES = [
    NewsSource(country="us", category="general", count=10),
    NewsSource(country="gb", category="general", count=10),
]
```

These are used when calling the adapter in `get_topics_for_description()`, since there is no community object with configured news_sources.

**Rationale**: US and UK cover the broadest English-language satirical territory and already power the existing `uk-politics` and `us-startup-crowd` communities. Adding them as a default gives meaningful headlines for most descriptions without requiring configuration. The adapter already handles multi-source merges.

**Alternatives considered**:
- Configurable default sources in `communities.yaml` under a `defaults:` key: adds schema complexity for marginal gain. Rejected.
- Using only US: excludes UK-relevant stories for the most common non-US audience. Rejected.
- Infer country from description: adds another LLM call and complexity. Rejected — default list is sufficient.

---

## Decision 4: Ranking prompt for free-text mode

**Decision**: Reuse `_rank_with_gemini()` as-is. The function already accepts a `Community` object for the profile. For free-text mode, construct a temporary `Community` from the inferred `StrategyBrief` plus the free-text description as the `name` field.

Actually — on review, constructing a fake `Community` just to pass to `_rank_with_gemini` is confusing. Better: add an overload parameter or a separate internal function.

**Revised decision**: Extract a private `_rank_headlines(headlines, audience, language, tone, description_hint, n)` helper used by both `get_topics()` (passing community fields) and `get_topics_for_description()` (passing inferred fields + original description as hint). The `description_hint` is appended to the ranking prompt when set, giving the model the raw community description for sharper relevance scoring.

**Rationale**: The raw description ("US community that dislikes Trump") contains information (political lean, specific figures) that structured fields alone would lose. Passing it as a hint to the ranking prompt produces more relevant results without changing the existing named-community path.

---

## Decision 5: Handling missing communities.yaml in free-text mode

**Decision**: In `pipeline.py`, check `os.path.exists("communities.yaml")` before calling `load_communities()`. If absent, `communities` is set to `[]` and the lookup finds no match, falling through to free-text inference — no crash, no error logged.

**Rationale**: `load_communities()` currently raises `ValueError("Config file not found: ...")` for a missing file — this is correct for the named-community mode. Rather than changing the existing function's semantics, a pre-check in `pipeline.py` is less invasive and keeps `load_communities` strict.

**Alternatives considered**:
- Add `load_communities_optional(path)` that returns `[]` on file absence: cleaner but adds a new public function for a small use case. Deferred — the `os.path.exists` check is simpler and sufficient.

---

## Decision 6: Output folder naming for free-text mode

**Decision**: Use `sanitize_path_segment(args.community)` — the same function used for topic sanitisation. The result is truncated at 50 chars. Example: `"US community that dislikes Trump"` → `output/us_community_that_dislikes_trump/`.

**Rationale**: Consistent with existing sanitisation logic; no new code needed.

---

## Decision 7: Empty `--community` validation

**Decision**: Add an explicit check in `pipeline.py` after argument parsing: `if args.community is not None and not args.community.strip(): sys.exit(1)`.

**Rationale**: `argparse` does not reject empty strings; an empty community description would produce a nonsense inference call. Validate at the entry point before any network calls.

---

## All NEEDS CLARIFICATION markers

None in the spec. All design decisions resolved above.
