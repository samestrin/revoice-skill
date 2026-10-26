import mailbox
import tempfile
import unittest
from pathlib import Path

from _load import BUILD, FIXTURES, load, run_main

mfb = load(BUILD / "mbox-filter-before.py", "mbox_filter_before")


class DateCutoffTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name) / "out.mbox"

    def run_filter(self, before="2022-09-01"):
        _, stdout = run_main(mfb, str(FIXTURES / "sent.mbox"), "--before", before, "-o", str(self.out))
        box = mailbox.mbox(str(self.out))
        subjects = [m["Subject"] for m in box]
        box.close()
        return subjects, stdout

    def test_keeps_only_messages_dated_before_the_cutoff(self):
        subjects, _ = self.run_filter()
        self.assertEqual(subjects, ["Garden plans", "Re: Late summer", "Naive date"])

    def test_message_exactly_at_the_cutoff_is_dropped(self):
        subjects, _ = self.run_filter()
        self.assertNotIn("Exactly at the cut-off", subjects)

    def test_cutoff_compares_in_utc(self):
        # 22:00 at -0300 on 31 Aug is 01:00 UTC on 1 Sep: after the cutoff.
        subjects, _ = self.run_filter()
        self.assertNotIn("Timezone edge", subjects)

    def test_undated_and_unparseable_dates_are_dropped(self):
        subjects, _ = self.run_filter()
        self.assertNotIn("No date header", subjects)
        self.assertNotIn("Garbled date", subjects)

    def test_reports_counts_and_range(self):
        _, stdout = self.run_filter()
        self.assertRegex(stdout, r"kept\s+: 3\b")
        self.assertRegex(stdout, r"dropped \(late\)\s+: 3\b")
        self.assertRegex(stdout, r"dropped \(undated\): 2\b")
        self.assertIn("date range kept : 2022-08-15 to 2022-08-31", stdout)

    def test_overwrites_an_existing_output(self):
        self.run_filter()
        subjects, _ = self.run_filter()
        self.assertEqual(len(subjects), 3)

    def test_early_cutoff_keeps_nothing(self):
        subjects, stdout = self.run_filter(before="2000-01-01")
        self.assertEqual(subjects, [])
        self.assertNotIn("date range kept", stdout)

    def test_output_uses_lf_line_endings(self):
        self.run_filter()
        self.assertNotIn(b"\r\n", self.out.read_bytes())


class MsgDateTest(unittest.TestCase):
    def test_naive_date_is_read_as_utc(self):
        msg = mailbox.mboxMessage("Date: Tue, 30 Aug 2022 12:00:00\n\nbody\n")
        self.assertEqual(mfb._msg_date(msg).utcoffset().total_seconds(), 0)

    def test_missing_date_is_none(self):
        self.assertIsNone(mfb._msg_date(mailbox.mboxMessage("Subject: x\n\nbody\n")))


if __name__ == "__main__":
    unittest.main()
