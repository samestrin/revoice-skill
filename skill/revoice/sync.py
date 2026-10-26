#!/usr/bin/env python3
"""Copy voice profiles from SilverBullet into the skill's assets/.

Fetches raw note bytes over SilverBullet's /.fs/ HTTP API so nothing passes
through the model's context (where it can be compressed or altered).

For each voice in the config, syncs the base note (voices.<slug>.sb_source ->
assets/<slug>.md) and, for each name in `audiences`, the overlay note
"<sb_source minus .md> (<audience>).md" -> assets/<slug>-<audience>.md.
A missing overlay is skipped. A missing base is an error for that voice.

The config is ~/.config/revoice/config.yaml. Reading it needs PyYAML
(pip install pyyaml); --help does not.
"""

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CONFIG = os.path.expanduser("~/.config/revoice/config.yaml")
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def fetch(sb_url: str, note: str) -> bytes | None:
    url = f"{sb_url.rstrip('/')}/.fs/{urllib.parse.quote(note)}"
    req = urllib.request.Request(url, headers={"X-Sync-Mode": "true"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def write(path: str, data: bytes) -> None:
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?", help="sync only this voice (default: every voice in the config)")
    args = ap.parse_args()

    # Imported here so --help works without PyYAML; only --sync needs it.
    try:
        import yaml
    except ImportError:
        print("error: sync needs PyYAML: pip install pyyaml", file=sys.stderr)
        return 1
    if not os.path.isfile(CONFIG):
        print(f"error: no config at {CONFIG} (copy config.example.yaml there)", file=sys.stderr)
        return 1
    with open(CONFIG) as f:
        cfg = yaml.safe_load(f)
    sb_url = cfg.get("sb_url")
    if not sb_url:
        print("error: sb_url is not set in config", file=sys.stderr)
        return 1
    voices = cfg.get("voices") or {}
    audiences = cfg.get("audiences") or []
    only = args.slug
    if only and only not in voices:
        print(f"error: voice '{only}' is not in config", file=sys.stderr)
        return 1

    os.makedirs(ASSETS, exist_ok=True)
    failed = False
    for slug, spec in voices.items():
        if only and slug != only:
            continue
        base = spec["sb_source"]
        data = fetch(sb_url, base)
        if not data:
            print(f"MISSING  {slug}: {base}")
            failed = True
            continue
        write(os.path.join(ASSETS, f"{slug}.md"), data)
        print(f"UPDATED  {slug}.md <- {base}")
        stem = base[:-3] if base.endswith(".md") else base
        for aud in audiences:
            note = f"{stem} ({aud}).md"
            data = fetch(sb_url, note)
            if not data:
                print(f"SKIPPED  {slug}-{aud}.md (no note: {note})")
                continue
            write(os.path.join(ASSETS, f"{slug}-{aud}.md"), data)
            print(f"UPDATED  {slug}-{aud}.md <- {note}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
