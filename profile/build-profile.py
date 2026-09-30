#!/usr/bin/env python3
"""Build an author's voice profile JSON from their reviewed writing samples.

Uses the text analysis API (https://text-analysis-api.estr.in):
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

The API key is read from --api-key or the TEXT_ANALYSIS_API_KEY environment
variable.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import statistics
import sys
import urllib.request
from datetime import date
from pathlib import Path


def post(api: str, path: str, body: dict, key: str) -> dict:
    headers = {"Content-Type": "application/json", "X-API-Key": key}
    req = urllib.request.Request(api + path, json.dumps(body).encode(), headers)
    return json.load(urllib.request.urlopen(req, timeout=600))


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
    ap.add_argument("--author", required=True, help="author name, recorded in the profile")
    ap.add_argument("--from", dest="senders", action="append", default=[],
                    help="author's address, recorded in the profile (repeatable)")
    ap.add_argument("--cutoff", default=None,
                    help="the date the mbox was filtered to, recorded in the profile (YYYY-MM-DD)")
    ap.add_argument("--api", default="https://text-analysis-api.estr.in")
    ap.add_argument("--api-key", default=os.environ.get("TEXT_ANALYSIS_API_KEY"))
    ap.add_argument("--top", type=int, default=15,
                    help="samples joined into the voice profile (about 15 worked best in testing)")
    ap.add_argument("-o", "--out", type=Path, default=Path("voice-profile.json"))
    args = ap.parse_args()
    if not args.api_key:
        sys.exit("error: no API key. Pass --api-key or set TEXT_ANALYSIS_API_KEY.")
    api, key = args.api.rstrip("/"), args.api_key

    files = ranked_files(args.samples)
    if not files:
        sys.exit(f"error: no usable samples in {args.samples}")
    if len(files) < args.top:
        print(f"warning: only {len(files)} samples; the profile is built from all of them")
    texts = [body(args.samples / f) for f in files]
    top_files = files[: args.top]
    reference_files = sorted(args.reference.glob("*.md")) if args.reference else []
    reference = [body(p) for p in reference_files]

    voice_profile = post(api, "/analyze/voice-profile",
                         {"texts": ["\n\n".join(texts[: args.top])]}, key)["results"][0]

    author_vectors = post(api, "/analyze/voice-profile", {"texts": texts}, key)["results"]
    reference_vectors = (post(api, "/analyze/voice-profile", {"texts": reference}, key)["results"]
                         if reference else [])
    feats = sorted(author_vectors[0]["feature_vector"])
    pool = [p["feature_vector"] for p in author_vectors + reference_vectors]
    baseline = {
        "mean": {k: round(statistics.fmean(v[k] for v in pool), 6) for k in feats},
        "std": {k: round(statistics.pstdev(v[k] for v in pool), 6) for k in feats},
    }
    author_mean = {k: round(statistics.fmean(p["feature_vector"][k] for p in author_vectors), 6)
                   for k in feats}

    fp_body = {"texts": texts}
    if reference:
        fp_body["options"] = {"reference_texts": reference}
    fp = post(api, "/analyze/fingerprint", fp_body, key)

    health = json.load(urllib.request.urlopen(api + "/health", timeout=30))

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
