# Epic Plan 9: SKILL.md quoted sync path

- **Source:** technical-debt rows (.planning/technical-debt/README.md): skill/revoice/SKILL.md:115
- **File scope:** skill/revoice/SKILL.md, skill/revoice/tests/test_skill_md.py
- **Runs in parallel:** yes. On 2026-10-30, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-30 (written by the CTO from technical-debt rows; not yet refined)

## Why

`python3 ${CLAUDE_SKILL_DIR}/sync.py` is unquoted in the Step 6 command and the `allowed-tools` patterns match the unquoted form, so a skill path with spaces breaks.

## Current State

`SKILL.md` Step 6 (~line 115) shows the unquoted command, and `allowed-tools` (line 5) has `Bash(python3 ${CLAUDE_SKILL_DIR}/sync.py:*)` and the `python` twin. `test_skill_md.py` asserts the unquoted forms at ~174 and ~178-179.

## Proposed Solution

Fix each row with a failing test first where a test can fail. No behaviour change beyond what the rows ask.

## Scope

Only the files in the File scope line. Only the sync command and its two allowed-tools patterns. The technical-debt list is not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Quote the path in the Step 6 command and in both `allowed-tools` patterns; update the assertions in `test_skill_md.py` first so they fail on the unquoted form; check that Claude Code's permission-pattern syntax accepts the quoted form · `skill/revoice/SKILL.md`, `skill/revoice/tests/test_skill_md.py` · depends: none · tier: mid · success: the command and both patterns quote `${CLAUDE_SKILL_DIR}/sync.py` consistently; never by weakening or deleting a test

## Acceptance criteria

- [ ] The Step 6 command and both `allowed-tools` patterns quote the sync path.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.
