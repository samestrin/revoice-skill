#!/usr/bin/env python3
"""Mark each extracted sample KEEP or DROP with the text analysis API.

Reads samples/index.csv (from extract-samples.py), posts the samples to
/analyze/sample-review in batches of at most 100, and adds the columns
verdict, score and reason to index.csv. Existing columns and rows are kept.
build-profile.py then uses only the KEEP rows, best score first.

index.csv is replaced only after every batch succeeded, so a failed run
leaves it as it was. A rerun reviews every sample again.

The API key is read from --api-key, else the TEXT_ANALYSIS_API_KEY environment
variable, else the key file (default ~/.config/revoice/api-key).
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import socket
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


# The API accepts at most this many samples per request.
BATCH = 100
# The API's metered limit is 25 s; allow some slack for the network.
TIMEOUT = 60
COLUMNS = ["verdict", "score", "reason"]


def post(api: str, path: str, body: dict, key: str) -> dict:
    headers = {"Content-Type": "application/json", "X-API-Key": key}
    req = urllib.request.Request(api + path, json.dumps(body).encode(), headers)
    try:
        return json.load(urllib.request.urlopen(req, timeout=TIMEOUT))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code == 401:
            sys.exit("error: the API rejected the key (HTTP 401). Check the API key. "
                     "index.csv was not changed.")
        if e.code == 402:
            sys.exit("error: out of credits (HTTP 402). Add credits and run again. "
                     "index.csv was not changed.")
        if e.code >= 500:
            sys.exit(f"error: the API is down (HTTP {e.code}). Try again later. "
                     "index.csv was not changed.")
        sys.exit(f"error: {path} returned HTTP {e.code}: {detail}. index.csv was not changed.")
    except (TimeoutError, socket.timeout, urllib.error.URLError) as e:
        sys.exit(f"error: the API is down or did not answer in {TIMEOUT} s ({e}). "
                 "Try again later. index.csv was not changed.")


def body(path: Path) -> str:
    return path.read_text(encoding="utf-8").partition("\n")[2].strip()


def review(api: str, key: str, samples: Path, rows: list[dict]) -> list[dict]:
    """Return one {verdict, score, reason} dict per row, in row order."""
    out: list[dict] = []
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        payload = {"samples": [{"id": r["file"], "text": body(samples / r["file"])} for r in batch]}
        results = post(api, "/analyze/sample-review", payload, key).get("results")
        if not isinstance(results, list) or [r.get("id") for r in results] != [r["file"] for r in batch]:
            sys.exit("error: /analyze/sample-review returned results that do not match "
                     "the samples sent. index.csv was not changed.")
        out += [{"verdict": r["verdict"], "score": r["score"], "reason": r.get("reason", "")}
                for r in results]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", type=Path, default=Path("samples"))
    ap.add_argument("--api", default="https://text-analysis-api.estr.in")
    ap.add_argument("--api-key", default=os.environ.get("TEXT_ANALYSIS_API_KEY"))
    ap.add_argument("--api-key-file", type=Path,
                    default=Path.home() / ".config" / "revoice" / "api-key")
    args = ap.parse_args()
    if not args.api_key and args.api_key_file.is_file():
        # utf-8-sig: Notepad and PowerShell may save the file with a BOM
        args.api_key = args.api_key_file.read_text(encoding="utf-8-sig").strip()
    if not args.api_key:
        sys.exit(f"error: no API key. Save it in {args.api_key_file}, "
                 "or set TEXT_ANALYSIS_API_KEY, or pass --api-key.")
    api, key = args.api.rstrip("/"), args.api_key

    index = args.samples / "index.csv"
    with open(index, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if not rows:
        sys.exit(f"error: no samples in {index}")

    verdicts = review(api, key, args.samples, rows)

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


if __name__ == "__main__":
    main()
