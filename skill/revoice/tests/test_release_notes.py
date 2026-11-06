"""Checks on .github/scripts/release-notes.py, which the release workflow runs.

The workflow passes the pushed tag's version (`v0.2.0` -> `0.2.0`); the script
fails unless plugin.json, SKILL.md and the newest CHANGELOG heading all name
that version, then prints the version's CHANGELOG section as the release notes.
The script runs as a subprocess here, the way the workflow calls it.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _load import SKILL

ROOT = SKILL.parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "release-notes.py"

SECTION_0_1_0 = """### Added

- `/revoice` rewrites text in a voice profile.
- MIT `LICENSE`.

### Fixed

- A line under a second heading, so the section is more than one block."""

SAMPLE_CHANGELOG = f"""# Changelog

All notable changes to this project are documented here.

## [Unreleased]

- Not released yet.

## [0.2.0] - 2026-11-03

### Added

- Something in 0.2.0.

## [0.1.0] - 2026-10-26

{SECTION_0_1_0}

## [0.0.1] - 2026-10-01

- The first one.
"""

SKILL_MD = """---
name: revoice
description: test
metadata:
  version: "{version}"
---

# revoice
"""


def make_repo(folder: Path, changelog: str, plugin: str, skill: str) -> Path:
    (folder / ".claude-plugin").mkdir()
    (folder / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "revoice", "version": plugin}), encoding="utf-8")
    (folder / "skill" / "revoice").mkdir(parents=True)
    (folder / "skill" / "revoice" / "SKILL.md").write_text(
        SKILL_MD.format(version=skill), encoding="utf-8")
    (folder / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return folder


def run(*args: str):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, timeout=60)


class NotesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.changelog = self.dir / "CHANGELOG.md"
        self.changelog.write_text(SAMPLE_CHANGELOG, encoding="utf-8")

    def test_prints_exactly_the_0_1_0_section(self):
        result = run("0.1.0", "--changelog", str(self.changelog))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, SECTION_0_1_0 + "\n")

    def test_last_section_stops_at_link_references(self):
        text = SAMPLE_CHANGELOG + "\n[0.0.1]: https://example.com/v0.0.1\n"
        self.changelog.write_text(text, encoding="utf-8")
        result = run("0.0.1", "--changelog", str(self.changelog))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "- The first one.\n")

    def test_fails_on_a_version_with_no_heading(self):
        result = run("0.3.0", "--changelog", str(self.changelog))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("no `## [0.3.0]` heading", result.stderr)

    def test_a_prefix_of_a_version_is_not_its_heading(self):
        # `## [0.1.0]` must not answer for 0.1 or 0.1.0.1.
        for version in ("0.1", "0.1.0.1"):
            with self.subTest(version=version):
                self.assertNotEqual(run(version, "--changelog", str(self.changelog)).returncode, 0)

    def test_fails_on_an_empty_section(self):
        self.changelog.write_text("## [0.1.0] - 2026-10-26\n\n## [0.0.1]\n\n- x\n", encoding="utf-8")
        result = run("0.1.0", "--changelog", str(self.changelog))
        self.assertEqual(result.returncode, 1)
        self.assertIn("empty", result.stderr)

    def test_fails_on_a_tag_that_is_not_x_y_z(self):
        # The workflow strips the `v`; anything left that is not x.y.z is a bad tag.
        for version in ("v0.1.0", "0.1.0-rc1", ""):
            with self.subTest(version=version):
                result = run(version, "--changelog", str(self.changelog))
                self.assertEqual(result.returncode, 1)
                self.assertIn("x.y.z", result.stderr)


class CheckTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def repo(self, plugin="0.2.0", skill="0.2.0", changelog=SAMPLE_CHANGELOG):
        folder = Path(tempfile.mkdtemp(dir=self.dir))
        return str(make_repo(folder, changelog, plugin, skill))

    def test_versions_agree(self):
        result = run("0.2.0", "--check", "--root", self.repo())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "### Added\n\n- Something in 0.2.0.\n")

    def test_each_disagreement_fails_and_prints_no_notes(self):
        cases = {
            "plugin.json": dict(plugin="0.1.0"),
            "SKILL.md": dict(skill="0.1.0"),
            "CHANGELOG.md": dict(changelog=SAMPLE_CHANGELOG.replace("## [0.2.0] - 2026-11-03\n\n### Added\n\n- Something in 0.2.0.\n\n", "")),
        }
        for name, kwargs in cases.items():
            with self.subTest(name=name):
                result = run("0.2.0", "--check", "--root", self.repo(**kwargs))
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn(name, result.stderr)

    def test_an_older_released_version_fails_the_check(self):
        # Tagging v0.1.0 again when 0.2.0 is the newest released heading.
        result = run("0.1.0", "--check", "--root", self.repo(plugin="0.1.0", skill="0.1.0"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("CHANGELOG.md", result.stderr)

    def test_this_repo_agrees_with_its_own_version(self):
        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        result = run(version, "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
