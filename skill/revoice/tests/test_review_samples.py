import csv
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _load import BUILD, load, run_main

rs = load(BUILD / "review-samples.py", "review_samples")

AUTHOR = "Alex Example"

# Fictional prose in the author's own voice, reused by several tests.
PROSE = (
    "I looked at the numbers again this morning and I think we should move the launch "
    "to the week after the conference. The team is tired and the last two builds had "
    "problems that we did not expect.\n\n"
    "What I would do is ship the small fix first, then let the testers run it for a few "
    "days while we write the notes. If nothing breaks we go ahead, and if something does "
    "we have time to deal with it.\n\n"
    "Let me know what you think before Friday and I will update the plan.\n\n"
    "Thanks,\nAlex"
)

# (name, text, expected verdict, expected reason)
DROP_CASES = [
    ("quoted lines", "\n".join(
        ["Sounds good to me."] + ["> " + l for l in (
            "I wrote the plan last week and it covers the launch.",
            "Please read it and send me your comments by Friday.",
            "We can talk about the budget when you are back.",
            "Thanks for your time on this one.")]),
     "DROP", "quoted or forwarded text"),
    ("forwarded block", "FYI\n\n-----Original Message-----\nFrom: Pat Sample\nSent: Monday\n"
     "Subject: Quarterly update\nThe quarterly numbers are attached and the board meets soon.\n"
     "Please review the figures before the meeting and reply with questions.\n"
     "We expect a short discussion about hiring plans.",
     "DROP", "quoted or forwarded text"),
    ("boilerplate", "This email and any attachments are confidential and intended only for the "
     "named recipient.\nIf you are not the intended recipient please delete it.\n"
     "To unsubscribe from this list click the link below.\nPrivacy notice applies to all messages.",
     "DROP", "quoted or forwarded text"),
    ("bullet list", "Things to buy:\n- eggs\n- flour\n- sugar\n- butter\n- milk\n- salt",
     "DROP", "list, table, code or log"),
    ("table", "Item | Qty | Price\nApple | 3 | 1.20\nPear | 2 | 0.90\nPlum | 9 | 4.10",
     "DROP", "list, table, code or log"),
    ("code", "    def add(a, b):\n        return a + b\n    x = add(1, 2)\n    print(x)\n"
     "    import sys\n    sys.exit(0)",
     "DROP", "list, table, code or log"),
    ("log", "2024-03-01 10:00:01 INFO starting worker\n2024-03-01 10:00:02 WARN slow disk\n"
     "2024-03-01 10:00:03 ERROR job failed\n2024-03-01 10:00:04 INFO retrying",
     "DROP", "list, table, code or log"),
    ("other language", "Ich habe gestern mit dem Team gesprochen und wir haben beschlossen, die "
     "Veröffentlichung auf nächste Woche zu verschieben, weil noch einige Fehler behoben werden "
     "müssen und die Tests nicht vollständig durchgelaufen sind. Bitte gib mir Bescheid.",
     "DROP", "not in the author's language"),
    ("other name", PROSE.replace("Alex", "Jordan Nobody"), "DROP", "written in another name"),
    ("mostly signature", "Alex Example\nTel: +1 555 0100\nMobile: +1 555 0101\n"
     "alex@example.com\nhttps://example.com/alex\nSent from my phone",
     "DROP", "broken extraction"),
    ("replacement chars", "I ��� saw �� the �� report �� "
     "and �� it �� was �� fine �� ok", "DROP", "broken extraction"),
    ("non-letters", "%%%% ##### 12 34 56 ==== ---- ***** 9999 ~~~~ ^^^^ 00 11 22 @@@@ !!!! 7 8 9 $$$$",
     "DROP", "broken extraction"),
    ("cut off short", "I think the best way forward is to talk to the", "DROP", "broken extraction"),
    ("empty", "", "DROP", "broken extraction"),
]

KEEP_CASES = [
    ("clean", PROSE),
    ("casual", "hey, just saw ur note. yeah lets do thursday, i can bring the slides and we can "
     "go over the stuff for the board thing. sound ok? lmk"),
    ("typos", "I recieved the report yesturday and their are a few things that dont add up to me, "
     "mostly the totals in the second table. Can you chekc them and let me no what you find, "
     "I would like to send it of tomorow."),
    ("short but complete", "Thanks, will do"),
    ("short question", "Are we still on for lunch on Wednesday?"),
    ("few bullets in prose", "Here is where I am on the move.\n\nI packed the books and the kitchen.\n"
     "- still to do: garage\n- still to do: bikes\n\nI think we will finish by Sunday if the "
     "weather holds and the van shows up on time."),
]


FILLERS = [
    "I have been thinking about the schedule for next month and I do not believe that we can "
    "finish everything that is on the list without asking for some help from the other team.",
    "Please send me the notes from the meeting when you have a minute, because I want to make "
    "sure that I understood what was decided about the budget and who is going to do the work.",
    "The weather was bad all week so we stayed inside and played games with the kids, and it "
    "turned out to be one of the nicest weekends that we have had in a long time.",
]


def sample_dir(tmp, texts):
    rows = []
    for i, text in enumerate(texts):
        name = f"{i:03d}-s.md"
        (tmp / name).write_text(f"# Subject {i}\n{text}\n", encoding="utf-8")
        rows.append({"file": name, "date": "2020-01-01", "words": "4", "subject": f"Subject {i}"})
    with open(tmp / "index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "date", "words", "subject"])
        w.writeheader()
        w.writerows(rows)


class Rules(unittest.TestCase):
    def judge(self, text):
        # The language check compares a sample with the rest of the set.
        return rs.review([text, *FILLERS], AUTHOR)[0]

    def test_each_drop_rule(self):
        for name, text, verdict, reason in DROP_CASES:
            with self.subTest(name):
                r = self.judge(text)
                self.assertEqual((r["verdict"], r["reason"]), (verdict, reason))

    def test_not_dropped(self):
        for name, text in KEEP_CASES:
            with self.subTest(name):
                self.assertEqual(self.judge(text)["verdict"], "KEEP", self.judge(text))

    def test_clean_keep(self):
        r = self.judge(PROSE)
        self.assertEqual(r["verdict"], "KEEP")
        self.assertEqual(r["reason"], "own writing")
        self.assertGreaterEqual(r["score"], 4)

    def test_name_matches(self):
        for sign in ["Alex", "Alex Example", "A.", "Al", "alex"]:
            with self.subTest(sign):
                self.assertEqual(self.judge(PROSE.replace("Alex", sign))["verdict"], "KEEP")

    def test_name_rule_off_without_author(self):
        r = rs.review([PROSE.replace("Alex", "Jordan Nobody")], "")[0]
        self.assertEqual(r["verdict"], "KEEP")

    def test_signoff_name_in_prose_line_is_not_a_name(self):
        text = PROSE.replace("Thanks,\nAlex", "Thanks,\nsee you at the conference next week")
        self.assertEqual(self.judge(text)["verdict"], "KEEP")

    def test_ordinary_phrase_after_closing_is_not_another_name(self):
        for phrase in ["Will follow up", "See you Friday", "Give me a call", "talk soon then"]:
            with self.subTest(phrase):
                self.assertEqual(self.judge(PROSE.replace("Alex", phrase))["verdict"], "KEEP")

    def test_overlong_name_line_is_not_a_name(self):
        long_name = "Bartholomew Montgomery Featherstonehaugh-Smythe"
        self.assertGreater(len(long_name), 40)
        self.assertEqual(self.judge(PROSE.replace("Alex", long_name))["verdict"], "KEEP")

    def test_addresses_inside_prose_are_not_contact_lines(self):
        text = ("Please forward the invoice from accounts@example.com to billing@example.com.\n"
                "Also copy me at me@example.com so I have it on file.\nThanks,")
        self.assertEqual(self.judge(text)["verdict"], "KEEP")

    def test_single_list_line_is_not_a_list(self):
        self.assertEqual(self.judge("- eggs")["verdict"], "KEEP")
        self.assertEqual(self.judge("- eggs\n- milk")["reason"], "list, table, code or log")

    def test_table_needs_two_pipes(self):
        prose = ("Please pick either the red | the blue folder for the files.\n"
                 "Then send me the signed form | by next Friday if you can.")
        self.assertTrue(rs.TABLE.search("name | role | team"))
        self.assertIsNone(rs.TABLE.search("pick the red | the blue one"))
        self.assertEqual(self.judge(prose)["verdict"], "KEEP")
        rows = "| name | role |\n| Alex | lead |\n| Sam | dev |"
        self.assertEqual(self.judge(rows)["reason"], "list, table, code or log")

    def test_short_repeats_kept_longer_repeats_dropped(self):
        eleven = "Please send the signed form back to me by next Friday."  # 7 shingles
        twelve = "Please send the signed form back to me by next Friday morning."  # 8 shingles
        self.assertEqual([o["verdict"] for o in rs.review([eleven, eleven, *FILLERS], AUTHOR)[:2]],
                         ["KEEP", "KEEP"])
        self.assertEqual([o["verdict"] for o in rs.review([twelve, twelve, *FILLERS], AUTHOR)[:2]],
                         ["DROP", "DROP"])

    def test_reason_is_never_a_quote(self):
        for _, text, _, _ in DROP_CASES:
            r = self.judge(text)
            self.assertIn(r["reason"], rs.REASONS)
        self.assertIn(self.judge(PROSE)["reason"], rs.REASONS)

    def test_score_bounds(self):
        texts = ["", "ok", "word " * 5, PROSE, (PROSE + "\n\n") * 20, "x " * 5000]
        for t in texts:
            self.assertIn(self.judge(t)["score"], range(1, 6), t[:20])
        self.assertEqual(self.judge("ok")["score"], 1)
        self.assertEqual(self.judge((PROSE.rsplit("\n\n", 1)[0] + "\n\n") * 6)["score"], 5)

    def test_score_rises_with_length_and_paragraphs(self):
        one = "I think this is fine and we should go ahead with the plan as written. " * 6
        multi = "\n\n".join([one.strip()] * 3)
        self.assertLess(self.judge(one)["score"], self.judge(multi)["score"])
        self.assertLess(self.judge("Short note here.")["score"], self.judge(one)["score"])

    def test_form_letter_dropped_but_short_repeats_kept(self):
        letter = ("Dear friend, thank you for your interest in our summer program. We have "
                  "received your request and will send the details within ten working days. "
                  "Please keep this letter for your records.")
        other = [PROSE, "Thanks, will do", "Thanks, will do"]
        out = rs.review([letter + " Ref %d" % 1, letter + " Ref %d" % 2, *other], AUTHOR)
        self.assertEqual([o["verdict"] for o in out], ["DROP", "DROP", "KEEP", "KEEP", "KEEP"])
        self.assertEqual(out[0]["reason"], "form letter")

    def test_different_letters_not_duplicates(self):
        a = "The garden needs water every morning during the dry weeks of July and August."
        b = "My brother bought a second hand bicycle and rode it across the old stone bridge."
        out = rs.review([a, b], AUTHOR)
        self.assertEqual([o["verdict"] for o in out], ["KEEP", "KEEP"])

    def test_near_duplicate_work_is_bounded(self):
        letter = " ".join(f"{a}{b}x" for a in "abcdefghij" for b in "abcdefghijklmnopqrst" for _ in "1234")
        stats = {}
        dups = rs.find_duplicates([letter] * 300, stats)
        self.assertEqual(dups, set(range(300)))
        self.assertLessEqual(stats["max_candidates"], rs.BUCKET)
        self.assertEqual(stats["max_shingles"], rs.MAX_SHINGLES)

    def test_other_language_follows_the_authors_set(self):
        german = DROP_CASES[7][1]
        # An author whose whole set is German: the check must not drop everything.
        out = rs.review([german, "Heute ist das Wetter schön und ich gehe mit dem Hund spazieren, "
                         "weil er nicht zu lange allein bleiben soll und es ihm gut tut."], AUTHOR)
        self.assertEqual([o["verdict"] for o in out], ["KEEP", "KEEP"])
        # One German sample among English ones is dropped.
        out = rs.review([PROSE, *FILLERS[:2], german], AUTHOR)
        self.assertEqual(out[3]["reason"], "not in the author's language")

    def test_german_author_drops_a_stray_english_sample(self):
        german = [DROP_CASES[7][1], *GERMAN]
        out = rs.review([*german, FILLERS[0]], AUTHOR)
        self.assertEqual([o["verdict"] for o in out], ["KEEP", "KEEP", "KEEP", "DROP"])
        self.assertEqual(out[3]["reason"], "not in the author's language")
        # A German-only set is all kept, and a short English line is too short to judge.
        out = rs.review([*german, "Thanks, will do"], AUTHOR)
        self.assertEqual([o["verdict"] for o in out], ["KEEP"] * 4)

    def test_english_author_still_checked_in_english(self):
        # A German line among English samples: English stays the author's language.
        out = rs.review([*FILLERS, GERMAN[0]], AUTHOR)
        self.assertEqual([o["verdict"] for o in out], ["KEEP", "KEEP", "KEEP", "DROP"])
        self.assertEqual(rs.FUNCTION_WORDS, rs.LANGUAGE_WORDS["english"])

    def test_share_constants_have_language_neutral_names(self):
        # The thresholds apply to the author's language, whichever it is.
        self.assertEqual(rs.LANGUAGE_SHARE, 0.12)
        self.assertEqual(rs.LANGUAGE_AUTHOR_SHARE, 0.2)
        self.assertEqual([n for n in dir(rs) if n.startswith("ENGLISH_")], [])

    def test_unknown_language_runs_no_check(self):
        spanish = ("Ayer hablé con el equipo y decidimos mover la publicación a la próxima semana, "
                   "porque todavía quedan algunos errores por corregir y las pruebas no terminaron.")
        other = ("Mañana voy a llamar al cliente para explicarle el retraso y luego te cuento "
                 "qué dijo, pero creo que lo va a entender sin problema porque ya lo sabía.")
        self.assertIsNone(rs.author_language([spanish, other]))
        out = rs.review([spanish, other, FILLERS[0]], AUTHOR)
        self.assertEqual([o["verdict"] for o in out], ["KEEP"] * 3)


GERMAN = [
    "Heute ist das Wetter schön und ich gehe mit dem Hund spazieren, weil er nicht zu lange "
    "allein bleiben soll und es ihm gut tut.",
    "Kannst du mir bitte bis Freitag die Zahlen schicken, damit ich den Bericht für die "
    "Sitzung fertig machen kann? Wir haben nicht mehr viel Zeit und ich will das Team nicht warten lassen.",
]


class MainTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def read(self):
        with open(self.dir / "index.csv", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return reader.fieldnames, list(reader)

    def test_main_runs_with_sockets_blocked_and_no_key(self):
        sample_dir(self.dir, [PROSE, DROP_CASES[3][1], FILLERS[0].replace("\n", " ") + "\n\nThanks,\nJordan Nobody"])
        with mock.patch("socket.socket", side_effect=AssertionError("network used")), \
                mock.patch("socket.create_connection", side_effect=AssertionError("network used")), \
                mock.patch.dict("os.environ", {}, clear=True):
            _, out = run_main(rs, "--samples", str(self.dir), "--author", AUTHOR)
        fields, rows = self.read()
        self.assertEqual(fields, ["file", "date", "words", "subject", "verdict", "score", "reason"])
        self.assertEqual([r["verdict"] for r in rows], ["KEEP", "DROP", "DROP"])
        self.assertIn("reviewed 3 samples: 1 KEEP, 2 DROP", out)
        self.assertEqual(list(self.dir.glob("*.tmp")), [])

    def test_rerun_replaces_columns(self):
        sample_dir(self.dir, [PROSE])
        run_main(rs, "--samples", str(self.dir), "--author", AUTHOR)
        run_main(rs, "--samples", str(self.dir), "--author", AUTHOR)
        self.assertEqual(self.read()[0].count("verdict"), 1)

    def test_header_only_index_exits_unchanged(self):
        (self.dir / "index.csv").write_text("file,date,words,subject\n", encoding="utf-8")
        before = (self.dir / "index.csv").read_bytes()
        with self.assertRaises(SystemExit) as cm:
            run_main(rs, "--samples", str(self.dir))
        self.assertIn("no samples", str(cm.exception))
        self.assertEqual((self.dir / "index.csv").read_bytes(), before)

    def test_failed_run_leaves_index_unchanged(self):
        sample_dir(self.dir, [PROSE, FILLERS[0]])
        (self.dir / "001-s.md").unlink()
        before = (self.dir / "index.csv").read_bytes()
        with self.assertRaises(FileNotFoundError):
            run_main(rs, "--samples", str(self.dir), "--author", AUTHOR)
        self.assertEqual((self.dir / "index.csv").read_bytes(), before)
        self.assertEqual(list(self.dir.glob("*.tmp")), [])

    def test_failed_write_leaves_index_unchanged(self):
        sample_dir(self.dir, [PROSE])
        before = (self.dir / "index.csv").read_bytes()
        with mock.patch.object(rs.os, "replace", side_effect=OSError("disk full")), \
                self.assertRaises(OSError):
            run_main(rs, "--samples", str(self.dir), "--author", AUTHOR)
        self.assertEqual((self.dir / "index.csv").read_bytes(), before)
        self.assertEqual(list(self.dir.glob("*.tmp")), [])


class CliContract(unittest.TestCase):
    """The output build-profile.py reads, and the command line build.md calls."""

    def test_build_profile_ranks_the_review_output(self):
        bp = load(BUILD / "build-profile.py", "build_profile")
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            short = "I can do Thursday, and I will bring the slides for the board."
            sample_dir(d, [DROP_CASES[3][1], short, PROSE])
            run_main(rs, "--samples", str(d), "--author", AUTHOR)
            # KEEP rows only, best score first; the list sample is dropped.
            self.assertEqual(bp.ranked_files(d), ["002-s.md", "001-s.md"])

    def test_help(self):
        out = subprocess.run([sys.executable, str(BUILD / "review-samples.py"), "--help"],
                             capture_output=True, text=True, check=True).stdout
        self.assertIn("--samples", out)
        self.assertIn("--author", out)
        self.assertNotIn("--api", out)

    def test_api_arguments_dropped_here_only(self):
        for arg in ("--api", "--api-key", "--api-key-file"):
            with self.subTest(arg), self.assertRaises(SystemExit), \
                    mock.patch("sys.stderr", io.StringIO()):
                run_main(rs, arg, "x")
        bp_help = subprocess.run([sys.executable, str(BUILD / "build-profile.py"), "--help"],
                                 capture_output=True, text=True, check=True).stdout
        for arg in ("--api", "--api-key", "--api-key-file"):
            self.assertIn(arg, bp_help)


if __name__ == "__main__":
    unittest.main()
