import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _load import BUILD, FIXTURES, load

SCRIPT = BUILD / "extract-samples.py"
es = load(SCRIPT, "extract_samples")


class OwnTextTest(unittest.TestCase):
    def test_cuts_from_on_wrote_marker(self):
        body = "My reply.\n\nOn Mon, Feb 28, 2022 at 6:00 PM Jordan Lee <jordan@example.org> wrote:\n> theirs\n"
        self.assertEqual(es._own_text(body), "My reply.")

    def test_cuts_on_wrote_marker_wrapped_over_two_lines(self):
        body = "My reply.\n\nOn Mon, Feb 28, 2022 at 6:00 PM Jordan Lee\n<jordan@example.org> wrote:\nTheirs.\n"
        self.assertEqual(es._own_text(body), "My reply.")

    def test_cuts_from_original_message_marker(self):
        body = "Mine.\n-----Original Message-----\nFrom: Morgan\nTheirs.\n"
        self.assertEqual(es._own_text(body), "Mine.")

    def test_cuts_from_outlook_header_block(self):
        body = "Mine.\n\nFrom: Morgan Diaz\nSent: Friday\nTo: Alex\nTheirs.\n"
        self.assertEqual(es._own_text(body), "Mine.")

    def test_cuts_from_signature_delimiter(self):
        body = "Mine.\n-- \nAlex Rivera\nGreen Thumb Club\n"
        self.assertEqual(es._own_text(body), "Mine.")

    def test_drops_quote_lines_and_sent_from_my(self):
        body = "First.\n> quoted\n  > indented quote\nSecond.\nSent from my phone\n"
        self.assertEqual(es._own_text(body), "First.\nSecond.")

    def test_normalises_crlf(self):
        self.assertEqual(es._own_text("One.\r\nTwo.\r\n"), "One.\nTwo.")


class StripSignatureTest(unittest.TestCase):
    def test_strips_trailing_signature_lines_and_blanks(self):
        text = "Body line.\nCheers\n\nAlex\n"
        self.assertEqual(es._strip_signature(text, {"Cheers", "Alex"}), "Body line.")

    def test_keeps_signature_words_that_are_not_trailing(self):
        text = "Cheers\nBody line."
        self.assertEqual(es._strip_signature(text, {"Cheers"}), text)


class ExtractRunTest(unittest.TestCase):
    """Runs the script on the synthetic mailbox, as a user would."""

    def extract(self, *extra):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "out"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(FIXTURES / "conversation.mbox"),
             "--from", "ALEX@example.com", "--min-words", "1", "--sig-min-count", "2",
             "-o", str(out), *extra],
            capture_output=True, text=True, check=True)
        with open(out / "index.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        texts = {r["subject"]: (out / r["file"]).read_text(encoding="utf-8") for r in rows}
        return texts, proc.stdout

    def test_author_samples(self):
        texts, _ = self.extract()
        self.assertEqual(sorted(texts), ["Bike ride", "Compost", "Fence", "Garden plans"])
        self.assertTrue(texts["Garden plans"].startswith("# Garden plans\n\nThanks Jordan,"))

    def test_quoted_replies_signatures_and_forwards_never_leak(self):
        texts, _ = self.extract()
        joined = "\n".join(texts.values())
        for marker in ("QUOTED-REPLY-TEXT", "SIGNATURE-BLOCK-TEXT", "INLINE-QUOTE-TEXT",
                       "ORIGINAL-MESSAGE-TEXT", "FORWARDED-TEXT", "Sent from my",
                       "JORDAN-OWN-TEXT", "MORGAN-OWN-TEXT"):
            self.assertNotIn(marker, joined)

    def test_recurring_trailing_line_is_stripped_as_signature(self):
        texts, stdout = self.extract()
        self.assertNotIn("Cheers from the allotment", texts["Bike ride"])
        self.assertNotIn("Cheers from the allotment", texts["Compost"])
        self.assertIn("We should try the hill route next week.", texts["Bike ride"])
        self.assertIn("Cheers from the allotment", stdout)

    def test_others_builds_reference_set_from_other_senders_only(self):
        texts, stdout = self.extract("--others")
        self.assertEqual(sorted(texts), ["Book club", "Seed swap"])
        self.assertIn("JORDAN-OWN-TEXT", texts["Seed swap"])
        self.assertIn("MORGAN-OWN-TEXT", texts["Book club"])
        self.assertRegex(stdout, r"author\s+: 5\b")

    def test_min_words_drops_short_samples(self):
        # Garden plans has 15 words, Bike ride 19 once stripped, Compost and Fence 13.
        texts, _ = self.extract("--min-words", "14")
        self.assertEqual(sorted(texts), ["Bike ride", "Garden plans"])


if __name__ == "__main__":
    unittest.main()
