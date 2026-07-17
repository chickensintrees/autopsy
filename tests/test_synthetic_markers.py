"""
Fixture test for skill-boot injection being misclassified as a live user message.

Finding (autopsy self-run, 2026-07-17): every Skill tool invocation injects the
full SKILL.md body into the transcript as a role="user" text message beginning
"Base directory for this skill: ...". The frustration/correction detectors treat
that prose like anything a user typed, so any skill whose own docs happen to
contain a phrase like "look at" or "did you actually" generates a false
frustration signal. On a real 7-day corpus this accounted for roughly two
thirds of reported frustration signals. See jsonl_parser.py's synthetic_markers.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from common.jsonl_parser import parse_session
from autopsy.corrections import find_user_frustration

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestSkillBootInjection(unittest.TestCase):
    def test_skill_boot_message_is_synthetic(self):
        s = parse_session(os.path.join(FIXTURES, "skill-boot-injection.jsonl"))
        boot_msg = s.messages[0]
        self.assertTrue(boot_msg.is_synthetic)

    def test_skill_boot_prose_does_not_count_as_frustration(self):
        s = parse_session(os.path.join(FIXTURES, "skill-boot-injection.jsonl"))
        frustrations = find_user_frustration(s)
        # Only the real user message should be flagged, not the injected skill body.
        self.assertEqual(len(frustrations), 1)
        self.assertIn("How many times", frustrations[0]["msg"])
