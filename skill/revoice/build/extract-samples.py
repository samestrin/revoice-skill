#!/usr/bin/env python3
"""Extract single-author writing samples from an mbox into one .md file each.

For each message sent FROM one of the given addresses:
  - skip forwards
  - take the text/plain body (HTML-only bodies are converted to text)
  - cut everything from the first quoted-reply marker down
  - drop ">" quote lines and signatures (the "-- " delimiter, "Sent from my
    ...", and trailing lines that recur at the end of many messages)
  - keep it if what is left has at least --min-words words
  - skip exact duplicates
  - keep at most --max-samples, the longest first (0 = no cap)

With --others the sender filter is inverted: it keeps messages NOT from the
given addresses. Use that to build a reference folder of other people's
writing from the same mailbox.

Each sample is written as ``# <subject>`` followed by the text. An index.csv
lists every sample so they can be reviewed and ranked.
"""
from __future__ import annotations
import argparse
import codecs
import collections
import csv
import hashlib
import sys
import html
import mailbox
import re
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

REPLY_MARKERS = re.compile(
    r"^(?:"
    r"On [^\n]{0,300}?(?:\n[^\n]{0,200}?)?wrote:[ \t]*$"
    r"|-{2,}\s*Original Message\s*-{2,}"
    r"|-{5,}\s*Forwarded message\s*-{5,}"
    r"|Begin forwarded message:"
    r"|_{20,}"
    r"|From:[^\n]*\n(?:[^\n]*\n){0,3}?(?:Sent|Date):"
    r")",
    re.M | re.I,
)
SIG_DELIM = re.compile(r"^--[ \t]*$", re.M)
SENT_FROM = re.compile(r"^\s*Sent from my \w[^\n]*$", re.M | re.I)
FWD_SUBJECT = re.compile(r"^\s*(fwd?|fw)\s*:", re.I)
RE_PREFIX = re.compile(r"^\s*((re|fwd?|fw|aw)\s*(\[\d+\])?\s*:\s*)+", re.I)


def _subject(msg) -> str:
    raw = msg.get("Subject")
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(str(raw)))).strip()
    except Exception:
        return str(raw).strip()


def _html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|tr|h\d)>", "\n\n", s)
    s = re.sub(r"(?is)<blockquote.*?</blockquote>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s)


def _body(msg) -> str | None:
    plain = html_part = None
    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        try:
            codecs.lookup(charset)
        except LookupError:  # mail in the wild declares charsets Python does not know
            charset = "utf-8"
        text = payload.decode(charset, "replace")
        if ctype == "text/plain" and plain is None:
            plain = text
        elif ctype == "text/html" and html_part is None:
            html_part = text
    if plain is not None:
        return plain
    if html_part is not None:
        return _html_to_text(html_part)
    return None


def _own_text(body: str) -> str:
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    m = REPLY_MARKERS.search(body)
    if m:
        body = body[: m.start()]
    m = SIG_DELIM.search(body)
    if m:
        body = body[: m.start()]
    body = SENT_FROM.sub("", body)
    lines = [l.rstrip() for l in body.split("\n") if not l.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def _trailing_lines(text: str, n: int = 6) -> list[str]:
    return [l.strip() for l in text.split("\n") if l.strip()][-n:]


def _strip_signature(text: str, sig_lines: set[str]) -> str:
    lines = text.split("\n")
    while lines and (not lines[-1].strip() or lines[-1].strip() in sig_lines):
        lines.pop()
    return "\n".join(lines).strip()


def _slug(s: str, n: int = 50) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:n].rstrip("-") or "untitled"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mbox", type=Path)
    ap.add_argument("--from", dest="senders", action="append", required=True,
                    help="the author's address (repeatable)")
    ap.add_argument("--others", action="store_true",
                    help="keep messages NOT from --from instead (builds a reference folder)")
    ap.add_argument("--min-words", type=int, default=150)
    ap.add_argument("--max-samples", type=int, default=200,
                    help="keep at most this many samples, the longest first (0 = no cap)")
    ap.add_argument("--sig-min-count", type=int, default=15,
                    help="a trailing line seen at the end of this many messages is a signature")
    ap.add_argument("-o", "--out", type=Path, default=Path("samples"))
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")  # non-ASCII subjects on a Windows console
    senders = {s.lower() for s in args.senders}

    stats = collections.Counter()
    candidates = []
    for msg in mailbox.mbox(str(args.mbox)):
        is_author = parseaddr(str(msg.get("From", "")))[1].lower() in senders
        if is_author == args.others:
            stats["author" if args.others else "other sender"] += 1
            continue
        subject = _subject(msg)
        if FWD_SUBJECT.match(subject):
            stats["forward"] += 1
            continue
        body = _body(msg)
        if body is None:
            stats["no text body"] += 1
            continue
        try:
            date = parsedate_to_datetime(str(msg.get("Date")))
        except (TypeError, ValueError):
            date = None
        candidates.append((date, subject, _own_text(body)))

    # Count each trailing line once per distinct subject, so a draft saved many
    # times cannot turn its own last paragraph into a "signature".
    trailing_subjects: dict[str, set[str]] = collections.defaultdict(set)
    for _, subject, text in candidates:
        for l in _trailing_lines(text):
            if len(l) <= 60:
                trailing_subjects[l].add(RE_PREFIX.sub("", subject).strip().lower())
    trailing = collections.Counter({l: len(s) for l, s in trailing_subjects.items()})
    sig_lines = {l for l, c in trailing.items() if c >= args.sig_min_count}

    kept = []
    for date, subject, text in candidates:
        text = _strip_signature(text, sig_lines)
        if len(text.split()) < args.min_words:
            stats["too short"] += 1
            continue
        kept.append((date, subject, text))

    # Drafts and resends: within one subject, keep the longest version and drop
    # any other version that shares most of its word 5-grams.
    kept.sort(key=lambda c: len(c[2].split()), reverse=True)
    by_title: dict[str, list[set]] = collections.defaultdict(list)
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for date, subject, text in kept:
        words = len(text.split())
        toks = text.lower().split()
        grams = {tuple(toks[i:i + 5]) for i in range(len(toks) - 4)}
        title_key = RE_PREFIX.sub("", subject).strip().lower()
        if any(len(grams & g) / max(1, min(len(grams), len(g))) >= 0.5 for g in by_title[title_key]):
            stats["duplicate"] += 1
            continue
        by_title[title_key].append(grams)
        if args.max_samples and stats["kept"] >= args.max_samples:
            stats["over the cap"] += 1
            continue
        key = hashlib.sha1(" ".join(toks).encode()).hexdigest()
        title = RE_PREFIX.sub("", subject).strip()
        if not title:
            title = " ".join(text.split()[:8]).rstrip(".,;:") + "..."
        day = f"{date:%Y-%m-%d}" if date else "undated"
        name = f"{day}_{_slug(title)}_{key[:6]}.md"
        (args.out / name).write_text(f"# {title}\n\n{text}\n", encoding="utf-8")
        rows.append({"file": name, "date": day, "words": words, "subject": title})
        stats["kept"] += 1

    rows.sort(key=lambda r: r["words"], reverse=True)
    with open(args.out / "index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "date", "words", "subject"])
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {stats['kept']:,} samples to {args.out}/")
    for k, v in stats.most_common():
        print(f"  {k:<15}: {v:,}")
    print(f"  signature lines stripped (seen {args.sig_min_count}+ times at the end):")
    for l in sorted(sig_lines, key=lambda l: -trailing[l]):
        print(f"    {trailing[l]:>4}  {l[:70]}")


if __name__ == "__main__":
    main()
