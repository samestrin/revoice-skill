#!/usr/bin/env python3
"""Print one version's CHANGELOG.md section, for the notes of a GitHub release.

    release-notes.py <x.y.z> [--changelog <path>]
    release-notes.py <x.y.z> --check [--root <repo>]

Prints the lines under `## [x.y.z]`, up to the next `## ` heading (or the
`[x.y.z]: <url>` link list at the end), without the heading itself, since the
release title already names the version.

With --check it first fails unless the version equals plugin.json `version`,
SKILL.md `metadata.version` and the newest released CHANGELOG heading, so a tag
that disagrees with the files never becomes a release. The release workflow
(`.github/workflows/release.yml`) runs it with the pushed tag minus its `v`.

Prints one GitHub `::error` line and exits 1 on any problem; prints nothing
to stdout then. Python 3 standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
# The version readers live with the test that keeps the three files in step.
sys.path.insert(0, str(ROOT / "skill" / "revoice" / "tests"))
from test_plugin_manifest import newest_released_version, skill_md_version  # noqa: E402

VERSION = re.compile(r"\d+\.\d+\.\d+")
NEXT_HEADING = re.compile(r"^## |^\[[^\]]+\]:\s")


class ReleaseError(Exception):
    pass


def section(changelog: str, version: str) -> str:
    """The body of the `## [version]` section, trimmed of blank lines at both ends."""
    lines = changelog.splitlines()
    heading = re.compile(rf"^## \[{re.escape(version)}\]")
    start = next((i for i, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        raise ReleaseError(f"CHANGELOG.md has no `## [{version}]` heading")
    body = []
    for line in lines[start + 1:]:
        if NEXT_HEADING.match(line):
            break
        body.append(line)
    text = "\n".join(body).strip("\n")
    if not text.strip():
        raise ReleaseError(f"CHANGELOG.md section `## [{version}]` is empty")
    return text


def check_versions(root: Path, version: str) -> None:
    plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    found = {
        "plugin.json version": plugin.get("version"),
        "SKILL.md metadata.version": skill_md_version(
            (root / "skill" / "revoice" / "SKILL.md").read_text(encoding="utf-8")),
        "CHANGELOG.md newest released heading": newest_released_version(
            (root / "CHANGELOG.md").read_text(encoding="utf-8")),
    }
    wrong = [f"{name} is {value}" for name, value in found.items() if value != version]
    if wrong:
        raise ReleaseError(f"tag version {version} does not match: " + "; ".join(wrong))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the release version, x.y.z (the tag without its v)")
    parser.add_argument("--changelog", type=Path, help="CHANGELOG.md to read (default: <root>/CHANGELOG.md)")
    parser.add_argument("--check", action="store_true",
                        help="first fail unless plugin.json, SKILL.md and CHANGELOG.md name this version")
    parser.add_argument("--root", type=Path, default=ROOT, help="repo root (default: this script's repo)")
    args = parser.parse_args(argv)

    try:
        if not VERSION.fullmatch(args.version):
            raise ReleaseError(f"version {args.version!r} is not x.y.z (push tags as v0.2.0)")
        if args.check:
            check_versions(args.root, args.version)
        changelog = args.changelog or args.root / "CHANGELOG.md"
        notes = section(changelog.read_text(encoding="utf-8"), args.version)
    except (ReleaseError, AssertionError, OSError, ValueError) as err:
        print(f"::error::{err}", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
