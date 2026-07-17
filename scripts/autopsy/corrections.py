"""
Correction Pair Detection — Find where user corrected the assistant,
and whether those corrections survived compaction.

The pattern: user corrects something → assistant says "You're right" / "I apologize" →
after compaction → assistant makes the same mistake again.

This is the most universal autopsy category. Everyone's corrections get lost.
"""

import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.jsonl_parser import find_sessions, find_sessions_by_date, parse_session


# Patterns that indicate the assistant acknowledged a correction
ACKNOWLEDGMENT_PATTERNS = [
    r"\byou'?re right\b",
    r"\bi apologize\b",
    r"\bi was wrong\b",
    r"\bgood catch\b",
    r"\bmy mistake\b",
    r"\bmy bad\b",
    r"\byou'?re correct\b",
    r"\bi stand corrected\b",
    r"\bsorry about that\b",
    r"\bi should have\b",
    r"\bthat'?s correct,? i\b",
    r"\bthank you for (?:the )?correct",
]

# Patterns that indicate the user is correcting/frustrated
USER_CORRECTION_PATTERNS = [
    r"\bthat'?s (?:not |wrong|incorrect)\b",
    r"\bno[,.]?\s+(?:it'?s|that'?s|i said|i told you)\b",
    r"\bhow many times\b",
    r"\bi(?:'ve| have) (?:already |just )?told you\b",
    r"\byou (?:already |just )?(?:forgot|lost|dropped)\b",
    r"\bthat'?s not what i\b",
    r"\bwrong (?:model|file|path|format|version)\b",
    r"\bi said\b.*\bnot\b",
    r"\byou live here\b",
    r"\blook (?:it up|around|at)\b",
    r"\bdid you (?:actually|even) (?:look|read|check)\b",
]


def find_correction_pairs(session):
    """Find correction → acknowledgment pairs in a session.

    Returns list of dicts with:
        - user_msg: the correcting user message
        - assistant_msg: the acknowledging assistant message
        - user_line: line number
        - assistant_line: line number
        - is_post_boundary: whether the correction happened after a compaction
        - boundary_index: which compaction this follows
        - pattern_matched: which acknowledgment pattern triggered
    """
    pairs = []
    messages = session.messages

    for i, msg in enumerate(messages):
        if msg.type != "assistant":
            continue

        # Check if assistant is acknowledging a correction
        text_lower = msg.content_text.lower()
        matched_pattern = None
        for pattern in ACKNOWLEDGMENT_PATTERNS:
            if re.search(pattern, text_lower):
                matched_pattern = pattern
                break

        if not matched_pattern:
            continue

        # Find the preceding user message (skip tool results and synthetic)
        preceding_user = None
        for j in range(i - 1, max(i - 10, -1), -1):
            if j >= 0 and messages[j].type == "user":
                if messages[j].is_tool_result_only or messages[j].is_synthetic:
                    continue
                preceding_user = messages[j]
                break

        if preceding_user:
            pairs.append({
                "user_msg": preceding_user.content_text[:500],
                "assistant_msg": msg.content_text[:500],
                "user_line": preceding_user.line_number,
                "assistant_line": msg.line_number,
                "is_post_boundary": msg.is_post_boundary,
                "boundary_index": msg.boundary_index,
                "pattern_matched": matched_pattern,
                "session_id": session.session_id[:8],
            })

    return pairs


def find_user_frustration(session):
    """Find user messages that match correction/frustration patterns.

    These may not have a paired acknowledgment (assistant may have
    proceeded confidently in the wrong direction).
    """
    frustrations = []

    for msg in session.messages:
        if msg.type != "user":
            continue
        if msg.is_tool_result_only or msg.is_synthetic:
            continue

        text_lower = msg.content_text.lower()
        matched = []
        for pattern in USER_CORRECTION_PATTERNS:
            if re.search(pattern, text_lower):
                matched.append(pattern)

        if matched:
            frustrations.append({
                "msg": msg.content_text[:500],
                "line": msg.line_number,
                "patterns": matched,
                "is_post_boundary": msg.is_post_boundary,
                "boundary_index": msg.boundary_index,
                "session_id": session.session_id[:8],
            })

    return frustrations


# Patterns for explicit user flags ("flag", "flag for autopsy", "flagged")
FLAG_PATTERNS = [
    r"\bflag\s+(?:this|that|it|for)\b",
    r"\bflagged\b",
    r"(?:^|\.\s+)flag\s*[.!]",  # "Flag." or "...something. Flag."
    r"(?:^|\n)\s*flag\s*$",  # just the word "flag" on its own line
]

# Phrases that mean the user is talking ABOUT flags, not flagging
FLAG_EXCLUSIONS = [
    r"\bfeature.flag",
    r"\bcommand.line.flag",
    r"\bboolean.flag",
    r"\b--\w+\b.*flag",  # CLI flags
]

# Messages that are system instructions or documentation injected as user messages.
# These often contain "flag" in instructional context ("Flag anything that needs attention").
SYSTEM_TEXT_MARKERS = [
    "Base directory for this skill:",  # Skill invocation text
    "---\nname:",                       # YAML frontmatter (skill docs)
]

# If a message is longer than this AND the "flag" match is past this position,
# it's likely buried in instructions, not a real user flag.
# Real flags are terse: "flag", "flag this", "Nope. Flag."
FLAG_MAX_POSITION = 500
FLAG_LONG_MESSAGE_THRESHOLD = 2000


def _is_system_text(text):
    """Check if a user message is actually system instructions or documentation."""
    for marker in SYSTEM_TEXT_MARKERS:
        if marker in text[:200]:
            return True
    return False


def _flag_match_position(text_lower):
    """Return the position of the first flag pattern match, or -1 if none."""
    for pattern in FLAG_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            return m.start()
    return -1


def find_user_flags(session):
    """Find user messages that explicitly flag a moment for review.

    Users write "flag" or "flag for autopsy" or "flagged" to mark
    moments that matter. These are the highest-confidence signals
    in the autopsy — the user called it out themselves.
    """
    flags = []

    messages = session.messages
    for i, msg in enumerate(messages):
        if msg.type != "user":
            continue
        if msg.is_tool_result_only or msg.is_synthetic:
            continue

        text = msg.content_text
        text_lower = text.lower()

        # Skip system instructions / skill documentation injected as user messages
        if _is_system_text(text):
            continue

        # Check exclusions first
        if any(re.search(ex, text_lower) for ex in FLAG_EXCLUSIONS):
            continue

        # Check flag patterns
        match_pos = _flag_match_position(text_lower)
        if match_pos < 0:
            continue

        # If the message is very long and "flag" is buried deep, it's likely
        # embedded in instructions, not a real user flag. Real flags are terse.
        if len(text) > FLAG_LONG_MESSAGE_THRESHOLD and match_pos > FLAG_MAX_POSITION:
            continue

        # Grab context: the assistant message before this flag
        preceding_assistant = None
        for j in range(i - 1, max(i - 5, -1), -1):
            if j >= 0 and messages[j].type == "assistant":
                preceding_assistant = messages[j]
                break

        flags.append({
            "msg": text[:500],
            "line": msg.line_number,
            "session_id": session.session_id[:8],
            "is_post_boundary": msg.is_post_boundary,
            "boundary_index": msg.boundary_index,
            "context_before": preceding_assistant.content_text[:300] if preceding_assistant else "",
        })

    return flags


def run_correction_scan(base_path=None, days=None):
    """Run correction pair detection across sessions.

    Returns:
        dict with correction findings
    """
    if days is not None:
        files = find_sessions_by_date(base_path, days)
    else:
        files = find_sessions(base_path)

    all_pairs = []
    all_frustrations = []
    all_flags = []

    for f in files:
        session = parse_session(f)
        if session.compaction_count == 0 and len(session.messages) < 10:
            continue  # Skip tiny sessions

        pairs = find_correction_pairs(session)
        frustrations = find_user_frustration(session)
        flags = find_user_flags(session)
        all_pairs.extend(pairs)
        all_frustrations.extend(frustrations)
        all_flags.extend(flags)

    # Separate pre/post compaction
    pre_compact = [p for p in all_pairs if not p["is_post_boundary"]]
    post_compact = [p for p in all_pairs if p["is_post_boundary"]]

    pre_frustration = [f for f in all_frustrations if not f["is_post_boundary"]]
    post_frustration = [f for f in all_frustrations if f["is_post_boundary"]]

    return {
        "total_correction_pairs": len(all_pairs),
        "pre_boundary_pairs": len(pre_compact),
        "post_boundary_pairs": len(post_compact),
        "total_user_frustrations": len(all_frustrations),
        "pre_boundary_frustrations": len(pre_frustration),
        "post_boundary_frustrations": len(post_frustration),
        "total_flags": len(all_flags),
        "pairs": all_pairs,
        "frustrations": all_frustrations,
        "flags": all_flags,
    }


def format_corrections(results):
    """Format correction results as readable text."""
    lines = []
    lines.append("# Correction Pair Analysis")
    lines.append("")
    lines.append(f"Total correction pairs (assistant acknowledged): {results['total_correction_pairs']}")
    lines.append(f"  Before a boundary: {results['pre_boundary_pairs']}")
    lines.append(f"  After a boundary: {results['post_boundary_pairs']}")
    lines.append("")
    lines.append(f"User frustration signals: {results['total_user_frustrations']}")
    lines.append(f"  Before a boundary: {results['pre_boundary_frustrations']}")
    lines.append(f"  After a boundary: {results['post_boundary_frustrations']}")
    lines.append("")

    if results.get("flags"):
        lines.append(f"User flags: {results['total_flags']}")
        lines.append("")
        lines.append("## User Flags")
        lines.append("*The user explicitly flagged these moments for review.*")
        lines.append("")
        for flag in results["flags"]:
            compact_tag = f" [POST-BOUNDARY #{flag['boundary_index']+1}]" if flag["is_post_boundary"] else ""
            lines.append(f"### `{flag['session_id']}` L{flag['line']}{compact_tag}")
            lines.append(f"**User:** {flag['msg'][:300]}")
            if flag["context_before"]:
                lines.append(f"**What was flagged:** {flag['context_before'][:200]}")
            lines.append("")

    if results["pairs"]:
        lines.append("## Correction Pairs (most recent first)")
        lines.append("")
        for p in results["pairs"][:20]:  # First 20 (newest sessions)
            compact_tag = f" [POST-BOUNDARY #{p['boundary_index']+1}]" if p["is_post_boundary"] else ""
            lines.append(f"### `{p['session_id']}` L{p['user_line']}{compact_tag}")
            lines.append(f"**User:** {p['user_msg'][:200]}")
            lines.append(f"**Assistant:** {p['assistant_msg'][:200]}")
            lines.append("")

    if results["frustrations"]:
        lines.append("## User Frustration Signals")
        lines.append("")
        for f in results["frustrations"][-15:]:  # Last 15
            compact_tag = f" [POST-BOUNDARY #{f['boundary_index']+1}]" if f["is_post_boundary"] else ""
            lines.append(f"- `{f['session_id']}` L{f['line']}{compact_tag}: {f['msg'][:200]}")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Correction Pair Detection")
    parser.add_argument("--path", help="Base path to search for sessions")
    parser.add_argument("--days", type=int, help="Only include sessions from last N days")
    args = parser.parse_args()

    results = run_correction_scan(args.path, args.days)
    print(format_corrections(results))
