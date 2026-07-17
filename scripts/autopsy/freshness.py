"""
Is the skill that is *running* the skill that is on *disk*?

Found 2026-07-17, by an autopsy run that failed at the first step. The repo was at
6bfe0cc. The installed SKILL.md was byte-identical to it, mtime 10:26 that morning.
Every check available from the outside said the install was healthy. The skill body
the agent had actually been handed was cd03f31's -- seven commits stale. It followed
the retired procedure, ran `cat assets/boot-flatline.txt` (a step main had already
deleted, against a directory the installer never populates), and the cold open died.
The fix for that had been written, committed, and installed hours earlier. It did not
reach the run.

Two different drifts, and they need different alarms:

  repo -> installed   Someone edited the repo and did not reinstall. The script can
                      see both files, so it can just check. That is `check_freshness`.

  installed -> agent  The harness snapshots SKILL.md when the session starts. Editing
                      or reinstalling does not reach a session already holding a copy;
                      only a restart does. No script can read the agent's context, so
                      this one cannot be *checked* -- it can only be made checkable.
                      Hence `skill-version`: the script prints the version on disk, the
                      agent reads the version in the copy it was handed, and a human
                      number mismatch does what no prose in the stale file could.

A version that is never bumped is the same failure wearing a different mask, so
content drift under an unchanged version is itself a warning.
"""

import hashlib
import os
import re

SKILL_VERSION_RE = re.compile(r"^skill-version:\s*(\S+)\s*$", re.MULTILINE)

REPO_SKILL = os.path.join(
    os.path.dirname(__file__), "..", "..", "skills", "autopsy", "SKILL.md"
)
INSTALLED_SKILL = os.path.join(
    os.path.expanduser("~"), ".claude", "skills", "autopsy", "SKILL.md"
)


def parse_skill_version(text):
    """Pull `skill-version:` out of the frontmatter. None if absent."""
    if not text:
        return None
    match = SKILL_VERSION_RE.search(text)
    return match.group(1) if match else None


def fingerprint(text):
    """Content hash, newline-normalized. Windows checkouts rewrite line endings, and
    a CRLF round-trip is not a stale skill."""
    if text is None:
        return None
    normalized = text.replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:12]


def check_freshness(repo_text, installed_text):
    """Compare the repo skill against the installed one.

    Pure: takes text, returns warnings. Returns [] when they agree. Each warning is
    one line, already phrased for a human.
    """
    warnings = []

    if repo_text is None:
        return ["Cannot read the repo's SKILL.md -- skipping the freshness check."]

    repo_version = parse_skill_version(repo_text)

    if installed_text is None:
        warnings.append(
            "Skill is NOT INSTALLED (no ~/.claude/skills/autopsy/SKILL.md). "
            "Run ./install.sh (or .\\install.ps1)."
        )
        return warnings

    installed_version = parse_skill_version(installed_text)

    if fingerprint(repo_text) != fingerprint(installed_text):
        warnings.append(
            "STALE INSTALL: the repo's SKILL.md differs from the installed copy "
            "(repo skill-version=%s, installed=%s). Run the installer, then start a "
            "NEW session -- a session already running holds the old copy."
            % (repo_version, installed_version)
        )
        if repo_version == installed_version:
            warnings.append(
                "The content changed but skill-version did NOT. Bump it, or the "
                "version stops being able to report drift."
            )

    return warnings


def read_freshness_warnings():
    """Read both files off disk and check them. Never raises -- a freshness check that
    crashes the scan would be a worse bug than the drift it looks for."""
    def read(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return None

    return check_freshness(read(REPO_SKILL), read(INSTALLED_SKILL))


def skill_version_on_disk():
    """The version the *repo* declares. Printed every run so the agent can compare it
    against the version in the copy it was handed."""
    try:
        with open(REPO_SKILL, "r", encoding="utf-8") as f:
            return parse_skill_version(f.read())
    except (OSError, UnicodeDecodeError):
        return None
