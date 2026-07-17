"""
Fixture tests for the tool amnesia detector.

These exist because a detector that never fires produces the same clean report as a
healthy system. A silent scanner and a system with nothing wrong look identical from
the outside, and only one of them is good news.

If you weaken a pattern or add a filter, run these first. A change that makes this
week's report cleaner by making the detector blind will fail here — that is the
entire point. See DESIGN.md, "Self-modification".
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from common.jsonl_parser import parse_session
from autopsy.amnesia import find_tool_amnesia

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestBoundaryModel(unittest.TestCase):
    def test_compaction_summary_is_not_a_second_boundary(self):
        """The isCompactSummary message is the compaction's payload, not a boundary.

        Counting it separately would double every compaction and invent a resume
        that never happened.
        """
        s = parse_session(os.path.join(FIXTURES, "amnesia-positive.jsonl"))
        self.assertEqual(len(s.boundaries), 1)
        self.assertEqual(s.boundaries[0].kind, "compaction")
        self.assertEqual(len(s.resumes), 0)

    def test_summary_text_attaches_to_its_compaction(self):
        s = parse_session(os.path.join(FIXTURES, "amnesia-positive.jsonl"))
        self.assertIn("continued from a previous conversation", s.boundaries[0].summary_text)

    def test_summary_is_synthetic_not_a_user_message(self):
        """It wears a user role. It is not the user speaking."""
        s = parse_session(os.path.join(FIXTURES, "amnesia-positive.jsonl"))
        summary = [m for m in s.messages if m.is_compact_summary]
        self.assertEqual(len(summary), 1)
        self.assertTrue(summary[0].is_synthetic)

    def test_retention_is_computed(self):
        s = parse_session(os.path.join(FIXTURES, "amnesia-positive.jsonl"))
        self.assertEqual(s.boundaries[0].retention_pct, 5.0)
        self.assertEqual(s.boundaries[0].discarded_tokens, 95000)

    def test_known_tools_are_read_from_metadata(self):
        s = parse_session(os.path.join(FIXTURES, "amnesia-positive.jsonl"))
        self.assertEqual(s.boundaries[0].known_tools, ["WebSearch"])


class TestToolAmnesia(unittest.TestCase):
    def test_fires_on_known_positive(self):
        """Tool known at the boundary, never used after, deferred on. A finding."""
        s = parse_session(os.path.join(FIXTURES, "amnesia-positive.jsonl"))
        findings = find_tool_amnesia(s)
        self.assertEqual(len(findings), 1, "detector did not fire on a known-positive case")
        self.assertEqual(findings[0]["tool"], "WebSearch")
        self.assertTrue(findings[0]["deferrals"], "finding carries no evidence")

    def test_finding_carries_a_line_number_and_a_quote(self):
        """No finding without a quote and a line number."""
        s = parse_session(os.path.join(FIXTURES, "amnesia-positive.jsonl"))
        d = find_tool_amnesia(s)[0]["deferrals"][0]
        self.assertIsInstance(d["line"], int)
        self.assertIn("google it yourself", d["quote"])

    def test_silent_on_known_negative(self):
        """The tool was used again. Knowledge intact. Not a finding."""
        s = parse_session(os.path.join(FIXTURES, "amnesia-negative.jsonl"))
        self.assertEqual(find_tool_amnesia(s), [])

    def test_unused_is_not_the_same_as_forgotten(self):
        """A tool that simply never came up again is not amnesia.

        Without this, every long session reports amnesia for every tool it stopped
        needing, and the report becomes noise nobody reads.
        """
        s = parse_session(os.path.join(FIXTURES, "amnesia-positive.jsonl"))
        for f in find_tool_amnesia(s):
            self.assertTrue(f["deferrals"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
