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
