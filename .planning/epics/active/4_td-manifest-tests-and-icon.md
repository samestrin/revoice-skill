# Epic Plan 4: Plugin manifest tests and icon

- **Source:** technical-debt rows (.planning/technical-debt/README.md): skill/revoice/tests/test_plugin_manifest.py:28, skill/revoice/tests/test_plugin_manifest.py:80, .claude-plugin/plugin.json:1
- **File scope:** skill/revoice/tests/test_plugin_manifest.py, .claude-plugin/plugin.json, .claude-plugin/icon.png (new)
- **Runs in parallel:** yes. On 2026-10-29, no file in the scope was in another open epic or open PR.
- **Base branch: `main`.** Every PR targets `main`.
- **Estimated time**: under 1 day
- **Last modified**: 2026-10-29 (written by the CTO from technical-debt rows; not yet refined)

## Why

Three LOW rows left by epic 3's reviews: the manifest test helpers have unexercised guards, one test repeats others, and the plugin has no icon (`ICON_MISSING` from `claude plugin validate`).

## Current State

`test_plugin_manifest.py` has helpers `newest_released_version` and `skill_md_version` that raise `AssertionError` in three guard branches (lines 28, 36, 41) that no test feeds bad input. `test_skill_md_version_reads_quoted_value` (line ~80) only asserts a semver regex, which the version-match tests already prove. `.claude-plugin/plugin.json` has no icon field.

## Proposed Solution

Fix each row with a failing test first. No behaviour change beyond what the rows ask.

## Scope

Only the files in the File scope line. `CHANGELOG.md` and the technical-debt list are not edited by this epic (`close-epic` edits the list).

## Tasks (canonical)

- **T1** — Guard tests: make the helpers take the text/path as a parameter (or accept a root override) so each of the three `AssertionError` guards is hit by a test with bad input (no released heading, no frontmatter, no `metadata.version`); drop `test_skill_md_version_reads_quoted_value` or fold its assertion into the version-match tests · `skill/revoice/tests/test_plugin_manifest.py` · depends: none · tier: junior · success: three new tests fail before the helper change and pass after; the redundant test is gone with no loss of assertion; never by weakening or deleting a test beyond the one named row
- **T2** — Icon: add an icon file to `.claude-plugin/` and reference it in `plugin.json` per the current Claude Code plugin docs; extend the manifest test to check the referenced file exists · `.claude-plugin/plugin.json`, `.claude-plugin/icon.png`, `skill/revoice/tests/test_plugin_manifest.py` · depends: T1 · tier: junior · success: the new test fails without the file, and `claude plugin validate . --strict` no longer reports `ICON_MISSING` (output pasted on the PR); never by weakening or deleting a test

## Acceptance criteria

- [ ] Each of the three guards has a test that feeds it bad input.
- [ ] The repeated test is dropped or folded in.
- [ ] `plugin.json` references an icon that exists, and a test pins it.
- [ ] CI is green.

## Repo rules

- Never run `deploy.sh`; never write to `~/.claude/skills/` or `~/.agents/skills/`.
- Every task ends green on `python3 -m unittest discover -s skill/revoice/tests`, never by weakening or deleting a test.
