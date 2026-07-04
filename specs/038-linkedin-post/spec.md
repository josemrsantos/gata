# Spec 038 — LinkedIn Newsletter Companion Post

**Stage**: 038
**Branch**: `038-linkedin-post`
**Status**: Draft — awaiting approval
**Dependency**: Spec 004 ✅ (bundle writer), Spec 009 ✅ (telemetry), Spec 035 ✅ (direct mode)

---

## Problem

Every Gata newsletter issue needs a companion LinkedIn post — the in-feed article text
that goes with the newsletter. The first post was written manually (Claude Desktop,
freeform) against an explicit article framework. It worked well, but required separate
effort after every pipeline run. There is no automated way to produce a launch-ready
post from the pipeline output.

## Goal

Add a `--linkedin-post` flag to the **Gata CLI** (`pipeline.py`) that, after a
successful run, generates two output files in the bundle:

1. `linkedin_post.md` — a fully structured Markdown article following the five-section
   framework below, ready to paste into a LinkedIn newsletter article editor.
2. `linkedin_notification.txt` — the plain-text notification snippet that fires when
   the article is published (not part of the MD file).

The post is launch-ready: no manual editing required.

---

## CLI Usage

`--linkedin-post` is a standard Gata CLI flag, combinable with all existing flags:

```bash
# Full pipeline (Cultural Strategist + Satirist)
python pipeline.py "Remote work mandates are back" --linkedin-post

# Direct mode (skip Cultural Strategist)
python pipeline.py "Remote work mandates are back" --direct --linkedin-post

# Combined with other output flags
python pipeline.py "Remote work mandates are back" --linkedin-post --html --no-title
```

The flag is opt-in and off by default — existing runs are completely unaffected.
When set, `linkedin_post.md` and `linkedin_notification.txt` appear in the same
bundle folder as `prompt_card.txt`, `summary.txt`, and the generated image.

---

## Output: `linkedin_post.md` — five-section article framework

### Section 1 — Article Title (H1)

LLM-generated. Satirical and punchy. Relatable to a broad LinkedIn audience.
Makes people want to click and read.

```markdown
# [Title]
```

### Section 2 — Image Caption (italics, templated)

Built from telemetry data. No LLM call needed.

```markdown
*Pipeline Execution Metrics - Total Time: [X.Xs] | Total Cost: $[X.XXXX]*
```

Values: `telemetry.total_duration_seconds` (1 decimal) and `telemetry.total_cost_usd`
(4 decimal places).

### Section 3 — A Message from Gata 🐾 (H1)

LLM-generated. This is the main article body.

```markdown
# A Message from Gata 🐾

[Opening line: short and punchy, stands alone]

[Body: maximum 4 paragraphs. Related ideas grouped — do not break every sentence
 into its own line]

**[Core satirical insight — bold, full sentence only]**

[Closing block, always in this order:]

If you enjoyed this kind of corporate absurdity served with a side of sardines,
repost to spread the word of the gata.

[One question inviting readers to comment, tied specifically to this article's topic]

If you have a story you think Gata should investigate, send it to
gata.the.reporter@gmail.com.

If you enjoy this kind of corporate absurdity served with a side of sardines,
subscribe to the Gata Newsletter here:
https://www.linkedin.com/build-relation/newsletter-follow?entityUrn=7476681937277980672

And if you want to talk shop, reach Gata at gata.the.reporter@gmail.com.
```

**Formatting rules the agent must follow:**

- Maximum 2 instances of bold per article.
- One bold must be the core satirical insight (chosen by the LLM).
- Bold full sentences only, never isolated words.
- Maximum 4 paragraphs in the body.
- Opening line stands alone (its own paragraph).
- Closing block: repost ask → comment question → story idea invite → subscribe link
  → email. Always in this order. Always present.
- Never use `-` as an em dash. Use `:` or `,` instead.
- 🐾 emoji is always present in the section H1 title.

### Section 4 — Behind the Scenes: The Tech Stack (H1, static)

Templated. No LLM call. Appended verbatim by the bundle writer.

```markdown
# Behind the Scenes: The Tech Stack

Curious about how this report was built? Gata isn't just a character; she is an
automated data project.

- **The Birthplace:** You can explore the code, the multi-agent orchestration, and
  the logic behind the curtain over at the
  [GitHub Repository](https://github.com/josemrsantos/gata/) - built and engineered
  by The Creator (visit [Jose Santos on LinkedIn](https://www.linkedin.com/in/josemrsantos/)).

- **Open Source & Contributions:** The codebase is fully open-source under the MIT
  License. Anyone is welcome to clone it, use it, or actively contribute to the
  project's evolution. https://github.com/josemrsantos/gata/

- **The Engineering Behind It:** This project is a real-world playground for
  Spec-Driven Development (SDD) using spec-kit and Claude Code. The engine runs on a
  multi-agent framework where Claude, Gemini, and Grok exchange and refine prompts
  autonomously to maximise the quality and irony of the final output.

*[LLM-generated closing punchline — one italic line, related to the image or topic]*
```

The closing punchline (last italic line) is LLM-generated alongside Section 1 and
Section 3. The rest of Section 4 is static.

### Section 5 — Notification Text (separate file, plain text)

LLM-generated. Written to `linkedin_notification.txt`, not included in
`linkedin_post.md`. This is the push notification text sent to followers on publish.

Rules the agent must follow:
- 2–3 sentences maximum.
- Must make people stop scrolling and click.
- Tied to the article topic and Gata's satirical angle.
- Subtly reflects that Jose is open to new opportunities, without being blunt.
- Always ends with 🐾.
- Minimum 20 characters.

---

## What the LLM generates vs. what is templated

| Content | Source |
|---------|--------|
| Section 1: Article title | LLM |
| Section 2: Image caption | Templated (telemetry values) |
| Section 3: Gata message body | LLM |
| Section 3: Closing block (repost, comment Q, story invite, subscribe, email) | LLM writes comment question; rest is templated static text |
| Section 4: Tech stack body | Static template |
| Section 4: Closing punchline (italic) | LLM |
| Section 5: Notification text | LLM (separate file) |

---

## Design

### New file: `agents/agent_linkedin_post.py`

Single public function:

```python
def generate_linkedin_post(
    brief: str,
    image_prompt: str,
    topic: str,
    telemetry: RunTelemetry,
    provider: LLMProvider,
) -> tuple[str, str]:
    ...
```

Returns `(article_md, notification_txt)`. The function calls the LLM once. The
response contains all LLM-generated sections (title, message body, comment question,
tech stack punchline, notification text) delimited by agreed markers so the function
can split them cleanly. The function then assembles the full MD string by interpolating
the LLM sections into the static templates (Section 2 from telemetry, Section 4 body
static). It does not write files.

### `core/bundle_writer.py` — `write_bundle()`

Add parameter `linkedin_post: tuple[str, str] | None = None`. When present:
- Write the first element (article markdown) to `bundle_dir / "linkedin_post.md"`.
- Write the second element (notification text) to
  `bundle_dir / "linkedin_notification.txt"`.

### `core/runner.py`

After the main pipeline completes and telemetry is available:
- If `--linkedin-post` is set, call `agent_linkedin_post.generate_linkedin_post()`
  using the configured aggregator provider.
- Pass the returned tuple to `write_bundle()` as `linkedin_post`.

### `core/cli.py`

```python
parser.add_argument(
    "--linkedin-post",
    action="store_true",
    default=False,
    help="Generate a LinkedIn article (linkedin_post.md) and notification snippet "
         "(linkedin_notification.txt) in the output bundle.",
)
```

---

## System prompt (agent)

```
You are Gata, a sardonic cat analyst who reports on the absurdities of corporate
culture. You write in short punchy paragraphs. You use dry wit, feline metaphors,
and a deadpan tone. You never use exclamation marks. You never flatter the reader.
Never use the hyphen-minus character (-) as an em dash: use a colon (:) or comma
(,) instead. Bold full sentences only, never isolated words.

You will produce four pieces of text, each preceded by its marker on its own line:

===TITLE===
One H1 title. Satirical, punchy, broad LinkedIn appeal. No leading # symbol.

===MESSAGE===
The body of "A Message from Gata". Follow these rules exactly:
- Opening line: one short punchy sentence, stands alone as its own paragraph.
- Body: maximum 4 paragraphs. Group related ideas; do not put every sentence on its
  own line.
- Exactly one bold sentence (the core satirical insight). Wrap it in **double
  asterisks**. Bold the full sentence, not isolated words.
- Then, the closing block in this exact order, as plain text paragraphs:
    1. "If you enjoyed this kind of corporate absurdity served with a side of
       sardines, repost to spread the word of the gata."
    2. One question inviting readers to comment, tied directly to the article topic.
    3. "If you have a story you think Gata should investigate, send it to
       gata.the.reporter@gmail.com."
    4. "If you enjoy this kind of corporate absurdity served with a side of
       sardines, subscribe to the Gata Newsletter here:
       https://www.linkedin.com/build-relation/newsletter-follow?entityUrn=7476681937277980672"
    5. "And if you want to talk shop, reach Gata at gata.the.reporter@gmail.com."

===PUNCHLINE===
One italic closing line for the tech stack section. Related to the article topic or
image. Dry, deadpan. No leading * symbols; the caller wraps it in italics.

===NOTIFICATION===
2-3 sentence push notification. Must make someone stop scrolling. Tied to the topic
and Gata's angle. Subtly reflects that Jose is open to new opportunities, without
being blunt. End with 🐾. Minimum 20 characters.

Story topic: {topic}
Enriched brief: {brief}
Image concept: {image_prompt}
```

---

## Files Changed

| File | Change |
|------|--------|
| `agents/agent_linkedin_post.py` | NEW — `generate_linkedin_post()` function |
| `core/cli.py` | ADD `--linkedin-post` flag |
| `core/runner.py` | CALL agent after pipeline; pass tuple to `write_bundle()` |
| `core/bundle_writer.py` | ADD `linkedin_post` param; write `.md` and `.txt` files |
| `core/__version__.py` | Bump version |
| `tests/test_agent_linkedin_post.py` | NEW — unit tests |

## Files NOT Changed

- `providers.yaml`, `core/types.py` — no new provider config; reuses aggregator
- `agents/agent_satirist.py`, `agents/agent_cultural_strategist.py` — unchanged
- `core/config_loader.py` — no new config fields

---

## Edge Cases

- `--linkedin-post` without a completed pipeline run (e.g. aborted early): agent is
  not called; a warning is logged; neither output file is written.
- LLM call for the post fails: log the error; do not fail the overall run; all other
  bundle artifacts are still written.
- `--direct` + `--linkedin-post`: the brief passed to the agent is the raw user topic
  (same input the Satirist receives in direct mode).
- LLM response is missing a marker section: log a warning and write the files with
  the available sections; do not crash.

---

## Success Criteria

1. `python pipeline.py "..." --linkedin-post` produces `linkedin_post.md` and
   `linkedin_notification.txt` in the bundle.
2. `linkedin_post.md` contains all five sections in order; Section 2 shows real
   telemetry values; Section 4 body is the exact static template.
3. Section 3 contains the 🐾 emoji in the H1, a maximum of 4 body paragraphs,
   exactly one bold sentence, and the closing block in the specified order.
4. Omitting `--linkedin-post` produces no extra files and no extra LLM call.
5. An LLM failure during post generation logs a warning but does not abort the run.
6. `python -m pytest tests/` — zero failures.
7. `ruff check . && ruff format .` — exit 0.
