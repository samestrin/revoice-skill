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

- **T1** — Quote the path in the Step 6 command and in both `allowed-tools` patterns; update the assertions in `test_skill_md.py` first so they fail on the unquoted form; check that Claude Code's permission-pattern syntax accepts the quoted form · `skill/revoice/SKILL.md`, `skill/revoice/tests/test_skill_md.py` · depends: none · tier: junior · success: the command and both patterns quote `${CLAUDE_SKILL_DIR}/sync.py` consistently; never by weakening or deleting a test

## Acceptance criteria

- [ ] The Step 6 command and both `allowed-tools` patterns quote the sync path.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.

<!-- refine-epic:begin -->
## Refinements (2026-10-30)
### Auto-applied corrections (1)
- T1 `tier: mid` is not a tier dispatch accepts (senior, junior, intern); set to `junior` (fully specified local edit).
### Items needing user confirmation (1)
- Q1: T1 says "check that Claude Code's permission-pattern syntax accepts the quoted form". No test or CI step can prove that, and `allowed-tools` already lists `Bash(python:*)` and `Bash(python3:*)` (SKILL.md:5), which match any python command, so the two sync-specific patterns are redundant today. Needs a decision on how the patterns are handled (see the card).
### Advisory observations (1)
- `test_skill_md.py:174,178,179` are the only assertions on the unquoted form; `SKILL.md:5` and `:115` are the only occurrences. Paths and lines in the plan are accurate.
### Verification context
- Code repo: revoice-skill at e6617fb. Plan written: 2026-10-30. Commits reviewed since: 0
- Tasks: 1 (limit 7). Components: 1 (limit 3): skill/revoice
- Claims checked: 5. Discovery searches: `rg sync.py` in SKILL.md and tests; File scope compared with plans 4, 6, 7, 8 (no shared file) and open PRs (none); no open epic in the project
- Failure modes: none apply: a docs/test edit, no route, data or deploy
- Vision fit: no VISION.md
<!-- refine-epic:end -->
