"""
Capability Regression Detection — Find where the assistant deferred to
the user for things it could have done itself.

The pattern: "you'll need to manually..." / "I can't access..." / "you should log in..."
when the assistant has the tools available.

Post-compaction regressions are especially telling — the assistant forgets
what it's capable of.
"""

import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.jsonl_parser import find_sessions, find_sessions_by_date, parse_session


# Deferral patterns — assistant pushing work to user
DEFERRAL_PATTERNS = [
    (r"\byou(?:'ll| will) (?:need|have|want) to\b", "explicit_deferral"),
    (r"\byou (?:should|could|might want to) (?:manually|check|log in|open|visit|go to|navigate)\b", "suggestion_deferral"),
    (r"\bi (?:can'?t|cannot|don'?t have|am unable to|don'?t think i can)\b", "inability_claim"),
    (r"\bunfortunately,? i (?:can'?t|cannot|don'?t|am not able)\b", "hedged_inability"),
    (r"\byou(?:'ll| will) (?:need|have) to (?:do |handle |manage )?(?:that|this|it) (?:yourself|manually)\b", "manual_deferral"),
    (r"\bi (?:don'?t|can'?t) have (?:access|permission|the ability)\b", "access_denial"),
    (r"\bthat (?:requires|needs) (?:you to|manual|human|a browser|a GUI)\b", "requirement_claim"),
]

# Context clues that make a deferral likely legitimate
LEGITIMATE_CONTEXTS = [
    r"\bbrowser\b.*\blogin\b",
    r"\b2fa\b",
    r"\btwo.factor\b",
    r"\bcaptcha\b",
    r"\bphysical\b",
    r"\bin.person\b",
    r"\bphone call\b",
    r"\bcorporate\b.*\bauth\b",
    r"\bsso\b",
    r"\bsharepoint\b",
    r"\bauthenticat",
    r"\bbut i (?:can|could|will|should)\b",  # self-correcting: "I can't X but I can Y"
    r"\binstead\b",  # offering alternative
    r"\bhowever\b",  # qualifying the limitation
    r"\bi can'?t listen\b",  # genuine limitation (no audio)
    r"\bi can'?t (?:see|view|watch|hear|listen|open a browser)\b",  # sensory/UI limits
    r"\bheadless\b",  # mentioning headless as workaround
]

# Meta-discussion patterns — the assistant is ANALYZING deferrals, not deferring.
# "The inability_claim pattern matches any 'I can't'" is about the pattern, not a regression.
META_DISCUSSION_PATTERNS = [
    r"\bpattern\b",
    r"\bdetect\b",
    r"\bscan\b",
    r"\bmatch(?:es|ed|ing)?\b",
    r"\bregex\b",
    r"\bfilter\b",
    r"\blegitimate.context",
    r"['\"\u201c\u201d].*?(?:i can'?t|i don'?t).*?['\"\u201c\u201d]",  # quoted "I can't"
    r"\bclaimed\b",  # "Claimed 'I can't edit Figma'"
    r"\bno ['\"]i can'?t\b",  # "No 'I can't edit it.'" — celebrating non-regression
]


def find_deferrals(session):
    """Find assistant messages that defer work to the user.

    Returns list of dicts with deferral details.
    """
    deferrals = []

    for msg in session.messages:
        if msg.type != "assistant":
            continue

        text_lower = msg.content_text.lower()
        matched = []

        for pattern, category in DEFERRAL_PATTERNS:
            matches = list(re.finditer(pattern, text_lower))
            for m in matches:
                # Get surrounding context (50 chars each side)
                start = max(0, m.start() - 50)
                end = min(len(text_lower), m.end() + 50)
                context = text_lower[start:end]

                # Wider context for meta-discussion check (150 chars each side)
                meta_start = max(0, m.start() - 150)
                meta_end = min(len(text_lower), m.end() + 150)
                wide_context = text_lower[meta_start:meta_end]

                # Check if likely legitimate
                is_legitimate = any(
                    re.search(lp, context) for lp in LEGITIMATE_CONTEXTS
                )

                # Check if meta-discussion (analyzing patterns, not exhibiting them)
                is_meta = any(
                    re.search(mp, wide_context) for mp in META_DISCUSSION_PATTERNS
                )

                matched.append({
                    "pattern": pattern,
                    "category": category,
                    "match": m.group(),
                    "context": msg.content_text[start:end],
                    "likely_legitimate": is_legitimate or is_meta,
                    "is_meta": is_meta,
                })

        if matched:
            deferrals.append({
                "line": msg.line_number,
                "session_id": session.session_id[:8],
                "is_post_boundary": msg.is_post_boundary,
                "boundary_index": msg.boundary_index,
                "matches": matched,
                "full_text": msg.content_text[:500],
            })

    return deferrals


def run_regression_scan(base_path=None, days=None):
    """Run capability regression detection across sessions."""
    if days is not None:
        files = find_sessions_by_date(base_path, days)
    else:
        files = find_sessions(base_path)

    all_deferrals = []
    session_count = 0

    for f in files:
        session = parse_session(f)
        if len(session.messages) < 10:
            continue
        session_count += 1

        deferrals = find_deferrals(session)
        all_deferrals.extend(deferrals)

    # Categorize
    pre_compact = [d for d in all_deferrals if not d["is_post_boundary"]]
    post_compact = [d for d in all_deferrals if d["is_post_boundary"]]

    # Suspicious = post-compaction AND not clearly legitimate.
    # Pre-compaction deferrals are just normal conversation.
    suspicious = [
        d for d in post_compact
        if not all(m["likely_legitimate"] for m in d["matches"])
    ]

    # Count how many were filtered by meta-discussion detection
    meta_filtered = [
        d for d in post_compact
        if not all(m["likely_legitimate"] for m in d["matches"])
        or any(m.get("is_meta") for m in d["matches"])
    ]
    meta_count = len([
        d for d in post_compact
        if any(m.get("is_meta") for m in d["matches"])
        and not any(m["likely_legitimate"] and not m.get("is_meta") for m in d["matches"])
    ])

    by_category = {}
    for d in all_deferrals:
        for m in d["matches"]:
            cat = m["category"]
            by_category.setdefault(cat, []).append(d)

    return {
        "sessions_scanned": session_count,
        "total_deferrals": len(all_deferrals),
        "pre_compaction": len(pre_compact),
        "post_boundary": len(post_compact),
        "suspicious": len(suspicious),
        "meta_filtered": meta_count,
        "by_category": {k: len(v) for k, v in by_category.items()},
        "deferrals": all_deferrals,
        "suspicious_deferrals": suspicious,
    }


def format_regressions(results):
    """Format regression results as readable text."""
    lines = []
    lines.append("# Capability Regression Detection")
    lines.append("")
    lines.append(f"Sessions scanned: {results['sessions_scanned']}")
    lines.append(f"Total deferrals found: {results['total_deferrals']}")
    lines.append(f"  Before a boundary: {results['pre_compaction']}")
    lines.append(f"  After a boundary: {results['post_boundary']}")
    lines.append(f"  Suspicious (likely not legitimate): {results['suspicious']}")
    if results.get("meta_filtered", 0) > 0:
        lines.append(f"  Meta-discussion excluded: {results['meta_filtered']} (analyzing patterns, not exhibiting them)")
    lines.append("")

    if results["by_category"]:
        lines.append("## By Category")
        for cat, count in sorted(results["by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"  {cat}: {count}")
        lines.append("")

    if results["suspicious_deferrals"]:
        lines.append("## Post-Compaction Deferrals (likely regression)")
        lines.append("*These happened after compaction and don't match known legitimate patterns.*")
        lines.append("")
        for d in results["suspicious_deferrals"][:15]:
            lines.append(f"### `{d['session_id']}` L{d['line']} [POST-BOUNDARY #{d['boundary_index']+1}]")
            for m in d["matches"]:
                if not m["likely_legitimate"]:
                    lines.append(f"  Pattern: {m['category']}")
                    lines.append(f"  Context: ...{m['context']}...")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Capability Regression Detection")
    parser.add_argument("--path", help="Base path to search for sessions")
    parser.add_argument("--days", type=int, help="Only include sessions from last N days")
    args = parser.parse_args()

    results = run_regression_scan(args.path, args.days)
    print(format_regressions(results))
