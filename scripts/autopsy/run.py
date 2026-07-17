#!/usr/bin/env python3
"""
Autopsy — read the record of agentic work, find what the system failed to retain.

The report this produces is not the deliverable. It is the intake form. The
deliverable is a rule, a hook, a doc, a script — something durable enough that the
lesson does not have to be learned a third time. See the skill.

Usage:
    python run.py --days 7
    python run.py --days 7 --banned-words glowing luminous
    python run.py --days 7 --banner=minimal -o report.md
"""

import argparse
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from census import run_census, format_census
from corrections import run_correction_scan, format_corrections
from regressions import run_regression_scan, format_regressions
from rules import run_rule_scan, format_rules
from amnesia import run_amnesia_scan, format_amnesia
from freshness import read_freshness_warnings, skill_version_on_disk

ASSETS = os.path.join(os.path.dirname(__file__), "..", "..", "assets")


def print_banner(which):
    """Cold open. Static art, read from disk — never generated."""
    if which == "none":
        return
    path = os.path.join(ASSETS, f"boot-{which}.txt")
    if not os.path.exists(path):
        # Do not fail silent. A missing cold open is the ritual quietly not happening,
        # which is the exact failure the ritual exists to prevent — and the most likely
        # cause is an install whose clone was moved or deleted.
        print(f"[autopsy] Cold open missing: {os.path.normpath(path)}\n"
              f"[autopsy] The skill is installed but the repo it points at is gone or moved. "
              f"Re-clone and rerun ./install.sh (or .\\install.ps1).",
              file=sys.stderr)
        return
    with open(path, "r", encoding="utf-8") as f:
        print(f.read(), file=sys.stderr)


def print_freshness(banner):
    """Is the skill that is running the skill that is on disk?

    Two drifts. `check_freshness` catches repo-vs-installed by reading both files.
    Nothing can read the agent's context, so installed-vs-running is made checkable
    instead of checked: print the version on disk and let the agent compare it against
    the copy it was handed. See freshness.py — 2026-07-17.
    """
    version = skill_version_on_disk()
    if version and banner != "none":
        print(f"[autopsy] skill-version on disk: {version} -- if the SKILL.md you are "
              f"running declares a different one, your session is holding a stale "
              f"snapshot. Reinstall and start a new session before trusting this run.",
              file=sys.stderr)
    for warning in read_freshness_warnings():
        print(f"[autopsy] {warning}", file=sys.stderr)


def format_tag(results, cause):
    """The closing stamp. Boots blank, gets filled in. If nothing was found, it
    says so plainly — a tag reading 'nothing to report' is a real finding."""
    intake = results.get("intake", "~/.claude/projects")
    lines = [
        "",
        "              .-------------------------.",
        "             /  o                        \\",
        f"            |  ---  SUBJECT: this system  |",
        f"            |       INTAKE:  {intake[:12]:<12} |",
        f"            |       CAUSE:   {cause[:12]:<12} |",
        "             \\       .................   /",
        "              '-------------------------'",
        "",
    ]
    return "\n".join(lines)


def determine_cause(results):
    """One line for the tag. The dominant failure, or an honest nothing."""
    amnesia = results["amnesia"]["total_findings"]
    corrections = results["corrections"]["post_boundary_pairs"]
    flags = results["corrections"].get("total_flags", 0)
    violations = results["rules"]["total_violations"] if results.get("rules") else 0

    if flags:
        return "user-flagged"
    if amnesia:
        return "tool amnesia"
    if corrections:
        return "lost fixes"
    if violations:
        return "rule breach"
    return "nothing"


def run_full_autopsy(base_path=None, days=None, banned_file=None, banned_words=None):
    """Run every category and return combined results."""
    print("Census...", file=sys.stderr)
    census = run_census(base_path, days)

    print("Correction pairs...", file=sys.stderr)
    corrections = run_correction_scan(base_path, days)

    print("Tool amnesia...", file=sys.stderr)
    amnesia = run_amnesia_scan(base_path, days)

    print("Capability deferrals...", file=sys.stderr)
    regressions = run_regression_scan(base_path, days)

    rules = None
    if banned_file or banned_words:
        print("Banned patterns...", file=sys.stderr)
        rules = run_rule_scan(base_path, days, banned_file, banned_words)

    return {
        "census": census,
        "corrections": corrections,
        "amnesia": amnesia,
        "regressions": regressions,
        "rules": rules,
        "intake": base_path or "~/.claude",
    }


def format_full_report(results):
    """Format the intake form."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    census = results["census"]
    corrections = results["corrections"]
    amnesia = results["amnesia"]
    regressions = results["regressions"]

    lines.append("# Autopsy Report")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **{census['total_sessions']}** sessions ({census['total_size_mb']} MB)")
    lines.append(f"- **{census['total_boundaries']}** boundaries "
                 f"({census['total_compactions']} compaction, {census['total_resumes']} resume)")
    if census["total_compactions"]:
        lines.append(f"- **{census['avg_retention_pct']}%** average context retained across a compaction "
                     f"({census['total_tokens_discarded']:,} tokens discarded)")
    lines.append(f"- **{amnesia['total_findings']}** tool amnesia findings "
                 f"(from {amnesia['boundaries_with_tool_data']} boundaries carrying tool data)")
    lines.append(f"- **{corrections['total_correction_pairs']}** correction pairs "
                 f"({corrections['post_boundary_pairs']} after a boundary)")
    lines.append(f"- **{corrections['total_user_frustrations']}** frustration signals "
                 f"({corrections['post_boundary_frustrations']} after a boundary)")
    if corrections.get("total_flags", 0):
        lines.append(f"- **{corrections['total_flags']}** user flags")
    lines.append(f"- **{regressions['total_deferrals']}** capability deferrals "
                 f"({regressions['suspicious']} suspicious)")
    if results["rules"] and "error" not in results["rules"]:
        r = results["rules"]
        note = f", {r['total_negated']} anti-examples excluded" if r.get("total_negated") else ""
        lines.append(f"- **{r['total_violations']}** banned pattern violations "
                     f"({r['in_tool_use_input']} in tool_use inputs{note})")
    lines.append("")

    findings = (amnesia["total_findings"] + corrections["total_correction_pairs"]
                + corrections.get("total_flags", 0) + regressions["suspicious"])
    lines.append(f"**{findings} findings need a durable fix.** A finding without an artifact "
                 f"is a finding you will meet again. See the skill for what each one becomes.")
    lines.append("")
    lines.append("---")
    lines.append("")

    if corrections.get("total_flags", 0):
        lines.append("*User flags appear first. The user told you which moments mattered.*")
        lines.append("")

    for section in (format_census(census), format_amnesia(amnesia),
                    format_corrections(corrections), format_regressions(regressions)):
        lines.append(section)
        lines.append("")
        lines.append("---")
        lines.append("")

    if results["rules"]:
        lines.append(format_rules(results["rules"]))
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Method")
    lines.append("")
    lines.append("Scripts extract candidates and carry evidence. They do not decide what a")
    lines.append("finding means — the skill does, and then proposes the fix.")
    lines.append("")
    lines.append("1. **Census** — boundaries, and what each one discarded")
    lines.append("2. **Tool amnesia** — tools known at a boundary, per `preCompactDiscoveredTools`,")
    lines.append("   that went unused afterward while the agent deferred on that exact work")
    lines.append("3. **Correction pairs** — the user corrected; the agent agreed")
    lines.append("4. **Capability deferrals** — inferred from phrasing; weaker than amnesia")
    lines.append("5. **Banned patterns** — deep scan, including tool_use inputs")
    lines.append("")
    lines.append("**Two passes.** The first scan is always too generous. Run the second.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Autopsy — find what the system failed to retain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--path", help="Base path to search (default: ~/.claude/projects/)")
    parser.add_argument("--days", type=int, help="Only sessions from the last N days")
    parser.add_argument("--banned-file", help="Banned patterns file (one per line)")
    parser.add_argument("--banned-words", nargs="+", help="Banned words/patterns")
    parser.add_argument("--banner", default="flatline",
                        choices=["flatline", "tape", "minimal", "none"],
                        help="Cold open. Use minimal for scheduled runs.")
    parser.add_argument("--output", "-o", help="Write report to a file")
    parser.add_argument("--json", action="store_true", help="Raw JSON instead of a report")
    args = parser.parse_args()

    print_banner(args.banner)
    print_freshness(args.banner)

    results = run_full_autopsy(
        base_path=args.path,
        days=args.days,
        banned_file=args.banned_file,
        banned_words=args.banned_words,
    )

    if args.json:
        import json
        output = json.dumps(results, indent=2, default=str)
    else:
        output = format_full_report(results) + "\n" + format_tag(results, determine_cause(results))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
