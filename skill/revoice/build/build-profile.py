#!/usr/bin/env python3
"""Build an author's voice profile JSON from their reviewed writing samples.

Uses the text analysis API (https://api.yourvoice.dev):
  - voice_profile   : /analyze/voice-profile on the top-N samples joined into
                      one text; usable as-is in /analyze/compare-profiles
  - comparison      : a z-score baseline (mean/std per feature over the author
                      samples plus any reference texts) and the author's mean
                      feature vector, for /analyze/compare-profiles
                      options.baseline
  - fingerprint     : /analyze/fingerprint on all kept samples. With
                      --reference, distinctive phrases are ranked against
                      other people's writing, which makes them far more
                      specific to the author. Without it, they are ranked by
                      how often they appear, so common phrases rise to the top.

Samples come from extract-samples.py. If index.csv has a "verdict" column
(from the review step), only KEEP rows are used, best "score" first.
Otherwise every sample is used, longest first.

Each text sent costs 1 credit, so a build costs
  1 + kept samples + reference texts + min(kept samples, 100)
credits. The first call reports the balance; if it cannot cover the rest of the
build, the build stops there and has spent 1 credit.

--check spends 1 credit on a short fixed text and prints whether the key works,
the balance and the estimated cost of a build from --samples and --reference.
It writes no profile and does not need --author.

The API key is read from --api-key, else the TEXT_ANALYSIS_API_KEY environment
variable, else the key file (default ~/.config/revoice/api-key). The key file
keeps the key out of chat transcripts and shell history.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import statistics
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path


# The API accepts at most this many documents per list ("texts" and
# "reference_texts" separately).
MAX_DOCS = 100

# The one text --check sends (1 credit).
CHECK_TEXT = "This is a short text to check the API key."

WAYS_OUT = ("Buy credits at https://yourvoice.dev, or rebuild with fewer samples "
            "or without --reference.")


def build_cost(samples: int, reference: int) -> int:
    """Credits a build spends: 1 per text sent."""
    return 1 + samples + reference + min(samples, MAX_DOCS)


def post(api: str, path: str, body: dict, key: str) -> dict:
    return post_with_balance(api, path, body, key)[0]


def post_with_balance(api: str, path: str, body: dict, key: str) -> tuple[dict, int | None]:
    """POST body; return the reply and X-Credits-Remaining (None if absent or unreadable)."""
    headers = {"Content-Type": "application/json", "X-API-Key": key}
    req = urllib.request.Request(api + path, json.dumps(body).encode(), headers)
    try:
        reply = urllib.request.urlopen(req, timeout=600)
        return json.load(reply), balance_of(reply)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        sys.exit(http_failure(path, e, detail))
    except urllib.error.URLError as e:
        sys.exit(f"error: cannot reach the API at {api} ({e.reason}). "
                 "Check the address and your connection.")
    except OSError as e:  # timeout or reset while reading the reply
        sys.exit(f"error: lost the connection to the API at {api} ({e}). Try again.")
    except ValueError:
        sys.exit(f"error: {path} returned an unexpected reply (not JSON). Try again.")


def balance_of(reply) -> int | None:
    headers = getattr(reply, "headers", None)
    value = headers.get("X-Credits-Remaining") if headers is not None else None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def count_reference(reference: Path | None) -> int:
    return len(list(reference.glob("*.md"))) if reference and reference.is_dir() else 0


def check(api: str, key: str, samples: Path, reference: Path | None) -> None:
    """Spend 1 credit to show the key works, the balance and the build's cost."""
    _, balance = post_with_balance(api, "/analyze/voice-profile", {"texts": [CHECK_TEXT]}, key)
    print("key: OK")
    print(f"balance: {balance} credits" if balance is not None else "balance: unknown")
    if not (samples / "index.csv").is_file():
        print(f"estimated cost: no samples in {samples} yet")
        return
    n, r = len(ranked_files(samples)), count_reference(reference)
    cost = build_cost(n, r)
    print(f"estimated cost: {cost} credits ({n} samples, {r} reference texts)")
    if balance is not None and balance < cost:
        print(f"short by {cost - balance} credits. {WAYS_OUT}")


def http_failure(path: str, e: urllib.error.HTTPError, detail: str) -> str:
    if e.code == 401:
        return "error: the API rejected the key (HTTP 401). Check the key and try again."
    if e.code == 402:
        try:
            info = json.loads(detail)
            return (f"error: out of credits: balance {info['balance']}, this build costs "
                    f"{info['cost']}. Add credits and try again.")
        except (ValueError, KeyError, TypeError):
            pass
    if e.code == 429:
        wait = e.headers.get("Retry-After") if e.headers else None
        return ("error: rate limited (HTTP 429). "
                + (f"Wait {wait} seconds and try again." if wait else "Wait a little and try again."))
    return f"error: {path} returned HTTP {e.code}: {detail}"


def profiles(api: str, texts: list[str], key: str) -> list[dict]:
    out = []
    for i in range(0, len(texts), MAX_DOCS):
        out += post(api, "/analyze/voice-profile", {"texts": texts[i:i + MAX_DOCS]}, key)["results"]
    return out


def body(path: Path) -> str:
    return path.read_text(encoding="utf-8").partition("\n")[2].strip()


def ranked_files(samples: Path) -> list[str]:
    with open(samples / "index.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if rows and "verdict" in rows[0]:
        rows = [r for r in rows if r["verdict"].strip().upper() == "KEEP"]

    def score(r: dict) -> float:
        try:
            return float(r.get("score") or 0)
        except ValueError:
            return 0.0

    rows.sort(key=lambda r: (score(r), int(r.get("words") or 0)), reverse=True)
    return [r["file"] for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", type=Path, default=Path("samples"))
    ap.add_argument("--reference", type=Path, default=None,
                    help="optional directory of .md texts by other writers (recommended)")
    ap.add_argument("--author", help="author name, recorded in the profile (required unless --check)")
    ap.add_argument("--from", dest="senders", action="append", default=[],
                    help="author's address, recorded in the profile (repeatable)")
    ap.add_argument("--cutoff", default=None,
                    help="the date the mbox was filtered to, recorded in the profile (YYYY-MM-DD)")
    ap.add_argument("--api", default="https://api.yourvoice.dev")
    ap.add_argument("--api-key", default=os.environ.get("TEXT_ANALYSIS_API_KEY"))
    ap.add_argument("--api-key-file", type=Path,
                    default=Path.home() / ".config" / "revoice" / "api-key")
    ap.add_argument("--top", type=int, default=15,
                    help="samples joined into the voice profile (about 15 worked best in testing)")
    ap.add_argument("-o", "--out", type=Path, default=Path("voice-profile.json"))
    ap.add_argument("--check", action="store_true",
                    help="spend 1 credit to check the key; print the balance and the "
                         "estimated cost of a build, write nothing")
    args = ap.parse_args()
    if not args.check and not args.author:
        ap.error("--author is required (except with --check)")
    if not args.api_key and args.api_key_file.is_file():
        # utf-8-sig: Notepad and PowerShell may save the file with a BOM
        args.api_key = args.api_key_file.read_text(encoding="utf-8-sig").strip()
    if not args.api_key:
        sys.exit(f"error: no API key. Save it in {args.api_key_file}, "
                 "or set TEXT_ANALYSIS_API_KEY, or pass --api-key.")
    api, key = args.api.rstrip("/"), args.api_key
    if args.check:
        check(api, key, args.samples, args.reference)
        return

    files = ranked_files(args.samples)
    if not files:
        sys.exit(f"error: no usable samples in {args.samples}")
    if len(files) < args.top:
        print(f"warning: only {len(files)} samples; the profile is built from all of them")
    texts = [body(args.samples / f) for f in files]
    top_files = files[: args.top]
    reference_files = sorted(args.reference.glob("*.md")) if args.reference else []
    reference = [body(p) for p in reference_files]
    cost = build_cost(len(texts), len(reference))
    print(f"this build costs {cost} credits ({len(texts)} samples, {len(reference)} reference texts)")

    reply, balance = post_with_balance(api, "/analyze/voice-profile",
                                       {"texts": ["\n\n".join(texts[: args.top])]}, key)
    voice_profile = reply["results"][0]
    # No header means the balance is unknown: go on, and a 402 says if it runs out.
    if balance is not None and balance < cost - 1:
        sys.exit(f"error: this build costs {cost} credits and you have {balance} credits left "
                 f"(1 spent checking the balance). {WAYS_OUT}")

    author_vectors = profiles(api, texts, key)
    reference_vectors = profiles(api, reference, key) if reference else []
    feats = sorted(author_vectors[0]["feature_vector"])
    pool = [p["feature_vector"] for p in author_vectors + reference_vectors]
    baseline = {
        "mean": {k: round(statistics.fmean(v[k] for v in pool), 6) for k in feats},
        "std": {k: round(statistics.pstdev(v[k] for v in pool), 6) for k in feats},
    }
    author_mean = {k: round(statistics.fmean(p["feature_vector"][k] for p in author_vectors), 6)
                   for k in feats}

    # The fingerprint compares the whole set at once, so it cannot be batched:
    # use the best samples and the longest reference texts, up to the API limit.
    fp_texts = texts[:MAX_DOCS]
    fp_reference = sorted(reference, key=len, reverse=True)[:MAX_DOCS]
    if len(texts) > MAX_DOCS or len(reference) > MAX_DOCS:
        print(f"note: fingerprint uses {len(fp_texts)} of {len(texts)} samples and "
              f"{len(fp_reference)} of {len(reference)} reference texts (API limit {MAX_DOCS})")
    fp_body = {"texts": fp_texts}
    if fp_reference:
        fp_body["options"] = {"reference_texts": fp_reference}
    fp = post(api, "/analyze/fingerprint", fp_body, key)

    try:
        health = json.load(urllib.request.urlopen(api + "/health", timeout=30))
    except (OSError, ValueError):
        health = {}  # the version is informational; still write the profile

    source = "email export, attachments ignored, reviewed samples"
    if args.cutoff:
        source += f", dated before {args.cutoff}"
    profile = {
        "meta": {
            "author": args.author,
            "generated": date.today().isoformat(),
            "source": source,
            "sender_addresses": args.senders,
            "api": {"url": api, "version": health.get("version")},
            "samples": {"voice_profile": top_files, "fingerprint_and_baseline": len(files)},
            "reference": {"description": "emails by other senders in the same mailbox",
                          "count": len(reference_files)},
        },
        "voice_profile": voice_profile,
        "comparison": {
            "usage": "POST /analyze/compare-profiles with profiles [author, candidate] and "
                     "options.baseline; set the author's feature_vector to author_feature_vector_mean",
            "baseline": baseline,
            "author_feature_vector_mean": author_mean,
        },
        "fingerprint": {
            "distinctive_phrases": fp["distinctive_phrases"],
            "first_person_patterns": fp["first_person_patterns"],
            "informality": fp["informality"],
            "corpus_document_count": fp["corpus_document_count"],
        },
    }
    args.out.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size:,} bytes) from {len(files)} samples"
          f" ({len(top_files)} in the voice profile), {len(reference_files)} reference texts")


if __name__ == "__main__":
    main()
