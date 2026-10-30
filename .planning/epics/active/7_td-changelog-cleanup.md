# Epic Plan 7: CHANGELOG Unreleased cleanup

- **Source:** technical-debt rows (.planning/technical-debt/README.md): CHANGELOG.md:17, CHANGELOG.md:19, CHANGELOG.md:25
- **File scope:** CHANGELOG.md
- **Runs in parallel:** yes. On 2026-10-30, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-30 (written by the CTO from technical-debt rows; not yet refined)

## Why

Three LOW docs rows against the Unreleased section: one entry is too long, there are two `### Changed` headings, and a `### Fixed` entry contradicts README.md.

## Current State

`CHANGELOG.md` Unreleased has the long `Voice profiles now live` entry under `### Changed`, a second `### Changed` block further down, and a `### Fixed` entry saying Claude reads the extracted samples "to pick the best". README.md now says the review is local and Claude reads only the 15 `--top` profile samples. Line numbers have drifted; find the entries by text.

## Proposed Solution

Fix each row with a failing test first where a test can fail. No behaviour change beyond what the rows ask.

## Scope

Only the files in the File scope line. This is the one technical-debt epic that edits `CHANGELOG.md`, because every row is about it. It edits only the Unreleased section. The technical-debt list is not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Shorten the `Voice profiles now live` entry to two sentences, merge the second `### Changed` block into the first, and reword the `### Fixed` "to pick the best" clause to match README.md (local review; Claude reads only the 15 `--top` samples) · `CHANGELOG.md` · depends: none · tier: junior · success: Unreleased has one `### Changed` heading, the long entry is at most two sentences, the Fixed entry no longer says "to pick the best", and `test_plugin_manifest.py` still passes; never by weakening or deleting a test

## Acceptance criteria

- [ ] Unreleased has exactly one `### Changed` heading and no entry loses its content.
- [ ] The `Voice profiles now live` entry is at most two sentences.
- [ ] The `### Fixed` entry matches README.md on who reads the samples.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.
