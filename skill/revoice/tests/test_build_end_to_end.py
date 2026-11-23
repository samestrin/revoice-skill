"""Runs the build helpers in a row, as build.md does, against a fake API.

The email path runs mbox-filter-before.py, extract-samples.py,
review-samples.py and build-profile.py; the document paths run
extract-documents.py, review-samples.py --mode writing|brand and
build-profile.py --source-type writing|brand on synthetic documents the
tests generate (fictional authors, a fictional brand, .md, .html and .docx).

The fake is a standard-library HTTP server on 127.0.0.1, so nothing leaves
the machine and no real key is used. Each helper runs as a subprocess and
reads only what the step before it wrote, so renaming an output file or a
CSV column breaks this test.

RealRunEndToEndTest runs the same row on the real-run shapes (Epic 19.1 T2):
the guarded excerpts of the operator's 0.3.0 run, written into a temp folder
as .html, .docx, .pdf (through a stub pdftotext) and .md, with fictional
filler so every document clears the review's floor.
"""
import csv
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
import zipfile
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.sax.saxutils import escape

from _load import BUILD, FIXTURES, load, real_run, real_run_body

bp = load(BUILD / "build-profile.py", "build_profile_e2e")

KEY = "fake-key-for-the-end-to-end-test"
AUTHOR = "alex@example.com"
FEATURES = {"avg_sentence_length": 10.0, "contractions": 0.5}
# Far above any build cost, so the balance stop never triggers.
BALANCE = 1_000_000
METERED = ("/analyze/voice-profile", "/analyze/fingerprint")
# The columns each step promises the next one.
EXTRACT_COLUMNS = ["file", "date", "words", "subject"]
REVIEW_COLUMNS = ["verdict", "score", "reason"]
# Documents also get what was cut out of each passage (EST-8273); email samples are never cut.
DOC_REVIEW_COLUMNS = REVIEW_COLUMNS + ["cut"]


class FakeAPI(BaseHTTPRequestHandler):
    """Answers like the text analysis API; records every request on the server."""

    def log_message(self, *args):  # keep the test output quiet
        pass

    def reply(self, data: dict, headers: dict) -> None:
        raw = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.server.requests.append({"path": self.path, "body": None, "key": None})
        if self.path != "/health":
            self.send_error(404)
            return
        self.reply({"version": "9.9.9"}, {})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(
            {"path": self.path, "body": body, "key": self.headers.get("X-API-Key")})
        if self.path not in METERED:
            self.send_error(404)
            return
        n = len(body["texts"])
        with self.server.lock:
            self.server.credits -= n
            left = self.server.credits
        if self.path == "/analyze/voice-profile":
            data = {"results": [{"feature_vector": dict(FEATURES), "summary": "s"}
                                for _ in range(n)]}
        else:
            data = {"distinctive_phrases": ["the hill route"], "first_person_patterns": [],
                    "informality": 0.2, "corpus_document_count": n}
        self.reply(data, {"X-Credits-Charged": str(n), "X-Credits-Remaining": str(left)})


class EndToEndBase(unittest.TestCase):
    """The fake API server, a temp HOME and key file, and subprocess helpers."""

    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAPI)
        self.server.requests = []
        self.server.credits = BALANCE
        self.server.lock = threading.Lock()
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.api = f"http://127.0.0.1:{self.server.server_address[1]}"

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        # A fresh HOME and no key or proxy in the environment: the build can
        # only use the temp key file and can only reach the loopback server.
        home = self.work / "home"
        home.mkdir()
        self.env = {k: v for k, v in os.environ.items()
                    if k != "TEXT_ANALYSIS_API_KEY" and not k.lower().endswith("_proxy")}
        self.env.update(HOME=str(home), USERPROFILE=str(home), NO_PROXY="*", no_proxy="*")
        self.key_file = self.work / "api-key"
        self.key_file.write_text(KEY + "\n", encoding="utf-8")

    def run_helper_proc(self, script: str, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(BUILD / script), *argv], cwd=self.work,
                              env=self.env, capture_output=True, text=True, timeout=120)

    def run_helper(self, script: str, *argv: str) -> str:
        proc = self.run_helper_proc(script, *argv)
        self.assertEqual(proc.returncode, 0,
                         f"{script} failed:\n{proc.stdout}\n{proc.stderr}")
        return proc.stdout

    def read_index(self, folder: str) -> tuple[list[str], list[dict]]:
        with open(self.work / folder / "index.csv", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader.fieldnames or []), list(reader)


class BuildEndToEndTest(EndToEndBase):

    def test_filter_extract_review_build(self):
        # One export holding both fixture mailboxes, as a user's export would.
        mbox = self.work / "export.mbox"
        mbox.write_bytes(b"".join((FIXTURES / name).read_bytes()
                                  for name in ("sent.mbox", "conversation.mbox")))

        # Phase 2: filter and extract (the fixture messages are short).
        self.run_helper("mbox-filter-before.py", "export.mbox", "--before", "2022-09-01",
                        "-o", "pre-ai.mbox")
        self.assertTrue((self.work / "pre-ai.mbox").is_file())
        self.run_helper("extract-samples.py", "pre-ai.mbox", "--from", AUTHOR,
                        "--min-words", "1", "-o", "samples")
        self.run_helper("extract-samples.py", "pre-ai.mbox", "--from", AUTHOR,
                        "--min-words", "1", "--others", "-o", "reference")
        columns, rows = self.read_index("samples")
        self.assertEqual(columns, EXTRACT_COLUMNS)
        self.assertTrue(rows)
        for row in rows:
            self.assertTrue((self.work / "samples" / row["file"]).is_file(), row["file"])
        reference = sorted((self.work / "reference").glob("*.md"))
        self.assertTrue(reference)

        # Phase 4: review adds its columns and keeps the rows.
        self.run_helper("review-samples.py", "--author", "Alex Rivera")
        columns, reviewed = self.read_index("samples")
        self.assertEqual(columns, EXTRACT_COLUMNS + REVIEW_COLUMNS)
        self.assertEqual([r["file"] for r in reviewed], [r["file"] for r in rows])
        kept = [r["file"] for r in reviewed if r["verdict"] == "KEEP"]
        self.assertTrue(kept)

        # Phase 5: build against the fake API with the temp key file.
        out = self.run_helper("build-profile.py", "--samples", "samples",
                              "--reference", "reference", "--author", "Alex Rivera",
                              "--from", AUTHOR, "--cutoff", "2022-09-01",
                              "--api", self.api, "--api-key-file", str(self.key_file),
                              "-o", "voice-profile.json")
        cost = bp.build_cost(len(kept), len(reference))
        self.assertIn(f"this build costs {cost} credits", out)

        profile = json.loads((self.work / "voice-profile.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(profile),
                         ["comparison", "fingerprint", "meta", "voice_profile"])
        self.assertEqual(profile["meta"]["author"], "Alex Rivera")
        self.assertEqual(profile["meta"]["api"], {"url": self.api, "version": "9.9.9"})
        self.assertEqual(sorted(profile["meta"]["samples"]["voice_profile"]), sorted(kept))
        self.assertEqual(profile["meta"]["samples"]["fingerprint_and_baseline"], len(kept))
        self.assertEqual(profile["meta"]["reference"]["count"], len(reference))

        # The server was charged exactly the texts build_cost() predicts.
        requests = self.server.requests
        metered = [r for r in requests if r["path"] in METERED]
        self.assertEqual(sum(len(r["body"]["texts"]) for r in metered), cost)
        self.assertEqual(BALANCE - self.server.credits, cost)
        self.assertEqual({r["key"] for r in metered}, {KEY})
        fingerprint = [r for r in requests if r["path"] == "/analyze/fingerprint"]
        self.assertEqual(len(fingerprint), 1)
        self.assertEqual(len(fingerprint[0]["body"]["texts"]), len(kept))
        self.assertEqual(len(fingerprint[0]["body"]["options"]["reference_texts"]),
                         len(reference))
        self.assertEqual([r["path"] for r in requests if r["path"] not in METERED],
                         ["/health"])

    def test_sample_the_user_drops_by_hand_is_never_sent(self):
        # build.md stops after phase 4 so the user can open the samples and set a
        # row's verdict to DROP in samples/index.csv before anything is sent.
        mbox = self.work / "export.mbox"
        mbox.write_bytes((FIXTURES / "sent.mbox").read_bytes())
        self.run_helper("mbox-filter-before.py", "export.mbox", "--before", "2022-09-01",
                        "-o", "pre-ai.mbox")
        self.run_helper("extract-samples.py", "pre-ai.mbox", "--from", AUTHOR,
                        "--min-words", "1", "-o", "samples")
        self.run_helper("review-samples.py", "--author", "Alex Rivera")
        columns, rows = self.read_index("samples")
        kept = [r["file"] for r in rows if r["verdict"] == "KEEP"]
        self.assertGreaterEqual(len(kept), 2)

        # The user's edit: one KEEP row changed to DROP, nothing else touched.
        dropped = kept[0]
        for row in rows:
            if row["file"] == dropped:
                row["verdict"] = "DROP"
        with open(self.work / "samples" / "index.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        left = kept[1:]
        cost = bp.build_cost(len(left), 0)

        # The free estimate counts only the rows still KEEP.
        out = self.run_helper("build-profile.py", "--estimate", "--samples", "samples")
        self.assertIn(f"estimated cost: {cost} credits ({len(left)} samples,", out)

        out = self.run_helper("build-profile.py", "--samples", "samples",
                              "--author", "Alex Rivera", "--from", AUTHOR,
                              "--api", self.api, "--api-key-file", str(self.key_file),
                              "-o", "voice-profile.json")
        self.assertIn(f"this build costs {cost} credits", out)

        dropped_text = bp.body(self.work / "samples" / dropped)
        self.assertTrue(dropped_text)
        sent = []
        for r in self.server.requests:
            if r["body"]:
                sent += r["body"]["texts"] + r["body"].get("options", {}).get("reference_texts", [])
        self.assertTrue(sent)
        for text in sent:
            self.assertNotIn(dropped_text, text)
        self.assertEqual(BALANCE - self.server.credits, cost)
        profile = json.loads((self.work / "voice-profile.json").read_text(encoding="utf-8"))
        self.assertNotIn(dropped, profile["meta"]["samples"]["voice_profile"])
        self.assertEqual(profile["meta"]["samples"]["fingerprint_and_baseline"], len(left))


# The document paths: fictional people and a fictional brand, so no real
# writing is ever needed. Each document draws its nouns from its own bank,
# so no two documents (and no two passages) share half their word 5-grams.
WRITING_AUTHOR = "Mira Holt"
GUEST = "Theo Vane"
BRAND = "Larkfield"
BRAND_AUTHORS = ["Ada Fen", "Bo Marsh", "Cy Quill"]
DOC_COLUMNS = EXTRACT_COLUMNS + ["source"]

BANKS = [
    "harbor lantern rope tide gull pier".split(),
    "orchard ladder apple basket prune graft".split(),
    "kettle copper steam tray spoon cloth".split(),
    "meadow clover fence stile thistle lark".split(),
    "quarry slate chisel dust crane ledge".split(),
    "attic trunk quilt hinge rafter pane".split(),
    "cellar barrel chalk shelf cobweb brick".split(),
    "trellis bean mulch trowel seed row".split(),
    "mill flour sack wheel chute grain".split(),
    "ferry ticket deck horn wake rail".split(),
    "forge anvil bellows tongs ember scale".split(),
    "loft hay owl beam hatch bale".split(),
]
TEMPLATES = [
    "we walked past the {a} while the {b} was quiet, and I wrote about the {c} in my note.",
    "the {a} reminds me of a morning when the {b} stood open and the {c} caught the first light.",
    "if you look at the {a} from the far side, the {b} seems smaller, but the {c} still tells the story.",
    "our plan was to move the {a} before the rain, yet the {b} held us back and the {c} waited.",
    "she kept the {a} near the door, so the {b} stayed dry, and the {c} was easy to find again.",
    "there is a kind of patience in the {a}, and the {b} teaches it better than the {c} ever could.",
    "after the long winter the {a} looked new, the {b} had settled, and the {c} was ready for the spring.",
    "I asked about the {a} twice, but the answer came from the {b} instead, and the {c} proved it.",
]
CONNECTIVES = ["Later,", "Meanwhile,", "In time,", "That week,",
               "Afterwards,", "Some days,", "In spring,", "Even so,"]
ADJECTIVES = ["old", "new", "wide", "narrow", "low", "tall", "dry", "wet"]


def doc_paragraph(d: int, p: int, sentences: int = 4) -> str:
    """One prose paragraph (~100 words) of document d; ordinary English function
    words, no lists, tables, code or contact lines, a full stop at every end.
    The connective and the adjective are the paragraph's own, so no two
    paragraphs repeat a sentence and the dedupe keeps every passage."""
    bank, adj = BANKS[d], ADJECTIVES[p % len(ADJECTIVES)]
    out = []
    for s in range(sentences):
        t = TEMPLATES[(p * 4 + s) % len(TEMPLATES)]
        i = (p * 7 + s * 3) % len(bank)
        out.append(CONNECTIVES[p % len(CONNECTIVES)] + " "
                   + t.format(a=f"{adj} {bank[i]}", b=f"{adj} {bank[(i + 2) % len(bank)]}",
                              c=f"{adj} {bank[(i + 4) % len(bank)]}"))
    return " ".join(out)


def docx_bytes(paragraphs: list[str]) -> bytes:
    """A minimal .docx: one w:p per string, nothing else the reader needs.
    A string opening with "# " marks becomes a Word Heading style, the way
    a heading is saved in a real .docx."""
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def one(p: str) -> str:
        m = re.match(r"(#{1,6})\s+(.*)\Z", p, re.S)
        style = (f'<w:pPr><w:pStyle w:val="Heading{len(m.group(1))}"/></w:pPr>'
                 if m else "")
        text = m.group(2) if m else p
        return f'<w:p>{style}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'

    body = "".join(one(p) for p in paragraphs)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>'
           f'<w:document xmlns:w="{w}"><w:body>{body}</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def write_documents(folder: Path, mode: str, docs: int = 12, paragraphs: int = 8,
                    bylines: bool = True) -> None:
    """Generate the synthetic corpus: 4 .md, 4 .html, 4 .docx (in that order).

    writing: every document is the author's; one carries her byline and one a
    guest's. brand: three documents carry three different authors' bylines.
    With paragraphs=1 each document is about 100 words: under the 150-word
    passage floor, kept whole, one sample per document.
    """
    folder.mkdir()
    for d in range(docs):
        title = f"Field notes {d}" if mode == "writing" else f"{BRAND} guide {d}"
        paras = [doc_paragraph(d, p) for p in range(paragraphs)]
        if bylines:
            byline = ({0: f"By {WRITING_AUTHOR}", 1: f"By {GUEST}"}.get(d)
                      if mode == "writing"
                      else f"By {BRAND_AUTHORS[d]}" if d < len(BRAND_AUTHORS) else None)
            if byline:
                paras = [byline] + paras
        stem = f"piece-{d:02d}"
        if d < 4:
            front = f'---\ntitle: "{title}"\ndate: 2019-0{d + 1}-15\n---\n\n'
            (folder / f"{stem}.md").write_text(front + "\n\n".join(paras) + "\n",
                                               encoding="utf-8")
        elif d < 8:
            page = (f"<html><head><title>{title}</title></head><body>"
                    "<nav>Home About Contact</nav>"
                    + "".join(f"<p>{p}</p>" for p in paras)
                    + f"<footer>\u00a9 2019 {BRAND}. All rights reserved.</footer>"
                    "</body></html>")
            (folder / f"{stem}.html").write_text(page, encoding="utf-8")
        else:
            (folder / f"{stem}.docx").write_bytes(docx_bytes(paras))


class DocumentsEndToEndTest(EndToEndBase):
    """extract-documents.py -> review-samples.py --mode -> build-profile.py
    --source-type, once as writing and once as brand, against the fake API."""

    def run_pipeline(self, mode: str, folder: str = "docs",
                     samples: str = "samples") -> tuple[str, list[dict], list[dict]]:
        author = WRITING_AUTHOR if mode == "writing" else BRAND
        write_documents(self.work / folder, mode)
        self.run_helper("extract-documents.py", folder, "-o", samples)
        columns, rows = self.read_index(samples)
        self.assertEqual(columns, DOC_COLUMNS)
        self.assertEqual(len({r["source"] for r in rows}), 12)
        self.assertGreaterEqual(len(rows), 20)
        for r in rows:
            text = (self.work / samples / r["file"]).read_text(encoding="utf-8")
            self.assertTrue((self.work / samples / r["file"]).is_file())
            self.assertNotIn("All rights reserved", text)  # the HTML footer
            self.assertNotIn("Home About Contact", text)  # the HTML nav
        review = self.run_helper("review-samples.py", "--samples", samples,
                                 "--mode", mode, "--author", author)
        columns, reviewed = self.read_index(samples)
        self.assertEqual(columns, DOC_COLUMNS + DOC_REVIEW_COLUMNS)
        self.assertEqual([r["file"] for r in reviewed], [r["file"] for r in rows])
        kept = [r for r in reviewed if r["verdict"] == "KEEP"]
        self.assertGreaterEqual(len(kept), 20)  # above the minimum: no warning
        self.assertIn(f"coverage: {len(kept)} KEEP passages from 12 documents", review)
        self.assertNotIn("below the minimum", review)
        return author, reviewed, kept

    def build_and_check(self, mode: str, author: str, kept: list[dict], samples: str,
                        out: str, dropped: str | None = None) -> dict:
        """Build against the fake API; assert the cost, the requests and the meta.

        dropped: a file the test marked DROP by hand; its body must not be sent.
        """
        mark = len(self.server.requests)
        before = self.server.credits
        stdout = self.run_helper("build-profile.py", "--samples", samples,
                                 "--author", author, "--source-type", mode,
                                 "--api", self.api, "--api-key-file", str(self.key_file),
                                 "-o", out)
        cost = bp.build_cost(len(kept), 0)
        self.assertIn(f"this build costs {cost} credits "
                      f"({len(kept)} samples, 0 reference texts)", stdout)

        profile = json.loads((self.work / out).read_text(encoding="utf-8"))
        meta = profile["meta"]
        if mode == "writing":
            source = "writing samples (12 documents), reviewed passages"
        else:
            source = "brand documents (12 documents, several authors), reviewed passages"
        self.assertEqual(meta["source"], source)
        self.assertEqual(meta["source_type"], mode)
        self.assertEqual(meta["author"], author)
        self.assertEqual(meta["sender_addresses"], [])
        self.assertEqual(meta["reference"], {"description": "none", "count": 0})
        self.assertEqual(meta["api"], {"url": self.api, "version": "9.9.9"})
        files = [r["file"] for r in kept]
        self.assertEqual(len(meta["samples"]["voice_profile"]), min(15, len(kept)))
        self.assertLessEqual(set(meta["samples"]["voice_profile"]), set(files))
        self.assertEqual(meta["samples"]["fingerprint_and_baseline"], len(kept))

        # The server was charged exactly the texts build_cost() predicts.
        requests = self.server.requests[mark:]
        metered = [r for r in requests if r["path"] in METERED]
        self.assertEqual(sum(len(r["body"]["texts"]) for r in metered), cost)
        self.assertEqual(before - self.server.credits, cost)
        self.assertEqual({r["key"] for r in metered}, {KEY})
        self.assertEqual([r["path"] for r in requests if r["path"] not in METERED],
                         ["/health"])
        fingerprint = [r for r in requests if r["path"] == "/analyze/fingerprint"]
        self.assertEqual(len(fingerprint), 1)
        self.assertEqual(len(fingerprint[0]["body"]["texts"]), len(kept))
        self.assertNotIn("options", fingerprint[0]["body"])  # no reference set
        if dropped is not None:
            self.assertNotIn(dropped, meta["samples"]["voice_profile"])
            dropped_text = bp.body(self.work / samples / dropped)
            self.assertTrue(dropped_text)
            for r in metered:
                for text in r["body"]["texts"]:
                    self.assertNotIn(dropped_text, text)
        return profile

    def test_writing_pipeline(self):
        author, reviewed, kept = self.run_pipeline("writing")
        # The author's own byline is hers; the guest's passage is dropped.
        own = [r for r in reviewed
               if bp.body(self.work / "samples" / r["file"]).startswith(f"By {WRITING_AUTHOR}")]
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]["verdict"], "KEEP")
        guest = [r for r in reviewed
                 if bp.body(self.work / "samples" / r["file"]).startswith(f"By {GUEST}")]
        self.assertEqual(len(guest), 1)
        self.assertEqual(guest[0]["verdict"], "DROP")
        self.assertEqual(guest[0]["reason"], "written by someone else")
        self.build_and_check("writing", author, kept, "samples", "voice-profile.json")

    def test_brand_pipeline(self):
        author, reviewed, kept = self.run_pipeline("brand")
        # Several authors is the point: every byline is kept.
        for name in BRAND_AUTHORS:
            rows = [r for r in reviewed
                    if bp.body(self.work / "samples" / r["file"]).startswith(f"By {name}")]
            self.assertEqual(len(rows), 1, name)
            self.assertEqual(rows[0]["verdict"], "KEEP", name)
        self.assertNotIn("written by someone else", {r["reason"] for r in reviewed})
        self.build_and_check("brand", author, kept, "samples", "voice-profile.json")

    def test_sample_the_user_drops_by_hand_is_never_sent(self):
        # The phase 4 approval pause: the user may set a row's verdict to DROP
        # in samples/index.csv before anything is sent, in either mode.
        for mode in ("writing", "brand"):
            with self.subTest(mode=mode):
                samples = f"samples-{mode}"
                author, reviewed, kept = self.run_pipeline(
                    mode, folder=f"docs-{mode}", samples=samples)
                self.assertGreaterEqual(len(kept), 2)
                dropped = kept[0]["file"]
                columns, rows = self.read_index(samples)
                for row in rows:
                    if row["file"] == dropped:
                        row["verdict"] = "DROP"
                with open(self.work / samples / "index.csv", "w", newline="",
                          encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(rows)
                left = kept[1:]
                cost = bp.build_cost(len(left), 0)
                out = self.run_helper("build-profile.py", "--estimate", "--samples", samples)
                self.assertIn(f"estimated cost: {cost} credits ({len(left)} samples,", out)
                self.build_and_check(mode, author, left, samples, f"profile-{mode}.json",
                                     dropped=dropped)

    def test_below_the_floor_stops_at_the_review(self):
        # 8 documents of about 100 words: one passage each, under the floor of
        # 10 KEEP passages. The review exits 3 and nothing is ever sent.
        for mode in ("writing", "brand"):
            with self.subTest(mode=mode):
                folder, samples = f"short-{mode}", f"short-samples-{mode}"
                write_documents(self.work / folder, mode, docs=8, paragraphs=1,
                                bylines=False)
                self.run_helper("extract-documents.py", folder, "-o", samples)
                columns, rows = self.read_index(samples)
                self.assertEqual(columns, DOC_COLUMNS)
                self.assertEqual(len(rows), 8)
                for r in rows:  # under 150 words, kept whole from 60
                    self.assertGreaterEqual(int(r["words"]), 60)
                    self.assertLess(int(r["words"]), 150)
                proc = self.run_helper_proc("review-samples.py", "--samples", samples,
                                            "--mode", mode, "--author", WRITING_AUTHOR)
                self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
                self.assertIn("coverage: 8 KEEP passages from 8 documents", proc.stdout)
                self.assertIn("below the floor", proc.stderr)
                # index.csv is still written, so the verdicts can be read.
                columns, reviewed = self.read_index(samples)
                self.assertEqual(columns, DOC_COLUMNS + DOC_REVIEW_COLUMNS)
                self.assertTrue(all(r["verdict"] == "KEEP" for r in reviewed))
        self.assertEqual(self.server.requests, [])


# The real-run shapes (Epic 19.1 T2): the operator's 0.3.0 run read 5 sources
# that are 3 distinct articles (tests/fixtures/real_run/README.md). The guarded
# excerpts are too short alone (3 articles give 3 passages, under the review's
# floor of 10), so each temporary article carries its real excerpts first, then
# unique fictional paragraphs in the doc_paragraph() style: enough for at least
# 5 KEEP passages per distinct document. Every file draws its filler from its
# own noun banks, so no two passages share half their word 5-grams.
REAL_AUTHOR = "Sam Estrin"
ICON_WORDS = ("arrow_forward", "smart_toy", "verified_user", "hub", "lock", "public")
# The terminal widget of brand_icons_widgets.html, line for line: on a page
# with icon fonts it is chrome, never prose.
WIDGET = """<div class="terminal-widget">
<div class="terminal-title">estrin-lab :: status</div>
<div class="terminal-line">ONLINE</div>
<div class="terminal-line">[01] :: PRIVATE LAB 17 MACHINES</div>
<div class="terminal-line">&gt; Linux | macOS | Windows</div>
<div class="terminal-line">&gt; KVM + UTM virtual machines | Docker</div>
<div class="terminal-line">&gt; 10GbE local backbone | 1GbE internet uplink</div>
<div class="terminal-line">[02] :: POWER PROTECTED</div>
<div class="terminal-line">&gt; multiple UPS groups | solar battery backup</div>
<div class="terminal-line">&gt; auto-shutdown on power loss</div>
</div>"""
LLM_OUTPUTS = ("llm_output_docx_a", "llm_output_docx_b", "llm_output_pdf_a")
# The Word copy's section headings: plain lines in the extracted-text fixture,
# Heading styles in the .docx the fixture was extracted from.
DOCX_HEADINGS = {"The Real Winner?", "Which Would I Avoid?",
                 "Why Is jamba-instruct Tested Twice?", "Reproducing My Comparison"}


def llm_answer_snippets() -> dict[str, list[str]]:
    """Ten-word runs from every quoted answer in each LLM-output fixture
    (hard line wraps normalised), so a KEEP passage holding any part of an
    answer is caught wherever a passage boundary falls."""
    out = {}
    for name in LLM_OUTPUTS:
        snips = []
        for block in real_run_body(name + ".md").split("\n\n"):
            ws = block.split()
            if len(ws) >= 12:
                snips.append(" ".join(ws[:10]))
            if len(ws) >= 24:
                snips.append(" ".join(ws[12:22]))
        out[name] = snips
    return out


class RealRunEndToEndTest(EndToEndBase):
    """The real-run shapes through extract-documents.py, review-samples.py
    --mode writing and build-profile.py --source-type writing: one article
    saved as .html, .docx and .pdf is one document, quoted model output and
    table text never reach KEEP, icon words never reach a sample, and the
    15 profile samples come from every document."""

    # Filler noun banks per file: no bank is used twice, so every fictional
    # paragraph is its own (the 12 banks of write_documents(), 8 each).
    BANKS = {"html": (0, 1), "docx": (2, 3), "pdf": (4, 5),
             "faster": (6, 7, 8), "llmenv": (9, 10, 11)}

    def filler(self, kind: str) -> list[str]:
        return [doc_paragraph(d, p) for d in self.BANKS[kind] for p in range(8)]

    def pdftotext_stub(self, text: str) -> None:
        """A fake pdftotext first on PATH: it prints the article's text layer
        (the copy_article_pdf.txt hard wraps kept), so no PDF is parsed and
        nothing leaves the machine."""
        bindir = self.work / "bin"
        bindir.mkdir()
        layer = self.work / "pdf-text.txt"
        layer.write_text(text, encoding="utf-8")
        stub = bindir / "pdftotext"
        stub.write_text(f'#!/bin/sh\nexec cat "{layer}"\n', encoding="utf-8")
        stub.chmod(0o755)
        self.env["PATH"] = f"{bindir}{os.pathsep}{self.env.get('PATH', '')}"

    def write_real_documents(self, folder: Path) -> None:
        """The 5 sources of the real run: article 1 as .html (the URL copy,
        with the icon spans and the terminal widget such a page carries),
        .docx (built with zipfile, carrying the quoted responses and the
        results table) and .pdf (through the pdftotext stub); articles 2 and
        3 as .md. Real excerpts first, then the file's own filler."""
        folder.mkdir()

        def blocks(name: str) -> list[str]:
            return real_run_body(name).split("\n\n")

        # The URL copy as HTML: the reader must drop the icon-font spans, the
        # widget, the nav and the footer, and keep the article's paragraphs
        # word for word, so the copies still dedupe into one document.
        title = real_run("copy_article_html.md").partition("\n")[0][2:]
        paras = blocks("copy_article_html.md")
        icons = iter(ICON_WORDS[1:])
        page = ["<html><head><title>" + escape(title) + "</title></head><body>",
                "<nav>Home About Contact</nav>",
                '<a class="cta" href="#responses">Jump to the responses '
                '<span class="material-symbols-outlined" aria-hidden="true">'
                "arrow_forward</span></a>"]
        for i, p in enumerate(paras):
            if i < 5:
                page.append(f'<p><span class="material-symbols-outlined" '
                            f'aria-hidden="true">{next(icons)}</span> {escape(p)}</p>')
            else:
                page.append(f"<p>{escape(p)}</p>")
        # The widget and one span per icon word sit on filler unique to this
        # copy: the article paragraphs above dedupe against the PDF, so an
        # icon there would never reach a kept sample. On kept filler the
        # icon and widget assertions fail if _hidden() or drop_widget()
        # stop dropping them.
        for i, p in enumerate(self.filler("html")):
            if i == 2:
                page.append(WIDGET)
            if i < len(ICON_WORDS):
                page.append(f'<p><span class="material-symbols-outlined" '
                            f'aria-hidden="true">{ICON_WORDS[i]}</span> {escape(p)}</p>')
            else:
                page.append(f"<p>{escape(p)}</p>")
        page.append(f"<footer>\u00a9 2019 {REAL_AUTHOR}. All rights reserved.</footer>")
        page.append("</body></html>")
        (folder / "comparing13.html").write_text("".join(page), encoding="utf-8")

        # The Word copy: the article text, the one-cell-per-line results
        # table and the quoted model responses it carries, then filler.
        docx = ([real_run("copy_article_docx.md").partition("\n")[0]]
                + ["# " + b if b in DOCX_HEADINGS else b
                   for b in blocks("copy_article_docx.md")]
                + blocks("table_docx_numbers.md")
                + blocks("llm_output_docx_a.md")
                + blocks("llm_output_docx_b.md")
                + self.filler("docx"))
        (folder / "comparing13.docx").write_bytes(docx_bytes(docx))

        # The PDF copy: pdftotext text with its hard wraps, a page break
        # between pages, the quoted responses and filler wrapped the same way.
        pdf = (real_run("copy_article_pdf.txt") + "\f"
               + real_run_body("llm_output_pdf_a.md") + "\f"
               + "\n\n".join(textwrap.fill(p, 78) for p in self.filler("pdf")) + "\f")
        self.pdftotext_stub(pdf)
        (folder / "comparing13.pdf").write_bytes(b"%PDF-1.4 stub: read by the pdftotext on PATH")

        # The other two articles, each its own document.
        for stem, names in (("faster", ("prose_72faster_a.md", "prose_72faster_b.md")),
                            ("llmenv", ("prose_llmenv_a.md", "prose_llmenv_b.md"))):
            title = real_run(names[0]).partition("\n")[0][2:]
            paras = [real_run_body(n) for n in names] + self.filler(stem)
            front = f'---\ntitle: "{title}"\ndate: 2019-06-15\n---\n\n'
            (folder / f"{stem}.md").write_text(front + "\n\n".join(paras) + "\n",
                                               encoding="utf-8")

    @unittest.skipIf(os.name == "nt", "the pdftotext stub is a shell script")
    def test_real_run_writing_pipeline(self):
        self.write_real_documents(self.work / "real-docs")

        # Phase 2: the 5 sources are read as 3 distinct documents.
        out = self.run_helper("extract-documents.py", "real-docs", "-o", "samples")
        self.assertIn("read 5 documents (3 distinct), wrote", out)
        columns, rows = self.read_index("samples")
        self.assertEqual(columns, DOC_COLUMNS)
        self.assertEqual(len({r["source"] for r in rows}), 3)
        for r in rows:
            self.assertTrue((self.work / "samples" / r["file"]).is_file())
            text = (self.work / "samples" / r["file"]).read_text(encoding="utf-8")
            # No icon word and no widget line survives into any sample.
            for icon in ICON_WORDS:
                self.assertNotRegex(text, rf"\b{icon}\b", (icon, r["file"]))
            for widget in ("estrin-lab", "ONLINE", "PRIVATE LAB", "KVM", "UPS",
                           "auto-shutdown", "> "):
                self.assertNotIn(widget, text, (widget, r["file"]))
            self.assertNotIn("All rights reserved", text)
            self.assertNotIn("Home About Contact", text)

        # Phase 4: the review keeps at least 5 passages per document, drops
        # the quoted model output and the table, and warns (3 documents is
        # below the minimum of 5) without stopping (above the floor of 10).
        review = self.run_helper("review-samples.py", "--samples", "samples",
                                 "--mode", "writing", "--author", REAL_AUTHOR)
        columns, reviewed = self.read_index("samples")
        self.assertEqual(columns, DOC_COLUMNS + DOC_REVIEW_COLUMNS)
        self.assertEqual([r["file"] for r in reviewed], [r["file"] for r in rows])
        kept = [r for r in reviewed if r["verdict"] == "KEEP"]
        by_doc = Counter(r["source"] for r in kept)
        self.assertEqual(len(by_doc), 3)
        for source, n in by_doc.items():
            self.assertGreaterEqual(n, 5, source)
        self.assertIn(f"coverage: {len(kept)} KEEP passages from 3 documents\n", review)
        self.assertIn("below the minimum for writing: 20 KEEP passages from 5 documents "
                      "give a stronger profile; this one will be weaker", review)
        self.assertNotIn("below the floor", review)
        self.assertIn("quoted model output", review)
        self.assertIn("table or numbers", review)
        snippets = llm_answer_snippets()
        self.assertTrue(all(snippets.values()))
        # Every fixture's quoted answers reached the review and were dropped
        # there, so the KEEP check below is not vacuous.
        dropped_bodies = [" ".join(bp.body(self.work / "samples" / r["file"]).split())
                          for r in reviewed if r["verdict"] == "DROP"]
        for name, snips in snippets.items():
            self.assertTrue(any(s in b for s in snips for b in dropped_bodies), name)
        for r in kept:
            body = " ".join(bp.body(self.work / "samples" / r["file"]).split())
            for snips in snippets.values():
                for snippet in snips:
                    self.assertNotIn(snippet, body, (snippet, r["file"]))

        # Phase 5: the build against the fake API. The 15 profile samples
        # come from every document, none above ceil(15 / documents).
        out = self.run_helper("build-profile.py", "--samples", "samples",
                              "--author", REAL_AUTHOR, "--source-type", "writing",
                              "--api", self.api, "--api-key-file", str(self.key_file),
                              "-o", "voice-profile.json")
        cost = bp.build_cost(len(kept), 0)
        self.assertIn(f"this build costs {cost} credits "
                      f"({len(kept)} samples, 0 reference texts)", out)
        profile = json.loads((self.work / "voice-profile.json").read_text(encoding="utf-8"))
        meta = profile["meta"]
        self.assertEqual(meta["source"], "writing samples (3 documents), reviewed passages")
        self.assertEqual(meta["source_type"], "writing")
        self.assertEqual(meta["author"], REAL_AUTHOR)
        self.assertEqual(meta["reference"], {"description": "none", "count": 0})
        self.assertEqual(meta["api"], {"url": self.api, "version": "9.9.9"})
        top = meta["samples"]["voice_profile"]
        self.assertEqual(len(top), 15)
        self.assertLessEqual(set(top), {r["file"] for r in kept})
        source_of = {r["file"]: r["source"] for r in reviewed}
        top_counts = Counter(source_of[f] for f in top)
        self.assertEqual(set(top_counts), set(by_doc))  # none missing
        per_doc = math.ceil(15 / len(by_doc))
        for source, n in top_counts.items():
            self.assertLessEqual(n, per_doc, source)
        self.assertEqual(meta["samples"]["fingerprint_and_baseline"], len(kept))

        # The stub was told to read exactly those 15 samples, and was charged
        # exactly the texts build_cost() predicts; only loopback was reached.
        requests = self.server.requests
        voice = [r for r in requests if r["path"] == "/analyze/voice-profile"]
        self.assertEqual(voice[0]["body"]["texts"],
                         ["\n\n".join(bp.body(self.work / "samples" / f) for f in top)])
        metered = [r for r in requests if r["path"] in METERED]
        self.assertEqual(sum(len(r["body"]["texts"]) for r in metered), cost)
        self.assertEqual(BALANCE - self.server.credits, cost)
        self.assertEqual({r["key"] for r in metered}, {KEY})
        fingerprint = [r for r in requests if r["path"] == "/analyze/fingerprint"]
        self.assertEqual(len(fingerprint), 1)
        self.assertEqual(len(fingerprint[0]["body"]["texts"]), len(kept))
        self.assertNotIn("options", fingerprint[0]["body"])  # no reference set
        self.assertEqual([r["path"] for r in requests if r["path"] not in METERED],
                         ["/health"])


if __name__ == "__main__":
    unittest.main()
