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

    def test_phase_4_stops_for_the_user_to_approve_the_samples(self):
        phase = build_phase(4)
        stop = phase[phase.index("### Stop: the user approves the samples"):]
        self.assertIn("`WORK/samples/`", stop)
        self.assertIn("`verdict`", stop)
        self.assertIn("DROP", stop)
        self.assertIn("`samples/index.csv`", stop)
        self.assertRegex(stop, r"explicit go")
        self.assertRegex(stop, r"Do not read the samples yourself")
        self.assertRegex(stop, r"fewer than 15")
        self.assertRegex(BUILD, r"(?s)### Stop: the user approves.*## Phase 5:")

    def test_phase_6_sets_aside_foreign_samples(self):
        phase = build_phase(6)
        self.assertRegex(phase, r"set aside any kept sample that clearly is not the author's own voice or language")
        self.assertRegex(phase, r"Say so in your report")

    def test_phase_0_checks_the_key_and_balance(self):
        phase = build_phase(0)
        self.assertIn("test -s ~/.config/revoice/api-key", phase)
        self.assertIn("build-profile.py --check", phase)
        self.assertRegex(phase, r"pbpaste")
        self.assertNotIn("test -s", build_phase(3))

    def test_phase_3_reports_cost_and_balance(self):
        phase = build_phase(3)
        self.assertRegex(phase, r"Check the cost")
        # Free: phase 0's --check already spent the one credit (Epic 14 T7).
        self.assertIn("--estimate --balance <balance> --samples samples --reference reference", phase)
        self.assertNotIn("--check", phase)
        self.assertRegex(phase, r"balance is short")

    def test_phase_5_names_each_failure(self):
        phase = build_phase(5)
        for code in ("401", "402", "429", "cannot reach the API"):
            self.assertIn(code, phase)
        self.assertIn("phase 0", phase)

    def test_phase_1_reference_set_defaults_to_no(self):
        phase = build_phase(1)
        self.assertRegex(phase, r"Reference set:\*\* default no")
        self.assertNotRegex(phase, r"Reference set:\*\* default yes")
        self.assertIn("148", build_phase(2))
        self.assertNotIn("200 samples", BUILD)


def subsection(phase: str, title: str) -> str:
    """The `### <title>` subsection of a phase, up to the next heading."""
    match = re.search(rf"^### {re.escape(title)}\n.*?(?=^##|\Z)", phase, re.M | re.S)
    if not match:
        raise AssertionError(f"phase has no '### {title}' subsection")
    return match.group(0)


def without_email(phase: str) -> str:
    """A phase as a writing or brand build reads it: every `### Email` part removed."""
    return re.sub(r"^### Email\n.*?(?=^##|\Z)", "", phase, flags=re.M | re.S)


# The word mbox, but not the helper's file name, which phase 0 checks for in every mode.
MBOX = re.compile(r"(?i)\bmbox\b(?!-filter-before\.py)")


class BuildSourcesTest(unittest.TestCase):
    """--build takes an email export, a folder of the user's writing or a folder
    of brand documents (Epic 17 T5)."""

    def test_phase_1_first_question_is_the_source(self):
        phase = build_phase(1)
        first = re.search(r"(?m)^1\. .*$", phase).group(0)
        self.assertIn("**Source:**", first)
        for source in ("an email export", "a folder of your own writing", "a folder of brand documents"):
            self.assertIn(source, first)
        for mode in ("`email`", "`writing`", "`brand`"):
            self.assertIn(mode, first)
        self.assertLess(phase.index(first), phase.index("### Email"))

    def test_phase_1_asks_documents_only_what_they_need(self):
        docs = subsection(build_phase(1), "Writing and brand")
        self.assertIn("`--urls`", docs)
        self.assertRegex(docs, r"brand's name")
        self.assertIn("slug", docs)
        self.assertRegex(docs, r"Cutoff date:\*\* optional")
        self.assertIn("This is my own writing, not AI-assisted.", docs)
        self.assertIn("I may send these to a third-party API and to Claude.", docs)
        self.assertNotIn("Addresses", docs)
        self.assertNotIn("Reference set", docs)

    def test_brand_path_confirms_the_user_may_send_the_documents(self):
        docs = subsection(build_phase(1), "Writing and brand")
        self.assertRegex(docs, r"brand documents are often confidential")
        self.assertRegex(docs, r"confirm they may send these documents")
        self.assertRegex(docs, r"clear yes")
        self.assertRegex(BUILD.split("## Phase 0:")[0], r"Brand documents are often confidential")

    def test_privacy_rules_cover_documents(self):
        rules = BUILD.split("## Phase 0:")[0]
        self.assertIn("**The email is private.**", rules)
        self.assertRegex(rules, r"never leaves the machine as a whole")
        self.assertRegex(rules, r"up to 148\) go to the text analysis API over HTTPS")
        self.assertRegex(rules, r"never fetch a URL yourself")

    def test_phase_2_branches_by_source(self):
        phase = build_phase(2)
        email = subsection(phase, "Email")
        docs = subsection(phase, "Writing and brand")
        self.assertIn("mbox-filter-before.py", email)
        self.assertIn("extract-samples.py", email)
        self.assertIn("extract-documents.py", docs)
        self.assertNotIn("extract-samples.py", docs)
        self.assertIn("--before <cutoff>", docs)
        self.assertRegex(docs, r"`--before` unless the user gave a cutoff date")
        self.assertIn("pdftotext", docs)

    def test_phase_4_names_the_document_modes_and_stops_at_the_floor(self):
        phase = build_phase(4)
        self.assertIn('review-samples.py --author "<Name>" --mode <mode>', phase)
        docs = subsection(phase, "Writing and brand")
        self.assertIn("`--mode writing`", docs)
        self.assertIn("`--mode brand`", docs)
        self.assertIn("`coverage:`", docs)
        self.assertRegex(docs, r"status 3")
        self.assertRegex(docs, r"Stop the build here: nothing has been uploaded")
        self.assertRegex(docs, r"10 KEEP passages from at least 3 documents")
        self.assertIn("fewer than 15", subsection(phase, "Email"))

    def test_phase_5_passes_the_source_type(self):
        phase = build_phase(5)
        self.assertIn("--source-type email", subsection(phase, "Email"))
        docs = subsection(phase, "Writing and brand")
        self.assertIn("--source-type <mode>", docs)
        self.assertNotRegex(docs.split("```")[1], r"--from|--reference")

    def test_phase_6_shapes_follow_the_source(self):
        phase = build_phase(6)
        self.assertIn("samples beat stats", phase)
        self.assertIn("the usual shape of an email", subsection(phase, "Email"))
        writing = subsection(phase, "Writing")
        self.assertIn("the usual shape of an article or post", writing)
        self.assertIn("once per piece at most", writing)
        brand = subsection(phase, "Brand")
        self.assertIn("the usual shape of a brand document", brand)
        self.assertIn("`# <Brand>: Writing Profile`", brand)
        self.assertRegex(brand, r"at least 3 different documents \(the `source` column")
        self.assertRegex(brand, r'"we" and "you"')
        self.assertRegex(brand, r"client names, prices and internal project names")
        for docs in (writing, brand):
            self.assertIn("in today's fast-paced world", docs)
            self.assertNotIn("I hope this email finds you well", docs)

    def test_phase_8_has_a_demo_per_source(self):
        phase = build_phase(8)
        for title in ("Email", "Writing", "Brand"):
            self.assertRegex(subsection(phase, title), r"(?m)^> ")

    def test_no_document_phase_mentions_mbox_or_email_limits(self):
        for n in range(9):
            with self.subTest(phase=n):
                text = without_email(build_phase(n))
                self.assertNotRegex(text, MBOX)
                self.assertNotIn("once per email", text)
                self.assertNotRegex(text, r"(?i)sent from")

    def test_the_checks_see_an_email_subsection(self):
        # The test above would pass on its own if every phase were one big Email part.
        self.assertRegex(without_email(build_phase(2)), "extract-documents.py")
        self.assertRegex(build_phase(2), MBOX)
        self.assertNotRegex(without_email(build_phase(2)), MBOX)


DESCRIPTION_LIMIT = 1024  # characters Claude allows in a skill's description


class DescriptionTest(unittest.TestCase):
    def test_build_sentence_names_the_three_sources(self):
        description = re.search(r"(?m)^description: (.*)$", frontmatter()).group(1)
        self.assertIn(
            "--build walks the user through building a voice profile from an email export (mbox), "
            "a folder of their own writing, or a folder of brand documents.", description)
        self.assertLessEqual(len(description), DESCRIPTION_LIMIT)


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
        # The generic python patterns already cover sync.py.
        self.assertNotIn("sync.py", ", ".join(tools))
        self.assertIn("Bash(python:*)", tools)
        self.assertIn("Bash(python3:*)", tools)

    def test_allowed_tools_have_no_duplicates(self):
        tools = allowed_tools()
        duplicates = sorted({tool for tool in tools if tools.count(tool) > 1})
        self.assertEqual(duplicates, [])

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


CHECK_SCRIPTS = ("check-facts.py", "check-do-not.py", "check-format.py")
CHECK_FILES_DIR = "~/.config/revoice/check"


def rewrite_check_block() -> str:
    """The 'Check the rewrite' bullet (with its sub-bullets) in Step 4."""
    match = re.search(r"^- \*\*Check the rewrite\.\*\*.*?(?=^- |\Z)", skill_step(4), re.M | re.S)
    if not match:
        raise AssertionError("SKILL.md Step 4 has no 'Check the rewrite' block")
    return match.group(0)


class RewriteCheckTest(unittest.TestCase):
    """Step 4 runs the three rewrite checks in code (Epic 18 T5), after the
    final grammar pass: fix what the lines list, run once more, and report
    leftovers or a broken check under Notes without stopping."""

    def test_step_4_names_all_three_scripts_under_the_skill_dir(self):
        block = rewrite_check_block()
        for script in CHECK_SCRIPTS:
            with self.subTest(script=script):
                self.assertIn(f'`python3 "{SKILL_DIR}/check/{script}"', block)

    def test_each_named_check_script_exists_on_disk(self):
        block = rewrite_check_block()
        named = re.findall(rf"{re.escape(SKILL_DIR)}/check/([\w.-]+)", block)
        self.assertEqual(sorted(set(named)), sorted(CHECK_SCRIPTS))
        for script in named:
            with self.subTest(script=script):
                self.assertTrue((SKILL / "check" / script).is_file())

    def test_block_comes_after_the_grammar_pass_and_before_step_5(self):
        step = skill_step(4)
        block = rewrite_check_block()
        self.assertLess(step.index("Final grammar pass"), step.index(block))
        self.assertLess(TEXT.index(block), TEXT.index("## Step 5"))

    def test_writes_the_input_and_the_plain_rewrite_overwriting(self):
        block = rewrite_check_block()
        self.assertIn(f"`mkdir -p {CHECK_FILES_DIR}`", block)
        self.assertIn(f"`{CHECK_FILES_DIR}/original.txt`", block)
        self.assertIn(f"`{CHECK_FILES_DIR}/rewrite.txt`", block)
        self.assertRegex(block, r"[Oo]verwrite")
        self.assertIn("never the filled template", block)

    def test_the_filled_template_is_not_checked(self):
        self.assertIn("filled template is not checked", rewrite_check_block())

    def test_check_flags_and_the_step_3_voice(self):
        block = rewrite_check_block()
        facts = re.search(r"check-facts\.py\"[^`]*", block).group(0)
        self.assertIn("--original", facts)
        self.assertIn("--rewrite", facts)
        do_not = re.search(r"check-do-not\.py\"[^`]*", block).group(0)
        self.assertIn("--voice", do_not)
        self.assertIn("Step 3", do_not)
        self.assertIn("--rewrite", do_not)
        fmt = re.search(r"check-format\.py\"[^`]*", block).group(0)
        self.assertIn("--rewrite", fmt)

    def test_windows_uses_python_as_step_6_says(self):
        block = rewrite_check_block()
        self.assertRegex(block, r"Windows.*`python`")
        self.assertIn("Step 6", block)

    def test_fix_only_the_listed_lines_then_run_once_more(self):
        block = rewrite_check_block()
        self.assertIn("Fix only what the lines list", block)
        self.assertRegex(block, r"restore a `MISSING` fact")
        self.assertRegex(block, r"remove an `ADDED`")
        self.assertRegex(block, r"replace a `BANNED` phrase")
        self.assertRegex(block, r"join wrapped lines")
        self.assertIn("once more", block)

    def test_leftover_lines_go_under_notes_three_bullets_max(self):
        block = rewrite_check_block()
        self.assertRegex(block, r"still listed.*\"Notes\"")
        self.assertRegex(block, r"3 bullets")

    def test_missing_script_or_exit_2_goes_under_notes_and_does_not_stop(self):
        block = rewrite_check_block()
        self.assertRegex(block, r"absent or exits 2")
        self.assertRegex(block, r"name the script and (its|the) error under \"Notes\"")
        self.assertIn("skip that check and go on", block)
        self.assertRegex(block, r"[Dd]o not stop")


if __name__ == "__main__":
    unittest.main()
