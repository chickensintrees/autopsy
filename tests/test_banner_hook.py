"""
Fixture test for the banner-relay Stop hook's pure core.

The hook exists because prose could not enforce "paste the banner." This test exists
because the hook is now the enforcement, and an enforcement that doesn't fire on the
exact failure it was built for is theatre. The three cases below are: the agent did
paste it (allow), the agent narrated instead of pasting (BLOCK — the real bug), and
autopsy never ran (allow — the silent common case that must stay silent).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

from check_banner_relay import evaluate

# The actual ASCII art, as it sits between the markers. The agent is told to paste
# THIS block — all of it — into its reply.
FULL_ART = (
    "    _     _   _  _____   ___   ____   ____  __   __\n"
    "   / \\   | | | ||_   _| / _ \\ |  _ \\ / ___| \\ \\ / /\n"
    "  / _ \\  | | | |  | |  | | | || |_) |\\___ \\  \\ V /\n"
    " / ___ \\ | |_| |  | |  | |_| ||  __/  ___) |  | |\n"
    "/_/   \\_\\ \\___/   |_|   \\___/ |_|    |____/   |_|\n"
    "\n"
    " | (o) REC    TAPE 001    EXAMINER ON DUTY             |"
)

# The stderr run.py emits: relay open signal, BEGIN marker, the art, END marker.
BANNER_STDERR = (
    ">>> AGENT: the block below is the cold open. A banner sitting in this tool\n"
    ">>> ---------- BANNER BEGIN ----------\n"
    "\n"
    f"{FULL_ART}\n"
    ">>> ---------- BANNER END ----------"
)


def _user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _assistant(text):
    return {"type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def _ran_autopsy():
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "Bash",
         "input": {"command": "python scripts/autopsy/run.py --days 7"}}]}}


def _banner_result():
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "content": BANNER_STDERR}]}}


class TestBannerHook(unittest.TestCase):
    def test_blocks_when_agent_narrated_instead_of_pasting(self):
        """The bug this hook was built for: banner printed, agent wrote *about* it."""
        records = [
            _user("run autopsy"),
            _ran_autopsy(),
            _banner_result(),
            _assistant("Banner delivered above. Here are the findings: 3 boundaries..."),
        ]
        v = evaluate(records)
        self.assertTrue(v["autopsy_ran"])
        self.assertFalse(v["relayed"])
        self.assertFalse(v["ok"], "hook must BLOCK when the art is missing from the reply")

    def test_allows_when_art_is_in_the_reply(self):
        """Agent pasted the actual art. Nothing to enforce."""
        reply = "Here is the cold open:\n\n" + FULL_ART + "\n\nNow, the findings."
        records = [
            _user("run autopsy"),
            _ran_autopsy(),
            _banner_result(),
            _assistant(reply),
        ]
        v = evaluate(records)
        self.assertTrue(v["autopsy_ran"])
        self.assertTrue(v["relayed"])
        self.assertTrue(v["ok"])

    def test_silent_when_autopsy_did_not_run(self):
        """Every non-autopsy Stop. Must be a no-op, or the hook becomes a nuisance on
        every session in the machine."""
        records = [
            _user("what's the weather"),
            _assistant("I can't check the weather from here."),
        ]
        v = evaluate(records)
        self.assertFalse(v["autopsy_ran"])
        self.assertTrue(v["ok"])

    def test_uses_last_message_when_transcript_lags(self):
        """The transcript is written async: the banner tool result is on disk but the
        final assistant message is not yet. The payload's last_assistant_message is the
        source of truth for the reply. Art present there → allow."""
        records = [_user("run autopsy"), _ran_autopsy(), _banner_result()]  # no assistant record yet
        v = evaluate(records, last_assistant_message="Cold open:\n" + FULL_ART + "\nfindings...")
        self.assertTrue(v["autopsy_ran"])
        self.assertTrue(v["ok"])

    def test_blocks_on_narrated_last_message_when_transcript_lags(self):
        """Same lag, but the final message narrates instead of pasting. Block."""
        records = [_user("run autopsy"), _ran_autopsy(), _banner_result()]
        v = evaluate(records, last_assistant_message="Banner shown above. Findings: ...")
        self.assertTrue(v["autopsy_ran"])
        self.assertFalse(v["ok"])

    def test_only_the_current_turn_counts(self):
        """A banner relayed in an EARLIER turn must not excuse a miss in THIS one."""
        records = [
            _user("run autopsy"),
            _ran_autopsy(),
            _banner_result(),
            _assistant(FULL_ART),          # relayed correctly last turn
            _user("run it again"),         # new turn starts here
            _ran_autopsy(),
            _banner_result(),
            _assistant("Findings only, forgot the banner this time."),
        ]
        v = evaluate(records)
        self.assertTrue(v["autopsy_ran"])
        self.assertFalse(v["ok"], "must judge only the latest turn")


if __name__ == "__main__":
    unittest.main(verbosity=2)
