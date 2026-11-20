#!/usr/bin/env python3
"""Extract writing samples from documents into one .md file each.

Reads the files and folders given (folders recursively, in sorted order,
skipping hidden files, Office lock files that start with "~$" and symlinks)
and the pages listed in --urls:

  .md, .txt     UTF-8 text; a leading "---" front matter block gives
                "title:" and "date:" and is then dropped
  .html, .htm   headings, paragraphs and list items; navigation, headers,
                footers, scripts, code, tables, quotes and forms are dropped
  .docx         the paragraphs of the main document; tables, headers and
                footers are dropped
  .pdf          through the pdftotext program (poppler) when it is on PATH
  --urls FILE   one http(s) URL per line, fetched from this machine and read
                as HTML (or as text for a text/plain page); "#" lines are
                comments. Use it only for pages you own.

Anything else is skipped and counted. Each document is written whole as
``# <title>`` followed by its text, and index.csv lists every sample with the
columns file, date, words, subject, source.
"""
from __future__ import annotations
import argparse
import collections
import csv
import datetime
import hashlib
import html.parser
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MAX_FILE_BYTES = 20 * 1024 * 1024
# The uncompressed size of word/document.xml. zipfile stops reading an entry
# at the size the archive declares, so checking that size is enough.
MAX_DOCX_XML_BYTES = 50 * 1024 * 1024
PDFTOTEXT_TIMEOUT = 30
# A scanned PDF has no text layer; pdftotext gives at most a page number or two.
PDF_MIN_WORDS = 50
URL_TIMEOUT = 20
MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_URLS = 100
URL_PAUSE = 1  # seconds between two requests

READERS = {".md": "text", ".txt": "text", ".html": "html", ".htm": "html",
           ".docx": "docx", ".pdf": "pdf"}
NO_PDFTOTEXT = ("no pdftotext: to read a PDF, install poppler (it provides pdftotext), "
                "or open the PDF and save it as .docx or .txt")

FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)^---[ \t]*$\n?", re.S | re.M)
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class Skip(Exception):
    """A document that is not read; the message is the reason in the report."""


def _paragraphs(text: str) -> list[str]:
    """Blocks separated by blank lines, with their line breaks kept."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n[ \t]*\n", text)
    out = []
    for b in blocks:
        b = "\n".join(l.rstrip() for l in b.split("\n")).strip("\n")
        if b.strip():
            out.append(b)
    return out


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v.strip()


def _date(v: str) -> str | None:
    m = DATE.match(_unquote(v))
    if not m:
        return None
    try:
        return datetime.date.fromisoformat(m.group()).isoformat()
    except ValueError:
        return None


def read_text(text: str, stem: str):
    """Markdown or plain text: (title, date, paragraphs)."""
    title, date = stem, None
    m = FRONT_MATTER.match(text.replace("\r\n", "\n"))
    if m:
        for line in m.group(1).split("\n"):
            key, sep, value = line.partition(":")
            if not sep:
                continue
            key = key.strip().lower()
            if key == "title" and _unquote(value):
                title = _unquote(value)
            elif key == "date":
                date = _date(value)
        text = text.replace("\r\n", "\n")[m.end():]
    return title, date, _paragraphs(text)


class _HTMLText(html.parser.HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "form", "pre",
            "code", "table", "figure", "blockquote", "template", "noscript", "svg"}
    BLOCK = {"p", "li", "div", "section", "article", "main", "br", "ul", "ol",
             "dd", "dt", "body", "hr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__()
        self.skip = 0
        self.in_title = False
        self.title = ""
        self.level = 0
        self.buf: list[str] = []
        self.paragraphs: list[str] = []

    def flush(self):
        text = " ".join("".join(self.buf).split())
        self.buf = []
        if text:
            self.paragraphs.append(f"{'#' * self.level} {text}" if self.level else text)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag in self.BLOCK and not self.skip:
            self.flush()
            if re.fullmatch(r"h[1-6]", tag):
                self.level = int(tag[1])

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "title":
            self.in_title = False
        elif tag in self.BLOCK and not self.skip:
            self.flush()
            if re.fullmatch(r"h[1-6]", tag):
                self.level = 0

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.buf.append(data)


def read_html(text: str, stem: str):
    """HTML: (title, date, paragraphs). Headings are written as "# ..." lines."""
    p = _HTMLText()
    p.feed(text)
    p.close()
    p.flush()
    title = " ".join(p.title.split()) or stem
    return title, None, p.paragraphs


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_paragraphs(el):
    for child in el:
        if child.tag == W + "p":
            yield child
        elif child.tag != W + "tbl":
            yield from _docx_paragraphs(child)


def read_docx(path: Path, stem: str):
    """Word document: (title, date, paragraphs) from word/document.xml only."""
    try:
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("word/document.xml")
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise Skip("docx too large")
            root = ET.fromstring(z.read(info))
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError, RuntimeError, EOFError):
        raise Skip("unreadable")
    body = root.find(W + "body")
    paragraphs = []
    for p in _docx_paragraphs(body if body is not None else root):
        parts = []
        for el in p.iter():
            if el.tag == W + "t":
                parts.append(el.text or "")
            elif el.tag == W + "tab":
                parts.append(" ")
            elif el.tag in (W + "br", W + "cr"):
                parts.append("\n")
        text = "".join(parts).strip()
        if not text:
            continue
        style = p.find(f"{W}pPr/{W}pStyle")
        val = style.get(W + "val", "") if style is not None else ""
        m = re.fullmatch(r"(?i)heading\s*(\d)", val)
        level = int(m.group(1)) if m else 1 if val.lower() == "title" else 0
        paragraphs.append(f"{'#' * level} {text}" if level else text)
    return stem, None, paragraphs


def read_pdf(path: Path, stem: str):
    """PDF through pdftotext: (title, date, paragraphs)."""
    exe = shutil.which("pdftotext")
    if not exe:
        raise Skip("no pdftotext")
    try:
        proc = subprocess.run([exe, "-enc", "UTF-8", str(path), "-"],
                              capture_output=True, timeout=PDFTOTEXT_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Skip("pdftotext timeout")
    except OSError:
        raise Skip("pdftotext failed")
    if proc.returncode != 0:
        raise Skip("pdftotext failed")
    paragraphs = _paragraphs(proc.stdout.decode("utf-8", "replace").replace("\f", "\n\n"))
    if sum(len(p.split()) for p in paragraphs) < PDF_MIN_WORDS:
        raise Skip("no text layer")
    return stem, None, paragraphs


def read_file(path: Path):
    kind = READERS.get(path.suffix.lower())
    if kind is None:
        raise Skip("unsupported type")
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise Skip("file too large")
        if kind == "docx":
            return read_docx(path, path.stem)
        if kind == "pdf":
            return read_pdf(path, path.stem)
        raw = path.read_bytes()
    except OSError:
        raise Skip("unreadable")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Skip("not UTF-8")
    return (read_text if kind == "text" else read_html)(text, path.stem)


def walk(paths: list[Path]):
    """The files to read as (path, source), and the skipped ones as (source, reason)."""
    files: list[tuple[Path, str]] = []
    skips: list[tuple[str, str]] = []

    def visit(folder: Path, root: Path):
        try:
            entries = sorted(os.scandir(folder), key=lambda e: e.name)
        except OSError:
            skips.append((folder.relative_to(root).as_posix(), "unreadable"))
            return
        for entry in entries:
            if entry.name.startswith((".", "~$")):
                continue
            path = Path(entry.path)
            rel = path.relative_to(root).as_posix()
            if entry.is_symlink():
                skips.append((rel, "symlink"))
            elif entry.is_dir(follow_symlinks=False):
                visit(path, root)
            elif entry.is_file(follow_symlinks=False):
                files.append((path, rel))

    for p in paths:
        if p.is_symlink():
            skips.append((str(p), "symlink"))
        elif p.is_dir():
            visit(p, p)
        elif p.is_file():
            files.append((p, p.name))
        else:
            skips.append((str(p), "not found"))
    return files, skips


class _HttpOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to another http(s) URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme.lower() not in ("http", "https"):
            raise urllib.error.HTTPError(newurl, code, "redirect to a non-http(s) URL refused",
                                         headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_HttpOnlyRedirect)


def fetch(url: str):
    """(body, content type, charset) of one page, at most MAX_PAGE_BYTES."""
    req = urllib.request.Request(url, headers={"User-Agent": "revoice-extract-documents"})
    try:
        with _OPENER.open(req, timeout=URL_TIMEOUT) as resp:
            length = resp.headers.get("Content-Length")
            if length and length.strip().isdigit() and int(length) > MAX_PAGE_BYTES:
                raise Skip("page too large")
            data = resp.read(MAX_PAGE_BYTES + 1)
            if len(data) > MAX_PAGE_BYTES:
                raise Skip("page too large")
            return data, resp.headers.get_content_type(), resp.headers.get_content_charset()
    except Skip:
        raise
    except Exception:  # URLError, HTTPError, timeouts, broken connections, bad URLs
        raise Skip("fetch failed")


def read_url(url: str):
    data, ctype, charset = fetch(url)
    try:
        text = data.decode(charset or "utf-8", "replace")
    except LookupError:
        text = data.decode("utf-8", "replace")
    parts = urllib.parse.urlsplit(url)
    stem = (parts.netloc + parts.path).rstrip("/")
    return (read_text if ctype == "text/plain" else read_html)(text, stem)


def read_urls(lines: list[str], skipped):
    """Yield (title, date, paragraphs, source) for each URL that is read."""
    fetched = 0
    for i, url in enumerate(lines):
        if i >= MAX_URLS:
            skipped.append((url, "over the URL limit"))
            continue
        if urllib.parse.urlsplit(url).scheme.lower() not in ("http", "https"):
            skipped.append((url, "not an http(s) URL"))
            continue
        if fetched:
            time.sleep(URL_PAUSE)
        fetched += 1
        try:
            title, date, paragraphs = read_url(url)
        except Skip as e:
            skipped.append((url, str(e)))
            continue
        yield title, date, paragraphs, url


def _slug(s: str, n: int = 50) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:n].rstrip("-") or "untitled"


def _key(text: str) -> str:
    """sha1 of the lowercased words; the last part of a sample's file name."""
    return hashlib.sha1(" ".join(text.lower().split()).encode()).hexdigest()


def _words(paragraphs: list[str]) -> int:
    """Words of prose: a heading's "#" marker is not a word."""
    return sum(len(p.lstrip("#").split()) for p in paragraphs)


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path, help="files or folders to read")
    ap.add_argument("--urls", type=Path, help="a file with one http(s) URL per line")
    ap.add_argument("-o", "--out", type=Path, default=Path("samples"))
    args = ap.parse_args()
    if not args.paths and not args.urls:
        ap.error("give at least one file or folder, or --urls FILE")
    if args.urls and not args.urls.is_file():
        ap.error(f"--urls: no such file: {args.urls}")
    if hasattr(sys.stdout, "reconfigure"):  # not on a captured stream
        sys.stdout.reconfigure(errors="replace")  # non-ASCII titles on a Windows console

    files, skipped = walk(args.paths)
    docs = []
    for path, source in files:
        try:
            title, date, paragraphs = read_file(path)
        except Skip as e:
            skipped.append((source, str(e)))
            continue
        docs.append((title, date, paragraphs, source))
    if args.urls:
        lines = [l.strip() for l in args.urls.read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l and not l.startswith("#")]
        docs.extend(read_urls(lines, skipped))

    args.out.mkdir(parents=True, exist_ok=True)
    rows, names = [], set()
    for title, date, paragraphs, source in docs:
        if not paragraphs:
            skipped.append((source, "no text"))
            continue
        text = "\n\n".join(paragraphs)
        name = f"{_slug(title)}_01_{_key(text)[:6]}.md"
        if name in names:
            skipped.append((source, "duplicate"))
            continue
        names.add(name)
        (args.out / name).write_text(f"# {title}\n\n{text}\n", encoding="utf-8")
        rows.append({"file": name, "date": date or "undated", "words": _words(paragraphs),
                     "subject": title, "source": source})

    rows.sort(key=lambda r: (-r["words"], r["file"]))
    with open(args.out / "index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "date", "words", "subject", "source"])
        w.writeheader()
        w.writerows(rows)

    for source, reason in skipped:
        print(f"skip {source}: {reason}")
    print(f"read {_plural(len(rows), 'document')}, wrote {_plural(len(rows), 'sample')} to {args.out}/")
    if skipped:
        print(f"skipped {len(skipped):,}:")
        for reason, n in collections.Counter(r for _, r in skipped).most_common():
            print(f"  {reason:<20}: {n:,}")
    if any(r == "no pdftotext" for _, r in skipped):
        print(NO_PDFTOTEXT)


if __name__ == "__main__":
    main()
