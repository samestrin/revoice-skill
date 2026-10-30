"""Checks on the Claude Code plugin manifests in .claude-plugin/.

`claude plugin validate` is not in CI, so these pin what an install from
`/plugin install revoice@revoice-skill` depends on: the required keys, the
marketplace entry pointing at this repo, the skill folder the manifest names,
and one version across plugin.json, CHANGELOG.md and SKILL.md (a plugin update
does nothing for users unless the version changes).
"""
import json
import re
import struct
import unittest

from _load import SKILL

ROOT = SKILL.parent.parent
PLUGIN_DIR = ROOT / ".claude-plugin"


def read_json(name: str) -> dict:
    return json.loads((PLUGIN_DIR / name).read_text(encoding="utf-8"))


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ICON_MIN_PX = 512
ICON_MAX_PX = 2048
ICON_MAX_BYTES = 2 * 1024 * 1024


def png_size(data: bytes) -> tuple[int, int]:
    """Width and height from the IHDR chunk of PNG bytes."""
    if data[:8] != PNG_SIGNATURE:
        raise AssertionError("icon is not a PNG (bad signature)")
    if len(data) < 24:
        raise AssertionError("icon PNG has no IHDR chunk first (file too short)")
    length, kind = struct.unpack(">I4s", data[8:16])
    if kind != b"IHDR" or length != 13:
        raise AssertionError("icon PNG has no IHDR chunk first")
    return struct.unpack(">II", data[16:24])


def check_icon(data: bytes) -> None:
    if len(data) >= ICON_MAX_BYTES:
        raise AssertionError("icon is 2 MB or larger")
    width, height = png_size(data)
    if width != height:
        raise AssertionError(f"icon is not square: {width}x{height}")
    if not ICON_MIN_PX <= width <= ICON_MAX_PX:
        raise AssertionError(f"icon side {width}px is outside 512-2048")


def newest_released_version(text: str | None = None) -> str:
    """The first `## [x.y.z]` heading in CHANGELOG.md, skipping Unreleased."""
    if text is None:
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.M)
    if not match:
        raise AssertionError("CHANGELOG.md has no released `## [x.y.z]` heading")
    return match.group(1)


def skill_md_version(text: str | None = None) -> str:
    if text is None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not front:
        raise AssertionError("SKILL.md has no frontmatter")
    # metadata: is a block of indented lines; version: is one of them.
    block = re.search(r"^metadata:\n((?:[ \t]+.*\n?)*)", front.group(1), re.M)
    match = block and re.search(r"^[ \t]+version:[ \t]*[\"']?([^\"'\n]+)", block.group(1), re.M)
    if not match:
        raise AssertionError("SKILL.md frontmatter has no metadata.version")
    return match.group(1).strip()


class PluginJsonTest(unittest.TestCase):
    def setUp(self):
        self.plugin = read_json("plugin.json")

    def test_metadata(self):
        self.assertEqual(self.plugin["name"], "revoice")
        self.assertTrue(self.plugin["description"].strip())
        self.assertTrue(self.plugin["author"]["name"].strip())
        self.assertEqual(self.plugin["license"], "MIT")
        self.assertRegex(self.plugin["homepage"], r"^https://")

    def test_skills_path_keeps_skill_folder(self):
        self.assertEqual(self.plugin["skills"], "./skill")
        self.assertTrue((ROOT / "skill" / "revoice" / "SKILL.md").is_file())

    def test_version_matches_changelog(self):
        self.assertEqual(self.plugin["version"], newest_released_version())

    def test_version_matches_skill_md(self):
        version = skill_md_version()
        # A quote left on the value would still be a mismatch, but say so.
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(self.plugin["version"], version)

    def test_icon_is_a_square_png_in_range(self):
        icon = self.plugin["icon"]
        path = ROOT / icon  # relative to the plugin root
        self.assertTrue(path.is_file(), f"{icon} does not exist")
        check_icon(path.read_bytes())


class MarketplaceJsonTest(unittest.TestCase):
    def setUp(self):
        self.market = read_json("marketplace.json")

    def test_required_keys(self):
        # The install command is revoice@revoice-skill.
        self.assertEqual(self.market["name"], "revoice-skill")
        self.assertTrue(self.market["owner"]["name"].strip())
        self.assertIsInstance(self.market["plugins"], list)

    def test_single_entry_is_this_repo(self):
        entries = self.market["plugins"]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["name"], read_json("plugin.json")["name"])
        self.assertEqual(entry["source"], "./")
        self.assertTrue(entry["description"].strip())


class HelpersTest(unittest.TestCase):
    """Each guard raises on bad input, so a broken file fails loudly."""

    def test_changelog_without_released_heading(self):
        text = "# Changelog\n\n## [Unreleased]\n\n- something\n"
        with self.assertRaisesRegex(AssertionError, "no released"):
            newest_released_version(text)

    def test_skill_md_without_frontmatter(self):
        text = "# revoice\n\nmetadata:\n  version: 1.0.0\n"
        with self.assertRaisesRegex(AssertionError, "no frontmatter"):
            skill_md_version(text)

    def test_skill_md_without_metadata_version(self):
        text = "---\nname: revoice\nmetadata:\n  author: someone\n---\n# revoice\n"
        with self.assertRaisesRegex(AssertionError, "no metadata.version"):
            skill_md_version(text)

    def test_icon_rejects_bad_files(self):
        def png(w, h):
            return PNG_SIGNATURE + struct.pack(">I4sII", 13, b"IHDR", w, h) + b"\0" * 5

        check_icon(png(512, 512))
        check_icon(png(2048, 2048))
        for data, msg in [
            (b"<svg/>" + b"\0" * 30, "not a PNG"),
            (PNG_SIGNATURE + struct.pack(">I4s", 13, b"tEXt") + b"\0" * 13, "no IHDR"),
            (PNG_SIGNATURE + b"\0" * 4, "no IHDR"),
            (png(256, 256), "outside"),
            (png(4096, 4096), "outside"),
            (png(512, 1024), "not square"),
            (png(512, 512) + b"\0" * ICON_MAX_BYTES, "2 MB"),
        ]:
            with self.assertRaisesRegex(AssertionError, msg):
                check_icon(data)


if __name__ == "__main__":
    unittest.main()
