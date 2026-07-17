"""
The plugin manifests are the install contract. If they're malformed, or point at a
file that moved, `/plugin install` fails for every colleague and the failure is
invisible from inside this repo — nobody runs the TUI install in CI. So: assert the
manifests are valid JSON, carry the required fields, and reference files that exist.
"""

import json
import os
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


class TestPluginManifests(unittest.TestCase):
    def test_plugin_json_valid_and_named(self):
        m = _load(".claude-plugin/plugin.json")
        self.assertEqual(m["name"], "autopsy", "plugin name must be 'autopsy' so the skill is /autopsy")

    def test_marketplace_lists_the_plugin(self):
        m = _load(".claude-plugin/marketplace.json")
        self.assertIn("owner", m)
        self.assertIn("name", m["owner"])
        names = [p["name"] for p in m["plugins"]]
        self.assertIn("autopsy", names)

    def test_hooks_reference_existing_script(self):
        h = _load("hooks/hooks.json")
        commands = [hook["command"]
                    for group in h["hooks"]["Stop"]
                    for hook in group["hooks"]]
        self.assertTrue(commands, "expected at least one Stop hook command")
        # The command references check_banner_relay.py under the plugin root; the file
        # must exist at the path the command names.
        self.assertTrue(any("check_banner_relay.py" in c for c in commands))
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "hooks", "check_banner_relay.py")))

    def test_skill_is_where_the_plugin_expects_it(self):
        # Plugins discover skills at skills/<name>/SKILL.md.
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "skills", "autopsy", "SKILL.md")))

    def test_scripts_the_skill_calls_exist(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "scripts", "autopsy", "run.py")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
