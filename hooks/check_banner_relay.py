#!/usr/bin/env python3
"""
Stop hook: did the agent run autopsy and then forget to paste the banner?

This is the durable version of a rule that prose kept failing to enforce. The banner
prints to stderr; the agent is supposed to copy the art into its reply; four prose
fixes (issue #3, PR #2, PR #4) each hardened that instruction and none made it
impossible, because prose cannot enforce behavior. A hook can.

test > hook > lint rule > sidecar > comment. The relay markers are the sidecar. This
is the hook.

Scope, stated plainly so nobody mistakes it for more than it is:
- Claude Code CLI / desktop only. Stop hooks do not exist on web, mobile, Codex, or
  Cursor. This is defense-in-depth for the surface where autopsy actually runs.
- It fires ONLY when autopsy ran this turn and produced a banner. Every other Stop is
  a silent no-op.
- It nudges ONCE. On the forced continuation `stop_hook_active` is true and the hook
  releases — a session that wedges is a worse bug than a missing banner.

Two signals, two sources, deliberately:
- "autopsy produced a banner this turn" comes from the TRANSCRIPT (the tool result,
  written well before the stop).
- "the art is in the reply" comes from `last_assistant_message` in the STDIN payload,
  because the transcript is written asynchronously and the final message may not be on
  disk yet when Stop fires. Reading it from the transcript would false-block.

`evaluate` is pure: signals in, verdict out. The stdin/exit wrapper is the only part
that touches the harness.
"""

import json
import sys

# Emitted by run.py ONLY when it prints the banner with relay on.
RELAY_OPEN_SIGNAL = "AGENT: the block below is the cold open"
BANNER_BEGIN = "---------- BANNER BEGIN ----------"
BANNER_END = "---------- BANNER END ----------"

SYNTHETIC_PREFIXES = ("Base directory for this skill:",)
SYNTHETIC_CONTAINS = (
    "This session is being continued from a previous conversation",
    "<task-notification",
    "<system-reminder",
)


def _text_of(record):
    """Flatten a transcript record to plain text: message content blocks AND any
    `toolUseResult` payload (tool results show up in either shape across versions)."""
    out = []
    msg = record.get("message", {})
    content = msg.get("content", "") if isinstance(msg, dict) else ""
    if isinstance(content, str):
        out.append(content)
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                out.append(block.get("text", ""))
            elif block.get("type") == "tool_result":
                c = block.get("content", "")
                if isinstance(c, list):
                    out.extend(b.get("text", "") for b in c if isinstance(b, dict))
                elif isinstance(c, str):
                    out.append(c)
    tur = record.get("toolUseResult")
    if isinstance(tur, dict):
        c = tur.get("content", "")
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, list):
            out.extend(b.get("text", "") for b in c if isinstance(b, dict))
    elif isinstance(tur, str):
        out.append(tur)
    return "\n".join(t for t in out if t)


def _is_real_user_turn_start(record):
    """A genuine human message — the boundary of 'this turn'. Excludes tool results and
    harness-injected content wearing a user role."""
    if record.get("type") != "user":
        return False
    msg = record.get("message", {})
    content = msg.get("content", "") if isinstance(msg, dict) else ""
    if isinstance(content, list) and content and all(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
    ):
        return False
    if record.get("isCompactSummary"):
        return False
    text = _text_of(record)
    if not text.strip():
        return False
    if text.startswith(SYNTHETIC_PREFIXES):
        return False
    if any(m in text for m in SYNTHETIC_CONTAINS):
        return False
    return True


def _extract_art_lines(text):
    """The substantial lines between the BEGIN/END markers, deduped, order preserved.

    A single line is a brittle signature — it depends on which line is longest and on
    the agent pasting that exact one. We compare against the whole set and require a
    majority, which tolerates a dropped blank or box line and still refuses a reply
    that merely talks about the banner."""
    if BANNER_BEGIN not in text:
        return []
    after = text.split(BANNER_BEGIN, 1)[1]
    body = after.split(BANNER_END, 1)[0] if BANNER_END in after else after
    seen, out = set(), []
    for raw in body.splitlines():
        ln = raw.strip()
        # Skip blanks, relay markers, and lines too short to be a distinctive match.
        if len(ln) < 6 or ln.startswith(">>>"):
            continue
        if ln not in seen:
            seen.add(ln)
            out.append(ln)
    return out


def evaluate(records, last_assistant_message=None):
    """Pure verdict.

    records: parsed transcript objects, oldest->newest.
    last_assistant_message: the final reply string from the Stop payload (preferred
        source for 'is the art in the reply', since the transcript may lag).

    Returns {autopsy_ran, relayed, ok, signature}.
    """
    start = 0
    for i, rec in enumerate(records):
        if _is_real_user_turn_start(rec):
            start = i
    turn = records[start:]

    art_lines = []
    for rec in turn:
        text = _text_of(rec)
        if RELAY_OPEN_SIGNAL in text or BANNER_BEGIN in text:
            found = _extract_art_lines(text)
            if found:
                art_lines = found

    if not art_lines:
        return {"autopsy_ran": False, "relayed": False, "ok": True, "signature": None}

    # Union of the two reply sources, to avoid false-blocking: the payload's final
    # message (may not be in the transcript yet) plus any assistant text already
    # written this turn (covers a banner pasted in an earlier message of the same turn).
    reply_sources = []
    if last_assistant_message:
        reply_sources.append(last_assistant_message)
    reply_sources.extend(
        _text_of(rec) for rec in turn if rec.get("type") == "assistant"
    )
    reply = "\n".join(reply_sources)

    matched = sum(1 for ln in art_lines if ln in reply)
    # Majority of the art's lines must appear verbatim. A narrated reply matches zero;
    # a genuine paste matches all; a paste missing a line still clears the bar.
    relayed = matched >= max(1, (len(art_lines) + 1) // 2)
    return {
        "autopsy_ran": True,
        "relayed": relayed,
        "ok": relayed,
        "signature": art_lines[0],
    }


def _read_transcript(path):
    records = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return None
    return records


def main():
    # Every failure path allows the stop (exit 0). A hook that wedges the session is a
    # worse bug than the banner it guards.
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # Loop guard: on the forced continuation we already nudged once. Release.
    if payload.get("stop_hook_active"):
        sys.exit(0)

    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        sys.exit(0)

    records = _read_transcript(transcript_path)
    if not records:
        sys.exit(0)

    verdict = evaluate(records, payload.get("last_assistant_message"))
    if verdict["ok"]:
        sys.exit(0)

    # Autopsy ran; the art is not in the reply. Block the stop and say exactly what to
    # do. Exit 0 + decision:block is the documented, deterministic mechanism.
    reason = (
        "autopsy ran but the cold-open banner is not in your reply. A banner in a tool "
        "result is not the user seeing it. Paste the ASCII art (the block between the "
        ">>> BANNER BEGIN / BANNER END markers) into your reply as the first thing, "
        "verbatim. A sentence describing it does not count -- the literal art must be "
        "there."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


if __name__ == "__main__":
    main()
