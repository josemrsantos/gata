# Implementation Plan: Uniform Source Titles

**Branch**: `043-gemini-source-titles` | **Date**: 2026-08-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/043-gemini-source-titles/spec.md`

## Summary

Unify all three panelist providers' Sources-list titles to `domain - page
title`. Gemini and Grok share a fetch-based resolver (`httpx` GET, following
redirects, parse `<title>`) since neither provides a usable title on its own;
Claude needs only a domain prefix added to the good title Anthropic's citation
API already returns. Any failure anywhere falls back to the bare domain alone —
never blocks a source from publishing.

**Revision note**: originally scoped to Gemini only. Extended per explicit
request to also cover Claude (domain prefix, no fetch) and Grok (same
fetch-based resolver as Gemini, since Grok's citation `title` field was already
confirmed unusable — it's the footnote index number, not a title).

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `httpx` (already in `pyproject.toml`); `urllib.parse`
(stdlib) for domain extraction; no new package
**Storage**: N/A
**Testing**: pytest with `unittest.mock` (no real HTTP calls per Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: Small enhancement to one existing agent module
**Performance Goals**: Parallel fetch across all of one provider's sources
(typically 5–15), each bounded by a short per-URL timeout — low single-digit
seconds added to each provider's existing 120s research budget; Claude's path
adds no latency (no network call)
**Constraints**: ruff `line-length = 88`; RULE 14
**Scale/Scope**: 1 file modified (`agents/agent_linkedin_post.py`), 1 test file
extended

## Constitution Check

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ N/A | No LLM/model call involved. |
| 2–6 | (image/verdict/character rules) | ✅ N/A | Text-only, no panel/verdict involved in this fix. |
| 7 | Language Rule | ✅ N/A | Titles are copied verbatim from their source, not translated. |
| 8 | Project Structure | ✅ | Only `agents/` and `tests/` touched. |
| 9 | Testing Rules | ✅ | All `httpx` calls mocked; success/timeout/non-2xx/missing-title cases covered for both fetch-based providers, plus Claude's domain-prefix-only path; RULE-3 comments on every test. |
| 10 | Secrets and Security | ✅ N/A | Fetches a public URL the provider already decided to cite. |
| 11 | Development Stages | ✅ | Branch `043-gemini-source-titles` created off `main` before any file was written. |
| 12 | Code Quality | ✅ | `ruff check`/`format` clean; RULE 14 followed. |
| 13 | Logging | ✅ | Resolution failures logged at DEBUG (FR-008) — cosmetic, not a research failure. |

**Constitution Check result**: all gates pass (most rows N/A — small, non-LLM,
non-image enhancement to text-processing paths already established in Spec 042).

## Project Structure

### Source Code Changes

```text
agents/agent_linkedin_post.py   MODIFY —
                                 - _domain_from_url(url) -> str: shared helper,
                                   netloc via urllib.parse, www. stripped,
                                   falls back to the raw url if unparseable
                                   (FR-001)
                                 - _fetch_page_title(url) -> str | None:
                                   unchanged from the original Gemini-only
                                   version — already provider-agnostic (FR-002)
                                 - _enrich_source_titles_via_fetch(sources) ->
                                   list[ResearchSource]: renamed from
                                   _enrich_gemini_source_titles — same
                                   behaviour, now reused by both Gemini and
                                   Grok (FR-003, FR-004, FR-005)
                                 - _extract_grok_sources: title is now
                                   _domain_from_url(url) instead of the raw url
                                   (FR-005's pre-fetch baseline)
                                 - _extract_claude_sources: title becomes
                                   "{domain} - {citation title}" when Claude
                                   supplies one, else just the domain (FR-006)
                                 - _research_gemini / _research_grok: both call
                                   _enrich_source_titles_via_fetch on their
                                   extracted sources before returning

tests/test_agent_linkedin_post.py   MODIFY — rename/extend the Gemini-only
                                     enrichment tests to cover the shared
                                     resolver; add Grok fetch-path coverage
                                     (success, failure); add Claude
                                     domain-prefix coverage (with title,
                                     without title); add _domain_from_url unit
                                     coverage (www. stripping, unparseable
                                     fallback).
```

**Structure Decision**: One shared fetch resolver for Gemini and Grok (both need
a live fetch since neither provider gives a usable title on its own) rather than
two near-identical copies. Claude gets its own, much simpler path — no network
call, since Anthropic already gives a good title; forcing it through the same
fetch resolver would add latency and failure surface for no benefit.
