# Epic Plan 7: CHANGELOG Unreleased cleanup

- **Source:** technical-debt rows (.planning/technical-debt/README.md): CHANGELOG.md:17, CHANGELOG.md:19, CHANGELOG.md:25
- **File scope:** CHANGELOG.md
- **Runs in parallel:** yes. On 2026-10-30, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-30 (written by the CTO from technical-debt rows; not yet refined)

## Why

Three LOW docs rows against the Unreleased section: one entry is too long and a `### Fixed` entry contradicts README.md.

## Current State

`CHANGELOG.md` Unreleased has the long `Voice profiles now live` entry under `### Changed`, and a `### Fixed` entry saying Claude reads the extracted samples "to pick the best". README.md now says the review is local and Claude reads only the 15 `--top` profile samples. Line numbers have drifted; find the entries by text.

## Proposed Solution

Fix each row with a failing test first where a test can fail. No behaviour change beyond what the rows ask.

## Scope

Only the files in the File scope line. This is the one technical-debt epic that edits `CHANGELOG.md`, because every row is about it. It edits only the Unreleased section. The technical-debt list is not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Shorten the `Voice profiles now live` entry to two sentences and reword the `### Fixed` "to pick the best" clause to match README.md (local review; Claude reads only the 15 `--top` samples) · `CHANGELOG.md` · depends: none · tier: junior · success: Unreleased still has one `### Changed` heading and no entry loses its content, the long entry is at most two sentences, the Fixed entry no longer says "to pick the best", and `test_plugin_manifest.py` still passes; never by weakening or deleting a test

## Acceptance criteria

- [ ] No Unreleased entry loses its content (there is already exactly one `### Changed` heading).
- [ ] The `Voice profiles now live` entry is at most two sentences.
- [ ] The `### Fixed` entry matches README.md on who reads the samples.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.

<!-- refine-epic:begin -->
## Refinements (2026-10-30)
### Auto-applied corrections (0)
### Items needing user confirmation (1)
- **Q1 (T1, AC1): the second `### Changed` heading no longer exists.** `CHANGELOG.md` Unreleased has one `### Added` (line 8), one `### Changed` (line 16) and one `### Fixed` (line 25); `grep '^### '` shows no duplicate. Debt row `CHANGELOG.md:19` (technical-debt README line 35) is already satisfied, and AC1's first half holds today. Options: drop the merge clause from T1 and reword AC1 to "no entry loses its content" (recommended); keep the plan as it is.
### Advisory observations (2)
- The "Voice profiles now live" entry is `CHANGELOG.md:18` and the "to pick the best" clause is `CHANGELOG.md:27`; both still need the work in T1 (the long entry has four sentences, the Fixed entry still says Claude reads the samples "to pick the best" while README.md:165 says Claude reads only the 15 `--top` samples).
- The `CHANGELOG.md` entry at line 22 (README updated to match) is also long, but no row covers it; left out of scope.
### Verification context
- Code repo: revoice-skill at e6617fb. Plan written: 2026-10-30. Commits reviewed since: 0 on CHANGELOG.md
- Tasks: 1 (limit 7). Components: 1 (limit 3): CHANGELOG.md
- Claims checked: 6. Discovery searches: `grep '^### ' CHANGELOG.md`, `grep -rn changelog skill/revoice/tests`, README.md `--top`/local review
- Parallel check: File scope `CHANGELOG.md` is not in plans 4, 6, 8, 9 (they list only their own files and say they do not edit it) and there are no open PRs. Scope not widened.
- Failure modes: none apply: docs-only edit to a changelog, no route, data, money or deploy.
- Vision fit: no VISION.md
<!-- refine-epic:end -->

<!-- refine-epic:begin -->
## Refinements (2026-10-30)
### Auto-applied corrections (1)
- Q1 (answered by EST-3331, 95%): dropped the "merge the second `### Changed` block" clause from T1 and reworded AC1 to "no entry loses its content"; Unreleased already has one `### Changed` heading (`CHANGELOG.md:16` on main e6617fb). Current State no longer mentions a second block.
### Items needing user confirmation (0)
### Advisory observations (0)
### Verification context
- Code repo: revoice-skill at e6617fb. Plan written: 2026-10-30. Commits reviewed since: 0
- Tasks: 1 (limit 7). Components: 1 (limit 3): CHANGELOG.md
- Claims checked: 6. Discovery searches: see earlier report
- Failure modes: none apply: docs-only
- Vision fit: no VISION.md
<!-- refine-epic:end -->
