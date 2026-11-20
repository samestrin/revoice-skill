"""The email golden test (Epic 19 T1, EST-7833; plan design 1).

Runs the email pipeline exactly as build.md does — extract-samples.py,
review-samples.py in its default mode, then build-profile.py against a
deterministic FakeAPI stub — over fixtures/sent.mbox, and pins the whole
index.csv and the whole profile JSON, byte for byte, as main writes them.
Every later Epic 19 task must keep this green: email output must not change.

The two run-dependent fields are frozen, not normalized away: the profile's
meta.generated date (a fixed date stands in for date.today()) and the API
address (a fixed URL; the FakeAPI stub answers in-process, so no socket is
opened and no port number can leak into the bytes). The golden files were
generated on unchanged main at e945f47. To regenerate them (only when a
change to email output is intended and approved), run run_pipeline() below
in a scratch directory and copy samples/index.csv and profile.json over
golden/email/.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from _load import BUILD, FIXTURES, GOLDEN, load, run_main

GOLDEN_EMAIL = GOLDEN / "email"
AUTHOR = "Alex Rivera"
SENDER = "alex@example.com"
KEY = "fake-key-for-the-golden-test"
API = "http://fake.api"
FEATURES = {"avg_sentence_length": 10.0, "contractions": 0.5}
BALANCE = 1_000_000


class FrozenDate(date):
    """date.today() for the profile's meta.generated, so the bytes are stable."""

    @classmethod
    def today(cls):
        return cls(2026, 11, 20)


class FakeAPI:
    """In-process stand-in for the text analysis API, with the same replies as
    the end-to-end test's HTTP fake. Records every call; opens no socket."""

    def __init__(self):
        self.requests = []
        self.credits = BALANCE

    def reply(self, path, body):
        self.requests.append((path, body))
        n = len(body["texts"])
        self.credits -= n
        if path == "/analyze/voice-profile":
            return ({"results": [{"feature_vector": dict(FEATURES), "summary": "s"}
                                 for _ in range(n)]}, self.credits)
        if path == "/analyze/fingerprint":
            return ({"distinctive_phrases": ["the hill route"], "first_person_patterns": [],
                     "informality": 0.2, "corpus_document_count": n}, self.credits)
        raise AssertionError(f"FakeAPI: unexpected path {path}")

    def health(self, url, timeout=None):
        self.requests.append(("/health", None))
        return io.BytesIO(json.dumps({"version": "9.9.9"}).encode())


def run_pipeline(work: Path):
    """The email pipeline over fixtures/sent.mbox; (index bytes, profile bytes, fake)."""
    env = {k: v for k, v in os.environ.items() if k != "TEXT_ANALYSIS_API_KEY"}
    for script, argv in (
        ("extract-samples.py", [str(FIXTURES / "sent.mbox"), "--from", SENDER,
                                "--min-words", "1", "-o", str(work / "samples")]),
        ("review-samples.py", ["--samples", str(work / "samples"), "--author", AUTHOR]),
    ):
        proc = subprocess.run([sys.executable, str(BUILD / script), *argv],
                              cwd=work, env=env, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise AssertionError(f"{script} failed:\n{proc.stdout}\n{proc.stderr}")

    bp = load(BUILD / "build-profile.py", "build_profile_golden")
    fake = FakeAPI()
    with mock.patch.object(bp, "post_with_balance",
                           lambda api, path, body, key: fake.reply(path, body)), \
         mock.patch.object(bp, "post",
                           lambda api, path, body, key: fake.reply(path, body)[0]), \
         mock.patch.object(bp.urllib.request, "urlopen", fake.health), \
         mock.patch.object(bp, "date", FrozenDate):
        run_main(bp, "--samples", str(work / "samples"), "--author", AUTHOR,
                 "--from", SENDER, "--api", API, "--api-key", KEY,
                 "-o", str(work / "profile.json"))
    return ((work / "samples" / "index.csv").read_bytes(),
            (work / "profile.json").read_bytes(), fake)


def check_bytes(test, actual: bytes, golden: Path):
    """The byte-for-byte pin. One changed byte fails it."""
    test.assertTrue(golden.is_file(), f"missing golden file: {golden}")
    test.assertEqual(actual, golden.read_bytes())


class EmailGoldenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.index_bytes, cls.profile_bytes, cls.fake = run_pipeline(Path(cls.tmp.name))

    def test_index_csv_matches_golden(self):
        check_bytes(self, self.index_bytes, GOLDEN_EMAIL / "index.csv")

    def test_profile_json_matches_golden(self):
        check_bytes(self, self.profile_bytes, GOLDEN_EMAIL / "profile.json")

    def test_one_byte_change_fails_the_pin(self):
        # The pin is byte-level, not semantic: flipping any single byte of the
        # golden output must fail check_bytes, and the unchanged bytes pass it.
        for name, actual in (("index.csv", self.index_bytes),
                             ("profile.json", self.profile_bytes)):
            with self.subTest(file=name):
                golden = GOLDEN_EMAIL / name
                check_bytes(self, actual, golden)  # known-good passes
                mutated = bytearray(golden.read_bytes())
                mutated[len(mutated) // 2] ^= 0x01
                with self.assertRaises(AssertionError):
                    check_bytes(self, bytes(mutated), golden)

    def test_pipeline_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            index, profile, _ = run_pipeline(Path(tmp))
        self.assertEqual(index, self.index_bytes)
        self.assertEqual(profile, self.profile_bytes)

    def test_fake_api_saw_the_whole_build(self):
        paths = [p for p, _ in self.fake.requests]
        self.assertEqual(paths, ["/analyze/voice-profile", "/analyze/voice-profile",
                                 "/analyze/fingerprint", "/health"])
        top = self.fake.requests[0][1]["texts"]
        self.assertEqual(len(top), 1)  # the joined top-N text
        profile = json.loads(self.profile_bytes)
        kept = profile["meta"]["samples"]["fingerprint_and_baseline"]
        self.assertEqual(len(self.fake.requests[1][1]["texts"]), kept)
        self.assertEqual(len(self.fake.requests[2][1]["texts"]), kept)
        self.assertEqual(BALANCE - self.fake.credits, 1 + kept + kept)


if __name__ == "__main__":
    unittest.main()
