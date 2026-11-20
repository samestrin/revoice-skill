import collections
import csv
import email.message
import io
import os
import shutil
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

from _load import BUILD, load, real_run, real_run_body, run_main

SCRIPT = BUILD / "extract-documents.py"
ed = load(SCRIPT, "extract_documents")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx_bytes(paragraphs, *, table=None, headings=(), raw=()) -> bytes:
    """A minimal .docx: one paragraph per string, an optional table after them.

    Each string in ``raw`` is the inner XML of one more paragraph."""
    def para(text, style=None):
        ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        return f"<w:p>{ppr}<w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"
    body = "".join(para(h, "Heading1") for h in headings)
    body += "".join(para(p) for p in paragraphs)
    body += "".join(f"<w:p>{r}</w:p>" for r in raw)
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


def prose(words: int, tag: str) -> str:
    """``words`` words no other tag shares, with a sentence end every 10 words."""
    return " ".join(f"{tag}-{i}" + ("." if i % 10 == 9 or i == words - 1 else "")
                    for i in range(words))


class Base(unittest.TestCase):
    # The reader tests use one-line documents; the passage rules have their own tests.
    ARGS = ("--min-words", "1")

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
        _, stdout = run_main(ed, *map(str, args), *self.ARGS, "-o", str(self.out))
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

    def test_front_matter_date_that_is_not_a_real_day_is_undated(self):
        _, date, _ = ed.read_text("---\ndate: 2021-02-30\n---\nBody.\n", "x")
        self.assertIsNone(date)

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
                         "# Spring & Seeds\n\nSpring planting\n\nSeeds go in when the soil is warm.\n\n"
                         "Peas first\n\nBeans later\n\nWater daily.\n")

    def test_an_unclosed_heading_ends_at_the_next_block(self):
        title, _, paragraphs = ed.read_html(
            "<title>T</title><h1>Main heading<p>para one<p>para two", "stem")
        self.assertEqual(paragraphs, ["# Main heading", "para one", "para two"])

    def test_a_line_break_inside_a_heading_stays_in_the_heading(self):
        _, _, paragraphs = ed.read_html("<h2>Head<br>still<hr></h2><p>Body.</p>", "stem")
        self.assertEqual(paragraphs, ["## Head still", "Body."])

    def test_a_title_inside_a_skipped_element_is_ignored(self):
        title, _, paragraphs = ed.read_html(
            "<noscript><title>NOS</title></noscript><title>Real</title><p>body</p>", "stem")
        self.assertEqual((title, paragraphs), ("Real", ["body"]))

    def test_htm_is_read_too(self):
        self.write("old.htm", "<p>Old page text.</p>")
        run = self.run_script(self.docs)
        self.assertEqual(run.by_source["old.htm"]["subject"], "old")


class IconAndWidgetTest(Base):
    """Bug 5: icon-font ligatures and a terminal widget read as prose (Epic 19 T3)."""
    ICONS = ("arrow_forward", "smart_toy", "verified_user", "public", "lock", "hub")

    def test_real_run_brand_page_keeps_no_icon_word_and_no_widget(self):
        self.write("brand.html", real_run("brand_icons_widgets.html"))
        run = self.run_script(self.docs)
        text = run.text("brand.html")
        paragraphs = text.split("\n\n")
        for icon in self.ICONS:
            # "public" is also genuine prose here ("two public companies"), so an
            # icon word is checked as the token an icon span leaves: one on its
            # own at the start or end of a paragraph.
            for p in paragraphs:
                self.assertFalse(p.startswith(icon + " ") or p.rstrip().endswith(" " + icon),
                                 (icon, p))
        for icon in ("arrow_forward", "smart_toy", "verified_user", "hub"):
            self.assertNotIn(icon, text)
        for widget in ("estrin-lab", "ONLINE", "PRIVATE LAB", "KVM", "UPS", "auto-shutdown", "> "):
            self.assertNotIn(widget, text)
        self.assertIn("founder of two public companies.", text)
        self.assertIn("\n\nWhere My Work Is Built, Tested and Previewed\n\n", text)
        self.assertIn("\n\nI choose the language by the constraint, not by habit.", text)
        self.assertIn("\n\nPrivate by Default. Your name", text)

    def test_real_run_brand_page_paragraphs(self):
        _, _, paragraphs = ed.read_html(real_run("brand_icons_widgets.html"), "stem")
        self.assertEqual([p.split()[0] for p in paragraphs],
                         ["Senior", "Book", "Where", "I", "Coding", "Direct", "Private", "Remote"])
        self.assertEqual(paragraphs[1], "Book a 30-Minute Call")

    def test_icon_font_classes_and_aria_hidden_are_dropped(self):
        _, _, paragraphs = ed.read_html(
            '<p><i class="fa fa-check"></i>One <span class="bi-star">star</span>two '
            '<span class="icon-home">home</span>three <span class="material-icons">face</span>four '
            '<span class="x material-symbols-rounded">bolt</span>five <b aria-hidden="TRUE">deco</b>six</p>'
            '<p>Kept <span class="iconic">iconic</span> and <span aria-hidden="false">shown</span>.</p>',
            "stem")
        self.assertEqual(paragraphs, ["One two three four five six", "Kept iconic and shown."])

    def test_a_dropped_element_nested_in_its_own_tag_ends_at_its_own_end_tag(self):
        _, _, paragraphs = ed.read_html(
            '<p>Before <span aria-hidden="true">a <span>b</span> c</span> after</p><p>Next</p>', "stem")
        self.assertEqual(paragraphs, ["Before after", "Next"])

    def test_an_unclosed_dropped_element_ends_with_its_parent(self):
        _, _, paragraphs = ed.read_html(
            '<ul><li class="icon-check">gone<li>also gone</ul><p>The rest of the page.</p>', "stem")
        self.assertEqual(paragraphs, ["The rest of the page."])

    def test_void_elements_with_icon_classes_drop_nothing(self):
        _, _, paragraphs = ed.read_html(
            '<p>One<img class="icon-x" aria-hidden="true">two<br class="fa-x"></p><p>Three</p>', "stem")
        self.assertEqual(paragraphs, ["Onetwo", "Three"])

    def test_a_self_closing_icon_element_drops_only_itself(self):
        _, _, paragraphs = ed.read_html(
            '<p>One <span class="icon-x"/>two <span>three</span></p><h2>Head <i class="fa-a"></i></h2>',
            "stem")
        self.assertEqual(paragraphs, ["One two three", "## Head"])

    def test_a_terminal_widget_is_dropped_whole(self):
        _, _, paragraphs = ed.read_html(
            "<div><p>Intro.</p><div class=term><div>build :: status</div><div>$ make test</div>"
            "<div>$ make build</div><div>ok</div><div>&gt; deployed</div></div><p>After.</p></div>",
            "stem")
        self.assertEqual(paragraphs, ["Intro.", "After."])

    def test_prose_just_before_a_nested_widget_is_kept(self):
        # "lead" is only written when the widget's <div> starts; the widget's
        # lines begin after it, so it must survive the widget being dropped.
        _, _, paragraphs = ed.read_html(
            "<div><p>p1</p><p>p2</p><p>p3</p>lead<div class=w><p>$ a</p><p>$ b</p>"
            "<p>$ c</p><p>$ d</p></div><p>after</p></div>", "stem")
        self.assertEqual(paragraphs, ["p1", "p2", "p3", "lead", "after"])

    def test_a_container_with_few_or_no_prompt_lines_is_kept(self):
        page = ("<div><p>$5 million raised.</p><p>$10 for a ticket.</p><p>&gt;50% grew.</p></div>"
                "<div><p>$ one prompt</p><p>prose line</p><p>more prose</p><p>&gt; quote</p></div>"
                "<div><p>$ ls</p><p>&gt; out</p></div>")
        _, _, paragraphs = ed.read_html(page, "stem")
        self.assertEqual(paragraphs, ["$5 million raised.", "$10 for a ticket.", ">50% grew.",
                                      "$ one prompt", "prose line", "more prose", "> quote",
                                      "$ ls", "> out"])

    def test_a_plain_pre_block_is_still_skipped(self):
        _, _, paragraphs = ed.read_html(
            "<p>Run this:</p><pre>$ npm install\n$ npm test\nPRE-TEXT</pre><p>Then this.</p>", "stem")
        self.assertEqual(paragraphs, ["Run this:", "Then this."])


class DocxReaderTest(Base):
    def test_reads_paragraphs_and_headings_skips_tables_and_footers(self):
        self.write("Brand Guide.docx", docx_bytes(["We write plainly.", "We keep it short."],
                                                  table="TABLE-TEXT", headings=["Our voice"]))
        run = self.run_script(self.docs)
        row = run.by_source["Brand Guide.docx"]
        # A heading is not prose, so "Our voice" is not counted.
        self.assertEqual((row["subject"], row["date"], row["words"]), ("Brand Guide", "undated", "7"))
        self.assertEqual(run.text("Brand Guide.docx"),
                         "# Brand Guide\n\nOur voice\n\nWe write plainly.\n\nWe keep it short.\n")

    def test_docx_xml_over_the_limit_is_skipped_and_counted(self):
        self.write("big.docx", docx_bytes(["word " * 400]))
        self.write("small.docx", docx_bytes(["Fine."]))
        with mock.patch.object(ed, "MAX_DOCX_XML_BYTES", 1000):
            run = self.run_script(self.docs)
        self.assertEqual(sorted(run.by_source), ["small.docx"])
        self.assertRegex(run.stdout, r"docx too large\s*: 1")

    def test_tabs_breaks_and_empty_paragraphs(self):
        self.write("tabs.docx", docx_bytes(
            ["First."],
            raw=['<w:r><w:t>a</w:t><w:tab/><w:t>b</w:t><w:br/><w:t>c</w:t><w:cr/><w:t>d</w:t></w:r>',
                 '<w:r><w:t xml:space="preserve">   </w:t></w:r>', ""]))
        run = self.run_script(self.docs)
        self.assertEqual(run.text("tabs.docx"), "# tabs\n\nFirst.\n\na b\nc\nd\n")

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

    def test_pdftotext_that_cannot_start_is_counted_as_failed(self):
        self.write("bad.pdf", "whatever")
        path = self.pdftotext_stub("exit 0\n")
        with mock.patch.dict(os.environ, {"PATH": path}), \
                mock.patch.object(ed.subprocess, "run", side_effect=OSError(8, "Exec format error")):
            run = self.run_script(self.docs)
        self.assertRegex(run.stdout, r"pdftotext failed\s*: 1")

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
        self.assertEqual(sorted(run.by_source), ["a/y.md", "a/z.txt", "b.md"])
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

    def test_unreadable_folder_is_skipped_and_counted(self):
        self.write("ok.md", "Fine.")
        self.write("locked/x.md", "Hidden by permissions.")
        real = os.scandir

        def scandir(path):
            if Path(path).name == "locked":
                raise PermissionError(13, "denied")
            return real(path)

        with mock.patch.object(ed.os, "scandir", side_effect=scandir):
            run = self.run_script(self.docs)
        self.assertEqual(list(run.by_source), ["ok.md"])
        self.assertRegex(run.stdout, r"unreadable\s*: 1")
        self.assertIn("skip locked: unreadable", run.stdout)

    def test_file_that_fails_to_read_is_counted_as_unreadable(self):
        self.write("gone.md", "Listed, then unreadable.")
        self.write("ok.md", "Fine.")
        real = Path.read_bytes

        def read_bytes(path):
            if path.name == "gone.md":
                raise PermissionError(13, "denied")
            return real(path)

        with mock.patch.object(Path, "read_bytes", read_bytes):
            run = self.run_script(self.docs)
        self.assertEqual(list(run.by_source), ["ok.md"])
        self.assertIn("skip gone.md: unreadable", run.stdout)

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

    def test_unknown_charset_falls_back_to_utf8(self):
        page = "<title>Caf\u00e9</title><p>Cr\u00e8me br\u00fbl\u00e9e.</p>".encode("utf-8")
        self.opener.side_effect = lambda req, timeout: FakeResponse(
            page, req.full_url, "text/html; charset=x-bogus")
        run = self.run_script("--urls", self.urls("https://example.com/menu"))
        self.assertEqual(run.text("https://example.com/menu"),
                         "# Caf\u00e9\n\nCr\u00e8me br\u00fbl\u00e9e.\n")

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
        # A different page each time: two same pages would be one passage.
        self.opener.side_effect = lambda req, timeout: FakeResponse(
            f"<p>Hi from {req.full_url}.</p>".encode(), req.full_url)
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

    def test_the_same_document_twice_is_written_once(self):
        self.write("a/post.md", "---\ntitle: Post\n---\nSame words.\n")
        self.write("b/post.md", "---\ntitle: Post\n---\nSame words.\n")
        run = self.run_script(self.docs)
        self.assertEqual(list(run.by_source), ["a/post.md"])
        self.assertRegex(run.stdout, r"duplicate\s*: 1")

    def test_missing_urls_file_is_a_plain_error(self):
        err = io.StringIO()
        with self.assertRaises(SystemExit), mock.patch.object(sys, "stderr", err):
            run_main(ed, "--urls", str(self.tmp / "nope.txt"), "-o", str(self.out))
        self.assertIn("nope.txt", err.getvalue())

    def test_no_input_is_an_error(self):
        with self.assertRaises(SystemExit):
            run_main(ed, "-o", str(self.out))

    def test_help_runs_as_a_script(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--urls", proc.stdout)


class PassageBase(Base):
    ARGS = ()

    def samples(self, run: Run) -> list[str]:
        return [(self.out / r["file"]).read_text(encoding="utf-8") for r in run.rows]

    def all_text(self, run: Run) -> str:
        return "\n".join(self.samples(run))

    def body_words(self, run: Run, row) -> int:
        """Prose words in a sample: neither the title line nor a heading is counted."""
        text = (self.out / row["file"]).read_text(encoding="utf-8")
        paragraphs = text.split("\n\n")[1:]
        return sum(len(p.split()) for p in paragraphs if not p.startswith("#"))


class BoilerplateTest(PassageBase):
    TAGLINE = "Acme Widgets: making widgets simple since 1999."

    def test_code_tables_nav_footer_legal_and_a_repeated_tagline_never_reach_a_sample(self):
        self.write("a.md", f"# Garden notes\n\n{prose(200, 'a1')}\n\n```python\nCODE-ONE = 1\n\nCODE-TWO = 2\n```\n\n"
                           f"| Plant | TABLE-HEAD |\n|---|---|\n| peas | TABLE-CELL |\n\n{prose(200, 'a2')}\n\n"
                           f"© 2019 Acme LEGAL-TEXT\n\n{self.TAGLINE}\n")
        self.write("b.txt", f"{prose(300, 'b1')}\n\nAll rights reserved RESERVED-TEXT.\n\n{self.TAGLINE}\n")
        self.write("c.html", f"<nav>NAV-TEXT</nav><header>HEADER-TEXT</header><p>{prose(300, 'c1')}</p>"
                             f"<p>{self.TAGLINE}</p><footer>FOOTER-TEXT © 2019</footer>")
        run = self.run_script(self.docs)
        self.assertEqual(sorted(run.by_source), ["a.md", "b.txt", "c.html"])
        text = self.all_text(run)
        for marker in ("CODE-", "TABLE-", "NAV-TEXT", "HEADER-TEXT", "FOOTER-TEXT", "LEGAL-TEXT",
                       "RESERVED-TEXT", "©", "making widgets simple", "```", "|"):
            self.assertNotIn(marker, text)
        self.assertIn(prose(200, "a2"), text)
        self.assertRegex(run.stdout, r"repeated line\s*: 3")
        self.assertIn(self.TAGLINE, run.stdout)

    def test_a_tagline_in_only_two_documents_is_kept(self):
        self.write("a.md", f"{prose(200, 'a1')}\n\n{self.TAGLINE}\n")
        self.write("b.md", f"{prose(200, 'b1')}\n\n{self.TAGLINE}\n")
        run = self.run_script(self.docs)
        self.assertIn(self.TAGLINE, run.text("a.md"))
        self.assertIn(self.TAGLINE, run.text("b.md"))

    def test_a_section_heading_shared_by_three_documents_is_kept(self):
        for i in range(3):
            self.write(f"d{i}.md", f"## Introduction\n\n{prose(200, f'e{i}')}\n")
        run = self.run_script(self.docs)
        for row in run.rows:
            self.assertTrue(run.text(row["source"]).startswith("# d"))
            self.assertIn("\n\nIntroduction\n\n", run.text(row["source"]))
        self.assertNotIn("repeated", run.stdout)

    def test_a_line_repeated_in_the_middle_of_documents_is_not_a_running_line(self):
        for i in range(3):
            tail = "\n\n".join(prose(10, f"d{i}t{j}") for j in range(6))
            self.write(f"d{i}.md", "\n\n".join(prose(10, f"d{i}h{j}") for j in range(6))
                       + f"\n\n{prose(150, f'd{i}x')}\n\nSee the chart below.\n\n{prose(150, f'd{i}y')}\n\n{tail}\n")
        run = self.run_script(self.docs)
        self.assertEqual(len(run.rows), 3)
        for row in run.rows:
            self.assertIn("See the chart below.", run.text(row["source"]))

    def test_line_rules_drop_page_numbers_contents_links_images_and_indented_code(self):
        self.write("doc.md", f"Contents ........ 3\n\n{prose(200, 'p1')}\n\nPage 3 of 12\n\n"
                             f"![a chart](chart.png)\n\n- [Home](/) | [About](/about)\n\nhttps://example.com/x\n\n"
                             f"    INDENTED-CODE = 1\n    more = 2\n\n{prose(100, 'p2')}\n")
        run = self.run_script(self.docs)
        self.assertEqual(run.text("doc.md"), f"# doc\n\n{prose(200, 'p1')}\n\n{prose(100, 'p2')}\n")
        self.assertRegex(run.stdout, r"code\s*: 2")
        self.assertRegex(run.stdout, r"page number\s*: 1")
        self.assertRegex(run.stdout, r"contents line\s*: 1")
        self.assertRegex(run.stdout, r"link or image\s*: 3")

    def test_prose_that_mentions_cookies_or_starts_indented_in_a_text_file_is_kept(self):
        long_para = f"My grandmother kept her cookie recipe in a tin. {prose(150, 'c1')}"
        self.write("doc.txt", f"    {prose(100, 'i1')}\n\n{long_para}\n")
        run = self.run_script(self.docs)
        self.assertIn(long_para, run.text("doc.txt"))
        self.assertIn(prose(100, "i1"), run.text("doc.txt"))

    def test_a_fence_that_opens_on_a_short_chrome_like_line_still_hides_the_code(self):
        self.write("doc.md", f"{prose(200, 'g1')}\n\n```\ncookie = 1\n\nCODE-AFTER = 2\n```\n\n{prose(100, 'g2')}\n")
        run = self.run_script(self.docs)
        self.assertEqual(run.text("doc.md"), f"# doc\n\n{prose(200, 'g1')}\n\n{prose(100, 'g2')}\n")

    def test_an_unclosed_fence_drops_the_rest_of_the_document(self):
        self.write("doc.md", f"{prose(200, 'k1')}\n\n```\nCODE-A\n\n{prose(100, 'k2')}\n")
        run = self.run_script(self.docs)
        self.assertEqual(run.text("doc.md"), f"# doc\n\n{prose(200, 'k1')}\n")

    def test_a_document_that_is_80_percent_boilerplate_is_dropped_whole(self):
        links = "\n".join(f"- [Our page number {i}](/p{i})" for i in range(40))  # 40 x 5 words
        legal = ("We use cookies to give you the best experience on our site. By continuing to browse "
                 "you agree to our cookie policy and our terms of use for this site.")  # 30 words
        chrome = f"{links}\n\n" + "\n\n".join([legal] * 6) + "\n\n\u00a9 2020 Acme Inc. All rights reserved.\n"
        self.write("chrome.md", f"{prose(100, 'm1')}\n\n{chrome}")  # 100 of 506 words are prose
        few_links = "\n".join(links.split("\n")[:10])
        self.write("fine.md", f"{prose(260, 'f1')}\n\n{legal}\n\n{few_links}\n")  # 80 of 340 words
        run = self.run_script(self.docs)
        self.assertEqual(list(run.by_source), ["fine.md"])
        self.assertEqual(run.text("fine.md"), f"# fine\n\n{prose(260, 'f1')}\n")
        self.assertIn("skip chrome.md: mostly boilerplate", run.stdout)
        self.assertRegex(run.stdout, r"mostly boilerplate\s*: 1")
        self.assertRegex(run.stdout, r"legal or site chrome\s*: 8")
        self.assertRegex(run.stdout, r"link or image\s*: 50")

    def test_a_document_with_a_long_code_block_and_real_prose_is_kept(self):
        code = "\n".join(f"line_{i} = {i}" for i in range(40))
        self.write("tech.md", f"{prose(120, 't1')}\n\n```\n{code}\n```\n\n{prose(120, 't2')}\n")
        run = self.run_script(self.docs)
        self.assertEqual(run.text("tech.md"), f"# tech\n\n{prose(120, 't1')}\n\n{prose(120, 't2')}\n")


class PassageTest(PassageBase):
    def test_an_1800_word_document_gives_passages_of_150_to_500_words_with_no_paragraph_cut(self):
        sizes = [40, 120, 90, 60, 140, 75, 110, 55, 130, 95, 85, 65, 135, 100, 80, 70, 125, 125, 100]
        self.assertEqual(sum(sizes), 1800)
        paragraphs = [prose(n, f"q{i}") for i, n in enumerate(sizes)]
        self.write("long.md", "\n\n".join(paragraphs) + "\n")
        run = self.run_script(self.docs)
        self.assertGreater(len(run.rows), 3)
        seen = []
        for row in run.rows:
            self.assertTrue(150 <= int(row["words"]) <= 500, row)
            self.assertEqual(int(row["words"]), self.body_words(run, row))
            body = (self.out / row["file"]).read_text(encoding="utf-8").split("\n\n")[1:]
            seen += [p.strip() for p in body]
        self.assertEqual(sorted(seen), sorted(paragraphs))
        names = sorted(r["file"] for r in run.rows)
        self.assertEqual([n.split("_")[1] for n in names], [f"{i:02d}" for i in range(1, len(names) + 1)])

    def test_the_tail_is_merged_into_the_previous_passage_up_to_500_words(self):
        self.write("doc.md", "\n\n".join(prose(n, f"r{i}") for i, n in enumerate([350, 350, 400, 50, 50])))
        run = self.run_script(self.docs)
        self.assertEqual(sorted(int(r["words"]) for r in run.rows), [350, 350, 500])
        self.assertNotRegex(run.stdout, r"too short")

    def test_a_tail_that_would_make_the_passage_over_500_words_is_dropped_as_too_short(self):
        self.write("doc.md", "\n\n".join(prose(n, f"s{i}") for i, n in enumerate([300, 350, 450, 50, 50])))
        run = self.run_script(self.docs)
        self.assertEqual(sorted(int(r["words"]) for r in run.rows), [300, 350, 450])
        self.assertNotIn(prose(50, "s3"), self.all_text(run))
        self.assertRegex(run.stdout, r"too short\s*: 1")

    def test_a_short_passage_in_the_middle_joins_the_previous_one_when_it_fits(self):
        self.write("fits.md", "\n\n".join(prose(n, f"u{i}") for i, n in enumerate([350, 100, 450])))
        self.write("over.md", "\n\n".join(prose(n, f"z{i}") for i, n in enumerate([480, 100, 450])))
        run = self.run_script(self.docs)
        words = collections.defaultdict(list)
        for r in run.rows:
            words[r["source"]].append(int(r["words"]))
        self.assertEqual({k: sorted(v) for k, v in words.items()}, {"fits.md": [450, 450], "over.md": [450, 480]})
        self.assertRegex(run.stdout, r"too short\s*: 1")

    def test_a_short_document_is_kept_whole_from_60_words(self):
        self.write("short.md", prose(60, "v1"))
        self.write("tiny.md", prose(59, "v2"))
        run = self.run_script(self.docs)
        self.assertEqual(list(run.by_source), ["short.md"])
        self.assertRegex(run.stdout, r"too short\s*: 1")

    def test_min_words_sets_the_shortest_passage(self):
        self.write("doc.md", "\n\n".join(prose(n, f"w{i}") for i, n in enumerate([400, 400, 120])))
        run = self.run_script(self.docs, "--min-words", "100")
        self.assertEqual(sorted(int(r["words"]) for r in run.rows), [120, 400, 400])
        self.out = self.tmp / "samples2"
        run = self.run_script(self.docs)
        self.assertEqual(sorted(int(r["words"]) for r in run.rows), [400, 400])

    def test_one_paragraph_over_500_words_is_split_at_sentence_ends(self):
        para = prose(1200, "x1")
        self.write("wall.txt", para)
        run = self.run_script(self.docs)
        pieces = [(self.out / r["file"]).read_text(encoding="utf-8").split("\n\n", 1)[1].strip()
                  for r in sorted(run.rows, key=lambda r: r["file"])]
        self.assertGreaterEqual(len(pieces), 3)
        for piece in pieces:
            self.assertTrue(150 <= len(piece.split()) <= 500, len(piece.split()))
            self.assertTrue(piece.endswith("."))
        self.assertEqual(sorted(" ".join(pieces).split()), sorted(para.split()))

    def test_a_sentence_over_500_words_is_cut_at_500(self):
        self.write("blob.txt", " ".join(f"y{i}" for i in range(1100)))
        run = self.run_script(self.docs)
        self.assertEqual(sorted(int(r["words"]) for r in run.rows), [500, 500])
        self.assertRegex(run.stdout, r"too short\s*: 1")

    def test_a_heading_stays_only_as_the_first_line_and_is_not_counted(self):
        self.write("doc.md", f"# Part one\n\n{prose(360, 'h1')}\n\n## Part two\nPart two is next\n\n"
                             f"{prose(200, 'h2')}\n\n## Aside\n\n{prose(100, 'h3')}\n\n# Trailing heading\n")
        run = self.run_script(self.docs)
        texts = sorted(self.samples(run))
        self.assertEqual(texts, [f"# doc\n\nPart one\n\n{prose(360, 'h1')}\n",
                                 f"# doc\n\nPart two\n\nPart two is next\n\n{prose(200, 'h2')}\n\n"
                                 f"{prose(100, 'h3')}\n"])
        self.assertEqual(sorted(int(r["words"]) for r in run.rows), [304, 360])

    def test_a_heading_with_no_blank_line_before_it_starts_the_next_passage(self):
        self.write("doc.md", f"{prose(360, 'n1')}\n## Next part\n{prose(200, 'n2')}\n")
        run = self.run_script(self.docs)
        self.assertEqual(sorted(self.samples(run)), [f"# doc\n\nNext part\n\n{prose(200, 'n2')}\n",
                                                    f"# doc\n\n{prose(360, 'n1')}\n"])
        self.assertEqual(sorted(int(r["words"]) for r in run.rows), [200, 360])

    def test_a_short_sentence_before_one_over_500_words_keeps_its_place(self):
        long = " ".join(f"z{i}" for i in range(1100))
        para = f"Short first. {long}"
        self.assertEqual(ed.split_paragraph(para),
                         ["Short first.", " ".join(long.split()[:500]),
                          " ".join(long.split()[500:1000]), " ".join(long.split()[1000:])])
        self.assertEqual([len(p.split()) for p in ed.split_paragraph(para)], [2, 500, 500, 100])
        self.assertEqual(" ".join(ed.split_paragraph(para)).split(), para.split())

    def test_a_document_of_headings_only_has_no_text(self):
        self.write("heads.md", "# One\n\n## Two\n")
        run = self.run_script(self.docs)
        self.assertEqual(run.rows, [])
        self.assertRegex(run.stdout, r"no text\s*: 1")


class DedupeAndCapTest(PassageBase):
    def test_two_copies_of_one_article_give_one_set_of_passages(self):
        article = "\n\n".join(prose(n, f"art{i}") for i, n in enumerate([300, 200, 350, 250]))
        self.write("post.md", f"---\ntitle: The Post\ndate: 2018-03-01\n---\n{article}\n")
        self.write("post.txt", article + "\n")
        run = self.run_script(self.docs)
        self.assertEqual({r["source"] for r in run.rows}, {"post.md"})
        self.assertEqual(len(run.rows), 3)
        self.assertRegex(run.stdout, r"duplicate\s*: 3")

    def test_a_passage_sharing_half_its_5_grams_with_a_longer_one_is_a_duplicate(self):
        base = prose(300, "dup")
        self.write("a.md", base)
        self.write("b.md", " ".join(base.split()[:160]) + " " + prose(100, "other"))
        self.write("c.md", " ".join(base.split()[:120]) + " " + prose(180, "third"))
        run = self.run_script(self.docs)
        self.assertEqual(sorted(run.by_source), ["a.md", "c.md"])
        self.assertRegex(run.stdout, r"duplicate\s*: 1")

    def test_200_passages_across_10_documents_keep_148_and_every_document(self):
        # One document is far longer and its passages are longer, so taking
        # the longest first would leave the other nine out.
        self.write("big.md", "\n\n".join(prose(400, f"big{i}") for i in range(155)))
        for d in range(9):
            self.write(f"small{d}.md", "\n\n".join(prose(350, f"s{d}p{i}") for i in range(5)))
        run = self.run_script(self.docs)
        self.assertEqual(len(run.rows), 148)
        counts = collections.Counter(r["source"] for r in run.rows)
        self.assertEqual(len(counts), 10)
        for d in range(9):
            self.assertEqual(counts[f"small{d}.md"], 5)
        self.assertRegex(run.stdout, r"over the cap\s*: 52")

    def test_max_samples_sets_the_cap_and_0_means_no_cap(self):
        for d in range(3):
            self.write(f"d{d}.md", "\n\n".join(prose(350, f"m{d}p{i}") for i in range(3)))
        run = self.run_script(self.docs, "--max-samples", "4")
        self.assertEqual(len(run.rows), 4)
        self.assertEqual(len({r["source"] for r in run.rows}), 3)
        self.out = self.tmp / "all"
        run = self.run_script(self.docs, "--max-samples", "0")
        self.assertEqual(len(run.rows), 9)

    def test_default_cap_and_passage_sizes_match_the_plan(self):
        es = load(BUILD / "extract-samples.py", "extract_samples_for_docs")
        self.assertEqual(ed.MAX_SAMPLES, es.MAX_SAMPLES)
        self.assertEqual((ed.MIN_WORDS, ed.TARGET_WORDS, ed.MAX_WORDS, ed.SHORT_DOC_WORDS),
                         (150, 350, 500, 60))

    def test_output_is_identical_when_the_input_files_are_given_in_reverse_order(self):
        tagline = "Read the whole series at example.com."
        paths = []
        for d in range(6):
            body = "\n\n".join(prose(350, f"o{d}p{i}") for i in range(3))
            paths.append(self.write(f"doc{d}.md", f"{body}\n\n{tagline}\n"))
        same = prose(350, "same") + "\n"
        paths.append(self.write("copy-a.txt", same))
        paths.append(self.write("copy-b.md", same))

        def snapshot(name, args):
            self.out = self.tmp / name
            self.run_script(*args, "--max-samples", "10")
            return {p.name: p.read_bytes() for p in sorted(self.out.iterdir())}

        forward = snapshot("forward", paths)
        backward = snapshot("backward", paths[::-1])
        self.assertEqual(len(forward), 11)
        self.assertEqual(forward, backward)


    def test_two_folders_with_the_same_relative_path_give_the_same_output_in_any_order(self):
        same = prose(300, "twin")
        one = self.write("one/post.md", f"---\ntitle: First Title\n---\n{same}\n").parent
        two = self.write("two/post.md", f"---\ntitle: Second Title\n---\n{same}\n").parent

        def snapshot(name, *args):
            self.out = self.tmp / name
            self.run_script(*args)
            return {p.name: p.read_bytes() for p in sorted(self.out.iterdir())}

        self.assertEqual(snapshot("forward", one, two), snapshot("backward", two, one))

    def test_a_negative_cap_or_minimum_is_a_plain_error(self):
        for flag in ("--max-samples", "--min-words"):
            err = io.StringIO()
            with self.assertRaises(SystemExit), mock.patch.object(sys, "stderr", err):
                run_main(ed, str(self.docs), flag, "-1", "-o", str(self.out))
            self.assertIn(flag, err.getvalue())


    def test_two_passages_that_would_share_a_file_name_write_one_file(self):
        self.write("a.md", f"---\ntitle: Same\n---\n{prose(200, 'fa')}\n")
        self.write("b.md", f"---\ntitle: Same\n---\n{prose(200, 'fb')}\n")
        real = ed._key
        with mock.patch.object(ed, "_key", lambda text: "abcdef" + real(text)):
            run = self.run_script(self.docs)
        self.assertEqual(len(run.rows), 1)
        self.assertEqual(run.rows[0]["file"], "same_01_abcdef.md")
        self.assertEqual(run.text(run.rows[0]["source"]).split("\n\n", 1)[1],
                         (self.docs / run.rows[0]["source"]).read_text().split("---\n")[-1])
        self.assertRegex(run.stdout, r"duplicate\s*: 1")


class OneDocumentTest(PassageBase):
    """Bugs 3 and 4 of the real run: one article saved three ways is one
    document, and a passage that straddles two kept passages is a duplicate."""

    def write_real_run(self) -> list[Path]:
        """The 3 copies of one article plus two other articles, as the real run read them."""
        return [
            self.write("article.md", real_run("copy_article_html.md")),
            self.write("article-pdf.txt", real_run("copy_article_pdf.txt")),
            self.write("article-docx.md", real_run("copy_article_docx.md")),
            self.write("faster.md", real_run_body("prose_72faster_a.md") + "\n\n"
                       + real_run_body("prose_72faster_b.md") + "\n"),
            self.write("llmenv.md", real_run_body("prose_llmenv_a.md") + "\n\n"
                       + real_run_body("prose_llmenv_b.md") + "\n"),
        ]

    def test_three_copies_of_one_article_give_rows_with_one_source(self):
        self.write_real_run()
        run = self.run_script(self.docs)
        copies = {"article.md", "article-pdf.txt", "article-docx.md"}
        article = [r for r in run.rows if r["subject"] in
                   {"article", "article-pdf", "article-docx"}]
        self.assertGreater(len(article), 1)
        self.assertEqual(len({r["source"] for r in article}), 1)
        self.assertIn(article[0]["source"], copies)

    def test_two_different_articles_are_not_merged(self):
        self.write_real_run()
        run = self.run_script(self.docs)
        sources = collections.Counter(r["source"] for r in run.rows)
        self.assertEqual(len(sources), 3)
        self.assertIn("faster.md", sources)
        self.assertIn("llmenv.md", sources)

    def test_the_report_says_how_many_documents_are_distinct(self):
        self.write_real_run()
        run = self.run_script(self.docs)
        self.assertIn("read 5 documents (3 distinct), wrote", run.stdout)

    def test_the_straddling_passage_from_the_real_run_is_a_duplicate(self):
        self.write_real_run()
        run = self.run_script(self.docs)
        # html#1 (the ranked results) is half in the pdf copy, half in the docx copy.
        self.assertNotIn("article", {r["subject"] for r in run.rows})
        self.assertRegex(run.stdout, r"duplicate\s*: 3")

    def test_a_passage_built_from_halves_of_two_kept_passages_is_dropped(self):
        a, b = prose(400, "half-a").split(), prose(400, "half-b").split()
        self.write("a.md", " ".join(a))
        self.write("b.md", " ".join(b))
        # 180 + 180 words: each pairwise share is 176/356, under DUPLICATE_SHARE.
        self.write("c.md", " ".join(a[-180:] + b[:180]))
        self.write("d.md", prose(300, "different"))
        # A third of it repeats a kept passage: still its own passage.
        self.write("e.md", " ".join(a[:100]) + " " + prose(200, "own"))
        run = self.run_script(self.docs)
        self.assertEqual(sorted(run.by_source), ["a.md", "b.md", "d.md", "e.md"])
        self.assertRegex(run.stdout, r"duplicate\s*: 1")

    def test_a_passage_half_among_the_passages_kept_before_it_is_dropped_there(self):
        # c.md is 146/376 in a.md and 96/376 in b.md, 0.64 in both: dropped when
        # it is read. Kept until the last pass, it would cover 0.74 of a.md and
        # drop a.md instead.
        x, y, a = (prose(n, t).split() for n, t in ((150, "sx"), (150, "sy"), (100, "sa")))
        b, c = prose(240, "sb").split(), prose(130, "sc").split()
        self.write("a.md", " ".join(x + y + a))
        self.write("b.md", " ".join(x + b))
        self.write("c.md", " ".join(y + b[:100] + c))
        run = self.run_script(self.docs)
        self.assertEqual(sorted(run.by_source), ["a.md", "b.md"])
        self.assertRegex(run.stdout, r"duplicate\s*: 1")
        self.assertIn("read 3 documents, wrote", run.stdout)

    def test_a_document_repeating_itself_is_not_merged_with_one_sharing_a_phrase(self):
        passage = prose(345, "self").replace("self-0 ", "the quick brown fox jumps ")
        self.write("x.md", f"{passage}\n\n{passage}\n")
        self.write("y.md", "the quick brown fox jumps " + prose(400, "y"))
        run = self.run_script(self.docs)
        self.assertEqual(sorted(r["source"] for r in run.rows), ["x.md", "y.md"])
        self.assertRegex(run.stdout, r"duplicate\s*: 1")
        self.assertIn("read 2 documents, wrote", run.stdout)

    def test_output_is_identical_when_the_real_run_inputs_are_given_in_reverse_order(self):
        paths = self.write_real_run()

        def snapshot(name, args):
            self.out = self.tmp / name
            run = self.run_script(*args)
            return run.stdout.replace(str(self.out), "OUT"), {
                p.name: p.read_bytes() for p in sorted(self.out.iterdir())}

        self.assertEqual(snapshot("forward", paths), snapshot("backward", paths[::-1]))


class GroupTest(unittest.TestCase):
    """group(): which sources are one document, and its canonical name."""

    @staticmethod
    def cand(source, text, words=None):
        return {"title": source, "date": None, "source": source, "n": 1, "text": text,
                "words": words or len(text.split()), "key": ed._key(text)}

    def test_a_source_that_shares_half_its_text_with_another_is_the_same_document(self):
        long, short = prose(400, "g"), prose(400, "g").split()
        cands = [self.cand("long.md", long),
                 self.cand("short.md", " ".join(short[:200] + prose(150, "s").split()))]
        self.assertEqual(ed.group(cands, []), {"long.md": "long.md", "short.md": "long.md"})

    def test_a_source_sharing_under_half_is_its_own_document(self):
        words = prose(400, "g").split()
        cands = [self.cand("long.md", " ".join(words)),
                 self.cand("other.md", " ".join(words[:100] + prose(300, "o").split()))]
        self.assertEqual(ed.group(cands, []), {"long.md": "long.md", "other.md": "other.md"})

    def test_a_lost_passage_joins_the_sources_and_the_first_in_order_names_them(self):
        cands = [self.cand("b.md", prose(200, "x")), self.cand("a.md", prose(300, "y")),
                 self.cand("c.md", prose(100, "z"))]
        self.assertEqual(ed.group(cands, [("c.md", "b.md"), ("b.md", "a.md")]),
                         {"a.md": "a.md", "b.md": "a.md", "c.md": "a.md"})


class BeforeTest(PassageBase):
    def test_before_drops_a_later_document_and_keeps_an_undated_one_with_the_count(self):
        self.write("old.md", f"---\ndate: 2019-05-01\n---\n{prose(200, 'old')}\n")
        self.write("new.md", f"---\ndate: 2023-01-02\n---\n{prose(200, 'new')}\n")
        self.write("cut.md", f"---\ndate: 2022-11-30\n---\n{prose(200, 'cut')}\n")
        self.write("nodate.md", prose(200, "nodate"))
        run = self.run_script(self.docs, "--before", "2022-11-30")
        self.assertEqual(sorted(run.by_source), ["nodate.md", "old.md"])
        self.assertEqual(run.by_source["nodate.md"]["date"], "undated")
        self.assertIn("skip new.md: on or after --before", run.stdout)
        self.assertRegex(run.stdout, r"on or after --before\s*: 2")
        self.assertIn("kept 1 undated document", run.stdout)

    def test_a_tagline_counted_only_in_documents_after_the_cutoff_is_kept(self):
        tagline = "Thanks for reading the Acme newsletter."
        self.write("old.md", f"---\ndate: 2019-05-01\n---\n{prose(200, 'old')}\n\n{tagline}\n")
        for i in range(2):
            self.write(f"new{i}.md", f"---\ndate: 2023-01-0{i + 1}\n---\n{prose(200, f'new{i}')}\n\n{tagline}\n")
        run = self.run_script(self.docs, "--before", "2022-01-01")
        self.assertIn(tagline, run.text("old.md"))
        self.assertNotIn("repeated", run.stdout)

    def test_a_bad_before_date_is_a_plain_error(self):
        err = io.StringIO()
        with self.assertRaises(SystemExit), mock.patch.object(sys, "stderr", err):
            run_main(ed, str(self.docs), "--before", "May 2020", "-o", str(self.out))
        self.assertIn("YYYY-MM-DD", err.getvalue())


class TitleSuffixTest(Base):
    """Bug 8 of the real run: every dev.to title ended " - DEV Community"."""

    def urls(self, pages: dict) -> Path:
        self.opener.side_effect = lambda req, timeout: FakeResponse(pages[req.full_url], req.full_url)
        path = self.tmp / "urls.txt"
        path.write_text("\n".join(pages) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def page(title: str, tag: str) -> bytes:
        return f"<title>{title}</title><p>{prose(20, tag)}</p>".encode()

    def test_a_site_name_shared_by_three_page_titles_is_dropped(self):
        titles = [real_run(f"prose_{n}_a.md").partition("\n")[0][2:]
                  for n in ("72faster", "comparing13", "llmenv")]
        self.assertTrue(all(t.endswith(" - DEV Community") for t in titles))
        pages = {f"https://dev.to/sam/{i}": self.page(t, f"t{i}") for i, t in enumerate(titles)}
        run = self.run_script("--urls", self.urls(pages))
        got = sorted(r["subject"] for r in run.rows)
        self.assertEqual(got, sorted(t[:-len(" - DEV Community")] for t in titles))
        self.assertIn("Stop Juggling API Keys: Meet llm-env — One Command, Any LLM Provider", got)
        for url in pages:
            self.assertNotIn("DEV Community", run.text(url))

    def test_a_site_name_on_a_single_page_is_kept(self):
        pages = {"https://dev.to/sam/one": self.page("My Post - DEV Community", "one"),
                 "https://example.com/two": self.page("Other Post - Example Blog", "two")}
        run = self.run_script("--urls", self.urls(pages))
        self.assertEqual(sorted(r["subject"] for r in run.rows),
                         ["My Post - DEV Community", "Other Post - Example Blog"])

    def test_other_separators_and_only_the_last_one_count(self):
        self.assertEqual(ed.strip_site_names(["A - B | Acme", "C \u2013 Acme", "D \u2014 Acme", "E-Acme",
                                              "Notes | Other"]),
                         ["A - B", "C", "D", "E-Acme", "Notes | Other"])

    def test_a_file_title_is_not_a_site_name(self):
        self.write("a.md", f"---\ntitle: Notes - Draft\n---\n{prose(20, 'a')}\n")
        self.write("b.md", f"---\ntitle: Plans - Draft\n---\n{prose(20, 'b')}\n")
        run = self.run_script(self.docs)
        self.assertEqual(sorted(r["subject"] for r in run.rows), ["Notes - Draft", "Plans - Draft"])


class HeadingMarkTest(PassageBase):
    """Bug 8: heading lines were written into the sample text as "# ..." lines."""

    def body_lines(self, run: Run) -> list[str]:
        """Every sample line after the "# <title>" header."""
        return [l for s in self.samples(run) for l in s.split("\n")[1:]]

    def test_no_sample_line_starts_with_a_hash_for_html_input(self):
        self.write("page.html", f"<title>Page</title><h1>Main part</h1><p>{prose(200, 'h1')}</p>"
                                f"<h2>Second part</h2><p>{prose(200, 'h2')}</p>")
        run = self.run_script(self.docs)
        lines = self.body_lines(run)
        self.assertEqual([l for l in lines if l.startswith("#")], [])
        self.assertIn("Main part", lines)

    def test_no_sample_line_starts_with_a_hash_for_docx_input(self):
        self.write("guide.docx", docx_bytes([prose(200, "d1")], headings=["Our voice"]))
        run = self.run_script(self.docs)
        lines = self.body_lines(run)
        self.assertEqual([l for l in lines if l.startswith("#")], [])
        self.assertIn("Our voice", lines)

    def test_a_heading_is_still_not_counted_as_prose(self):
        self.write("guide.docx", docx_bytes([prose(200, "d1")], headings=["Our voice"]))
        run = self.run_script(self.docs)
        self.assertEqual(run.rows[0]["words"], "200")


class PageNumberLabelTest(PassageBase):
    """Bug 8: a numbered section label "01" was removed as a page number."""

    def test_a_section_label_before_a_heading_is_kept_as_text(self):
        self.write("doc.md", f"{prose(200, 'p1')}\n\n01\n\n## Getting started\n\n{prose(200, 'p2')}\n")
        run = self.run_script(self.docs)
        self.assertIn("\n01\n", self.all_text(run))
        self.assertNotIn("page number", run.stdout)

    def test_a_section_label_before_a_short_title_cased_line_is_kept(self):
        self.write("doc.txt", f"{prose(200, 'p1')}\n\n02\nWhy Latency Matters\n\n{prose(200, 'p2')}\n")
        run = self.run_script(self.docs)
        self.assertIn("02\nWhy Latency Matters", self.all_text(run))
        self.assertNotIn("page number", run.stdout)

    def test_a_bare_number_before_prose_is_still_a_page_number(self):
        self.write("doc.txt", f"{prose(200, 'p1')}\n\n7\n\n{prose(200, 'p2')}\n")
        run = self.run_script(self.docs)
        self.assertNotIn("\n7\n", self.all_text(run))
        self.assertRegex(run.stdout, r"page number\s*: 1")

    def test_a_bare_number_before_a_line_that_is_not_a_short_title_is_a_page_number(self):
        cases = {
            "03\nthe results were slow": "lowercase",
            "03\nand Then Latency Matters": "first word lowercase, the rest capitalized",
            "03\nWhy the results were so slow": "first word capitalized, most not",
            "03\nWhy Latency Matters.": "a sentence end",
            "03\nWhy The Latency Of These Providers Matters So Much": "9 words, over the 8-word cap",
            "003\nWhy Latency Matters": "3 digits, not 01 to 99",
        }
        for i, (lines, why) in enumerate(cases.items()):
            with self.subTest(why):
                label, line = lines.split("\n")
                self.write(f"doc{i}.txt", f"{prose(200, f'a{i}')}\n\n{lines}\n\n{prose(200, f'b{i}')}\n")
                run = self.run_script(self.docs / f"doc{i}.txt")
                text = self.all_text(run)
                self.assertNotIn(f"\n{label}\n", text)
                self.assertIn(f"\n{line}\n", text)
                self.assertRegex(run.stdout, r"page number\s*: 1")
                shutil.rmtree(self.out)

    @unittest.skipIf(os.name == "nt", "the pdftotext stub is a shell script")
    def test_a_lone_number_on_a_page_break_is_still_removed(self):
        # The page's number, then the next page opening with a title-cased heading.
        self.write("report.pdf", f"{prose(200, 'p1')}\n\n7\n\fWhy Latency Matters\n\n{prose(200, 'p2')}\n"
                                 f"\f8\n\nResults And Notes\n\n{prose(100, 'p3')}\n")
        path = self.pdftotext_stub('for a; do prev="$last"; last="$a"; done\nexec cat "$prev"\n')
        with mock.patch.dict(os.environ, {"PATH": path}):
            run = self.run_script(self.docs)
        text = self.all_text(run)
        self.assertNotIn("\n7\n", text)
        self.assertNotIn("\n8\n", text)
        self.assertIn("Why Latency Matters", text)
        self.assertRegex(run.stdout, r"page number\s*: 2")


@unittest.skipIf(os.name == "nt", "the pdftotext stub is a shell script")
class HyphenJoinTest(PassageBase):
    """Bug 8: pdftotext keeps a word broken by a hyphen at a line end."""

    def pdf_text(self, text: str) -> str:
        self.write("report.pdf", text)
        path = self.pdftotext_stub('for a; do prev="$last"; last="$a"; done\nexec cat "$prev"\n')
        with mock.patch.dict(os.environ, {"PATH": path}):
            run = self.run_script(self.docs)
        return self.all_text(run)

    def test_a_broken_word_found_whole_elsewhere_is_joined(self):
        text = self.pdf_text(f"{prose(100, 'a')} We need real-\ntime answers here.\n\n"
                             f"{prose(100, 'b')} A realtime system is fast.\n")
        self.assertIn("We need realtime\nanswers here.", text)
        self.assertNotIn("real-", text)

    def test_a_broken_word_alone_on_its_line_joins_without_a_paragraph_break(self):
        text = self.pdf_text(f"{prose(100, 'a')} We need real-\ntime\nanswers here.\n\n"
                             f"{prose(100, 'b')} A Realtime system is fast.\n")
        self.assertIn("We need realtime\nanswers here.", text)

    def test_with_no_whole_word_elsewhere_the_line_is_left_alone(self):
        out = self.pdf_text(f"{prose(100, 'a')} Offering near real-\ntime responses.\n\n{prose(100, 'b')}\n")
        self.assertIn("near real-\ntime responses.", out)

    def test_a_join_is_not_reported(self):
        self.write("report.pdf", f"{prose(100, 'a')} real-\ntime\n\n{prose(100, 'b')} realtime.\n")
        path = self.pdftotext_stub('for a; do prev="$last"; last="$a"; done\nexec cat "$prev"\n')
        with mock.patch.dict(os.environ, {"PATH": path}):
            run = self.run_script(self.docs)
        self.assertNotIn("hyphen", run.stdout)
        self.assertNotIn("join", run.stdout)

    def test_join_hyphens_leaves_a_hyphenated_continuation_and_a_capital_alone(self):
        self.assertEqual(ed.join_hyphens("near real-\ntime-critical work\nrealtime"),
                         "near real-\ntime-critical work\nrealtime")
        self.assertEqual(ed.join_hyphens("New-\nYork\nnewyork"), "New-\nYork\nnewyork")
        self.assertEqual(ed.join_hyphens("a real-\ntime, b\nrealtime"), "a realtime,\nb\nrealtime")

    def test_text_files_are_not_joined(self):
        self.write("note.txt", f"{prose(100, 'a')} We need real-\ntime answers.\n\n{prose(100, 'b')} realtime.\n")
        run = self.run_script(self.docs)
        self.assertIn("real-\ntime", self.all_text(run))


if __name__ == "__main__":
    unittest.main()
