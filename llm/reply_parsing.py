from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_EXCERPT_CHARS = 400

_FENCE_RE = re.compile(r"```[A-Za-z0-9_+-]*[ \t]*\r?\n?(.*?)\s*```", re.DOTALL)

_PICK_LINE_RE = re.compile(
    r"^[ \t]*(?:[-*•][ \t]+)?\**[ \t]*PICK[ \t]*:[ \t]*\**[ \t]*(\d+)\**[ \t.]*$",
    re.IGNORECASE | re.MULTILINE,
)
_PICK_ANYWHERE_RE = re.compile(r"PICK:\s*\**(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class ParseContext:
    """Who produced a reply, so a parse problem is traceable (Spec 058)."""

    agent: str
    role: str
    round: int
    model: str
    stop_reason: str | None = None
    output_tokens: int | None = None
    max_tokens: int | None = None


def log_parse_issue(
    ctx: ParseContext | None, field: str, applied: str, reply: str
) -> None:
    """Emit the single WARNING used for every parse failure or fallback (FR-007)."""
    if ctx is None:
        who = "unknown agent"
        detail = ""
    else:
        who = f"{ctx.agent}/{ctx.role} round {ctx.round}"
        parts = [ctx.model]
        if ctx.stop_reason:
            parts.append(f"stop_reason={ctx.stop_reason}")
        if ctx.output_tokens is not None and ctx.max_tokens is not None:
            parts.append(f"output_tokens={ctx.output_tokens}/{ctx.max_tokens}")
        detail = f" [{', '.join(parts)}]"
    logger.warning(
        "%s%s: %s — applied %s; reply starts: %r",
        who,
        detail,
        field,
        applied,
        reply[:_EXCERPT_CHARS],
    )


def _strip_fence(text: str) -> str:
    # Removes one surrounding code fence; the fence is formatting, not content.
    stripped = text.strip()
    fenced = _FENCE_RE.fullmatch(stripped)
    return fenced.group(1).strip() if fenced else stripped


def unwrap_reply(text: str, ctx: ParseContext | None = None) -> str:
    """Return the answer inside a panel reply, whatever shape the model used.

    Tag-free is the normal case: the whole reply is the answer. Legacy shapes
    (Specs 052/057) are still accepted: a closed or unclosed <verdict> tag, or a
    wholly-JSON reply. Only an empty reply is unusable.
    """
    closed = re.findall(r"<verdict>(.*?)</verdict>", text, re.DOTALL)
    if closed:
        content = closed[-1].strip()
        if not content:
            raise ValueError("empty <verdict> block")
        return content
    unclosed = re.search(r"<verdict>(.*)$", text, re.DOTALL)
    if unclosed and unclosed.group(1).strip():
        # Opening tag with no closing tag: a truncation or a forgotten tag.
        log_parse_issue(
            ctx, "missing closing </verdict> tag", "the truncated content", text
        )
        return unclosed.group(1).strip()
    bare = _strip_fence(text)
    if not bare:
        raise ValueError("empty reply")
    if bare.startswith(("{", "[")):
        try:
            json.loads(bare)
        except ValueError:
            return bare
        log_parse_issue(
            ctx, "reply was JSON without tags", "the JSON as the answer", text
        )
    return bare


def split_pick(text: str) -> tuple[int | None, str]:
    """Split an aggregator reply into its PICK number and the chosen answer."""
    match = _PICK_LINE_RE.search(text)
    if match:
        rest = text[: match.start()] + text[match.end() :]
        return int(match.group(1)), rest.strip()
    loose = _PICK_ANYWHERE_RE.search(text)
    if loose:
        return int(loose.group(1)), text.strip()
    return None, text.strip()


def parse_labelled(text: str, labels: list[str]) -> list[tuple[str, str]]:
    """Parse `LABEL: value` text into ordered (LABEL, value) pairs.

    A value runs until the next label line. Tolerates case, `**LABEL**:`, `## Label`,
    bullets, a trailing number (`Scene 1:`) and one surrounding code fence. Text
    before the first label is ignored. A label with no colon counts only when it is
    alone on its line (`PANEL 1`), so prose that merely starts with a label word is
    treated as value text.
    """
    alternation = "|".join(re.escape(label) for label in labels)
    line_re = re.compile(
        rf"^[ \t]*(?:#{{1,6}}[ \t]*|[-*•][ \t]+)?\**[ \t]*(?P<label>{alternation})"
        r"(?:[ \t]*\d+)?[ \t]*\**[ \t]*"
        r"(?:(?::[ \t]*\**[ \t]*(?P<rest>.*))|(?P<bare>))$",
        re.IGNORECASE,
    )
    pairs: list[tuple[str, list[str]]] = []
    for line in _strip_fence(text).splitlines():
        match = line_re.match(line)
        if match:
            rest = (match.group("rest") or "").strip().strip("*").strip()
            pairs.append((match.group("label").upper(), [rest] if rest else []))
        elif pairs:
            pairs[-1][1].append(line.rstrip())
    return [(label, "\n".join(lines).strip()) for label, lines in pairs]
