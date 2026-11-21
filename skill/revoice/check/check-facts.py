#!/usr/bin/env python3
"""Check that a rewrite keeps every fact in the original text.

Pulls numbers, dates, URLs and email addresses out of both texts and
compares them as sets. Prints one line per problem on stdout:

    MISSING <kind> <token>   a fact in the original but not the rewrite
    ADDED <kind> <token>     a fact in the rewrite but not the original

Exit status: 0 nothing found, 1 one or more problems, 2 bad arguments or
an unreadable file (one line on stderr).

Numbers keep an optional decimal part and trailing %; a leading $ and
thousands commas are dropped, so $1,200 equals 1200. Number words are
never extracted; a missing digit from one to twenty is accepted when its
number word ("one" to "twenty") appears in the rewrite, so "2" and "two"
match and the pronoun "one" never counts. Full dates (ISO 2026-11-20,
slash 11/20/2026 or 2026/11/20, and month-name "November 20, 2026" or
"3 May", with or without a year) become one canonical date token before
numbers are extracted, so equivalent forms compare equal. URLs lose
trailing ".,;)" punctuation. Standard library only; no network.
"""
from __future__ import annotations
import argparse
import re
import sys
from datetime import date
from pathlib import Path

NUMBER_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
    12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
    20: "twenty",
}

_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)
MONTHS: dict[str, int] = {}
for _i, _name in enumerate(_MONTH_NAMES, start=1):
    MONTHS[_name.lower()] = _i
    MONTHS[_name[:3].lower()] = _i
# Longest first so "September" is tried before "Sep".
_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
SLASH_YMD_RE = re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b")
SLASH_MDY_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
DAY_MONTH_RE = re.compile(
    rf"\b(\d{{1,2}})\s+({_MONTH_ALT})\.?(?![A-Za-z])(?:,?\s+(\d{{4}}))?\b",
    re.IGNORECASE,
)
MONTH_DAY_RE = re.compile(
    rf"\b({_MONTH_ALT})\.?(?![A-Za-z])\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"(?<![\w.$])\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?!\w)")


def _canonical_date(year: str | None, month: str, day: str) -> str | None:
    """One canonical token for a real date, or None when it is not one."""
    m, d = int(month), int(day)
    y = int(year) if year else 2000  # a leap year, so Feb 29 without a year works
    try:
        date(y, m, d)
    except ValueError:
        return None
    return f"{y:04d}-{m:02d}-{d:02d}" if year else f"{m:02d}-{d:02d}"


def extract(text: str) -> set[tuple[str, str]]:
    """The (kind, token) facts in a text. Each match is removed once taken,
    so digits inside a URL, email or date never count again as numbers."""
    facts: set[tuple[str, str]] = set()

    def take(pattern: re.Pattern, kind: str, token):
        nonlocal text

        def repl(m: re.Match) -> str:
            value = token(m)
            if value is None:
                return m.group(0)
            facts.add((kind, value))
            return " "

        text = pattern.sub(repl, text)

    take(EMAIL_RE, "email", lambda m: m.group(0))
    take(URL_RE, "url", lambda m: m.group(0).rstrip(".,;)"))
    take(ISO_DATE_RE, "date", lambda m: _canonical_date(m[1], m[2], m[3]))
    take(SLASH_YMD_RE, "date", lambda m: _canonical_date(m[1], m[2], m[3]))
    take(SLASH_MDY_RE, "date", lambda m: _canonical_date(m[3], m[1], m[2]))
    take(DAY_MONTH_RE, "date",
         lambda m: _canonical_date(m[3], str(MONTHS[m[2].lower()]), m[1]))
    take(MONTH_DAY_RE, "date",
         lambda m: _canonical_date(m[3], str(MONTHS[m[1].lower()]), m[2]))
    take(NUMBER_RE, "number", lambda m: m.group(0).lstrip("$").replace(",", ""))
    return facts


def compare(original: str, rewrite: str) -> list[str]:
    """The MISSING and ADDED lines for one original/rewrite pair."""
    orig, rew = extract(original), extract(rewrite)
    words = set(re.findall(r"[a-z]+", rewrite.lower()))
    lines = []
    for kind, token in sorted(orig - rew):
        if kind == "number" and token.isdigit():
            word = NUMBER_WORDS.get(int(token))
            if word and word in words:
                continue  # "2" kept as "two"
        lines.append(f"MISSING {kind} {token}")
    lines.extend(f"ADDED {kind} {token}" for kind, token in sorted(rew - orig))
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--original", required=True, type=Path, help="the input text")
    ap.add_argument("--rewrite", required=True, type=Path, help="the rewritten text")
    args = ap.parse_args()

    texts = []
    for path in (args.original, args.rewrite):
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as e:
            print(f"error: cannot read {path}: {e}", file=sys.stderr)
            return 2

    lines = compare(*texts)
    for line in lines:
        print(line)
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main())
