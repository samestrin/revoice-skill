import csv
import email.message
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

from _load import BUILD, load, run_main

SCRIPT = BUILD / "extract-documents.py"
ed = load(SCRIPT, "extract_documents")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx_bytes(paragraphs, *, table=None, headings=()) -> bytes:
    """A minimal .docx: one paragraph per string, an optional table after them."""
    def para(text, style=None):
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        return f"<w:p>{ppr}<w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"
    body = "".join(para(h, "Heading1") for h in headings)
    body += "".join(para(p) for p in paragraphs)
    if table:
        body += f"<w:tbl><w:tr><w:tc>{para(table)}</w:tc></w:tr></w:tbl>"
    xml = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
        z.writestr("word/footer1.xml", f'<w:ftr xmlns:w="{W}"><w:p><w:r><w:t>FOOTER-TEXT</w:t></w:r></w:p></w:ftr>')
    return buf.getvalue()


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, url: str, ctype="text/html; charset=utf-8", length=None):
        super().__init__(body)
        self.headers = email.message.Message()
        self.headers["Content-Type"] = ctype
        if length is not None:
            self.headers["Content-Length"] = str(length)
        self.url = url

    def geturl(self):
        return self.url


class Run:
    """One run of the script: its stdout, the index rows and the sample texts."""

    def __init__(self, out: Path, stdout: str):
        self.out = out
        self.stdout = stdout
        with open(out / "index.csv", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.columns = reader.fieldnames
            self.rows = list(reader)
        self.by_source = {r["source"]: r for r in self.rows}

    def text(self, source: str) -> str:
        return (self.out / self.by_source[source]["file"]).read_text(encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.docs = self.tmp / "docs"
        self.docs.mkdir()
        self.out = self.tmp / "samples"
        # No test may reach the network or wait for the pause between URLs.
        opener = mock.patch.object(ed._OPENER, "open", side_effect=AssertionError("network"))
        self.opener = opener.start()
        self.addCleanup(opener.stop)
        sleep = mock.patch.object(ed.time, "sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def write(self, rel: str, content) -> Path:
        path = self.docs / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def run_script(self, *args) -> Run:
        _, stdout = run_main(ed, *map(str, args), "-o", str(self.out))
        return Run(self.out, stdout)

    def pdftotext_stub(self, body: str) -> str:
        """A fake pdftotext on PATH; returns the PATH value to use."""
        bindir = self.tmp / "bin"
        bindir.mkdir(exist_ok=True)
        stub = bindir / "pdftotext"
        stub.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


class TextReaderTest(Base):
    def test_markdown_front_matter_title_and_date_are_used_then_dropped(self):
        self.write("post.md", "---\ntitle: \"Notes on Compost\"\ndate: 2019-04-02\ntags: [garden]\n---\n"
                              "First paragraph here.\n\nSecond paragraph.\n")
        run = self.run_script(self.docs)
        row = run.by_source["post.md"]
        self.assertEqual(row["subject"], "Notes on Compost")
        self.assertEqual(row["date"], "2019-04-02")
        self.assertEqual(row["words"], "5")
        text = run.text("post.md")
        self.assertEqual(text, "# Notes on Compost\n\nFirst paragraph here.\n\nSecond paragraph.\n")
        self.assertNotIn("tags", text)

    def test_front_matter_date_with_a_time_keeps_the_day(self):
        title, date, _ = ed.read_text("---\ndate: '2021-07-09T10:00:00Z'\n---\nBody.\n", "x")
        self.assertEqual((title, date), ("x", "2021-07-09"))

    def test_front_matter_date_that_is_not_a_date_is_undated(self):
        _, date, _ = ed.read_text("---\ndate: last spring\n---\nBody.\n", "x")
        self.assertIsNone(date)

    def test_no_front_matter_uses_file_name_and_undated(self):
        self.write("garden-plans.txt", "﻿Line one\nstill one.\n\n\n\nTwo.\n")
        run = self.run_script(self.docs)
        row = run.by_source["garden-plans.txt"]
        self.assertEqual((row["subject"], row["date"]), ("garden-plans", "undated"))
        self.assertEqual(run.text("garden-plans.txt"), "# garden-plans\n\nLine one\nstill one.\n\nTwo.\n")

    def test_text_that_is_not_utf8_is_skipped_and_counted(self):
        self.write("latin1.txt", "caf\xe9 au lait".encode("latin-1"))
        run = self.run_script(self.docs)
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"not UTF-8\s*: 1")

    def test_empty_file_is_counted_as_no_text(self):
        self.write("empty.md", "---\ntitle: Nothing\n---\n\n   \n")
        run = self.run_script(self.docs)
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"no text\s*: 1")


class HtmlReaderTest(Base):
    PAGE = """<!doctype html><html><head><title>Spring &amp; Seeds</title>
    <style>.x{color:red}</style><script>var STYLE_LEAK = 1;</script></head>
    <body><nav>NAV-TEXT</nav><header>HEADER-TEXT</header>
    <article><h1>Spring planting</h1><p>Seeds go in   when the
    soil is warm.</p><ul><li>Peas first</li><li>Beans later</li></ul>
    <blockquote>QUOTE-TEXT</blockquote><pre>PRE-TEXT</pre><p>Water <code>CODE-TEXT</code> daily.</p>
    <table><tr><td>TABLE-TEXT</td></tr></table><figure>FIGURE-TEXT</figure>
    <form>FORM-TEXT</form><aside>ASIDE-TEXT</aside></article><footer>FOOTER-TEXT</footer></body></html>"""

    def test_keeps_headings_paragraphs_and_list_items_drops_the_rest(self):
        self.write("page.html", self.PAGE)
        run = self.run_script(self.docs)
        row = run.by_source["page.html"]
        self.assertEqual(row["subject"], "Spring & Seeds")
        self.assertEqual(row["date"], "undated")
        self.assertEqual(run.text("page.html"),
                         "# Spring & Seeds\n\n# Spring planting\n\nSeeds go in when the soil is warm.\n\n"
                         "Peas first\n\nBeans later\n\nWater daily.\n")

    def test_htm_is_read_too(self):
        self.write("old.htm", "<p>Old page text.</p>")
        run = self.run_script(self.docs)
        self.assertEqual(run.by_source["old.htm"]["subject"], "old")


class DocxReaderTest(Base):
    def test_reads_paragraphs_and_headings_skips_tables_and_footers(self):
        self.write("Brand Guide.docx", docx_bytes(["We write plainly.", "We keep it short."],
                                                  table="TABLE-TEXT", headings=["Our voice"]))
        run = self.run_script(self.docs)
        row = run.by_source["Brand Guide.docx"]
        self.assertEqual((row["subject"], row["date"], row["words"]), ("Brand Guide", "undated", "8"))
        self.assertEqual(run.text("Brand Guide.docx"),
                         "# Brand Guide\n\n# Our voice\n\nWe write plainly.\n\nWe keep it short.\n")

    def test_docx_xml_over_the_limit_is_skipped_and_counted(self):
        self.write("big.docx", docx_bytes(["word " * 400]))
        self.write("small.docx", docx_bytes(["Fine."]))
        with mock.patch.object(ed, "MAX_DOCX_XML_BYTES", 1000):
            run = self.run_script(self.docs)
        self.assertEqual(sorted(run.by_source), ["small.docx"])
        self.assertRegex(run.stdout, r"docx too large\s*: 1")

    def test_docx_whose_declared_size_lies_is_still_capped(self):
        self.write("big.docx", docx_bytes(["word " * 400]))
        info = mock.Mock(file_size=10)
        with mock.patch.object(ed, "MAX_DOCX_XML_BYTES", 1000), \
                mock.patch.object(zipfile.ZipFile, "getinfo", return_value=info):
            run = self.run_script(self.docs)
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"docx too large\s*: 1")

    def test_broken_docx_is_counted_as_unreadable(self):
        self.write("broken.docx", b"not a zip at all")
        self.write("nodoc.docx", self._zip_without_document())
        run = self.run_script(self.docs)
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"unreadable\s*: 2")

    @staticmethod
    def _zip_without_document() -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/other.xml", "<x/>")
        return buf.getvalue()


@unittest.skipIf(os.name == "nt", "the pdftotext stub is a shell script")
class PdfReaderTest(Base):
    def test_reads_pdf_with_pdftotext_on_path(self):
        words = " ".join(f"word{i}" for i in range(60))
        self.write("report.pdf", f"Annual report\n\n{words}\n\f")
        path = self.pdftotext_stub('for a; do prev="$last"; last="$a"; done\n'
                                   '[ "$last" = "-" ] || exit 9\nexec cat "$prev"\n')
        with mock.patch.dict(os.environ, {"PATH": path}):
            run = self.run_script(self.docs)
        row = run.by_source["report.pdf"]
        self.assertEqual((row["subject"], row["words"]), ("report", "62"))
        self.assertEqual(run.text("report.pdf"), f"# report\n\nAnnual report\n\n{words}\n")

    def test_missing_pdftotext_skips_the_file_with_the_message(self):
        self.write("report.pdf", "whatever")
        self.write("note.txt", "Still read.")
        empty = self.tmp / "empty-bin"
        empty.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(empty)}):
            run = self.run_script(self.docs)
        self.assertEqual(sorted(run.by_source), ["note.txt"])
        self.assertRegex(run.stdout, r"no pdftotext\s*: 1")
        self.assertIn("report.pdf", run.stdout)
        self.assertIn("install poppler", run.stdout)
        self.assertIn("save it as .docx or .txt", run.stdout)

    def test_pdftotext_that_runs_past_the_timeout_is_skipped(self):
        self.write("slow.pdf", "whatever")
        path = self.pdftotext_stub("exec sleep 5\n")
        with mock.patch.dict(os.environ, {"PATH": path}), \
                mock.patch.object(ed, "PDFTOTEXT_TIMEOUT", 0.3):
            run = self.run_script(self.docs)
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"pdftotext timeout\s*: 1")

    def test_default_pdftotext_timeout_is_30_seconds(self):
        self.assertEqual(ed.PDFTOTEXT_TIMEOUT, 30)

    def test_pdftotext_failure_is_counted(self):
        self.write("bad.pdf", "whatever")
        path = self.pdftotext_stub("echo broken >&2\nexit 1\n")
        with mock.patch.dict(os.environ, {"PATH": path}):
            run = self.run_script(self.docs)
        self.assertRegex(run.stdout, r"pdftotext failed\s*: 1")

    def test_scanned_pdf_under_50_words_is_no_text_layer(self):
        self.write("scan.pdf", "Page 1\n")
        path = self.pdftotext_stub('for a; do prev="$last"; last="$a"; done\nexec cat "$prev"\n')
        with mock.patch.dict(os.environ, {"PATH": path}):
            run = self.run_script(self.docs)
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"no text layer\s*: 1")


class WalkTest(Base):
    def test_walks_recursively_in_sorted_order_skipping_hidden_and_office_locks(self):
        self.write("b.md", "B.")
        self.write("a/z.txt", "Z.")
        self.write("a/y.md", "Y.")
        self.write(".hidden.md", "HIDDEN")
        self.write(".git/config.md", "HIDDEN")
        self.write("~$draft.docx", b"lock file")
        self.write("a/~$lock.md", "LOCK")
        run = self.run_script(self.docs)
        self.assertEqual([r["source"] for r in run.rows], ["a/y.md", "a/z.txt", "b.md"])
        self.assertEqual(ed.walk([self.docs])[0], [
            (self.docs / "a" / "y.md", "a/y.md"),
            (self.docs / "a" / "z.txt", "a/z.txt"),
            (self.docs / "b.md", "b.md"),
        ])

    def test_a_file_argument_is_read_with_its_name_as_source(self):
        path = self.write("sub/one.md", "One.")
        run = self.run_script(path)
        self.assertEqual(list(run.by_source), ["one.md"])

    def test_unsupported_rtf_is_counted(self):
        self.write("letter.rtf", r"{\rtf1 Hello}")
        self.write("pic.png", b"\x89PNG")
        self.write("ok.md", "Fine.")
        run = self.run_script(self.docs)
        self.assertEqual(list(run.by_source), ["ok.md"])
        self.assertRegex(run.stdout, r"unsupported type\s*: 2")
        self.assertIn("letter.rtf", run.stdout)

    def test_file_over_the_size_limit_is_skipped_and_counted(self):
        self.write("big.txt", "word " * 100)
        self.write("small.txt", "Fine.")
        with mock.patch.object(ed, "MAX_FILE_BYTES", 100):
            run = self.run_script(self.docs)
        self.assertEqual(list(run.by_source), ["small.txt"])
        self.assertRegex(run.stdout, r"file too large\s*: 1")

    def test_default_limits_match_the_plan(self):
        self.assertEqual(ed.MAX_FILE_BYTES, 20 * 1024 * 1024)
        self.assertEqual(ed.MAX_DOCX_XML_BYTES, 50 * 1024 * 1024)
        self.assertEqual(ed.MAX_PAGE_BYTES, 5 * 1024 * 1024)
        self.assertEqual(ed.URL_TIMEOUT, 20)
        self.assertEqual(ed.MAX_URLS, 100)
        self.assertEqual(ed.URL_PAUSE, 1)

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_symlinked_file_and_folder_are_skipped_and_counted(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "secret.md").write_text("SECRET", encoding="utf-8")
        self.write("real.md", "Real.")
        (self.docs / "link.md").symlink_to(outside / "secret.md")
        (self.docs / "linkdir").symlink_to(outside, target_is_directory=True)
        run = self.run_script(self.docs, self.tmp / "docs" / "link.md")
        self.assertEqual(list(run.by_source), ["real.md"])
        self.assertRegex(run.stdout, r"symlink\s*: 3")

    def test_missing_path_is_counted(self):
        run = self.run_script(self.docs / "nope")
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"not found\s*: 1")


class UrlTest(Base):
    def urls(self, *lines) -> Path:
        path = self.tmp / "urls.txt"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_fetches_http_and_https_pages_as_html(self):
        pages = {
            "https://example.com/post": b"<title>My Post</title><p>Hello from the web.</p>",
            "http://example.org/notes.txt": b"Plain notes.",
        }

        def fake_open(req, timeout):
            self.assertEqual(timeout, ed.URL_TIMEOUT)
            url = req.full_url
            ctype = "text/plain" if url.endswith(".txt") else "text/html; charset=utf-8"
            return FakeResponse(pages[url], url, ctype)

        self.opener.side_effect = fake_open
        run = self.run_script("--urls", self.urls("# my pages", "", *pages))
        self.assertEqual(run.by_source["https://example.com/post"]["subject"], "My Post")
        self.assertEqual(run.text("https://example.com/post"), "# My Post\n\nHello from the web.\n")
        self.assertEqual(run.text("http://example.org/notes.txt"), "# example.org/notes.txt\n\nPlain notes.\n")
        self.assertEqual(self.sleep.call_args_list, [mock.call(ed.URL_PAUSE)])

    def test_file_and_ftp_urls_are_refused_without_fetching(self):
        run = self.run_script("--urls", self.urls("file:///etc/passwd", "ftp://example.com/a.html"))
        self.opener.assert_not_called()
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"not an http\(s\) URL\s*: 2")

    def test_page_over_the_size_limit_is_refused(self):
        big = b"<p>" + b"x" * 200 + b"</p>"
        self.opener.side_effect = lambda req, timeout: FakeResponse(big, req.full_url)
        with mock.patch.object(ed, "MAX_PAGE_BYTES", 100):
            run = self.run_script("--urls", self.urls("https://example.com/big"))
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"page too large\s*: 1")

    def test_page_with_a_large_content_length_is_refused_before_reading(self):
        resp = FakeResponse(b"<p>small</p>", "https://example.com/big", length=10 ** 9)
        resp.read = mock.Mock(side_effect=AssertionError("read"))
        self.opener.side_effect = lambda req, timeout: resp
        run = self.run_script("--urls", self.urls("https://example.com/big"))
        self.assertRegex(run.stdout, r"page too large\s*: 1")

    def test_default_page_limit_is_5_mb(self):
        self.assertEqual(ed.MAX_PAGE_BYTES, 5 * 1024 * 1024)

    def test_fetch_errors_are_counted_as_fetch_failed(self):
        self.opener.side_effect = urllib.error.URLError("no route")
        run = self.run_script("--urls", self.urls("https://example.com/a", "https://example.com/b"))
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"fetch failed\s*: 2")

    def test_redirect_to_another_scheme_is_refused(self):
        handler = ed._HttpOnlyRedirect()
        req = urllib.request.Request("https://example.com/a")
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(req, None, 302, "Found", {}, "ftp://example.com/x")
        self.assertIsNotNone(handler.redirect_request(req, None, 302, "Found", {}, "https://example.com/b"))

    def test_at_most_max_urls_are_fetched(self):
        self.opener.side_effect = lambda req, timeout: FakeResponse(b"<p>Hi.</p>", req.full_url)
        with mock.patch.object(ed, "MAX_URLS", 2):
            run = self.run_script("--urls", self.urls(*[f"https://example.com/{i}" for i in range(4)]))
        self.assertEqual(self.opener.call_count, 2)
        self.assertEqual(len(run.rows), 2)
        self.assertRegex(run.stdout, r"over the URL limit\s*: 2")


class OutputTest(Base):
    def test_index_has_the_five_columns_and_names_follow_the_layout(self):
        self.write("one.md", "---\ntitle: One Doc\ndate: 2020-01-01\n---\nAlpha beta.\n")
        self.write("two.txt", "Gamma delta epsilon.")
        run = self.run_script(self.docs)
        self.assertEqual(run.columns, ["file", "date", "words", "subject", "source"])
        for row in run.rows:
            self.assertRegex(row["file"], r"^[a-z0-9-]+_01_[0-9a-f]{6}\.md$")
            self.assertTrue((self.out / row["file"]).is_file())
        self.assertTrue(run.by_source["one.md"]["file"].startswith("one-doc_01_"))
        # longest first, like extract-samples.py
        self.assertEqual([r["source"] for r in run.rows], ["two.txt", "one.md"])

    def test_report_counts_documents_read_and_skipped(self):
        self.write("one.md", "One.")
        self.write("two.rtf", "x")
        run = self.run_script(self.docs)
        self.assertIn("read 1 document, wrote 1 sample", run.stdout)
        self.assertIn("skipped 1", run.stdout)

    def test_build_profile_reads_the_samples_folder(self):
        bp = load(BUILD / "build-profile.py", "build_profile_for_docs")
        self.write("one.md", "---\ntitle: One Doc\n---\nAlpha beta gamma.\n")
        run = self.run_script(self.docs)
        name = run.rows[0]["file"]
        self.assertEqual(bp.body(self.out / name), "Alpha beta gamma.")

    def test_no_input_is_an_error(self):
        with self.assertRaises(SystemExit):
            run_main(ed, "-o", str(self.out))

    def test_help_runs_as_a_script(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--urls", proc.stdout)


if __name__ == "__main__":
    unittest.main()
