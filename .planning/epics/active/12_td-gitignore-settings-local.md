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

- [ ] `.claude/settings.local.json` is ignored by git.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.
