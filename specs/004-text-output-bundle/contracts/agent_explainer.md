# Contract: agent_explainer

**Module**: `agents/agent_explainer.py`
**Role**: Dual-LLM agent that generates HTML explanation files from pipeline outputs.

---

## Public Interface

```python
def generate_html(
    enriched_brief: EnrichedBrief,
    agent0_log: ConversationLog,
    bc_log: ConversationLog,
    image_prompt: str,
) -> tuple[str, str]:
    ...
```

**Returns**: `(in_language_html, english_html)` — both are complete, valid HTML strings.

**Raises**: `RuntimeError` if all models are exhausted for either persona on either call.

---

## Personas

### Writer (Proposer) — Claude claude-sonnet-4-6

System prompt instructs the Writer to generate a complete, self-contained HTML page. The
Writer uses the `<verdict>` tag to wrap its HTML output:

```
<verdict>
<!DOCTYPE html>
<html lang="{lang}">
...
</html>
</verdict>
```

Fallback model chain: `["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"]`

### Editor (Reviewer) — Gemini gemini-2.5-flash

System prompt instructs the Editor to verify:
1. HTML is valid and self-contained (no external JS/CSS dependencies).
2. For in-language HTML: all text is in the target language (no English leakage).
3. For English HTML: cultural references are explained sufficiently for a cultural outsider.
4. UTF-8 charset declaration is present.
5. Content explains the satirical angle clearly.

If satisfied: `<verdict>APPROVED</verdict>`
If not: `<verdict>NEEDS REVISION</verdict>` followed by specific, actionable feedback.

Fallback model chain: `["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-pro"]`

---

## Loop Parameters

- **Max iterations**: 3 (shorter than creative loops — HTML quality converges faster)
- **Timeout**: 300 seconds
- **Protocol**: Same `DualPersonaLoop` class from `agents/dual_loop.py`

---

## Input Composition

The Writer's initial prompt includes:

```
ENRICHED BRIEF:
Target audience: {enriched_brief.target_audience}
Language: {enriched_brief.output_language}
Tone: {enriched_brief.tone}
Cultural angle: {enriched_brief.cultural_angle}
Key references: {enriched_brief.culturally_loaded_references}

AGENT 0 LOG (summary):
{formatted agent0_log turns — condensed to key decisions}

B/C LOG (summary):
{formatted bc_log turns — condensed to key decisions}

IMAGE PROMPT:
{image_prompt}

TASK:
Generate a {language} HTML explanation page for end users...
```

The English deep-dive uses the same input but asks for an English-language operator briefing.

---

## HTML Requirements (enforced by Editor)

- Valid HTML5 with `<!DOCTYPE html>`
- `<meta charset="UTF-8">` in `<head>`
- `lang` attribute on `<html>` tag matching the target language
- No external resources (no CDN links, no `<script src="">`, no `<link rel="stylesheet">`)
- Semantic structure: one `<h1>`, body paragraphs in `<p>` tags
- No inline `style` attributes that would break in a basic renderer
