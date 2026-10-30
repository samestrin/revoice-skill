#!/usr/bin/env python3
"""Mark each extracted sample KEEP or DROP with plain rules, on this machine.

Reads samples/index.csv (from extract-samples.py), judges every sample file
with the rules below, and adds the columns verdict, score and reason to
index.csv. Existing columns and rows are kept. build-profile.py then uses only
the KEEP rows, best score first. Nothing is sent anywhere: the script uses the
standard library only and makes no network call.

A sample is DROPPED when it is: broken extraction (mostly signature or contact
lines, many replacement or non-letter characters, or cut off mid-sentence and
very short); mostly quoted, forwarded or boilerplate lines; mostly list, table,
code or log lines; a near-duplicate form letter within the set; not in the
author's usual language; or signed with a clearly different name than --author.
score is 1-5 from prose length and paragraph structure. reason is one fixed
label (see REASONS), never a quote from the email.

index.csv is replaced only after every sample was judged, so a failed run
leaves it as it was. A rerun reviews every sample again.
"""
from __future__ import annotations
import argparse
import csv
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

COLUMNS = ["verdict", "score", "reason"]

KEEP_REASON = "own writing"
REASONS = [KEEP_REASON, "broken extraction", "quoted or forwarded text",
           "list, table, code or log", "form letter", "not in the author's language",
           "written in another name"]

# A rule fires when at least this share of the non-blank lines match.
MOSTLY = 0.5
SIGNATURE_SHARE = 0.6
# Broken extraction: replacement characters, and letters among non-space characters.
MAX_REPLACEMENT_SHARE = 0.02
MIN_LETTER_SHARE = 0.5
# "Very short" for the cut-off check.
CUT_OFF_WORDS = 12
# Near-duplicates: word n-grams, and the bounds on the work done per sample.
NGRAM = 5
MIN_SHINGLES = 8  # shorter samples (a one-line reply) can repeat honestly
MAX_SHINGLES = 500  # shingles looked at per sample
BUCKET = 50  # samples remembered per shingle
DUPLICATE_OVERLAP = 0.7
# Language: share of common function words of the author's language (see LANGUAGE_WORDS).
MIN_LANGUAGE_WORDS = 20
LANGUAGE_SHARE = 0.12  # below this a sample does not look like the author's language
LANGUAGE_AUTHOR_SHARE = 0.2  # the set's median must reach this for the check to run

FUNCTION_WORDS = frozenset(
    "the a an and or but of to in on at for with from by as is are was were be been it this "
    "that these those i you he she we they my your our their me us them not no if so do does "
    "did have has had will would can could should there what which who when about".split())
GERMAN_FUNCTION_WORDS = frozenset(
    "der die das den dem des ein eine einen einem einer eines und oder aber von zu zum zur in "
    "im an am auf aus bei mit nach für über um ist sind war waren sein bin bist hat haben habe "
    "hatte wird werden wurde es ich du er sie wir ihr mich mir dich dir uns euch ihn ihm ihnen "
    "nicht kein keine wenn dass ob als wie was wer wo auch noch nur schon sehr doch da hier "
    "mein dein unser kann können muss müssen soll sollte will würde weil".split())
# The author's language is the one with the highest median share; English wins a tie.
# FUNCTION_WORDS stays English: other_name uses it to tell a name from an ordinary word.
LANGUAGE_WORDS = {"english": FUNCTION_WORDS, "german": GERMAN_FUNCTION_WORDS}
DANGLING = frozenset(
    "the a an and or but of to in on at for with from by as is are was were be that this "
    "which who if so than then because my your our their his her its".split())
COMMON_NON_NAMES = frozenset("will see give talk call let get send thanks soon later again".split())
CLOSINGS = re.compile(
    r"^(thanks|thank you|best|best regards|kind regards|regards|warm regards|cheers|sincerely|"
    r"yours|yours sincerely|yours truly|many thanks|all the best|take care|talk soon)\s*[,!.]?$",
    re.I)
NAME_LINE = re.compile(r"^[^\W\d_][\w.'-]*(\s+[^\W\d_][\w.'-]*){0,2}$")

QUOTE = re.compile(r"^\s*>")
FORWARD_START = re.compile(
    r"^\s*(-{2,}\s*(original message|forwarded message)|begin forwarded message|"
    r"_{5,}$|on .{5,120} wrote:\s*$)", re.I)
HEADER = re.compile(r"^\s*(from|sent|to|cc|subject|date):\s", re.I)
BOILERPLATE = re.compile(
    r"confidential|intended (only )?for the|unsubscribe|privacy (notice|policy)|"
    r"disclaimer|this (e-?mail|message) and any attachments|if you are not the intended", re.I)
BULLET = re.compile(r"^\s*([-*\u2022\u25cf]|\d{1,3}[.)])\s+\S")
TABLE = re.compile(r"\|.*\||\t\S.*\t|\S {3,}\S.* {3,}\S")
CODE = re.compile(r"^(\t| {4})\s*\S|^\s*(def |class |import |from \S+ import |#include|\$ |```)|[{};]\s*$")
LOG = re.compile(
    r"^\s*\[?(\d{4}-\d\d-\d\d[ T]\d\d:\d\d|\d\d:\d\d:\d\d|"
    r"(TRACE|DEBUG|INFO|WARN(ING)?|ERROR|FATAL)\b)")
CONTACT_LABEL = re.compile(
    r"^\s*(--\s*$|(tel|phone|mobile|cell|fax|address|email|e-mail|web|www)\b[\s.:]|sent from my|"
    r"get outlook|sent via)", re.I)
# An address, URL or phone number; a line is contact-like when little else is on it.
CONTACT_ITEM = re.compile(
    r"\+\d[\d\s().-]{7,}\d|\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}|\S+@\S+\.\S+|https?://\S+|www\.\S+")
CONTACT_EXTRA_WORDS = 3
WORD = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)?")


def body(path: Path) -> str:
    return path.read_text(encoding="utf-8").partition("\n")[2].strip()


def lines_of(text: str) -> list[str]:
    return [l for l in text.splitlines() if l.strip()]


def is_contact(line: str) -> bool:
    if CONTACT_LABEL.search(line):
        return True
    rest = CONTACT_ITEM.sub(" ", line)
    return rest != line and len(words(rest)) <= CONTACT_EXTRA_WORDS


def share(lines: list[str], hit) -> float:
    return sum(1 for l in lines if hit(l)) / len(lines) if lines else 0.0


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text)]


def is_broken(text: str) -> bool:
    lines = lines_of(text)
    if not lines:
        return True
    if share(lines, is_contact) >= SIGNATURE_SHARE:
        return True
    chars = [c for c in text if not c.isspace()]
    return chars.count("\ufffd") / len(chars) > MAX_REPLACEMENT_SHARE


def is_garbled(text: str) -> bool:
    """Mostly non-letters, or cut off mid-sentence and very short.

    Checked after the list and log rules, which also have few letters.
    """
    chars = [c for c in text if not c.isspace()]
    if sum(c.isalpha() for c in chars) / len(chars) < MIN_LETTER_SHARE:
        return True
    ws = text.split()
    last = ws[-1].lower().strip("\"'")
    return len(ws) < CUT_OFF_WORDS and (
        last.rstrip(",;:-\u2013\u2014(") != last or last in DANGLING)


def is_quoted(text: str) -> bool:
    lines = lines_of(text)
    quoted = 0
    forwarded = False
    for l in lines:
        if FORWARD_START.search(l):
            forwarded = True
        if forwarded or QUOTE.search(l) or BOILERPLATE.search(l) or HEADER.search(l):
            quoted += 1
    return bool(lines) and quoted / len(lines) >= MOSTLY


def is_structured(text: str) -> bool:
    lines = lines_of(text)
    n = sum(1 for l in lines if BULLET.search(l) or TABLE.search(l) or CODE.search(l) or LOG.search(l))
    return n >= 2 and n / len(lines) >= MOSTLY


def shingles(text: str) -> set[int]:
    ws = words(text)
    grams = (hash(tuple(ws[i:i + NGRAM])) for i in range(len(ws) - NGRAM + 1))
    out: set[int] = set()
    for g in grams:
        out.add(g)
        if len(out) >= MAX_SHINGLES:
            break
    return out


def find_duplicates(texts: list[str], stats: dict | None = None) -> set[int]:
    """Indexes of samples that share most word 5-grams with another sample.

    Work is bounded: at most MAX_SHINGLES shingles per sample, and each
    shingle remembers at most BUCKET samples, so a sample is compared with at
    most BUCKET other samples per shingle however large the set is.
    """
    index: dict[int, list[int]] = {}
    shingles_of: dict[int, set[int]] = {}
    dups: set[int] = set()
    stats = stats if stats is not None else {}
    stats.update(max_candidates=0, max_shingles=0)
    for i, text in enumerate(texts):
        sh = shingles(text)
        stats["max_shingles"] = max(stats["max_shingles"], len(sh))
        if len(sh) < MIN_SHINGLES:
            continue
        seen: Counter = Counter()
        for g in sh:
            for j in index.get(g, ()):
                seen[j] += 1
        stats["max_candidates"] = max(stats["max_candidates"], len(seen))
        for j, n in seen.items():
            if n / min(len(sh), len(shingles_of[j])) >= DUPLICATE_OVERLAP:
                dups.update((i, j))
        for g in sh:
            bucket = index.setdefault(g, [])
            if len(bucket) < BUCKET:
                bucket.append(i)
        shingles_of[i] = sh
    return dups


def language_share(text: str, language: str) -> float:
    ws, common = words(text), LANGUAGE_WORDS[language]
    return sum(w in common for w in ws) / len(ws) if ws else 0.0


def author_language(texts: list[str]) -> str | None:
    """The language with the highest median share over the samples long enough to judge.

    None when no language reaches LANGUAGE_AUTHOR_SHARE, and then no sample is
    dropped for its language.
    """
    long = [t for t in texts if len(words(t)) >= MIN_LANGUAGE_WORDS]
    if not long:
        return None
    medians = {}
    for language in LANGUAGE_WORDS:
        shares = sorted(language_share(t, language) for t in long)
        medians[language] = shares[len(shares) // 2]
    best = max(medians, key=medians.get)  # the first, English, on a tie
    return best if medians[best] >= LANGUAGE_AUTHOR_SHARE else None


def signoff_name(text: str) -> str:
    """The name on the line after a closing such as "Thanks," ("" if none)."""
    lines = [l.strip() for l in lines_of(text)]
    for k in range(len(lines) - 2, -1, -1):
        if CLOSINGS.match(lines[k]):
            nxt = lines[k + 1]
            return nxt if NAME_LINE.match(nxt) and len(nxt) <= 40 else ""
    return ""


def other_name(text: str, author: str) -> bool:
    """True when the sign-off name clearly is not the author's."""
    name, mine = signoff_name(text), author.lower().replace(".", " ").split()
    if not name or not mine:
        return False
    # A name is capitalised and has no ordinary word in it ("Will follow up" is not one).
    toks = name.replace(".", " ").split()
    if any(not t[0].isupper() or t.lower() in FUNCTION_WORDS or t.lower() in COMMON_NON_NAMES
           for t in toks if t.lower() not in mine and not any(a.startswith(t.lower()) for a in mine)):
        return False
    for tok in name.lower().replace(".", " ").split():
        if any(a.startswith(tok) or tok.startswith(a) for a in mine):
            return False
    return True


def score(text: str) -> int:
    n = len(words(text))
    paras = sum(1 for p in re.split(r"\n\s*\n", text) if len(words(p)) >= 8)
    s = 1 if n < 15 else 2 if n < 50 else 3 if n < 100 else 4 if n < 200 else 5
    if s > 2 and paras <= 1:
        s -= 1
    elif s < 5 and paras >= 3 and n >= 60:
        s += 1
    return max(1, min(5, s))


def review(texts: list[str], author: str = "") -> list[dict]:
    """Return one {verdict, score, reason} dict per text, in order."""
    dups = find_duplicates(texts)
    language = author_language(texts)
    out = []
    for i, t in enumerate(texts):
        if is_broken(t):
            reason = "broken extraction"
        elif is_quoted(t):
            reason = "quoted or forwarded text"
        elif is_structured(t):
            reason = "list, table, code or log"
        elif is_garbled(t):
            reason = "broken extraction"
        elif i in dups:
            reason = "form letter"
        elif (language and len(words(t)) >= MIN_LANGUAGE_WORDS
              and language_share(t, language) < LANGUAGE_SHARE):
            reason = "not in the author's language"
        elif other_name(t, author):
            reason = "written in another name"
        else:
            reason = KEEP_REASON
        out.append({"verdict": "KEEP" if reason == KEEP_REASON else "DROP",
                    "score": score(t), "reason": reason})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", type=Path, default=Path("samples"))
    ap.add_argument("--author", default="",
                    help="the author's name; a sign-off with a clearly different name is dropped")
    args = ap.parse_args()

    index = args.samples / "index.csv"
    with open(index, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if not rows:
        sys.exit(f"error: no samples in {index}")

    verdicts = review([body(args.samples / r["file"]) for r in rows], args.author)

    fields += [c for c in COLUMNS if c not in fields]
    fd, tmp = tempfile.mkstemp(dir=args.samples, prefix="index.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows({**r, **v} for r, v in zip(rows, verdicts))
        os.replace(tmp, index)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    keep = sum(v["verdict"] == "KEEP" for v in verdicts)
    print(f"reviewed {len(rows)} samples: {keep} KEEP, {len(rows) - keep} DROP")
    drops = Counter(v["reason"] for v in verdicts if v["verdict"] == "DROP")
    for reason, n in drops.most_common():
        print(f"  dropped {n}: {reason}")


if __name__ == "__main__":
    main()
