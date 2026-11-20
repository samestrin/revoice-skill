#!/usr/bin/env python3
"""Check a voice file against the build.md phase 6 format, on this machine.

Reads the voice file written in build.md phase 6 and checks its shape: a
first line `# <Name>: Writing Profile`, the 11 section headings below as
`## ` headings in that order, a non-empty `## Do not` section with at least
one double-quoted phrase (straight or curly quotes) and a line that says do
not invent facts, numbers or names, and no emoji anywhere.

Prints one line per problem on stdout and exits 1, or nothing and exits 0:
  BAD-TITLE line 1            first line is not `# <Name>: Writing Profile`
  MISSING-SECTION <name>      an expected `## ` heading is not in the file
  OUT-OF-ORDER <name>         a heading appears before an earlier one in the list
  EMPTY-SECTION Do not        the Do not section has no content
  NO-QUOTED-PHRASE Do not     no double-quoted phrase under Do not
  NO-INVENT-RULE Do not       no "do not invent facts, numbers or names" line
  EMOJI line N                an emoji on line N (1-based)

Extra `## ` sections are allowed; only the 11 expected ones are checked.
Bad arguments or an unreadable file: one line on stderr, exit 2.

Standard library only; no network call. The bundled assets/example.md
passes this check.
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

# The 11 section headings from build.md phase 6 step 2, in order.
SECTIONS = (
    "The voice in one paragraph",
    "Core traits",
    "Sentences",
    "Word choice and signature phrases",
    "Punctuation and formatting habits",
    "Paragraphs and structure",
    "Pronouns",
    "Stats reference",
    "Do not",
    "Short examples from the corpus",
    "Before and after",
)

TITLE_RE = re.compile(r"^# \S.*: Writing Profile\s*$")
QUOTED_RE = re.compile(r'"[^"\r\n]+"|“[^”\r\n]+”')
# "do not invent" plus all three words on one line, in any order.
INVENT_RE = re.compile(
    r"^(?=.*\bdo not invent\b)(?=.*\bfacts\b)(?=.*\bnumbers\b)(?=.*\bnames\b)",
    re.IGNORECASE)
# Emoji and pictograph blocks: symbols and dingbats, arrows-and-stars block,
# the emoji planes, and the emoji variation selector (text-vs-emoji marker).
EMOJI_RE = re.compile("[\u2600-\u27BF\u2B00-\u2BFF\U0001F000-\U0001FAFF\uFE0F]")


def check(text: str) -> list[str]:
    """Every problem with the voice file text, one line per problem."""
    problems: list[str] = []
    lines = text.splitlines()
    if not lines or not TITLE_RE.match(lines[0]):
        problems.append("BAD-TITLE line 1")

    # First occurrence of each expected `## ` heading, by line number.
    found: dict[str, int] = {}
    for i, line in enumerate(lines):
        if line.startswith("## "):
            name = line[3:].strip()
            if name in SECTIONS and name not in found:
                found[name] = i

    for name in SECTIONS:
        if name not in found:
            problems.append(f"MISSING-SECTION {name}")

    # Walk the found headings in file order; one that steps back in the
    # expected order is the heading that moved.
    highest = -1
    for name in sorted(found, key=found.get):
        index = SECTIONS.index(name)
        if index < highest:
            problems.append(f"OUT-OF-ORDER {name}")
        else:
            highest = index

    if "Do not" in found:
        start = found["Do not"] + 1
        end = start
        while end < len(lines) and not lines[end].startswith("## "):
            end += 1
        body = lines[start:end]
        if not any(line.strip() for line in body):
            problems.append("EMPTY-SECTION Do not")
        else:
            body_text = "\n".join(body)
            if not QUOTED_RE.search(body_text):
                problems.append("NO-QUOTED-PHRASE Do not")
            if not any(INVENT_RE.search(line) for line in body):
                problems.append("NO-INVENT-RULE Do not")

    for i, line in enumerate(lines, start=1):
        if EMOJI_RE.search(line):
            problems.append(f"EMOJI line {i}")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", required=True, metavar="FILE",
                    help="the voice file to check (build.md phase 6 format)")
    args = ap.parse_args()
    try:
        # utf-8-sig: a BOM from a Windows editor is not part of the title.
        text = Path(args.voice).expanduser().read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read {args.voice}: {exc}", file=sys.stderr)
        return 2
    problems = check(text)
    for line in problems:
        print(line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
