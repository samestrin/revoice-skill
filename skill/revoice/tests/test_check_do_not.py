"""Both-ways tests for check/check-do-not.py (Epic 18 T2).

The before/after pair below is copied from the README's "What it looks like"
section; the voice is the real shipped assets/example.md. The generic AI
draft must fail with the three banned tells, Alex's rewrite must pass.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _load import SKILL, load, run_main

SCRIPT = SKILL / "check" / "check-do-not.py"
VOICE = SKILL / "assets" / "example.md"
mod = load(SCRIPT, "check_do_not")

# README "What it looks like": generic AI-style draft.
AI_DRAFT = (
    "Hello, I hope this email finds you well. I wanted to reach out regarding "
    "the project timeline. After careful consideration, it's worth noting that "
    "the current schedule is not robust. I would recommend that we add a "
    "buffer. Please let me know your thoughts at your earliest convenience."
)

# README "What it looks like": the same text in the example voice.
ALEX_REWRITE = (
    "Hi team,\n"
    "\n"
    "Quick note on the timeline. I think the current schedule is too tight, "
    "since one late delivery pushes everything back. Can we add a week of "
    "buffer?\n"
    "\n"
    "Happy to update the plan if that works.\n"
    "\n"
    "Thanks,\n"
    "Alex"
)

MIN_VOICE = '# T: Writing Profile\n\n## Do not\n\n- Do not use "delve".\n'

LINE = re.compile(r'^(?:BANNED "[^"]+" x\d+|OVERUSED "[^"]+" x\d+ \(max 1\))$')


class CheckDoNot(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def voice_file(self, text):
        path = self.tmp / "voice.md"
        path.write_text(text, encoding="utf-8")
        return path

    def run_check(self, rewrite, voice=VOICE):
        path = self.tmp / "rewrite.txt"
        path.write_text(rewrite, encoding="utf-8")
        return run_main(mod, "--voice", str(voice), "--rewrite", str(path))

    def run_proc(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True)

    # --help and argument errors

    def test_help_exits_zero(self):
        proc = self.run_proc("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--voice", proc.stdout)
        self.assertIn("--rewrite", proc.stdout)

    def test_missing_arguments_exit_2(self):
        self.assertEqual(self.run_proc().returncode, 2)

    def test_missing_rewrite_file_exits_2_one_stderr_line(self):
        proc = self.run_proc("--voice", str(VOICE),
                             "--rewrite", str(self.tmp / "nope.txt"))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1)

    def test_missing_voice_file_exits_2(self):
        path = self.tmp / "rewrite.txt"
        path.write_text("Hi", encoding="utf-8")
        proc = self.run_proc("--voice", str(self.tmp / "nope.md"),
                             "--rewrite", str(path))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")

    def test_voice_without_do_not_section_exits_2(self):
        voice = self.voice_file("# T: Writing Profile\n\n## Core traits\n\n- plain\n")
        path = self.tmp / "rewrite.txt"
        path.write_text("Hi", encoding="utf-8")
        proc = self.run_proc("--voice", str(voice), "--rewrite", str(path))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("NO-DO-NOT-SECTION", proc.stderr)
        self.assertEqual(proc.stdout, "")

    # The README pair against the real shipped voice

    def test_ai_draft_fails_with_the_three_banned_tells(self):
        result, out = self.run_check(AI_DRAFT)
        self.assertEqual(result, 1)
        lines = out.splitlines()
        self.assertTrue(lines)
        for line in lines:
            self.assertRegex(line, LINE)
        for tell in ('BANNED "I hope this email finds you well"',
                     'BANNED "it\'s worth noting"',
                     'BANNED "robust"'):
            self.assertTrue(any(line.startswith(tell) for line in lines),
                            f"{tell!r} not in {lines}")

    def test_alex_rewrite_passes(self):
        result, out = self.run_check(ALEX_REWRITE)
        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    # Once-per caps and their stand-ins

    def test_happy_to_twice_is_overused(self):
        result, out = self.run_check("Happy to help. Happy to walk through it.")
        self.assertEqual(result, 1)
        self.assertIn('OVERUSED "Happy to" x2 (max 1)', out.splitlines())

    def test_happy_to_once_passes(self):
        result, out = self.run_check("Happy to update the plan if that works.")
        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    def test_stand_ins_are_banned(self):
        for phrase in ("Glad to", "Pleased to", "I believe", "In my opinion"):
            with self.subTest(phrase=phrase):
                result, out = self.run_check(f"{phrase} help with the plan.")
                self.assertEqual(result, 1)
                self.assertIn(f'BANNED "{phrase}" x1', out.splitlines())

    def test_stand_in_used_twice_is_banned_not_overused(self):
        result, out = self.run_check("Glad to help. Glad to hear it.")
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ['BANNED "Glad to" x2'])

    def test_once_per_piece_marker_caps_too(self):
        voice = self.voice_file(
            '# T: Writing Profile\n\n## Word choice\n\n'
            '- "Quick note": once per piece at most.\n\n'
            '## Do not\n\n- Do not use "delve".\n')
        result, out = self.run_check("Quick note on A. Quick note on B.", voice)
        self.assertEqual(result, 1)
        self.assertIn('OVERUSED "Quick note" x2 (max 1)', out.splitlines())

    def test_only_first_quoted_phrase_is_capped_instead_marker(self):
        voice = self.voice_file(
            '# T: Writing Profile\n\n## Word choice\n\n'
            '- "I think": once per email at most. Prefer "My take" instead '
            'of "I believe".\n\n## Do not\n\n- Do not use "delve".\n')
        result, out = self.run_check(
            "My take is yes. My take is no. I believe so.", voice)
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ['BANNED "I believe" x1'])

    def test_once_per_bullet_without_a_quote_caps_nothing(self):
        voice = self.voice_file(
            '# T: Writing Profile\n\n## Word choice\n\n'
            '- Plain words, once per email at most.\n\n'
            '## Do not\n\n- Do not use "delve".\n')
        result, out = self.run_check("Plain words. Plain words again.", voice)
        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    def test_bullet_without_once_marker_caps_nothing(self):
        voice = self.voice_file(
            '# T: Writing Profile\n\n## Word choice\n\n'
            '- "Plain words" reads well.\n\n'
            '## Do not\n\n- Do not use "delve".\n')
        result, out = self.run_check("Plain words here. Plain words again.", voice)
        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    def test_marker_line_that_is_not_a_bullet_caps_nothing(self):
        voice = self.voice_file(
            '# T: Writing Profile\n\n## Word choice\n\n'
            '"Plain words": once per email at most.\n\n'
            '## Do not\n\n- Do not use "delve".\n')
        result, out = self.run_check("Plain words here. Plain words again.", voice)
        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    def test_capped_bullet_without_standin_marker_bans_nothing_extra(self):
        voice = self.voice_file(
            '# T: Writing Profile\n\n## Word choice\n\n'
            '- "I think": once per email at most. "My take" is warmer.\n\n'
            '## Do not\n\n- Do not use "delve".\n')
        result, out = self.run_check("My take is yes. My take is no.", voice)
        self.assertEqual(result, 0)
        self.assertEqual(out, "")
        # The cap itself still applies without a stand-in marker.
        result, out = self.run_check("I think so. I think not.", voice)
        self.assertEqual(result, 1)
        self.assertEqual(out.splitlines(), ['OVERUSED "I think" x2 (max 1)'])

    def test_binary_rewrite_file_exits_2(self):
        voice_ok = self.voice_file(MIN_VOICE)
        path = self.tmp / "rewrite.txt"
        path.write_bytes(b"\xff\xfe\x00binary")
        proc = self.run_proc("--voice", str(voice_ok), "--rewrite", str(path))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1)

    # Matching rules

    def test_robustness_does_not_match_robust(self):
        result, out = self.run_check("The robustness of the plan is fine.")
        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    def test_delved_does_not_match_delve(self):
        result, out = self.run_check("We delved into the data.")
        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    def test_curly_apostrophe_still_matches(self):
        result, out = self.run_check("Well, it\u2019s worth noting the delay.")
        self.assertEqual(result, 1)
        self.assertIn('BANNED "it\'s worth noting" x1', out.splitlines())

    def test_match_is_case_insensitive(self):
        result, out = self.run_check("We DELVE deep. It's Worth Noting.")
        self.assertEqual(result, 1)
        lines = out.splitlines()
        self.assertIn('BANNED "delve" x1', lines)
        self.assertIn('BANNED "it\'s worth noting" x1', lines)

    def test_banned_phrase_counted(self):
        result, out = self.run_check("Let us delve. We must delve.")
        self.assertEqual(result, 1)
        self.assertIn('BANNED "delve" x2', out.splitlines())

    def test_curly_double_quotes_in_voice_are_read(self):
        voice = self.voice_file(
            "# T: Writing Profile\n\n## Do not\n\n- Do not use \u201cdelve\u201d.\n")
        result, out = self.run_check("Let us delve.", voice)
        self.assertEqual(result, 1)
        self.assertIn('BANNED "delve" x1', out.splitlines())

    def test_do_not_section_stops_at_next_heading(self):
        voice = self.voice_file(
            '# T: Writing Profile\n\n## Do not\n\n- Do not use "delve".\n\n'
            '## Short examples\n\n- Offer: "seamless".\n')
        result, out = self.run_check("The help is seamless.", voice)
        self.assertEqual(result, 0)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()