from __future__ import annotations

import concurrent.futures
import logging
import re
import time

from core.types import (
    AgentTelemetry,
    ConversationLog,
    ConversationTurn,
    LoopOutput,
    PersonaConfig,
    TokenUsage,
)
from llm.base import ConversationProtocol
from llm.dual_loop import _extract_proposer_verdict

logger = logging.getLogger(__name__)


class FairParallelPanel(ConversationProtocol):
    """Multi-round parallel panel with peer-response sharing between rounds.

    Round 1: all panelists respond independently, in parallel threads.
    Rounds 2-N: each surviving panelist sees its peers' previous verdicts before
    responding; they run in parallel with a per-slot timeout that preserves Spec 032
    cross-provider fallback chains (primary provider + fallbacks share the budget).
    Final: aggregator LLM picks the best concept from all survivors' last responses.
    """

    def __init__(
        self,
        panelists: list[PersonaConfig],
        aggregator: PersonaConfig,
        panel_name: str = "",
        iterations: int = 2,
        panelist_timeout: float = 60.0,
    ) -> None:
        self._panelists = panelists
        self._aggregator = aggregator
        self._panel_name = panel_name
        self._iterations = iterations
        self._panelist_timeout = panelist_timeout

    def _call_persona(
        self,
        persona: PersonaConfig,
        messages: list[dict],
    ) -> tuple[str, TokenUsage]:
        for provider in persona.providers:
            try:
                if provider.timeout is None:
                    # No per-provider timeout — call directly, no executor overhead.
                    return provider.generate(
                        persona.system_prompt, messages, max_tokens=persona.max_tokens
                    )
                # Per-provider timeout set — wrap in a 1-worker executor so a stalled
                # call is abandoned and the next provider gets its own fresh budget.
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(
                        provider.generate,
                        persona.system_prompt,
                        messages,
                        max_tokens=persona.max_tokens,
                    )
                    return future.result(timeout=provider.timeout)
            except concurrent.futures.TimeoutError:
                logger.warning(
                    "%s: provider %s exceeded %ss — trying next provider",
                    persona.name,
                    provider.model_id,
                    provider.timeout,
                )
            except Exception as exc:
                logger.warning(
                    "%s: provider %s failed — %s — trying next provider",
                    persona.name,
                    provider.model_id,
                    exc,
                )
        raise RuntimeError(f"all providers exhausted for {persona.name}")

    def _build_peer_prompt(
        self,
        initial_input: str,
        my_previous_response: str,
        peers: list[tuple[str, str]],
    ) -> str:
        lines = [
            "Original request:",
            initial_input,
            "",
            "Your previous proposal:",
            my_previous_response,
            "",
            "Other panelists proposed:",
            "",
        ]
        for name, verdict_content in peers:
            lines.append(f"--- Panelist: {name} ---")
            lines.append(verdict_content)
            lines.append("")
        lines.append(
            "Given the perspectives above, please revise your proposal or confirm"
            " it stands."
        )
        lines.append("Wrap your final response in <verdict>…</verdict> tags as before.")
        return "\n".join(lines)

    def run(self, initial_input: str) -> LoopOutput:
        start = time.monotonic()
        log = ConversationLog(loop_name=self._panel_name)
        token_calls: list[TokenUsage] = []
        logger.info(
            "%s: starting fair parallel panel (%d panelists, %d iteration(s))",
            self._panel_name,
            len(self._panelists),
            self._iterations,
        )
        # active: panelists still in the exchange. final_results: name -> last
        # successful (verdict_content, raw_response, usage) for aggregation.
        active: list[PersonaConfig] = list(self._panelists)
        final_results: dict[str, tuple[str, str, TokenUsage]] = {}
        for round_num in range(1, self._iterations + 1):
            if not active:
                # All panelists dropped; stop iterating but still aggregate survivors.
                break
            logger.debug(
                "%s: round %d — %d panelist(s) active",
                self._panel_name,
                round_num,
                len(active),
            )
            # Round 1 uses the original prompt; later rounds use peer-aware prompts.
            if round_num == 1:
                messages_per = [
                    [{"role": "user", "content": initial_input}] for _ in active
                ]
            else:
                messages_per = []
                for panelist in active:
                    my_prev_raw = final_results[panelist.name][1]
                    peers = [
                        (other.name, final_results[other.name][0])
                        for other in active
                        if other.name != panelist.name
                    ]
                    if peers:
                        prompt = self._build_peer_prompt(
                            initial_input, my_prev_raw, peers
                        )
                    else:
                        # Single survivor — no peers; re-state the original request.
                        prompt = initial_input
                    messages_per.append([{"role": "user", "content": prompt}])
            # Submit all panelists concurrently; collect within the slot timeout.
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(active)
            ) as executor:
                futures = [
                    executor.submit(self._call_persona, panelist, messages)
                    for panelist, messages in zip(active, messages_per)
                ]
                new_active: list[PersonaConfig] = []
                for panelist, future in zip(active, futures):
                    try:
                        response, usage = future.result(timeout=self._panelist_timeout)
                        verdict_content = _extract_proposer_verdict(response)
                        token_calls.append(usage)
                        final_results[panelist.name] = (
                            verdict_content,
                            response,
                            usage,
                        )
                        log.turns.append(
                            ConversationTurn(
                                iteration=round_num,
                                role=panelist.name,
                                text=response,
                                verdict="",
                            )
                        )
                        new_active.append(panelist)
                        logger.debug(
                            "%s: panelist %s completed round %d",
                            self._panel_name,
                            panelist.name,
                            round_num,
                        )
                    except concurrent.futures.TimeoutError:
                        logger.warning(
                            "%s: panelist %s timed out in round %d"
                            " — dropping from subsequent rounds",
                            self._panel_name,
                            panelist.name,
                            round_num,
                        )
                    except Exception as exc:
                        logger.warning(
                            "%s: panelist %s failed in round %d — %s"
                            " — dropping from subsequent rounds",
                            self._panel_name,
                            panelist.name,
                            round_num,
                            exc,
                        )
            active = new_active
        if not final_results:
            raise RuntimeError(f"{self._panel_name}: all panelists failed")
        # Aggregate: build numbered concept list from each panelist's last response.
        lines = [f"Topic: {initial_input}", ""]
        for i, (name, (verdict_content, _, _)) in enumerate(final_results.items(), 1):
            lines.append(f"CONCEPT {i} ({name}):")
            lines.append(verdict_content)
            lines.append("")
        aggregation_message = "\n".join(lines).strip()
        aggregator_response, agg_usage = self._call_persona(
            self._aggregator,
            [{"role": "user", "content": aggregation_message}],
        )
        token_calls.append(agg_usage)
        final_verdict = _extract_proposer_verdict(aggregator_response)
        pick_match = re.search(r"PICK:\s*(\d+)", aggregator_response)
        pick_label = f"PICK: {pick_match.group(1)}" if pick_match else "PICK: ?"
        log.turns.append(
            ConversationTurn(
                iteration=self._iterations,
                role="Aggregator",
                text=aggregator_response,
                verdict=pick_label,
            )
        )
        # Wrap all round and aggregator call records into a single telemetry entry.
        telemetry = AgentTelemetry(
            agent_name=self._panel_name,
            duration_seconds=time.monotonic() - start,
            iterations=self._iterations,
            calls=token_calls,
        )
        logger.info(
            "%s: complete — aggregator selected from %d concept(s)",
            self._panel_name,
            len(final_results),
        )
        return LoopOutput(verdict=final_verdict, log=log, telemetry=telemetry)
