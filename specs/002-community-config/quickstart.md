# Quickstart: Stage 2 Community Configuration

**Branch**: `002-stage-2-community-config` | **Date**: 2026-05-03

Integration scenarios for validating Stage 2 end-to-end. All scenarios assume `.env` is present with valid
API keys and `communities.yaml` exists at the project root (provided with the repo).

---

## Scenario 1 — Run for a named community

```bash
python pipeline.py --community uk-tech-engineers
```

**Expected**:
- Log line: `Selected community: uk-tech-engineers`
- Log line: `Selected topic: <one of the uk-tech-engineers topics>`
- Log line: `Output path: output/uk_tech_engineers/<sanitized_topic>.png`
- Pipeline completes; image file exists at the logged path
- No `communities.yaml`-related error

---

## Scenario 2 — Run with no arguments (random community)

```bash
python pipeline.py
```

**Expected**:
- Log line: `Selected community: <any valid community name>`
- Log line: `Selected topic: <topic from that community>`
- Pipeline completes; image file exists at the correct output path
- On repeated runs, different communities and topics appear (statistical, not deterministic)

---

## Scenario 3 — Manual mode (no communities.yaml required)

```bash
# Rename communities.yaml temporarily to verify manual mode doesn't need it
mv communities.yaml communities.yaml.bak
python pipeline.py --topic "AI hype" --audience "developers" --language "English" --tone "dry"
mv communities.yaml.bak communities.yaml
```

**Expected**:
- No error about missing config file
- Log line: `Manual mode — topic: AI hype`
- Log line: `Output path: output/manual/ai_hype.png`
- Image saved to `output/manual/ai_hype.png`

---

## Scenario 4 — Unknown community name

```bash
python pipeline.py --community does-not-exist
```

**Expected**:
- Exit code 1
- Stderr: `Error: community "does-not-exist" not found in communities.yaml`
- No API call made (no model log lines)

---

## Scenario 5 — Missing communities.yaml (community mode)

```bash
mv communities.yaml communities.yaml.bak
python pipeline.py
mv communities.yaml.bak communities.yaml
```

**Expected**:
- Exit code 1
- Stderr: `Error: communities.yaml not found at <project root>/communities.yaml`
- No API call made

---

## Scenario 6 — Argument conflict

```bash
python pipeline.py --community uk-tech-engineers --topic "AI hype" --audience "devs" --language "English" --tone "dry"
```

**Expected**:
- Exit code 1
- Stderr: `Error: --community and manual mode flags (--topic, --audience, --language, --tone) are mutually exclusive`
- No API call made

---

## Scenario 7 — Non-English community (language compliance path)

```bash
python pipeline.py --community portuguese-adults
```

**Expected**:
- Pipeline runs; Critic checks for English leakage in Portuguese output
- Output path: `output/portuguese_adults/<sanitized_topic>.png`
- Image caption and board text are in Portuguese

---

## Scenario 8 — Output path sanitization

```bash
python pipeline.py --topic "Is Scrum really Agile?" --audience "engineers" --language "English" --tone "sarcastic"
```

**Expected**:
- Output path: `output/manual/is_scrum_really_agile.png`
- Topic sanitized correctly: lowercase, spaces→underscores, `?` stripped

---

## Scenario 9 — Logging format verification

Run any scenario above and confirm every log line matches the format:

```
YYYY-MM-DD HH:MM:SS [module_name] LEVEL message
```

No bare `print()` output should appear outside of argparse error messages.
