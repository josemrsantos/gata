# TODO

## Single-audience default for `gata` — *new Spec (number TBD)*

**Goal:** Running `gata` generates for one audience by default — `uk-tech-engineers`
only — instead of today's topic-inferred audiences plus the always-added UK
public audience. A repeatable `--audience` flag overrides the default and
accepts more than one audience.

**Reason:** Each extra audience is a full paid pipeline run (Strategist,
Satirist, image, evaluator), so the current ~2-audience default doubles cost
and time. Most runs need one; multi-audience stays available on request.

**Confirmed:**
- Default is a fixed audience definition for `gata` (language/tone of
  `uk-tech-engineers`), replacing the "UK public" fallback in `_ensure_uk`.
- `--audience` is repeatable (multiple values).
- A new spec (Flow-Forward, per RULE 18), not an amendment — it changes a
  default and evolves Specs 008 (multi-audience CLI), 015 (single main
  audience) and possibly 010 (dynamic audiences).

**Things to figure out:**
- What `--audience` accepts: community names from `communities.yaml`,
  free-text audience descriptions, or both.
- Whether the default reads `uk-tech-engineers` from `communities.yaml` or
  hardcodes an equivalent in `gata`.
- Whether `--audience` replaces the default or adds to it, and how to get
  the old behaviour (topic-inferred audiences) back, if at all.
- Interaction with `--research-only`, which today uses the first inferred
  audience — should it use the new default?

---

## Image-prompt-only mode — *new Spec (number TBD)*

**Goal:** A new `--image-prompt-only` flag, on both `pipeline.py` and `gata`,
runs the whole text pipeline but skips only the actual image creation (the
Gemini image call). Instead it writes the full image-generation request to a
file and prints a message that no image was auto-generated, that it must be
generated manually using that file as input in Gemini, and the file's location.

**Reason:** Image generation is the slowest, most expensive and sometimes
failing step. Prompt-only mode lets you pay only for the text stages, see
exactly what Gemini would receive, and paste it into Gemini yourself. It also
lets you use a monthly plan you are already paying for (the Gemini app)
instead of spending more money on direct API calls for image generation.

**Confirmed:**
- Skips ONLY the image creation; every other stage still runs (and so the text
  bundle is still produced).
- On `gata` with multiple audiences: one prompt file per audience, each
  location printed.
- A new spec (Flow-Forward, per RULE 18), not an amendment to Spec 004.
- Finding: today's `prompt_card.txt` is not the full request. For multi-panel
  cartoons it holds `concept.full_text` while Gemini receives
  `_build_multi_panel_prompt(panels, layout)`; and the aspect-ratio config
  (only when `target_size` is pinned), the title banner overlay and the final
  crop are applied in Python, outside the prompt text.

**Things to figure out:**
- Whether the file should be the exact string `ImageGeneration.generate()`
  sends (from one shared builder used by both paths) plus a header with the
  manual-use settings (aspect ratio/target size, title, note that banner and
  crop are not applied) — and whether to fix `prompt_card.txt` to the same
  string in this spec.
- The file's name and location in the bundle (new file vs. reusing
  `prompt_card.txt`).
- What the Image Evaluator and its retry loop do when no image exists
  (presumably skipped entirely).
- How the flag interacts with `--linkedin-post`, whose cartoon is pinned to
  1200x644 (the header would need to state that size).

---

## FairParallelPanel executor hang risk — *new Spec (number TBD)*

**Goal:** Fix the same `ThreadPoolExecutor` context-manager hang pattern in
`llm/fair_parallel_panel.py`'s `_call_persona()` that was just fixed in
`agents/agent_linkedin_post.py` (Spec 042 amendment, 2026-09-15) — replace
`with ThreadPoolExecutor(...) as ex:` + `future.result(timeout=provider.timeout)`
with a non-context-manager executor and
`shutdown(wait=False, cancel_futures=True)`, plus (where feasible) an
SDK-level per-call timeout passed directly to `provider.generate()`.

**Reason:** `_call_persona()` only exercises the executor path when a
panelist provider has an explicit `timeout` set via `providers.yaml` (Spec
036) — that wasn't the case in the incident that surfaced the bug, so it
didn't contribute there, but the exact same "caller gives up via
future.result(timeout=...), then shutdown(wait=True) blocks on the same
stuck thread anyway" defect is present, and every FairParallelPanel caller
(Cultural Strategist, Satirist, Explainer, LinkedIn Angle
Planning/Writing/Domain Classification) is reachable through it whenever an
operator configures a per-provider timeout.

**Confirmed:** Isolated to `llm/fair_parallel_panel.py`'s `_call_persona()`
method — no other file shares this exact pattern outside the two already
fixed in Spec 042's 2026-09-15 amendment.

**Things to figure out:**
- Whether `LLMProvider.generate()`'s signature can accept a passthrough
  per-call timeout uniformly across Claude/Gemini/Grok without breaking
  every existing call site, or whether this needs to stay
  orchestration-only (executor fix alone, no SDK-level bound) since
  `generate()` doesn't currently expose that.
- Whether this is a Living Spec amendment to Spec 036 (per-provider
  timeout) or Spec 034 (FairParallelPanel itself), or a fresh spec number —
  same RULE 18 question as this session's fix, deferred until this item is
  picked up.

---

## FairParallelPanel aggregation improvements — *new Spec (number TBD)*

**Goal:** Three related improvements to FairParallelPanel's aggregation
step, all touching the same shared class:
1. **Blind review** — anonymize `CONCEPT {i} ({name}):` to `CONCEPT {i}:`
   in the aggregator-facing message, so the aggregator judges purely on
   content with no visibility into which model/panelist produced which
   concept.
2. **Configurable round count** — expose `iterations` as a CLI flag (e.g.
   --fair-rounds N) on both pipeline.py and gata, threaded down to every
   FairParallelPanel construction site, instead of each panel's hardcoded
   default (mostly 2).
3. **Aggregator source disclosure** — after aggregation, have code (not
   the LLM) determine which panelist's concept the aggregator actually
   picked (via the existing PICK: N parse), translate that back to the
   real provider/model name, and log it — e.g. "INFO: Satirist/Co-Satirist:
   aggregator selected concept from claude-sonnet-4-6".

**Reason:** All three came up together while auditing FairParallelPanel's
aggregation design: today the aggregator sees full panelist identities (a
possible bias blind-spot), round count is hardcoded per-panel with no
operator control, and there's no visibility into which provider's work
actually won out at the end of a run.

**Confirmed:** All three are changes to the shared
llm/fair_parallel_panel.py class (plus each call site for round-count flag
threading) — a single spec, not three per-panel patches.

**Things to figure out:**
- Exact CLI flag name/default for round count, and whether omitting it
  keeps each panel's own historical default.
- Whether the disclosure log line belongs at INFO only, or should also
  surface in quiet-mode terminal output (ties into Spec 050).
- Whether disclosure attributes credit only via the PICK: N line, since a
  synthesized answer may draw from multiple panelists.
- Panelist anonymization order — stable per-run vs. shuffled, so position
  doesn't become a de facto identity giveaway.

---

## Lightweight webserver front-end — *new Spec (number TBD)*

**Goal:** Stand up a lightweight webserver that can trigger the `gata` CLI (e.g. "generate a
report on X") over HTTP instead of only via terminal.

**Reason:** Enables using the tool without direct CLI access — a simple request-a-report
workflow.

**Things to figure out:**
- Sync vs. async job model — a report takes roughly 5–10 minutes.
- Auth/access control, since each request triggers real paid API calls.
- Framework choice (stdlib `http.server` vs. FastAPI/Flask).
- Whether this depends on Spec 046 (research-only mode) landing first.

---

## Move generation to AWS (cost-conscious) — *new Spec (number TBD)*

**Goal:** Investigate moving the generation workload to AWS, using free-tier or otherwise
minimal-cost resources where possible.

**Reason:** Currently runs locally only; AWS hosting would enable remote/scheduled use
cases, kept as cheap/free as this side project needs.

**Confirmed:** standalone from Spec 047 — not necessarily tied to hosting the webserver.

**Things to figure out:**
- Which free/cheap AWS services to evaluate (Lambda, Fargate Spot, EC2 free tier, etc.).
- Secrets management for API keys.
- Whether this is for scheduled/batch runs, webserver hosting (Spec 047), or both.

---

## Self-documenting CLI — *new Spec (number TBD)*

**Goal:** Calling the pipeline script with no arguments (or with `--help`) should display all available calling modes with concrete, ready-to-edit examples.

**Reason:** Make it immediately clear what options exist and give the developer an example they can copy and tweak — no need to read the source or the README to know how to run a specific image.

**Success criteria:** Running `python pipeline.py` alone prints usage with at least one fully worked example per mode (manual, community, random).

**Spec check:** No existing spec covers CLI help/usage output (checked every `specs/*/spec.md` for "help"/"usage"/"self-doc" — no hits; spec 008, the closest candidate, only covers audience selection, not help text). Confirmed live: `pipeline.py` with no arguments today prints no usage at all, just falls through to the API-key check. This is new capability, not a correction — new spec number.

---

## Automatic model selection — *new Spec (number TBD)*

**Goal:** Stop hand-picking and hand-updating the default model for every
role. Instead, choose models by a stated policy (e.g. cheapest, best value,
best performance, or a per-role mix) from what each provider currently offers,
so a model release or retirement no longer needs a person to edit chain lists
and price tables across the codebase.

**Reason:** Defaults are hardcoded model IDs duplicated across ~10 files
(`providers.yaml`, `core/runner.py`, `core/image_generation.py`,
`core/newsletter_merge.py`, the agents, and three price tables), so every
provider release forces a manual refresh spec (Spec 039, and Model currency
refresh II). The refresh recurs and goes stale between runs of it.

**Confirmed:** Idea only, agreed to be recorded now with its open questions
left to be decided later. Model currency refresh II stays a manual,
hardcoded refresh; this item is a separate, later approach.

**Things to decide later (open questions):**
- Selection policy: cheapest, best value, best performance, lowest latency, or
  a weighted/per-role mix — and how each role (panelist, aggregator,
  inference, image, newsletter) maps to a policy.
- Source of truth for what is available: each provider's models-list API,
  the documentation/pricing pages, or a maintained manifest in the repo.
- Where prices come from, since provider APIs mostly do not expose them —
  and what to do when price or availability cannot be fetched.
- When selection runs: live at the start of each run, or a separate
  refresh command that rewrites `providers.yaml`/the defaults for review.
- Whether a human approval gate is required before a newly discovered model
  becomes a default, and whether to cap the cost increase an automatic
  upgrade may cause.
- How "same tier" and "stable vs preview" are defined for providers without
  tier names (xAI) or with preview-only releases, so a policy can be applied.
- A last-known-good fallback list when discovery fails, so a provider outage
  does not break runs.
- How the chosen model is recorded (run log/telemetry) so runs stay
  reproducible and cost reports stay explainable.
- Constitution §1/§6 name specific models; a rule-based policy would need an
  amendment, and the relationship with operator overrides in `providers.yaml`
  must be defined.
