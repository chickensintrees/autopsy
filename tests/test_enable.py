"""
Tests for the hook enabler. It edits settings.json — a persistent, machine-wide file —
so the properties that matter are safety ones: it never clobbers unrelated content, it
is idempotent, and enable→disable is a clean round-trip back to the original.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ENABLE = os.path.join(os.path.dirname(__file__), "..", "hooks", "enable.py")


def _run(settings_path, *args):
    env = dict(os.environ, AUTOPSY_SETTINGS=settings_path)
    p = subprocess.run([sys.executable, ENABLE, *args], env=env, capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


class TestEnable(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.sp = os.path.join(self.dir, "settings.json")

    def _load(self):
        with open(self.sp, encoding="utf-8") as f:
            return json.load(f)

    def _our_entries(self, settings):
        return [h for g in settings.get("hooks", {}).get("Stop", [])
                for h in g.get("hooks", []) if "check_banner_relay" in h.get("command", "")]

    def test_enable_from_scratch(self):
        _run(self.sp)  # no file yet
        self.assertEqual(len(self._our_entries(self._load())), 1)

    def test_idempotent(self):
        _run(self.sp)
        _run(self.sp)
        self.assertEqual(len(self._our_entries(self._load())), 1, "second enable must not duplicate")

    def test_preserves_unrelated_content(self):
        original = {"model": "opus",
                    "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo keep-me"}]}]}}
        json.dump(original, open(self.sp, "w"))
        _run(self.sp)
        s = self._load()
        self.assertEqual(s["model"], "opus")
        self.assertTrue(any("keep-me" in h["command"]
                            for g in s["hooks"]["Stop"] for h in g["hooks"]))

    def test_clean_round_trip(self):
        original = {"model": "opus",
                    "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo keep-me"}]}]}}
        json.dump(original, open(self.sp, "w"))
        _run(self.sp)
        _run(self.sp, "--disable")
        self.assertEqual(self._load(), original, "enable then disable must restore the original exactly")

    def test_refuses_invalid_json(self):
        open(self.sp, "w").write("{ this is not json")
        rc, _ = _run(self.sp)
        self.assertEqual(rc, 1, "must refuse to edit an unparseable settings.json")
        self.assertEqual(open(self.sp).read(), "{ this is not json", "must not overwrite it")

    def test_dry_run_writes_nothing(self):
        _run(self.sp, "--dry-run")
        self.assertFalse(os.path.exists(self.sp), "--dry-run must not create the file")


if __name__ == "__main__":
    unittest.main(verbosity=2)
