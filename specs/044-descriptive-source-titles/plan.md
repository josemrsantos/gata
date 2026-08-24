# Implementation Plan: Descriptive Source Titles

**Branch**: `044-descriptive-source-titles` | **Date**: 2026-08-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/044-descriptive-source-titles/spec.md`

## Summary

Replace the single-tier `<title>`-only fetch in `agents/agent_linkedin_post.py`
with a four-step resolution chain, shared uniformly across all three
panelist providers: (1) the source's own raw candidate title (Claude's real
citation title, or a bare-domain seed for Gemini/Grok), (2) a live fetch's
`<title>`, then `og:title`, then `twitter:title`, (3) a humanised URL-path
slug, and (4) a title the source's own provider supplies in the *same*
research call via an appended `===SOURCE_TITLES===` block — no second call.
A source for which none of the four steps is descriptive is dropped from
the published list. The key architectural decision is putting all four
steps behind one shared function, `_resolve_sources`, so every provider's
extraction function stops doing its own domain-prefixing and instead
returns a raw `(title, url)` candidate — the resolver alone decides what
gets published.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `httpx` (already in `pyproject.toml`); `urllib.parse`,
`re`, `html` (stdlib) — no new package
**Storage**: N/A
**Testing**: pytest with `unittest.mock` (no real HTTP or LLM calls per
Constitution §9)
**Target Platform**: Linux/macOS CLI
**Project Type**: Enhancement to one existing agent module
**Performance Goals**: No new network or LLM call added — `og:title`/
`twitter:title` are parsed from the same already-fetched HTML response;
the provider-supplied-title step is folded into each provider's existing
research call via a longer prompt/response, not a second call. The 120s
per-provider research budget and 5s per-URL fetch timeout are unchanged.
**Constraints**: ruff `line-length = 88`; RULE 14 (no bare blank-line phase
dividers inside function bodies)
**Scale/Scope**: 1 file modified (`agents/agent_linkedin_post.py`), 1 test
file extended (`tests/test_agent_linkedin_post.py`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Note |
|---|-----------|--------|------|
| 1 | SDK and Model Rules | ✅ N/A | No new SDK, model, or provider — reuses the three existing research calls unchanged. |
| 2–6 | (image/verdict/character rules) | ✅ N/A | Text-only source-title resolution; no image, verdict-JSON, or character-prompt path involved. |
| 7 | Language Rule | ✅ | Fetched/slug-derived titles are copied verbatim from their source (not translated); provider-supplied titles are written by that provider in the same language as its own research summary — no separate translation step introduced. |
| 8 | Project Structure | ✅ | Only `agents/` and `tests/` touched — no new directory or package. |
| 9 | Testing Rules | ✅ | All `httpx` calls and all provider client calls are mocked; every step of the resolution chain (raw-candidate accept, fetch success/failure incl. og/twitter, redirect-destination capture on failure, slug success/reject, provider-title accept/reject/unverified-URL-ignored, drop) has dedicated coverage; RULE-3 comments on every new test. |
| 10 | Secrets and Security | ✅ N/A | Fetches a public URL the provider already decided to cite; no new secret or credential involved. |
| 11 | Development Stages | ✅ | Branch `044-descriptive-source-titles` created off `main` before any file was written. |
| 12 | Code Quality | ✅ | `ruff check`/`format` clean on both modified files; RULE 14 followed (no bare blank-line phase dividers — comments mark each step of the resolution chain). |
| 13 | Logging | ✅ | Every dropped source and every fetch failure logged at `DEBUG` (cosmetic/soft-failure, not research failure), matching Spec 043's existing posture. |

**Constitution Check result**: all gates pass (rows 2–6 N/A — this is a
text-processing enhancement to an existing agent, no image/verdict/panel
scaffolding touched).

## Project Structure

### Documentation (this feature)

```text
specs/044-descriptive-source-titles/
├── plan.md          (this file)
├── spec.md
└── tasks.md
```

### Source Code Changes

```text
agents/agent_linkedin_post.py   MODIFY —
                                 - _RESEARCH_SYSTEM: appends the
                                   ===SOURCE_TITLES=== instruction, shared
                                   by all three providers (FR-007)
                                 - _extract_title_tag(html) -> str | None:
                                   the existing <title> regex, extracted
                                   into its own helper (FR-001)
                                 - _extract_meta_content(html, attr_name,
                                   attr_value) -> str | None: attribute-
                                   order-independent <meta> parser, used
                                   for both og:title and twitter:title
                                   (FR-001)
                                 - _fetch_page_title(url) -> tuple[str |
                                   None, str]: now returns (title,
                                   resolved_url); tries <title>, then
                                   og:title, then twitter:title; captures
                                   the redirect-resolved destination URL
                                   even when the destination request then
                                   fails (FR-001, FR-014)
                                 - _normalize_for_comparison(text) -> str:
                                   lowercase + alnum-only, shared by the
                                   non-descriptive check
                                 - _is_descriptive_title(title, domain) ->
                                   bool: rejects empty, the domain's first
                                   label, AND the full domain restated
                                   (Gemini/Grok's raw seed is the full
                                   domain, not just the label) — a
                                   deliberate widening of FR-002's literal
                                   wording, still within its "own domain
                                   label" intent (FR-002)
                                 - _humanize_slug(url) -> str | None: most
                                   specific path segment with >= 3 real
                                   words, numeric/hex-like segments and
                                   trailing numeric IDs skipped (FR-003,
                                   FR-004)
                                 - _is_unresolved_redirect_wrapper(original,
                                   slug_url) -> bool /
                                   _GROUNDING_REDIRECT_HOST: live-verification
                                   fix (found during the example run below) —
                                   when a fetch through Gemini's grounding
                                   redirect host fails before any redirect
                                   resolves, FR-014's own fallback correctly
                                   returns that host's opaque URL unchanged;
                                   without this check, step 3 would humanise
                                   that opaque base64-ish path and publish it
                                   as a "title". _resolve_sources now skips
                                   the slug step in exactly that situation,
                                   falling straight through to the
                                   provider-supplied title (FR-014 extension)
                                 - _split_source_titles_block(text) ->
                                   tuple[str, dict[str, str]]: splits a
                                   provider's raw response into
                                   (summary_without_block, url_to_title) —
                                   satisfies FR-010 by construction (FR-007,
                                   FR-008, FR-010)
                                 - _resolve_sources(candidates,
                                   provider_titles, do_fetch) ->
                                   list[ResearchSource]: the shared 4-step
                                   chain; drops any source resolving to
                                   nothing descriptive (FR-002..FR-011)
                                 - _extract_claude_sources: stops
                                   domain-prefixing — returns the raw
                                   citation title (or "") un-prefixed
                                 - _extract_gemini_sources /
                                   _extract_grok_sources: UNCHANGED (their
                                   existing raw-domain-seed behaviour is
                                   already exactly what the shared resolver
                                   needs as a starting candidate)
                                 - _research_gemini / _research_claude /
                                   _research_grok: each now splits its raw
                                   response via _split_source_titles_block,
                                   builds (raw_title, url, domain)
                                   candidates, and calls _resolve_sources
                                   (do_fetch=True for Gemini/Grok,
                                   do_fetch=False for Claude)
                                 - _enrich_source_titles_via_fetch: REMOVED
                                   — fully superseded by _resolve_sources

tests/test_agent_linkedin_post.py   MODIFY — updates the two
                                     _extract_claude_sources tests whose
                                     expected title changed shape; updates
                                     the Gemini/Grok success tests' mocks
                                     for the new _fetch_page_title tuple
                                     signature; removes the four
                                     _enrich_source_titles_via_fetch tests
                                     (function deleted); adds new coverage
                                     for _fetch_page_title's og/twitter
                                     fallback and FR-014 redirect-capture,
                                     _is_descriptive_title,
                                     _humanize_slug,
                                     _split_source_titles_block, and
                                     _resolve_sources (accept-at-each-step,
                                     unverified-URL-ignored, drop,
                                     one-failure-does-not-affect-others)
```

**Structure Decision**: One shared resolver (`_resolve_sources`) rather
than three near-identical per-provider implementations — all three
providers need the same four-step chain, differing only in whether they
fetch (`do_fetch`) and what raw candidate they start from. Extraction
functions were simplified to return raw, un-prefixed candidates rather
than each doing its own domain-prefixing, so the resolver is the single
place that decides a source's final published title (or that it's dropped)
— consistent with Spec 042 FR-011's existing principle that the Sources
list is always code-assembled, never trusted to free-form LLM text, now
extended to also never let any one extraction function silently decide a
title is "good enough" without going through the shared non-descriptive
check.

## Complexity Tracking

*No constitution violations — this section is omitted per the template's
own instruction.*
