import logging
import re
import time

import anthropic
from google import genai
from google.genai import types as genai_types

from agents.types import ConversationLog, ConversationTurn, LoopOutput, PersonaConfig

logger = logging.getLogger(__name__)

_anthropic_client: anthropic.Anthropic | None = None
_gemini_client: genai.Client | None = None

_SELF_REVIEW_SUFFIX = """

---
SELF-REVIEW — before writing your output, complete {n} passes assuming each time \
that you missed something in the previous pass:
REVIEW 1: [Assume your first instinct was too obvious or too lenient — what \
sharper or stricter position exists?]
REVIEW 2: [Assume you skipped a criterion — re-examine every requirement explicitly.]
REVIEW 3: [Assume a material improvement still exists that you have not made — \
what is it?]
Write your final output only after completing all {n} review passes."""

# Injected into the proposer's system prompt at the final iteration only
_FINAL_SAY_SUFFIX = """

---
FINAL SAY PROTOCOL

You have reached the final iteration. You must now produce your definitive output.
Across all previous iterations you have received feedback from the reviewer.
Your final response must:
(a) Acknowledge the reviewer's most recent feedback explicitly
(b) State which elements you are adopting and which you are not, and why
(c) Produce a synthesis that reflects genuine consideration — not a restatement of your
    iteration-1 proposal

Wrap your output in <verdict>...</verdict> tags as usual.

Last reviewer feedback:
{last_feedback}
"""


def _call_model(
    model: str, system_prompt: str, messages: list[dict], max_tokens: int = 2048
) -> str:
    global _anthropic_client, _gemini_client
    if model.startswith("claude"):
        if _anthropic_client is None:
            _anthropic_client = anthropic.Anthropic()
        response = _anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
    if _gemini_client is None:
        _gemini_client = genai.Client()
    # Format conversation history as a single string (consistent with agent_satirist.py)
    prompt = "\n\n".join(
        f"{'Assistant' if m['role'] == 'assistant' else 'User'}: {m['content']}"
        for m in messages
    )
    response = _gemini_client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        ),
    )
    return response.text


def _extract_proposer_verdict(text: str) -> str:
    matches = re.findall(r"<verdict>(.*?)</verdict>", text, re.DOTALL)
    if not matches:
        raise ValueError(f"proposer response missing <verdict> tag: {text[:200]!r}")
    return matches[-1]


def _parse_reviewer_verdict(text: str) -> str:
    match = re.search(r"<verdict>(.*?)</verdict>", text, re.DOTALL)
    if not match:
        return "NEEDS REVISION"
    if match.group(1).strip().upper().startswith("APPROVED"):
        return "APPROVED"
    return "NEEDS REVISION"


class DualPersonaLoop:
    def __init__(
        self,
        proposer: PersonaConfig,
        reviewer: PersonaConfig,
        max_iterations: int = 5,
        timeout_seconds: int = 900,
        loop_name: str = "",
        self_review_passes: int = 0,
    ):
        self._proposer = proposer
        self._reviewer = reviewer
        self._max_iterations = max_iterations
        self._timeout_seconds = timeout_seconds
        self._loop_name = loop_name
        self._self_review_suffix = (
            _SELF_REVIEW_SUFFIX.format(n=self_review_passes)
            if self_review_passes > 0
            else ""
        )

    def _call_persona(
        self,
        persona: PersonaConfig,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> str:
        base = system_prompt if system_prompt is not None else persona.system_prompt
        effective_system = base + self._self_review_suffix
        for model in persona.models:
            try:
                return _call_model(
                    model, effective_system, messages, max_tokens=persona.max_tokens
                )
            except Exception as exc:
                logger.warning(
                    "%s: model %s failed — %s — trying next model",
                    persona.name,
                    model,
                    exc,
                )
        raise RuntimeError(f"all models exhausted for {persona.name}")

    def run(self, initial_input: str) -> LoopOutput:
        start = time.monotonic()
        proposer_messages: list[dict] = [{"role": "user", "content": initial_input}]
        last_feedback = ""
        last_proposer_verdict = ""
        log = ConversationLog(loop_name=self._loop_name)

        for iteration in range(1, self._max_iterations + 1):
            if time.monotonic() - start > self._timeout_seconds:
                raise TimeoutError(
                    f"DualPersonaLoop: timeout after {self._timeout_seconds}s"
                )
            is_final = iteration == self._max_iterations and last_feedback
            if is_final:
                proposer_system = (
                    self._proposer.system_prompt
                    + _FINAL_SAY_SUFFIX.format(last_feedback=last_feedback)
                )
            else:
                proposer_system = self._proposer.system_prompt

            proposer_response = self._call_persona(
                self._proposer, proposer_messages, system_prompt=proposer_system
            )
            last_proposer_verdict = _extract_proposer_verdict(proposer_response)
            log.turns.append(
                ConversationTurn(
                    iteration=iteration,
                    role=self._proposer.name,
                    text=proposer_response,
                    verdict="",
                )
            )

            reviewer_response = self._call_persona(
                self._reviewer,
                [{"role": "user", "content": proposer_response}],
            )
            verdict = _parse_reviewer_verdict(reviewer_response)

            logger.info(
                "%s: iteration %d/%d verdict=%s",
                self._proposer.name,
                iteration,
                self._max_iterations,
                verdict,
            )

            if verdict == "APPROVED":
                log.turns.append(
                    ConversationTurn(
                        iteration=iteration,
                        role=self._reviewer.name,
                        text=reviewer_response,
                        verdict="APPROVED",
                    )
                )
                return LoopOutput(verdict=last_proposer_verdict, log=log)

            # Determine reviewer turn verdict label
            reviewer_verdict_label = "FINAL_SAY" if is_final else "NEEDS REVISION"
            log.turns.append(
                ConversationTurn(
                    iteration=iteration,
                    role=self._reviewer.name,
                    text=reviewer_response,
                    verdict=reviewer_verdict_label,
                )
            )

            last_feedback = reviewer_response
            proposer_messages.append(
                {"role": "assistant", "content": proposer_response}
            )
            proposer_messages.append({"role": "user", "content": reviewer_response})

        logger.info(
            "%s: final_say=True — returning iteration-%d output",
            self._proposer.name,
            self._max_iterations,
        )
        return LoopOutput(verdict=last_proposer_verdict, log=log)
