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

    def test_build_mode_does_not_need_config(self):
        self.assertIn("`--build` itself does not need one", missing_config_rule())

    def test_sb_refs_still_stop_without_config(self):
        rule = missing_config_rule()
        self.assertRegex(rule, r"`sb:` ref.*stop")

    def test_example_voice_ships_with_the_skill(self):
        self.assertTrue((SKILL / "assets" / "example.md").is_file())


BUILD = (SKILL / "build.md").read_text(encoding="utf-8")


def build_phase(n: int) -> str:
    match = re.search(rf"^## Phase {n}:.*?(?=^## Phase |\Z)", BUILD, re.M | re.S)
    if not match:
        raise AssertionError(f"build.md has no phase {n}")
    return match.group(0)


class BuildReviewTest(unittest.TestCase):
    def test_no_remote_review_or_fallback(self):
        self.assertNotIn("/analyze/sample-review", BUILD)
        self.assertNotRegex(BUILD, r"(?i)fallback")
        self.assertNotRegex(BUILD, r"(?i)claude'?s model provider")
        self.assertNotRegex(BUILD, r"(?i)API review")

    def test_review_is_local_with_author(self):
        phase = build_phase(4)
        self.assertIn('review-samples.py --author "<Name>"', phase)
        self.assertNotRegex(phase, r"(?i)posts the samples|HTTP 40|timeout")
        self.assertRegex(phase, r"KEEP vs DROP")

    def test_phase_6_sets_aside_foreign_samples(self):
        phase = build_phase(6)
        self.assertRegex(phase, r"set aside any kept sample that clearly is not the author's own voice or language")
        self.assertRegex(phase, r"Say so in your report")


if __name__ == "__main__":
    unittest.main()
