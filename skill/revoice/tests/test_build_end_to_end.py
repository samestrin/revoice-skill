"""Runs the four build helpers in a row, as build.md does, against a fake API.

The fake is a standard-library HTTP server on 127.0.0.1, so nothing leaves
the machine and no real key is used. Each helper runs as a subprocess and
reads only what the step before it wrote, so renaming an output file or a
CSV column breaks this test.
"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from _load import BUILD, FIXTURES, load

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


class BuildEndToEndTest(unittest.TestCase):

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

    def run_helper(self, script: str, *argv: str) -> str:
        proc = subprocess.run([sys.executable, str(BUILD / script), *argv], cwd=self.work,
                              env=self.env, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0,
                         f"{script} failed:\n{proc.stdout}\n{proc.stderr}")
        return proc.stdout

    def read_index(self, folder: str) -> tuple[list[str], list[dict]]:
        with open(self.work / folder / "index.csv", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader.fieldnames or []), list(reader)

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


if __name__ == "__main__":
    unittest.main()
