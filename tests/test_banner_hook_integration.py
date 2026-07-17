"""
Integration test for the banner-relay hook's stdin/exit wrapper.

`test_banner_hook.py` covers the pure `evaluate`. This covers `main()` — the part
that reads the Stop payload from stdin, reads the transcript off disk, and emits the
block decision. That wrapper is where a real hook lives or dies, and unit-testing the
pure core does not exercise it. (This was found the hard way: the pure logic was
correct while a smoke test reported all-silent — the fault was in payload plumbing,
not the verdict. So: test the plumbing.)
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "check_banner_relay.py")

ART = "\n".join([
    " _   _",
    "|A| |U|",
    "/_/   \\_\\ \\___/   |_|   \\___/ |_|    |____/   |_|",
    " | (o) REC EXAMINER ON DUTY |",
])
STDERR = (">>> AGENT: the block below is the cold open\n"
          ">>> ---------- BANNER BEGIN ----------\n\n" + ART +
          "\n>>> ---------- BANNER END ----------")


def _transcript(path, with_banner=True):
    recs = [{"type": "user", "message": {"role": "user", "content": "run autopsy"}}]
    if with_banner:
        recs += [
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "run.py"}}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "content": STDERR}]}},
        ]
    else:
        recs.append({"type": "assistant",
                     "message": {"role": "assistant", "content": [{"type": "text", "text": "hi"}]}})
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in recs) + "\n")


def _run(payload):
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


class TestBannerHookIntegration(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.tp = os.path.join(self.dir, "t.jsonl")

    def test_blocks_narrated_reply(self):
        _transcript(self.tp)
        rc, out = _run({"transcript_path": self.tp, "stop_hook_active": False,
                        "last_assistant_message": "Banner shown above. Findings follow."})
        self.assertEqual(rc, 0)
        self.assertTrue(out, "expected a block decision on stdout")
        self.assertEqual(json.loads(out).get("decision"), "block")

    def test_allows_pasted_reply(self):
        _transcript(self.tp)
        rc, out = _run({"transcript_path": self.tp, "stop_hook_active": False,
                        "last_assistant_message": "here:\n" + ART + "\nfindings"})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "", "a pasted banner must not block")

    def test_loop_guard_releases(self):
        _transcript(self.tp)
        rc, out = _run({"transcript_path": self.tp, "stop_hook_active": True,
                        "last_assistant_message": "narrated, no art"})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "", "must not block twice on a forced continuation")

    def test_silent_without_autopsy(self):
        _transcript(self.tp, with_banner=False)
        rc, out = _run({"transcript_path": self.tp, "stop_hook_active": False,
                        "last_assistant_message": "hi"})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_malformed_stdin_allows_stop(self):
        rc = subprocess.run([sys.executable, HOOK], input="not json",
                            capture_output=True, text=True).returncode
        self.assertEqual(rc, 0, "a crash must never wedge the session")


if __name__ == "__main__":
    unittest.main(verbosity=2)
