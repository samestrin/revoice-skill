# Epic Plan 12: ignore settings.local.json

- **Source:** technical-debt rows (.planning/technical-debt/README.md): .gitignore:1
- **File scope:** .gitignore
- **Runs in parallel:** yes. On 2026-10-30, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-30 (written by the CTO from technical-debt rows; not yet refined)

## Why

`.claude/settings.local.json` is not ignored, so it shows up as untracked.

## Current State

`.gitignore` has no `.claude/settings.local.json` entry. The CI step that fails on tracked files matching `.gitignore` must stay green.

## Proposed Solution

Fix the row with a failing test first where a test can fail. No behaviour change beyond what the row asks.

## Scope

Only the files in the File scope line. `CHANGELOG.md` and the technical-debt list are not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Add `.claude/settings.local.json` to `.gitignore`; check with `git check-ignore .claude/settings.local.json` · `.gitignore` · depends: none · tier: intern · success: `git check-ignore` reports the file and no tracked file becomes ignored; never by weakening or deleting a test

## Acceptance criteria

- [x] `.claude/settings.local.json` is ignored by git. _(verified 2026-10-30: `git check-ignore -v` on main matches .gitignore:16; no tracked file is ignored (`git ls-files -ci --exclude-standard` empty))_
- [x] CI is green. _(verified 2026-10-30: CI success on main at 0de30cf and 9be9928)_

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.

<!-- refine-epic:begin -->
## Refinements (2026-10-30)
### Auto-applied corrections (0)
### Items needing user confirmation (0)
### Advisory observations (1)
- `.planning/epics/active/` also holds `4_td-manifest-tests-and-icon.md` and `6_td-sync-audience-names.md`, which have copies in `completed/` on `main`. Neither touches `.gitignore`, so they do not affect this epic.
### Verification context
- Code repo: revoice-skill at f49e9a5. Plan written: 2026-10-30. Commits reviewed since: 0 (none touch .gitignore)
- Tasks: 1 (limit 7). Components: 1 (limit 3): .gitignore
- Claims checked: 4 (no `.claude/settings.local.json` entry in .gitignore; the file exists untracked and `git check-ignore` does not match it; no tracked file under `.claude/`; CI step `.github/workflows/ci.yml:40` runs `git ls-files -ci --exclude-standard`). Discovery searches: gitignore and ls-files in `.github`, `.planning/epics/active`
- Parallel check: File scope `.gitignore` is in no other active plan's scope or tasks (4, 6, 10, 11) and in no open PR (`gh pr list` is empty).
- Failure modes: none apply: a one-line ignore entry touches no route, login, money, personal data, deploy or remote command.
- Vision fit: no VISION.md
<!-- refine-epic:end -->
