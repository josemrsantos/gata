# TODO

## Quieter default terminal output + persistent logging — *new Spec 050*

**Goal:** Reduce default terminal output so a run's important signal (final
output location, total cost/time, and any real failures) isn't buried under
per-agent/per-model cost breakdowns and routine log noise — while making
sure nothing hidden from the terminal is lost: add a FileHandler (WARNING+
by default) so every run's logging output is also persisted to disk. Move
the full per-agent/per-model token/cost breakdown out of the default
terminal view (it already duplicates summary.txt in the bundle) down to a
single TOTAL line; add a --verbose/-v flag that restores today's full
on-screen detail.

**Reason:** A real --research-only run's terminal output is dominated by
~20+ WARNING lines (SDK nags, panelist retries, excluded-source
classifications) and a full per-agent/per-model breakdown, making it hard to
see at a glance whether the run succeeded and where the output landed.
Separately, a retrospective audit of FairParallelPanel panelist drop-offs
(29/92 historical runs had a panelist silently fail to reach the final
round) hit a dead end: the actual failure reason (timeout vs. exception) is
never persisted anywhere — pipeline.py/core/cli.py only call
logging.basicConfig() with no FileHandler.

**Confirmed:** WARNING-level lines already go to stderr (verified via
logging.basicConfig's default stream) — `2>/dev/null` already hides them
today, but nothing captures them for later. The per-agent/per-model cost
breakdown is print()-based (stdout), the same stream as the final "Report
saved to..." line, so it can't currently be hidden independently.

**Things to figure out:**
- Exact default-quiet format: progress markers + TOTAL line + output path
  only, or leaner still?
- Whether --verbose restores today's exact output or a new intermediate
  level is warranted.
- Log file location/naming (per-run file inside the output bundle? a single
  rolling gata.log? both?) and whether DEBUG-level detail belongs there too.
- Whether any WARNING-level messages are worth surfacing on-screen by
  default vs. file-only for purely diagnostic ones.
- Whether this applies to both pipeline.py and gata, or just the
  interactive gata CLI.

---

## FairParallelPanel aggregation improvements — *new Spec 051*

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

## Lightweight webserver front-end — *new Spec 047*

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

## Move generation to AWS (cost-conscious) — *new Spec 048*

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

## Self-documenting CLI — *new Spec 049*

**Goal:** Calling the pipeline script with no arguments (or with `--help`) should display all available calling modes with concrete, ready-to-edit examples.

**Reason:** Make it immediately clear what options exist and give the developer an example they can copy and tweak — no need to read the source or the README to know how to run a specific image.

**Success criteria:** Running `python pipeline.py` alone prints usage with at least one fully worked example per mode (manual, community, random).

**Spec check:** No existing spec covers CLI help/usage output (checked every `specs/*/spec.md` for "help"/"usage"/"self-doc" — no hits; spec 008, the closest candidate, only covers audience selection, not help text). Confirmed live: `pipeline.py` with no arguments today prints no usage at all, just falls through to the API-key check. This is new capability, not a correction — new spec number.
