from __future__ import annotations

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


class ParallelPanel(ConversationProtocol):
    def __init__(
        self,
        panelists: list[PersonaConfig],
        aggregator: PersonaConfig,
        panel_name: str = "",
    ) -> None:
        self._panelists = panelists
        self._aggregator = aggregator
        self._panel_name = panel_name

    def _call_persona(
        self,
        persona: PersonaConfig,
        messages: list[dict],
    ) -> tuple[str, TokenUsage]:
        for provider in persona.providers:
            try:
                return provider.generate(
                    persona.system_prompt, messages, max_tokens=persona.max_tokens
                )
            except Exception as exc:
                logger.warning(
                    "%s: provider %s failed — %s — trying next provider",
                    persona.name,
                    provider.model_id,
                    exc,
                )
        raise RuntimeError(f"all providers exhausted for {persona.name}")

    def run(self, initial_input: str) -> LoopOutput:
        start = time.monotonic()
        log = ConversationLog(loop_name=self._panel_name)
        token_calls: list[TokenUsage] = []
        logger.info(
            "%s: starting parallel panel (%d panelists)",
            self._panel_name,
            len(self._panelists),
        )
        # call each panelist independently; skip those whose providers all fail
        panelist_outputs: list[tuple[str, str]] = []
        for panelist in self._panelists:
            try:
                response, usage = self._call_persona(
                    panelist, [{"role": "user", "content": initial_input}]
                )
                token_calls.append(usage)
                verdict_content = _extract_proposer_verdict(response)
                panelist_outputs.append((panelist.name, verdict_content))
                log.turns.append(
                    ConversationTurn(
                        iteration=1, role=panelist.name, text=response, verdict=""
                    )
                )
                logger.debug(
                    "%s: panelist %s responded", self._panel_name, panelist.name
                )
            except Exception as exc:
                logger.warning(
                    "%s: panelist %s failed — %s — skipping",
                    self._panel_name,
                    panelist.name,
                    exc,
                )
        if not panelist_outputs:
            raise RuntimeError(f"{self._panel_name}: all panelists failed")
        # build numbered aggregation message from successful panelist outputs
        lines = [f"Topic: {initial_input}", ""]
        for i, (name, verdict) in enumerate(panelist_outputs, 1):
            lines.append(f"CONCEPT {i} ({name}):")
            lines.append(verdict)
            lines.append("")
        aggregation_message = "\n".join(lines).strip()
        # call aggregator with the numbered concepts; extract verdict and PICK label
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
                iteration=1,
                role="Aggregator",
                text=aggregator_response,
                verdict=pick_label,
            )
        )
        # accumulate all token costs and duration into a single telemetry entry
        telemetry = AgentTelemetry(
            agent_name=self._panel_name,
            duration_seconds=time.monotonic() - start,
            iterations=1,
            calls=token_calls,
        )
        logger.info(
            "%s: complete — aggregator selected from %d concept(s)",
            self._panel_name,
            len(panelist_outputs),
        )
        return LoopOutput(verdict=final_verdict, log=log, telemetry=telemetry)
