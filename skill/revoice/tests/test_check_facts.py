"""Both-ways tests for check/check-facts.py (Epic 18 T1).

A rewrite that keeps every number, date, URL and email passes; one that
drops or invents a fact fails with one line per problem. All texts are
invented; no real person's address appears here.
"""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _load import SKILL, load, run_main

CHECK = SKILL / "check"
SCRIPT = CHECK / "check-facts.py"
cf = load(SCRIPT, "check_facts")

ORIGINAL = (
    "We grew 40% and earned $1,200 by 3 May. "
    "See https://a.example/x or email kim@a.example."
)


class CheckFactsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def run_check(self, original: str, rewrite: str):
        """Return (exit code, stdout, stderr) for one original/rewrite pair."""
        orig = self.dir / "original.txt"
        rew = self.dir / "rewrite.txt"
        orig.write_text(original, encoding="utf-8")
        rew.write_text(rewrite, encoding="utf-8")
        return self.run_paths(orig, rew)

    def run_paths(self, orig: Path, rew: Path):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, out = run_main(cf, "--original", str(orig), "--rewrite", str(rew))
        return code, out, err.getvalue()

    # -- the both-ways pair from the issue -------------------------------

    def test_rewrite_keeping_all_five_facts_exits_0(self):
        rewrite = (
            "By 3 May we earned $1,200, a growth of 40%. "
            "Details: https://a.example/x (kim@a.example)."
        )
        code, out, err = self.run_check(ORIGINAL, rewrite)
        self.assertEqual((code, out, err), (0, "", ""))

    def test_dropped_percent_and_added_number_exit_1(self):
        rewrite = (
            "We earned $1,200 by 3 May, with 15 new customers. "
            "See https://a.example/x or email kim@a.example."
        )
        code, out, err = self.run_check(ORIGINAL, rewrite)
        self.assertEqual(code, 1)
        self.assertEqual(out, "MISSING number 40%\nADDED number 15\n")
        self.assertEqual(err, "")

    def test_missing_40_percent_prints_exactly_one_line(self):
        rewrite = ORIGINAL.replace("40%", "a lot")
        code, out, _ = self.run_check(ORIGINAL, rewrite)
        self.assertEqual(code, 1)
        self.assertEqual(out, "MISSING number 40%\n")

    # -- numbers ----------------------------------------------------------

    def test_dollar_and_thousands_commas_equal_plain_number(self):
        code, out, _ = self.run_check("It cost $1,200.", "It cost 1200.")
        self.assertEqual((code, out), (0, ""))

    def test_number_word_in_rewrite_matches_digit_in_original(self):
        code, out, _ = self.run_check("2 items shipped.", "two items shipped.")
        self.assertEqual((code, out), (0, ""))

    def test_number_word_must_be_a_whole_word(self):
        code, out, _ = self.run_check("2 cats.", "twenty cats.")
        self.assertEqual(code, 1)
        self.assertEqual(out, "MISSING number 2\n")

    def test_missing_digit_without_its_word_is_reported(self):
        code, out, _ = self.run_check("2 items shipped.", "some items shipped.")
        self.assertEqual(code, 1)
        self.assertEqual(out, "MISSING number 2\n")

    def test_pronoun_one_is_never_a_fact(self):
        code, out, _ = self.run_check(
            "One of the teams shipped it.", "The teams shipped it."
        )
        self.assertEqual((code, out), (0, ""))

    def test_number_words_are_never_extracted(self):
        code, out, _ = self.run_check("twenty teams joined.", "many teams joined.")
        self.assertEqual((code, out), (0, ""))

    def test_added_number_is_reported(self):
        code, out, _ = self.run_check("We shipped it.", "We shipped 15 of them.")
        self.assertEqual(code, 1)
        self.assertEqual(out, "ADDED number 15\n")

    def test_decimal_numbers_compare_equal(self):
        code, out, _ = self.run_check("It grew 3.5 times.", "Growth: 3.5 times.")
        self.assertEqual((code, out), (0, ""))

    # -- dates --------------------------------------------------------------

    def test_iso_and_month_name_dates_are_equal(self):
        code, out, _ = self.run_check("Due 2026-11-20.", "Due November 20, 2026.")
        self.assertEqual((code, out), (0, ""))

    def test_slash_and_iso_dates_are_equal(self):
        code, out, _ = self.run_check("Due 2026-11-20.", "Due 11/20/2026.")
        self.assertEqual((code, out), (0, ""))

    def test_day_month_and_month_day_without_year_are_equal(self):
        code, out, _ = self.run_check("Due 3 May.", "Due May 3.")
        self.assertEqual((code, out), (0, ""))

    def test_year_first_slash_date_matches_iso(self):
        code, out, _ = self.run_check("Due 2026-11-20.", "Due 2026/11/20.")
        self.assertEqual((code, out), (0, ""))

    def test_day_month_with_year_matches_iso(self):
        code, out, _ = self.run_check("Due 2026-05-03.", "Due 3 May 2026.")
        self.assertEqual((code, out), (0, ""))

    def test_abbreviated_month_name_matches_iso(self):
        code, out, _ = self.run_check("Due 2026-11-20.", "Due Nov 20, 2026.")
        self.assertEqual((code, out), (0, ""))

    def test_missing_date_prints_the_canonical_token(self):
        code, out, _ = self.run_check("Due 2026-11-20.", "Due soon.")
        self.assertEqual(code, 1)
        self.assertEqual(out, "MISSING date 2026-11-20\n")

    def test_added_date_is_reported(self):
        code, out, _ = self.run_check("Due soon.", "Due 2026-11-20.")
        self.assertEqual(code, 1)
        self.assertEqual(out, "ADDED date 2026-11-20\n")

    def test_impossible_date_is_not_a_date(self):
        # 2026-13-45 is not a real date; its digits compare as plain numbers.
        code, out, _ = self.run_check("Ref 2026-13-45.", "Ref 2026-13-45.")
        self.assertEqual((code, out), (0, ""))
        facts = cf.extract("Ref 2026-13-45.")
        self.assertEqual(
            facts, {("number", "2026"), ("number", "13"), ("number", "45")}
        )

    def test_changed_digit_in_impossible_dates_is_reported(self):
        # The fallback must keep the digits: without it both sides would
        # yield one None date token and the changed digit would be missed.
        code, out, _ = self.run_check("Ref 2026-13-45.", "Ref 2026-14-45.")
        self.assertEqual(code, 1)
        self.assertEqual(out, "MISSING number 13\nADDED number 14\n")

    # -- URLs and emails ------------------------------------------------------

    def test_url_trailing_punctuation_is_stripped(self):
        code, out, _ = self.run_check(
            "See https://a.example/x.", "See https://a.example/x"
        )
        self.assertEqual((code, out), (0, ""))

    def test_url_trailing_paren_and_period_are_stripped(self):
        code, out, _ = self.run_check(
            "Docs (https://a.example/x).", "Docs at https://a.example/x"
        )
        self.assertEqual((code, out), (0, ""))

    def test_missing_url_is_reported(self):
        code, out, _ = self.run_check("See https://a.example/x.", "See the docs.")
        self.assertEqual(code, 1)
        self.assertEqual(out, "MISSING url https://a.example/x\n")

    def test_added_url_is_reported(self):
        code, out, _ = self.run_check(
            "Visit https://a.example/x.", "Visit https://a.example/x and https://b.example/y."
        )
        self.assertEqual(code, 1)
        self.assertEqual(out, "ADDED url https://b.example/y\n")

    def test_missing_email_is_reported(self):
        code, out, _ = self.run_check("Email kim@a.example.", "Email the team.")
        self.assertEqual(code, 1)
        self.assertEqual(out, "MISSING email kim@a.example\n")

    def test_added_email_is_reported(self):
        code, out, _ = self.run_check("Email the team.", "Email kim@a.example.")
        self.assertEqual(code, 1)
        self.assertEqual(out, "ADDED email kim@a.example\n")

    def test_digits_inside_urls_and_emails_are_not_numbers(self):
        code, out, _ = self.run_check(
            "See https://a.example/2026 or kim99@a.example.",
            "See https://a.example/2026 or kim99@a.example.",
        )
        self.assertEqual((code, out), (0, ""))

    # -- arguments, files and --help -------------------------------------------

    def test_missing_original_file_exits_2_with_one_stderr_line(self):
        rew = self.dir / "rewrite.txt"
        rew.write_text("anything", encoding="utf-8")
        code, out, err = self.run_paths(self.dir / "nope.txt", rew)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("nope.txt", err)

    def test_missing_rewrite_file_exits_2(self):
        orig = self.dir / "original.txt"
        orig.write_text("anything", encoding="utf-8")
        code, out, err = self.run_paths(orig, self.dir / "nope.txt")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_undecodable_file_exits_2_with_one_stderr_line(self):
        orig = self.dir / "original.txt"
        orig.write_bytes(b"caf\xe9 latin-1, not utf-8")
        rew = self.dir / "rewrite.txt"
        rew.write_text("anything", encoding="utf-8")
        code, out, err = self.run_paths(orig, rew)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_help_exits_0(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--original", proc.stdout)
        self.assertIn("--rewrite", proc.stdout)

    def test_no_arguments_exits_2(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
