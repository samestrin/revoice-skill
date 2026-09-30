#!/usr/bin/env python3
"""Copy an mbox, keeping only messages dated before a cutoff.

Messages whose Date header cannot be parsed are dropped and counted, so an
undated message can never sneak into a corpus meant to be pre-cutoff.

A cutoff of 2022-09-01 (ChatGPT launched 2022-11-30, minus a 3-month buffer)
keeps AI-assisted writing out of the corpus.
"""
from __future__ import annotations
import argparse
import mailbox
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


def _msg_date(msg) -> datetime | None:
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(str(raw))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mbox", type=Path)
    ap.add_argument("--before", required=True, help="cutoff date, YYYY-MM-DD (UTC)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args()

    cutoff = datetime.strptime(args.before, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    # mailbox writes os.linesep, so on Windows the copy gets CRLF line endings,
    # and mailbox then cannot parse its headers when reading it back. Keep LF,
    # which is what Gmail exports use.
    mailbox.linesep = b"\n"
    src = mailbox.mbox(str(args.mbox))
    dst = mailbox.mbox(str(args.out))
    dst.clear()

    kept = dropped_late = dropped_undated = 0
    oldest = newest = None
    for msg in src:
        dt = _msg_date(msg)
        if dt is None:
            dropped_undated += 1
        elif dt >= cutoff:
            dropped_late += 1
        else:
            dst.add(msg)
            kept += 1
            oldest = dt if oldest is None or dt < oldest else oldest
            newest = dt if newest is None or dt > newest else newest
    dst.flush()
    dst.close()

    print(f"wrote {args.out}")
    print(f"  kept            : {kept:,}")
    print(f"  dropped (late)  : {dropped_late:,}")
    print(f"  dropped (undated): {dropped_undated:,}")
    if kept:
        print(f"  date range kept : {oldest:%Y-%m-%d} to {newest:%Y-%m-%d}")


if __name__ == "__main__":
    main()
