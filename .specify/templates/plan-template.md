# Implementation Plan: [FEATURE NAME]

**Branch**: `NNN-feature-slug` | **Date**: YYYY-MM-DD | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/NNN-feature-slug/spec.md`

## Summary

[2–4 sentences. What is being built? What is the key architectural decision?]

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: [list from pyproject.toml that this stage touches]
**Storage**: [Files / DB / none]
**Testing**: pytest with mocks (no real API calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI pipeline — additive extension
**Performance Goals**: [Latency or throughput target, if any]
**Constraints**: ruff `line-length=88`; [other hard constraints]
**Scale/Scope**: [Size of change]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ | |
| 2 | Image Output Rule | ✅ | |
| 3 | XML and Output Contract | ✅ | |
| 4 | Character Rules | ✅ | |
| 5 | Visual Style Rules | ✅ | |
| 6 | Verdict JSON Schema and Iteration Rules | ✅ | |
| 7 | Language Rule | ✅ | |
| 8 | Project Structure | ✅ | |
| 9 | Testing Rules | ✅ | |
| 10 | Secrets and Security | ✅ | |
| 11 | Development Stages | ✅ | |
| 12 | Code Quality | ✅ | |
| 13 | Logging | ✅ | |

**Constitution Check result**: [all gates pass / N violations — see Complexity Tracking]

## Project Structure

### Documentation (this feature)

```text
specs/NNN-feature-slug/
├── plan.md
├── spec.md
├── research.md        (Phase 0 output)
├── data-model.md      (Phase 1 output, if needed)
├── quickstart.md      (Phase 1 output)
├── contracts/
│   └── [contract files, if needed]
└── tasks.md           (Phase 2 output)
```

### Source Code Changes

```text
[List files with ADD / EXTEND / MODIFY annotations and one-line description]
```

**Structure Decision**: [Why this layout? Option chosen and alternatives rejected.]

## Complexity Tracking

*Omit this section entirely if there are no constitution violations.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| §N [principle] — [what changes] | [Reason] | [Why simpler option fails] |
