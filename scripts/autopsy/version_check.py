"""
Is this CLONE behind the published version?

freshness.py answers three local drifts: repo ↔ installed ↔ running. This answers a
fourth that no local file can see — the clone itself is behind `origin/main` on
GitHub. An agent can install cleanly, run the freshest *installed* skill, and still
execute a months-old autopsy because nobody ever pulled. That is the "agents run the
old version by default" failure, and it is invisible from inside the clone.

Design constraints, both deliberate:

- **run.py never calls this.** The scan advertises "nothing is sent anywhere," and it
  keeps that promise. This is a separate step, invoked by the agent per the skill.
- **Only the user's own remote.** It reads `origin` — the remote they configured by
  cloning — not a hardcoded endpoint. One `git ls-remote`, hard 5s timeout, and every
  failure path (no git, no network, no origin, detached HEAD) returns a clean
  "unknown" rather than failing anything. A version check that breaks the run would be
  a worse bug than the staleness it looks for.

The comparison is pure and unit-tested (`classify`); only the git plumbing is not.
"""

import os
import subprocess

REMOTE_TIMEOUT_S = 5
MAIN_REF = "refs/heads/main"


def classify(local_sha, remote_sha, local_is_ancestor):
    """Pure. Given two shas and whether local is an ancestor of remote, return
    (status, one-line message). status in: up-to-date, behind, ahead, diverged,
    unknown."""
    if not local_sha or not remote_sha:
        return ("unknown", "Could not determine the published version — skipping.")

    if local_sha == remote_sha:
        return ("up-to-date", "This clone matches origin/main. Running the newest autopsy.")

    if local_is_ancestor:
        return (
            "behind",
            "STALE CLONE: origin/main on GitHub is newer than this checkout "
            f"(local {local_sha[:7]}, remote {remote_sha[:7]}). You are running an old "
            "autopsy. Run `git pull` and re-run ./install.sh before trusting findings.",
        )

    # local is not an ancestor of remote: either local is ahead (unpushed work) or the
    # two have diverged. Either way, not stale — don't cry wolf.
    return (
        "ahead",
        f"This clone has commits origin/main lacks (local {local_sha[:7]}, "
        f"remote {remote_sha[:7]}). Not stale; nothing to pull.",
    )


def _git(root, *args):
    """Run a git command under root. Return stripped stdout, or None on any failure."""
    try:
        out = subprocess.run(
            ["git", "-C", root, *args],
            capture_output=True, text=True, timeout=REMOTE_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def check_clone_version(root=None):
    """Compare local HEAD against origin/main on GitHub. Returns a one-line message,
    or None if the check couldn't run (not a git clone, offline, no origin). Never
    raises."""
    if root is None:
        root = os.path.join(os.path.dirname(__file__), "..", "..")
    root = os.path.abspath(root)

    if _git(root, "rev-parse", "--is-inside-work-tree") != "true":
        return None  # not a git clone (e.g. installed via tarball) — nothing to check

    local = _git(root, "rev-parse", "HEAD")

    # ls-remote is the network call. One round trip to the user's own origin.
    remote_line = _git(root, "ls-remote", "origin", MAIN_REF)
    remote = remote_line.split()[0] if remote_line else None

    if not local or not remote:
        return None  # offline, or no origin — stay silent, this is best-effort

    if local == remote:
        return None  # up to date: say nothing, don't add noise to a healthy run

    # merge-base --is-ancestor signals via exit code, not stdout: exit 0 = ancestor.
    # _git returns "" on exit 0 and None on non-zero, so `is not None` is the answer.
    is_ancestor = _git(root, "merge-base", "--is-ancestor", local, remote) is not None

    status, message = classify(local, remote, is_ancestor)
    return message if status in ("behind", "ahead") else None


if __name__ == "__main__":
    msg = check_clone_version()
    if msg:
        print(f"[autopsy] {msg}")
    else:
        print("[autopsy] version check: up to date, or not applicable (no git/origin/network).")
