# Feature Specification: Multi-Audience CLI — `gata <topic>` command

**Feature Branch**: `009-multi-audience-cli`
**Created**: 2026-06-13
**Status**: Draft

## Summary

Add a `gata` console-script entry point (installed with `pip install gata`) that accepts a
single free-text topic and generates three satirical cartoons in parallel — one for the Swiss
public (Swiss German), one for the Qatari public (Arabic), and one for a global English
audience. Output lands in a subdirectory of the caller's working directory, named after the
topic slug. No knowledge of `pipeline.py`, `communities.yaml`, or the agent internals is
required.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Generate three audience-adapted images from a topic (Priority: P1)

A user installs `gata` from PyPI, sets `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`, then runs
`gata "World Cup Qatar vs Swiss"`. After the pipeline completes they find three PNG files plus
per-image bundles in a `world_cup_qatar_vs_swiss/` folder in their working directory: one
image in Swiss German, one in Arabic, one in English. Each image is satirically tailored to
its target audience — the Swiss image uses Swiss cultural references, the Qatari image uses
Gulf cultural references, and the global image uses internationally accessible framing.

**Why this priority**: This is the entire purpose of the feature.

**Independent Test**: Run `gata "Test topic for CI"` and verify three PNGs appear in
`test_topic_for_ci/`.

**Acceptance Scenarios**:

1. **Given** valid API keys and a topic string, **When** `gata "<topic>"` runs, **Then** three
   PNG files (`swiss.png`, `qatar.png`, `global.png`) are created in `<topic_slug>/`.
2. **Given** each image, **When** inspected, **Then** the Swiss image references Swiss cultural
   context in German, the Qatari image uses Arabic and Gulf cultural references, and the global
   image is in English with internationally legible satire.
3. **Given** a topic, **When** two images for different audiences are compared, **Then** the
   satirical angle, cultural references, and visual style differ between them.

---

### User Story 2 — Partial failure does not suppress successful images (Priority: P1)

One audience's pipeline run fails (e.g. image model quota exceeded). The other two images are
still written and the CLI exits with code 1 to signal the partial failure.

**Acceptance Scenarios**:

1. **Given** one audience fails at the image generation step, **When** the run completes,
   **Then** the two successful PNGs are present and the one failed audience's PNG is absent.
2. **Given** a partial failure, **When** the CLI exits, **Then** exit code is 1.
3. **Given** all three audiences fail, **When** the CLI exits, **Then** exit code is 1 and no
   PNGs are written.

---

### User Story 3 — Output lands in caller's working directory (Priority: P1)

The user runs `gata` from any directory and output appears there, not in the package
installation directory.

**Acceptance Scenarios**:

1. **Given** cwd is `/home/user/projects/`, **When** `gata "Test"` runs, **Then** output is in
   `/home/user/projects/test/`.
2. **Given** a topic with spaces and punctuation, **When** the slug is created, **Then** the
   folder name contains only lowercase alphanumeric characters and underscores.

---

### User Story 4 — humor.yaml is honoured if present in cwd (Priority: P2)

If `humor.yaml` exists in the caller's working directory it is loaded and applied to all three
runs, exactly as it would be for `python pipeline.py`.

**Acceptance Scenarios**:

1. **Given** a `humor.yaml` in cwd, **When** `gata` runs, **Then** the humor config is applied
   to all three audience runs.
2. **Given** no `humor.yaml` in cwd, **When** `gata` runs, **Then** the pipeline runs without
   humor directives and no error is emitted.

---

### Edge Cases

- What if `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` is missing? → Exit 1 with a clear error
  before any API call.
- What if the topic string is empty or whitespace? → Exit 1 with a clear error.
- What if the output directory already exists? → Reuse it; existing files for other audiences
  are not deleted.

## Technical Design

### New files

| File | Purpose |
|------|---------|
| `agents/runner.py` | Public `run_pipeline()` function (extracted from `pipeline._run_pipeline`) |
| `agents/cli.py` | `main()` entry point for the `gata` console script |

### Modified files

| File | Change |
|------|--------|
| `pipeline.py` | Replace inline `_run_pipeline` with import from `agents.runner` |
| `pyproject.toml` | Add `[project.scripts]`, bump version to `1.0.0` |
| `agents/__version__.py` | Bump to `1.0.0` |
| `README.md` | Document `gata` command |
| `TODO.md` | Add this feature |

### Audience profiles (hardcoded MVP)

```python
[
    {"name": "swiss",  "audience": "Swiss public",                  "language": "Swiss German", "tone": "dry Swiss wit"},
    {"name": "qatar",  "audience": "Qatari public",                 "language": "Arabic",       "tone": "Gulf Arabic satire"},
    {"name": "global", "audience": "global English-speaking public","language": "English",      "tone": "international wit"},
]
```

### Output layout

```
{cwd}/{topic_slug}/
├── swiss.png
├── swiss/          ← bundle (logs, HTML, prompt card)
├── qatar.png
├── qatar/
├── global.png
└── global/
```

### Entry point

```toml
[project.scripts]
gata = "agents.cli:main"
```

## PyPI release steps (manual)

After merging this branch to `main`:

1. The version in `pyproject.toml` and `agents/__version__.py` will be `1.0.0`.
2. Create and push a git tag: `git tag v1.0.0 && git push origin v1.0.0`.
3. The `publish.yml` workflow triggers automatically and uploads to PyPI.
