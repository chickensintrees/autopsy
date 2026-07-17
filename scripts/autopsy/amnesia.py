"""
Tool Amnesia — capability regression, with evidence instead of inference.

Every compaction records `preCompactDiscoveredTools`: the tools the agent had
discovered at the instant its context was summarized away. That is ground truth.
It means we do not have to guess whether a capability was forgotten. We know what
was known, and we can watch what happened after.

A finding here is:

    tool T was known at boundary B
    after B, the agent never used T again
    after B, the agent told the user to do something T does

That is a forgotten capability with a receipt. Compare `regressions.py`, which
infers amnesia from phrasing alone and needs filters to survive its own false
positives.

This module reports EVIDENCE, not verdicts. It does not decide that a deferral was
illegitimate — "you'll need to log into the bank" is a real limit even when WebFetch
exists. It surfaces the collision and attaches line numbers. The skill decides.
"""

import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.jsonl_parser import find_sessions, find_sessions_by_date, parse_session


# What a deferral looks like for a given capability. Keyed by tool name.
# Deliberately narrow: each pattern must describe work the tool actually does.
TOOL_DEFERRAL_PATTERNS = {
    "WebSearch": [
        r"\bi (?:can'?t|cannot|don'?t have (?:the )?abilit\w+ to) (?:search|browse|google)\b",
        r"\bi don'?t have (?:web|internet|browsing) access\b",
        r"\byou'?ll need to (?:search|google|look (?:it|that) up)\b",
        r"\byou (?:should|could|can) (?:search|google) (?:for )?(?:it|that|this)\b",
    ],
    "WebFetch": [
        r"\bi (?:can'?t|cannot) (?:fetch|open|read|access|visit) (?:that |the )?(?:url|link|page|site|website)\b",
        r"\byou'?ll need to (?:open|visit|check|read) (?:the |that )?(?:url|link|page|site)\b",
        r"\bi don'?t have access to (?:that )?(?:url|link|page|website)\b",
    ],
    "Read": [
        r"\byou'?ll need to (?:open|check|read|look at) (?:the )?file\b",
        r"\bi (?:can'?t|cannot) (?:read|open|see) (?:the |that )?file\b",
    ],
    "Bash": [
        r"\byou'?ll need to run (?:the |this |that )?command\b",
        r"\byou (?:should|can) run (?:it|this|that) (?:yourself|manually|in your terminal)\b",
        r"\bi (?:can'?t|cannot) (?:run|execute) (?:commands|that command)\b",
    ],
    "Edit": [
        r"\byou'?ll need to (?:edit|change|update|modify) (?:the )?file (?:yourself|manually)\b",
        r"\bi (?:can'?t|cannot) (?:edit|modify) (?:the |that )?file\b",
    ],
    "Write": [
        r"\byou'?ll need to (?:create|write) (?:the |that )?file (?:yourself|manually)\b",
    ],
    "TaskCreate": [
        r"\byou'?ll need to track (?:this|that|it) (?:yourself|manually)\b",
    ],
    "Grep": [
        r"\byou'?ll need to (?:search|grep) (?:the|through) (?:the )?(?:code|codebase|files)\b",
    ],
    "Glob": [
        r"\byou'?ll need to find (?:the )?files? (?:yourself|manually)\b",
    ],
}

# Meta-discussion: the agent talking ABOUT deferral patterns is not deferring.
# This module can otherwise flag its own documentation, and has.
META_MARKERS = [
    r"\bpattern\b",
    r"\bregex\b",
    r"\bdetector\b",
    r"\bfalse positive\b",
    r"\bautopsy\b",
    r"^\s*[-*]\s",  # bullet lists (documentation, not speech)
    r"^\s*r?[\"']",  # quoted pattern strings
]


def _is_meta(text: str) -> bool:
    """Is this the agent analysing deferral rather than deferring?"""
    lowered = text.lower()
    hits = sum(1 for m in META_MARKERS if re.search(m, lowered, re.MULTILINE))
    return hits >= 2


def find_tool_amnesia(session):
    """For each compaction, check whether tools known at the boundary went dark.

    Returns a list of per-boundary findings, each carrying its own evidence.
    """
    findings = []

    for bi, boundary in enumerate(session.boundaries):
        if boundary.kind != "compaction" or not boundary.known_tools:
            continue

        after = [m for m in session.messages if m.line_number > boundary.line_number]
        if not after:
            continue

        used_after = set()
        for m in after:
            for tu in m.tool_uses:
                used_after.add(tu["name"])

        for tool in boundary.known_tools:
            if tool in used_after:
                continue  # still knows it. no finding.

            patterns = TOOL_DEFERRAL_PATTERNS.get(tool)
            if not patterns:
                continue  # no way to describe deferring this tool. stay quiet.

            deferrals = []
            for m in after:
                if m.type != "assistant" or not m.content_text:
                    continue
                if _is_meta(m.content_text):
                    continue
                for pat in patterns:
                    hit = re.search(pat, m.content_text.lower())
                    if hit:
                        start = max(0, hit.start() - 80)
                        deferrals.append({
                            "line": m.line_number,
                            "quote": m.content_text[start:hit.end() + 80].strip(),
                        })
                        break

            if deferrals:
                findings.append({
                    "session_id": session.session_id[:8],
                    "tool": tool,
                    "boundary_index": bi,
                    "boundary_line": boundary.line_number,
                    "trigger": boundary.trigger,
                    "retention_pct": boundary.retention_pct,
                    "known_tools": boundary.known_tools,
                    "used_after": False,
                    "deferrals": deferrals,
                })

    return findings


def run_amnesia_scan(base_path=None, days=None):
    """Scan sessions for capability regression backed by compaction metadata."""
    files = find_sessions_by_date(base_path, days) if days is not None else find_sessions(base_path)

    findings = []
    boundaries_examined = 0
    boundaries_with_tools = 0

    for f in files:
        session = parse_session(f)
        for b in session.boundaries:
            if b.kind == "compaction":
                boundaries_examined += 1
                if b.known_tools:
                    boundaries_with_tools += 1
        findings.extend(find_tool_amnesia(session))

    return {
        "total_findings": len(findings),
        "boundaries_examined": boundaries_examined,
        "boundaries_with_tool_data": boundaries_with_tools,
        "findings": findings,
    }


def format_amnesia(results):
    """Format tool amnesia findings."""
    lines = []
    lines.append("# Tool Amnesia")
    lines.append("")
    lines.append("*Capability regression with a receipt. Every compaction records which")
    lines.append("tools the agent had discovered. This checks what happened to them.*")
    lines.append("")
    lines.append(f"Compactions examined: {results['boundaries_examined']}")
    lines.append(f"Compactions carrying tool data: {results['boundaries_with_tool_data']}")
    lines.append(f"Findings: {results['total_findings']}")
    lines.append("")

    if not results["findings"]:
        lines.append("No tool amnesia detected. Every tool known at a boundary was either")
        lines.append("used again afterward, or never deferred on.")
        return "\n".join(lines)

    for f in results["findings"]:
        lines.append(f"## `{f['tool']}` — session `{f['session_id']}`, boundary at L{f['boundary_line']}")
        lines.append("")
        lines.append(f"- Known at boundary: **yes** (`preCompactDiscoveredTools`)")
        lines.append(f"- Used after boundary: **no**")
        lines.append(f"- Context retained: {f['retention_pct']}% ({f['trigger']} compaction)")
        lines.append(f"- Deferrals after the boundary: {len(f['deferrals'])}")
        lines.append("")
        for d in f["deferrals"][:3]:
            lines.append(f"  - L{d['line']}: \"...{d['quote']}...\"")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tool Amnesia — capability regression with evidence")
    parser.add_argument("--path", help="Base path to search for sessions")
    parser.add_argument("--days", type=int, help="Only include sessions from last N days")
    args = parser.parse_args()

    print(format_amnesia(run_amnesia_scan(args.path, args.days)))
