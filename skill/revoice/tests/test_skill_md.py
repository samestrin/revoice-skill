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


def skill_step(n: int) -> str:
    match = re.search(rf"^## Step {n}:.*?(?=^## |\Z)", TEXT, re.M | re.S)
    if not match:
        raise AssertionError(f"SKILL.md has no step {n}")
    return match.group(0)


USER_VOICES = "~/.config/revoice/voices/"


class VoicesLocationTest(unittest.TestCase):
    """User voices live in ~/.config/revoice/voices/, which a plugin update never
    touches; only example.md ships inside the skill."""

    def test_paths_name_the_user_voices_dir(self):
        self.assertRegex(TEXT, r"(?m)^- Voices: `~/\.config/revoice/voices/<slug>\.md`")
        self.assertRegex(TEXT, r"(?m)^- Audience overlays: `~/\.config/revoice/voices/<slug>-<audience>\.md`")

    def test_voice_is_read_from_user_dir_then_from_the_skill(self):
        step = skill_step(3)
        self.assertIn(f"`{USER_VOICES}<voice>.md`", step)
        self.assertRegex(step, r"If it does not exist, read `[^`]*assets/<voice>\.md`")
        self.assertRegex(step, r"`[^`]*assets/<voice>-<audience>\.md`")
        self.assertNotRegex(step, r"Read `assets/<voice>\.md`\. If it does not exist, list")

    def test_example_voice_still_resolves_from_the_skill(self):
        self.assertTrue((SKILL / "assets" / "example.md").is_file())
        self.assertRegex(skill_step(3), r"example")

    def test_sync_and_description_point_at_user_dir(self):
        self.assertNotIn("into the skill's assets", TEXT)
        self.assertIn(USER_VOICES, skill_step(6))

    def test_build_saves_the_voice_to_the_user_dir(self):
        phase = build_phase(6)
        self.assertIn(f"`{USER_VOICES}<slug>.md`", phase)
        self.assertNotIn("SKILL/assets/", BUILD)
        self.assertNotIn("skills folder", phase)

    def test_build_overlay_tip_points_at_user_dir(self):
        self.assertIn(f"`{USER_VOICES}<slug>-<audience>.md`", build_phase(8))
        self.assertNotRegex(BUILD, r"(?<![/\w])assets/")

    def test_example_config_points_at_user_dir(self):
        cfg = (SKILL / "config.example.yaml").read_text(encoding="utf-8")
        self.assertNotIn("assets/", cfg)
        self.assertIn(USER_VOICES, cfg)


SKILL_DIR = "${CLAUDE_SKILL_DIR}"

# Any spelling of a fixed install folder: ~/.claude/skills, $HOME/.claude/skills,
# %USERPROFILE%\.claude\skills, or a plugin cache path.
HARD_CODED = re.compile(r"\.claude[/\\](skills|plugins)\b")


def shipped_text_files():
    """Every text file the skill ships, except its own tests."""
    for path in sorted(SKILL.rglob("*")):
        if path.is_file() and "tests" not in path.relative_to(SKILL).parts and path.suffix in {".md", ".py", ".yaml"}:
            yield path


def frontmatter() -> str:
    match = re.match(r"---\n(.*?)\n---\n", TEXT, re.S)
    if not match:
        raise AssertionError("SKILL.md has no frontmatter")
    return match.group(1)


def allowed_tools() -> list[str]:
    match = re.search(r"(?m)^allowed-tools: (.*)$", frontmatter())
    if not match:
        raise AssertionError("SKILL.md has no allowed-tools")
    return [tool.strip() for tool in match.group(1).split(", ")]


class InstallPathTest(unittest.TestCase):
    """The skill runs from a copied folder or from a plugin, so it names its own
    folder with ${CLAUDE_SKILL_DIR}, never a fixed path."""

    def test_no_hard_coded_install_path(self):
        files = list(shipped_text_files())
        self.assertIn(SKILL / "SKILL.md", files)
        self.assertIn(SKILL / "build.md", files)
        for path in files:
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                with self.subTest(file=path.name, line=n):
                    self.assertNotRegex(line, HARD_CODED)

    def test_skill_dir_names_its_own_folder(self):
        self.assertRegex(TEXT, rf"(?m)^- Skill dir: `{re.escape(SKILL_DIR)}/`")
        self.assertIn(f"`{SKILL_DIR}/assets/`", TEXT)
        self.assertIn(f"read `{SKILL_DIR}/build.md`", TEXT)
        self.assertIn(f"`{SKILL_DIR}/assets/<voice>.md`", skill_step(3))
        self.assertIn(f"`{SKILL_DIR}/assets/<voice>-<audience>.md`", skill_step(3))
        # Quoted so a skill path with spaces stays one argument.
        self.assertIn(f'`python3 "{SKILL_DIR}/sync.py"`', skill_step(6))

    def test_allowed_tools_use_skill_dir(self):
        tools = allowed_tools()
        self.assertIn(f"Bash(python3 {SKILL_DIR}/sync.py:*)", tools)
        self.assertIn(f"Bash(python {SKILL_DIR}/sync.py:*)", tools)
        # The generic python patterns already cover sync.py.
        self.assertNotIn("sync.py", ", ".join(tools))
        self.assertIn("Bash(python:*)", tools)
        self.assertIn("Bash(python3:*)", tools)

    def test_no_fallback_path(self):
        # ${CLAUDE_SKILL_DIR} is set in both installs; a second path would only drift.
        self.assertNotIn("CLAUDE_PLUGIN_ROOT", TEXT)
        self.assertNotIn("CLAUDE_PLUGIN_ROOT", BUILD)
        self.assertRegex(TEXT, rf"(?m)^- Skill dir: `{re.escape(SKILL_DIR)}/`$")

    def test_build_md_does_not_rely_on_expansion(self):
        # build.md is read with the Read tool, not loaded as the skill, so
        # Claude Code does not expand variables in it.
        self.assertNotIn("${", BUILD)
        self.assertRegex(BUILD, r"`SKILL` is this skill's folder \(the Skill dir in `SKILL\.md`")


class CommandNameTest(unittest.TestCase):
    def test_name_field_keeps_bare_revoice_command(self):
        # A plugin skill answers to its bare name only when SKILL.md has a
        # `name:` field; without it only /revoice:revoice works.
        self.assertRegex(frontmatter(), r"(?m)^name: revoice$")


if __name__ == "__main__":
    unittest.main()
