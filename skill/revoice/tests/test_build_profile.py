import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from _load import BUILD, load, run_main

bp = load(BUILD / "build-profile.py", "build_profile")

FEATURES = {"avg_sentence_length": 10.0, "contractions": 0.5}


METERED = ("/analyze/voice-profile", "/analyze/fingerprint")


class FakeReply(io.BytesIO):
    """A urlopen reply: a body plus response headers."""

    def __init__(self, data: bytes, headers: dict):
        super().__init__(data)
        self.headers = headers


class FakeAPI:
    """Stands in for urllib.request.urlopen; records every request, no network.

    Like the API, each metered call costs 1 credit per text in "texts" and the
    reply carries the balance left in X-Credits-Remaining. credits=None sends
    no header (the balance is unknown); header= sends that value as is.
    """

    def __init__(self, fail_path=None, fail_code=402, fail_body=None, fail_headers=None,
                 fail_exc=None, credits=1000, header=None):
        self.requests = []
        self.credits = credits
        self.header = header
        self.fail_path = fail_path
        self.fail_code = fail_code
        self.fail_body = fail_body if fail_body is not None else b'{"detail": "out of credits"}'
        self.fail_headers = fail_headers or {}
        self.fail_exc = fail_exc

    def __call__(self, req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        path = url.split("https://api.test", 1)[1]
        body = json.loads(req.data) if not isinstance(req, str) else None
        headers = {} if isinstance(req, str) else dict(req.header_items())
        self.requests.append({"path": path, "body": body, "headers": headers, "timeout": timeout})
        if path == self.fail_path:
            if self.fail_exc:
                raise self.fail_exc
            raise urllib.error.HTTPError(url, self.fail_code, "Error", self.fail_headers,
                                         io.BytesIO(self.fail_body))
        if path == "/analyze/voice-profile":
            n = len(body["texts"])
            reply = {"results": [{"feature_vector": dict(FEATURES), "summary": "s"} for _ in range(n)]}
        elif path == "/analyze/fingerprint":
            reply = {"distinctive_phrases": ["the hill route"], "first_person_patterns": [],
                     "informality": 0.2, "corpus_document_count": len(body["texts"])}
        elif path == "/health":
            reply = {"version": "9.9.9"}
        else:
            raise AssertionError(f"unexpected path {path}")
        headers = {}
        if path in METERED:
            if self.credits is not None:
                self.credits -= len(body["texts"])
                headers["X-Credits-Remaining"] = str(self.credits)
            if self.header is not None:
                headers["X-Credits-Remaining"] = self.header
        return FakeReply(json.dumps(reply).encode(), headers)

    def calls(self, path):
        return [r for r in self.requests if r["path"] == path]

    def metered(self):
        return [r for r in self.requests if r["path"] in METERED]


def write_samples(folder: Path, rows: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for r in rows:
        (folder / r["file"]).write_text(f"# {r['file']}\n\n{r['text']}\n", encoding="utf-8")
    cols = [c for c in rows[0] if c != "text"]
    lines = [",".join(cols)] + [",".join(str(r[c]) for c in cols) for r in rows]
    (folder / "index.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


class BuildProfileTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.samples = self.dir / "samples"
        self.out = self.dir / "voice-profile.json"
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("TEXT_ANALYSIS_API_KEY", None)

    def build(self, *argv, api=None, key=("--api-key", "test-key"),
              author=("--author", "Alex Rivera")):
        api = api or FakeAPI()
        args = ["--samples", str(self.samples), *author,
                "--from", "alex@example.com", "--api", "https://api.test/",
                "--api-key-file", str(self.dir / "no-key-file"), "-o", str(self.out), *key, *argv]
        with mock.patch.object(bp.urllib.request, "urlopen", api):
            _, self.stdout = run_main(bp, *args)
        return api

    def reference_set(self, n):
        ref = self.dir / "reference"
        ref.mkdir()
        for i in range(n):
            (ref / f"{i}.md").write_text(f"# r{i}\n\nReference {i}.\n", encoding="utf-8")
        return ref

    def reviewed_samples(self):
        write_samples(self.samples, [
            {"file": "a.md", "words": 3, "verdict": "KEEP", "score": 2, "text": "Text A one."},
            {"file": "b.md", "words": 9, "verdict": "drop", "score": 9, "text": "Text B dropped."},
            {"file": "c.md", "words": 5, "verdict": " keep ", "score": 7, "text": "Text C best."},
            {"file": "d.md", "words": 4, "verdict": "KEEP", "score": "", "text": "Text D unscored."},
        ])

    def test_request_headers_carry_key_and_json(self):
        self.reviewed_samples()
        api = self.build()
        req = api.calls("/analyze/fingerprint")[0]
        self.assertEqual(req["headers"]["X-api-key"], "test-key")
        self.assertEqual(req["headers"]["Content-type"], "application/json")
        self.assertEqual(req["timeout"], 600)

    def test_voice_profile_body_joins_top_kept_samples_best_score_first(self):
        self.reviewed_samples()
        api = self.build("--top", "2")
        first = api.requests[0]
        self.assertEqual(first["path"], "/analyze/voice-profile")
        self.assertEqual(first["body"], {"texts": ["Text C best.\n\nText A one."]})

    def test_per_sample_profiles_and_fingerprint_use_only_kept_samples(self):
        self.reviewed_samples()
        api = self.build()
        kept = ["Text C best.", "Text A one.", "Text D unscored."]
        self.assertEqual(api.calls("/analyze/voice-profile")[1]["body"], {"texts": kept})
        self.assertEqual(api.calls("/analyze/fingerprint")[0]["body"], {"texts": kept})

    def test_without_verdict_column_uses_every_sample_longest_first(self):
        write_samples(self.samples, [
            {"file": "short.md", "words": 2, "text": "Short one."},
            {"file": "long.md", "words": 8, "text": "The long one."},
        ])
        api = self.build()
        self.assertEqual(api.calls("/analyze/fingerprint")[0]["body"],
                         {"texts": ["The long one.", "Short one."]})

    def test_reference_texts_go_to_fingerprint_options_longest_first(self):
        self.reviewed_samples()
        ref = self.dir / "reference"
        ref.mkdir()
        (ref / "1.md").write_text("# x\n\nShort ref.\n", encoding="utf-8")
        (ref / "2.md").write_text("# y\n\nA much longer reference text.\n", encoding="utf-8")
        api = self.build("--reference", str(ref))
        fp = api.calls("/analyze/fingerprint")[0]["body"]
        self.assertEqual(fp["options"], {"reference_texts": ["A much longer reference text.", "Short ref."]})
        self.assertEqual(api.calls("/analyze/voice-profile")[2]["body"],
                         {"texts": ["Short ref.", "A much longer reference text."]})
        profile = json.loads(self.out.read_text())
        self.assertEqual(profile["meta"]["reference"]["count"], 2)

    def test_batches_per_sample_profiles_at_the_api_limit(self):
        rows = [{"file": f"s{i}.md", "words": 300 - i, "text": f"Sample {i}."} for i in range(bp.MAX_DOCS + 1)]
        write_samples(self.samples, rows)
        api = self.build()
        batches = [len(r["body"]["texts"]) for r in api.calls("/analyze/voice-profile")[1:]]
        self.assertEqual(batches, [bp.MAX_DOCS, 1])
        self.assertEqual(len(api.calls("/analyze/fingerprint")[0]["body"]["texts"]), bp.MAX_DOCS)

    def test_writes_profile(self):
        self.reviewed_samples()
        self.build("--top", "2", "--cutoff", "2022-09-01")
        profile = json.loads(self.out.read_text())
        self.assertEqual(profile["meta"]["author"], "Alex Rivera")
        self.assertEqual(profile["meta"]["sender_addresses"], ["alex@example.com"])
        self.assertEqual(profile["meta"]["api"], {"url": "https://api.test", "version": "9.9.9"})
        self.assertEqual(profile["meta"]["samples"]["voice_profile"], ["c.md", "a.md"])
        self.assertIn("dated before 2022-09-01", profile["meta"]["source"])
        self.assertEqual(profile["comparison"]["baseline"]["std"], {k: 0.0 for k in FEATURES})
        self.assertEqual(profile["comparison"]["author_feature_vector_mean"], FEATURES)
        self.assertEqual(profile["fingerprint"]["distinctive_phrases"], ["the hill route"])

    def test_http_error_exits_with_path_code_and_detail(self):
        self.reviewed_samples()
        with self.assertRaises(SystemExit) as cm:
            self.build(api=FakeAPI(fail_path="/analyze/fingerprint"))
        self.assertEqual(str(cm.exception),
                         'error: /analyze/fingerprint returned HTTP 402: {"detail": "out of credits"}')
        self.assertFalse(self.out.exists())

    def fail_message(self, **kw):
        self.reviewed_samples()
        with self.assertRaises(SystemExit) as cm:
            self.build(api=FakeAPI(fail_path="/analyze/voice-profile", **kw))
        self.assertFalse(self.out.exists())
        return str(cm.exception)

    def test_401_says_key_wrong(self):
        self.assertIn("rejected the key", self.fail_message(fail_code=401))

    def test_402_reports_balance_and_cost(self):
        msg = self.fail_message(
            fail_body=b'{"error":"insufficient_credits","balance":12,"cost":40}')
        self.assertEqual(msg, "error: out of credits: balance 12, this build costs 40. "
                              "Add credits and try again.")

    def test_429_reports_retry_after(self):
        msg = self.fail_message(fail_code=429, fail_headers={"Retry-After": "30"})
        self.assertIn("Wait 30 seconds", msg)

    def test_429_without_retry_after_has_no_none(self):
        msg = self.fail_message(fail_code=429)
        self.assertIn("Wait a little and try again.", msg)
        self.assertNotIn("None", msg)

    def test_timeout_while_reading_reply_is_one_line(self):
        msg = self.fail_message(fail_exc=TimeoutError("timed out"))
        self.assertIn("lost the connection", msg)

    def test_non_json_reply_is_one_line(self):
        msg = self.fail_message(fail_exc=ValueError("bad json"))
        self.assertIn("unexpected reply", msg)

    def test_unreachable_api_says_so(self):
        msg = self.fail_message(fail_exc=urllib.error.URLError("refused"))
        self.assertIn("cannot reach the API at https://api.test", msg)
        self.assertNotIn("Traceback", msg)

    def test_failed_health_still_writes_profile_with_null_version(self):
        self.reviewed_samples()
        api = FakeAPI(fail_path="/health", fail_exc=urllib.error.URLError("down"))
        self.build(api=api)
        profile = json.loads(self.out.read_text())
        self.assertIsNone(profile["meta"]["api"]["version"])

    def test_missing_key_exits_before_any_request(self):
        self.reviewed_samples()
        api = FakeAPI()
        with self.assertRaises(SystemExit) as cm:
            self.build(api=api, key=())
        self.assertIn("no API key", str(cm.exception))
        self.assertEqual(api.requests, [])

    def test_key_file_with_bom_is_read(self):
        self.reviewed_samples()
        key_file = self.dir / "api-key"
        key_file.write_text("﻿file-key\n", encoding="utf-8")
        api = self.build(key=("--api-key-file", str(key_file)))
        self.assertEqual(api.requests[0]["headers"]["X-api-key"], "file-key")

    def test_no_usable_samples_exits(self):
        write_samples(self.samples, [{"file": "a.md", "words": 3, "verdict": "DROP", "score": 1, "text": "x"}])
        api = FakeAPI()
        with self.assertRaises(SystemExit) as cm:
            self.build(api=api)
        self.assertIn("no usable samples", str(cm.exception))
        self.assertEqual(api.requests, [])


    # Cost guard. reviewed_samples() keeps 3 samples, so a build costs
    # 1 (joined profile) + 3 (per sample) + 0 (reference) + 3 (fingerprint) = 7.

    def test_cost_formula(self):
        self.assertEqual(bp.build_cost(3, 0), 7)
        self.assertEqual(bp.build_cost(149, 0), 250)
        self.assertEqual(bp.build_cost(200, 200), 501)

    def test_balance_below_cost_stops_after_one_metered_request(self):
        self.reviewed_samples()
        api = FakeAPI(credits=6)  # 5 left after the first call, 6 still needed
        with self.assertRaises(SystemExit) as cm:
            self.build(api=api)
        self.assertEqual(len(api.metered()), 1)
        self.assertEqual(len(api.requests), 1)
        self.assertFalse(self.out.exists())
        msg = str(cm.exception)
        self.assertIn("costs 7 credits", msg)
        self.assertIn("5 credits left", msg)
        self.assertIn("yourvoice.dev", msg)
        self.assertIn("fewer samples", msg)
        self.assertIn("without --reference", msg)

    def test_reference_texts_count_toward_the_cost(self):
        self.reviewed_samples()
        ref = self.reference_set(4)
        api = FakeAPI(credits=10)  # cost 1 + 3 + 4 + 3 = 11
        with self.assertRaises(SystemExit) as cm:
            self.build("--reference", str(ref), api=api)
        self.assertEqual(len(api.metered()), 1)
        self.assertIn("costs 11 credits", str(cm.exception))
        self.assertFalse(self.out.exists())

    def test_balance_exactly_the_cost_builds(self):
        self.reviewed_samples()
        api = FakeAPI(credits=7)
        self.build(api=api)
        self.assertTrue(self.out.exists())
        self.assertEqual(api.credits, 0)

    def test_build_prints_its_cost_before_spending(self):
        self.reviewed_samples()
        self.build()
        self.assertIn("costs 7 credits", self.stdout)

    def test_missing_balance_header_does_not_stop_the_build(self):
        self.reviewed_samples()
        api = FakeAPI(credits=None)
        self.build(api=api)
        self.assertTrue(self.out.exists())

    def test_unreadable_balance_header_does_not_stop_the_build(self):
        self.reviewed_samples()
        api = FakeAPI(credits=None, header="lots")
        self.build(api=api)
        self.assertTrue(self.out.exists())

    # --check

    def test_check_makes_one_metered_request_without_author_or_profile(self):
        self.reviewed_samples()
        api = FakeAPI(credits=250)
        self.build("--check", api=api, author=())
        self.assertEqual(len(api.requests), 1)
        self.assertEqual(len(api.metered()), 1)
        self.assertEqual(len(api.requests[0]["body"]["texts"]), 1)
        self.assertEqual(api.requests[0]["body"], {"texts": [bp.CHECK_TEXT]})
        self.assertFalse(self.out.exists())
        self.assertIn("key: OK", self.stdout)
        self.assertIn("balance: 249 credits", self.stdout)
        self.assertIn("estimated cost: 7 credits", self.stdout)

    def test_check_counts_reference_texts(self):
        self.reviewed_samples()
        ref = self.reference_set(4)
        self.build("--check", "--reference", str(ref), author=())
        self.assertIn("estimated cost: 11 credits", self.stdout)
        self.assertIn("3 samples", self.stdout)
        self.assertIn("4 reference texts", self.stdout)

    def test_check_says_when_balance_is_short(self):
        self.reviewed_samples()
        self.build("--check", api=FakeAPI(credits=5), author=())
        self.assertIn("short by 3 credits", self.stdout)
        self.assertIn("yourvoice.dev", self.stdout)
        self.assertFalse(self.out.exists())

    def test_check_before_extraction_has_no_samples_yet(self):
        api = FakeAPI()
        self.build("--check", api=api, author=())
        self.assertEqual(len(api.requests), 1)
        self.assertIn("key: OK", self.stdout)
        self.assertIn("no samples", self.stdout)

    def test_check_with_unknown_balance(self):
        self.reviewed_samples()
        self.build("--check", api=FakeAPI(credits=None), author=())
        self.assertIn("balance: unknown", self.stdout)
        self.assertIn("estimated cost: 7 credits", self.stdout)

    def test_check_with_rejected_key_is_one_line(self):
        api = FakeAPI(fail_path="/analyze/voice-profile", fail_code=401)
        with self.assertRaises(SystemExit) as cm:
            self.build("--check", api=api, author=())
        self.assertIn("rejected the key", str(cm.exception))
        self.assertEqual(len(api.requests), 1)

    def test_build_without_author_or_check_is_refused_before_any_request(self):
        self.reviewed_samples()
        api = FakeAPI()
        with self.assertRaises(SystemExit), mock.patch("sys.stderr", io.StringIO()) as err:
            self.build(api=api, author=())
        self.assertIn("--author", err.getvalue())
        self.assertEqual(api.requests, [])


if __name__ == "__main__":
    unittest.main()
