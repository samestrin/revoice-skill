"""Tests for check/check-format.py (epic 18 T3).

Both ways: a paragraph hard-wrapped at 60 columns is flagged with one
HARD-WRAP line per wrapped continuation; the same text as one line per
paragraph, a sign-off block, lists, tables and code fences all pass.
All texts are fictional.
"""
import contextlib
import io
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from _load import SKILL, load, run_main

SCRIPT = SKILL / "check" / "check-format.py"
cf = load(SCRIPT, "check_format")

# One fictional paragraph; every word after the first is lowercase, so
# wrapping it at 60 columns gives continuation lines that start lowercase.
PARA = (
    "The launch moved to next week because the last two builds had problems "
    "that nobody expected and the team needs a few quiet days to recover "
    "before we try again."
)
WRAPPED = textwrap.wrap(PARA, width=60)

SIGNOFF = (
    "Hi team,\n"
    "\n"
    "The plan is ready and the numbers are in the sheet.\n"
    "\n"
    "Thanks,\n"
    "Alex\n"
)


class CheckFormatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "rewrite.txt"

    def run_check(self, text):
        """Write text, run main(--rewrite file); return (exit code, stdout)."""
        self.file.write_text(text, encoding="utf-8")
        return run_main(cf, "--rewrite", str(self.file))

    def test_wrapped_at_60_columns_is_flagged(self):
        self.assertGreaterEqual(len(WRAPPED), 3)
        for line in WRAPPED[1:]:
            self.assertTrue(line[0].islower(), line)
        code, out = self.run_check("\n".join(WRAPPED) + "\n")
        self.assertEqual(code, 1)
        expected = "".join(f"HARD-WRAP line {n}\n" for n in range(2, len(WRAPPED) + 1))
        self.assertEqual(out, expected)

    def test_one_line_per_paragraph_passes(self):
        code, out = self.run_check(PARA + "\n\n" + PARA + "\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_signoff_block_passes(self):
        code, out = self.run_check(SIGNOFF)
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_bulleted_list_passes(self):
        text = (
            "Things to buy:\n"
            "- eggs and flour\n"
            "  and sugar for the cake\n"
            "- milk\n"
            "* butter\n"
            "+ salt\n"
            "1. first step\n"
            "2. second step\n"
        )
        code, out = self.run_check(text)
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_table_passes(self):
        text = (
            "Item | Qty | Price\n"
            "apple | 3 | 1.20\n"
            "pear | 2 | 0.90\n"
            "\n"
            "| Item | Qty |\n"
            "| --- | --- |\n"
            "| plum | 9 |\n"
        )
        code, out = self.run_check(text)
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_wrapped_paragraph_in_code_fence_passes(self):
        code, out = self.run_check("```\n" + "\n".join(WRAPPED) + "\n```\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_tilde_fence_passes(self):
        code, out = self.run_check("~~~\n" + "\n".join(WRAPPED) + "\n~~~\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_wrap_after_closed_fence_is_still_flagged(self):
        text = "```\ncode\n```\n\n" + "\n".join(WRAPPED) + "\n"
        code, out = self.run_check(text)
        self.assertEqual(code, 1)
        offset = 4  # fence, code, fence, blank line
        expected = "".join(
            f"HARD-WRAP line {offset + n}\n" for n in range(2, len(WRAPPED) + 1))
        self.assertEqual(out, expected)

    def test_quotes_and_headings_pass(self):
        text = (
            "# A heading\n"
            "lowercase line right after a heading\n"
            "\n"
            "> quoted text that goes on\n"
            "> and continues in lowercase\n"
        )
        code, out = self.run_check(text)
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_capital_continuation_is_not_flagged(self):
        code, out = self.run_check("We met on Monday.\nAlex took the notes.\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_blank_line_between_paragraphs_is_not_a_wrap(self):
        code, out = self.run_check("and one paragraph ends here\n\nand another begins here\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_two_wrapped_paragraphs_report_absolute_line_numbers(self):
        text = "\n".join(WRAPPED) + "\n\n" + "\n".join(WRAPPED) + "\n"
        code, out = self.run_check(text)
        self.assertEqual(code, 1)
        n = len(WRAPPED)
        expected = "".join(f"HARD-WRAP line {i}\n" for i in range(2, n + 1))
        expected += "".join(f"HARD-WRAP line {n + 2 + i}\n" for i in range(2, n + 1))
        self.assertEqual(out, expected)

    def test_empty_file_passes(self):
        code, out = self.run_check("")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_missing_file_exits_2_with_one_stderr_line(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, out = run_main(cf, "--rewrite", str(Path(self.tmp.name) / "nope.txt"))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.getvalue().splitlines()), 1)

    def test_missing_flag_exits_2(self):
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
            run_main(cf)
        self.assertEqual(cm.exception.code, 2)

    def test_help_exits_0(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--rewrite", proc.stdout)


if __name__ == "__main__":
    unittest.main()
