# Epic Plan 6: sync.py audience name validation

- **Source:** technical-debt rows (.planning/technical-debt/README.md): skill/revoice/sync.py:main
- **File scope:** skill/revoice/sync.py, skill/revoice/tests/test_sync.py
- **Runs in parallel:** yes. On 2026-10-29, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-29 (written by the CTO from technical-debt rows; not yet refined)

## Why

One LOW correctness row from epic 3: audience names from the config are not validated, so an `audiences` entry containing `/` or `..` writes outside the voices dir.

## Current State

`sync.py` `main()` already rejects a voice slug that is not a plain file name (`INVALID  {slug}: a voice slug must be a plain file name`, line ~81), but the loop over `audiences` (line ~93) builds `voices/<slug>-<audience>.md` from the raw config value.

## Proposed Solution

Fix each row with a failing test first. No behaviour change beyond what the rows ask.

## Scope

Only the files in the File scope line. `CHANGELOG.md` and the technical-debt list are not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Apply the same plain-file-name check to each audience; an invalid one prints `INVALID` and is skipped (exit status as for an invalid slug); failing test first with an audience like `../x` and `a/b` · `skill/revoice/sync.py`, `skill/revoice/tests/test_sync.py` · depends: none · tier: junior · success: the test shows no file is written outside the voices dir; never by weakening or deleting a test

## Acceptance criteria

- [ ] An audience containing a path separator or `..` is rejected and nothing is written outside the voices dir.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.
