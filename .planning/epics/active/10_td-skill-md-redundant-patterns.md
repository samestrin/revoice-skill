# Epic Plan 10: SKILL.md redundant allowed-tools patterns

- **Source:** technical-debt rows (.planning/technical-debt/README.md): skill/revoice/SKILL.md:5
- **File scope:** skill/revoice/SKILL.md, skill/revoice/tests/test_skill_md.py
- **Runs in parallel:** yes. On 2026-10-30, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-30 (written by the CTO from technical-debt rows; not yet refined)

## Why

The `allowed-tools` sync-specific patterns are redundant with `Bash(python:*)` and `Bash(python3:*)` on the same line (EST-3330 Q1 decided they stay unquoted; this epic removes them instead).

## Current State

`SKILL.md` line 5 lists `Bash(python3 ${CLAUDE_SKILL_DIR}/sync.py:*)` and `Bash(python ${CLAUDE_SKILL_DIR}/sync.py:*)` beside `Bash(python:*)` and `Bash(python3:*)`. `test_skill_md.py` `test_allowed_tools_use_skill_dir` (~line 177) asserts the two sync patterns. Check both on `main`; the row may be stale.

## Proposed Solution

Fix the row with a failing test first where a test can fail. No behaviour change beyond what the row asks.

## Scope

Only the files in the File scope line. `CHANGELOG.md` and the technical-debt list are not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Remove the two sync-specific patterns from `allowed-tools` and their two assertions in `test_allowed_tools_use_skill_dir`; first add an assertion that they are absent and that `Bash(python:*)` and `Bash(python3:*)` remain, so it fails before the edit · `skill/revoice/SKILL.md`, `skill/revoice/tests/test_skill_md.py` · depends: none · tier: junior · success: line 5 has no `sync.py` pattern, the two generic python patterns remain, and the Step 6 command is unchanged; never by weakening or deleting a test

## Acceptance criteria

- [ ] The two sync-specific `allowed-tools` patterns are gone and the generic python patterns remain.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.

<!-- refine-epic:begin -->
## Refinements (2026-10-30)
### Auto-applied corrections (0)
### Items needing user confirmation (0)
### Advisory observations (1)
- `skill/revoice/SKILL.md:5` also lists `Bash(test:*)` twice. It is outside this row and the plan, so T1 leaves it alone.
### Verification context
- Code repo: revoice-skill at f49e9a5. Plan written: 2026-10-30. Commits reviewed since: 0 (the last change to either file is 0f3a807, before the plan)
- Tasks: 1 (limit 7). Components: 1 (limit 3): skill/revoice
- Claims checked: 6. SKILL.md:5 has both sync patterns plus `Bash(python:*)` and `Bash(python3:*)`; test_skill_md.py:179-180 asserts the two sync patterns; test_skill_md.py:175 pins the quoted Step 6 command; SKILL.md:115 is that command; both files exist; the row is not stale. Discovery searches: `rg sync.py` in SKILL.md and test_skill_md.py, `rg allowed_tools` in the tests
- Parallel check: the scope (SKILL.md, test_skill_md.py) is named by no other plan in `.planning/epics/active/` (4, 6, 11, 12) and by no open PR (`gh pr list` is empty).
- Failure modes: none apply: the change removes two allow-list entries that the generic python patterns already cover; no route, login, money, data or deploy.
- Vision fit: no VISION.md
<!-- refine-epic:end -->
