"""Checks on SKILL.md, the prompt text Claude follows for /revoice.

The prompt cannot be run in a unit test, so these pin the rules a fresh
install depends on: `/revoice --voice=example <text>` must rewrite without
~/.config/revoice/config.yaml.
"""
import re
import unittest

from _load import SKILL

TEXT = (SKILL / "SKILL.md").read_text(encoding="utf-8")


def missing_config_rule() -> str:
    """The paragraph (with its bullets) that says what to do without a config."""
    match = re.search(r"^If the config file is missing.*?(?=\n\n)", TEXT, re.M | re.S)
    if not match:
        raise AssertionError("SKILL.md has no 'If the config file is missing' rule")
    return match.group(0)


class MissingConfigTest(unittest.TestCase):
    def test_no_unconditional_stop_on_missing_config(self):
        self.assertNotRegex(TEXT, r"If the config file is missing, stop")

    def test_voice_flag_runs_without_config(self):
        rule = missing_config_rule()
        self.assertRegex(rule, r"`--voice` is given.*run without it")
        self.assertIn("no default audience", rule)
        self.assertIn("current working directory", rule)

    def test_no_voice_flag_still_stops(self):
        rule = missing_config_rule()
        self.assertRegex(rule, r"no `--voice`.*stop and tell the user to create it from `config.example.yaml`")
        self.assertIn("Do not guess defaults", rule)

    def test_sb_refs_still_stop_without_config(self):
        rule = missing_config_rule()
        self.assertRegex(rule, r"`sb:` ref.*stop")

    def test_example_voice_ships_with_the_skill(self):
        self.assertTrue((SKILL / "assets" / "example.md").is_file())


if __name__ == "__main__":
    unittest.main()
