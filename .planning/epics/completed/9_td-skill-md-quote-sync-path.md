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

Only the files in the File scope line. Only the Step 6 sync command. The two `allowed-tools` sync patterns stay unquoted (decision 2026-10-30, EST-3330 Q1). The technical-debt list is not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Quote the path in the Step 6 command as `python3 "${CLAUDE_SKILL_DIR}/sync.py"`; update the assertion at `test_skill_md.py:174` first so it fails on the unquoted form; leave both `allowed-tools` sync patterns and their assertions (~178-179) unchanged · `skill/revoice/SKILL.md`, `skill/revoice/tests/test_skill_md.py` · depends: none · tier: junior · success: the Step 6 command quotes `${CLAUDE_SKILL_DIR}/sync.py` and the two `allowed-tools` patterns are byte-identical to before; never by weakening or deleting a test

## Acceptance criteria

- [x] The Step 6 command quotes the sync path; the two sync-specific `allowed-tools` patterns stay unquoted. _(verified 2026-10-30: SKILL.md:115 reads `python3 "${CLAUDE_SKILL_DIR}/sync.py"`; SKILL.md:5 patterns unquoted; test_skill_md.py `test_skill_dir_names_its_own_folder` asserts the quoted form and `test_allowed_tools_use_skill_dir` the unquoted patterns)_
- [x] CI is green. _(verified 2026-10-30: CI success on main 0f3a807, https://github.com/samestrin/revoice-skill/actions/runs/40984534659)_

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.

<!-- refine-epic:begin -->
## Refinements (2026-10-30)
### Auto-applied corrections (1)
- T1 `tier: mid` is not a tier dispatch accepts (senior, junior, intern); set to `junior` (fully specified local edit).
### Items needing user confirmation (1)
- Q1 (answered, see second report): T1 says "check that Claude Code's permission-pattern syntax accepts the quoted form". No test or CI step can prove that, and `allowed-tools` already lists `Bash(python:*)` and `Bash(python3:*)` (SKILL.md:5), which match any python command, so the two sync-specific patterns are redundant today. Needs a decision on how the patterns are handled (see the card).
### Advisory observations (1)
- `test_skill_md.py:174,178,179` are the only assertions on the unquoted form; `SKILL.md:5` and `:115` are the only occurrences. Paths and lines in the plan are accurate.
### Verification context
- Code repo: revoice-skill at e6617fb. Plan written: 2026-10-30. Commits reviewed since: 0
- Tasks: 1 (limit 7). Components: 1 (limit 3): skill/revoice
- Claims checked: 5. Discovery searches: `rg sync.py` in SKILL.md and tests; File scope compared with plans 4, 6, 7, 8 (no shared file) and open PRs (none); no open epic in the project
- Failure modes: none apply: a docs/test edit, no route, data or deploy
- Vision fit: no VISION.md
<!-- refine-epic:end -->

<!-- refine-epic:begin -->
## Refinements (2026-10-30, answers applied)
### Auto-applied corrections (3)
- Q1 answered by a person: option B (EST-3330 card f2acc7e0). T1, Scope and acceptance criterion 1 now quote only the Step 6 command; the two `allowed-tools` patterns stay unquoted.
- T1 no longer asks to verify Claude Code's pattern syntax (untestable), so its success criterion is observable in the repo's tests.
- Added technical-debt row for the redundant sync patterns (`.planning/technical-debt/README.md`, section 2026-10-30).
### Items needing user confirmation (0)
### Advisory observations (0)
### Verification context
- Code repo: revoice-skill at e6617fb. Plan written: 2026-10-30. Commits reviewed since: 0
- Tasks: 1 (limit 7). Components: 1 (limit 3): skill/revoice
- Claims checked: 5. Discovery searches: none new
- Failure modes: none apply: a docs/test edit
- Vision fit: no VISION.md
<!-- refine-epic:end -->
