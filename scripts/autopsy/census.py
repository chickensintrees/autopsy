"""
Census — how many boundaries, and what each one cost.

The baseline for everything else. A boundary is where context was reconstructed
instead of remembered; this counts them and reports what did not survive.

The interesting number is retention: what percent of the context was still there
afterward. In practice it is small.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.jsonl_parser import find_sessions, find_sessions_by_date, parse_session


def run_census(base_path=None, days=None, min_boundaries=0):
    """Count sessions and boundaries, and measure what each boundary discarded."""
    files = find_sessions_by_date(base_path, days) if days is not None else find_sessions(base_path)

    sessions = []
    total_compactions = 0
    total_resumes = 0
    total_size = 0
    total_messages = 0
    retentions = []
    discarded = 0

    for f in files:
        session = parse_session(f)
        if session.boundary_count < min_boundaries:
            continue

        for b in session.compactions:
            if b.pre_tokens:
                retentions.append(b.retention_pct)
                discarded += b.discarded_tokens

        sessions.append({
            "session_id": session.session_id[:8],
            "full_id": session.session_id,
            "size_mb": round(session.size_mb, 1),
            "entry": session.entry_kind,
            "compactions": session.compaction_count,
            "resumes": len(session.resumes),
            "messages": len(session.messages),
            "start": session.start_time,
            "end": session.end_time,
            "triggers": [b.trigger for b in session.compactions],
            "retentions": [b.retention_pct for b in session.compactions],
            "tools_at_boundary": sorted({t for b in session.compactions for t in b.known_tools}),
        })
        total_compactions += session.compaction_count
        total_resumes += len(session.resumes)
        total_size += session.file_size
        total_messages += len(session.messages)

    sessions.sort(key=lambda s: s["compactions"], reverse=True)

    return {
        "total_sessions": len(sessions),
        "total_boundaries": total_compactions + total_resumes,
        "total_compactions": total_compactions,
        "total_resumes": total_resumes,
        "total_size_mb": round(total_size / (1024 * 1024), 1),
        "total_messages": total_messages,
        "sessions": sessions,
        "sessions_with_boundaries": len([s for s in sessions if s["compactions"] or s["resumes"]]),
        "resumed_sessions": len([s for s in sessions if s["entry"] == "resumed"]),
        "avg_retention_pct": round(sum(retentions) / len(retentions), 1) if retentions else 0,
        "worst_retention_pct": min(retentions) if retentions else 0,
        "total_tokens_discarded": discarded,
    }


def format_census(results):
    """Format census results."""
    lines = []
    lines.append("# Census")
    lines.append("")
    lines.append(f"Sessions analyzed: {results['total_sessions']} ({results['total_size_mb']} MB, {results['total_messages']} messages)")
    lines.append(f"Sessions with a boundary: {results['sessions_with_boundaries']}")
    lines.append(f"Sessions resumed from a prior session: {results['resumed_sessions']}")
    lines.append("")
    lines.append(f"Boundaries: **{results['total_boundaries']}** "
                 f"({results['total_compactions']} compaction, {results['total_resumes']} session-resume)")

    if results["total_compactions"]:
        lines.append(f"Average context retained across a compaction: **{results['avg_retention_pct']}%**")
        lines.append(f"Worst single retention: **{results['worst_retention_pct']}%**")
        lines.append(f"Total tokens discarded: **{results['total_tokens_discarded']:,}**")

    lines.append("")
    lines.append("| Session | Entry | MB | Compactions | Retained | Messages | Triggers |")
    lines.append("|---------|-------|-----|-------------|----------|----------|----------|")
    for s in results["sessions"]:
        triggers = ", ".join(s["triggers"]) if s["triggers"] else "-"
        retained = ", ".join(f"{r}%" for r in s["retentions"]) if s["retentions"] else "-"
        lines.append(
            f"| `{s['session_id']}` | {s['entry']} | {s['size_mb']} | {s['compactions']} "
            f"| {retained} | {s['messages']} | {triggers} |"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Census — boundaries and what they cost")
    parser.add_argument("--path", help="Base path to search for sessions")
    parser.add_argument("--days", type=int, help="Only include sessions from last N days")
    parser.add_argument("--min-boundaries", type=int, default=0, help="Minimum boundaries to include")
    args = parser.parse_args()

    print(format_census(run_census(args.path, args.days, args.min_boundaries)))
