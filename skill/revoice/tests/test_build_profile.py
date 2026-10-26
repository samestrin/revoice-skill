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


class FakeAPI:
    """Stands in for urllib.request.urlopen; records every request, no network."""

    def __init__(self, fail_path=None):
        self.requests = []
        self.fail_path = fail_path

    def __call__(self, req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        path = url.split("https://api.test", 1)[1]
        body = json.loads(req.data) if not isinstance(req, str) else None
        headers = {} if isinstance(req, str) else dict(req.header_items())
        self.requests.append({"path": path, "body": body, "headers": headers, "timeout": timeout})
        if path == self.fail_path:
            raise urllib.error.HTTPError(url, 402, "Payment Required", {},
                                         io.BytesIO(b'{"detail": "out of credits"}'))
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
        return io.BytesIO(json.dumps(reply).encode())

    def calls(self, path):
        return [r for r in self.requests if r["path"] == path]


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

    def build(self, *argv, api=None, key=("--api-key", "test-key")):
        api = api or FakeAPI()
        args = ["--samples", str(self.samples), "--author", "Alex Rivera",
                "--from", "alex@example.com", "--api", "https://api.test/",
                "--api-key-file", str(self.dir / "no-key-file"), "-o", str(self.out), *key, *argv]
        with mock.patch.object(bp.urllib.request, "urlopen", api):
            run_main(bp, *args)
        return api

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


if __name__ == "__main__":
    unittest.main()
