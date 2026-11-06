#!/usr/bin/env bash
# Checks an installed copy of the revoice skill folder: SKILL.md says
# `name: revoice`, and every helper is there and answers --help.
#
# Usage: check-installed-skill.sh <installed skill/revoice folder> <repo checkout>
#
# The helper list is written out here, not read from the installed copy, so a
# helper missing from the install fails. The repo check below keeps the list
# honest: a new helper in the repo that is not listed here fails too.
set -euo pipefail

installed="${1:?usage: $0 <installed skill folder> <repo checkout>}"
repo="${2:?usage: $0 <installed skill folder> <repo checkout>}"

helpers=(
  build/build-profile.py
  build/extract-samples.py
  build/mbox-filter-before.py
  build/review-samples.py
  sync.py
)

fail() {
  echo "::error::$*"
  exit 1
}

command -v python3 > /dev/null || fail "python3 is not on PATH; the helper --help checks need it"

[ -d "$installed" ] || fail "installed skill folder not found: $installed"
echo "== installed copy: $installed"

# The repo's helpers must all be in the list above.
for path in "$repo"/skill/revoice/build/*.py "$repo"/skill/revoice/sync.py; do
  rel="${path#"$repo"/skill/revoice/}"
  listed=no
  for h in "${helpers[@]}"; do
    [ "$h" = "$rel" ] && listed=yes
  done
  [ "$listed" = yes ] || fail "helper $rel is in the repo but not in the list in $0"
done

# SKILL.md with `name: revoice` inside its front matter.
skill_md="$installed/SKILL.md"
[ -f "$skill_md" ] || fail "SKILL.md missing from the installed copy: $skill_md"
[ "$(head -n 1 "$skill_md")" = "---" ] || fail "SKILL.md does not start with front matter"
front_matter="$(awk 'NR == 1 { next } /^---$/ { exit } { print }' "$skill_md")"
grep -qx 'name: revoice' <<< "$front_matter" || fail "SKILL.md front matter has no 'name: revoice' line"
echo "ok: SKILL.md has name: revoice"

# Each helper's --help, run from the installed copy.
for h in "${helpers[@]}"; do
  [ -f "$installed/$h" ] || fail "helper missing from the installed copy: $h"
  python3 "$installed/$h" --help > /dev/null || fail "$h --help failed in the installed copy"
  echo "ok: $h --help"
done
