# TODO

## Multi-audience CLI — `gata <topic>` command

Allow anyone who installs `gata` from PyPI to generate a complete multi-audience cartoon set
from a single topic string with no knowledge of the pipeline internals — the MVP distribution
story for the project.

---

## Voting system — funny / not funny

Allow people to rate each cartoon. Votes feed back into the pipeline to improve future
output (e.g. weight satirical angles that score well, retire angles that consistently
score low).

Things to figure out:
- Where cartoons are served (needed before voting UI can be designed)
- Vote storage — per cartoon, per community, over time
- Whether votes influence prompt generation or community config directly
- Abuse / ballot stuffing prevention


## Post-generation image review

After `agent_image_generator.generate()` saves the image, pass it to a vision model to check for
rendering artifacts before accepting the output. Known failure modes to detect:

- Duplicate text labels (e.g. "Interest Rates — Now Yours" appearing twice on the board)
- Illegible or garbled chalkboard text
- Gata character integrity failures (wrong colours, accessories added, not present)
- Missing elements from the prompt that are load-bearing for the joke

If the review fails, trigger a regeneration (up to N retries) before writing the bundle.

---

## Self-documenting CLI

**Goal:** Calling the pipeline script with no arguments (or with `--help`) should display all available calling modes with concrete, ready-to-edit examples.

**Reason:** Make it immediately clear what options exist and give the developer an example they can copy and tweak — no need to read the source or the README to know how to run a specific image.

**Success criteria:** Running `python pipeline.py` alone prints usage with at least one fully worked example per mode (manual, community, random).

---

## Gemini-only Satirist/Critic loop — co-satirist mode

**Goal:** Replace Claude with Gemini in the Satirist role and redesign both agents as
collaborators chasing the same goal (funniest possible concept) rather than creator vs.
evaluator.

**Reason:** Empirical observation that Gemini delivers stronger, more culturally-aware
jokes than Claude; having both agents iterate towards the sharpest angle (rather than one
creating and one gatekeeping) produces better output.

---

## Grok integration — add xAI Grok as a third LLM provider

**Goal:** Add xAI's Grok as a third LLM option alongside Gemini and Claude.

**Reason:** Grok's irreverent, culture-aware personality may strengthen satirical output;
a third provider also adds redundancy and lets the pipeline mix voices across agents
(e.g. Grok as Co-Satirist).

---

## Image Evaluator — concept fidelity check

**Goal:** Extend the Image Evaluator to explicitly verify that the rendered image shows the
*specific* intended concept, not just something thematically plausible. The evaluator must
compare named elements from the approved concept (labels, diagrams, objects, scenes) against
what is actually visible, and reject the image if the model substituted a different visual.

**Reason:** Demonstrated by a chicken-crossing-the-road run: `gemini-3.1-flash-image-preview`
ignored the approved spider-diagram prompt and rendered a British weather cycle instead. The
image was visually convincing and passed the existing checks, but depicted a completely
different concept. Thematic similarity is not concept fidelity.

---

## Post-generation image evaluator — vision model checks for LLM artifacts and rates funniness

**Goal:** After the image is saved, pass it to a vision model that checks for LLM rendering
artifacts *and* rates whether the image is actually funny to a human viewer before the bundle
is accepted.

**Reason:** The pipeline currently has no feedback loop on whether the final image lands as
funny; an evaluator that flags artifact failures and low-humour scores in one pass catches
two failure modes together, and sets up the voting system with a baseline quality floor.

---

## Gemini fact-check gate with FACT tag

**Goal:** After Claude produces a concept proposal, Gemini must perform a thorough fact-check of every specific claim (dates, names, events, economic figures). If any claim is factually wrong, Gemini must return it to Claude with an explicit `FACT:` tag that Claude cannot skip or override.

**Reason:** The B/C loop currently checks tone and quality but not factual accuracy. This allowed a clearly impossible detail (Mário Soares "reforma em 2026", when he died in January 2017) to pass through unchallenged and appear in the generated image.

**Success criteria:** A concept containing a verifiable factual error is caught by Gemini, returned to Claude with a `FACT:` tag, and Claude must correct the error before the image prompt is finalised. A concept with no factual errors passes through without triggering the tag.
