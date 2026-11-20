#!/usr/bin/env python3
"""Check a rewrite against a voice file's Do not list and once-per caps.

Reads the voice file's "## Do not" section (up to the next "## " heading);
every double-quoted phrase in it (straight or curly quotes) is banned.
Anywhere in the voice, a bullet marked "once per email at most" or "once per
piece at most" caps its first quoted phrase at one use; quoted phrases after
"swap in" or "instead" on that bullet are banned stand-ins.

Matching is case-insensitive on word boundaries ("robustness" is not
"robust"), with curly apostrophes read as straight ones.

Prints one line per problem on stdout:
  BANNED "delve" x2
  OVERUSED "Happy to" x3 (max 1)

Exit status: 0 nothing found, 1 one or more problems, 2 bad arguments, an
unreadable file, or a voice file with no "## Do not" section
(NO-DO-NOT-SECTION on stderr). Standard library only; no network.
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

# A double-quoted phrase, straight or curly quotes, on one line.
QUOTED = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')
DO_NOT_HEADING = re.compile(r"^##\s+Do not\s*$", re.IGNORECASE)
ONCE_MARKERS = ("once per email at most", "once per piece at most")
STANDIN_MARKERS = ("swap in", "instead")
BULLET = re.compile(r"^\s*[-*+]\s")


def normalize(text: str) -> str:
    """Curly apostrophes read as straight ones."""
    return text.replace("\u2019", "'")


def quoted_phrases(line: str) -> list[tuple[int, str]]:
    """(start offset, phrase) for every quoted phrase on the line."""
    return [(m.start(), normalize(m.group(1) or m.group(2)))
            for m in QUOTED.finditer(line)]


def parse_voice(text: str) -> tuple[dict[str, str], dict[str, str]]:
    """(banned, capped) as {lowercased phrase: display phrase}, voice order.

    Raises ValueError("NO-DO-NOT-SECTION") when the section is absent.
    """
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if DO_NOT_HEADING.match(ln)), None)
    if start is None:
        raise ValueError("NO-DO-NOT-SECTION")
    banned: dict[str, str] = {}
    capped: dict[str, str] = {}
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        for _, phrase in quoted_phrases(line):
            banned.setdefault(phrase.lower(), phrase)
    for line in lines:
        lowered = line.lower()
        if not BULLET.match(line) or not any(m in lowered for m in ONCE_MARKERS):
            continue
        phrases = quoted_phrases(line)
        if not phrases:
            continue
        capped.setdefault(phrases[0][1].lower(), phrases[0][1])
        # Search the original line, not its lower(): lower() can change a
        # character's length (e.g. U+0130) and shift the quote offsets.
        marker = min((m.start() for m in
                      (re.search(s, line, re.IGNORECASE) for s in STANDIN_MARKERS)
                      if m), default=None)
        if marker is not None:
            for pos, phrase in phrases[1:]:
                if pos > marker:
                    banned.setdefault(phrase.lower(), phrase)
    return banned, capped


def count_matches(phrase: str, text: str) -> int:
    pattern = re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.IGNORECASE)
    return len(pattern.findall(text))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check a rewrite for the voice's banned phrases and "
                    "once-per-email overuse. Exit 0 clean, 1 problems listed "
                    "on stdout, 2 bad arguments or unreadable file.")
    parser.add_argument("--voice", required=True, metavar="FILE",
                        help="the voice profile file (needs a '## Do not' section)")
    parser.add_argument("--rewrite", required=True, metavar="FILE",
                        help="the rewrite to check")
    args = parser.parse_args()
    try:
        voice_text = Path(args.voice).read_text(encoding="utf-8")
        rewrite_text = normalize(Path(args.rewrite).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        banned, capped = parse_voice(voice_text)
    except ValueError as exc:
        print(f"{exc}: {args.voice}", file=sys.stderr)
        return 2
    found = False
    for phrase in banned.values():
        n = count_matches(phrase, rewrite_text)
        if n:
            print(f'BANNED "{phrase}" x{n}')
            found = True
    for phrase in capped.values():
        n = count_matches(phrase, rewrite_text)
        if n > 1:
            print(f'OVERUSED "{phrase}" x{n} (max 1)')
            found = True
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())