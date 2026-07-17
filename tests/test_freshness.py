"""
Fixture tests for the skill freshness check.

The incident, 2026-07-17: repo at 6bfe0cc, installed SKILL.md byte-identical to it,
installed that morning. Everything checkable from the outside said healthy. The skill
body the agent was actually running was cd03f31's, seven commits stale, and it
followed a procedure main had already deleted. See freshness.py's docstring.

The known-negative matters as much as the known-positive here. A freshness check that
cries stale on a clean install gets a `2>/dev/null` within a week, and then it is not
a check at all.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from autopsy.freshness import (
    check_freshness,
    fingerprint,
    parse_skill_version,
)

REPO_SKILL = os.path.join(
    os.path.dirname(__file__), "..", "skills", "autopsy", "SKILL.md"
)

CURRENT = "---\nname: autopsy\nskill-version: 2\n---\n\n# Autopsy\n\nRun it. One command.\n"
STALE = "---\nname: autopsy\nskill-version: 1\n---\n\n# Autopsy\n\ncat assets/boot-flatline.txt\n"
UNVERSIONED = "---\nname: autopsy\n---\n\n# Autopsy\n"


class TestSkillVersion(unittest.TestCase):
    def test_reads_version_from_frontmatter(self):
        self.assertEqual(parse_skill_version(CURRENT), "2")

    def test_absent_version_is_none_not_a_crash(self):
        self.assertIsNone(parse_skill_version(UNVERSIONED))
        self.assertIsNone(parse_skill_version(None))

    def test_the_shipped_skill_declares_a_version(self):
        """The whole mechanism rests on this field existing in the real file."""
        with open(REPO_SKILL, "r", encoding="utf-8") as f:
            version = parse_skill_version(f.read())
        self.assertIsNotNone(
            version, "skills/autopsy/SKILL.md has no skill-version: the agent has "
                     "nothing to compare its injected copy against"
        )


class TestFingerprint(unittest.TestCase):
    def test_crlf_roundtrip_is_not_a_stale_skill(self):
        """A Windows checkout rewrites line endings. That is not drift."""
        self.assertEqual(fingerprint(CURRENT), fingerprint(CURRENT.replace("\n", "\r\n")))

    def test_real_change_moves_the_fingerprint(self):
        self.assertNotEqual(fingerprint(CURRENT), fingerprint(STALE))


class TestFreshness(unittest.TestCase):
    def test_fires_on_known_positive(self):
        """The 2026-07-17 case: installed copy is an older version."""
        warnings = check_freshness(CURRENT, STALE)
        self.assertTrue(warnings, "check did not fire on a stale install")
        self.assertIn("STALE INSTALL", warnings[0])

    def test_stale_warning_names_both_versions(self):
        """No finding without evidence. A bare 'something is stale' is not actionable."""
        warnings = check_freshness(CURRENT, STALE)
        self.assertIn("skill-version=2", warnings[0])
        self.assertIn("installed=1", warnings[0])

    def test_stale_warning_says_to_restart_not_just_reinstall(self):
        """Reinstalling mid-session does not reach a session already holding a copy.
        Telling the user to reinstall and stop there reproduces the original bug."""
        self.assertIn("NEW session", check_freshness(CURRENT, STALE)[0])

    def test_silent_on_known_negative(self):
        """Install matches the repo. Nothing to say."""
        self.assertEqual(check_freshness(CURRENT, CURRENT), [])

    def test_not_installed_is_reported(self):
        warnings = check_freshness(CURRENT, None)
        self.assertTrue(warnings)
        self.assertIn("NOT INSTALLED", warnings[0])

    def test_unbumped_version_under_changed_content_is_itself_a_warning(self):
        """A version nobody bumps cannot report drift. Catch the bump we forgot."""
        edited = CURRENT.replace("Run it. One command.", "Run it. Two commands.")
        warnings = check_freshness(edited, CURRENT)
        self.assertEqual(len(warnings), 2)
        self.assertIn("skill-version did NOT", warnings[1])

    def test_unreadable_repo_skill_degrades_quietly(self):
        """A freshness check that crashes the scan is worse than the drift it hunts."""
        warnings = check_freshness(None, CURRENT)
        self.assertEqual(len(warnings), 1)
        self.assertIn("skipping", warnings[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
