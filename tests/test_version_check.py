"""
Tests for the clone-staleness classifier.

The git plumbing (ls-remote, merge-base) can't be unit-tested hermetically, so the
logic is a pure function and only that is tested here. The IO wrapper is kept thin on
purpose — the same split freshness.py uses.

The load-bearing case is `behind`: a clone that is an ancestor of origin/main is
running old code and must say so. The dangerous mistake would be calling `ahead`
(unpushed local work) "behind" and nagging the user to pull over their own commits.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from autopsy.version_check import classify


class TestClassify(unittest.TestCase):
    def test_up_to_date(self):
        status, _ = classify("abc123", "abc123", False)
        self.assertEqual(status, "up-to-date")

    def test_behind_warns_to_pull(self):
        status, msg = classify("aaaaaaa", "bbbbbbb", local_is_ancestor=True)
        self.assertEqual(status, "behind")
        self.assertIn("git pull", msg)

    def test_ahead_does_not_nag(self):
        """Local has commits origin lacks. Not stale. Must not tell the user to pull."""
        status, msg = classify("fffffff", "1111111", local_is_ancestor=False)
        self.assertEqual(status, "ahead")
        self.assertNotIn("git pull", msg)

    def test_unknown_when_a_sha_is_missing(self):
        self.assertEqual(classify(None, "abc", False)[0], "unknown")
        self.assertEqual(classify("abc", None, False)[0], "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
