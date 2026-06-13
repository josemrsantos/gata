# Quickstart: Multi-Panel Cartoon Format

**Feature**: specs/007-multi-panel-cartoon/
**Phase**: 1 — Design
**Date**: 2026-06-11

## End-to-End Invocations

### Named community — 3-panel horizontal strip (US1)

```bash
python pipeline.py --community uk-politics --panels 3 --layout horizontal
```

Expected output path:
```
output/uk-politics_<topic-slug>/3h_english_<topic-slug>.png
```

A single PNG containing 3 horizontally arranged panels with visible borders and per-panel captions.

---

### Named community — 2-panel vertical strip (US2)

```bash
python pipeline.py --community uk-politics --panels 2 --layout vertical
```

Expected output path:
```
output/uk-politics_<topic-slug>/2v_english_<topic-slug>.png
```

A single PNG containing 2 vertically stacked panels with visible borders and per-panel captions.

---

### Free-text community — 3-panel horizontal (US1 + Stage 8)

```bash
python pipeline.py --community "US techies who follow AI news" --panels 3 --layout horizontal
```

Expected output path:
```
output/us_techies_who_follow_ai_news_<topic-slug>/3h_english_<topic-slug>.png
```

---

### Manual mode with panels (RULE 12 compliance)

```bash
python pipeline.py \
  --topic "AI hype reaches peak" \
  --audience "UK tech readers" \
  --language English \
  --tone "dry wit" \
  --panels 3 \
  --layout horizontal
```

---

### Community config — no CLI panel flags needed (US3)

Add to `communities.yaml`:

```yaml
- name: uk-politics
  target_audience: "UK politically engaged adults"
  output_language: "English"
  tone: "dry wit"
  topics: [...]
  panels: 3
  layout: horizontal
```

Then run without panel flags:

```bash
python pipeline.py --community uk-politics
```

Output is a 3-panel horizontal strip using the community config.

---

### CLI override of community config (US3 AC3)

Community has `panels: 3` in its config, but the operator wants 2 panels for this run:

```bash
python pipeline.py --community uk-politics --panels 2
```

Output is a 2-panel horizontal strip (CLI takes precedence; layout defaults to horizontal).

---

### Single-panel — unchanged (US4)

```bash
python pipeline.py --community uk-politics
# or equivalently:
python pipeline.py --community uk-politics --panels 1
```

Output is identical to pre-feature single-panel output. No `<Nh|Nv>_` prefix in the filename.

---

## Output File Naming Convention

| Panels | Direction | Filename prefix |
|--------|-----------|----------------|
| 1 | — | *(none — unchanged)* |
| 2 | horizontal | `2h_` |
| 2 | vertical | `2v_` |
| 3 | horizontal | `3h_` |
| 3 | vertical | `3v_` |
| 4 | horizontal | `4h_` |
| 4 | vertical | `4v_` |

Full path pattern for multi-panel runs:
```
output/<community-slug>_<topic-slug>/<Nh|Nv>_<language>_<topic-slug>.png
```

---

## Error Cases

```bash
# Too many panels — exits before any API call
python pipeline.py --community uk-politics --panels 5
# ERROR: --panels must be between 1 and 4

# Invalid layout string — exits before any API call
python pipeline.py --community uk-politics --panels 3 --layout diagonal
# ERROR: --layout must be 'horizontal' or 'vertical'
```
