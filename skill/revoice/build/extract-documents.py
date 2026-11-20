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

Anything else is skipped and counted. Then:

  - boilerplate is dropped: markdown code (fenced or indented), pipe tables,
    image-only and link-only lines, page numbers, contents lines with dotted
    leaders, short legal and site-chrome paragraphs ("\u00a9", "all rights
    reserved", "privacy policy", "cookie", "subscribe to", ...), and any line
    of at most 80 characters among the first or last 6 lines of 3 or more
    documents (a running header, footer or tagline), which is removed
    everywhere. A document that is mostly such lines is dropped whole
  - with --before, a document whose front matter date is on or after it is
    dropped; undated documents are kept and counted
  - each document is split into passages of about 350 words (150 to 500,
    --min-words sets the 150) without cutting a paragraph; a paragraph over
    500 words is split at sentence ends. A short last passage joins the one
    before it when that stays within 500 words, or is dropped as too short. A
    document under --min-words words is kept whole from 60 words
  - a passage that shares half its word 5-grams with a longer one, in any
    document, or has half of them among all the longer passages kept (one
    that straddles two others), is a duplicate
  - sources that are one document (a passage of one was a duplicate of the
    other's, or half of one's 5-grams are in the other) are named by one
    source in index.csv: the one with the longest passage. The report then
    says how many of the documents read are distinct
  - at most --max-samples (default 148) are kept, round-robin across
    documents: each document's longest passage first, then the second, ...

Each passage is written as ``# <title>`` followed by its text, and index.csv
lists every sample with the columns file, date, words, subject, source. The
same inputs in any order give the same output.
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

# A default build of N samples costs 1 + N + min(N, 100) credits, as for
# email (extract-samples.py): 148 makes 250, the free credits of a new key.
MAX_SAMPLES = 148
MIN_WORDS = 150
TARGET_WORDS = 350
MAX_WORDS = 500
SHORT_DOC_WORDS = 60  # a document under MIN_WORDS is kept whole from here
REPEAT_MIN_DOCS = 3
REPEAT_MAX_CHARS = 80
EDGE_LINES = 6
CHROME_MAX_WORDS = 30  # a longer paragraph is prose that mentions a cookie
MOSTLY_BOILERPLATE = 0.5
DUPLICATE_SHARE = 0.5

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^#{1,6}\s")
INDENTED = re.compile(r"^(?: {4}|\t)")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
LINK = r"(?:!?\[[^\]]*\]\([^)]*\)|<?https?://\S+?>?)"
LINK_ONLY = re.compile(rf"^\s*(?:[-*+\u2022]\s+)?{LINK}(?:\s*[|\u2022\u00b7,]?\s*{LINK})*\s*$")
PAGE_NUMBER = re.compile(r"(?i)^[\s\-\u2013\u2014]*(?:page\s+)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?[\s\-\u2013\u2014]*$")
CONTENTS = re.compile(r"(?:\.\s?){4,}\s*\d{1,4}\s*$")
CHROME = re.compile(r"(?i)\u00a9|\ball rights reserved\b|\bterms (?:of|and) (?:use|service)\b|"
                    r"\bprivacy policy\b|\bcookies?\b|\bsubscribe to\b|\bshare this\b|"
                    r"\bread more\b|\bposted by\b.*\bon\b")
LEGAL = re.compile(r"(?i)\u00a9|\ball rights reserved\b")  # dropped as a line, whatever the length
SENTENCE_END = re.compile(r"[.!?][\"'\u201d\u2019)\]]*$")

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
        elif self.skip:
            return
        elif tag == "title":
            self.in_title = True
        elif tag in ("br", "hr") and self.level:
            self.buf.append(" ")  # a line break inside a heading
        elif tag in self.BLOCK:
            self.flush()
            # Any other block start also ends a heading left unclosed.
            self.level = int(tag[1]) if re.fullmatch(r"h[1-6]", tag) else 0

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif self.skip:
            return
        elif tag == "title":
            self.in_title = False
        elif tag in self.BLOCK and not (tag in ("br", "hr") and self.level):
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


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _norm(line: str) -> str:
    return " ".join(line.lower().split())


def strip_markup(paragraphs: list[str], markdown: bool, counts: collections.Counter):
    """Drop code, tables and chrome; (blocks of lines kept, words of chrome dropped).

    Code and tables are counted in ``counts`` but not as chrome: a post with a
    long code sample is not "mostly boilerplate". A heading line becomes a
    block of its own."""
    blocks: list[list[str]] = []
    chrome = 0
    fence = None
    for p in paragraphs:
        lines = p.split("\n")
        if fence is None and markdown and all(INDENTED.match(l) for l in lines):
            counts["code"] += len(lines)
            continue
        if (fence is None and len(p.split()) <= CHROME_MAX_WORDS and CHROME.search(p)
                and not HEADING.match(p) and not any(FENCE.match(l) for l in lines)):
            counts["legal or site chrome"] += 1
            chrome += len(p.split())
            continue
        table = any(TABLE_RULE.match(l) for l in lines)
        block: list[str] = []
        for line in lines:
            m = FENCE.match(line)
            if fence is not None:
                counts["code"] += 1
                if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                        and not line.strip().strip(fence[0]):
                    fence = None
                continue
            if m:
                fence = m.group(1)
                counts["code"] += 1
                continue
            reason = ("table" if TABLE_ROW.match(line) or TABLE_RULE.match(line)
                      or (table and "|" in line)
                      else "link or image" if LINK_ONLY.match(line)
                      else "page number" if PAGE_NUMBER.match(line)
                      else "contents line" if CONTENTS.search(line)
                      else "legal or site chrome" if LEGAL.search(line) else None)
            if reason is None:
                if HEADING.match(line):
                    if block:
                        blocks.append(block)
                    blocks.append([line])
                    block = []
                else:
                    block.append(line)
                continue
            counts[reason] += 1
            if reason != "table":
                chrome += len(line.split())
        if block:
            blocks.append(block)
    return blocks, chrome


def edge_lines(blocks: list[list[str]]) -> dict[str, str]:
    """The short lines among a document's first and last EDGE_LINES lines, by
    their lowercased words. Headings are not counted: "## Introduction" in
    three posts is a section, not a tagline."""
    lines = [l for b in blocks for l in b if l.strip() and not HEADING.match(l)]
    edges = lines[:EDGE_LINES] + lines[-EDGE_LINES:]
    return {_norm(l): l.strip() for l in edges if len(l.strip()) <= REPEAT_MAX_CHARS}


def drop_lines(blocks: list[list[str]], repeated: set[str], counts: collections.Counter):
    """Remove the repeated lines; (paragraphs left, words removed)."""
    out, removed = [], 0
    for block in blocks:
        kept = []
        for line in block:
            if _norm(line) in repeated:
                counts["repeated line"] += 1
                removed += len(line.split())
            else:
                kept.append(line)
        if any(l.strip() for l in kept):
            out.append("\n".join(kept))
    return out, removed


def _prose_words(p: str) -> int:
    return 0 if HEADING.match(p) else len(p.split())


def split_paragraph(p: str) -> list[str]:
    """A paragraph over MAX_WORDS, cut at sentence ends into pieces of about
    TARGET_WORDS; a sentence over MAX_WORDS is cut every MAX_WORDS words."""
    toks = p.split()
    if len(toks) <= MAX_WORDS:
        return [p]
    sentences, cur = [], []
    for t in toks:
        cur.append(t)
        if SENTENCE_END.search(t):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)
    pieces, cur = [], []
    for s in sentences:
        while len(s) > MAX_WORDS:
            if cur:
                pieces.append(cur)
                cur = []
            pieces.append(s[:MAX_WORDS])
            s = s[MAX_WORDS:]
        if cur and (len(cur) >= TARGET_WORDS or len(cur) + len(s) > MAX_WORDS):
            pieces.append(cur)
            cur = []
        cur = cur + s
    if cur:
        pieces.append(cur)
    return [" ".join(x) for x in pieces]


def passages(paragraphs: list[str], min_words: int):
    """Split one document; ([(text, words)], number of passages too short).

    Paragraphs are joined until a passage has TARGET_WORDS words, never past
    MAX_WORDS. A heading stays only as the first line of a passage."""
    units, heading = [], None  # (heading or None, text, words)
    for p in paragraphs:
        if HEADING.match(p):
            heading = p
            continue
        for piece in split_paragraph(p):
            units.append((heading, piece, len(piece.split())))
            heading = None
    groups, cur, n = [], [], 0
    for u in units:
        if cur and (n >= TARGET_WORDS or n + u[2] > MAX_WORDS):
            groups.append(cur)
            cur, n = [], 0
        cur.append(u)
        n += u[2]
    if cur:
        groups.append(cur)

    def words(g):
        return sum(u[2] for u in g)

    short = 0
    if len(groups) == 1:  # the whole document
        keep = groups if words(groups[0]) >= min(SHORT_DOC_WORDS, min_words) else []
        short = len(groups) - len(keep)
    else:
        keep = []
        for g in groups:
            if words(g) >= min_words:
                keep.append(g)
            elif keep and words(keep[-1]) + words(g) <= MAX_WORDS:
                keep[-1] = keep[-1] + g
            else:
                short += 1
    out = []
    for g in keep:
        parts = [g[0][0]] if g[0][0] else []
        parts += [u[1] for u in g]
        out.append(("\n\n".join(parts), words(g)))
    return out, short


def _grams(text: str) -> set:
    toks = text.lower().split()
    if len(toks) < 5:
        return {tuple(toks)}
    return {tuple(toks[i:i + 5]) for i in range(len(toks) - 4)}


def _order(c: dict):
    """Longest first; ties by sha1, then source, title, date and place, so the
    order of the inputs never decides."""
    return (-c["words"], c["key"], c["source"], c["title"], c["date"] or "", c["n"])


def _held(grams: set, index: dict, kept: list[dict], c: dict) -> str | None:
    """The other source whose kept passages hold most of these 5-grams."""
    held = collections.Counter(s for g in grams
                               for s in {kept[k]["source"] for k in index.get(g, ())})
    held.pop(c["source"], None)
    return min(held, key=lambda s: (-held[s], s)) if held else None


def dedupe(items: list[dict]) -> tuple[list[dict], int, list[tuple[str, str]]]:
    """Drop each passage that shares DUPLICATE_SHARE of its 5-grams with one
    before it in _order, or has DUPLICATE_SHARE of them among the passages
    kept before it. Then, in _order, drop each kept passage with
    DUPLICATE_SHARE of its 5-grams among all the other kept passages (one that
    straddles two shorter ones). Also returns the pairs (source, other source)
    for each dropped passage whose 5-grams were mostly in another source."""
    items = sorted(items, key=_order)
    index: dict[tuple, list[int]] = collections.defaultdict(list)
    kept_grams: list[set] = []
    kept, links = [], []
    for c in items:
        grams = _grams(c["text"])
        hits = collections.Counter(k for g in grams for k in index.get(g, ()))
        if (any(h / max(1, min(len(grams), len(kept_grams[k]))) >= DUPLICATE_SHARE
                for k, h in hits.items())
                or sum(g in index for g in grams) / max(1, len(grams)) >= DUPLICATE_SHARE):
            links.append((c["source"], _held(grams, index, kept, c)))
            continue
        for g in grams:
            index[g].append(len(kept_grams))
        kept_grams.append(grams)
        kept.append(c)

    copies = collections.Counter(g for grams in kept_grams for g in grams)
    for k, (c, grams) in enumerate(zip(kept, kept_grams)):
        if sum(copies[g] > 1 for g in grams) / max(1, len(grams)) >= DUPLICATE_SHARE:
            copies.subtract(grams)
            for g in grams:
                index[g].remove(k)
            links.append((c["source"], _held(grams, index, kept, c)))
            kept_grams[k] = None
    out = [c for c, grams in zip(kept, kept_grams) if grams is not None]
    return out, len(items) - len(out), [(a, b) for a, b in links if b]


def group(items: list[dict], links: list[tuple[str, str]]) -> dict[str, str]:
    """Which sources are one document: {source: the source that names it}.

    Two sources are one document when they are linked (a passage of one was a
    duplicate of the other's) or DUPLICATE_SHARE of one's 5-grams are in the
    other. A document is named by the source of its first passage in _order."""
    grams: dict[str, set] = collections.defaultdict(set)
    for c in items:
        grams[c["source"]] |= _grams(c["text"])
    holders: dict[tuple, set] = collections.defaultdict(set)
    for source, gs in grams.items():
        for g in gs:
            holders[g].add(source)
    pairs = list(links)
    for source, gs in grams.items():
        shared = collections.Counter(o for g in gs for o in holders[g] if o != source)
        pairs += [(source, o) for o, n in shared.items() if n >= DUPLICATE_SHARE * len(gs)]

    parent = {s: s for s in grams}

    def root(s):
        while parent[s] != s:
            s = parent[s]
        return s

    for a, b in pairs:
        parent[root(a)] = root(b)
    name: dict[str, str] = {}
    for c in sorted(items, key=_order):
        name.setdefault(root(c["source"]), c["source"])
    return {s: name[root(s)] for s in grams}


def cap(items: list[dict], max_samples: int) -> list[dict]:
    """At most max_samples, round-robin across documents, longest first."""
    by_doc: dict[tuple, list[dict]] = collections.defaultdict(list)
    for c in items:
        by_doc[c["source"], c["title"], c["date"] or ""].append(c)
    lists = [sorted(v, key=_order) for v in by_doc.values()]
    picked = []
    for r in range(max((len(l) for l in lists), default=0)):
        picked += sorted((l[r] for l in lists if r < len(l)), key=_order)
    return picked[:max_samples] if max_samples else picked


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path, help="files or folders to read")
    ap.add_argument("--urls", type=Path, help="a file with one http(s) URL per line")
    ap.add_argument("--min-words", type=int, default=MIN_WORDS,
                    help="the shortest passage kept (a shorter document is kept whole from 60 words)")
    ap.add_argument("--max-samples", type=int, default=MAX_SAMPLES,
                    help="keep at most this many passages, round-robin across documents (0 = no cap)")
    ap.add_argument("--before", metavar="YYYY-MM-DD",
                    help="drop documents whose front matter date is on or after this day")
    ap.add_argument("-o", "--out", type=Path, default=Path("samples"))
    args = ap.parse_args()
    if not args.paths and not args.urls:
        ap.error("give at least one file or folder, or --urls FILE")
    if args.urls and not args.urls.is_file():
        ap.error(f"--urls: no such file: {args.urls}")
    for flag, value in (("--min-words", args.min_words), ("--max-samples", args.max_samples)):
        if value < 0:
            ap.error(f"{flag}: must be 0 or more")
    before = None
    if args.before:
        try:
            before = datetime.date.fromisoformat(args.before).isoformat()
        except ValueError:
            ap.error(f"--before: not a YYYY-MM-DD date: {args.before}")
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
        docs.append((title, date, paragraphs, source, path.suffix.lower() == ".md"))
    if args.urls:
        lines = [l.strip() for l in args.urls.read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l and not l.startswith("#")]
        docs.extend((*d, False) for d in read_urls(lines, skipped))
    n_read = len(docs)
    if before:
        for d in docs:
            if d[1] and d[1] >= before:
                skipped.append((d[3], "on or after --before"))
        docs = [d for d in docs if not (d[1] and d[1] >= before)]

    # Boilerplate: per document first, then the lines that open or close 3+ documents.
    lines = collections.Counter()
    stripped = []
    for title, date, paragraphs, source, markdown in docs:
        blocks, chrome = strip_markup(paragraphs, markdown, lines)
        stripped.append((title, date, blocks, chrome, source))
    seen, shown = collections.Counter(), {}
    for _, _, blocks, _, _ in stripped:
        for norm, line in edge_lines(blocks).items():
            seen[norm] += 1
            shown[norm] = min(shown.get(norm, line), line)  # not the first seen: order-free
    repeated = {l for l, n in seen.items() if n >= REPEAT_MIN_DOCS}

    stats = collections.Counter()
    candidates, undated = [], 0
    for title, date, blocks, chrome, source in stripped:
        paragraphs, removed = drop_lines(blocks, repeated, lines)
        chrome += removed
        words = sum(len(p.split()) for p in paragraphs)
        if chrome and chrome > MOSTLY_BOILERPLATE * (chrome + words):
            skipped.append((source, "mostly boilerplate"))
            continue
        if not any(_prose_words(p) for p in paragraphs):
            skipped.append((source, "no text"))
            continue
        undated += date is None
        found, short = passages(paragraphs, args.min_words)
        stats["too short"] += short
        for i, (text, n) in enumerate(found, 1):
            candidates.append({"title": title, "date": date, "source": source, "n": i,
                               "text": text, "words": n, "key": _key(text)})

    kept, stats["duplicate"], links = dedupe(candidates)
    document = group(candidates, links)
    distinct = n_read - sum(s != d for s, d in document.items())
    picked = cap(kept, args.max_samples)
    stats["over the cap"] = len(kept) - len(picked)

    args.out.mkdir(parents=True, exist_ok=True)
    rows, names = [], set()
    for c in picked:
        name = f"{_slug(c['title'])}_{c['n']:02d}_{c['key'][:6]}.md"
        if name in names:  # same title, same place, same sha1 prefix
            stats["duplicate"] += 1
            continue
        names.add(name)
        (args.out / name).write_text(f"# {c['title']}\n\n{c['text']}\n", encoding="utf-8")
        rows.append({"file": name, "date": c["date"] or "undated", "words": c["words"],
                     "subject": c["title"], "source": document[c["source"]]})

    rows.sort(key=lambda r: (-r["words"], r["file"]))
    with open(args.out / "index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "date", "words", "subject", "source"])
        w.writeheader()
        w.writerows(rows)

    for source, reason in skipped:
        print(f"skip {source}: {reason}")
    also = f" ({distinct:,} distinct)" if distinct != n_read else ""
    print(f"read {_plural(n_read, 'document')}{also}, wrote {_plural(len(rows), 'sample')} to {args.out}/")
    if skipped:
        print(f"skipped {_plural(len(skipped), 'document')}:")
        for reason, n in collections.Counter(r for _, r in skipped).most_common():
            print(f"  {reason:<20}: {n:,}")
    stats = +stats
    if stats:
        print(f"dropped {_plural(sum(stats.values()), 'passage')}:")
        for reason, n in sorted(stats.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {reason:<20}: {n:,}")
    if lines:
        print("boilerplate removed (lines, or short paragraphs of chrome):")
        for reason, n in sorted(lines.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {reason:<20}: {n:,}")
    if repeated:
        print(f"  lines that open or close {REPEAT_MIN_DOCS}+ documents, removed everywhere:")
        for l in sorted(repeated, key=lambda l: (-seen[l], l)):
            print(f"    {seen[l]:>4}  {shown[l][:70]}")
    if before:
        print(f"kept {_plural(undated, 'undated document')} (--before reads the front matter date only)")
    if any(r == "no pdftotext" for _, r in skipped):
        print(NO_PDFTOTEXT)


if __name__ == "__main__":
    main()
