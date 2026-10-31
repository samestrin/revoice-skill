# Epic Plan 13: SKILL.md duplicate Bash(test:*) in allowed-tools

- **Source:** technical-debt rows (.planning/technical-debt/README.md): skill/revoice/SKILL.md:5
- **File scope:** skill/revoice/SKILL.md, skill/revoice/tests/test_skill_md.py
- **Runs in parallel:** yes. On 2026-10-31, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-31 (written by the CTO from technical-debt rows; not yet refined)

## Why

`allowed-tools` lists `Bash(test:*)` twice. The second entry is noise and hides real differences when the list is edited.

## Current State

`skill/revoice/SKILL.md` line 5 lists `Bash(test:*)` twice (after `Bash(ls:*)` and after `Bash(python3:*)`) on `main` today. Check it again; the row may be stale.

## Proposed Solution

Add a test that each `allowed-tools` entry appears once, watch it fail, then remove the second `Bash(test:*)`. No other change.

## Scope

Only the files in the File scope line. `CHANGELOG.md` and the technical-debt list are not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Remove the second `Bash(test:*)` from `allowed-tools`; first add a test in `test_skill_md.py` that the entries of `allowed-tools` have no duplicates, so it fails before the edit · `skill/revoice/SKILL.md`, `skill/revoice/tests/test_skill_md.py` · depends: none · tier: junior · success: line 5 lists `Bash(test:*)` once, every other entry is unchanged, and the new test passes; never by weakening or deleting a test

## Acceptance criteria

- [ ] `allowed-tools` has no duplicate entries and a test pins it.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.
