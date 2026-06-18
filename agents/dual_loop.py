import logging
import re
import time

import anthropic
from google import genai
from google.genai import types as genai_types

from agents.types import (
    AgentTelemetry,
    ConversationLog,
    ConversationTurn,
    LoopOutput,
    PersonaConfig,
    TokenUsage,
    compute_cost,
)

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
) -> tuple[str, TokenUsage]:
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
        text = response.content[0].text
        # usage is always present on Anthropic responses
        in_tok = getattr(response.usage, "input_tokens", 0) or 0
        out_tok = getattr(response.usage, "output_tokens", 0) or 0
        return text, TokenUsage(
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=compute_cost(model, in_tok, out_tok),
        )
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
    # usage_metadata may be absent on some Gemini models — guard defensively
    meta = getattr(response, "usage_metadata", None)
    in_tok = getattr(meta, "prompt_token_count", 0) or 0
    out_tok = getattr(meta, "candidates_token_count", 0) or 0
    return response.text, TokenUsage(
        model=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=compute_cost(model, in_tok, out_tok),
    )


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
    ) -> tuple[str, TokenUsage]:
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
        token_calls: list[TokenUsage] = []
        iterations_run = 0
        logger.info("%s: starting", self._loop_name)
        # each iteration runs proposer then reviewer; APPROVED exits early
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
            proposer_response, proposer_usage = self._call_persona(
                self._proposer, proposer_messages, system_prompt=proposer_system
            )
            token_calls.append(proposer_usage)
            last_proposer_verdict = _extract_proposer_verdict(proposer_response)
            log.turns.append(
                ConversationTurn(
                    iteration=iteration,
                    role=self._proposer.name,
                    text=proposer_response,
                    verdict="",
                )
            )
            reviewer_response, reviewer_usage = self._call_persona(
                self._reviewer,
                [{"role": "user", "content": proposer_response}],
            )
            token_calls.append(reviewer_usage)
            verdict = _parse_reviewer_verdict(reviewer_response)
            iterations_run = iteration
            logger.debug(
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
                telemetry = AgentTelemetry(
                    agent_name=self._loop_name,
                    duration_seconds=time.monotonic() - start,
                    iterations=iterations_run,
                    calls=token_calls,
                )
                logger.info(
                    "%s: complete — approved after %d iteration(s)",
                    self._loop_name,
                    iterations_run,
                )
                return LoopOutput(
                    verdict=last_proposer_verdict, log=log, telemetry=telemetry
                )
            # Reviewer turn verdict label differs on the final iteration
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

        logger.info("%s: complete — max iterations reached", self._loop_name)
        telemetry = AgentTelemetry(
            agent_name=self._loop_name,
            duration_seconds=time.monotonic() - start,
            iterations=iterations_run,
            calls=token_calls,
        )
        return LoopOutput(verdict=last_proposer_verdict, log=log, telemetry=telemetry)
