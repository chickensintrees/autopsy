#!/usr/bin/env python3
"""
Enable (or disable) the banner-relay Stop hook in Claude Code's settings.json.

Editing settings.json is a persistent, machine-wide change: the Stop hook fires on
every session, for every project. So this script is conservative — idempotent, it
backs up before writing, it refuses to touch a settings.json it can't parse, and
`--disable` cleanly removes exactly what it added.

Usage:
    python enable.py            # add the hook (idempotent)
    python enable.py --disable  # remove it
    python enable.py --dry-run  # show what would change, write nothing

Settings path defaults to ~/.claude/settings.json; override with AUTOPSY_SETTINGS
(used by the tests, and handy for a project-scoped .claude/settings.json).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

HOOK_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "check_banner_relay.py"))
MARKER = "check_banner_relay.py"  # how we recognize our own entry, idempotently


def settings_path():
    return os.environ.get("AUTOPSY_SETTINGS") or os.path.expanduser("~/.claude/settings.json")


def pick_python():
    """The interpreter that actually runs — not merely one that resolves on PATH."""
    for candidate in ("python3", "python"):
        try:
            r = subprocess.run(
                [candidate, "-c", "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)"],
                capture_output=True,
            )
            if r.returncode == 0:
                return candidate
        except OSError:
            continue
    return "python3"


def hook_command():
    # Double-quoted so a path with spaces survives both cmd and bash.
    return f'"{pick_python()}" "{HOOK_SCRIPT}"'


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)  # a JSONDecodeError here is intentional — see main()


def find_our_entries(settings):
    """Yield (group, hook) pairs under Stop that are ours."""
    for group in settings.get("hooks", {}).get("Stop", []):
        for h in group.get("hooks", []):
            if MARKER in h.get("command", ""):
                yield group, h


def enable(settings):
    if any(True for _ in find_our_entries(settings)):
        return settings, False  # already present
    hooks = settings.setdefault("hooks", {})
    stop = hooks.setdefault("Stop", [])
    stop.append({"hooks": [{"type": "command", "command": hook_command()}]})
    return settings, True


def disable(settings):
    """Strip our entries, and drop any Stop group left empty. Leaves everything else
    untouched. Whether anything actually changed is decided by the caller via
    `find_our_entries` before this runs."""
    stop = settings.get("hooks", {}).get("Stop", [])
    for group in list(stop):
        group["hooks"] = [h for h in group.get("hooks", []) if MARKER not in h.get("command", "")]
        if not group["hooks"]:
            stop.remove(group)
    return settings


def main():
    ap = argparse.ArgumentParser(description="Enable/disable the banner-relay Stop hook")
    ap.add_argument("--disable", action="store_true", help="remove the hook")
    ap.add_argument("--dry-run", action="store_true", help="print the change, write nothing")
    args = ap.parse_args()

    path = settings_path()
    try:
        settings = load(path)
    except json.JSONDecodeError:
        print(f"Refusing to edit: {path} is not valid JSON. Fix it by hand first.", file=sys.stderr)
        sys.exit(1)

    had_ours = any(True for _ in find_our_entries(settings))

    if args.disable:
        settings = disable(settings)
        did_change = had_ours
        verb = "Removed" if did_change else "Nothing to remove"
    else:
        settings, added = enable(settings)
        did_change = added
        verb = "Enabled" if added else "Already enabled"

    if args.dry_run:
        print(f"[dry-run] {verb}. settings.json would become:\n")
        print(json.dumps(settings, indent=2))
        return

    if did_change:
        if os.path.exists(path):
            shutil.copy(path, path + ".autopsy-bak")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")
        print(f"{verb} in {path}")
        if not args.disable:
            print(f"Hook command: {hook_command()}")
        if os.path.exists(path + ".autopsy-bak"):
            print(f"Backup: {path}.autopsy-bak")
    else:
        print(verb + ".")


if __name__ == "__main__":
    main()
