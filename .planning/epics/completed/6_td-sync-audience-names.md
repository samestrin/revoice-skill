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

- [x] An audience containing a path separator or `..` is rejected and nothing is written outside the voices dir. _(verified 2026-10-29: skill/revoice/tests/test_sync.py `test_audience_that_is_not_a_plain_name_is_refused` covers `../x`, `a/b`, `a\b`, `..`, `.`, `` and asserts exit 1, INVALID lines, only the expected files in the assets dir and no fetch for a bad audience; sync.py `plain_name` check in the audience loop; runs on a fake SilverBullet in the test)_
- [x] CI is green. _(verified 2026-10-29: CI run 40806791883 on main at 1e23fd2 succeeded; 123 tests pass locally)_

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.

<!-- refine-epic:begin -->
## Refinements (2026-10-29)
### Auto-applied corrections (0)
### Items needing user confirmation (0)
### Advisory observations (2)
- `sync.py` line numbers drifted by one or two (slug check is at lines 80-83, the audience loop at 93-100); the plan's `~` markers cover it and the symbols each match once.
- An invalid audience is checked inside the per-voice loop, so with several voices its `INVALID` line prints once per voice. Acceptable; the builder may hoist the check above the loop if the test stays simple. `--slug` runs and the empty string `""` should follow the same rule as the slug check (`sync.py:80`).
### Verification context
- Code repo: revoice-skill at e645a86. Plan written: 2026-10-29. Commits reviewed since: 0 (only `9260d47` touched `sync.py`, before the plan).
- Tasks: 1 (limit 7). Components: 1 (limit 3): skill/revoice
- Claims checked: 5 (slug check exists at sync.py:80; audience loop builds `{slug}-{aud}.md` from raw config at :99; test_sync.py has the matching slug test at :122; no test for audiences; tests dir path). Discovery searches: `INVALID`, `audiences`, `os.path.join(VOICES`
- Parallel check (technical-debt exception): File scope `skill/revoice/sync.py`, `skill/revoice/tests/test_sync.py` shares no file with epic 4 (`test_plugin_manifest.py`, `.claude-plugin/*`) or epic 5 (`review-samples.py`, `test_review_samples.py`); `gh pr list --state open` is empty. Scope not widened.
- Failure modes: input forms checked: `/`, `\`, `..`, `.`, `""` in the audience, same set as the slug check at sync.py:80. Nothing else applies (no network route, money or deploy; the fetch is to the owner's SilverBullet URL and unchanged).
- Vision fit: no VISION.md
<!-- refine-epic:end -->
