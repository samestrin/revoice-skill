#!/usr/bin/env python3
"""Check a rewrite for hard-wrapped prose (standard library only, no network).

A wrap is a line outside a code fence that is followed directly (no blank
line) by a line starting with a lowercase letter, where neither line is a
list item, table row, quote or heading. A greeting or sign-off block
("Thanks," then "Alex") is not a wrap: the next line starts with a capital.

Prints one `HARD-WRAP line N` per wrapped continuation line (N is that
line's 1-based number). Exit 0: nothing found. Exit 1: one or more lines
on stdout. Exit 2: bad arguments or unreadable file (one line on stderr).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LIST_ITEM = re.compile(r"^([-*+]|\d+[.)])\s")


def structural(line: str) -> bool:
    """True for a blank line, heading, quote, list item or table row.

    Table rows are recognised by their pipes; prose in these rewrites
    does not carry pipes.
    """
    s = line.strip()
    return (not s or s.startswith(("#", ">")) or "|" in s
            or bool(LIST_ITEM.match(s)))


def prose_lines(lines: list[str]) -> list[bool]:
    """Per line: True when it is outside a code fence (fence markers count
    as inside). A fence opens with ``` or ~~~ and closes with the same
    marker, so a ~~~ line inside a ``` fence stays code."""
    out = []
    fence = None
    for line in lines:
        s = line.strip()
        if fence is None and s.startswith(("```", "~~~")):
            fence = s[:3]
            out.append(False)
        elif fence is not None and s.startswith(fence):
            fence = None
            out.append(False)
        else:
            out.append(fence is None)
    return out


def hard_wraps(lines: list[str]) -> list[int]:
    """1-based numbers of the wrapped continuation lines, in order."""
    prose = prose_lines(lines)
    found = []
    for i in range(len(lines) - 1):
        a, b = lines[i], lines[i + 1]
        if (prose[i] and prose[i + 1]
                and not structural(a) and not structural(b)
                and b.lstrip()[:1].islower()):
            found.append(i + 2)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Check a rewrite for hard-wrapped prose: a line followed "
                    "directly by a lowercase continuation outside code fences, "
                    "lists, tables, quotes and headings. Prints one "
                    "'HARD-WRAP line N' per wrap; exit 0 clean, 1 wraps found, "
                    "2 bad arguments or unreadable file.")
    ap.add_argument("--rewrite", required=True, type=Path,
                    help="path to the rewrite text file")
    args = ap.parse_args()

    try:
        text = args.rewrite.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    found = hard_wraps(text.splitlines())
    for n in found:
        print(f"HARD-WRAP line {n}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
