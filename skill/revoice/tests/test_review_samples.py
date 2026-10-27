import csv
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from _load import BUILD, load, run_main

rs = load(BUILD / "review-samples.py", "review_samples")


class FakeAPI:
    """Stands in for urllib.request.urlopen; records every request, no network."""

    def __init__(self, fail_on=None, status=None, exc=None):
        self.requests = []
        self.fail_on = fail_on  # 1-based request number that fails
        self.status = status
        self.exc = exc

    def __call__(self, req, timeout=None):
        body = json.loads(req.data)
        self.requests.append({"url": req.full_url, "body": body, "timeout": timeout,
                              "headers": dict(req.header_items())})
        if self.fail_on == len(self.requests):
            if self.exc:
                raise self.exc
            raise urllib.error.HTTPError(req.full_url, self.status, "x", {}, io.BytesIO(b"{}"))
        results = [{"id": s["id"], "verdict": "DROP" if s["id"].endswith("0.md") else "KEEP",
                    "score": 4, "reason": "fine, with a comma"} for s in body["samples"]]
        return io.BytesIO(json.dumps({"results": results, "warnings": []}).encode())


class ReviewSamples(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def make(self, n):
        rows = []
        for i in range(n):
            name = f"{i:03d}-s{i}0.md" if i % 10 == 0 else f"{i:03d}-s{i}.md"
            (self.dir / name).write_text(f"# Subject {i}\nBody of sample {i}.\n", encoding="utf-8")
            rows.append({"file": name, "date": "2020-01-01", "words": "4", "subject": f"Subject {i}"})
        with open(self.dir / "index.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["file", "date", "words", "subject"])
            w.writeheader()
            w.writerows(rows)
        return (self.dir / "index.csv").read_bytes()

    def run_it(self, fake, *extra):
        argv = ["--samples", str(self.dir), "--api", "https://api.test/", "--api-key", "k", *extra]
        with mock.patch("urllib.request.urlopen", fake):
            return run_main(rs, *argv)

    def test_150_samples_split_into_100_and_50(self):
        self.make(150)
        fake = FakeAPI()
        self.run_it(fake)
        self.assertEqual([len(r["body"]["samples"]) for r in fake.requests], [100, 50])
        self.assertEqual(fake.requests[0]["url"], "https://api.test/analyze/sample-review")
        self.assertEqual(fake.requests[0]["timeout"], 60)
        self.assertEqual(fake.requests[0]["headers"]["X-api-key"], "k")
        self.assertEqual(fake.requests[0]["body"]["samples"][0],
                         {"id": "000-s00.md", "text": "Body of sample 0."})

    def test_columns_written_in_order_and_rows_kept(self):
        self.make(150)
        self.run_it(FakeAPI())
        with open(self.dir / "index.csv", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(reader.fieldnames,
                         ["file", "date", "words", "subject", "verdict", "score", "reason"])
        self.assertEqual(len(rows), 150)
        self.assertEqual(rows[1]["subject"], "Subject 1")
        self.assertEqual(rows[1]["verdict"], "KEEP")
        self.assertEqual(rows[0]["verdict"], "DROP")
        self.assertEqual(rows[149]["reason"], "fine, with a comma")
        self.assertEqual(list(self.dir.glob("*.tmp")), [])

    def test_rerun_replaces_existing_columns(self):
        self.make(3)
        self.run_it(FakeAPI())
        self.run_it(FakeAPI())
        with open(self.dir / "index.csv", newline="", encoding="utf-8") as f:
            self.assertEqual(csv.DictReader(f).fieldnames,
                             ["file", "date", "words", "subject", "verdict", "score", "reason"])

    def assert_exit_unchanged(self, fake, text):
        before = self.make(150)
        with self.assertRaises(SystemExit) as cm:
            self.run_it(fake)
        self.assertIn(text, str(cm.exception))
        self.assertEqual((self.dir / "index.csv").read_bytes(), before)
        self.assertEqual(list(self.dir.glob("*.tmp")), [])

    def test_401_wrong_key(self):
        self.assert_exit_unchanged(FakeAPI(fail_on=1, status=401), "rejected the key")

    def test_402_out_of_credits(self):
        self.assert_exit_unchanged(FakeAPI(fail_on=1, status=402), "out of credits")

    def test_5xx_api_down(self):
        self.assert_exit_unchanged(FakeAPI(fail_on=1, status=503), "API is down")

    def test_timeout_api_down(self):
        self.assert_exit_unchanged(FakeAPI(fail_on=1, exc=TimeoutError("timed out")), "API is down")

    def test_failure_in_second_batch_leaves_index_unchanged(self):
        self.assert_exit_unchanged(FakeAPI(fail_on=2, status=402), "out of credits")

    def test_mismatched_results_exit_unchanged(self):
        for name, mangle in [("missing", lambda r: r[:-1]),
                             ("extra", lambda r: r + [{**r[0], "id": "zzz.md"}]),
                             ("reversed", lambda r: r[::-1])]:
            with self.subTest(name):
                before = self.make(3)

                class Bad(FakeAPI):
                    def __call__(self, req, timeout=None):
                        data = json.load(super().__call__(req, timeout))
                        data["results"] = mangle(data["results"])
                        return io.BytesIO(json.dumps(data).encode())

                with self.assertRaises(SystemExit) as cm:
                    self.run_it(Bad())
                self.assertIn("do not match", str(cm.exception))
                self.assertEqual((self.dir / "index.csv").read_bytes(), before)

    def test_header_only_index_exits_unchanged(self):
        (self.dir / "index.csv").write_text("file,date,words,subject\n", encoding="utf-8")
        before = (self.dir / "index.csv").read_bytes()
        fake = FakeAPI()
        with self.assertRaises(SystemExit) as cm:
            self.run_it(fake)
        self.assertIn("no samples", str(cm.exception))
        self.assertEqual(fake.requests, [])
        self.assertEqual((self.dir / "index.csv").read_bytes(), before)

    def test_key_file_with_bom_is_used(self):
        self.make(2)
        keyfile = self.dir / "key.txt"
        keyfile.write_bytes(b"\xef\xbb\xbffile-key\n")
        fake = FakeAPI()
        argv = ["--samples", str(self.dir), "--api", "https://api.test",
                "--api-key-file", str(keyfile)]
        with mock.patch.dict("os.environ", {}, clear=True), \
                mock.patch("urllib.request.urlopen", fake):
            run_main(rs, *argv)
        self.assertEqual(fake.requests[0]["headers"]["X-api-key"], "file-key")

    def test_no_key_exits(self):
        self.make(1)
        with mock.patch.dict("os.environ", {}, clear=True), self.assertRaises(SystemExit) as cm:
            run_main(rs, "--samples", str(self.dir), "--api-key-file", str(self.dir / "none"))
        self.assertIn("no API key", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
