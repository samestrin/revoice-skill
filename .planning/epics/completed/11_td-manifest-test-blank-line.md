# Epic Plan 11: plugin manifest test blank line

- **Source:** technical-debt rows (.planning/technical-debt/README.md): skill/revoice/tests/test_plugin_manifest.py:99
- **File scope:** skill/revoice/tests/test_plugin_manifest.py
- **Runs in parallel:** yes. On 2026-10-30, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-30 (written by the CTO from technical-debt rows; not yet refined)

## Why

Two blank lines sit between methods inside `PluginJsonTest`.

## Current State

`test_plugin_manifest.py` has two blank lines before `test_icon_is_a_square_png_in_range` (~line 99). Style only; no test can fail first.

## Proposed Solution

Fix the row with a failing test first where a test can fail. No behaviour change beyond what the row asks.

## Scope

Only the files in the File scope line. `CHANGELOG.md` and the technical-debt list are not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Remove one of the two blank lines before `test_icon_is_a_square_png_in_range` · `skill/revoice/tests/test_plugin_manifest.py` · depends: none · tier: intern · success: one blank line separates the methods and the test count is unchanged; never by weakening or deleting a test

## Acceptance criteria

- [x] One blank line separates the methods in `PluginJsonTest`. _(verified 2026-10-30: `skill/revoice/tests/test_plugin_manifest.py:99-100` on main has one blank line before `test_icon_is_a_square_png_in_range`, commit 0de30cf)_
- [x] CI is green. _(verified 2026-10-30: CI run 41001601683 on main at 0de30cf succeeded; 130 tests pass locally)_

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.

<!-- refine-epic:begin -->
## Refinements (2026-10-30)
### Auto-applied corrections (0)
### Items needing user confirmation (0)
### Advisory observations (1)
- `.planning/epics/active/4_td-manifest-tests-and-icon.md` still sits in `active/` although `completed/4_td-manifest-tests-and-icon.md` exists on `main` (shipped in #39, #40). It lists the same test file, but it is not in flight, so it does not block this epic. Not touched here.
### Verification context
- Code repo: revoice-skill at f49e9a5. Plan written: 2026-10-30. Commits reviewed since: 0
- Tasks: 1 (limit 7). Components: 1 (limit 3): skill/revoice/tests
- Claims checked: 3. `test_plugin_manifest.py:99-100` are two blank lines before `test_icon_is_a_square_png_in_range` (line 101); the file has 11 `def test_`; `unittest discover` runs 130 tests, OK. Discovery searches: rg for the file across active plans and the technical-debt row (row 1, `[/]`, epic 11).
- Parallel exception (step 0): scope `skill/revoice/tests/test_plugin_manifest.py` shared with no other active plan except the shipped epic 4 file above; no open PRs (`gh pr list`); no open `Epic` issues in the project. Scope not widened.
- Failure modes: none apply: a whitespace-only edit to a test file.
- Vision fit: no VISION.md
<!-- refine-epic:end -->
