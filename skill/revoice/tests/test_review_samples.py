import csv
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _load import BUILD, load, real_run_body, run_main

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

    def test_spanish_and_french_authors_drop_stray_samples(self):
        for language, own, stray in (("spanish", SPANISH, FRENCH[0]), ("french", FRENCH, SPANISH[0])):
            with self.subTest(language=language):
                self.assertEqual(rs.author_language(own), language)
                # An own-language set is all kept.
                out = rs.review(own, AUTHOR)
                self.assertEqual([o["verdict"] for o in out], ["KEEP"] * 3)
                # A stray English sample, and one in the other language, are dropped.
                for other in (FILLERS[0], stray):
                    out = rs.review([*own, other], AUTHOR)
                    self.assertEqual([o["verdict"] for o in out], ["KEEP", "KEEP", "KEEP", "DROP"])
                    self.assertEqual(out[3]["reason"], "not in the author's language")
                # A short English line is too short to judge.
                out = rs.review([*own, "Thanks, will do"], AUTHOR)
                self.assertEqual([o["verdict"] for o in out], ["KEEP"] * 4)

    def test_english_and_german_authors_drop_spanish_and_french(self):
        for own in (FILLERS, [DROP_CASES[7][1], *GERMAN]):
            for other in (SPANISH[0], FRENCH[0]):
                out = rs.review([*own, other], AUTHOR)
                self.assertEqual([o["verdict"] for o in out], ["KEEP", "KEEP", "KEEP", "DROP"])

    def test_unknown_language_runs_no_check(self):
        # Spanish was the unknown language here until it got a word list; Finnish has none.
        finnish = ("Puhuin eilen tiimin kanssa ja päätimme siirtää julkaisua ensi viikolle, "
                   "koska muutama virhe on vielä korjaamatta eikä testaus ole valmis.")
        other = ("Soitan huomenna asiakkaalle ja kerron viivästyksestä, sitten kerron sinulle "
                 "mitä hän sanoi, mutta luulen että hän ymmärtää sen hyvin koska hän tiesi jo.")
        self.assertIsNone(rs.author_language([finnish, other]))
        out = rs.review([finnish, other, FILLERS[0]], AUTHOR)
        self.assertEqual([o["verdict"] for o in out], ["KEEP"] * 3)


GERMAN = [
    "Heute ist das Wetter schön und ich gehe mit dem Hund spazieren, weil er nicht zu lange "
    "allein bleiben soll und es ihm gut tut.",
    "Kannst du mir bitte bis Freitag die Zahlen schicken, damit ich den Bericht für die "
    "Sitzung fertig machen kann? Wir haben nicht mehr viel Zeit und ich will das Team nicht warten lassen.",
]

SPANISH = [
    "Ayer hablé con el equipo y decidimos mover la publicación a la próxima semana, porque "
    "todavía quedan algunos errores por corregir y las pruebas no terminaron.",
    "Mañana voy a llamar al cliente para explicarle el retraso y luego te cuento qué dijo, "
    "pero creo que lo va a entender sin problema porque ya lo sabía.",
    "¿Me puedes mandar los números antes del viernes? Quiero terminar el informe para la "
    "reunión y no tenemos mucho tiempo, así que no quiero que el equipo tenga que esperar.",
]

FRENCH = [
    "Hier j'ai parlé avec l'équipe et nous avons décidé de repousser la sortie à la semaine "
    "prochaine, parce qu'il reste encore des erreurs à corriger et que les tests ne sont pas finis.",
    "Demain je vais appeler le client pour lui expliquer le retard et je te dirai ce qu'il a "
    "dit, mais je pense qu'il va comprendre sans problème parce qu'il le savait déjà.",
    "Est-ce que tu peux m'envoyer les chiffres avant vendredi ? Je veux finir le rapport pour "
    "la réunion et nous n'avons plus beaucoup de temps, donc je ne veux pas faire attendre l'équipe.",
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


QUOTED = DROP_CASES[0][1]
SIGNED_BY_OTHER = PROSE.replace("Thanks,\nAlex", "Best regards,\nSomeone Else")
BYLINE_OTHER = "By Jane Doe\n\n" + PROSE.rsplit("\n\n", 1)[0]
BYLINE_OWN = "By Sam Lee\n\n" + PROSE.rsplit("\n\n", 1)[0]

SYLLABLES = "ka lo mi ren to sa vel du po ni".split()


def passage(i: int) -> str:
    """A distinct English-shaped passage of 100 words.

    Every other word is a made-up word of this passage only, so no two passages
    share a word 5-gram and none is a form letter.
    """
    vocab = [SYLLABLES[i % 10] + SYLLABLES[i // 10 % 10] + SYLLABLES[j] for j in range(8)]
    sentences = [f"The {vocab[k % 8]} of the {vocab[(k + 3) % 8]} was {vocab[(k + 5) % 8]} "
                 f"and {vocab[(k + 6) % 8]}." for k in range(10)]
    return " ".join(sentences[:5]) + "\n\n" + " ".join(sentences[5:])


def passage_dir(tmp, texts, sources):
    rows = []
    for i, (text, source) in enumerate(zip(texts, sources)):
        name = f"{i:03d}-p.md"
        (tmp / name).write_text(f"# Title {i}\n{text}\n", encoding="utf-8")
        rows.append({"file": name, "date": "undated", "words": "100", "subject": f"Title {i}",
                     "source": source})
    with open(tmp / "index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "date", "words", "subject", "source"])
        w.writeheader()
        w.writerows(rows)


class Modes(unittest.TestCase):
    """--mode email|writing|brand, per the review-modes table in epic plan 17."""

    def judge(self, text, mode, author=AUTHOR):
        return rs.review([text, *FILLERS], author, mode)[0]

    def test_quoted_passage_dropped_in_email_only(self):
        self.assertEqual(self.judge(QUOTED, "email")["reason"], "quoted or forwarded text")
        for mode in ("writing", "brand"):
            with self.subTest(mode):
                self.assertEqual(self.judge(QUOTED, mode)["verdict"], "KEEP")

    def test_other_signoff_dropped_in_email_only(self):
        self.assertEqual(self.judge(SIGNED_BY_OTHER, "email")["reason"], "written in another name")
        for mode in ("writing", "brand"):
            with self.subTest(mode):
                self.assertEqual(self.judge(SIGNED_BY_OTHER, mode)["verdict"], "KEEP")

    def test_byline_of_someone_else_dropped_in_writing_only(self):
        r = self.judge(BYLINE_OTHER, "writing", "Sam Lee")
        self.assertEqual((r["verdict"], r["reason"]), ("DROP", "written by someone else"))
        self.assertEqual(self.judge(BYLINE_OTHER, "brand", "Sam Lee")["verdict"], "KEEP")
        self.assertEqual(self.judge(BYLINE_OTHER, "email", "Sam Lee")["verdict"], "KEEP")

    def test_byline_variants(self):
        for line in ("Written by Jane Doe", "Posted by Jane Doe", "Written By Jane Doe", "*By Jane Doe*",
                     "Posted by Jane Doe on March 3, 2019"):
            with self.subTest(line):
                text = line + "\n\n" + PROSE.rsplit("\n\n", 1)[0]
                self.assertEqual(self.judge(text, "writing", "Sam Lee")["reason"],
                                 "written by someone else")
        last = PROSE.rsplit("\n\n", 1)[0] + "\n\nBy Jane Doe"
        self.assertEqual(self.judge(last, "writing", "Sam Lee")["reason"], "written by someone else")

    def test_byline_rule_needs_a_name(self):
        for line in ("By Sam Lee", "By S. Lee", "Written by Sam", "By the way, this is mine.",
                     "By Friday we need the plan.", "By Monday", "By March 2019"):
            with self.subTest(line):
                text = line + "\n\n" + PROSE.rsplit("\n\n", 1)[0]
                self.assertEqual(self.judge(text, "writing", "Sam Lee")["verdict"], "KEEP")
        # A byline in the middle of a passage is a quotation, not the byline.
        middle = PROSE.replace("\n\n", "\n\nBy Jane Doe\n\n", 1).rsplit("\n\n", 1)[0]
        self.assertEqual(self.judge(middle, "writing", "Sam Lee")["verdict"], "KEEP")

    def test_byline_rule_off_without_author(self):
        self.assertEqual(self.judge(BYLINE_OTHER, "writing", "")["verdict"], "KEEP")
        self.assertEqual(self.judge(BYLINE_OWN, "writing", "Sam Lee")["verdict"], "KEEP")

    def test_generic_rules_stay_on_in_every_mode(self):
        for mode in rs.MODES:
            for name, text, _, reason in DROP_CASES:
                if reason in ("quoted or forwarded text", "written in another name"):
                    continue
                with self.subTest(mode=mode, case=name):
                    self.assertEqual(self.judge(text, mode)["reason"], reason)

    def test_default_mode_is_email(self):
        texts = [QUOTED, SIGNED_BY_OTHER, BYLINE_OTHER, *FILLERS]
        self.assertEqual(rs.review(texts, AUTHOR), rs.review(texts, AUTHOR, "email"))

    def test_new_reason_is_listed(self):
        self.assertIn("written by someone else", rs.REASONS)

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):
            rs.review([PROSE], AUTHOR, "mbox")


class ModeMain(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def run_cli(self, *argv):
        return subprocess.run([sys.executable, str(BUILD / "review-samples.py"),
                               "--samples", str(self.dir), *argv],
                              capture_output=True, text=True)

    def verdicts(self):
        with open(self.dir / "index.csv", newline="", encoding="utf-8") as f:
            return [r["verdict"] for r in csv.DictReader(f)]

    def test_passages_are_distinct_keeps(self):
        texts = [passage(i) for i in range(12)]
        self.assertEqual([v["verdict"] for v in rs.review(texts, "", "writing")], ["KEEP"] * 12)

    def test_coverage_counts_keep_passages_and_distinct_sources(self):
        texts = [passage(i) for i in range(12)] + [DROP_CASES[3][1]]
        sources = [f"doc{i % 4}.md" for i in range(12)] + ["doc9.md"]
        passage_dir(self.dir, texts, sources)
        _, out = run_main(rs, "--samples", str(self.dir), "--mode", "writing")
        # The dropped list's document is not counted.
        self.assertIn("coverage: 12 KEEP passages from 4 documents", out)
        self.assertIn("reviewed 13 samples: 12 KEEP, 1 DROP", out)

    def test_coverage_without_a_source_column_counts_no_documents(self):
        sample_dir(self.dir, [passage(i) for i in range(10)])
        _, out = run_main(rs, "--samples", str(self.dir), "--mode", "writing")
        self.assertIn("coverage: 10 KEEP passages from 0 documents", out)

    def test_nine_keep_passages_exit_3_in_writing_and_still_write_the_index(self):
        passage_dir(self.dir, [passage(i) for i in range(9)], [f"d{i}.md" for i in range(9)])
        p = self.run_cli("--mode", "writing", "--author", "Sam Lee")
        self.assertEqual(p.returncode, 3, p.stderr)
        self.assertIn("coverage: 9 KEEP passages from 9 documents", p.stdout)
        self.assertIn("10", p.stderr)
        self.assertEqual(self.verdicts(), ["KEEP"] * 9)

    def test_ten_keep_passages_pass_in_writing(self):
        passage_dir(self.dir, [passage(i) for i in range(10)], [f"d{i}.md" for i in range(10)])
        p = self.run_cli("--mode", "writing")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("coverage: 10 KEEP passages from 10 documents", p.stdout)

    def test_drops_do_not_count_toward_the_floor(self):
        texts = [passage(i) for i in range(9)] + [QUOTED.replace("Sounds", "By Jane Doe\n\nSounds")]
        passage_dir(self.dir, texts, [f"d{i}.md" for i in range(10)])
        p = self.run_cli("--mode", "writing", "--author", "Sam Lee")
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertEqual(self.verdicts(), ["KEEP"] * 9 + ["DROP"])

    def test_brand_needs_three_documents(self):
        texts = [passage(i) for i in range(12)]
        passage_dir(self.dir, texts, [f"d{i % 2}.md" for i in range(12)])
        p = self.run_cli("--mode", "brand", "--author", "Acme")
        self.assertEqual(p.returncode, 3, p.stderr)
        self.assertIn("coverage: 12 KEEP passages from 2 documents", p.stdout)
        self.assertIn("3 documents", p.stderr)
        passage_dir(self.dir, texts, [f"d{i % 3}.md" for i in range(12)])
        p = self.run_cli("--mode", "brand", "--author", "Acme")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("coverage: 12 KEEP passages from 3 documents", p.stdout)

    def test_brand_needs_ten_passages(self):
        passage_dir(self.dir, [passage(i) for i in range(9)], [f"d{i}.md" for i in range(9)])
        self.assertEqual(self.run_cli("--mode", "brand").returncode, 3)

    def test_between_floor_and_minimum_warns_and_passes(self):
        passage_dir(self.dir, [passage(i) for i in range(12)], [f"d{i % 6}.md" for i in range(12)])
        p = self.run_cli("--mode", "writing")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("below the minimum", p.stdout)
        self.assertIn("20", p.stdout)

    def test_email_mode_has_no_floor_and_no_coverage_line(self):
        sample_dir(self.dir, [PROSE])
        p = self.run_cli("--author", AUTHOR)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "reviewed 1 samples: 1 KEEP, 0 DROP\n")
        self.assertEqual(p.stderr, "")
        self.assertEqual(self.run_cli("--author", AUTHOR, "--mode", "email").stdout, p.stdout)

    def test_floors_are_constants(self):
        self.assertEqual(rs.FLOORS, {"writing": (10, 0), "brand": (10, 3)})
        self.assertEqual(rs.MINIMUMS, {"writing": (20, 5), "brand": (20, 5)})

    def test_unknown_mode_rejected_by_cli(self):
        sample_dir(self.dir, [PROSE])
        p = self.run_cli("--mode", "mbox")
        self.assertEqual(p.returncode, 2)
        self.assertIn("invalid choice", p.stderr)
        self.assertIn("--mode", self.run_cli("--help").stdout)

    def test_one_document_is_singular(self):
        passage_dir(self.dir, [passage(i) for i in range(10)], ["only.md"] * 10)
        p = self.run_cli("--mode", "writing")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("coverage: 10 KEEP passages from 1 document\n", p.stdout)
        self.assertNotIn("1 documents", p.stdout + p.stderr)

    def test_below_the_minimum_documents_warns(self):
        # One article saved three ways is one document (T2); 25 passages from 3 is weaker.
        passage_dir(self.dir, [passage(i) for i in range(25)], [f"d{i % 3}.md" for i in range(25)])
        p = self.run_cli("--mode", "writing")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("coverage: 25 KEEP passages from 3 documents\n", p.stdout)
        self.assertIn("below the minimum for writing: 20 KEEP passages from 5 documents "
                      "give a stronger profile; this one will be weaker", p.stdout)

    def test_at_the_minimum_no_warning(self):
        passage_dir(self.dir, [passage(i) for i in range(25)], [f"d{i % 5}.md" for i in range(25)])
        p = self.run_cli("--mode", "brand")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("coverage: 25 KEEP passages from 5 documents\n", p.stdout)
        self.assertNotIn("weaker", p.stdout)


# Excerpts from the operator's real 0.3.0 run (tests/fixtures/real_run/README.md).
REAL_PROSE = [real_run_body(f"prose_{n}.md") for n in (
    "comparing13_a", "comparing13_b", "72faster_a", "72faster_b", "llmenv_a", "llmenv_b")]
REAL_LLM_OUTPUT = {n: real_run_body(f"{n}.md")
                   for n in ("llm_output_docx_a", "llm_output_docx_b", "llm_output_pdf_a")}
REAL_TABLE = real_run_body("table_docx_numbers.md")
DOCUMENT_MODES = ("writing", "brand")


class RealRun(unittest.TestCase):
    """Bugs 2 and 6: quoted model output and table text, judged in a set like the real one."""

    def judge(self, text, mode):
        return rs.review([text, *REAL_PROSE], "Sam Estrin", mode)[0]

    def test_quoted_model_output_dropped_in_document_modes(self):
        for mode in DOCUMENT_MODES:
            for name, text in REAL_LLM_OUTPUT.items():
                with self.subTest(mode=mode, passage=name):
                    r = self.judge(text, mode)
                    self.assertEqual((r["verdict"], r["reason"]), ("DROP", "quoted model output"))

    def test_table_dropped_in_document_modes(self):
        for mode in DOCUMENT_MODES:
            with self.subTest(mode):
                r = self.judge(REAL_TABLE, mode)
                self.assertEqual((r["verdict"], r["reason"]), ("DROP", "table or numbers"))

    def test_real_prose_kept(self):
        texts = [*REAL_PROSE, *REAL_LLM_OUTPUT.values(), REAL_TABLE]
        for mode in DOCUMENT_MODES:
            with self.subTest(mode):
                out = rs.review(texts, "Sam Estrin", mode)[:len(REAL_PROSE)]
                self.assertEqual([(o["verdict"], o["reason"]) for o in out],
                                 [("KEEP", "own writing")] * len(REAL_PROSE))

    def test_synthetic_prose_kept_in_document_modes(self):
        texts = [PROSE, *(t for _, t in KEEP_CASES), QUOTED, SIGNED_BY_OTHER, BYLINE_OWN,
                 *(passage(i) for i in range(12))]
        for mode in DOCUMENT_MODES:
            self.assertEqual([o["verdict"] for o in rs.review(FILLERS, "Sam Lee", mode)],
                             ["KEEP"] * len(FILLERS))
            for text in texts:
                with self.subTest(mode=mode, text=text[:40]):
                    self.assertEqual(rs.review([text, *FILLERS], "Sam Lee", mode)[0]["verdict"],
                                     "KEEP")

    def test_email_mode_judges_them_as_before(self):
        # Pinned from main at 10d30cb: email has neither rule.
        texts = [*REAL_LLM_OUTPUT.values(), REAL_TABLE, *REAL_PROSE]
        out = rs.review(texts, "Sam Estrin", "email")
        self.assertEqual([(o["verdict"], o["reason"], o["score"]) for o in out],
                         [("KEEP", "own writing", 5)] * 8 + [("KEEP", "own writing", 4)] * 2)
        self.assertEqual(rs.review(texts, "Sam Estrin"), out)

    def test_synthetic_model_output_shapes(self):
        cases = {
            "colon lead-in": "Here is what ChatGPT said:\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            # F1: a model or vendor name, or "model"/"assistant" before the response word.
            "vendor heading": "Mistral Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "model response heading": "Model Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "GPT heading": "GPT-4o Output\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "AI response heading": "AI Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "vendor AI heading": "Fireworks AI Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "vendor first heading": "AI21 Studio Response\n\n" + FILLERS[0] + "\n\n"
                                    + FILLERS[1],
            "assistant colon lead-in": "The assistant's answer:\n\n" + FILLERS[0] + "\n\n"
                                       + FILLERS[1],
            # Most of the words come before the lead-in, so only its short block decides.
            "prompt with a short block": PROSE.rsplit("\n\n", 1)[0]
                                         + "\n\nThe prompt:\nlist three fruits\nno prose\nkeep it short",
            # Lines the code rule above does not see (no "$ ", no closing brace).
            "code-like lines": "\n".join([
                "This is what came back from the call.",
                ">>> response = client.chat(model='small', messages=history, temperature=0)",
                '{"model": "small", "messages": [], "stream": false, "max_tokens": 256},',
                "curl -s https://example.com/v1/chat -H 'Accept: application/json' -d @body.json"]),
        }
        for name, text in cases.items():
            for mode in DOCUMENT_MODES:
                with self.subTest(name, mode=mode):
                    self.assertEqual(self.judge(text, mode)["reason"], "quoted model output")

    def test_model_words_in_prose_are_not_a_lead_in(self):
        cases = [
            # A colon inside a line, a long lead-in sentence, an ordinary heading.
            "My answer: ship it. " + FILLERS[0] + "\n\n" + FILLERS[1],
            "This is a long sentence that mentions the model and the prompt and ends with a colon:\n\n"
            + FILLERS[0],
            "Our Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            # F1: an ordinary section heading or a human lead-in names no model.
            "Incident Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "Customer Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "The short answer:\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "## Final Output\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "My reply:\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "Our business model:\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "Our AI roadmap:\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "Groq pricing:\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "A note to the AI:\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "Questions for the AI:\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            # A generic model word counts only right before the response word.
            "AI Incident Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "AI Safety Incident Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "Model Risk Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            "Bot Traffic Response\n\n" + FILLERS[0] + "\n\n" + FILLERS[1],
            # A paragraph that opens with a price is not a shell prompt.
            "$2,400 later, " + FILLERS[0] + " " + FILLERS[1] + "\n\n" + FILLERS[2],
            # A "...:" lead-in followed by sentences is not a quoted block.
            PROSE.rsplit("\n\n", 1)[0] + "\n\nThe prompt:\nI asked for a plan.\nIt gave one.\nI used it.",
        ]
        for text in cases:
            for mode in DOCUMENT_MODES:
                with self.subTest(text[:30], mode=mode):
                    self.assertEqual(self.judge(text, mode)["verdict"], "KEEP")

    def test_short_lines_without_digits_are_not_a_table(self):
        text = "Plan\n\nBuild\n\nShip\n\nRepeat\n\n" + FILLERS[0]
        for mode in DOCUMENT_MODES:
            with self.subTest(mode):
                self.assertNotEqual(self.judge(text, mode)["reason"], "table or numbers")

    def test_new_reasons_are_listed(self):
        self.assertIn("quoted model output", rs.REASONS)
        self.assertIn("table or numbers", rs.REASONS)


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
