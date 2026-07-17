"""
Rule Adherence Checker — Parse CLAUDE.md for rules, check if they
survived compaction.

Two modes:
1. Banned patterns: user-specified words/phrases that should never appear
   in tool_use output (generation prompts, file writes, etc.)
2. CLAUDE.md rules: extract rules and check for violations

The deep scan tracks what went INTO tool_use commands (Edit, Write, Bash),
not just response text. This is where the real violations hide.
"""

import re
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.jsonl_parser import find_sessions, find_sessions_by_date, parse_session


def extract_tool_text(tool_uses):
    """Extract all text content from tool_use inputs.

    This is the deep scan — checking what went INTO tool_use commands,
    not just what appeared in response text.
    """
    texts = []
    for tool in tool_uses:
        inp = tool.get("input", {})
        if isinstance(inp, dict):
            for key, val in inp.items():
                if isinstance(val, str):
                    texts.append(val)
                elif isinstance(val, dict):
                    texts.append(json.dumps(val))
        elif isinstance(inp, str):
            texts.append(inp)
    return "\n".join(texts)


# Negation words that suggest the banned word is being referenced as
# something to AVOID, not something being used.
# "No glowing nodes" or "avoid luminous" are anti-examples, not violations.
NEGATION_PATTERNS = [
    r"\bnot?\b", r"\bdon'?t\b", r"\bavoid\b", r"\bnever\b",
    r"\breject(?:ed|ing)?\b", r"\bwithout\b", r"\bban(?:ned)?\b",
    r"\bexclud(?:e|ed|ing)\b", r"\bremov(?:e|ed|ing)\b",
    r"\btoo\s+(?:cold|generic|much)\b",  # "Too cold: Glowing nodes..."
]

# How many characters before the match to check for negation
NEGATION_WINDOW = 60


def _has_negation_context(text, match_start):
    """Check if a banned word match is in negation context (anti-example)."""
    window_start = max(0, match_start - NEGATION_WINDOW)
    preceding = text[window_start:match_start].lower()
    return any(re.search(p, preceding) for p in NEGATION_PATTERNS)


def scan_banned_patterns(session, patterns):
    """Scan a session for banned patterns in assistant output and tool_use inputs.

    Args:
        session: Parsed Session object
        patterns: List of (pattern_regex, label) tuples

    Returns:
        List of violation dicts
    """
    violations = []

    for msg in session.messages:
        if msg.type != "assistant":
            continue

        # Scan response text
        for pattern, label in patterns:
            matches = list(pattern.finditer(msg.content_text))
            for m in matches:
                start = max(0, m.start() - 40)
                end = min(len(msg.content_text), m.end() + 40)
                is_negated = _has_negation_context(msg.content_text, m.start())
                violations.append({
                    "session_id": session.session_id[:8],
                    "line": msg.line_number,
                    "location": "response_text",
                    "pattern": label,
                    "match": m.group(),
                    "context": msg.content_text[start:end],
                    "is_post_boundary": msg.is_post_boundary,
                    "boundary_index": msg.boundary_index,
                    "is_negated": is_negated,
                })

        # Deep scan: tool_use inputs
        tool_text = extract_tool_text(msg.tool_uses)
        if tool_text:
            for pattern, label in patterns:
                matches = list(pattern.finditer(tool_text))
                for m in matches:
                    start = max(0, m.start() - 40)
                    end = min(len(tool_text), m.end() + 40)
                    is_negated = _has_negation_context(tool_text, m.start())
                    violations.append({
                        "session_id": session.session_id[:8],
                        "line": msg.line_number,
                        "location": "tool_use_input",
                        "pattern": label,
                        "match": m.group(),
                        "context": tool_text[start:end],
                        "is_post_boundary": msg.is_post_boundary,
                        "boundary_index": msg.boundary_index,
                        "is_negated": is_negated,
                    })

    return violations


def parse_banned_list(banned_file=None, banned_words=None):
    """Parse banned patterns from a file or list.

    File format: one pattern per line, optionally with label after |
        glowing|aesthetic_violation
        luminous|aesthetic_violation
        you'll need to|deferral

    Returns list of (compiled_regex, label) tuples.
    """
    patterns = []

    if banned_words:
        for word in banned_words:
            if "|" in word:
                pattern, label = word.rsplit("|", 1)
            else:
                pattern, label = word, word
            patterns.append((re.compile(r"\b" + re.escape(pattern) + r"\b", re.IGNORECASE), label))

    if banned_file:
        if not os.path.exists(banned_file):
            print(f"Warning: banned file not found: {banned_file}", file=sys.stderr)
        else:
            with open(banned_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "|" in line:
                        pattern, label = line.rsplit("|", 1)
                    else:
                        pattern, label = line, line
                    patterns.append((re.compile(r"\b" + re.escape(pattern.strip()) + r"\b", re.IGNORECASE), label.strip()))

    return patterns


def run_rule_scan(base_path=None, days=None, banned_file=None, banned_words=None):
    """Run banned pattern scan across sessions."""
    patterns = parse_banned_list(banned_file, banned_words)

    if not patterns:
        return {
            "error": "No patterns provided. Use --banned-file or --banned-words.",
            "violations": [],
        }

    if days is not None:
        files = find_sessions_by_date(base_path, days)
    else:
        files = find_sessions(base_path)

    all_violations = []
    session_count = 0

    for f in files:
        session = parse_session(f)
        if len(session.messages) < 5:
            continue
        session_count += 1
        violations = scan_banned_patterns(session, patterns)
        all_violations.extend(violations)

    # Separate negated (anti-examples) from real violations
    real_violations = [v for v in all_violations if not v.get("is_negated")]
    negated = [v for v in all_violations if v.get("is_negated")]

    # Categorize (real violations only for primary counts)
    in_response = [v for v in real_violations if v["location"] == "response_text"]
    in_tools = [v for v in real_violations if v["location"] == "tool_use_input"]
    post_compact = [v for v in real_violations if v["is_post_boundary"]]

    by_pattern = {}
    for v in real_violations:
        by_pattern.setdefault(v["pattern"], []).append(v)

    return {
        "sessions_scanned": session_count,
        "total_violations": len(real_violations),
        "total_negated": len(negated),
        "total_raw": len(all_violations),
        "in_response_text": len(in_response),
        "in_tool_use_input": len(in_tools),
        "post_boundary": len(post_compact),
        "by_pattern": {k: len(v) for k, v in by_pattern.items()},
        "violations": real_violations,
        "negated_violations": negated,
        "patterns_checked": len(patterns),
    }


def format_rules(results):
    """Format rule scan results as readable text."""
    lines = []
    lines.append("# Rule Adherence / Banned Pattern Scan")
    lines.append("")

    if results.get("error"):
        lines.append(f"ERROR: {results['error']}")
        return "\n".join(lines)

    lines.append(f"Patterns checked: {results['patterns_checked']}")
    lines.append(f"Sessions scanned: {results['sessions_scanned']}")
    lines.append(f"Total violations: {results['total_violations']}")
    lines.append(f"  In response text: {results['in_response_text']}")
    lines.append(f"  In tool_use input (DEEP): {results['in_tool_use_input']}")
    lines.append(f"  After a boundary: {results['post_boundary']}")
    if results.get("total_negated", 0) > 0:
        lines.append(f"  Anti-examples excluded: {results['total_negated']} (negation context detected)")
    lines.append("")

    if results["by_pattern"]:
        lines.append("## Violations By Pattern")
        for pat, count in sorted(results["by_pattern"].items(), key=lambda x: -x[1]):
            lines.append(f"  {pat}: {count}")
        lines.append("")

    if results["violations"]:
        # Show tool_use violations first (more important)
        tool_violations = [v for v in results["violations"] if v["location"] == "tool_use_input"]
        if tool_violations:
            lines.append("## Tool Use Violations (Deep Scan)")
            lines.append("*These are patterns that made it INTO file writes, generation prompts, etc.*")
            lines.append("")
            for v in tool_violations[-20:]:
                compact_tag = f" [POST-BOUNDARY #{v['boundary_index']+1}]" if v["is_post_boundary"] else ""
                lines.append(f"- `{v['session_id']}` L{v['line']}{compact_tag} [{v['pattern']}]: ...{v['context']}...")

        lines.append("")
        response_violations = [v for v in results["violations"] if v["location"] == "response_text"]
        if response_violations:
            lines.append("## Response Text Violations")
            lines.append("")
            for v in response_violations[-20:]:
                compact_tag = f" [POST-BOUNDARY #{v['boundary_index']+1}]" if v["is_post_boundary"] else ""
                lines.append(f"- `{v['session_id']}` L{v['line']}{compact_tag} [{v['pattern']}]: ...{v['context']}...")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Rule Adherence / Banned Pattern Scan")
    parser.add_argument("--path", help="Base path to search for sessions")
    parser.add_argument("--days", type=int, help="Only include sessions from last N days")
    parser.add_argument("--banned-file", help="Path to banned patterns file")
    parser.add_argument("--banned-words", nargs="+", help="Banned words/patterns")
    args = parser.parse_args()

    results = run_rule_scan(args.path, args.days, args.banned_file, args.banned_words)
    print(format_rules(results))
