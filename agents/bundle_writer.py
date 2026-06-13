import logging
from pathlib import Path

from agents import agent_explainer
from agents.types import ConversationLog, EnrichedBrief

logger = logging.getLogger(__name__)

_VERDICT_LABELS = {
    "APPROVED": "Verdict: APPROVED",
    "NEEDS REVISION": "Verdict: NEEDS REVISION",
    "FINAL_SAY": "FINAL SAY (approved)",
    "": "",
}


def format_log(log: ConversationLog) -> str:
    """Format a ConversationLog as human-readable plain text."""
    sections: list[str] = []
    # Group turns by iteration
    iterations: dict[int, list] = {}
    for turn in log.turns:
        iterations.setdefault(turn.iteration, []).append(turn)

    for idx, (iteration, turns) in enumerate(sorted(iterations.items())):
        header = f"=== Iteration {iteration} ==="
        parts = [header]
        for turn in turns:
            role_line = f"[{turn.role}]"
            parts.append(role_line)
            parts.append(turn.text)
            if turn.verdict:
                label = _VERDICT_LABELS.get(turn.verdict, f"Verdict: {turn.verdict}")
                parts.append(label)
            parts.append("")
        sections.append("\n".join(parts))

    return "\n---\n".join(sections)


def write_bundle(
    output_path: str,
    agent0_log: ConversationLog | None,
    bc_log: ConversationLog | None,
    enriched_brief: EnrichedBrief | None,
    image_prompt: str | None,
) -> str:
    """Create the bundle folder and write all output files. Never raises."""
    bundle_dir = Path(output_path).parent / Path(output_path).stem
    bundle_dir.mkdir(parents=True, exist_ok=True)
    logger.info("bundle_writer: writing bundle to %s", bundle_dir)

    # Write conversation logs
    if agent0_log is not None:
        _write_text(bundle_dir / "agent0_log.txt", format_log(agent0_log))

    if bc_log is not None:
        _write_text(bundle_dir / "bc_log.txt", format_log(bc_log))

    # Write prompt card
    if image_prompt is not None:
        _write_text(bundle_dir / "prompt_card.txt", image_prompt)

    # Generate and write HTML files when we have enough context
    if enriched_brief is not None and image_prompt is not None:
        try:
            in_lang_html, english_html = agent_explainer.generate_html(
                enriched_brief,
                agent0_log,
                bc_log,
                image_prompt,
            )
            _write_text(bundle_dir / "explanation.html", in_lang_html)
            _write_text(bundle_dir / "deep_dive_en.html", english_html)
        except Exception as exc:
            logger.error(
                "bundle_writer: agent_explainer failed — HTML files not written: %s",
                exc,
            )

    return str(bundle_dir)


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        logger.error("bundle_writer: could not write %s — %s", path, exc)
