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

    def test_max_samples_keeps_the_longest(self):
        texts, stdout = self.extract("--max-samples", "2")
        self.assertEqual(sorted(texts), ["Bike ride", "Garden plans"])
        self.assertRegex(stdout, r"over the cap\s+: 2\b")

    def test_max_samples_zero_means_no_cap(self):
        texts, _ = self.extract("--max-samples", "0")
        self.assertEqual(len(texts), 4)

    def test_default_cap_is_148(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        mbox = Path(tmp.name) / "big.mbox"
        words = " ".join(f"word{i}" for i in range(20))
        with open(mbox, "w", encoding="utf-8") as f:
            for i in range(160):
                f.write(f"From alex@example.com Tue Mar  1 09:00:00 2022\n"
                        f"From: Alex Rivera <alex@example.com>\n"
                        f"To: Jordan Lee <jordan@example.org>\n"
                        f"Subject: Note {i}\n"
                        f"Date: Tue, 01 Mar 2022 09:00:00 +0000\n\n"
                        f"Message {i} {words}\n\n")
        out = Path(tmp.name) / "out"
        subprocess.run(
            [sys.executable, str(SCRIPT), str(mbox), "--from", "ALEX@example.com",
             "--min-words", "1", "--sig-min-count", "1000", "-o", str(out)],
            capture_output=True, text=True, check=True)
        with open(out / "index.csv", newline="", encoding="utf-8") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 148)


class MessageOrderTest(unittest.TestCase):
    """The same mailbox in another message order gives the same output folder."""

    BODY = " ".join(f"word{i}" for i in range(20))
    MESSAGES = [
        # Equal length, different subjects: the cap and index.csv must not
        # fall back to mbox order.
        ("Fence", "Tue, 01 Mar 2022 09:00:00 +0000", f"Fence {BODY}"),
        ("Compost", "Tue, 01 Mar 2022 09:00:00 +0000", f"Compost {BODY}"),
        # One forward sent twice minutes apart: duplicates of equal length.
        ("Gas report", "Wed, 02 Mar 2022 06:18:00 +0000", f"Forwarded by Alex 06:18 {BODY}"),
        ("Gas report", "Wed, 02 Mar 2022 06:30:00 +0000", f"Forwarded by Alex 06:30 {BODY}"),
        # No date at all, and a date with no time zone ("-0000").
        ("Bike ride", None, f"Ride {BODY}"),
        ("Seed swap", "Tue, 01 Mar 2022 09:00:00 -0000", f"Seeds {BODY}"),
    ]

    def run_order(self, messages, *extra):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        mbox = Path(tmp.name) / "in.mbox"
        with open(mbox, "w", encoding="utf-8") as f:
            for subject, date, body in messages:
                f.write("From alex@example.com Tue Mar  1 09:00:00 2022\n"
                        "From: Alex Rivera <alex@example.com>\n"
                        f"Subject: {subject}\n"
                        + (f"Date: {date}\n" if date else "")
                        + f"\n{body}\n\n")
        out = Path(tmp.name) / "out"
        subprocess.run(
            [sys.executable, str(SCRIPT), str(mbox), "--from", "alex@example.com",
             "--min-words", "1", "--sig-min-count", "1000", "-o", str(out), *extra],
            capture_output=True, text=True, check=True)
        return {p.name: p.read_bytes() for p in sorted(out.iterdir())}

    def assert_order_independent(self, *extra):
        forward = self.run_order(self.MESSAGES, *extra)
        backward = self.run_order(self.MESSAGES[::-1], *extra)
        self.assertEqual(list(forward), list(backward))
        self.assertEqual(forward, backward)
        return forward

    def test_no_cap(self):
        files = self.assert_order_independent("--max-samples", "0")
        # Fence, Compost, one Gas report, Bike ride, Seed swap, index.csv.
        self.assertEqual(len(files), 6)

    def test_cap_on_equal_lengths(self):
        # One Gas report (longest), then one of four samples of 21 words.
        files = self.assert_order_independent("--max-samples", "2")
        self.assertEqual(len(files), 3)


if __name__ == "__main__":
    unittest.main()
